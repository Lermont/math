"""Bounded sequential experiment; never overwrite an existing run directory."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from time import perf_counter, sleep
import numpy as np
import psutil
from kmedian125.data import ROOT, digest, distance_matrix, independent_cost, real_seeds, synthetic, validate_metric, write_json

def run_one(ds_path, run, method, seed, mode, cfg, core):
    ident = f"{ds_path.stem}__{method}__{seed}__{mode}"
    output = run/"raw"/(ident+".json")
    logfile = run/"logs"/(ident+".txt")
    cmd = [sys.executable, "-m", "kmedian125.worker", "--dataset", str(ds_path),
           "--config", str(run/"config.json"), "--output", str(output), "--method", method,
           "--seed", str(seed), "--mode", mode, "--core", str(core)]
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               NUMEXPR_NUM_THREADS="1", RAYON_NUM_THREADS="1", PYTHONHASHSEED="0")
    start = perf_counter()
    with logfile.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        psproc = psutil.Process(process.pid)
        psproc.cpu_affinity([core])
        status = None
        sampled_peak = 0
        while process.poll() is None:
            try:
                rss = psproc.memory_info().rss
                sampled_peak = max(sampled_peak, rss)
                if rss > cfg["process_rss_limit_bytes"]:
                    status = "rss_limit"
                elif perf_counter()-start > cfg["process_seconds"]:
                    status = "time_limit"
                if status:
                    process.kill()
                    process.wait()
                    break
            except psutil.NoSuchProcess:
                break
            sleep(.02)
    elapsed = perf_counter()-start
    if output.exists():
        result = json.loads(output.read_text(encoding="utf-8"))
    else:
        ds = json.loads(ds_path.read_text(encoding="utf-8"))
        result = dict(dataset=ds["name"], method=method, seed=seed, mode=mode,
                      n=ds["n"], k=ds["k"], status=status or "process_error")
    result.update(process_wall_seconds=elapsed, exit_code=process.returncode,
                  sampled_peak_rss_bytes=sampled_peak)
    if result["status"] == "ok":
        ds = json.loads(ds_path.read_text(encoding="utf-8"))
        assert independent_cost(ds, result["medoids"]) == result["cost"]
    # The worker result is finalized once, retaining all failure statuses.
    write_json(output, result)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("pilot-%Y%m%dT%H%M%SZ"))
    args = parser.parse_args()
    run = ROOT/"results/kmedian125"/args.run_id
    if run.exists():
        raise SystemExit("Refusing to overwrite an existing run; choose a new --run-id")
    for sub in ("raw", "logs", "datasets", "source-snapshot"):
        (run/sub).mkdir(parents=True)
    cfg = json.loads((ROOT/"kmedian125/config.json").read_text(encoding="utf-8"))
    write_json(run/"config.json", cfg)
    sources = {}
    for path in sorted((ROOT/"kmedian125").glob("*")):
        if path.is_file() and path.suffix in (".py", ".json", ".md", ".txt"):
            sources[path.name] = digest(path)
            (run/"source-snapshot"/path.name).write_bytes(path.read_bytes())
    core = psutil.Process().cpu_affinity()[0]
    packages = {name: importlib.metadata.version(name) for name in
                ("numpy", "scipy", "kmedoids", "onebatch", "psutil", "scikit-learn", "threadpoolctl")}
    write_json(run/"environment.json", dict(python=sys.version, executable=sys.executable,
               os=platform.platform(), processor=platform.processor(), cpu_count=psutil.cpu_count(),
               physical_cores=psutil.cpu_count(logical=False), total_ram=psutil.virtual_memory().total,
               logical_cpu=core, packages=packages, source_sha256=sources,
               sources_manifest_sha256=digest(ROOT/"references/kmedian125/sources.json"),
               started_utc=datetime.now(timezone.utc).isoformat()))
    started = perf_counter()
    datasets = []
    for structure in cfg["structures"]:
        for seed in cfg["small_data_seeds"]:
            datasets.append(synthetic(structure, cfg["small_n"], cfg["small_k"], seed))
    for structure in cfg["structures"]:
        for k in cfg["medium_ks"]:
            datasets.append(synthetic(structure, cfg["medium_n"], k, cfg["medium_data_seed"]))
    datasets += [real_seeds(k) for k in cfg["real_ks"]]
    dataset_manifest = []
    for ds in datasets:
        ds_path = run/"datasets"/(ds["name"]+".json")
        write_json(ds_path, ds)
        t = perf_counter()
        d = distance_matrix(ds)
        construction = perf_counter()-t
        validate_metric(d)
        np.save(ds_path.with_suffix(".npy"), d, allow_pickle=False)
        dataset_manifest.append(dict(name=ds["name"], kind=ds["kind"], n=ds["n"], k=ds["k"],
                                     json_sha256=digest(ds_path), matrix_sha256=digest(ds_path.with_suffix(".npy")),
                                     matrix_payload_bytes=d.nbytes, construction_seconds=construction,
                                     metric_triangle_check="all triples pass"))
    write_json(run/"datasets.json", dataset_manifest)
    rows = []
    tasks = []
    # All small exact certificates are obtained before any heuristic benchmark.
    for ds in datasets[:8]:
        for method in ("enumeration", "milp"):
            tasks.append((ds, method, 101, "fresh"))
    for ds in datasets:
        modes = ["fresh"] if ds["n"] == cfg["small_n"] else ["fresh", "shared"]
        for mode in modes:
            for method in cfg["methods"]:
                seeds = [101] if method == "greedy_swap" else cfg["algorithm_seeds"]
                for seed in seeds:
                    tasks.append((ds, method, seed, mode))
    for index, (ds, method, seed, mode) in enumerate(tasks):
        if perf_counter()-started > cfg["suite_seconds"]:
            write_json(run/"budget-stop.json", dict(completed=len(rows), scheduled=len(tasks)))
            break
        ds_path = run/"datasets"/(ds["name"]+".json")
        result = run_one(ds_path, run, method, seed, mode, cfg, core)
        rows.append(result)
        with (run/"raw.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False)+"\n")
        print(f"{index+1}/{len(tasks)} {ds['name']} {method} seed={seed} {mode}: "
              f"{result['status']} cost={result.get('cost')} t={result.get('algorithm_seconds', 0):.4f}s", flush=True)
    write_json(run/"completion.json", dict(completed=len(rows), scheduled=len(tasks),
               successful=sum(r["status"] == "ok" for r in rows), elapsed_seconds=perf_counter()-started,
               ended_utc=datetime.now(timezone.utc).isoformat()))
    print(f"RESULTS: {run}", flush=True)

if __name__ == "__main__":
    main()
