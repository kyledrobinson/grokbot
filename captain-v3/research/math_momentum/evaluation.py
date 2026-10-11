"""Structures 10-11 + promotion gates: effective sample size, feature budget, gate status."""
import numpy as np


def acf(x, k):
    x = np.asarray(x, float) - np.mean(x); d = (x * x).sum()
    return float((x[:-k] * x[k:]).sum() / d) if d > 0 and k < len(x) else 0.0


def n_eff(x, kmax=96, fixed_k=None):
    n = len(x)
    if n < 10:
        return float(n), 0
    s, used = 0.0, 0
    for k in range(1, (fixed_k or kmax) + 1):
        r = acf(x, k)
        if fixed_k is None and r <= 0:
            break
        s += r; used = k
    return float(n / max(1.0 + 2.0 * s, 1e-9)), used


def n_eff_stability(x, ks=(16, 48, 96)):
    vals = [n_eff(x, fixed_k=k)[0] for k in ks]
    lo, hi = min(vals), max(vals)
    return {"by_K": dict(zip(map(str, ks), vals)), "ratio": hi / lo if lo > 0 else float("inf"),
            "status": "INCONCLUSIVE" if lo <= 0 or hi / lo > 1.5 else "STABLE"}


def feature_budget(Z, names, thr=0.9):
    ok = np.all(np.isfinite(Z), axis=1); Zt = Z[ok]
    kept = []
    for j in range(Zt.shape[1]):
        if Zt[:, j].std() == 0:
            continue
        if all(abs(np.corrcoef(Zt[:, j], Zt[:, i])[0, 1]) <= thr for i in kept):
            kept.append(j)
    return {"raw_feature_count": len(names), "effective_feature_count": len(kept), "kept": [names[i] for i in kept],
            "collinearity_rule": f"drop a feature with |corr| > {thr} vs an earlier kept one, or zero variance"}


def promotion_gates(resolved_by_asset, sessions_by_asset, cfg):
    pg = cfg["promotion_gates"]; out = {}
    for m, n in resolved_by_asset.items():
        out[f"{m}_resolved_shadow_forecasts>={pg['min_resolved_shadow_forecasts_per_asset']}"] = "FAIL" if n < pg["min_resolved_shadow_forecasts_per_asset"] else "PASS"
        out[f"{m}_independent_session_dates>={pg['min_session_dates_per_asset']}"] = "FAIL" if sessions_by_asset[m] < pg["min_session_dates_per_asset"] else "PASS"
    out.update({
        "positive_net_EV_LCB_overall_no_catastrophic_cell": "INCONCLUSIVE",
        "beats_baselines_brier_logloss_and_net_expectancy": "INCONCLUSIVE",
        "stable_under_1.5x_and_2x_cost_stress": "INCONCLUSIVE",
        "no_month_or_asset_over_half_of_profit": "INCONCLUSIVE",
        "thresholds_and_version_frozen_before_holdout": "PASS (math-momentum-v1.0.0 frozen at first shadow run)",
        "sizing_gates_100_closed_paper_trades_etc": "FAIL",
    })
    out["overall"] = "NOT PROMOTABLE - shadow only; must not affect official Captain v3.1.1 entries or sizing"
    return out
