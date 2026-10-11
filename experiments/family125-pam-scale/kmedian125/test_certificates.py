import unittest
import numpy as np
from kmedian125.certify import strengthen_certificate, verify_strengthened
from kmedian125.methods import exact_enumeration, dual_certificate

class ExactBoundTests(unittest.TestCase):
    def test_arbitrary_prices_are_valid_not_only_solver_prices(self):
        rng = np.random.default_rng(810)
        # The certificate even holds without the triangle inequality.
        for _ in range(40):
            d = rng.integers(0, 30, (6, 8))
            alpha = rng.integers(-10, 50, 6)
            for k in (1, 3, 8):
                original = dual_certificate(d, alpha, k)
                cert = strengthen_certificate(d, original, k)
                bound = verify_strengthened(d, cert, k)
                _, opt, _ = exact_enumeration(d, k)
                self.assertLessEqual(bound, opt)

    def test_tampered_certificate_is_rejected(self):
        d = np.array([[0, 2, 3], [2, 0, 1], [3, 1, 0]])
        cert = strengthen_certificate(d, dual_certificate(d, [2, 2, 2], 1), 1)
        cert["facility_charge_numerators"][0] += 1
        with self.assertRaises(AssertionError):
            verify_strengthened(d, cert, 1)

if __name__ == "__main__":
    unittest.main()
