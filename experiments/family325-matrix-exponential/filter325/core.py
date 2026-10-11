"""Exact enclosure/degree certificates, float64 action implementations.

The certificates cover exact-arithmetic approximation, NOT floating evaluation.
This is a scalar application of family 325; Taylor and the disk are our choices.
"""
from dataclasses import dataclass
from fractions import Fraction as F
import math
import time
from contextlib import contextmanager
import numpy as np
from scipy import sparse, linalg
from scipy.sparse.linalg import expm_multiply


def float_up(q):
    """Convert a nonnegative rational to an enclosing binary64 endpoint."""
    v = float(q)
    if F.from_float(v) < q:
        v = float(np.nextafter(v, np.inf))
    return v


def sqrt_upper(q, bits=80):
    """Integer arithmetic, including final exact comparison; not an estimate."""
    q = F(q)
    if q < 0:
        raise ValueError('negative square root')
    scale = 1 << bits
    a = math.isqrt((q.numerator * scale * scale) // q.denominator)
    out = F(a, scale)
    return out if out*out == q else F(a+1, scale)


def exp_bounds(c, target=F(1, 10**70)):
    """Rational lower/upper endpoints by positive series and geometric tail."""
    c = F(c)
    a, s, term, k = abs(c), F(1), F(1), 0
    if a == 0:
        return F(1), F(1)
    while True:
        k += 1
        term *= a / k
        s += term
        if k+2 > a:
            tail = term*a/(k+1)/(1-a/F(k+2))
            if tail < target:
                break
        if k > 2000:
            raise ValueError('exponential certificate budget exceeded')
    return (s, s+tail) if c >= 0 else (1/(s+tail), 1/s)


def choose_degree(radius, exp_upper, constant, tolerance):
    """Least degree accepted by this geometric-tail certificate (not minimax)."""
    r, e, C, tol = map(F, (radius, exp_upper, constant, tolerance))
    if r < 0 or C <= 0 or tol <= 0:
        raise ValueError('invalid degree-selection arguments')
    if r == 0:
        return 0, F(0), F(0)
    term = F(1)
    for m in range(1000):
        term *= r / (m+1)  # first omitted term r^(m+1)/(m+1)!
        if m+2 > r:
            scalar = e * term / (1-r/F(m+2))
            if C*scalar <= tol:
                return m, scalar, C*scalar
    raise ValueError('degree budget exceeded')


def exact_dyadic_csr(B):
    """Represent the actual stored float64 matrix exactly, as integers / 2^k."""
    ratios = [float(v).as_integer_ratio() for v in B.data]
    denom = max((b for _, b in ratios), default=1)
    assert denom & (denom-1) == 0
    nums = [a*(denom//b) for a, b in ratios]
    return nums, denom


@dataclass
class Geometry:
    B: object
    c: F
    radius: F
    norm_radius: F
    exp_lo: F
    exp_hi: F
    certificate: dict
    geometry_s: float
    scalar_setup_s: float


def geometry(A, use_numerical_range=True, iterations=12, quantization=1048576):
    start = time.perf_counter()
    if np.iscomplexobj(A.data) or not np.isfinite(A.data).all():
        raise ValueError('this certified prototype accepts finite real matrices')
    diag = A.diagonal()
    c = (F.from_float(float(diag.min()))+F.from_float(float(diag.max())))/2
    cf = float(c)
    if F.from_float(cf) != c:
        raise ValueError('center not exactly representable')
    B = (A - sparse.eye(A.shape[0], format='csr') * cf).tocsr()
    B.eliminate_zeros()
    # Verify the subtraction, so the exact bound concerns the original A.
    for a, b in zip(diag, B.diagonal()):
        if F.from_float(float(a))-c != F.from_float(float(b)):
            raise ValueError('shift rounded: outside this restricted prototype')
    nums, denom = exact_dyadic_csr(B)
    n = B.shape[0]
    rows, cols = [0]*n, [0]*n
    for i in range(n):
        for k in range(B.indptr[i], B.indptr[i+1]):
            a = abs(nums[k])
            rows[i] += a
            cols[int(B.indices[k])] += a
    norm_radius = sqrt_upper(F(max(rows)*max(cols), denom*denom))
    row_bound = max(F(rows[i]+cols[i], 2*denom) for i in range(n))
    certificate = {'center': str(c), 'matrix_denominator': str(denom),
                   'norm_radius': str(norm_radius), 'row_radius': str(row_bound),
                   'candidate_iterations': 0, 'setup_aux_spmv': 0}
    radius = norm_radius
    if use_numerical_range:
        M = abs(B)
        S = ((M + M.T)*0.5).tocsr()
        v = np.ones(n)
        alpha = float(row_bound)
        if alpha:
            for _ in range(iterations):
                v = S @ v + alpha*v
                v /= v.max()
        ints = np.maximum(1, np.rint(v*quantization)).astype(np.int64)
        # Exact verification using B, NOT float S or an iterative eigenvalue.
        numer = [0]*n
        for i in range(n):
            for k in range(B.indptr[i], B.indptr[i+1]):
                j, a = int(B.indices[k]), abs(nums[k])
                numer[i] += a*int(ints[j])
                numer[j] += a*int(ints[i])
        collatz = max(F(numer[i], 2*denom*int(ints[i])) for i in range(n))
        radius = min(norm_radius, row_bound, collatz)
        certificate.update(positive_witness=ints.tolist(), collatz_radius=str(collatz),
                           candidate_iterations=iterations if alpha else 0,
                           setup_aux_spmv=iterations if alpha else 0)
    certificate['radius'] = str(radius)
    gs = time.perf_counter()-start
    start = time.perf_counter()
    elo, ehi = exp_bounds(c)
    es = time.perf_counter()-start
    return Geometry(B, c, radius, norm_radius, elo, ehi, certificate, gs, es)


@dataclass
class Prepared:
    method: str
    A: object
    tolerance: float
    config: dict
    geom: Geometry | None = None
    degree: int | None = None
    scalar_bound: float | None = None
    operator_bound: float | None = None
    constant: float | None = None
    trace: float | None = None
    factor: float | None = None
    setup_s: float = 0.
    degree_s: float = 0.
    coefficient_s: float = 0.
    internal: dict | None = None

    def apply(self, x):
        if self.method == 'scipy':
            return expm_multiply(self.A, x, traceA=self.trace), {}
        if self.method == 'scipy_cached':
            from scipy.sparse.linalg import _expm_multiply as em
            q = self.internal
            y = em._expm_multiply_simple_core(q['B'],x,1.,q['mu'],q['m'],q['s'],2**-53,False)
            return y, {'degree':q['m'],'scaling':q['s']}
        if self.method == 'arnoldi':
            return arnoldi(self.A, x, self.tolerance, self.config)
        term, y = x.copy(), x.copy()
        for k in range(1, self.degree+1):
            term = (self.geom.B @ term) / k
            y += term
        return y*self.factor, {'degree': self.degree}


def prepare(A, method, tolerance, config):
    t0 = time.perf_counter()
    p = Prepared(method, A, float(tolerance), config)
    if method == 'scipy':
        p.trace = float(A.diagonal().sum())
    elif method == 'scipy_cached':
        from scipy.sparse.linalg import _expm_multiply as em
        mu = float(A.diagonal().sum())/float(A.shape[0])
        B = A-mu*sparse.eye(A.shape[0],format='csr')
        n1 = em._exact_1_norm(B)
        if n1 == 0:
            m,s = 0,1
        else:
            info = em.LazyOperatorNormInfo(B,A_1_norm=n1,ell=2)
            m,s = em._fragment_3_1(info,1,2**-53,ell=2)
        p.internal = {'B':B,'mu':mu,'m':m,'s':s}
        p.degree = m
    elif method == 'arnoldi':
        pass
    else:
        p.geom = geometry(A, method != 'norm_taylor', config['collatz_iterations'], config['collatz_quantization'])
        t = time.perf_counter()
        constant = F(2) if method == 'crouzeix2' else 1+sqrt_upper(F(2)) if method == 'crouzeix_old' else F(1)
        p.constant = float_up(constant)
        p.degree, scalar, bound = choose_degree(p.geom.radius, p.geom.exp_hi, constant,
                                               F(tolerance)*F(config['approximation_budget']))
        p.scalar_bound, p.operator_bound = float_up(scalar), float_up(bound)
        p.degree_s = time.perf_counter()-t
        t = time.perf_counter()
        p.factor = math.exp(float(p.geom.c))
        p.coefficient_s = time.perf_counter()-t
    p.setup_s = time.perf_counter()-t0
    return p


def arnoldi(A, x, tolerance, config):
    beta = linalg.norm(x)
    if beta == 0:
        return x.copy(), {'degree': 0, 'indicator': 0., 'stop': 'zero'}
    n = len(x)
    mmax = min(n, config['arnoldi_max'])
    V, H = np.zeros((n, mmax+1)), np.zeros((mmax+1, mmax))
    V[:, 0] = x/beta
    previous = None
    indicator = math.inf
    for j in range(mmax):
        w = A @ V[:, j]
        for _ in range(2):
            for i in range(j+1):
                hij = np.dot(V[:, i], w)
                H[i, j] += hij
                w -= hij * V[:, i]
        h = linalg.norm(w)
        H[j+1, j] = h
        happy = h <= 32*np.finfo(float).eps*max(1., linalg.norm(H[:j+1, j]))
        if h > 0:
            V[:, j+1] = w/h
        m = j+1
        if m % config['arnoldi_step'] == 0 or happy or m == mmax:
            y = beta * (V[:, :m] @ linalg.expm(H[:m, :m])[:, 0])
            if previous is not None:
                indicator = float(linalg.norm(y-previous))
            if happy or indicator <= config['arnoldi_stop_factor']*tolerance*beta:
                return y, {'degree': m, 'indicator': indicator if math.isfinite(indicator) else None,
                           'stop': 'happy_breakdown_numeric' if happy else 'successive_difference_heuristic'}
            previous = y
    return y, {'degree': mmax, 'indicator': indicator, 'stop': 'budget'}


@contextmanager
def count_sparse_products(n):
    """Instrument the same CSR/CSC code path; never time while patched."""
    from scipy.sparse._compressed import _cs_matrix
    original_v = _cs_matrix._matmul_vector
    original_m = _cs_matrix._matmul_multivector
    counts = {'csr_forward': 0, 'csc_adjoint': 0, 'other': 0}
    def record(obj, cols):
        if obj.shape == (n, n):
            key = 'csr_forward' if obj.format == 'csr' else 'csc_adjoint' if obj.format == 'csc' else 'other'
            counts[key] += cols
    def vector(obj, v):
        record(obj, 1)
        return original_v(obj, v)
    def matrix(obj, v):
        record(obj, v.shape[1])
        return original_m(obj, v)
    _cs_matrix._matmul_vector, _cs_matrix._matmul_multivector = vector, matrix
    try:
        yield counts
    finally:
        _cs_matrix._matmul_vector, _cs_matrix._matmul_multivector = original_v, original_m
