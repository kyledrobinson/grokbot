"""Pure tag computations (no I/O). Bars are dicts/tuples with o,h,l,c. Context labels only."""
import statistics


def direction(o, c):
    return "up" if c > o else "down" if c < o else "flat"


def candle_shape(o, h, l, c, max_opp_wick=0.25, min_body=0.5):
    """Body / wick fractions of range, close location, clean flag."""
    rng = h - l
    d = direction(o, c)
    out = {"dir": d, "range": rng, "body_frac": None, "upper_wick_frac": None, "lower_wick_frac": None,
           "opposing_wick_frac": None, "close_loc": None, "clean": False}
    if rng <= 0:
        return out
    out["body_frac"] = abs(c - o) / rng
    out["upper_wick_frac"] = (h - max(o, c)) / rng
    out["lower_wick_frac"] = (min(o, c) - l) / rng
    out["close_loc"] = (c - l) / rng
    if d == "up":
        out["opposing_wick_frac"] = out["upper_wick_frac"]
    elif d == "down":
        out["opposing_wick_frac"] = out["lower_wick_frac"]
    out["clean"] = bool(d != "flat" and out["body_frac"] > min_body and out["opposing_wick_frac"] < max_opp_wick)
    return out


def range_vs_median(today_range, past_ranges, min_days):
    vals = [r for r in past_ranges if r is not None and r > 0]
    if len(vals) < min_days or not today_range:
        return None, len(vals), None
    med = statistics.median(vals)
    return today_range / med, len(vals), med


def session_profile(asia_dir, london_dir):
    """london_reversed_asia + day_type using the source post's mapping."""
    if asia_dir in (None, "flat") or london_dir in (None, "flat"):
        return None, None
    rev = asia_dir != london_dir
    return rev, ("continuation_day" if rev else "reversal_day")


def atr_wilder(bars, period=14):
    """bars: list of (o,h,l,c). Wilder ATR with SMA seed; returns last value or None."""
    if len(bars) < period + 1:
        return None
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i][1], bars[i][2], bars[i - 1][3]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


def find_fvgs(bars, form_lo_ms, form_hi_ms, min_gap_pct=0.0):
    """bars: list of dict(start,o,h,l,c) contiguous hourly, ascending, all ending <= moment.
    A gap is formed by candles (i-1, i, i+1); third candle start in [form_lo_ms, form_hi_ms).
    Bullish: low[i+1] > high[i-1]; zone [high[i-1], low[i+1]]. Bearish: high[i+1] < low[i-1]; zone [high[i+1], low[i-1]].
    Filled (full) by any LATER bar (after i+1): bullish if low <= zone bottom, bearish if high >= zone top.
    Returns list of gaps (oldest first) with 'filled' flag."""
    out = []
    for i in range(1, len(bars) - 1):
        a, b, z = bars[i - 1], bars[i], bars[i + 1]
        if not (form_lo_ms <= z["start"] < form_hi_ms):
            continue
        if z["start"] - a["start"] != 2 * (b["start"] - a["start"]):
            continue  # not contiguous
        g = None
        if z["l"] > a["h"]:
            g = {"type": "bullish", "low": a["h"], "high": z["l"]}
        elif z["h"] < a["l"]:
            g = {"type": "bearish", "low": z["h"], "high": a["l"]}
        if not g:
            continue
        g["gap_pct"] = (g["high"] - g["low"]) / g["low"] * 100
        if g["gap_pct"] < min_gap_pct:
            continue
        g["formed_bar_start"] = z["start"]
        later = bars[i + 2:]
        if g["type"] == "bullish":
            g["filled"] = any(x["l"] <= g["low"] for x in later)
        else:
            g["filled"] = any(x["h"] >= g["high"] for x in later)
        out.append(g)
    return out


def fvg_distance(g, price, atr):
    """Signed distance from price to the nearest zone edge (negative = zone below price)."""
    if price is None or g is None:
        return None
    if g["low"] <= price <= g["high"]:
        pos, edge = "price_inside", price
    elif g["high"] < price:
        pos, edge = "below_price", g["high"]
    else:
        pos, edge = "above_price", g["low"]
    d = edge - price
    return {"position": pos, "nearest_edge": edge, "dist_pct": d / price * 100, "dist_atr": (d / atr) if atr else None}


def excursion(bars, level, d, tol=1e-9):
    """% beyond level in direction d over bars (max). Positive => beyond."""
    if not bars or level is None:
        return None
    if d == "up":
        x = max(b["h"] for b in bars)
        return (x - level * (1 + tol)) / level * 100 if x > level * (1 + tol) else min(0.0, (x - level) / level * 100)
    x = min(b["l"] for b in bars)
    return (level * (1 - tol) - x) / level * 100 if x < level * (1 - tol) else min(0.0, (level - x) / level * 100)


def confirm_label(n_others_beyond, n_others=2):
    if n_others_beyond is None:
        return None
    return "all_confirm" if n_others_beyond == n_others else "diverge" if n_others_beyond == 0 else "partial"


def cross_asset(signal_mkt, d, per_asset):
    """per_asset[m] = {'level': float, 'pre': [bars ending <= t0], 'next': bar ending t0+15 or None}.
    Returns the event label set. 'pre' = previous + trigger bar; full window = pre + next."""
    ex_pre, ex_full, beyond_pre, beyond_full = {}, {}, {}, {}
    for m, a in per_asset.items():
        ex_pre[m] = excursion(a["pre"], a["level"], d)
        full = a["pre"] + ([a["next"]] if a.get("next") else [])
        ex_full[m] = excursion(full, a["level"], d)
        beyond_pre[m] = bool(ex_pre[m] is not None and ex_pre[m] > 0)
        beyond_full[m] = bool(ex_full[m] is not None and ex_full[m] > 0)
    others = [m for m in per_asset if m != signal_mkt]
    have_next = all(per_asset[m].get("next") for m in per_asset)
    n_pre = sum(beyond_pre[m] for m in others)
    n_full = sum(beyond_full[m] for m in others) if have_next else None
    cands = {m: v for m, v in ex_pre.items() if v is not None and v > 0}
    strongest = max(cands, key=cands.get) if cands else None
    switch = None
    if strongest and per_asset[strongest].get("next"):
        nb, lvl = per_asset[strongest]["next"], per_asset[strongest]["level"]
        switch = bool(nb["c"] <= lvl) if d == "up" else bool(nb["c"] >= lvl)
    return {"break_dir": d, "self_beyond_at_signal": beyond_pre.get(signal_mkt), "excursion_pct_at_signal": ex_pre,
            "excursion_pct_window": ex_full if have_next else None,
            "confirm_at_signal": confirm_label(n_pre), "n_confirm_at_signal": n_pre,
            "confirm_label": confirm_label(n_full), "n_confirm": n_full,
            "strongest": strongest, "strongest_excursion_pct": cands.get(strongest) if strongest else None,
            "strength_switch": switch, "complete": have_next}
