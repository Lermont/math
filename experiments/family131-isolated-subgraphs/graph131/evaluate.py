from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


def top_k(y, scores, k=100):
    """Expected true positives under uniform random tie-breaking at the boundary."""
    k = min(k, len(y))
    boundary = np.sort(scores)[-k]
    above, tied = scores > boundary, scores == boundary
    hits = float(y[above].sum() + (k - above.sum()) * y[tied].mean())
    return {"precision_at_100": hits / k, "recall_at_100": hits / max(1, y.sum()), "expected_true_at_100": hits, "boundary_tie_size": int(tied.sum())}


def threshold_at_fpr(y, scores, limit=0.01):
    negatives = np.sort(scores[y == 0])[::-1]
    budget = int(np.floor(limit * len(negatives)))
    # Strictly exceed the (budget+1)-th negative, including all ties safely.
    return float(np.nextafter(negatives[budget], np.inf))


def metrics(y, scores, threshold):
    predicted = scores >= threshold
    positive = y == 1
    result = {"ap": float(average_precision_score(y, scores)), "roc_auc": float(roc_auc_score(y, scores)), "prevalence": float(y.mean()), "count": len(y), "positives": int(y.sum()), "threshold": float(threshold), "recall_at_val_1pct_fpr": float(predicted[positive].mean()), "test_fpr": float(predicted[~positive].mean()), "alerts": int(predicted.sum()), "true_alerts": int((predicted & positive).sum())}
    result.update(top_k(y, scores))
    return result
