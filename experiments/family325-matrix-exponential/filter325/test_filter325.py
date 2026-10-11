import json
from pathlib import Path
from fractions import Fraction as F
import unittest
import numpy as np
from scipy import sparse,linalg
from filter325.core import geometry,choose_degree,exp_bounds,sqrt_upper,prepare,count_sparse_products
from filter325.data import make_case,decimal_action

CONFIG = json.loads((Path(__file__).parent/'config.json').read_text())


class FilterChecks(unittest.TestCase):
    def test_zero_and_scalar(self):
        x = np.array([0.,1.,-2.,3.])
        for value in (0.,-4.,2.):
            A = sparse.eye(4,format='csr')*value
            for method in ('crouzeix2','crouzeix_old','norm_taylor','normal1','scipy','scipy_cached','arnoldi'):
                p = prepare(A,method,'1e-10',CONFIG)
                np.testing.assert_allclose(p.apply(x)[0],np.exp(value)*x,rtol=3e-14,atol=1e-14)
                self.assertTrue(np.all(p.apply(np.zeros(4))[0] == 0))

    def test_nonnormal_scalar_boundary_bound_is_not_spectrum_bound(self):
        # Sharpness witness for the polynomial z: numerical radius 1, norm 2.
        A = sparse.csr_matrix([[0.,2.],[0.,0.]])
        g = geometry(A)
        self.assertEqual(g.radius,F(1))
        self.assertEqual(linalg.norm(A.toarray(),2),2.)
        x = np.array([0.,1.])
        for method in ('crouzeix2','crouzeix_old','norm_taylor'):
            p = prepare(A,method,'1e-10',CONFIG)
            np.testing.assert_allclose(p.apply(x)[0],np.array([2.,1.]),atol=1e-14)

    def test_exact_enclosure_witness_against_dense_diagnostics(self):
        for family in ('directed_regular','directed_hub','jordan','grcar'):
            A,_ = make_case(family,16,32501,1)
            g = geometry(A)
            S = (abs(g.B)+abs(g.B).T).toarray()/2
            self.assertLessEqual(linalg.eigvalsh(S)[-1],float(g.radius)+2e-12)
            # Diagnostic eigensolve is NOT used by the production certificate.
            for theta in np.linspace(0,2*np.pi,13):
                B = g.B.toarray().astype(complex)*np.exp(-1j*theta)
                self.assertLessEqual(linalg.eigvalsh((B+B.conj().T)/2)[-1],float(g.radius)+2e-12)

    def test_tail_against_high_precision_scalar_and_vector(self):
        from decimal import Decimal,localcontext
        with localcontext() as ctx:
            ctx.prec = 100
            for c,r in ((0,1),(-4,8),(-8,13)):
                lo,hi = exp_bounds(F(c))
                e = Decimal(c).exp()
                self.assertLessEqual(Decimal(lo.numerator)/Decimal(lo.denominator),e)
                self.assertGreaterEqual(Decimal(hi.numerator)/Decimal(hi.denominator),e)
                m,_,bound = choose_degree(F(r),hi,F(2),F('1e-10'))
                tail = Decimal(r).exp()-sum(Decimal(r)**k/Decimal(__import__('math').factorial(k)) for k in range(m+1))
                self.assertGreaterEqual(float(bound),float(2*e*tail))
        A,X = make_case('grcar',16,32501,2)
        for method in ('crouzeix2','crouzeix_old','norm_taylor'):
            p = prepare(A,method,'1e-7',CONFIG)
            ref,_ = decimal_action(A,X,degree=p.degree,center=float(p.geom.c))
            high = np.array([[float(v) for v in row] for row in ref])
            for j in range(2):
                np.testing.assert_allclose(p.apply(X[:,j])[0],high[:,j],rtol=1e-12,atol=1e-13)

    def test_old_constant_degree_and_counting_same_sparse_path(self):
        A,X = make_case('directed_regular',16,32501,1)
        new = prepare(A,'crouzeix2','1e-7',CONFIG)
        old = prepare(A,'crouzeix_old','1e-7',CONFIG)
        self.assertGreaterEqual(old.degree,new.degree)
        self.assertEqual(new.geom.radius,old.geom.radius)
        with count_sparse_products(16) as counts:
            y,_ = new.apply(X[:,0])
        self.assertEqual(counts['csr_forward'],new.degree)
        s = prepare(A,'scipy','1e-7',CONFIG)
        expected,_ = s.apply(X[:,0])
        with count_sparse_products(16) as counts:
            counted,_ = s.apply(X[:,0])
        np.testing.assert_array_equal(expected,counted)
        self.assertGreater(counts['csr_forward'],0)
        cached = prepare(A,'scipy_cached','1e-7',CONFIG)
        np.testing.assert_array_equal(expected,cached.apply(X[:,0])[0])

    def test_normal_controls(self):
        for family in ('symmetric_ring','normal_cycle'):
            A,X = make_case(family,16,32501,1)
            np.testing.assert_array_equal((A.T@A-A@A.T).toarray(),np.zeros((16,16)))
            p = prepare(A,'normal1','1e-10',CONFIG)
            err = linalg.norm(p.apply(X[:,0])[0]-linalg.expm(A.toarray())@X[:,0])
            self.assertLessEqual(err,p.operator_bound*linalg.norm(X[:,0])+1e-14)


if __name__ == '__main__':
    unittest.main()
