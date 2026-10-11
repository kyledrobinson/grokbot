"""Structure 2: Ballistic Persistence Score BP = B * sqrt(E). Context only."""
import numpy as np


def ballistic(f, horizons, H):
    c = f["close"]; d = np.sign(f["dEMA50_1h"]); v = np.sign(f["dVWAP"]); sig = f["sigma15"]
    num = np.zeros(len(c)); den = 0.0
    for name, h in horizons.items():
        rh = {1: f["r15m"], 2: f["r30m"], 4: f["r1h"], 8: f["r2h"], 16: f["r4h"]}[h]
        q = np.tanh(rh / (sig * np.sqrt(h)))
        a = ((np.sign(rh) == d) & (d == v) & (d != 0)).astype(float)
        num = num + q * a; den += 1.0
    B = num / den
    E = np.full(len(c), np.nan)
    for t in range(H, len(c)):
        w = c[t - H:t + 1]
        if np.all(np.isfinite(w)):
            path = np.abs(np.diff(w)).sum()
            E[t] = abs(w[-1] - w[0]) / path if path > 0 else 0.0
    BP = B * np.sqrt(E)
    return B, E, BP
