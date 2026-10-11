"""Exact proposal kernels, with finite-budget (uncertified) MC features."""
from __future__ import annotations

from collections import Counter
from itertools import combinations
import math
import random

import numpy as np


class State:
    def __init__(self, n, edges):
        self.n = n
        self.adj = [set() for _ in range(n)]
        self.edges = [tuple(sorted(e)) for e in edges]
        self.positions = {e: i for i, e in enumerate(self.edges)}
        assert len(self.positions) == len(self.edges)
        for a, b in self.edges:
            assert a != b
            self.adj[a].add(b)
            self.adj[b].add(a)
        self.degrees = tuple(map(len, self.adj))

    def proposal(self, a, b, c, d):
        """Remove ab,cd; add ac,bd if and only if valid."""
        adj = self.adj
        if b not in adj[a] or d not in adj[c] or c in adj[a] or d in adj[b]:
            return False
        old1, old2 = tuple(sorted((a, b))), tuple(sorted((c, d)))
        new1, new2 = tuple(sorted((a, c))), tuple(sorted((b, d)))
        i, j = self.positions.pop(old1), self.positions.pop(old2)
        self.edges[i], self.edges[j] = new1, new2
        self.positions[new1], self.positions[new2] = i, j
        adj[a].remove(b); adj[b].remove(a)
        adj[c].remove(d); adj[d].remove(c)
        adj[a].add(c); adj[c].add(a)
        adj[b].add(d); adj[d].add(b)
        return True

    def step_paper(self, rng):
        if self.n < 4 or rng.random() < 0.5:
            return False
        # A uniform ordered quadruple induces each ordered pair of distinct
        # perfect matchings exactly four times. This is precisely the paper's
        # uniform 4-set + uniform one-of-six matching-pair proposal.
        return self.proposal(*rng.sample(range(self.n), 4))

    def step_edge(self, rng):
        m = len(self.edges)
        if m < 2 or rng.random() < 0.5:
            return False
        i, j = rng.sample(range(m), 2)
        a, b = self.edges[i]
        c, d = self.edges[j]
        if len({a, b, c, d}) != 4:
            return False
        if rng.randrange(2):
            c, d = d, c
        return self.proposal(a, b, c, d)

    def has_switch(self):
        adj = self.adj
        for (a, b), (c, d) in combinations(self.edges, 2):
            if len({a, b, c, d}) != 4:
                continue
            if (c not in adj[a] and d not in adj[b]) or (d not in adj[a] and c not in adj[b]):
                return True
        return False


TARGET_NAMES = ["triangles", "squares", "degree_mixing", "components", "largest_component_fraction"]


def structural_targets(state):
    adj, n, edges, degrees = state.adj, state.n, state.edges, state.degrees
    triangles = sum(len(adj[a] & adj[b]) for a, b in edges) / 3
    common = Counter()
    for neighbors in adj:
        for a, b in combinations(sorted(neighbors), 2):
            common[(a, b)] += 1
    squares = sum(c * (c - 1) // 2 for c in common.values()) / 2
    unseen = set(range(n))
    sizes = []
    while unseen:
        todo = [unseen.pop()]
        size = 0
        while todo:
            a = todo.pop()
            size += 1
            new = adj[a] & unseen
            unseen.difference_update(new)
            todo.extend(new)
        sizes.append(size)
    mixing = sum(degrees[a] * degrees[b] for a, b in edges) / max(1, len(edges))
    return np.array([triangles, squares, mixing, len(sizes), max(sizes, default=0) / max(1, n)], dtype=float)


def null_features(n, edges, *, kernel, seed, burn=512, samples=32, stride=64):
    state = State(n, edges)
    original = structural_targets(state)
    if not state.has_switch():
        # All retained graphs would be identical: deltas=0, both smoothed tails=1.
        return np.r_[np.zeros(5), np.ones(10)], {"frozen": True, "proposals": 0, "accepted": 0, "distinct_states": 1, "varying_targets": 0}
    rng = random.Random(seed)
    step = state.step_paper if kernel == "paper" else state.step_edge
    accepted = 0
    for _ in range(burn):
        accepted += step(rng)
    values, seen = [], set()
    for _ in range(samples):
        for _ in range(stride):
            accepted += step(rng)
        values.append(structural_targets(state))
        seen.add(tuple(sorted(state.edges)))
    assert tuple(map(len, state.adj)) == state.degrees
    draws = np.asarray(values)
    residual = (original - draws.mean(axis=0)) / np.sqrt(draws.var(axis=0, ddof=1) + 1)
    upper = (1 + (draws >= original - 1e-12).sum(axis=0)) / (samples + 1)
    lower = (1 + (draws <= original + 1e-12).sum(axis=0)) / (samples + 1)
    return np.r_[residual, upper, lower], {"frozen": False, "proposals": burn + samples * stride, "accepted": accepted, "distinct_states": len(seen), "varying_targets": int((np.ptp(draws, axis=0) > 1e-12).sum())}


NULL_NAMES = [f"{kind}_{name}" for kind in ("residual", "upper_tail", "lower_tail") for name in TARGET_NAMES]
