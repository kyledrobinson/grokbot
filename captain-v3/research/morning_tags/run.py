"""Morning tags v1.0.0 — read-only research tagger (context labels only, never entry rules).

Usage (from /workspace/captain-v3):
  python3 -m research.morning_tags.run                 # backfill anything missing + tag latest session/signals (idempotent)
  python3 -m research.morning_tags.run --early-read    # also print/write the small-sample early read
  python3 -m research.morning_tags.run --today         # print the latest daily tags in plain words
Reads captain.db and math-momentum shadow.db with sqlite mode=ro; writes only research/morning_tags/tags.db (+ early_read.*)."""
import datetime as dt, hashlib, json, os, sqlite3, statistics, sys
from . import tags as T
from .data import Bars, connect_ro, iso, parse_ms, et_ms, et_date, et_str, M1, M15, H1, TZ

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(HERE, "morning-tags-v1.0.0.json")
SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_tags(
  session_date TEXT NOT NULL, asset TEXT NOT NULL, config_version TEXT NOT NULL, status TEXT NOT NULL, knowledge TEXT,
  moment_ts TEXT NOT NULL, known_at_ts TEXT NOT NULL, computed_ts TEXT NOT NULL, weekday TEXT,
  c4_source TEXT, c4_open REAL, c4_high REAL, c4_low REAL, c4_close REAL, c4_dir TEXT, body_frac REAL,
  upper_wick_frac REAL, lower_wick_frac REAL, opposing_wick_frac REAL, close_loc REAL, range_pct REAL,
  range_vs_med20 REAL, med_days_used INTEGER, clean INTEGER,
  asia_dir TEXT, london_dir TEXT, london_reversed_asia INTEGER, day_type TEXT,
  fvg_type TEXT, fvg_low REAL, fvg_high REAL, fvg_formed_bar_start_ts TEXT, fvg_position TEXT, fvg_dist_pct REAL, fvg_dist_atr REAL,
  fvg_unfilled_count INTEGER, atr1h REAL, price_0600 REAL, max_received_ts TEXT, detail TEXT,
  PRIMARY KEY(session_date, asset));
CREATE TABLE IF NOT EXISTS event_tags(
  source TEXT NOT NULL, record_id TEXT NOT NULL, market TEXT, session_date TEXT, daily_session_date TEXT, setup TEXT, side TEXT,
  break_dir TEXT, event_ts TEXT, known_at_ts TEXT, status TEXT NOT NULL, knowledge TEXT,
  confirm_label TEXT, n_confirm INTEGER, confirm_at_signal TEXT, n_confirm_at_signal INTEGER, confirm_fresh_label TEXT, n_confirm_fresh INTEGER,
  strongest TEXT, strongest_excursion_pct REAL, strength_switch INTEGER, self_beyond_at_signal INTEGER,
  max_received_ts TEXT, detail TEXT, config_version TEXT NOT NULL, computed_ts TEXT NOT NULL,
  PRIMARY KEY(source, record_id));
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, started_ts TEXT, finished_ts TEXT, config_version TEXT, config_sha256 TEXT,
  daily_written INTEGER, events_written INTEGER, note TEXT);
"""


def load_cfg(path=CFG_PATH):
    with open(path, "rb") as f:
        raw = f.read()
    c = json.loads(raw)
    c["_sha256"] = hashlib.sha256(raw).hexdigest()
    return c


def now_ms():
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def knowledge(max_recv, known_at_ms, allow_s):
    return "live" if max_recv is not None and max_recv <= known_at_ms + allow_s * 1000 else "reconstructed"


# ------------------------------------------------------------------ daily tags
def c4_cached(cache, bars, d, cfg):
    k = str(d)
    if k not in cache:
        c = cfg["candle_6am"]
        cache[k] = bars.window(et_ms(d, c["window_start"]), et_ms(d, c["window_end"]))
    return cache[k]


def compute_daily(bars, d, cfg, cache, now):
    """Tags for asset session date d, as of 06:00 ET. Only bars ending <= 06:00 are used."""
    c, sp, fc = cfg["candle_6am"], cfg["session_profile"], cfg["fvg"]
    moment = et_ms(d, c["window_end"])
    known_at = moment + cfg["received_allowance_s"] * 1000
    row = {"session_date": str(d), "moment_ts": iso(moment), "known_at_ts": iso(known_at), "weekday": d.strftime("%a"),
           "config_version": cfg["config_version"]}
    if now < known_at:
        return None
    c4 = c4_cached(cache, bars, d, cfg)
    if not c4:
        row["status"] = "missing_data"
        return row
    recvs = [c4["recv"]]
    shp = T.candle_shape(c4["o"], c4["h"], c4["l"], c4["c"], c["clean_max_opposing_wick_frac"], c["clean_min_body_frac"])
    past = []
    for k in range(1, c["range_median_days"] + 1):
        p = c4_cached(cache, bars, d - dt.timedelta(days=k), cfg)
        past.append(p["h"] - p["l"] if p else None)
    ratio, used, med = T.range_vs_median(shp["range"], past, c["range_median_min_days"])
    prev = d - dt.timedelta(days=1)
    asia = bars.window(et_ms(prev, sp["asia_start_prev_day"]), et_ms(d, sp["asia_end"]))
    london = bars.window(et_ms(d, sp["london_start"]), et_ms(d, sp["london_end"]))
    a_dir = T.direction(asia["o"], asia["c"]) if asia else None
    l_dir = T.direction(london["o"], london["c"]) if london else None
    if asia: recvs.append(asia["recv"])
    rev, day_type = T.session_profile(a_dir, l_dir)
    # FVG on 1h bars: prior calendar day through 06:00
    p0 = et_ms(prev, "00:00")
    hrs = bars.hours(p0 - 2 * H1, moment)
    gaps = T.find_fvgs(hrs, p0, et_ms(d, "00:00"), fc["min_gap_pct"])
    unfilled = [g for g in gaps if not g["filled"]]
    atr_bars = bars.hours(moment - fc["atr_seed_bars"] * H1, moment)
    atr = T.atr_wilder([(b["o"], b["h"], b["l"], b["c"]) for b in atr_bars], fc["atr_period"]) if len(atr_bars) == fc["atr_seed_bars"] else None
    recvs += [b["recv"] for b in hrs] + [b["recv"] for b in atr_bars]
    g = unfilled[-1] if unfilled else None
    dist = T.fvg_distance(g, c4["c"], atr) if g else None
    max_recv = max(recvs)
    row.update({
        "status": "ok", "knowledge": knowledge(max_recv, moment, cfg["received_allowance_s"]),
        "c4_source": c4["src"], "c4_open": c4["o"], "c4_high": c4["h"], "c4_low": c4["l"], "c4_close": c4["c"],
        "c4_dir": shp["dir"], "body_frac": shp["body_frac"], "upper_wick_frac": shp["upper_wick_frac"],
        "lower_wick_frac": shp["lower_wick_frac"], "opposing_wick_frac": shp["opposing_wick_frac"], "close_loc": shp["close_loc"],
        "range_pct": shp["range"] / c4["o"] * 100, "range_vs_med20": ratio, "med_days_used": used, "clean": int(shp["clean"]),
        "asia_dir": a_dir, "london_dir": l_dir, "london_reversed_asia": None if rev is None else int(rev), "day_type": day_type,
        "fvg_type": g["type"] if g else None, "fvg_low": g["low"] if g else None, "fvg_high": g["high"] if g else None,
        "fvg_formed_bar_start_ts": iso(g["formed_bar_start"]) if g else None,
        "fvg_position": dist["position"] if dist else None, "fvg_dist_pct": dist["dist_pct"] if dist else None,
        "fvg_dist_atr": dist["dist_atr"] if dist else None, "fvg_unfilled_count": len(unfilled), "atr1h": atr,
        "price_0600": c4["c"], "max_received_ts": iso(max_recv),
        "detail": json.dumps({"range_median_abs": med, "prior_day_gaps": [dict(x, formed_bar_start=iso(x["formed_bar_start"])) for x in gaps],
                              "asia_ohlc": [asia[k] for k in "ohlc"] if asia else None, "hourly_bars_used": len(hrs),
                              "fvg_hours_src": sorted({b["src"] for b in hrs})}, sort_keys=True)})
    return row


# ------------------------------------------------------------------ event tags
def overnight(bars15, d, cfg):
    ca = cfg["cross_asset"]
    s, e = et_ms(d, ca["overnight_start"]), et_ms(d, ca["overnight_end"])
    rows = [bars15.bar15(t) for t in range(s, e, M15)]
    if not all(rows):
        return None
    return {"high": max(r["h"] for r in rows), "low": min(r["l"] for r in rows), "recv": max(r["recv"] for r in rows), "end": e}


def compute_event(B, cfg, mkt, t0, d_dir, now, meta):
    """t0 = end of trigger bar (ms). Window = bar ending t0-15m, trigger bar (ending t0), next bar (ending t0+15m)."""
    d = et_date(t0 - 1)
    known_at = t0 + M15
    base = {"market": mkt, "session_date": str(d), "event_ts": iso(t0), "known_at_ts": iso(known_at),
            "config_version": cfg["config_version"], **meta}
    sess_start = et_ms(d, cfg["cross_asset"]["overnight_end"])
    if t0 <= sess_start:
        return dict(base, status="no_level_yet", break_dir=d_dir)
    per, recvs = {}, []
    for m in cfg["market_order"]:
        on = overnight(B[m], d, cfg)
        if not on:
            return dict(base, status="missing_data", break_dir=d_dir, detail=json.dumps({"missing": f"{m} overnight 15m bars"}))
        pre = [B[m].bar15(t0 - 2 * M15), B[m].bar15(t0 - M15)]
        if not all(pre):
            return dict(base, status="missing_data", break_dir=d_dir, detail=json.dumps({"missing": f"{m} window bars"}))
        nxt = B[m].bar15(t0) if now >= known_at else None
        per[m] = {"level": on["high"] if d_dir == "up" else on["low"], "pre": pre, "next": nxt, "onh": on["high"], "onl": on["low"]}
        per[m]["first_beyond_end"] = first_beyond(B[m], sess_start, t0 + (M15 if nxt else 0), per[m]["level"], d_dir, cfg["float_tolerance_rel"])
        recvs += [on["recv"]] + [b["recv"] for b in pre] + ([nxt["recv"]] if nxt else [])
    r = T.cross_asset(mkt, d_dir, per)
    if not r["complete"]:
        status = "pending" if now < known_at + 6 * H1 else "missing_data"
    else:
        status = "ok"
    max_recv = max(recvs)
    others = [m for m in per if m != mkt]
    fresh = {m: per[m]["first_beyond_end"] is not None and t0 - M15 <= per[m]["first_beyond_end"] <= t0 + M15 for m in per}
    n_fresh = sum(fresh[m] for m in others) if r["complete"] else None
    return dict(base, status=status, confirm_fresh_label=T.confirm_label(n_fresh), n_confirm_fresh=n_fresh, knowledge=knowledge(max_recv, known_at, cfg["received_allowance_s"]) if status == "ok" else None,
                break_dir=d_dir, confirm_label=r["confirm_label"], n_confirm=r["n_confirm"], confirm_at_signal=r["confirm_at_signal"],
                n_confirm_at_signal=r["n_confirm_at_signal"], strongest=r["strongest"], strongest_excursion_pct=r["strongest_excursion_pct"],
                strength_switch=None if r["strength_switch"] is None else int(r["strength_switch"]),
                self_beyond_at_signal=int(bool(r["self_beyond_at_signal"])), max_received_ts=iso(max_recv),
                detail=json.dumps({"levels": {m: {"onh": per[m]["onh"], "onl": per[m]["onl"]} for m in per},
                                   "first_beyond_bar_end": {m: (iso(per[m]["first_beyond_end"]) if per[m]["first_beyond_end"] else None) for m in per},
                                   "fresh_break_in_window": fresh,
                                   "excursion_pct_at_signal": r["excursion_pct_at_signal"],
                                   "excursion_pct_window": r["excursion_pct_window"]}, sort_keys=True))


def first_beyond(b, start, end, level, d, tol):
    """End time of the first session 15m bar (06:00 onward, ending <= end) that traded beyond the level."""
    t = start
    while t + M15 <= end:
        x = b.bar15(t)
        if x and ((d == "up" and x["h"] > level * (1 + tol)) or (d == "down" and x["l"] < level * (1 - tol))):
            return t + M15
        t += M15
    return None


def v3_break_dir(setup, side):
    # A = breakout (long through ONH / short through ONL); B = failed probe (short after probing ONH / long after probing ONL)
    if setup == "A":
        return "up" if side == "long" else "down"
    return "up" if side == "short" else "down"


def daily_session_for(t0, cfg):
    d = et_date(t0 - 1)
    return d if t0 >= et_ms(d, cfg["candle_6am"]["window_end"]) + cfg["received_allowance_s"] * 1000 else d - dt.timedelta(days=1)


def v3_events(con):
    con.row_factory = sqlite3.Row
    sig = {r["signal_id"]: dict(r) for r in con.execute("SELECT signal_id,market,setup,side,trigger_bar_end_ts FROM signals WHERE synthetic=0")}
    out = []
    for s in sig.values():
        out.append(("v3_signal", s["signal_id"], s))
    for r in con.execute("SELECT hyp_id, signal_id FROM hypothetical_outcomes WHERE synthetic=0 AND signal_id IS NOT NULL"):
        if r["signal_id"] in sig:
            out.append(("v3_hypothetical", r["hyp_id"], sig[r["signal_id"]]))
    for r in con.execute("SELECT t.trade_id, d.signal_id FROM trades t JOIN decisions d USING(decision_id) WHERE t.synthetic=0"):
        if r["signal_id"] in sig:
            out.append(("v3_trade", r["trade_id"], sig[r["signal_id"]]))
    con.row_factory = None
    return out


def mm_runs(path):
    if not os.path.exists(path):
        return []
    c = connect_ro(path)
    try:
        return c.execute("SELECT run_id, cutoff_ts, action, action_market FROM runs ORDER BY cutoff_ts").fetchall()
    finally:
        c.close()


# ------------------------------------------------------------------ storage / driver
def open_tags(path):
    c = sqlite3.connect(path, timeout=30)
    c.executescript(SCHEMA)
    return c


def upsert(c, table, row):
    cols = list(row)
    c.execute(f"INSERT OR REPLACE INTO {table}({','.join(cols)}) VALUES({','.join('?' * len(cols))})", [row[k] for k in cols])


def run(cfg=None, now=None, src_db=None, mm_db=None, tags_db=None, recompute=False, log=print):
    cfg = cfg or load_cfg()
    now = now or now_ms()
    src_db, mm_db, tags_db = src_db or cfg["source_db"], mm_db or cfg["math_momentum_db"], tags_db or cfg["tags_db"]
    started = iso(now_ms())
    con = connect_ro(src_db)
    tc = open_tags(tags_db)
    final_daily = set() if recompute else {(r[0], r[1]) for r in tc.execute("SELECT session_date, asset FROM daily_tags WHERE status='ok'")}
    final_ev = set() if recompute else {(r[0], r[1]) for r in tc.execute("SELECT source, record_id FROM event_tags WHERE status NOT IN ('pending','missing_data')")}
    B = {m: Bars(con, v["provider"], v["symbol"]) for m, v in cfg["markets"].items()}
    nd = ne = 0
    today = et_date(now)
    for m in cfg["market_order"]:
        b = B[m]
        starts = [min(b.h1n) if b.h1n else None, min(b.m1) if b.m1 else None]
        first = et_date(min(s for s in starts if s is not None)) + dt.timedelta(days=1)
        cache = {}
        d = first
        while d <= today:
            if (str(d), m) not in final_daily:
                row = compute_daily(b, d, cfg, cache, now)
                if row and not (row["status"] == "missing_data" and d < today - dt.timedelta(days=3)):
                    row.update(asset=m, computed_ts=iso(now_ms()))
                    upsert(tc, "daily_tags", row); nd += 1
            d += dt.timedelta(days=1)
    for src, rid, s in v3_events(con):
        if (src, rid) in final_ev:
            continue
        t0 = parse_ms(s["trigger_bar_end_ts"])
        meta = {"source": src, "record_id": rid, "setup": s["setup"], "side": s["side"],
                "daily_session_date": str(daily_session_for(t0, cfg))}
        row = compute_event(B, cfg, s["market"], t0, v3_break_dir(s["setup"], s["side"]), now, meta)
        row["computed_ts"] = iso(now_ms())
        upsert(tc, "event_tags", row); ne += 1
    for run_id, cutoff, action, amkt in mm_runs(mm_db):
        t0 = parse_ms(cutoff)
        for m in cfg["market_order"]:
            rid = f"{run_id}:{m}"
            if ("math_momentum", rid) in final_ev:
                continue
            meta = {"source": "math_momentum", "record_id": rid, "setup": f"MM:{action}" + (f":{amkt}" if amkt else ""), "side": None,
                    "daily_session_date": str(daily_session_for(t0, cfg))}
            # MM records are not level-break events: tag the direction in which this market is beyond its level at the cutoff
            cand = []
            for dd in ("up", "down"):
                r = compute_event(B, cfg, m, t0, dd, now, meta)
                ex = (json.loads(r.get("detail") or "{}").get("excursion_pct_at_signal") or {}).get(m)
                cand.append((ex if ex is not None else -1e9, r))
            ex, row = max(cand, key=lambda x: x[0])
            if row["status"] in ("ok", "pending") and not (ex > 0):
                row.update(status="no_break" if row["status"] == "ok" else "pending", break_dir=None, confirm_label="no_break" if row["status"] == "ok" else None)
            row["computed_ts"] = iso(now_ms())
            upsert(tc, "event_tags", row); ne += 1
    rid = "MT-" + iso(now).replace(":", "").replace("-", "")
    tc.execute("INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?,?,?,?)", (rid, started, iso(now_ms()), cfg["config_version"], cfg["_sha256"], nd, ne,
                                                                        "read-only tagger; context labels only"))
    tc.commit(); tc.close(); con.close()
    log(f"[morning_tags] daily rows written {nd}, event rows written {ne} (already-final rows skipped)")
    return nd, ne


# ------------------------------------------------------------------ reporting
def today_words(tags_db, now=None, cfg=None):
    """Latest daily tags per coin in plain words; returns (session_date, is_today, {coin: words}, day_type_words)."""
    cfg = cfg or load_cfg()
    now = now or now_ms()
    if not os.path.exists(tags_db):
        return None
    c = connect_ro(tags_db)
    r = c.execute("SELECT MAX(session_date) FROM daily_tags WHERE status='ok'").fetchone()
    if not r or not r[0]:
        return None
    sd = r[0]
    rows = {a: (dirn, clean, rev, dt_) for a, dirn, clean, rev, dt_ in
            c.execute("SELECT asset,c4_dir,clean,london_reversed_asia,day_type FROM daily_tags WHERE session_date=? AND status='ok'", (sd,))}
    c.close()
    words, days = {}, {}
    for a in cfg["market_order"]:
        if a in rows:
            dirn, clean, rev, dt_ = rows[a]
            words[a] = f"{dirn}, {'clean' if clean else 'not clean'}"
            days[a] = {"continuation_day": "continuation", "reversal_day": "reversal"}.get(dt_, "unclear")
    return {"session_date": sd, "is_today": sd == str(et_date(now)), "coins": words, "day_type": days}


def early_read(cfg=None, src_db=None, tags_db=None):
    cfg = cfg or load_cfg()
    con = connect_ro(src_db or cfg["source_db"])
    out_vals = {}
    for kind, q in (("v3_hypothetical", "SELECT hyp_id, net_r, side FROM hypothetical_outcomes WHERE status='CLOSED' AND net_r IS NOT NULL AND synthetic=0"),
                    ("v3_trade", "SELECT trade_id, net_r, side FROM trades WHERE status='CLOSED' AND net_r IS NOT NULL AND synthetic=0")):
        out_vals[kind] = {r[0]: (r[1], r[2]) for r in con.execute(q)}
    con.close()
    tc = connect_ro(tags_db or cfg["tags_db"])
    res = {}
    for kind, vals in out_vals.items():
        rows = []
        for rid, (nr, side) in vals.items():
            e = tc.execute("SELECT status, knowledge, confirm_label, strength_switch, daily_session_date, market, confirm_fresh_label FROM event_tags WHERE source=? AND record_id=?", (kind, rid)).fetchone()
            if not e:
                continue
            dly = tc.execute("SELECT c4_dir, clean, london_reversed_asia, knowledge FROM daily_tags WHERE session_date=? AND asset=? AND status='ok'", (e[4], e[5])).fetchone()
            rows.append({"net_r": nr, "side": side, "ev_status": e[0], "ev_knowledge": e[1], "confirm": e[2], "switch": e[3], "daily": dly, "fresh": e[6]})
        cells = []
        def add(group, label, sel):
            v = [r["net_r"] for r in rows if sel(r)]
            cells.append({"group": group, "cell": label, "n": len(v), "mean_net_r": (sum(v) / len(v)) if v else None,
                          "verdict": "INCONCLUSIVE (n<30)" if len(v) < 30 else "EARLY (n>=30 but ~2 weeks, one regime; no conclusion)"})
        def aligned(r):
            if not r["daily"] or r["daily"][0] in (None, "flat"):
                return None
            return (r["daily"][0] == "up") == (r["side"] == "long")
        add("all", "all resolved", lambda r: True)
        add("6AM 4h candle", "clean & aligned with signal", lambda r: r["daily"] and r["daily"][1] == 1 and aligned(r) is True)
        add("6AM 4h candle", "clean & opposed to signal", lambda r: r["daily"] and r["daily"][1] == 1 and aligned(r) is False)
        add("6AM 4h candle", "not clean", lambda r: r["daily"] and r["daily"][1] == 0)
        add("6AM 4h candle", "no tag", lambda r: not r["daily"])
        add("session profile", "london_reversed_asia = true (continuation day)", lambda r: r["daily"] and r["daily"][2] == 1)
        add("session profile", "london_reversed_asia = false (reversal day)", lambda r: r["daily"] and r["daily"][2] == 0)
        add("session profile", "unlabelled (flat/missing)", lambda r: not r["daily"] or r["daily"][2] is None)
        for lab in ("all_confirm", "partial", "diverge"):
            add("cross-asset (+/-15m)", lab, lambda r, lab=lab: r["ev_status"] == "ok" and r["confirm"] == lab)
        add("cross-asset (+/-15m)", "not labelled (missing/pending)", lambda r: r["ev_status"] != "ok")
        for lab in ("all_confirm", "partial", "diverge"):
            add("cross-asset, fresh breaks only", lab, lambda r, lab=lab: r["ev_status"] == "ok" and r["fresh"] == lab)
        add("strength switch", "strength_switch = true", lambda r: r["ev_status"] == "ok" and r["switch"] == 1)
        add("strength switch", "strength_switch = false", lambda r: r["ev_status"] == "ok" and r["switch"] == 0)
        res[kind] = {"n_resolved": len(rows), "n_daily_live": sum(1 for r in rows if r["daily"] and r["daily"][3] == "live"),
                     "n_event_live": sum(1 for r in rows if r["ev_knowledge"] == "live"), "cells": cells}
    tc.close()
    return res


def early_read_md(res):
    L = ["# Morning tags — EARLY READ (small sample, NO conclusions)", "",
         "Net R after modeled/real fees. Any cell with n < 30 is INCONCLUSIVE. Tags are context labels only; nothing here changes any rule.", ""]
    for kind, title in (("v3_hypothetical", "Captain v3 skipped signals (resolved hypothetical outcomes)"), ("v3_trade", "Captain v3 official paper trades")):
        r = res.get(kind)
        if not r:
            continue
        L += [f"## {title}: {r['n_resolved']} resolved", f"(daily tags built from bars received on time ('live'): {r['n_daily_live']}; event tags live: {r['n_event_live']}; the rest are reconstructed from backfilled bars)", "",
              "| Group | Cell | n | Mean net R | Verdict |", "|---|---|---:|---:|---|"]
        for c in r["cells"]:
            L.append(f"| {c['group']} | {c['cell']} | {c['n']} | {'' if c['mean_net_r'] is None else f'{c['mean_net_r']:+.2f}R'} | {c['verdict']} |")
        L.append("")
    return "\n".join(L)


def main(argv):
    cfg = load_cfg()
    run(cfg, recompute="--recompute" in argv)
    if "--early-read" in argv:
        res = early_read(cfg)
        md = early_read_md(res)
        open(os.path.join(HERE, "early_read.md"), "w").write(md + "\n")
        json.dump(res, open(os.path.join(HERE, "early_read.json"), "w"), indent=1)
        print(md)
    if True:
        t = today_words(cfg["tags_db"], cfg=cfg)
        if t:
            print(f"[morning_tags] latest 6AM tags ({t['session_date']}{', today' if t['is_today'] else ', not today yet'}): "
                  + "; ".join(f"{a}: {w} ({t['day_type'].get(a)} day)" for a, w in t["coins"].items()))


if __name__ == "__main__":
    main(sys.argv[1:])
