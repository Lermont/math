"""Prespecified synthetic matrices and independent high-precision references."""
import hashlib
import json
import math
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal, localcontext
import numpy as np
from scipy import sparse, linalg
from .core import choose_degree, sqrt_upper, float_up

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def case_specs(config):
    return [(family, n, seed) for family, n in config['small_cases'] for seed in config['seeds']] + [tuple(a) for a in config['large_cases']]


def make_case(family, n, seed, vectors=8):
    I = sparse.eye(n, format='csr')
    S = sparse.diags(np.ones(n-1), 1, shape=(n,n), format='csr')
    P = sparse.csr_matrix((np.ones(n), (np.arange(n), (np.arange(n)+1)%n)), shape=(n,n))
    if family == 'symmetric_ring':
        A = 2*(P+P.T)-4*I
    elif family == 'normal_cycle':
        A = 4*(P-I)
    elif family == 'directed_regular':
        rng = np.random.default_rng(seed)
        cols = []
        for i in range(n):
            q = rng.choice(n-1, size=4, replace=False)
            cols.extend((q+(q>=i)).tolist())
        P = sparse.csr_matrix((np.full(4*n, .25), (np.repeat(np.arange(n), 4), cols)), shape=(n,n))
        A = 8*(P-I)
    elif family == 'directed_hub':
        hub = sparse.csr_matrix((np.ones(n), (np.arange(n), np.zeros(n,dtype=int))), shape=(n,n))
        A = 3*hub+P-4*I
    elif family == 'jordan':
        A = -4*I+8*S
    elif family == 'grcar':
        A = -4*I+2*(S+S@S+S@S@S-S.T)
    else:
        raise ValueError(family)
    A = A.tocsr()
    A.sum_duplicates(); A.eliminate_zeros(); A.sort_indices()
    rng = np.random.default_rng(seed+100000+n)
    scale = 2**math.ceil(math.log2(math.sqrt(n)))
    X = (2*rng.integers(0,2,size=(n,vectors))-1).astype(float)/scale
    return A, X


def decimal_action(A, X, degree=None, center=0., dps=80):
    """Independent decimal sparse series; returns decimals without float rounding.

    Unshifted series for reference; shifted finite polynomial for roundoff audit.
    This does not call benchmark geometry/prepare/apply.
    """
    X = np.asarray(X)
    if X.ndim == 1:
        X = X[:, None]
    n, nvec = X.shape
    with localcontext() as ctx:
        ctx.prec = dps
        dc = Decimal.from_float(float(center))
        rows = []
        for i in range(n):
            row = {int(A.indices[k]): Decimal.from_float(float(A.data[k])) for k in range(A.indptr[i], A.indptr[i+1])}
            row[i] = row.get(i, Decimal(0))-dc
            rows.append([(j,a) for j,a in row.items() if a])
        vals = [[Decimal.from_float(float(v)) for v in row] for row in X]
        total = [row[:] for row in vals]
        meta = {}
        if degree is None:
            # Exact rational infinity-norm bound, converted to Euclidean error.
            norminf = max(sum((F(a) for _,a in row if a >= 0), F(0)) +
                          sum((-F(a) for _,a in row if a < 0), F(0)) for row in rows)
            xinf = max(F(abs(v)) for row in vals for v in row)
            C = sqrt_upper(F(n))*xinf
            degree, _, bound = choose_degree(norminf, F(1), max(C,F(1,10**100)), F(1,10**65))
            meta = {'reference_degree': degree, 'reference_exact_series_tail_2norm': float_up(bound),
                    'reference_norm_inf': float_up(norminf)}
        zero = Decimal(0)
        for k in range(1,degree+1):
            next_vals = []
            for i,row in enumerate(rows):
                out = [sum((a*vals[j][v] for j,a in row), zero)/k for v in range(nvec)]
                next_vals.append(out)
                for v in range(nvec):
                    total[i][v] += out[v]
            vals = next_vals
        factor = dc.exp()
        answer = [[v*factor for v in row] for row in total]
    return answer, meta


def decimal_error(a, b, dps=110):
    with localcontext() as ctx:
        ctx.prec = dps
        return float(sum((a[i][0]-b[i][0])**2 for i in range(len(a))).sqrt())


def prepare_datasets(out, config):
    data_dir = out/'data'
    data_dir.mkdir(exist_ok=True)
    cases = []
    for family,n,seed in case_specs(config):
        name = f'{family}_n{n}_s{seed}'
        path = data_dir/name
        path.mkdir(exist_ok=True)
        if (path/'case.json').exists():
            cases.append(json.loads((path/'case.json').read_text(encoding='utf-8')))
            continue
        A,X = make_case(family,n,seed,config['vectors'])
        sparse.save_npz(path/'A.npz', A)
        np.save(path/'X.npy',X)
        comm = A.T@A-A@A.T
        normality = float(sparse.linalg.norm(comm,'fro')/max(sparse.linalg.norm(A,'fro')**2,1e-300))
        print(f'Reference {name}',flush=True)
        ref80, meta = decimal_action(A,X,dps=config['reference_dps'])
        ref110, _ = decimal_action(A,X[:,0],dps=config['reference_check_dps'])
        high = np.array([[float(v) for v in row] for row in ref80])
        refinement = decimal_error([[row[0]] for row in ref80],ref110)
        # Measure conversion error directly with Decimal exact float conversion.
        with localcontext() as ctx:
            ctx.prec = 110
            conversion = max(float(sum((ref80[i][j]-Decimal.from_float(high[i,j]))**2 for i in range(n)).sqrt()) for j in range(X.shape[1]))
        if n <= 128:
            dense = linalg.expm(A.toarray())@X
            discrepancy = np.linalg.norm(dense-high,axis=0)
            reference = dense
            method = 'scipy_dense_Pade_crosschecked_decimal80'
        else:
            discrepancy = np.zeros(X.shape[1])
            reference = high
            method = 'independent_decimal80_unshifted_series_refined110_first_vector'
        np.save(path/'reference.npy',reference)
        np.save(path/'high_precision_rounded.npy',high)
        (path/'reference_first_vector_110digits.json').write_text(json.dumps([str(row[0]) for row in ref110]),encoding='utf-8')
        record = {'name':name,'family':family,'n':n,'seed':seed,'nnz':A.nnz,
                  'normal_control':family in ('symmetric_ring','normal_cycle'),
                  'synthetic':True,'nonnormality_fro':normality,
                  'reference_method':method,'reference_refinement_2norm':refinement,
                  'reference_float_conversion_2norm_max':conversion,
                  'reference_dense_vs_decimal_2norm':discrepancy.tolist(), **meta,
                  'hashes':{p.name:digest(p) for p in path.iterdir() if p.is_file()}}
        (path/'case.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        cases.append(record)
    (out/'cases.json').write_text(json.dumps(cases,indent=2),encoding='utf-8')
    return cases
