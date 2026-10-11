"""Resource obstruction derived from the manuscript's displayed preparation bounds."""
from decimal import Decimal, getcontext
from pathlib import Path
from math import e
import json

def calculate(epsilon):
    getcontext().prec = 90
    eps = Decimal(epsilon)
    # Main theorem: pseudo-loss eps/4; pseudo proof: t <= pseudo-loss/10.
    eta = eps/40
    delta_lower = 144*(1+eta)**2*(2+eta)**2/(eta**10)
    return dict(epsilon=str(eps), preparation_t=str(eta),
                approximation_upper=1+2/e+float(eps),
                delta_lower_bound=str(delta_lower),
                log10_delta=float(delta_lower.log10()),
                minimum_8byte_copy_storage_bytes=str(8*delta_lower),
                seconds_at_one_billion_copies_per_second=str(delta_lower/Decimal(10**9)))

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((root/"kmedian125/config.json").read_text(encoding="utf-8"))
    rows = [calculate(eps) for eps in cfg["epsilon_feasibility"]]
    (root/"results/kmedian125/feasibility.json").write_text(json.dumps(rows, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(rows, indent=2))
