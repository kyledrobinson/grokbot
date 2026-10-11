"""Paper fill simulator (spec section 8). Pure functions over primary 1m bars in timestamp order.
Bars: dicts with candle_start_ms, open, high, low, close."""
MIN = 60_000


def entry_fill(bars, commit_ms, latency_ms, side, slip_bps):
    """Next observable price: open of the first 1m bar starting at/after commit+latency, adverse slippage."""
    t = commit_ms + latency_ms
    for b in bars:
        if b["candle_start_ms"] >= t:
            slip = slip_bps / 1e4
            px = b["open"] * (1 + slip) if side == "long" else b["open"] * (1 - slip)
            return b, px
    return None, None


def target_price(side, entry, stop, r_mult):
    dist = (entry - stop) if side == "long" else (stop - entry)
    return entry + r_mult * dist if side == "long" else entry - r_mult * dist


def valid_levels(side, entry, stop):
    return stop < entry if side == "long" else stop > entry


def step(side, stop, target, bar, slip_bps, noon_ms):
    """Evaluate one post-entry bar. Returns None or (reason, price, ambiguous)."""
    slip = slip_bps / 1e4
    o, h, l = bar["open"], bar["high"], bar["low"]
    if bar["candle_start_ms"] >= noon_ms:
        px = o * (1 - slip) if side == "long" else o * (1 + slip)
        return ("NOON_CLOSE", px, False)
    if side == "long":
        if o <= stop:
            return ("STOP_GAP", o * (1 - slip), False)
        if o >= target:
            return ("TARGET", target, False)
        hit_s, hit_t = l <= stop, h >= target
        if hit_s:
            return ("STOP", stop * (1 - slip), hit_t)
        if hit_t:
            return ("TARGET", target, False)
    else:
        if o >= stop:
            return ("STOP_GAP", o * (1 + slip), False)
        if o <= target:
            return ("TARGET", target, False)
        hit_s, hit_t = h >= stop, l <= target
        if hit_s:
            return ("STOP", stop * (1 + slip), hit_t)
        if hit_t:
            return ("TARGET", target, False)
    return None


def run_exits(side, stop, target, bars, start_ms, slip_bps, noon_ms, lock_px=None, lock_pending=False):
    """Process bars from start_ms (inclusive) in order. Returns dict with exit or last_processed/unresolved.
    lock_px: price at which the 5% daily loss lockout is breached on a bar close -> flatten at next bar open."""
    expected = start_ms
    last = None
    slip = slip_bps / 1e4
    for b in bars:
        if b["candle_start_ms"] < start_ms:
            continue
        if b["candle_start_ms"] != expected:
            return {"status": "UNRESOLVED", "reason": "MISSING_1M_BARS", "gap_from_ms": expected, "gap_to_ms": b["candle_start_ms"], "last_processed_ms": last}
        if lock_pending and b["candle_start_ms"] < noon_ms:
            px = b["open"] * (1 - slip) if side == "long" else b["open"] * (1 + slip)
            return {"status": "EXIT", "reason": "LOCKOUT_FLATTEN", "price": px, "ambiguous": False, "exit_ms": b["candle_start_ms"], "last_processed_ms": b["candle_start_ms"], "bar": b}
        r = step(side, stop, target, b, slip_bps, noon_ms)
        if r:
            return {"status": "EXIT", "reason": r[0], "price": r[1], "ambiguous": r[2], "exit_ms": b["candle_start_ms"], "last_processed_ms": b["candle_start_ms"], "bar": b}
        if lock_px is not None and ((side == "long" and b["close"] <= lock_px) or (side == "short" and b["close"] >= lock_px)):
            lock_pending = True
        last = b["candle_start_ms"]
        expected = b["candle_start_ms"] + MIN
    return {"status": "OPEN", "last_processed_ms": last, "next_expected_ms": expected, "lock_pending": lock_pending}


def gross_pnl(side, notional, entry, exit_px):
    return notional * (exit_px / entry - 1) if side == "long" else notional * (1 - exit_px / entry)


def integrate_borrow(snapshots, start_ms, end_ms, notional, side):
    """Piecewise-constant integration of hourly borrow % over [start,end]. snapshots: [(ms, long_pct, short_pct)] sorted.
    The rate in force at start is the latest snapshot at/before start (or first after, flagged)."""
    if end_ms <= start_ms:
        return 0.0, []
    snaps = sorted(snapshots)
    before = [s for s in snaps if s[0] <= start_ms]
    inside = [s for s in snaps if start_ms < s[0] < end_ms]
    flags = []
    if before:
        pts = [(start_ms, before[-1][1], before[-1][2])] + inside
    elif inside:
        pts = [(start_ms, inside[0][1], inside[0][2])] + inside
        flags.append("NO_SNAPSHOT_AT_ENTRY_USED_FIRST_LATER")
    else:
        return None, ["NO_BORROW_SNAPSHOTS"]
    total = 0.0
    intervals = []
    for i, p in enumerate(pts):
        a = p[0]
        b = pts[i + 1][0] if i + 1 < len(pts) else end_ms
        rate = p[1] if side == "long" else p[2]
        cost = notional * rate / 100 * (b - a) / 3_600_000
        total += cost
        intervals.append({"from_ms": a, "to_ms": b, "hourly_pct": rate, "cost_usd": cost})
    return total, intervals + ([{"flags": flags}] if flags else [])


def update_excursions(state, side, notional, entry, bars, exit_px=None, exit_ms=None):
    """MAE/MFE from fully post-entry bars (entry bar included: entry is at its open). In the exit bar only the
    exit price counts. state keys: mae_px, mae_ms, mfe_px, mfe_ms. Excursions are signed $: <0 adverse."""
    st = dict(state)
    pts = []
    for b in bars:
        adv, fav = (b["low"], b["high"]) if side == "long" else (b["high"], b["low"])
        pts.append((adv, fav, b["candle_start_ms"]))
    if exit_px is not None:
        pts.append((exit_px, exit_px, exit_ms))
    for adv, fav, ms in pts:
        if st.get("mae_px") is None or (adv < st["mae_px"] if side == "long" else adv > st["mae_px"]):
            st["mae_px"], st["mae_ms"] = adv, ms
        if st.get("mfe_px") is None or (fav > st["mfe_px"] if side == "long" else fav < st["mfe_px"]):
            st["mfe_px"], st["mfe_ms"] = fav, ms
    if st.get("mae_px") is not None:
        st["mae_usd"] = gross_pnl(side, notional, entry, st["mae_px"])
        st["mfe_usd"] = gross_pnl(side, notional, entry, st["mfe_px"])
    return st


def exit_slippage_usd(side, notional, entry, exit_px, reason, slip_bps):
    if reason == "TARGET":
        return 0.0
    slip = slip_bps / 1e4
    raw = exit_px / (1 - slip) if side == "long" else exit_px / (1 + slip)
    return abs(raw - exit_px) / entry * notional


def entry_slippage_usd(notional, entry, proxy_open):
    return abs(entry - proxy_open) / entry * notional


def cost_sensitivity(gross, fees, financing, slippage, multipliers):
    """Slippage is already embedded in gross (fill prices), so k*slippage adds (k-1)*slippage."""
    return {f"{k:g}x": gross - k * fees - k * financing - (k - 1) * slippage for k in multipliers}
