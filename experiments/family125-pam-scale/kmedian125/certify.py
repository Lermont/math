"""Post-run exact bounded-opening certificates from saved dual client prices."""
from time import perf_counter

def strengthen_certificate(d, original, k):
    start = perf_counter()
    alpha = list(map(int, original["alpha_numerators"]))
    q = int(original["denominator"])
    charges = [sum(max(alpha[j]-int(d[j, i])*q, 0) for j in range(len(d)))
               for i in range(d.shape[1])]
    top = sorted(range(len(charges)), key=lambda i: (-charges[i], i))[:k]
    numerator = sum(alpha)-sum(charges[i] for i in top)
    return dict(kind="bounded_openings_dual", alpha_numerators=alpha, denominator=q,
                facility_charge_numerators=charges, top_k=top,
                lower_bound_numerator=numerator, integer_lower_bound=-(-numerator//q),
                original_integer_lower_bound=original["integer_lower_bound"],
                audit_seconds=perf_counter()-start)

def verify_strengthened(d, cert, k):
    q = cert["denominator"]
    alpha = cert["alpha_numerators"]
    assert q > 0 and 1 <= k <= d.shape[1] and len(alpha) == len(d)
    # Equivalent dual: lambda is the kth-largest facility charge, gamma_i=(b_i-lambda)+.
    # Python ints ensure the certificate is exact, despite its numerical LP origin.
    charges = []
    for column in d.T.tolist():
        value = 0
        for a, distance in zip(alpha, column):
            if a > distance*q:
                value += a-distance*q
        charges.append(value)
    assert charges == cert["facility_charge_numerators"]
    lam = sorted(charges, reverse=True)[k-1]
    lower_num = sum(alpha)-k*lam-sum(max(0, b-lam) for b in charges)
    assert lower_num == cert["lower_bound_numerator"]
    lower = -(-lower_num//q)
    assert lower == cert["integer_lower_bound"]
    assert lower >= cert["original_integer_lower_bound"]
    return lower
