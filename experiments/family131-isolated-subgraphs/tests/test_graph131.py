import itertools
import random
import unittest
from collections import Counter, defaultdict

import networkx as nx
import numpy as np

from graph131.evaluate import threshold_at_fpr, top_k
from graph131.directed import directed_features
from graph131.switches import State, null_features, structural_targets


def degree_key(n, edges):
    return tuple(sum(i in edge for edge in edges) for i in range(n))


class ProposalRng:
    def __init__(self, quadruple):
        self.quadruple = quadruple

    def random(self):
        return 0.75

    def sample(self, population, k):
        return self.quadruple


class Graph131Tests(unittest.TestCase):
    def test_conventional_kernel_exact(self):
        class EdgeRng:
            def __init__(self, i, j, flip):
                self.ij, self.flip = (i, j), flip
            def random(self):
                return 0.75
            def sample(self, population, k):
                return self.ij
            def randrange(self, n):
                return self.flip
        universe = list(itertools.combinations(range(6), 2))
        graphs = [frozenset(e) for e in itertools.combinations(universe, 6) if degree_key(6, e) == (2,) * 6]
        self.assertEqual(len(graphs), 70)
        for graph in graphs:
            counts = Counter()
            for i, j in itertools.permutations(range(6), 2):
                for flip in (0, 1):
                    state = State(6, sorted(graph))
                    if state.step_edge(EdgeRng(i, j, flip)):
                        counts[frozenset(state.edges)] += 1
            self.assertEqual(set(counts), {g for g in graphs if len(g ^ graph) == 4})
            self.assertTrue(all(c == 2 for c in counts.values()))
            # Including holding: 1/2 * 2/(2*m*(m-1)) = 1/(4*C(m,2)).

    def test_direction_and_multiplicity_control(self):
        outstar = directed_features(3, [(0, 1), (0, 2)])
        instar = directed_features(3, [(1, 0), (2, 0)])
        self.assertEqual(outstar[2:4], [1, 2])
        self.assertEqual(instar[2:4], [2, 1])
        repeated = directed_features(3, [(0, 1), (0, 1), (1, 2)])
        self.assertEqual(repeated[1], 1.5)
        self.assertEqual(repeated[-2:], [2, 2])

    def test_exhaustive_kernel(self):
        """Independent degree-space enumeration, not a second switch algorithm."""
        checked = 0
        for n in (4, 5, 6):
            all_edges = list(itertools.combinations(range(n), 2))
            candidates = (itertools.combinations(all_edges, 6) if n == 6 else (tuple(e for i, e in enumerate(all_edges) if mask & (1 << i)) for mask in range(1 << len(all_edges))))
            groups = defaultdict(list)
            for edges in candidates:
                key = degree_key(n, edges)
                if n == 6 and key != (2,) * 6:
                    continue
                groups[key].append(frozenset(edges))
            for key, graphs in groups.items():
                for graph in graphs:
                    # Switch neighbors independently characterized by degree
                    # equality and four-edge symmetric difference.
                    expected = {g for g in graphs if len(graph ^ g) == 4}
                    counts = Counter()
                    for quad in itertools.permutations(range(n), 4):
                        state = State(n, sorted(graph))
                        if state.step_paper(ProposalRng(quad)):
                            target = frozenset(state.edges)
                            self.assertEqual(degree_key(n, target), key)
                            counts[target] += 1
                    self.assertEqual(set(counts), expected)
                    self.assertTrue(all(c == 4 for c in counts.values()))
                    # P(G,H) = 1/2 * 4/(24*C(n,4)) = 1/(12*C(n,4)).
                    # Symmetric neighbor relation => symmetric transition matrix
                    # and uniform stationary law; diagonal is the remaining mass.
                    self.assertEqual(State(n, sorted(graph)).has_switch(), bool(expected))
                    checked += 1
        self.assertEqual(checked, 1158)

    def test_structural_counts_independent_matrix(self):
        rng = random.Random(131)
        for n in range(2, 11):
            for _ in range(10):
                edges = [e for e in itertools.combinations(range(n), 2) if rng.random() < 0.3]
                state = State(n, edges)
                g = nx.Graph()
                g.add_nodes_from(range(n)); g.add_edges_from(edges)
                a = nx.to_numpy_array(g, dtype=np.int64)
                a2 = a @ a
                triangles = np.trace(a2 @ a) / 6
                degrees = np.array(list(dict(g.degree()).values()))
                squares = (np.trace(a2 @ a2) - 2 * len(edges) - 2 * sum(degrees * (degrees - 1))) / 8
                actual = structural_targets(state)
                self.assertEqual(actual[0], triangles)
                self.assertEqual(actual[1], squares)
                self.assertEqual(actual[3], nx.number_connected_components(g))
                self.assertEqual(actual[4], len(max(nx.connected_components(g), key=len)) / n)

    def test_both_samplers_preserve_graph(self):
        for kernel in ("paper", "edge"):
            state = State(10, list(nx.cycle_graph(10).edges()))
            rng = random.Random(131)
            step = state.step_paper if kernel == "paper" else state.step_edge
            for _ in range(10000):
                step(rng)
                self.assertEqual(tuple(map(len, state.adj)), (2,) * 10)
                self.assertEqual(len(set(state.edges)), 10)
                self.assertTrue(all(a != b for a, b in state.edges))
                self.assertEqual(state.positions, {e: i for i, e in enumerate(state.edges)})

    def test_frozen_and_reproducible(self):
        for n in (2, 3, 7):
            edges = list(nx.star_graph(n - 1).edges())
            values, diag = null_features(n, edges, kernel="paper", seed=131)
            self.assertTrue(diag["frozen"])
            np.testing.assert_array_equal(values, np.r_[np.zeros(5), np.ones(10)])
        args = dict(n=6, edges=list(nx.cycle_graph(6).edges()), kernel="paper", seed=131)
        a, da = null_features(**args)
        b, db = null_features(**args)
        np.testing.assert_array_equal(a, b)
        self.assertEqual(da, db)

    def test_ties_and_validation_threshold(self):
        y = np.array([0] * 990 + [1] * 10)
        scores = np.zeros(1000)
        self.assertEqual(top_k(y, scores)["precision_at_100"], 0.01)
        threshold = threshold_at_fpr(y, scores)
        self.assertEqual(int((scores >= threshold).sum()), 0)


if __name__ == "__main__":
    unittest.main()
