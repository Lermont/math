"""One fresh OS process per measured run. Imports and dataset I/O timed externally."""
from __future__ import annotations
import argparse
import json
import os
import traceback
from pathlib import Path
from time import perf_counter
import numpy as np
import scipy
import kmedoids
import psutil
from onebatch import OneBatchPAM
from threadpoolctl import threadpool_limits, threadpool_info
from kmedian125.data import distance_matrix, independent_cost, write_json
from kmedian125.methods import cost, greedy, local_search, lp_dr_swap, exact_enumeration, solve_milp

def main():
    parser = argparse.ArgumentParser()
    for name in ("dataset", "config", "output", "method", "mode"):
        parser.add_argument("--"+name, required=True)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--core", type=int, required=True)
    args = parser.parse_args()
    process = psutil.Process()
    process.cpu_affinity([args.core])
    threadpool_limits(limits=1)
    ds = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    n, k = ds["n"], ds["k"]
    d = np.load(Path(args.dataset).with_suffix(".npy")) if args.mode == "shared" else None
    baseline_rss = process.memory_info().rss
    result = dict(dataset=ds["name"], method=args.method, seed=args.seed, mode=args.mode,
                  n=n, k=k, baseline_rss_bytes=baseline_rss, cpu_affinity=process.cpu_affinity())
    start = perf_counter()
    stages = {}
    info = {}
    try:
        if args.method.startswith("onebatch"):
            batch = min(n, max(k, 64)) if args.method == "onebatch64" else min(n, max(k, int(100*np.log(max(2, n*k)))))
            rng = np.random.default_rng(args.seed)
            columns = rng.choice(n, batch, replace=False)
            dist_start = perf_counter()
            sampled = distance_matrix(ds, columns) if d is None else d[:, columns]
            stages["distance"] = perf_counter()-dist_start
            fit_start = perf_counter()
            model = OneBatchPAM(n_medoids=k, distance="precomputed", weighting=True,
                                normalize=True, max_iter=cfg["max_iter"], tol=1e-6,
                                n_jobs=1, random_state=rng).fit(sampled)
            meds = list(map(int, model.medoid_indices_))
            stages["fit"] = perf_counter()-fit_start
            info = dict(batch_size=batch, batch_indices=columns.tolist(), n_iter=int(model.n_iter_),
                        package_inertia=float(model.inertia_), weighting=True, normalize=True,
                        package_inertia_is_full_objective=False)
            payload = sampled.nbytes
        else:
            dist_start = perf_counter()
            if d is None:
                d = distance_matrix(ds)
            stages["distance"] = perf_counter()-dist_start
            payload = d.nbytes
            fit_start = perf_counter()
            if args.method == "fasterpam":
                # Conversion to the package's dense f64 input counts in fit.
                model = kmedoids.fasterpam(d.astype(np.float64), k, random_state=args.seed,
                                           max_iter=cfg["max_iter"], n_cpu=1)
                meds = list(map(int, model.medoids))
                info = dict(n_iter=int(model.n_iter), n_swap=int(model.n_swap), package_loss=float(model.loss))
                stages["fit"] = perf_counter()-fit_start
            elif args.method == "greedy_swap":
                initial = greedy(d, k)
                initialized = perf_counter()
                meds, trace, converged = local_search(d, initial, cfg["max_swaps"])
                stages.update(greedy=initialized-fit_start, local_search=perf_counter()-initialized)
                info = dict(local_trace=trace, local_optimum=converged)
            elif args.method == "lp_dr16_swap":
                meds, info = lp_dr_swap(d, k, args.seed, cfg)
                stages.update(info.pop("stages"))
            elif args.method == "enumeration":
                meds, val, count = exact_enumeration(d, k)
                stages["enumeration"] = perf_counter()-fit_start
                info = dict(proven_optimum=val, combinations_checked=count)
            elif args.method == "milp":
                meds, info = solve_milp(d, k, cfg["solver_seconds"])
                stages["milp_model_and_solve"] = perf_counter()-fit_start
                if meds is None:
                    raise RuntimeError("MILP returned no incumbent")
            else:
                raise ValueError(args.method)
        finished = perf_counter()
        independent = independent_cost(ds, meds)
        if d is not None:
            assert cost(d, meds) == independent
        if "package_loss" in info:
            assert abs(info["package_loss"]-independent) < 1e-7
        if "certificate" in info:
            assert info["certificate"]["integer_lower_bound"] <= independent
        checked = perf_counter()
        stages["verification"] = checked-finished
        result.update(status="ok", cost=independent, medoids=meds, center_count=len(meds),
                      algorithm_seconds=finished-start, verified_seconds=checked-start,
                      distance_payload_bytes=payload, info=info)
    except Exception as exc:
        result.update(status="error", error=str(exc), traceback=traceback.format_exc(),
                      algorithm_seconds=perf_counter()-start)
    result["stages"] = stages
    memory = process.memory_info()
    result["peak_working_set_bytes"] = getattr(memory, "peak_wset", memory.rss)
    result["final_rss_bytes"] = memory.rss
    result["threadpools"] = threadpool_info()
    write_json(args.output, result)

if __name__ == "__main__":
    main()
