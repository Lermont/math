"""Run paired benchmarks serially, each in an independent process."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

import psutil

from .data import OUT, ROOT


def main():
    env = os.environ.copy()
    env.update({"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1", "PYTHONHASHSEED": "0"})
    code_paths = list((ROOT / "graph131").glob("*.py")) + [ROOT / "graph131/PLAN.md", ROOT / "tests/test_graph131.py"]
    meta = {"platform": platform.platform(), "processor": platform.processor(), "logical_cpus": psutil.cpu_count(), "physical_cpus": psutil.cpu_count(logical=False), "ram_bytes": psutil.virtual_memory().total, "seeds": [131, 132, 133], "code_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths}}
    (OUT / "run_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (OUT / "requirements-lock.txt").write_text(subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True), encoding="utf-8")
    for seed in meta["seeds"]:
        for method in ("rules", "degree", "graph", "paper", "edge"):
            if (OUT / f"seed{seed}/{method}.json").exists():
                print(f"Already complete: {method} {seed}", flush=True)
                continue
            print(f"Starting {method} seed={seed}", flush=True)
            subprocess.run([sys.executable, "-m", "graph131.worker", "--method", method, "--seed", str(seed)], cwd=ROOT, env=env, check=True)
    print("All paired runs complete", flush=True)


if __name__ == "__main__":
    main()
