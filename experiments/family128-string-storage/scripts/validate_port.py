"""Seeded stress check; writes branch witnesses and validates an exact oracle."""
import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stringpack.paper128 import pack_superstring
from tests.test_paper128 import exact_length


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1282026)
    parser.add_argument("--output", default="results/validation.json")
    args = parser.parse_args()
    rng, branches, witnesses = random.Random(args.seed), Counter(), {}
    for i in range(args.cases):
        alphabet = rng.choice([b"ab", b"abc", b"abcdef"])
        count = rng.randint(1, 8)
        if i % 3:
            strings = [bytes(rng.choices(alphabet, k=rng.randint(1, 30)))
                       for _ in range(count)]
        else:
            templates = [bytes(rng.choices(alphabet, k=rng.randint(1, 7)))
                         for _ in range(count)]
            strings = [t * rng.randint(2, 5) + bytes(rng.choices(alphabet, k=rng.randint(0, 5)))
                       for t in templates]
        try:
            result, stats = pack_superstring(strings)
            opt = exact_length(strings)
            assert all(s in result for s in strings)
            assert stats["lower_bound"] <= opt <= len(result) <= 2 * opt
        except Exception:
            print("FAILED case", i, repr(strings), flush=True)
            raise
        branches.update(stats["branch_counts"])
        for branch in stats["branch_counts"]:
            witnesses.setdefault(branch, [s.hex() for s in strings])
        if (i + 1) % 250 == 0:
            print(i + 1, dict(branches), flush=True)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(cases=args.cases, seed=args.seed,
                                  branches=dict(branches), witnesses=witnesses), indent=2))
    print("Saved", out)


if __name__ == "__main__":
    main()
