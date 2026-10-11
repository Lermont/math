"""Fresh-process native package benchmark; no shared distance cache."""
from __future__ import annotations
from time import perf_counter
IMPORT_START = perf_counter()
import argparse
import json
import traceback
from pathlib import Path
import numpy as np
import kmedoids
import psutil
from onebatch import OneBatchPAM
from threadpoolctl import threadpool_limits, threadpool_info
from .core import l1_f32, score_integer, batch_for, write_json, digest
IMPORT_SECONDS = perf_counter() - IMPORT_START


def peak(process):
    m = process.memory_info()
    return int(getattr(m, "peak_wset", m.rss))


def main():
    p = argparse.ArgumentParser()
    for name in ("dataset", "config", "output", "method"):
        p.add_argument("--" + name, required=True)
    for name in ("seed", "core", "k"):
        p.add_argument("--" + name, type=int, required=True)
    args = p.parse_args()
    process = psutil.Process()
    process.cpu_affinity([args.core])
    threadpool_limits(limits=1)
    t = perf_counter()
    ds = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    x = np.load(Path(args.dataset).with_suffix(".npy"), allow_pickle=False)
    groups = np.load(Path(args.dataset).with_name(Path(args.dataset).stem + "-groups.npy"), allow_pickle=False)
    load_seconds = perf_counter() - t
    n, k = len(x), args.k
    batch = batch_for(args.method, n, k)
    result = dict(dataset=ds["name"], structure=ds["structure"], data_seed=ds["seed"], n=n,
                  k=k, method=args.method, seed=args.seed, batch_size=batch,
                  import_seconds=IMPORT_SECONDS, load_seconds=load_seconds,
                  cpu_affinity=process.cpu_affinity(), baseline_rss_bytes=process.memory_info().rss,
                  baseline_peak_bytes=peak(process), matrix_payload_bytes=4*n*batch,
                  system_available_before=psutil.virtual_memory().available)
    stages, info = {}, {}
    cpu_start = sum(process.cpu_times()[:2])
    start = perf_counter()
    try:
        if args.method == "fasterpam":
            td = perf_counter()
            dist = l1_f32(x, x, cfg["distance_block_rows"])
            stages["distance_seconds"] = perf_counter() - td
            tf = perf_counter()
            model = kmedoids.fasterpam(dist, k, max_iter=cfg["max_iter"], init="random",
                                       random_state=args.seed, n_cpu=1)
            stages["fit_seconds"] = perf_counter() - tf
            meds = list(map(int, model.medoids))
            info.update(n_iter=int(model.n_iter), n_swap=int(model.n_swap),
                        package_loss=float(model.loss), sampled_indices=None)
        else:
            # Native wrapper performs sampling, conversion, normalization and weighting.
            captured = {}

            def distance(a, b, n_jobs):
                td = perf_counter()
                value = l1_f32(a, b, cfg["distance_block_rows"])
                stages["distance_seconds"] = perf_counter() - td
                captured["sampled_coordinates"] = b
                captured["shape"] = list(value.shape)
                return value

            model = OneBatchPAM(n_medoids=k, distance=distance,
                                batch_size="auto" if args.method == "onebatch_auto" else batch,
                                weighting=True, normalize=True, max_iter=cfg["max_iter"],
                                tol=cfg["tol"], n_jobs=1, random_state=args.seed).fit(x)
            meds = list(map(int, model.medoid_indices_))
            info.update(n_iter=int(model.n_iter_), package_inertia=float(model.inertia_),
                        package_inertia_is_full_objective=False, weighting=True, normalize=True,
                        package_label_count=len(model.labels_), distance_shape=captured["shape"])
        fitted = perf_counter()
        result["algorithm_peak_working_set_bytes"] = peak(process)
        result["algorithm_cpu_seconds"] = sum(process.cpu_times()[:2]) - cpu_start
        result["algorithm_seconds"] = fitted - start
        if args.method != "fasterpam":
            stages["fit_seconds"] = result["algorithm_seconds"] - stages["distance_seconds"]
            rng = np.random.default_rng(args.seed)
            columns = rng.choice(n, batch, replace=False)
            assert np.array_equal(captured["sampled_coordinates"], x[columns])
            assert captured["shape"] == [n, batch]
            info["sampled_indices"] = columns.tolist()
            info["initial_medoids"] = rng.choice(n, k, replace=False).tolist()
            rare_sample = groups[columns][groups[columns] >= 0]
            info["sampled_rare_count"] = len(rare_sample)
            info["sampled_rare_groups"] = sorted(set(map(int, rare_sample)))
        else:
            info["initial_medoids"] = np.random.RandomState(args.seed).choice(n, k, False).tolist()
        tv = perf_counter()
        assert len(meds) == k
        quality, nearest, labels = score_integer(x, groups, meds)
        stages["full_assignment_seconds"] = perf_counter() - tv
        if args.method == "fasterpam":
            assert quality["cost"] == info["package_loss"]
            assert np.array_equal(dist[np.arange(n), np.asarray(meds)[model.labels]], nearest)
        rare_indices = np.flatnonzero(groups >= 0)
        quality["rare_indices"] = rare_indices.tolist()
        quality["rare_group_ids"] = groups[rare_indices].tolist()
        result.update(status="ok", medoids=meds, quality=quality, info=info,
                      algorithm_and_assignment_seconds=result["algorithm_seconds"] + stages["full_assignment_seconds"],
                      verified_seconds=perf_counter()-start,
                      iteration_limit_reached=info["n_iter"] >= cfg["max_iter"])
        assignment_path = Path(args.output).with_suffix(".npz")
        np.savez(assignment_path, nearest=nearest, assigned_medoid=labels)
        result["assignment_sha256"] = digest(assignment_path)
    except Exception as exc:
        result.update(status="error", error=str(exc), traceback=traceback.format_exc())
    result.update(stages=stages, whole_process_peak_working_set_bytes=peak(process),
                  final_rss_bytes=process.memory_info().rss, threadpools=threadpool_info(),
                  system_available_after=psutil.virtual_memory().available)
    write_json(args.output, result)


if __name__ == "__main__":
    main()
