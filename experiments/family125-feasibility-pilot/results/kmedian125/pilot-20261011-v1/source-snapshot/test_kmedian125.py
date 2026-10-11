import unittest
from fractions import Fraction
from itertools import combinations, product
import numpy as np
from kmedian125.data import synthetic, distance_matrix, independent_cost, validate_metric
from kmedian125.methods import (cost, greedy, local_search, exact_enumeration, solve_milp,
                               solve_lp, verify_certificate, exact_rounding_distribution,
                               quantize_openings, dependent_round)

class RoundingTests(unittest.TestCase):
    def test_complete_exact_moments(self):
        # Exhaust all quarter-grid four-coordinate inputs with integral sum.
        for counts in product(range(5), repeat=4):
            if sum(counts) % 4:
                continue
            distribution = exact_rounding_distribution(counts, 4)
            self.assertEqual(sum(distribution.values()), 1)
            for state in distribution:
                self.assertEqual(sum(state), sum(counts))
                self.assertTrue(all(v in (0, 4) for v in state))
            for i in range(4):
                mean = sum(p*state[i] for state, p in distribution.items())
                self.assertEqual(mean, counts[i])
                for j in range(i):
                    cross = sum(p*state[i]*state[j] for state, p in distribution.items())
                    self.assertLessEqual(cross, counts[i]*counts[j])

    def test_sampled_budget_and_quantization(self):
        y = np.array([.2, .6, .7, .5, 1., 0.])
        counts = quantize_openings(y, 3, 10**6)
        for seed in range(50):
            out = dependent_round(counts, 10**6, np.random.default_rng(seed))
            self.assertEqual(len(out), 3)
            self.assertEqual(len(set(out)), 3)
            self.assertIn(4, out)
            self.assertNotIn(5, out)
        with self.assertRaises(ValueError):
            dependent_round([1, 1, 1], 2, np.random.default_rng(1))

class OptimizationTests(unittest.TestCase):
    def test_milp_and_dual_against_proven_optima(self):
        for seed in range(8):
            dataset = synthetic("graph" if seed % 2 else "compact", 9, 3, seed)
            d = distance_matrix(dataset)
            enum_meds, opt, count = exact_enumeration(d, 3)
            self.assertEqual(count, 84)
            self.assertEqual(independent_cost(dataset, enum_meds), opt)
            milp_meds, result = solve_milp(d, 3, 10)
            self.assertEqual(result["status"], 0)
            self.assertEqual(cost(d, milp_meds), opt)
            y, lp = solve_lp(d, 3, 10)
            lower = verify_certificate(d, lp["certificate"], 3)
            self.assertLessEqual(lower, opt)
            self.assertAlmostEqual(y.sum(), 3)

    def test_distinct_candidates_model(self):
        # Rectangular client-facility model, separate from the F=J benchmark.
        clients = [0, 2, 7, 10, 15]
        facilities = [-2, 3, 12, 18]
        d = np.array([[abs(a-b) for b in facilities] for a in clients])
        meds, val, _ = exact_enumeration(d, 2)
        expected = min(sum(min(abs(p-facilities[i]) for i in s) for p in clients)
                       for s in combinations(range(4), 2))
        self.assertEqual(val, expected)
        milp_meds, result = solve_milp(d, 2, 10)
        self.assertEqual(result["status"], 0)
        self.assertEqual(cost(d, milp_meds), expected)
        _, lp = solve_lp(d, 2, 10)
        self.assertLessEqual(verify_certificate(d, lp["certificate"], 2), expected)

    def test_swap_local_optimum_and_edge_budgets(self):
        dataset = synthetic("compact", 12, 3, 45)
        d = distance_matrix(dataset)
        for k in (1, 3, 12):
            initial = greedy(d, k)
            meds, trace, done = local_search(d, initial)
            self.assertTrue(done)
            self.assertEqual(len(meds), k)
            self.assertTrue(all(a > b for a, b in zip(trace, trace[1:])))
            for slot in range(k):
                for candidate in set(range(12))-set(meds):
                    trial = meds.copy()
                    trial[slot] = candidate
                    self.assertGreaterEqual(cost(d, trial), cost(d, meds))
        with self.assertRaises(ValueError):
            greedy(d, 13)

    def test_library_baselines_objective_and_feasibility(self):
        import kmedoids
        from onebatch import OneBatchPAM
        ds = synthetic("outliers", 18, 3, 99)
        d = distance_matrix(ds)
        result = kmedoids.fasterpam(d.astype(float), 3, random_state=101, n_cpu=1)
        self.assertEqual(independent_cost(ds, result.medoids), int(result.loss))
        ob = OneBatchPAM(n_medoids=3, distance="precomputed", weighting=True,
                         normalize=True, random_state=101).fit(d)
        self.assertEqual(independent_cost(ds, ob.medoid_indices_), cost(d, ob.medoid_indices_))
        self.assertLessEqual(len(set(ob.medoid_indices_)), 3)

class MetricTests(unittest.TestCase):
    def test_all_triangle_inequalities_and_independent_evaluator(self):
        for structure in ("compact", "unbalanced", "outliers", "graph"):
            ds = synthetic(structure, 18, 3, 11)
            d = distance_matrix(ds)
            validate_metric(d)
            self.assertTrue(np.array_equal(distance_matrix(ds, [1, 4, 9]), d[:, [1, 4, 9]]))
            for meds in ([0, 1, 2], [4, 8, 17]):
                self.assertEqual(independent_cost(ds, meds), cost(d, meds))

    def test_reject_nonmetric_and_bad_medoid_ids(self):
        with self.assertRaises(ValueError):
            validate_metric(np.array([[0, 1, 4], [1, 0, 1], [4, 1, 0]]))
        ds = synthetic("compact", 8, 2, 1)
        for meds in ([1, 1], [1], [1, 8]):
            with self.assertRaises(ValueError):
                independent_cost(ds, meds)

if __name__ == "__main__":
    unittest.main()
