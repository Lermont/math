"""Deterministic datasets and independent exact-integer objective evaluation."""
from __future__ import annotations
import hashlib
import heapq
import io
import json
import zipfile
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def synthetic(structure, n, k, seed):
    rng = np.random.default_rng(seed)
    out = dict(name=f"{structure}_n{n}_k{k}_s{seed}", kind="synthetic",
               structure=structure, n=n, k=k, data_seed=seed)
    if structure == "graph":
        edges = {}
        for i in range(n):
            a, b = sorted((i, (i + 1) % n))
            edges[a, b] = int(rng.integers(1, 16))
        for _ in range(3 * n):
            a, b = sorted(map(int, rng.choice(n, 2, replace=False)))
            w = int(rng.integers(1, 31))
            edges[a, b] = min(edges.get((a, b), w), w)
        out.update(metric="integer_shortest_path", edges=[[a, b, w] for (a, b), w in sorted(edges.items())])
        return out
    centers = np.array([[0, 0], [1000, 0], [0, 1000], [1000, 1000]])
    p = np.array([.25, .25, .25, .25]) if structure != "unbalanced" else np.array([.70, .20, .08, .02])
    points, seen = [], set()
    for i in range(n):
        while True:
            group = int(rng.choice(4, p=p))
            point = centers[group] + rng.integers(-60, 61, 2)
            if structure == "outliers" and i >= n - max(2, n // 40):
                point = np.array([8000 + (i - n) * 330, 8000 + (i - n) * 590]) + rng.integers(-20, 21, 2)
            pt = tuple(map(int, point))
            if pt not in seen:
                seen.add(pt)
                points.append(list(pt))
                break
    out.update(metric="integer_l1", points=points)
    return out

def real_seeds(k):
    raw_path = ROOT / "references/kmedian125/datasets/seeds.zip"
    with zipfile.ZipFile(raw_path) as z:
        raw = z.read("seeds_dataset.txt")
    arr = np.loadtxt(io.BytesIO(raw))
    x = arr[:, :7]
    lo, hi = x.min(axis=0), x.max(axis=0)
    coords = np.rint(1000 * (x - lo) / (hi - lo)).astype(np.int64)
    assert len(coords) == 210 and len(np.unique(coords, axis=0)) == 210
    return dict(name=f"uci_seeds_n210_k{k}", kind="real", structure="uci_seeds",
                metric="integer_l1", n=210, k=k, points=coords.tolist(),
                raw_sha256=digest(raw_path), transform="rint(1000*(x-min)/(max-min)); first 7 columns; class excluded",
                feature_min=lo.tolist(), feature_max=hi.tolist(), original_order=True,
                source="https://archive.ics.uci.edu/dataset/236/seeds",
                citation="Charytanowicz et al. (2010). Seeds. UCI. DOI:10.24432/C5H30K; CC BY 4.0")

def distance_matrix(dataset, columns=None):
    """Primary distance implementation; optional sampled-client columns."""
    n = dataset["n"]
    cols = np.arange(n) if columns is None else np.asarray(columns)
    if dataset["metric"] == "integer_l1":
        x = np.asarray(dataset["points"], dtype=np.int64)
        # Accumulate one coordinate at a time, avoiding an n*n*d temporary.
        d = np.zeros((n, len(cols)), dtype=np.int64)
        for q in range(x.shape[1]):
            d += np.abs(x[:, q, None] - x[cols, q][None, :])
        return d
    edges = np.asarray(dataset["edges"], dtype=np.int64)
    rows = np.r_[edges[:, 0], edges[:, 1]]
    cols_edge = np.r_[edges[:, 1], edges[:, 0]]
    graph = coo_matrix((np.tile(edges[:, 2], 2), (rows, cols_edge)), shape=(n, n)).tocsr()
    d = dijkstra(graph, directed=False, indices=cols).T
    assert np.isfinite(d).all() and np.equal(d, np.rint(d)).all()
    return np.ascontiguousarray(d, dtype=np.int64)

def validate_metric(d):
    if d.ndim != 2 or d.shape[0] != d.shape[1] or len(d) == 0:
        raise ValueError("nonempty square metric required")
    n = len(d)
    if not np.array_equal(d, d.T) or np.any(np.diag(d) != 0):
        raise ValueError("symmetry/diagonal failure")
    if np.any(d[~np.eye(n, dtype=bool)] <= 0):
        raise ValueError("distinct locations must have positive distance")
    for h in range(n):
        if np.any(d > d[:, h, None] + d[h, None, :]):
            raise ValueError("triangle inequality failure")

def independent_cost(dataset, medoids):
    """No use of the stored matrix, solver assignments or package inertia."""
    meds = list(map(int, medoids))
    n, k = dataset["n"], dataset["k"]
    if len(meds) != k or len(set(meds)) != k or any(i < 0 or i >= n for i in meds):
        raise ValueError("invalid exact-budget medoid set")
    if dataset["metric"] == "integer_l1":
        x = dataset["points"]
        return sum(min(sum(abs(a - b) for a, b in zip(p, x[i])) for i in meds) for p in x)
    adjacency = [[] for _ in range(n)]
    for a, b, weight in dataset["edges"]:
        adjacency[a].append((b, weight))
        adjacency[b].append((a, weight))
    # Independent multi-source heap Dijkstra, with integer arithmetic.
    distances = [10**30] * n
    heap = []
    for i in meds:
        distances[i] = 0
        heapq.heappush(heap, (0, i))
    while heap:
        dist, a = heapq.heappop(heap)
        if dist != distances[a]:
            continue
        for b, w in adjacency[a]:
            new = dist + w
            if new < distances[b]:
                distances[b] = new
                heapq.heappush(heap, (new, b))
    assert max(distances) < 10**30
    return sum(distances)

def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
