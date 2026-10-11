"""Graph construction, independent structural checks and spectral diagnostics."""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import random

import networkx as nx


def seed_for(*parts) -> int:
    raw = json.dumps(parts, separators=(",", ":")).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def graph_bytes(graph: nx.Graph) -> bytes:
    edges = sorted((min(u, v), max(u, v)) for u, v in graph.edges())
    return (json.dumps({"n": len(graph), "edges": edges}, separators=(",", ":")) + "\n").encode()


def load_graph(data: bytes) -> nx.Graph:
    obj = json.loads(data)
    graph = nx.Graph()
    graph.add_nodes_from(range(obj["n"]))
    graph.add_edges_from(obj["edges"])
    return graph


def structure(graph: nx.Graph, n: int, d: int) -> dict:
    degrees = [value for _, value in graph.degree()]
    simple = not graph.is_directed() and not graph.is_multigraph() and nx.number_of_selfloops(graph) == 0
    connected = bool(len(graph)) and nx.is_connected(graph)
    return {
        "n": len(graph), "edges": graph.number_of_edges(), "simple": simple,
        "connected": connected, "components": nx.number_connected_components(graph),
        "bipartite": nx.is_bipartite(graph), "degree_min": min(degrees, default=0),
        "degree_max": max(degrees, default=0),
        "valid": simple and connected and len(graph) == n and all(x == d for x in degrees)
                 and set(graph) == set(range(n)),
    }


def lps_graph(p: int = 5, q: int = 13) -> nx.Graph:
    """Classical LPS via projective 2x2 matrices, restricted p,q == 1 mod 4.

    Mathematical formula from LPS (1988), confirmed against the public
    RamanujanGraphs.jl generator. Independent implementation, no Julia code
    copied. Only p=5,q=13 is used in the measurements. This is NOT paper 178.
    """
    def prime(x):
        return x >= 2 and all(x % k for k in range(2, math.isqrt(x) + 1))

    if not (prime(p) and prime(q) and p != q and p % 4 == q % 4 == 1 and q > 2 * math.sqrt(p)):
        raise ValueError("require distinct primes p,q=1 mod4 and q>2sqrt(p)")
    imaginary = next(i for i in range(q) if i * i % q == q - 1)

    def normalize(m):
        m = tuple(x % q for x in m)
        inv = pow(next(x for x in m if x), -1, q)
        return tuple(x * inv % q for x in m)

    def multiply(m, h):
        a, b, c, d = m
        e, f, g, h = h
        return normalize((a * e + b * g, a * f + b * h, c * e + d * g, c * f + d * h))

    radius = math.isqrt(p)
    even = [x for x in range(-radius, radius + 1) if x % 2 == 0]
    generators = set()
    for a in range(1, radius + 1, 2):
        for b, c, d in itertools.product(even, repeat=3):
            if a * a + b * b + c * c + d * d == p:
                generators.add(normalize((a + imaginary * b, c + imaginary * d,
                                          -c + imaginary * d, a - imaginary * b)))
    generators = sorted(generators)
    identity = (1, 0, 0, 1)
    assert len(generators) == p + 1 and identity not in generators
    for a, b, c, d in generators:
        assert normalize((d, -b, -c, a)) in generators
    states = [identity]
    labels = {identity: 0}
    graph = nx.Graph()
    graph.add_node(0)
    legendre = pow(p, (q - 1) // 2, q)
    expected = q * (q * q - 1) // (2 if legendre == 1 else 1)
    for index, state in enumerate(states):
        for generator in generators:
            target = multiply(state, generator)
            if target not in labels:
                labels[target] = len(states)
                states.append(target)
                assert len(states) <= expected
            graph.add_edge(index, labels[target])
    assert len(graph) == expected
    assert all(value == p + 1 for _, value in graph.degree())
    return graph


def generate(method: str, n: int, d: int, seed: int, candidate: int = 0) -> nx.Graph:
    if method in ("random_regular", "spectral_rejection"):
        graph = nx.random_regular_graph(d, n, seed=seed_for(seed, n, d, "candidate", candidate))
    elif method == "circulant":
        if d % 2 or d >= n:
            raise ValueError("circulant requires even degree below n")
        graph = nx.circulant_graph(n, list(range(1, d // 2 + 1)))
    elif method == "lps":
        if (n, d) != (2184, 6):
            raise ValueError("this benchmark uses only X^(5,13)")
        graph = lps_graph()
    else:
        raise ValueError(method)
    permutation = list(range(n))
    random.Random(seed_for(seed, n, "placement")).shuffle(permutation)
    return nx.relabel_nodes(graph, dict(enumerate(permutation)), copy=True)


def spectrum(graph: nx.Graph, *, tol=1e-10, residual_limit=1e-8, margin=1e-7, force_dense=False) -> dict:
    """Two algebraic extremes; numerics are diagnostics, never a certificate.

    Reject disconnected input instead of deleting every occurrence of +/-d.
    Remove exactly one d and exactly one -d iff graph is connected bipartite.
    """
    import numpy as np
    from scipy.sparse.linalg import eigsh

    n = len(graph)
    degrees = {value for _, value in graph.degree()}
    if not nx.is_connected(graph) or len(degrees) != 1 or graph.is_multigraph() or nx.number_of_selfloops(graph):
        raise ValueError("spectrum requires connected simple regular graph")
    degree = degrees.pop()
    bipartite = nx.is_bipartite(graph)
    matrix = nx.to_scipy_sparse_array(graph, nodelist=range(n), dtype=float, format="csr")
    if n <= 64 or force_dense:
        values, vectors = np.linalg.eigh(matrix.toarray())
        residual = float(np.max(np.linalg.norm(matrix @ vectors - vectors * values, axis=0)))
        assert abs(values[-1] - degree) < residual_limit
        nontrivial = values[:-1]
        if bipartite:
            assert abs(nontrivial[0] + degree) < residual_limit
            nontrivial = nontrivial[1:]
        high, low = float(max(nontrivial)), float(min(nontrivial))
        extremes = [float(v) for v in values]
        solver = "numpy.linalg.eigh"
    else:
        rng = np.random.default_rng(seed_for(n, degree, "arpack-v0"))
        v0 = rng.normal(size=n)
        upper, vu = eigsh(matrix, k=3, which="LA", tol=tol, v0=v0,
                          maxiter=max(5000, 20 * n), ncv=40)
        lower, vl = eigsh(matrix, k=3, which="SA", tol=tol, v0=v0,
                          maxiter=max(5000, 20 * n), ncv=40)
        residual = float(max(np.max(np.linalg.norm(matrix @ vu - vu * upper, axis=0)),
                             np.max(np.linalg.norm(matrix @ vl - vl * lower, axis=0))))
        upper, lower = np.sort(upper), np.sort(lower)
        assert abs(upper[-1] - degree) < residual_limit
        high = float(upper[-2])
        if bipartite:
            assert abs(lower[0] + degree) < residual_limit
        low = float(lower[1] if bipartite else lower[0])
        extremes = [float(v) for v in list(lower) + list(upper)]
        solver = "scipy.sparse.linalg.eigsh LA+SA"
    absolute = max(abs(high), abs(low))
    bound = 2 * math.sqrt(degree - 1)
    return {"lambda2": high, "lambda_min_nontrivial": low, "lambda_abs": absolute,
            "ramanujan_bound": bound, "margin_to_bound": bound - absolute,
            "residual_max": residual, "residual_ok": residual <= residual_limit,
            "numeric_pass": residual <= residual_limit and absolute < bound - margin,
            "removed_trivial": [degree, -degree] if bipartite else [degree],
            "extremes": extremes, "solver": solver, "tol": tol,
            "acceptance_margin": margin, "formal_certificate": False}


def exact_paper_acceptance(graph: nx.Graph) -> bool:
    """Exact integer Sylvester/Bareiss test of section 9, only n<=32.

    Verifies the acceptance criterion on a supplied graph. Does not construct
    the paper's graphs or certify the theorem/proof. Bipartite graphs fail.
    """
    n = len(graph)
    if not (3 <= n <= 32):
        raise ValueError("exact validation intentionally bounded to 3..32 vertices")
    degrees = {d for _, d in graph.degree()}
    if graph.is_multigraph() or nx.number_of_selfloops(graph) or len(degrees) != 1:
        return False
    d = degrees.pop()
    adjacency = [[int(graph.has_edge(i, j)) for j in range(n)] for i in range(n)]
    ab = [[row[j] - row[n - 1] for j in range(n - 1)] for row in adjacency]
    matrix = [[4 * (d - 1) * (int(i == j) + 1) - sum(row[i] * row[j] for row in ab)
               for j in range(n - 1)] for i in range(n - 1)]
    previous = 1
    for k in range(n - 1):
        pivot = matrix[k][k]
        if pivot <= 0:
            return False
        for i in range(k + 1, n - 1):
            for j in range(k + 1, n - 1):
                numerator = matrix[i][j] * pivot - matrix[i][k] * matrix[k][j]
                assert numerator % previous == 0
                matrix[i][j] = numerator // previous
        previous = pivot
    return True
