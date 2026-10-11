"""Direction control and one prespecified 4x-proposal sensitivity check."""
import os
import subprocess
import sys

from .data import ROOT, OUT
from .directed import prepare


def main():
    prepare()
    env = os.environ.copy()
    env.update({"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1", "PYTHONHASHSEED": "0"})
    for seed in (131, 132, 133):
        if not (OUT / f"seed{seed}/directed.json").exists():
            subprocess.run([sys.executable, "-m", "graph131.worker", "--method", "directed", "--seed", str(seed)], cwd=ROOT, env=env, check=True)
    if not (OUT / "seed131-budget4/paper.json").exists():
        subprocess.run([sys.executable, "-m", "graph131.worker", "--method", "paper", "--seed", "131", "--burn", "2048", "--stride", "256", "--suffix=-budget4"], cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    main()
