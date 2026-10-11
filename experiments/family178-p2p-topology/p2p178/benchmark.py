"""Serial subprocess benchmark; every attempted candidate is retained."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

import psutil

from .graphs import generate, graph_bytes, load_graph, seed_for, spectrum, structure
from .simulate import make_trace, simulate

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n", "utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Memory:
    """Absolute process memory, not just Python allocation tracing."""
    def __enter__(self):
        self.process = psutil.Process()
        self.baseline = self.process.memory_info().rss
        self.sampled = self.baseline
        self.stop = threading.Event()

        def sample():
            while not self.stop.wait(.01):
                self.sampled = max(self.sampled, self.process.memory_info().rss)

        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join()
        info = self.process.memory_info()
        self.sampled = max(self.sampled, info.rss)
        peak = getattr(info, "peak_wset", self.sampled)
        self.result = {"baseline_rss_bytes": self.baseline, "peak_rss_bytes": peak,
                       "sampled_peak_rss_bytes": self.sampled,
                       "peak_increment_from_baseline_bytes": max(0, peak - self.baseline),
                       "method": "Windows peak_wset (whole process)" if hasattr(info, "peak_wset")
                                 else "sampled RSS, 10ms; may miss peaks",
                       "includes_interpreter_and_imports": True}


def build_worker(config, job, directory):
    # Load numerical dependencies BEFORE timing, consistently for every method.
    import numpy  # noqa: F401
    from scipy.sparse.linalg import eigsh  # noqa: F401

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    attempts = []
    selected = None
    with Memory() as memory:
        started = time.perf_counter()
        for index in range(config["max_candidates"] if job["method"] == "spectral_rejection" else 1):
            began = time.perf_counter()
            graph = generate(job["method"], job["n"], job["d"], job["seed"], index)
            generated = time.perf_counter()
            validation = structure(graph, job["n"], job["d"])
            checked = time.perf_counter()
            spec, error = None, None
            if validation["valid"]:
                try:
                    spec = spectrum(graph, tol=config["eig_tol"], residual_limit=config["residual_limit"],
                                    margin=config["spectral_margin"])
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
            spectral_done = time.perf_counter()
            raw = graph_bytes(graph)
            graph_file = directory / f"candidate-{index:02d}.json"
            graph_file.write_bytes(raw)
            accepted = validation["valid"] and spec is not None and spec["residual_ok"]
            if job["method"] == "spectral_rejection":
                accepted = accepted and not validation["bipartite"] and spec["numeric_pass"]
            attempt = {
                "candidate": index, "generator_seed": seed_for(job["seed"], job["n"], job["d"], "candidate", index),
                "graph_file": str(graph_file.relative_to(directory)), "graph_sha256": hashlib.sha256(raw).hexdigest(),
                "graph_bytes": len(raw), "structure": validation, "spectrum": spec, "error": error,
                "generation_seconds": generated - began, "structure_seconds": checked - generated,
                "spectral_seconds": spectral_done - checked, "serialization_seconds": time.perf_counter() - spectral_done,
                "selected": bool(accepted),
                "rejection_reason": None if accepted else error or ("structure" if not validation["valid"] else "spectral_bound_or_bipartite"),
            }
            attempts.append(attempt)
            write_json(directory / "attempts.json", attempts)
            if accepted:
                selected = index
                break
        total = time.perf_counter() - started
    result = {**job, "status": "ok" if selected is not None else "no_accepted_graph",
              "selected_candidate": selected, "attempts": attempts, "attempt_count": len(attempts),
              "rejected_count": sum(not a["selected"] for a in attempts), "memory": memory.result,
              "total_build_seconds": total, "generation_seconds": sum(a["generation_seconds"] for a in attempts),
              "structure_seconds": sum(a["structure_seconds"] for a in attempts),
              "spectral_seconds": sum(a["spectral_seconds"] for a in attempts),
              "networkx_internal_stub_rejections": "not exposed; their time and memory are included"}
    write_json(directory / "build.json", result)


def simulate_worker(config, job, directory):
    directory = Path(directory)
    build = json.loads((directory / "build.json").read_text("utf-8"))
    assert build["status"] == "ok"
    accepted = build["attempts"][build["selected_candidate"]]
    with Memory() as memory:
        began = time.perf_counter()
        raw = (directory / accepted["graph_file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == accepted["graph_sha256"]
        graph = load_graph(raw)
        load_seconds = time.perf_counter() - began
        scenarios = []
        for model in config["latency_models"]:
            for fraction in config["failure_fractions"]:
                began = time.perf_counter()
                trace = make_trace(job["n"], job["seed"], fraction, config["messages"])
                result = simulate(graph, trace, config, model)
                result["simulation_seconds"] = time.perf_counter() - began
                trace_file = directory / f"trace-{fraction}.json"
                write_json(trace_file, trace)
                result["trace_file"] = trace_file.name
                scenarios.append(result)
    result = {**job, "graph_sha256": accepted["graph_sha256"], "scenarios": scenarios,
              "graph_load_seconds": load_seconds, "memory": memory.result,
              "memory_scope": "fresh simulation process; all six scenarios including graph loading",
              "total_simulation_seconds": sum(s["simulation_seconds"] for s in scenarios)}
    write_json(directory / "simulation.json", result)


def run(config_path, destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text("utf-8"))
    write_json(destination / "config.json", config)
    source_paths = [*sorted((ROOT / "p2p178").rglob("*.py")), ROOT / "p2p178/PLAN.md",
                    ROOT / "p2p178/config.json", ROOT / "p2p178/requirements.txt"]
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in source_paths}
    write_json(destination / "code_hashes.json", hashes)
    (destination / "PLAN.md").write_bytes((ROOT / "p2p178/PLAN.md").read_bytes())
    (destination / "sources.json").write_bytes((ROOT / "references/p2p178/sources.json").read_bytes())
    environment = {**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                   "NUMEXPR_NUM_THREADS": "1", "PYTHONHASHSEED": "0"}
    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "p2p178/tests", "-v"],
                           cwd=ROOT, env=environment, capture_output=True, text=True, timeout=180)
    (destination / "tests.txt").write_text(tests.stdout + tests.stderr, "utf-8")
    if tests.returncode:
        raise RuntimeError("Preflight failed; see tests.txt; no benchmark executed")
    versions = {name: importlib.metadata.version(name) for name in ["networkx", "numpy", "scipy", "psutil"]}
    metadata = {"started_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
                "executable": sys.executable, "platform": platform.platform(), "processor": platform.processor(),
                "logical_cpus": psutil.cpu_count(), "physical_cpus": psutil.cpu_count(logical=False),
                "physical_ram_bytes": psutil.virtual_memory().total, "dependencies": versions,
                "thread_environment": {k: environment[k] for k in ["OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "PYTHONHASHSEED"]},
                "workers_parallel": 1, "tests_returncode": tests.returncode, "plan_sha256": digest(ROOT / "p2p178/PLAN.md")}
    write_json(destination / "environment.json", metadata)
    jobs = []
    for case in config["cases"]:
        methods = list(config["methods"])
        if case == {"n": config["extra_lps_case"]["n"], "d": config["extra_lps_case"]["d"]}:
            methods.append("lps")
        for seed in config["seeds"]:
            for method in methods:
                jobs.append({**case, "seed": seed, "method": method})
    # Fixed shuffled order avoids systematically giving one method the warmest CPU.
    import random
    random.Random(1782026).shuffle(jobs)
    raw_results = []
    run_started = time.perf_counter()
    for i, job in enumerate(jobs):
        key = f"n{job['n']}-d{job['d']}-{job['method']}-s{job['seed']}"
        directory = destination / "jobs" / key
        directory.mkdir(parents=True)
        write_json(directory / "job.json", job)
        record = {**job, "directory": str(directory.relative_to(destination))}
        for operation in ["build", "simulate"]:
            command = [sys.executable, "-m", "p2p178.benchmark", operation, "--config", str(config_path), "--output", str(directory)]
            started = time.perf_counter()
            try:
                result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True,
                                        timeout=config["worker_timeout_seconds"])
                record[f"{operation}_worker_wall_seconds"] = time.perf_counter() - started
                (directory / f"{operation}.log").write_text(result.stdout + result.stderr, "utf-8")
                if result.returncode:
                    record["error"] = f"{operation} exit {result.returncode}"
                    break
            except subprocess.TimeoutExpired:
                record["error"] = f"{operation} timeout {config['worker_timeout_seconds']}s"
                record[f"{operation}_worker_wall_seconds"] = time.perf_counter() - started
                break
            result_file = "build.json" if operation == "build" else "simulation.json"
            record[operation] = json.loads((directory / result_file).read_text("utf-8"))
            if operation == "build" and record[operation]["status"] != "ok":
                break
        raw_results.append(record)
        write_json(destination / "raw.json", raw_results)
        print(f"{i+1}/{len(jobs)} {key}: {record.get('error', record.get('build', {}).get('status', 'missing'))}", flush=True)
    metadata["finished_utc"] = datetime.now(timezone.utc).isoformat()
    metadata["benchmark_wall_seconds"] = time.perf_counter() - run_started
    metadata["jobs"] = len(jobs)
    metadata["failed_jobs"] = sum("error" in r or r.get("build", {}).get("status") != "ok" for r in raw_results)
    write_json(destination / "environment.json", metadata)
    print(json.dumps({"output": str(destination), "wall_seconds": metadata["benchmark_wall_seconds"],
                      "failed_jobs": metadata["failed_jobs"]}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["run", "build", "simulate"])
    parser.add_argument("--config", default=str(ROOT / "p2p178/config.json"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.operation == "run":
        run(args.config, args.output)
    else:
        job = json.loads((Path(args.output) / "job.json").read_text("utf-8"))
        cfg = json.loads(Path(args.config).read_text("utf-8"))
        (build_worker if args.operation == "build" else simulate_worker)(cfg, job, args.output)


if __name__ == "__main__":
    main()
