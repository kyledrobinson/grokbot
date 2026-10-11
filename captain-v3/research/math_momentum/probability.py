"""Structure 3: calibrated UP/RANGE/DOWN probabilities, margin and disagreement.
Model: L2-ridge multinomial logistic regression (Newton), temperature-scaled walk-forward."""
import numpy as np

CLASSES = ["UP", "RANGE", "DOWN"]


def classify(r, band):
    y = np.full(len(r), -1)
    ok = np.isfinite(r)
    y[ok & (r > band)] = 0
    y[ok & (np.abs(r) <= band)] = 1
    y[ok & (r < -band)] = 2
    return y


def softmax(L):
    L = L - L.max(axis=1, keepdims=True); e = np.exp(L); return e / e.sum(axis=1, keepdims=True)


def fit_softmax_ridge(X, y, lam=1.0, iters=50, tol=1e-8):
    n, p = X.shape; K = 3
    W = np.zeros((p, K)); Y = np.eye(K)[y]
    for _ in range(iters):
        P = softmax(X @ W)
        G = X.T @ (P - Y) + lam * W                    # p x K
        H = np.zeros((p * K, p * K))
        for a in range(K):
            for b in range(K):
                w = P[:, a] * ((a == b) - P[:, b])
                H[a * p:(a + 1) * p, b * p:(b + 1) * p] = (X * w[:, None]).T @ X
        H += lam * np.eye(p * K)
        g = G.T.reshape(-1)                            # class-major
        step = np.linalg.solve(H, g).reshape(K, p).T
        W -= step
        if np.abs(step).max() < tol:
            break
    return W


def logits(X, W):
    return X @ W


def fit_temperature(L, y):
    if len(y) < 30:
        return 1.0
    best, bt = np.inf, 1.0
    for T in np.arange(0.3, 5.0001, 0.01):
        P = softmax(L / T); nll = -np.log(np.clip(P[np.arange(len(y)), y], 1e-12, 1)).mean()
        if nll < best:
            best, bt = nll, float(T)
    return bt


def freq_probs(y, alpha=1.0):
    c = np.bincount(y[y >= 0], minlength=3).astype(float) + alpha
    return c / c.sum()


def margin(P):
    s = np.sort(P, axis=1); return s[:, -1] - s[:, -2]


def disagreement(Ps):
    """Ps: list of (n x 3) prob arrays from sub-models -> mean over classes of across-model variance."""
    A = np.stack(Ps, axis=0)
    return A.var(axis=0).mean(axis=1)


def brier(P, y):
    Y = np.eye(3)[y]; return ((P - Y) ** 2).sum(axis=1)


def logloss(P, y):
    return -np.log(np.clip(P[np.arange(len(y)), y], 1e-12, 1))


def ece_top(P, y, bins=10):
    conf = P.max(axis=1); pred = P.argmax(axis=1); hit = (pred == y).astype(float)
    if len(y) == 0:
        return np.nan
    e = 0.0
    for b in range(bins):
        m = (conf >= b / bins) & (conf < (b + 1) / bins if b < bins - 1 else conf <= 1)
        if m.any():
            e += m.mean() * abs(hit[m].mean() - conf[m].mean())
    return float(e)


# ---- session-close horizon: conditional-frequency model on sign of trailing 4h return ----
def session_close_model(samples, alpha=1.0, window=365):
    """samples: time-ordered list of dicts {t_ms, bucket (+1/-1/0), y (class idx or -1 if unresolved)}.
    Returns walk-forward OOS probs (each from prior `window` resolved samples) and a function for the live bucket."""
    oos = []
    for i, s in enumerate(samples):
        prior = [q for q in samples[max(0, i - window):i] if q["y"] >= 0 and q["resolved_ms"] <= s["t_ms"]]
        if len(prior) < 60 or s["y"] < 0:
            continue
        same = np.array([q["y"] for q in prior if q["bucket"] == s["bucket"]] or [-1])
        allp = np.array([q["y"] for q in prior])
        oos.append({"t_ms": s["t_ms"], "y": s["y"], "p": freq_probs(same, alpha), "p_base": freq_probs(allp, alpha)})
    return oos
