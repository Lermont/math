"""Prespecified sequential, randomized fresh-process scale experiment."""
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
from .core import ROOT, make_dataset, write_json, digest, score_integer

HERE = Path(__file__).resolve().parent


def prepare(run):
    for name in ("datasets", "raw", "logs", "source-snapshot"):
        (run/name).mkdir(parents=True)
    cfg = json.loads((HERE/"config.json").read_text(encoding="utf-8"))
    write_json(run/"config.json", cfg)
    sources = {}
    for path in sorted(HERE.iterdir()):
        if path.is_file() and path.suffix in (".py", ".md", ".json"):
            sources[path.name] = digest(path)
            (run/"source-snapshot"/path.name).write_bytes(path.read_bytes())
    datasets, tasks = {}, []

    def add(structure, n, data_seed, k, methods, grid):
        name = f"{structure}_n{n}_s{data_seed}"
        if name not in datasets:
            x, groups = make_dataset(structure, n, data_seed)
            stem = run/"datasets"/name
            np.save(stem.with_suffix(".npy"), x, allow_pickle=False)
            group_path = stem.with_name(name + "-groups.npy")
            np.save(group_path, groups, allow_pickle=False)
            ds = dict(name=name, n=n, structure=structure, seed=data_seed, dimensions=x.shape[1],
                      metric="integer_l1", unique_points=len(np.unique(x, axis=0)),
                      rare_count=int(np.count_nonzero(groups >= 0)),
                      features_sha256=digest(stem.with_suffix(".npy")), groups_sha256=digest(group_path),
                      max_possible_distance=int(np.ptp(x.astype(np.int64), axis=0).sum()))
            assert ds["unique_points"] == n
            assert ds["max_possible_distance"] < 2**24
            write_json(stem.with_suffix(".json"), ds)
            ds["json_sha256"] = digest(stem.with_suffix(".json"))
            datasets[name] = ds
        for seed in cfg["algorithm_seeds"]:
            for method in methods:
                ident = f"{name}__k{k}__{method}__s{seed}"
                tasks.append(dict(id=ident, dataset=name, structure=structure, data_seed=data_seed,
                                  n=n, k=k, method=method, seed=seed, grid=grid))

    for n in cfg["sizes"]:
        for structure in cfg["structures"]:
            for ds in cfg["data_seeds"]:
                add(structure, n, ds, cfg["k"], cfg["methods"], "main")
                if n in cfg["sweep_sizes"]:
                    add(structure, n, ds, cfg["k"], cfg["sweep_methods"], "batch_sweep")
    for n in cfg["sensitivity_sizes"]:
        for structure in cfg["structures"]:
            for ds in cfg["sensitivity_data_seeds"]:
                add(structure, n, ds, cfg["sensitivity_k"], cfg["sensitivity_methods"], "k_sensitivity")
    assert len(tasks) == len({t["id"] for t in tasks}) == 576
    perm = np.random.default_rng(cfg["schedule_seed"]).permutation(len(tasks))
    tasks = [tasks[int(i)] for i in perm]
    write_json(run/"datasets.json", list(datasets.values()))
    write_json(run/"schedule.json", tasks)
    site = Path(importlib.metadata.distribution("onebatch").locate_file(""))
    installed = {}
    for pkg in ("onebatch", "kmedoids"):
        for p in sorted((site/pkg).rglob("*")):
            if p.is_file() and p.suffix in (".py", ".pyd", ".pyx"):
                installed[str(p.relative_to(site))] = digest(p)
    original = ROOT/"results/kmedian125/pilot-20261011-v1"
    original_env = json.loads((original/"environment.json").read_text(encoding="utf-8"))
    for name, expected in original_env["source_sha256"].items():
        assert digest(ROOT/"kmedian125"/name) == expected
        assert digest(original/"source-snapshot"/name) == expected
    core = psutil.Process().cpu_affinity()[0]
    env = dict(started_utc=datetime.now(timezone.utc).isoformat(), python=sys.version,
               executable=sys.executable, platform=platform.platform(), processor=platform.processor(),
               logical_cpu=core, logical_cpus=psutil.cpu_count(), physical_cores=psutil.cpu_count(False),
               total_ram=psutil.virtual_memory().total, available_ram=psutil.virtual_memory().available,
               packages={p: importlib.metadata.version(p) for p in
                         ("numpy", "scipy", "kmedoids", "onebatch", "psutil", "scikit-learn", "threadpoolctl")},
               source_sha256=sources, installed_package_sha256=installed,
               sources_manifest_sha256=digest(ROOT/"references/kmedian125/sources.json"),
               original_pilot_raw_sha256=digest(original/"raw.jsonl"),
               original_pilot_inputs_unchanged=True, schedule_sha256=digest(run/"schedule.json"),
               matrix_cache=False, threads=1)
    write_json(run/"environment.json", env)
    return cfg, tasks, env


def run_one(run, task, cfg, core):
    output = run/"raw"/(task["id"] + ".json")
    cmd = [sys.executable, "-m", "kmedian125.scale.worker", "--dataset",
           str(run/"datasets"/(task["dataset"]+".json")), "--config", str(run/"config.json"),
           "--output", str(output), "--method", task["method"], "--seed", str(task["seed"]),
           "--k", str(task["k"]), "--core", str(core)]
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               NUMEXPR_NUM_THREADS="1", RAYON_NUM_THREADS="1", PYTHONHASHSEED="0")
    started = perf_counter()
    status, sampled_peak = None, 0
    with (run/"logs"/(task["id"]+".txt")).open("w", encoding="utf-8") as log:
        child = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        proc = psutil.Process(child.pid)
        proc.cpu_affinity([core])
        while child.poll() is None:
            try:
                rss = proc.memory_info().rss
                sampled_peak = max(sampled_peak, rss)
                if rss > cfg["process_rss_limit_bytes"]:
                    status = "rss_limit"
                elif perf_counter()-started > cfg["process_seconds"]:
                    status = "time_limit"
                if status:
                    child.kill()
                    child.wait()
                    break
            except psutil.NoSuchProcess:
                break
            sleep(.02)
        # A process can exit between poll() and memory_info(); always reap it.
        child.wait()
    elapsed = perf_counter()-started
    if output.exists():
        result = json.loads(output.read_text(encoding="utf-8"))
    else:
        result = dict(status=status or "process_error")
    result.update(task, process_wall_seconds=elapsed, exit_code=child.returncode,
                  controller_sampled_peak_rss_bytes=sampled_peak,
                  finished_utc=datetime.now(timezone.utc).isoformat())
    if result["status"] == "ok" and child.returncode != 0:
        result["status"] = "nonzero_process_exit"
    if result["status"] == "ok":
        x = np.load(run/"datasets"/(task["dataset"]+".npy"), allow_pickle=False)
        groups = np.load(run/"datasets"/(task["dataset"]+"-groups.npy"), allow_pickle=False)
        assert score_integer(x, groups, result["medoids"])[0]["cost"] == result["quality"]["cost"]
    write_json(output, result)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()
    if Path(args.run_id).name != args.run_id or "/" in args.run_id or "\\" in args.run_id:
        raise SystemExit("--run-id must be a directory name, not a path")
    run = ROOT/"results/kmedian125"/args.run_id
    if args.resume:
        cfg = json.loads((run/"config.json").read_text(encoding="utf-8"))
        tasks = json.loads((run/"schedule.json").read_text(encoding="utf-8"))
        env = json.loads((run/"environment.json").read_text(encoding="utf-8"))
        for name, expected in env["source_sha256"].items():
            assert digest(HERE/name) == digest(run/"source-snapshot"/name) == expected
        assert digest(run/"schedule.json") == env["schedule_sha256"]
    else:
        if run.exists():
            raise SystemExit("Refusing to overwrite existing output; use a new run-id or --resume")
        cfg, tasks, env = prepare(run)
    started = perf_counter()
    rows = []
    for index, task in enumerate(tasks):
        existing = run/"raw"/(task["id"]+".json")
        if existing.exists():
            record = json.loads(existing.read_text(encoding="utf-8"))
            if "id" in record:
                rows.append(record)
                continue
            raise RuntimeError("Unfinalized worker output needs explicit recovery: " + str(existing))
        if perf_counter()-started > cfg["suite_seconds"]:
            break
        result = run_one(run, task, cfg, env["logical_cpu"])
        rows.append(result)
        with (run/"progress.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(id=task["id"], status=result["status"],
                                        completed=len(rows), scheduled=len(tasks),
                                        elapsed_seconds=perf_counter()-started)) + "\n")
        q = result.get("quality", {})
        print(f"{index+1}/{len(tasks)} {task['id']}: {result['status']} "
              f"t={result.get('algorithm_seconds', 0):.4f}s cost={q.get('cost')} "
              f"rare={q.get('rare_groups_covered')}/{q.get('rare_groups_total')}", flush=True)
    (run/"raw.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False)+"\n" for r in rows), encoding="utf-8")
    write_json(run/"completion.json", dict(completed=len(rows), scheduled=len(tasks),
               successful=sum(r["status"] == "ok" for r in rows), elapsed_this_session=perf_counter()-started,
               ended_utc=datetime.now(timezone.utc).isoformat()))
    print("RESULTS: " + str(run), flush=True)


if __name__ == "__main__":
    main()
