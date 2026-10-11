"""Structure 12: rolling split-conformal class sets + Wilson bounds."""
import math
import numpy as np

CLASSES = ["UP", "RANGE", "DOWN"]


def conformal_quantile(scores, alpha):
    s = np.sort(np.asarray(scores)); n = len(s)
    if n == 0:
        return np.inf
    k = math.ceil((n + 1) * (1 - alpha))
    return float(s[min(k, n) - 1]) if k <= n else np.inf


def conformal_set(p, q):
    return [CLASSES[k] for k in range(3) if 1.0 - p[k] <= q]


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 1.0
    ph = k / n; d = 1 + z * z / n; c = ph + z * z / (2 * n); r = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))
    return (c - r) / d, (c + r) / d


def rolling_coverage(fold_ids, scores_by_fold, P_by_fold, y_by_fold, alpha, max_prior=7, min_prior=2):
    """Fold j uses the quantile from up to `max_prior` earlier folds. Returns (covered, n, per-fold detail)."""
    cov, n, detail = 0, 0, []
    for j, fid in enumerate(fold_ids):
        if j < min_prior:
            continue
        prior = np.concatenate([scores_by_fold[f] for f in fold_ids[max(0, j - max_prior):j]])
        q = conformal_quantile(prior, alpha)
        P, y = P_by_fold[fid], y_by_fold[fid]
        c = int(((1.0 - P[np.arange(len(y)), y]) <= q).sum())
        sizes = [len(conformal_set(p, q)) for p in P]
        cov += c; n += len(y)
        detail.append({"fold": fid, "q": q, "coverage": c / max(len(y), 1), "n": len(y), "mean_set_size": float(np.mean(sizes)) if sizes else None,
                       "singleton_rate": float(np.mean([s == 1 for s in sizes])) if sizes else None})
    return cov, n, detail
