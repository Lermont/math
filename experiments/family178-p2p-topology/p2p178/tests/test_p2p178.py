import math
import unittest

import networkx as nx
import numpy as np

from p2p178.graphs import exact_paper_acceptance, generate, graph_bytes, lps_graph, spectrum, structure
from p2p178.simulate import edge_latency, make_trace, simulate


def config(messages=1, payload=1000, bandwidth=1, interval=100):
    return {"messages": messages, "payload_bytes": payload, "header_bytes": 0,
            "uplink_mbps": bandwidth, "interval_ms": interval}


class GraphTests(unittest.TestCase):
    def test_regular_simple_and_shared_first_candidate(self):
        for n, d in [(32, 4), (64, 8)]:
            for method in ["random_regular", "circulant", "spectral_rejection"]:
                self.assertTrue(structure(generate(method, n, d, 19), n, d)["valid"])
            self.assertEqual(graph_bytes(generate("random_regular", n, d, 19)),
                             graph_bytes(generate("spectral_rejection", n, d, 19)))

    def test_lps_structure_and_bipartite_spectrum(self):
        graph = lps_graph()
        self.assertTrue(structure(graph, 2184, 6)["valid"])
        self.assertTrue(nx.is_bipartite(graph))
        diagnostic = spectrum(graph)
        self.assertEqual(diagnostic["removed_trivial"], [6, -6])
        self.assertTrue(diagnostic["numeric_pass"])
        for parameters in [(5, 5), (3, 13), (5, 9)]:
            with self.assertRaises(ValueError):
                lps_graph(*parameters)

    def test_sparse_extremes_against_dense_oracle(self):
        for graph in [nx.random_regular_graph(4, 100, seed=41), nx.circulant_graph(100, [1, 2]), nx.cycle_graph(100)]:
            sparse = spectrum(graph)
            dense = spectrum(graph, force_dense=True)
            self.assertAlmostEqual(sparse["lambda_abs"], dense["lambda_abs"], places=7)
            self.assertLess(sparse["residual_max"], 1e-8)

    def test_bipartite_and_disconnected(self):
        value = spectrum(nx.complete_bipartite_graph(4, 4))
        self.assertLess(value["lambda_abs"], 1e-10)
        self.assertTrue(value["numeric_pass"])
        graph = nx.disjoint_union(nx.complete_graph(5), nx.complete_graph(5))
        with self.assertRaises(ValueError):
            spectrum(graph)
        self.assertFalse(exact_paper_acceptance(graph))

    def test_exact_paper_criterion_known_graphs(self):
        self.assertTrue(exact_paper_acceptance(nx.petersen_graph()))
        self.assertTrue(exact_paper_acceptance(nx.complete_graph(5)))
        self.assertFalse(exact_paper_acceptance(nx.complete_bipartite_graph(3, 3)))
        self.assertFalse(exact_paper_acceptance(nx.cycle_graph(4)))
        for seed in range(10):
            graph = nx.random_regular_graph(4, 16, seed=seed)
            diagnostic = spectrum(graph)
            expected = diagnostic["numeric_pass"] and not nx.is_bipartite(graph)
            self.assertEqual(exact_paper_acceptance(graph), expected)


class SimulatorTests(unittest.TestCase):
    def test_traffic_conservation_connected_flooding(self):
        for d in (4, 8):
            n = 40
            graph = nx.random_regular_graph(d, n, seed=21)
            trace = make_trace(n, 12, 0, 3)
            result = simulate(graph, trace, config(3), "heterogeneous")
            for row in result["messages"]:
                self.assertEqual(row["transmissions"], n * d - (n - 1))
                self.assertEqual(row["duplicates"], (d - 2) * n + 2)
                self.assertEqual(row["unreachable_fraction"], 0)

    def test_shortest_path_oracle_zero_serialization(self):
        graph = nx.random_regular_graph(4, 30, seed=8)
        trace = make_trace(30, 20, 0, 1)
        result = simulate(graph, trace, config(payload=0), "heterogeneous")["messages"][0]
        distances = nx.single_source_dijkstra_path_length(graph, trace["sources"][0],
                    weight=lambda u, v, _: edge_latency(u, v, "heterogeneous", trace))
        times = sorted(distances.values())
        for q in (50, 95, 99, 100):
            self.assertAlmostEqual(result[f"t{q}_ms"], times[math.ceil(q * 30 / 100) - 1])

    def test_single_uplink_serialization(self):
        graph = nx.star_graph(3)
        trace = make_trace(4, 23, 0, 1)
        trace["sources"] = [0]
        result = simulate(graph, trace, config(payload=1000), "uniform")["messages"][0]
        self.assertEqual(result["transmissions"], 3)
        self.assertEqual(result["t100_ms"], 34.0)  # 3*8ms serialization + 10ms propagation
        self.assertEqual(result["duplicates"], 0)

    def test_fifo_contention_between_messages(self):
        graph = nx.path_graph(2)
        trace = make_trace(2, 4, 0, 2)
        trace["sources"] = [0, 0]
        rows = simulate(graph, trace, config(messages=2, interval=1), "uniform")["messages"]
        self.assertEqual(rows[0]["t100_ms"], 18.0)
        self.assertEqual(rows[1]["t100_ms"], 25.0)  # second finishes at 16, arrives 26, launch 1

    def test_partition_null_threshold_and_failed_bytes(self):
        graph = nx.path_graph(5)
        trace = make_trace(5, 3, 0.2, 1)
        trace["failed"], trace["sources"] = [2], [0]
        row = simulate(graph, trace, config(), "uniform")["messages"][0]
        self.assertEqual(row["reached"], 2)
        self.assertEqual(row["available"], 4)
        self.assertEqual(row["unreachable_fraction"], 0.5)
        self.assertEqual(row["t50_ms"], 18.0)
        self.assertIsNone(row["t95_ms"])
        self.assertEqual(row["transmissions"], 2)
        self.assertEqual(row["failed_transmissions"], 1)
        self.assertEqual(row["wire_bytes"], 2000)

    def test_failure_traces_nested_and_reproducible(self):
        low, high = make_trace(100, 1, .1, 8), make_trace(100, 1, .3, 8)
        self.assertEqual(low, make_trace(100, 1, .1, 8))
        self.assertTrue(set(low["failed"]) < set(high["failed"]))
        self.assertEqual(low["regions"], high["regions"])


if __name__ == "__main__":
    unittest.main()
