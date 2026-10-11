"""Structure 5: exact enumeration of the 27 BTC/ETH/SOL states with shrinkage covariance and correlation stress."""
import itertools
import numpy as np

ES95_NORMAL = 2.0627


def shrink_cov(R, delta):
    """Constant-correlation shrinkage of the sample covariance (R: n x 3, rows strictly before the cutoff)."""
    S = np.cov(R, rowvar=False); sd = np.sqrt(np.diag(S)); C = S / np.outer(sd, sd)
    rbar = (C.sum() - 3) / 6.0
    F = rbar * np.outer(sd, sd); np.fill_diagonal(F, sd ** 2)
    return (1 - delta) * S + delta * F, C, rbar


def stress_corr(S, toward):
    sd = np.sqrt(np.diag(S)); C = S / np.outer(sd, sd)
    C2 = C + toward * (1 - C); np.fill_diagonal(C2, 1.0)
    return C2 * np.outer(sd, sd)


def enumerate_states(mu_long, mu_short, Sigma, lam, gamma, rho, current=(0, 0, 0), max_positions=1):
    """mu_*: per-asset conservative net expected return (fraction of notional) for +1 / -1."""
    out = []
    for s in itertools.product((-1, 0, 1), repeat=3):
        s = np.array(s)
        mu = sum(mu_long[i] if s[i] == 1 else mu_short[i] if s[i] == -1 else 0.0 for i in range(3))
        var = float(s @ Sigma @ s); tail = ES95_NORMAL * np.sqrt(var)
        turn = int(np.abs(s - np.array(current)).sum())
        J = mu - lam * var - gamma * turn - rho * tail
        out.append({"state": s.tolist(), "J": float(J), "mu": float(mu), "var": var, "tail_es95": float(tail), "turnover": turn,
                    "feasible": int(np.abs(s).sum()) <= max_positions})
    out.sort(key=lambda d: -d["J"])
    return out
