import itertools
import unittest
import numpy as np
import kmedoids
from onebatch import OneBatchPAM
from .core import l1_f32, make_dataset, score_integer, miss_probability, auto_batch


class ScaleChecks(unittest.TestCase):
    def test_distances_exact_and_bounded_blocks(self):
        x = np.array([[0, 0], [0, 0], [-100005, 100005], [100003, -100004]], dtype=np.int32)
        exact = np.array([[sum(abs(int(a)-int(b)) for a, b in zip(p, q))
                           for q in x] for p in x])
        for block in (1, 3, 128):
            d = l1_f32(x, x, block)
            np.testing.assert_array_equal(d, exact)
            self.assertEqual(d.dtype, np.float32)
            self.assertTrue(d.flags.c_contiguous)
        self.assertEqual(l1_f32(x, x[:0]).shape, (4, 0))

    def test_score_against_scalar_and_permuted_ids(self):
        x, groups = make_dataset("rare_triplets", 70, 31)
        meds = [0, 9, 16, 30, 41]
        q, nearest, labels = score_integer(x, groups, meds)
        scalar = [min(sum(abs(int(a)-int(b)) for a, b in zip(p, x[m])) for m in meds) for p in x]
        np.testing.assert_array_equal(nearest, scalar)
        self.assertEqual(q["cost"], sum(scalar))
        self.assertEqual(q["cost"], q["bulk_cost"] + q["rare_cost"])
        self.assertEqual(q["rare_groups_total"], 8)
        self.assertEqual(q["rare_count"], 24)
        self.assertEqual(set(labels) - set(meds), set())
        self.assertEqual(q["rare_served_within_20"], 3*q["rare_groups_covered"])
        self.assertEqual(len(np.unique(x, axis=0)), len(x))

    def test_native_onebatch_callable_matches_precomputed(self):
        x, groups = make_dataset("rare_triplets", 100, 47)
        n, batch, k, seed = len(x), 35, 8, 101
        rng = np.random.default_rng(seed)
        cols = rng.choice(n, batch, replace=False)
        sampled = l1_f32(x, x[cols])
        expected = OneBatchPAM(n_medoids=k, distance="precomputed", random_state=rng,
                               weighting=True, normalize=True, n_jobs=1).fit(sampled)
        actual = OneBatchPAM(n_medoids=k, batch_size=batch,
                             distance=lambda a, b, jobs: l1_f32(a, b),
                             random_state=seed, n_jobs=1).fit(x)
        np.testing.assert_array_equal(expected.medoid_indices_, actual.medoid_indices_)
        self.assertEqual(expected.inertia_, actual.inertia_)
        self.assertEqual(score_integer(x, groups, actual.medoid_indices_)[0]["cost"],
                         score_integer(x, groups, expected.medoid_indices_)[0]["cost"])

    def test_fasterpam_float32_loss_is_full_integer_cost(self):
        x, groups = make_dataset("rare_singletons", 70, 47)
        d = l1_f32(x, x)
        fitted = kmedoids.fasterpam(d, 20, random_state=202, n_cpu=1)
        self.assertEqual(fitted.loss, score_integer(x, groups, fitted.medoids)[0]["cost"])

    def test_probability_against_enumeration(self):
        for n, b, r in ((7, 3, 2), (7, 6, 2), (8, 1, 1), (8, 8, 1)):
            selections = list(itertools.combinations(range(n), b))
            missed = sum(not (set(s) & set(range(r))) for s in selections) / len(selections)
            self.assertAlmostEqual(miss_probability(n, b, r), missed)
        self.assertEqual(auto_batch(10000, 20), 1220)


if __name__ == "__main__":
    unittest.main()
