"""Deterministic setup evaluation (spec section 6). Uses only completed bars received at/before cutoff.

Float tolerance: eps = tol_rel * max(|a|,|b|). gt(a,b): a > b + eps. le(a,b): a <= b + eps.
Evaluation happens only on the 15m bar that ends exactly at the decision time floored to 15 minutes;
a missed decision cycle is never evaluated retroactively."""
import datetime as dt
from .collector import bars as get_bars
from .indicators import atr_wilder, ema, contiguous
from .util import iso, from_ms, to_ms, toronto_dt, toronto_date, sha256_text, canon

MIN = 60_000
CALC_VERSIONS = {"atr": "wilder14-sma-seed-v1", "ema": "ema50-sma-seed-v1", "overnight": "15m-agg-00:00-06:00-toronto-v1", "signals": "setups-A1-B1-v1"}


def floor15(d):
    ms = to_ms(d)
    return ms - ms % (15 * MIN)


def _tol(cfg):
    t = cfg["float_tolerance_rel"]
    gt = lambda a, b: a > b + t * max(abs(a), abs(b))
    lt = lambda a, b: a < b - t * max(abs(a), abs(b))
    le = lambda a, b: a <= b + t * max(abs(a), abs(b))
    ge = lambda a, b: a >= b - t * max(abs(a), abs(b))
    return gt, lt, le, ge


def overnight_levels(con, cfg, market, session_date, cutoff_dt, through_dt=None):
    """Overnight 00:00-06:00 Toronto high/low from primary 15m bars (DST-aware length).
    through_dt < 06:00 gives a partial range labelled 'through forecast cutoff'."""
    p = cfg["markets"][market]["primary"]
    s = toronto_dt(session_date, cfg["session"]["overnight_start"])
    e = toronto_dt(session_date, cfg["session"]["session_start"])
    end = min(e, through_dt) if through_dt else e
    if through_dt and through_dt < e:
        rows = get_bars(con, p["provider"], p["symbol"], "1m", to_ms(end), cutoff_dt, start_ms=to_ms(s))
        expected = int((end - s).total_seconds() // 60)
        label = "partial: through forecast cutoff (not a completed overnight range)"
    else:
        rows = get_bars(con, p["provider"], p["symbol"], "15m", to_ms(e), cutoff_dt, start_ms=to_ms(s))
        expected = int((e - s).total_seconds() // 900)
        label = "final: locked at 06:00"
    if not rows:
        return {"complete": False, "bars": 0, "expected": expected, "label": label}
    return {"high": max(r["high"] for r in rows), "low": min(r["low"] for r in rows), "bars": len(rows), "expected": expected,
            "complete": len(rows) == expected, "start": iso(s), "end": iso(end), "label": label}


def evaluate_market(con, cfg, market, decision_dt, cutoff_dt=None):
    """Return snapshot features and candidate list for one market at one decision time."""
    cutoff_dt = cutoff_dt or decision_dt
    gt, lt, le, ge = _tol(cfg)
    p = cfg["markets"][market]["primary"]
    ind = cfg["indicators"]
    session_date = toronto_date(decision_dt)
    t_end = floor15(decision_dt)
    sess_start = toronto_dt(session_date, cfg["session"]["session_start"])
    feats = {"market": market, "session_date": str(session_date), "decision_ts": iso(decision_dt), "cutoff_ts": iso(cutoff_dt),
             "signal_bar_end": iso(from_ms(t_end))}
    gates = {}
    b15 = get_bars(con, p["provider"], p["symbol"], "15m", t_end, cutoff_dt, limit=ind["atr"]["warmup_bars_required"])
    b1h_end = t_end - t_end % (60 * MIN)
    b1h = get_bars(con, p["provider"], p["symbol"], "1h", b1h_end, cutoff_dt, limit=ind["ema"]["warmup_bars_required"])
    on = overnight_levels(con, cfg, market, session_date, cutoff_dt)
    feats["overnight"] = on
    gates["overnight_complete"] = bool(on.get("complete"))
    atr_ok = len(b15) == ind["atr"]["warmup_bars_required"] and contiguous(b15, 15 * MIN) and b15 and b15[-1]["candle_end_ms"] == t_end
    gates["atr_warmup"] = bool(atr_ok)
    ema_ok = len(b1h) == ind["ema"]["warmup_bars_required"] and contiguous(b1h, 60 * MIN) and b1h and b1h[-1]["candle_end_ms"] == b1h_end
    gates["ema_warmup"] = bool(ema_ok)
    in_session = t_end > to_ms(sess_start)
    gates["post_0600_bar"] = in_session
    feats["bars_15m"] = len(b15)
    feats["bars_1h"] = len(b1h)
    cands = []
    if atr_ok:
        atrs = atr_wilder(b15, ind["atr"]["period"])
        atr = atrs[-1]
        sig, prev = b15[-1], b15[-2]
        feats.update({"atr14": atr, "signal_bar": {k: sig[k] for k in ("candle_start_ms", "open", "high", "low", "close")}, "prev_close": prev["close"]})
    if ema_ok:
        e = ema([b["close"] for b in b1h], ind["ema"]["period"])
        lb = ind["ema"]["slope_lookback_bars"]
        feats.update({"h1_close": b1h[-1]["close"], "ema50": e[-1], "ema50_3back": e[-1 - lb], "h1_bar_end": iso(from_ms(b1h[-1]["candle_end_ms"]))})
    checks = {}
    if atr_ok and ema_ok and on.get("complete") and in_session:
        A, B = cfg["setups"]["A"], cfg["setups"]["B"]
        onh, onl = on["high"], on["low"]
        hc, em, em3 = feats["h1_close"], feats["ema50"], feats["ema50_3back"]
        # Setup A
        a_long = gt(sig["close"], onh + A["breakout_atr_mult"] * atr) and le(prev["close"], onh)
        a_short = lt(sig["close"], onl - A["breakout_atr_mult"] * atr) and ge(prev["close"], onl)
        checks["A_long"] = {"trigger": a_long, "trend_ok": gt(hc, em)}
        checks["A_short"] = {"trigger": a_short, "trend_ok": lt(hc, em)}
        if a_long:
            cands.append({"setup": "A", "side": "long", "trend_gate": gt(hc, em), "stop": onh - A["stop_atr_mult"] * atr,
                          "target_r": A["target_r_mult"], "signal_price": sig["close"], "level": onh})
        if a_short:
            cands.append({"setup": "A", "side": "short", "trend_gate": lt(hc, em), "stop": onl + A["stop_atr_mult"] * atr,
                          "target_r": A["target_r_mult"], "signal_price": sig["close"], "level": onl})
        # Setup B
        b_short = ge(sig["high"], onh + B["probe_atr_mult"] * atr) and lt(sig["close"], onh)
        b_long = le(sig["low"], onl - B["probe_atr_mult"] * atr) and gt(sig["close"], onl)
        excl_short = gt(hc, em) and gt(em, em3)
        excl_long = lt(hc, em) and lt(em, em3)
        checks["B_short"] = {"trigger": b_short, "excluded": excl_short}
        checks["B_long"] = {"trigger": b_long, "excluded": excl_long}
        if b_short:
            cands.append({"setup": "B", "side": "short", "trend_gate": not excl_short, "stop": sig["high"] + B["stop_buffer_atr_mult"] * atr,
                          "target_r": B["target_r_mult"], "signal_price": sig["close"], "level": onh})
        if b_long:
            cands.append({"setup": "B", "side": "long", "trend_gate": not excl_long, "stop": sig["low"] - B["stop_buffer_atr_mult"] * atr,
                          "target_r": B["target_r_mult"], "signal_price": sig["close"], "level": onl})
    feats["setup_checks"] = checks
    feats["condition_labels"] = condition_labels(con, cfg, market, t_end, cutoff_dt, feats)
    for c in cands:
        c["setup_version"] = cfg["setups"][c["setup"]]["version"]
        c["atr14"] = feats["atr14"]
        c["trigger_bar_start"] = iso(from_ms(sig["candle_start_ms"]))
        c["trigger_bar_end"] = iso(from_ms(t_end))
        c["stop_distance_frac_at_signal"] = abs(c["signal_price"] - c["stop"]) / c["signal_price"]
    feats["gates"] = gates
    fh = sha256_text(canon({"features": feats, "cands": cands}))
    return {"features": feats, "candidates": cands, "gates": gates, "features_hash": fh, "calc_versions": CALC_VERSIONS}


def _vs_level(price, level, gt, lt):
    """above|below|at using configured float tolerance helpers."""
    if gt(price, level):
        return "above"
    if lt(price, level):
        return "below"
    return "at"


def condition_labels(con, cfg, market, t_end, cutoff_dt, feats):
    """Market-condition labels (config measurement.condition_labels, frozen at signal time).

    Tags are descriptive only — never consulted by setup triggers, trend gates, sizing, or fills.
    """
    mc = cfg.get("measurement", {}).get("condition_labels")
    if not mc:
        return None
    gt, lt, le, ge = _tol(cfg)
    out = {"version": mc["version"]}
    if "ema50" in feats:
        hc, em, em3 = feats["h1_close"], feats["ema50"], feats["ema50_3back"]
        out["trend"] = "TREND_UP" if gt(hc, em) and gt(em, em3) else ("TREND_DOWN" if lt(hc, em) and lt(em, em3) else "RANGE")
        out["trend_inputs"] = {"h1_close": hc, "ema50": em, "ema50_slope3": em - em3}
    else:
        out["trend"] = "UNAVAILABLE"
    p = cfg["markets"][market]["primary"]
    n = mc["volatility"]["trailing_bars"]
    period = cfg["indicators"]["atr"]["period"]
    need = n + 1 + 5 * period
    rows = get_bars(con, p["provider"], p["symbol"], "15m", t_end, cutoff_dt, limit=need)
    if len(rows) == need and contiguous(rows, 15 * MIN) and rows[-1]["candle_end_ms"] == t_end:
        a = atr_wilder(rows, period)
        cur, prev = a[-1], [x for x in a[-1 - n:-1] if x is not None]
        if len(prev) == n:
            rank = 100.0 * sum(1 for x in prev if x < cur) / n
            out["volatility"] = "HIGH_VOL" if rank >= mc["volatility"]["high_threshold_pct"] else "LOW_VOL"
            out["atr_pct_rank"] = rank
            out["atr_long_series"] = cur
        else:
            out["volatility"] = "UNAVAILABLE"
    else:
        out["volatility"] = "UNAVAILABLE"
        out["volatility_reason"] = f"need {need} contiguous 15m bars, have {len(rows)}"

    # --- cond-v1.1.0 context tags (logged only; not gates) ---
    _label_volume(out, mc, con, cfg, p, t_end, cutoff_dt, rows if rows else None)
    _label_vwap(out, mc, con, cfg, market, p, t_end, cutoff_dt, feats, gt, lt)
    _label_ema_trend(out, mc, con, cfg, p, t_end, cutoff_dt, feats, gt, lt)
    return out


def _label_volume(out, mc, con, cfg, p, t_end, cutoff_dt, rows15):
    """Trigger 15m bar volume vs trailing average of prior N 15m bars."""
    vol_cfg = mc.get("volume")
    if not vol_cfg:
        return
    n = int(vol_cfg["trailing_bars"])
    need = n + 1
    rows = rows15
    if rows is None or len(rows) < need or rows[-1]["candle_end_ms"] != t_end:
        rows = get_bars(con, p["provider"], p["symbol"], "15m", t_end, cutoff_dt, limit=need)
    if len(rows) >= need and rows[-1]["candle_end_ms"] == t_end:
        # use the last need bars; require contiguous among them
        window = rows[-need:]
        if contiguous(window, 15 * MIN):
            candle_v = window[-1]["volume"]
            prior = [b["volume"] for b in window[:-1]]
            if candle_v is None or any(v is None for v in prior):
                out["volume"] = "UNAVAILABLE"
                out["volume_reason"] = "missing volume on 15m bars"
                return
            avg = sum(prior) / n
            ratio = (candle_v / avg) if avg > 0 else None
            beats = bool(candle_v > avg) if avg > 0 else False
            out["volume_beats_avg"] = beats
            out["volume_ratio"] = ratio
            out["volume_candle"] = candle_v
            out["volume_avg"] = avg
            out["volume_trailing_bars"] = n
            out["volume"] = "ABOVE_AVG" if beats else "BELOW_OR_EQ_AVG"
            return
    out["volume"] = "UNAVAILABLE"
    out["volume_reason"] = f"need {need} contiguous 15m bars ending at signal, have {len(rows) if rows else 0}"


def _label_vwap(out, mc, con, cfg, market, p, t_end, cutoff_dt, feats, gt, lt):
    """Toronto-session VWAP from overnight_start through signal bar end on primary 1m bars."""
    vwap_cfg = mc.get("vwap")
    if not vwap_cfg:
        return
    session_date = feats.get("session_date")
    if not session_date:
        out["vwap"] = "UNAVAILABLE"
        out["vwap_reason"] = "no session_date in features"
        return
    if isinstance(session_date, str):
        y, m, d = map(int, session_date.split("-"))
        session_date = dt.date(y, m, d)
    start_field = vwap_cfg.get("session_start_field", "overnight_start")
    day_start = toronto_dt(session_date, cfg["session"][start_field])
    start_ms = to_ms(day_start)
    expected = int((t_end - start_ms) // MIN)
    if expected <= 0:
        out["vwap"] = "UNAVAILABLE"
        out["vwap_reason"] = "signal bar ends at/before session open"
        return
    rows = get_bars(con, p["provider"], p["symbol"], "1m", t_end, cutoff_dt, start_ms=start_ms)
    if len(rows) != expected or (rows and rows[-1]["candle_end_ms"] != t_end) or not contiguous(rows, MIN):
        out["vwap"] = "UNAVAILABLE"
        out["vwap_reason"] = f"need {expected} contiguous 1m bars from {cfg['session'][start_field]}, have {len(rows)}"
        return
    num = den = 0.0
    for b in rows:
        v = b["volume"]
        if v is None:
            out["vwap"] = "UNAVAILABLE"
            out["vwap_reason"] = "missing 1m volume"
            return
        tp = (b["high"] + b["low"] + b["close"]) / 3.0
        num += tp * v
        den += v
    if den <= 0:
        out["vwap"] = "UNAVAILABLE"
        out["vwap_reason"] = "zero session volume"
        return
    vwap = num / den
    if "signal_bar" in feats:
        price = feats["signal_bar"]["close"]
        price_source = "15m_signal_close"
    else:
        price = rows[-1]["close"]
        price_source = "1m_last_close"
    vs = _vs_level(price, vwap, gt, lt)
    out["vwap_value"] = vwap
    out["vwap_price"] = price
    out["vwap_price_source"] = price_source
    out["price_vs_vwap"] = vs
    out["vwap_distance_frac"] = (price - vwap) / vwap
    out["vwap_session_start"] = iso(day_start)
    out["vwap"] = vs.upper()  # ABOVE|BELOW|AT summary label


def _label_ema_trend(out, mc, con, cfg, p, t_end, cutoff_dt, feats, gt, lt):
    """1h close vs EMA50 and EMA200 (above|below). Does not affect entry gates."""
    et_cfg = mc.get("ema_trend")
    if not et_cfg:
        return
    b1h_end = t_end - t_end % (60 * MIN)
    need = int(et_cfg.get("warmup_bars_required_200", 200))
    rows = get_bars(con, p["provider"], p["symbol"], "1h", b1h_end, cutoff_dt, limit=need)
    ok = len(rows) == need and contiguous(rows, 60 * MIN) and rows and rows[-1]["candle_end_ms"] == b1h_end
    closes = [b["close"] for b in rows] if ok else None
    hc = closes[-1] if closes else feats.get("h1_close")

    # trend_50: prefer freshly computed series when available; else reuse feats
    if closes and len(closes) >= 50:
        e50 = ema(closes, 50)[-1]
    elif "ema50" in feats:
        e50 = feats["ema50"]
        hc = feats["h1_close"]
    else:
        e50 = None
    if e50 is None or hc is None:
        out["trend_50"] = "UNAVAILABLE"
        out["ema50_value"] = None
    else:
        out["trend_50"] = _vs_level(hc, e50, gt, lt)
        out["ema50_value"] = e50

    if closes and len(closes) >= 200:
        e200 = ema(closes, 200)[-1]
        out["trend_200"] = _vs_level(hc, e200, gt, lt)
        out["ema200_value"] = e200
        out["ema_trend_h1_close"] = hc
        out["ema_trend_h1_bar_end"] = iso(from_ms(rows[-1]["candle_end_ms"]))
    else:
        out["trend_200"] = "UNAVAILABLE"
        out["ema200_value"] = None
        out["ema_trend_reason"] = f"need {need} contiguous 1h bars for EMA200, have {len(rows)}"


def relative_strength(con, cfg, decision_dt, cutoff_dt=None):
    """Descriptive only (not a gate): SOL-BTC and ETH-BTC returns over the preceding 1h and 24h (primary 1m closes)."""
    cutoff_dt = cutoff_dt or decision_dt
    t = floor15(decision_dt)
    out = {}
    rets = {}
    for m in cfg["market_order"]:
        p = cfg["markets"][m]["primary"]
        r = {}
        for lbl, mins in (("1h", 60), ("24h", 1440)):
            a = get_bars(con, p["provider"], p["symbol"], "1m", t - mins * MIN, cutoff_dt, limit=1)
            b = get_bars(con, p["provider"], p["symbol"], "1m", t, cutoff_dt, limit=1)
            if a and b and a[0]["candle_end_ms"] == t - mins * MIN and b[0]["candle_end_ms"] == t:
                r[lbl] = b[0]["close"] / a[0]["close"] - 1
        rets[m] = r
    for alt in ("SOL", "ETH"):
        for lbl in ("1h", "24h"):
            if lbl in rets.get(alt, {}) and lbl in rets.get("BTC", {}):
                out[f"{alt}-BTC_{lbl}"] = rets[alt][lbl] - rets["BTC"][lbl]
    return {"returns": rets, "relative": out, "note": "descriptive feature; untested; not used as a gate"}
