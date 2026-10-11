"""Bounded exact-input distances, synthetic controls, independent scoring."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def auto_batch(n, k):
    return min(n, max(k, int(100.0 * np.log(max(2, n * max(1, k))))))


def batch_for(method, n, k):
    if method == "onebatch_auto":
        return auto_batch(n, k)
    if method == "onebatch_2auto":
        return min(n, 2 * auto_batch(n, k))
    if method in ("onebatch_full", "fasterpam"):
        return n
    return min(n, int(method.removeprefix("onebatch")))


def make_dataset(structure, n, seed):
    if structure not in ("balanced", "rare_triplets", "rare_singletons"):
        raise ValueError(structure)
    rng = np.random.default_rng(seed)
    per_rare = {"balanced": 0, "rare_triplets": 3, "rare_singletons": 1}[structure]
    if n < 8 * per_rare + 12:
        raise ValueError("Need twelve bulk clients in addition to the rare clients")
    centers = [(1000 * i, 1000 * j) for i in range(4) for j in range(3)]
    remote = [(100000 * i, 100000 * j) for i in (-1, 0, 1)
              for j in (-1, 0, 1) if (i, j) != (0, 0)]
    points, groups, seen = [], [], set()

    def add(center, radius, group):
        while True:
            p = tuple(int(center[d] + rng.integers(-radius, radius + 1)) for d in range(2))
            if p not in seen:
                seen.add(p)
                points.append(p)
                groups.append(group)
                return

    for i in range(n - 8 * per_rare):
        add(centers[i % len(centers)], 100, -1)
    for group, center in enumerate(remote):
        for _ in range(per_rare):
            add(center, 5, group)
    order = rng.permutation(n)
    x = np.ascontiguousarray(np.asarray(points, dtype=np.int32)[order])
    labels = np.asarray(groups, dtype=np.int32)[order]
    return x, labels


def l1_f32(x, y, block_rows=128):
    """One output plus bounded scratch; no NxNxD or float64 temporary."""
    x, y = np.asarray(x), np.asarray(y)
    if x.ndim != 2 or y.ndim != 2 or x.shape[1] != y.shape[1] or not x.shape[1]:
        raise ValueError("Expected matching, nonempty feature dimensions")
    if block_rows <= 0:
        raise ValueError("block_rows must be positive")
    out = np.empty((len(x), len(y)), dtype=np.float32)
    scratch = np.empty((min(block_rows, len(x)), len(y)), dtype=np.float32)
    for start in range(0, len(x), block_rows):
        stop = min(start + block_rows, len(x))
        target = out[start:stop]
        tmp = scratch[:stop-start]
        np.subtract(x[start:stop, 0, None], y[None, :, 0], out=target)
        np.abs(target, out=target)
        for axis in range(1, x.shape[1]):
            np.subtract(x[start:stop, axis, None], y[None, :, axis], out=tmp)
            np.abs(tmp, out=tmp)
            np.add(target, tmp, out=target)
    return out


def score_integer(x, groups, medoids):
    """Independent integer broadcast formula, never reuses the sampled matrix."""
    meds = np.asarray(medoids, dtype=np.int64)
    if len(meds) == 0 or len(np.unique(meds)) != len(meds) or min(meds) < 0 or max(meds) >= len(x):
        raise ValueError("Invalid medoid indices")
    exact = np.abs(np.asarray(x, dtype=np.int64)[:, None, :] -
                   np.asarray(x, dtype=np.int64)[meds][None, :, :]).sum(axis=2)
    labels = np.argmin(exact, axis=1)
    nearest = exact[np.arange(len(x)), labels]
    rare_mask = np.asarray(groups) >= 0
    rare = nearest[rare_mask]
    all_groups = sorted(set(map(int, np.asarray(groups)[rare_mask])))
    selected = sorted(set(map(int, np.asarray(groups)[meds])) - {-1})
    quality = dict(cost=int(nearest.sum()), bulk_cost=int(nearest[~rare_mask].sum()),
                   rare_cost=int(rare.sum()), rare_count=len(rare), rare_groups_total=len(all_groups),
                   rare_groups_covered=len(selected), covered_group_ids=selected,
                   rare_served_within_20=int(np.count_nonzero(rare <= 20)),
                   rare_mean_distance=float(rare.mean()) if len(rare) else None,
                   rare_p95_distance=float(np.quantile(rare, .95)) if len(rare) else None,
                   rare_max_distance=int(rare.max()) if len(rare) else None,
                   rare_distances=rare.tolist(), full_max_distance=int(nearest.max()))
    return quality, nearest, meds[labels]


def miss_probability(n, batch, group_size):
    if batch > n - group_size:
        return 0.0
    return float(np.prod([(n-batch-j)/(n-j) for j in range(group_size)]))
