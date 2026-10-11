"""Structure 9: fixed-margin conditional skill test (permutation of predicted labels keeps row and column totals)."""
import numpy as np


def fixed_margin_accuracy_test(pred, y, n_samples=2000, seed=20261010):
    rng = np.random.default_rng(seed)
    obs = float((pred == y).mean()) if len(y) else float("nan")
    ge = 0
    for _ in range(n_samples):
        if (rng.permutation(pred) == y).mean() >= obs:
            ge += 1
    return {"statistic": "accuracy", "observed": obs, "p_null": (1 + ge) / (1 + n_samples), "n": int(len(y)), "samples": n_samples,
            "use": "research-validity check only, not an entry signal"}
