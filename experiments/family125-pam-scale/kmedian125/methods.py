"""Components and baselines. LP-DR16-swap has NO family-125 approximation guarantee."""
from __future__ import annotations
from fractions import Fraction
from itertools import combinations
from time import perf_counter
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, milp
from scipy.sparse import coo_matrix, vstack

def cost(d, meds):
    return int(d[:, list(meds)].min(axis=1).sum())

def greedy(d, k):
    n, m = d.shape
    if not 1 <= k <= m:
        raise ValueError("invalid k")
    nearest = np.full(n, np.inf)
    meds = []
    for _ in range(k):
        values = np.minimum(d, nearest[:, None]).sum(axis=0)
        values[meds] = np.inf
        i = int(np.argmin(values))
        meds.append(i)
        nearest = np.minimum(nearest, d[:, i])
    return meds

def local_search(d, meds, max_swaps=100):
    meds = list(map(int, meds))
    current = cost(d, meds)
    trace = [current]
    if len(meds) == d.shape[1]:
        return meds, trace, True
    for _ in range(max_swaps):
        values = d[:, meds]
        owner = values.argmin(axis=1)
        closest = values.min(axis=1)
        second = np.partition(values, 1, axis=1)[:, 1] if len(meds) > 1 else np.full(len(d), np.inf)
        best_cost, move = current, None
        for slot in range(len(meds)):
            remain = np.where(owner == slot, second, closest)
            candidate = np.minimum(d, remain[:, None]).sum(axis=0).astype(float)
            candidate[meds] = np.inf
            new = int(np.argmin(candidate))
            if candidate[new] < best_cost:
                best_cost, move = int(candidate[new]), (slot, new)
        if move is None:
            return meds, trace, True
        meds[move[0]] = move[1]
        current = cost(d, meds)
        assert current == best_cost and current < trace[-1]
        trace.append(current)
    return meds, trace, False

def exact_enumeration(d, k):
    best, best_cost, count = None, None, 0
    for meds in combinations(range(d.shape[1]), k):
        val = cost(d, meds)
        count += 1
        if best_cost is None or val < best_cost:
            best, best_cost = list(meds), val
    return best, best_cost, count

def model(d, k):
    """Client-major x_ji, y first. Exactly k is equivalent by padding facilities."""
    n, m = d.shape
    v = n * m
    idx = np.arange(v, dtype=np.int32)
    link = coo_matrix((np.r_[-np.ones(v), np.ones(v)],
                       (np.r_[idx, idx], np.r_[np.tile(np.arange(m), n), m + idx])),
                      shape=(v, m + v)).tocsr()
    eq = coo_matrix((np.ones(v + m),
                    (np.r_[np.repeat(np.arange(n), m), np.full(m, n)],
                     np.r_[m + idx, np.arange(m)])), shape=(n + 1, m + v)).tocsr()
    c = np.r_[np.zeros(m), d.ravel().astype(float)]
    rhs = np.r_[np.ones(n), k]
    return c, link, eq, rhs

def dual_certificate(d, alpha, k, denominator=1000000):
    """Exact feasible dual of an equivalent relaxation, independent of solver success.

    For any alpha: beta_ji=max(alpha_j-d_ji,0), lambda=max_i sum_j beta_ji.
    Then sum alpha-k*lambda <= any feasible integer k-median cost. All operations
    after rounding alpha use integers. Costs in this pilot are small enough for int64.
    """
    q = denominator
    a = np.rint(np.asarray(alpha) * q).astype(np.int64)
    if int(np.max(np.abs(a), initial=0)) * len(a) >= 2**62:
        raise OverflowError("certificate too large for int64")
    lam = int(np.maximum(a[:, None] - d * q, 0).sum(axis=0).max())
    numerator = int(a.sum()) - k * lam
    return dict(alpha_numerators=a.tolist(), denominator=q, lambda_numerator=lam,
                lower_bound_numerator=numerator, lower_bound=numerator / q,
                integer_lower_bound=-(-numerator // q))

def verify_certificate(d, cert, k):
    # Python integers, not the vectorized certificate-generating implementation.
    a, q, lam = cert["alpha_numerators"], cert["denominator"], cert["lambda_numerator"]
    assert q > 0 and len(a) == d.shape[0]
    required = max(sum(max(int(a[j]) - int(d[j, i]) * q, 0) for j in range(len(d)))
                   for i in range(d.shape[1]))
    assert lam >= required
    num = sum(a) - k * lam
    assert num == cert["lower_bound_numerator"]
    assert cert["integer_lower_bound"] == -(-num // q)
    return cert["integer_lower_bound"]

def solve_lp(d, k, seconds=30):
    started = perf_counter()
    c, link, eq, rhs = model(d, k)
    prepared = perf_counter()
    # CPU affinity and OMP/BLAS limits are set by the harness.
    res = linprog(c, A_ub=link, b_ub=np.zeros(link.shape[0]), A_eq=eq, b_eq=rhs,
                  bounds=(0, 1), method="highs", options={"time_limit": seconds})
    solved = perf_counter()
    if not res.success:
        raise RuntimeError(f"LP status={res.status}: {res.message}")
    m = d.shape[1]
    y = res.x[:m]
    cert = dual_certificate(d, res.eqlin.marginals[:-1], k)
    verify_certificate(d, cert, k)
    certified = perf_counter()
    return y, dict(lp_status=int(res.status), lp_message=res.message, lp_value=float(res.fun),
                   fractional_facilities=int(np.sum((y > 1e-7) & (y < 1 - 1e-7))),
                   max_equality_residual=float(np.max(np.abs(eq @ res.x - rhs))),
                   max_link_violation=float(max(0, np.max(link @ res.x))),
                   certificate=cert, stages={"model": prepared-started, "lp": solved-prepared,
                                             "certificate": certified-solved})

def solve_milp(d, k, seconds=30):
    c, link, eq, rhs = model(d, k)
    a = vstack((eq, link), format="csc")
    constraints = LinearConstraint(a, np.r_[rhs, np.full(link.shape[0], -np.inf)],
                                   np.r_[rhs, np.zeros(link.shape[0])])
    m = d.shape[1]
    res = milp(c, integrality=np.r_[np.ones(m), np.zeros(len(c)-m)], bounds=Bounds(0, 1),
               constraints=constraints, options={"time_limit": seconds, "mip_rel_gap": 0.0})
    meds = None if res.x is None else np.flatnonzero(res.x[:m] > .5).tolist()
    return meds, dict(status=int(res.status), message=res.message,
                     objective=None if res.fun is None else float(res.fun),
                     dual_bound=None if res.mip_dual_bound is None else float(res.mip_dual_bound),
                     mip_gap=None if res.mip_gap is None else float(res.mip_gap),
                     nodes=None if res.mip_node_count is None else int(res.mip_node_count))

def quantize_openings(y, k, q):
    y = np.clip(np.asarray(y, dtype=float), 0, 1)
    if abs(float(y.sum()) - k) > 1e-5:
        raise ValueError("LP opening budget residual exceeds tolerance")
    raw = y * q
    counts = np.floor(raw).astype(np.int64)
    missing = k * q - int(counts.sum())
    if missing < 0 or missing > len(y):
        raise ValueError("invalid quantization residual")
    priority = np.argsort(-(raw-counts), kind="stable")
    counts[priority[:missing]] += 1
    assert int(counts.sum()) == k*q and np.all((0 <= counts) & (counts <= q))
    return counts

def pair_branches(counts, q):
    """Two endpoints and exact probability for the unweighted lemma's update."""
    frac = [i for i, v in enumerate(counts) if 0 < v < q]
    if len(frac) < 2:
        return None
    i, j = frac[:2]
    plus = min(q-counts[i], counts[j])
    minus = min(counts[i], q-counts[j])
    a, b = list(counts), list(counts)
    a[i] += plus; a[j] -= plus
    b[i] -= minus; b[j] += minus
    return a, b, int(minus), int(plus+minus)

def dependent_round(counts, q, rng):
    counts = list(map(int, counts))
    if sum(counts) % q:
        raise ValueError("integral total mass required")
    while True:
        branch = pair_branches(counts, q)
        if branch is None:
            break
        a, b, numerator, denominator = branch
        counts = a if int(rng.integers(denominator)) < numerator else b
    assert all(v in (0, q) for v in counts)
    return [i for i, v in enumerate(counts) if v == q]

def exact_rounding_distribution(counts, q):
    states = {tuple(counts): Fraction(1)}
    done = {}
    while states:
        next_states = {}
        for state, weight in states.items():
            br = pair_branches(state, q)
            if br is None:
                done[state] = done.get(state, 0) + weight
            else:
                a, b, num, den = br
                for child, p in ((a, Fraction(num, den)), (b, 1-Fraction(num, den))):
                    child = tuple(child)
                    next_states[child] = next_states.get(child, 0) + weight*p
        states = next_states
    return done

def lp_dr_swap(d, k, seed, cfg):
    y, info = solve_lp(d, k, cfg["solver_seconds"])
    start = perf_counter()
    counts = quantize_openings(y, k, cfg["rounding_denominator"])
    rng = np.random.default_rng(seed)
    q = cfg["rounding_denominator"]
    trials = 1 if np.all((counts == 0) | (counts == q)) else cfg["rounding_trials"]
    best_meds, best_cost, trial_costs = None, None, []
    for _ in range(trials):
        meds = dependent_round(counts, q, rng)
        value = cost(d, meds)
        trial_costs.append(value)
        if best_cost is None or value < best_cost:
            best_meds, best_cost = meds, value
    rounded = perf_counter()
    meds, trace, converged = local_search(d, best_meds, cfg["max_swaps"])
    refined = perf_counter()
    info["stages"].update(rounding=rounded-start, local_search=refined-rounded)
    info.update(trial_costs=trial_costs, rounding_trials_executed=trials,
                quantization_max_change=float(np.max(np.abs(counts/q-y))),
                local_trace=trace, local_optimum=converged)
    return meds, info
