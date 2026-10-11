"""Deterministic research analytics. Official = closed non-synthetic trades. Hypothetical = skipped-signal
outcomes (never mixed into official numbers). All outputs carry sample counts and reliability flags."""
import json, math, random
from .util import parse_ts, from_ms, iso, to_ms

CLASSES = ["UP", "DOWN", "RANGE"]


def _moments(x):
    n = len(x)
    if n == 0:
        return {"n": 0}
    m = sum(x) / n
    if n < 2:
        return {"n": n, "mean": m}
    sd = math.sqrt(sum((v - m) ** 2 for v in x) / (n - 1))
    out = {"n": n, "mean": m, "sd": sd}
    if sd > 0:
        out["sharpe_per_obs"] = m / sd
        out["skew"] = sum(((v - m) / sd) ** 3 for v in x) / n
        out["kurtosis"] = sum(((v - m) / sd) ** 4 for v in x) / n
    return out


def block_bootstrap(rows, cfg, key="net_r"):
    """rows: dicts with session_date and key. Resample whole session blocks with replacement."""
    b = cfg["measurement"]["bootstrap"]
    vals = [r[key] for r in rows if r.get(key) is not None]
    blocks = {}
    for r in rows:
        if r.get(key) is not None:
            blocks.setdefault(r["session_date"], []).append(r[key])
    out = dict(_moments(vals), n_blocks=len(blocks))
    reliable = len(vals) >= b["min_trades"] and len(blocks) >= b["min_blocks"]
    out["reliable"] = reliable
    if not reliable:
        out["ci"] = None
        out["reliability_note"] = f"UNRELIABLE: n={len(vals)} (<{b['min_trades']}) or blocks={len(blocks)} (<{b['min_blocks']})"
        return out
    rng = random.Random(b["seed"])
    keys = sorted(blocks)
    means = []
    for _ in range(b["resamples"]):
        s = []
        for _ in keys:
            s += blocks[keys[rng.randrange(len(keys))]]
        means.append(sum(s) / len(s))
    means.sort()
    a = (1 - b["ci"]) / 2
    out["ci"] = [means[int(a * len(means))], means[int((1 - a) * len(means)) - 1]]
    out["ci_level"] = b["ci"]
    return out


def official_trades(con):
    return [dict(r) for r in con.execute("SELECT * FROM trades WHERE status='CLOSED' AND synthetic=0").fetchall()]


def hypothetical_rows(con):
    return [dict(r) for r in con.execute("SELECT * FROM hypothetical_outcomes WHERE status='CLOSED' AND kind='SKIPPED_PROSPECTIVE' AND synthetic=0").fetchall()]


def expectancy(rows, cfg, group_fn):
    groups = {}
    for r in rows:
        groups.setdefault(group_fn(r), []).append(r)
    return {str(k): block_bootstrap(v, cfg) for k, v in sorted(groups.items(), key=lambda kv: str(kv[0]))}


def _labels(r):
    try:
        l = json.loads(r.get("condition_labels") or "null") or {}
    except Exception:
        l = {}
    return (l.get("trend", "UNAVAILABLE"), l.get("volatility", "UNAVAILABLE"))


def cost_sensitivity_summary(rows):
    out = {}
    for r in rows:
        for k, v in json.loads(r.get("cost_sensitivity") or "{}").items():
            out.setdefault(k, []).append(v / r["initial_risk_usd"] if r.get("initial_risk_usd") else None)
    return {k: {"n": len([x for x in v if x is not None]), "mean_net_r": (sum(x for x in v if x is not None) / len([x for x in v if x is not None])) if any(x is not None for x in v) else None} for k, v in out.items()}


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [c - h, c + h]


def calibration(con, cfg, model_id=None):
    edges = cfg["measurement"]["calibration"]["bins"]
    q = "SELECT f.model_id, f.market, f.p_up, f.p_down, f.p_range, s.outcome, s.brier FROM forecasts f JOIN scores s ON s.forecast_id=f.forecast_id WHERE s.status='SCORED' AND f.synthetic=0"
    rows = con.execute(q).fetchall()
    out = {}
    for mid in sorted({r[0] for r in rows}):
        if model_id and mid != model_id:
            continue
        rs = [r for r in rows if r[0] == mid]
        bins = [{"lo": edges[i], "hi": min(edges[i + 1], 1.0), "n": 0, "sum_p": 0.0, "hits": 0} for i in range(len(edges) - 1)]
        for r in rs:
            for cls, p in zip(CLASSES, r[2:5]):
                for b in bins:
                    if b["lo"] <= p < (edges[bins.index(b) + 1]):
                        b["n"] += 1; b["sum_p"] += p; b["hits"] += 1 if r[5] == cls else 0
                        break
        for b in bins:
            b["mean_p"] = b["sum_p"] / b["n"] if b["n"] else None
            b["observed"] = b["hits"] / b["n"] if b["n"] else None
            b["wilson95"] = wilson(b["hits"], b["n"])
            del b["sum_p"]
        acc = sum(1 for r in rs if max(zip(r[2:5], CLASSES))[1] == r[5])
        out[mid] = {"forecasts_scored": len(rs), "mean_brier": sum(r[6] for r in rs) / len(rs), "accuracy": acc / len(rs), "bins": bins,
                    "note": "one-vs-rest pooled over the 3 classes; each forecast contributes 3 (p, outcome) points"}
    return out


def equity_curve(con, cfg):
    init = cfg["risk"]["initial_paper_capital_usd"]
    ev = con.execute("SELECT event_id, event_ts, event_type, trading_cash_delta, reserve_delta FROM trade_events WHERE synthetic=0 ORDER BY event_ts, recorded_ts, event_id").fetchall()
    tc, rs = init, 0.0
    peak, peak_ts = init, None
    pts = []
    max_dd, max_dd_pct, under_since, longest = 0.0, 0.0, None, 0.0
    for e in ev:
        tc += e[3]; rs += e[4]
        tot = tc + rs
        t = parse_ts(e[1])
        if tot >= peak - 1e-12:
            if under_since is not None:
                longest = max(longest, (t - under_since).total_seconds())
            peak, peak_ts, under_since = tot, e[1], None
        elif under_since is None:
            under_since = t
        dd = peak - tot
        max_dd = max(max_dd, dd)
        max_dd_pct = max(max_dd_pct, dd / peak if peak else 0)
        pts.append({"event_id": e[0], "event_ts": e[1], "event_type": e[2], "trading": tc, "reserve": rs, "total": tot, "peak": peak, "drawdown_usd": dd, "drawdown_pct": dd / peak if peak else 0})
    stats = {"events": len(ev), "peak_total": peak, "peak_ts": peak_ts, "current_total": tc + rs, "current_drawdown_usd": peak - (tc + rs),
             "max_drawdown_usd": max_dd, "max_drawdown_pct": max_dd_pct, "underwater_since": iso(under_since) if under_since else None,
             "longest_underwater_closed_s": longest, "note": "derived from trade_events (total = trading + reserve; internal transfers cancel); mark-to-market between events not included"}
    return pts, stats


def feature_comparison(con, cfg):
    """With-vs-without on the same signals: baseline = all signals with outcomes (official or hypothetical);
    variant = only signals whose alt-minus-BTC 1h return agrees with the side (BTC signals: n/a). Descriptive only."""
    rows = []
    for r in con.execute("SELECT s.signal_id, s.market, s.side, s.descriptive_features, COALESCE(t.net_r, h.net_r) AS net_r, COALESCE(t.session_date, h.session_date) AS session_date, CASE WHEN t.trade_id IS NOT NULL THEN 'official' ELSE 'hypothetical' END AS src FROM signals s LEFT JOIN decisions d ON d.signal_id=s.signal_id LEFT JOIN trades t ON t.decision_id=d.decision_id AND t.status='CLOSED' LEFT JOIN hypothetical_outcomes h ON h.signal_id=s.signal_id AND h.status='CLOSED' WHERE s.synthetic=0").fetchall():
        if r[4] is None:
            continue
        rows.append(dict(r))
    def agrees(r):
        f = json.loads(r["descriptive_features"] or "{}")
        k = f"{r['market']}-BTC_1h"
        if k not in f:
            return None
        return (f[k] > 0) == (r["side"] == "long")
    base = block_bootstrap(rows, cfg)
    var = block_bootstrap([r for r in rows if agrees(r)], cfg)
    return {"period": "all stored signals with resolved outcomes", "baseline_all": base, "variant_rs1h_agrees": var,
            "whale_lean": "not evaluated: feed absent (null on every signal)", "gating": "none (descriptive comparison only)"}


def refresh_trials(con, cfg):
    """Update experiment_trials stats (inputs for Deflated Sharpe later: n, mean, sd, skew, kurtosis, trial count)."""
    off, hyp = official_trades(con), hypothetical_rows(con)
    series = {"EXP-A1": [r["net_r"] for r in off if r["setup"] == "A" and r["net_r"] is not None],
              "EXP-B1": [r["net_r"] for r in off if r["setup"] == "B" and r["net_r"] is not None]}
    hser = {"EXP-A1": [r["net_r"] for r in hyp if r["setup"] == "A" and r["net_r"] is not None],
            "EXP-B1": [r["net_r"] for r in hyp if r["setup"] == "B" and r["net_r"] is not None]}
    out = {}
    for tr in con.execute("SELECT trial_id, experiment_id, variant FROM experiment_trials").fetchall():
        x = series.get(tr[1], []) if tr[2].endswith("official") else hser.get(tr[1], []) if tr[2].endswith("hypothetical") else []
        m = _moments(x)
        con.execute("UPDATE experiment_trials SET n_obs=?, mean_r=?, sd_r=?, sharpe_per_obs=?, skew=?, kurtosis=?, updated_ts=? WHERE trial_id=?",
                    (m.get("n"), m.get("mean"), m.get("sd"), m.get("sharpe_per_obs"), m.get("skew"), m.get("kurtosis"), iso(__import__("captain.util", fromlist=["now_utc"]).now_utc()), tr[0]))
        out[tr[0]] = m
    return out


def full(con, cfg):
    off, hyp = official_trades(con), hypothetical_rows(con)
    pts, dd = equity_curve(con, cfg)
    return {
        "official": {"n_closed": len(off), "expectancy_r_by_setup": expectancy(off, cfg, lambda r: r["setup"]),
                     "expectancy_r_by_condition": expectancy(off, cfg, _labels), "cost_sensitivity": cost_sensitivity_summary(off),
                     "mae_mfe_r": [{"trade_id": r["trade_id"], "mae_r": r["mae_r"], "mae_ts": r["mae_ts"], "mfe_r": r["mfe_r"], "mfe_ts": r["mfe_ts"], "net_r": r["net_r"]} for r in off]},
        "hypothetical_EXCLUDED_FROM_OFFICIAL": {"n_closed": len(hyp), "expectancy_r_by_setup": expectancy(hyp, cfg, lambda r: r["setup"]),
                                               "expectancy_r_by_skip_reason": expectancy(hyp, cfg, lambda r: r["skip_reason"]),
                                               "expectancy_r_by_condition": expectancy(hyp, cfg, _labels), "cost_sensitivity": cost_sensitivity_summary(hyp)},
        "calibration": calibration(con, cfg),
        "drawdown": dd,
        "feature_comparison": feature_comparison(con, cfg),
    }
