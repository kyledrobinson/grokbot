"""Collector: stores primary and secondary candles separately (never blended), aggregates completed
15m/1h bars from primary 1m, and evaluates freshness gates."""
import datetime as dt
from . import providers
from .db import tx, writer_lock
from .util import iso, now_utc, from_ms, to_ms, parse_ts

MIN = 60_000


def store(con, batches, provider, instrument, timeframe, derivation, synthetic=0):
    ins = dup = rev = 0
    for rows, received, raw_ref, _host in batches:
        rts = iso(received)
        step = {"1m": MIN, "1h": 60 * MIN, "15m": 15 * MIN}[timeframe]
        for r in rows:
            cur = con.execute("INSERT OR IGNORE INTO market_data(provider,instrument,timeframe,derivation,candle_start_ms,candle_end_ms,open,high,low,close,volume,received_ts,is_final,raw_ref,synthetic) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)",
                              (provider, instrument, timeframe, derivation, r[0], r[0] + step, r[1], r[2], r[3], r[4], r[5], rts, raw_ref, synthetic))
            if cur.rowcount:
                ins += 1
            else:
                dup += 1
                old = con.execute("SELECT open,high,low,close FROM market_data WHERE provider=? AND instrument=? AND timeframe=? AND derivation=? AND candle_start_ms=?",
                                  (provider, instrument, timeframe, derivation, r[0])).fetchone()
                if old and any(abs(old[i] - r[i + 1]) > 1e-9 * max(1, abs(old[i])) for i in range(4)):
                    rev += 1
                    con.execute("INSERT INTO data_revisions(provider,instrument,timeframe,candle_start_ms,stored,received,received_ts) VALUES(?,?,?,?,?,?,?)",
                                (provider, instrument, timeframe, r[0], str(list(old)), str(r[1:5]), rts))
    return {"inserted": ins, "duplicates": dup, "revisions": rev}


def aggregate(con, provider, instrument, minutes, since_ms=None, synthetic=0):
    """Build completed N-minute bars from stored final 1m bars. Only bars with all N minutes present."""
    tf = {15: "15m", 60: "1h"}[minutes]
    span = minutes * MIN
    if since_ms is None:
        last = con.execute("SELECT MAX(candle_start_ms) FROM market_data WHERE provider=? AND instrument=? AND timeframe=? AND derivation='agg_1m'", (provider, instrument, tf)).fetchone()[0]
        since_ms = (last - 3 * span) if last else 0
    since_ms = since_ms - since_ms % span
    rows = con.execute("SELECT candle_start_ms,open,high,low,close,volume,received_ts FROM market_data WHERE provider=? AND instrument=? AND timeframe='1m' AND derivation='native_1m' AND candle_start_ms>=? ORDER BY candle_start_ms",
                       (provider, instrument, since_ms)).fetchall()
    buckets = {}
    for r in rows:
        buckets.setdefault(r[0] - r[0] % span, []).append(r)
    ins = 0
    for b, rs in sorted(buckets.items()):
        if len(rs) != minutes:
            continue
        o, c = rs[0][1], rs[-1][4]
        h = max(x[2] for x in rs)
        l = min(x[3] for x in rs)
        v = sum(x[5] or 0 for x in rs)
        rts = max(x[6] for x in rs)
        cur = con.execute("INSERT OR IGNORE INTO market_data(provider,instrument,timeframe,derivation,candle_start_ms,candle_end_ms,open,high,low,close,volume,received_ts,is_final,raw_ref,synthetic) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)",
                          (provider, instrument, tf, "agg_1m", b, b + span, o, h, l, c, v, rts, f"agg:{minutes}x1m", synthetic))
        ins += cur.rowcount
    return ins


def missing_minutes(con, provider, instrument, start_ms, end_ms):
    have = {r[0] for r in con.execute("SELECT candle_start_ms FROM market_data WHERE provider=? AND instrument=? AND timeframe='1m' AND derivation='native_1m' AND candle_start_ms>=? AND candle_start_ms<?",
                                      (provider, instrument, start_ms, end_ms)).fetchall()}
    return [t for t in range(start_ms - start_ms % MIN, end_ms, MIN) if t not in have]


def repair_primary_gaps(con, cfg, market, hours=48):
    """Refetch interior gaps in primary 1m data (late data repairs research data; it never makes a missed decision on-time)."""
    p = cfg["markets"][market]["primary"]
    now_ms = to_ms(now_utc())
    first = con.execute("SELECT MIN(candle_start_ms) FROM market_data WHERE provider=? AND instrument=? AND timeframe='1m' AND derivation='native_1m'", (p["provider"], p["symbol"])).fetchone()[0]
    if first is None:
        return 0
    start = max(first, now_ms - hours * 3600_000)
    miss = missing_minutes(con, p["provider"], p["symbol"], start, now_ms - 2 * MIN)
    if not miss:
        return 0
    batches = providers.binance_klines(p["symbol"], "1m", miss[0], end_ms=miss[-1] + MIN - 1)
    with writer_lock(), tx(con):
        r = store(con, batches, p["provider"], p["symbol"], "1m", "native_1m")
        aggregate(con, p["provider"], p["symbol"], 15, since_ms=miss[0])
        aggregate(con, p["provider"], p["symbol"], 60, since_ms=miss[0])
    return r["inserted"]


def last_start(con, provider, instrument, timeframe, derivation):
    return con.execute("SELECT MAX(candle_start_ms) FROM market_data WHERE provider=? AND instrument=? AND timeframe=? AND derivation=?",
                       (provider, instrument, timeframe, derivation)).fetchone()[0]


def collect(con, cfg, backfill_minutes=60 * 24 * 8, secondary_backfill_minutes=60 * 24, markets=None):
    """Fetch new primary+secondary 1m candles for each market, store, aggregate. Returns summary."""
    summary = {}
    now = now_utc()
    for m in markets or cfg["market_order"]:
        mc = cfg["markets"][m]
        p, s = mc["primary"], mc["secondary"]
        res = {}
        try:
            last = last_start(con, p["provider"], p["symbol"], "1m", "native_1m")
            start = (last + MIN) if last else to_ms(now) - backfill_minutes * MIN
            start = max(start, to_ms(now) - backfill_minutes * MIN)
            batches = providers.binance_klines(p["symbol"], "1m", start)
            with writer_lock(), tx(con):
                res["primary"] = store(con, batches, p["provider"], p["symbol"], "1m", "native_1m")
                res["agg15"] = aggregate(con, p["provider"], p["symbol"], 15)
                res["agg60"] = aggregate(con, p["provider"], p["symbol"], 60)
            rep = repair_primary_gaps(con, cfg, m)
            if rep:
                res["gap_repair_inserted"] = rep
        except Exception as e:
            res["primary_error"] = repr(e)
        try:
            last = last_start(con, s["provider"], s["symbol"], "1m", "native_1m")
            sstart = from_ms(last + MIN) if last else now - dt.timedelta(minutes=secondary_backfill_minutes)
            sstart = max(sstart, now - dt.timedelta(minutes=secondary_backfill_minutes))
            batches = providers.coinbase_1m(s["symbol"], sstart, now)
            with writer_lock(), tx(con):
                res["secondary"] = store(con, batches, s["provider"], s["symbol"], "1m", "native_1m")
        except Exception as e:
            res["secondary_error"] = repr(e)
        summary[m] = res
    return summary


def backfill_native_1h(con, cfg, since_ms_by_symbol=None):
    """Native primary 1h klines for forecast baseline history (separate derivation, never mixed with agg)."""
    out = {}
    for m in cfg["market_order"]:
        p = cfg["markets"][m]["primary"]
        last = last_start(con, p["provider"], p["symbol"], "1h", "native_1h")
        start = (last + 60 * MIN) if last else (since_ms_by_symbol or {}).get(p["symbol"], 1502928000000)
        batches = providers.binance_klines(p["symbol"], "1h", start, save_raw=False)
        with writer_lock(), tx(con):
            out[m] = store(con, batches, p["provider"], p["symbol"], "1h", "native_1h")
    return out


def bars(con, provider, instrument, timeframe, end_ms, cutoff_ts, limit=None, start_ms=None, derivation=None):
    """Completed bars with candle_end <= end_ms and received at/before cutoff (no look-ahead)."""
    derivation = derivation or ("native_1m" if timeframe == "1m" else "agg_1m")
    q = "SELECT candle_start_ms,candle_end_ms,open,high,low,close,volume,received_ts FROM market_data WHERE provider=? AND instrument=? AND timeframe=? AND derivation=? AND candle_end_ms<=? AND received_ts<=?"
    args = [provider, instrument, timeframe, derivation, end_ms, iso(cutoff_ts) if not isinstance(cutoff_ts, str) else cutoff_ts]
    if start_ms is not None:
        q += " AND candle_start_ms>=?"
        args.append(start_ms)
    if limit:
        q += " ORDER BY candle_start_ms DESC LIMIT ?"
        args.append(limit)
        rows = con.execute(q, args).fetchall()[::-1]
    else:
        q += " ORDER BY candle_start_ms"
        rows = con.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def freshness(con, cfg, market, decision_dt, expected_bar_end_ms=None):
    """Section-5 data gates evaluated with data received at/before decision_dt."""
    g = cfg["data_gates"]
    mc = cfg["markets"][market]
    p, s = mc["primary"], mc["secondary"]
    cutoff = iso(decision_dt)
    dms = to_ms(decision_dt)
    lp = con.execute("SELECT candle_end_ms, close, received_ts FROM market_data WHERE provider=? AND instrument=? AND timeframe='1m' AND derivation='native_1m' AND received_ts<=? AND candle_end_ms<=? ORDER BY candle_start_ms DESC LIMIT 1",
                     (p["provider"], p["symbol"], cutoff, dms)).fetchone()
    ls = con.execute("SELECT candle_end_ms, close, received_ts FROM market_data WHERE provider=? AND instrument=? AND timeframe='1m' AND derivation='native_1m' AND received_ts<=? AND candle_end_ms<=? ORDER BY candle_start_ms DESC LIMIT 1",
                     (s["provider"], s["symbol"], cutoff, dms)).fetchone()
    out = {"decision_ts": cutoff, "gates": {}}
    if lp is None:
        out["gates"]["latest_price_fresh"] = {"pass": False, "reason": "NO_PRIMARY_DATA"}
    else:
        age = (dms - lp[0]) / 1000
        out["latest_primary"] = {"candle_end": iso(from_ms(lp[0])), "close": lp[1], "received_ts": lp[2], "age_s": age}
        out["gates"]["latest_price_fresh"] = {"pass": age <= g["max_latest_price_age_s"], "age_s": age, "max_s": g["max_latest_price_age_s"]}
    if expected_bar_end_ms is not None:
        n = con.execute("SELECT COUNT(*), MAX(received_ts) FROM market_data WHERE provider=? AND instrument=? AND timeframe='1m' AND derivation='native_1m' AND candle_start_ms>=? AND candle_end_ms<=? AND received_ts<=?",
                        (p["provider"], p["symbol"], expected_bar_end_ms - 15 * MIN, expected_bar_end_ms, cutoff)).fetchone()
        out["gates"]["expected_bar_present"] = {"pass": n[0] == 15, "minutes_present": n[0], "bar_end": iso(from_ms(expected_bar_end_ms)),
                                                "last_received": n[1]}
    if lp is not None and ls is not None:
        # compare at the same candle if possible
        same = con.execute("SELECT a.close, b.close, a.candle_start_ms FROM market_data a JOIN market_data b ON a.candle_start_ms=b.candle_start_ms WHERE a.provider=? AND a.instrument=? AND a.timeframe='1m' AND a.derivation='native_1m' AND b.provider=? AND b.instrument=? AND b.timeframe='1m' AND b.derivation='native_1m' AND a.received_ts<=? AND b.received_ts<=? AND a.candle_end_ms<=? ORDER BY a.candle_start_ms DESC LIMIT 1",
                           (p["provider"], p["symbol"], s["provider"], s["symbol"], cutoff, cutoff, dms)).fetchone()
        if same:
            diff = abs(same[0] / same[1] - 1) * 100
            sec_age = (dms - (same[2] + MIN)) / 1000
            ok = diff <= g["provider_disagreement_tolerance_pct"] and sec_age <= 300
            out["gates"]["provider_agreement"] = {"pass": ok, "diff_pct": round(diff, 5), "tol_pct": g["provider_disagreement_tolerance_pct"],
                                                  "compared_candle": iso(from_ms(same[2])), "compared_age_s": sec_age,
                                                  "primary_close": same[0], "secondary_close": same[1]}
        else:
            out["gates"]["provider_agreement"] = {"pass": False, "reason": "NO_OVERLAPPING_SECONDARY_CANDLE"}
    else:
        out["gates"]["provider_agreement"] = {"pass": False, "reason": "SECONDARY_MISSING" if ls is None else "PRIMARY_MISSING"}
    out["pass"] = all(v["pass"] for v in out["gates"].values())
    return out
