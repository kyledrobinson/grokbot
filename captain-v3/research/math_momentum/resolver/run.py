"""Resolve stored math-momentum shadow forecasts whose horizon has passed.

Lives in a subpackage so the shadow runner's code_hash (top-level *.py only) is unchanged.
Reads captain.db read-only. Only fills outcome/outcome_return/resolved_ts on rows where outcome IS NULL;
never edits probabilities, EVs, records, or any other column. Never touches Captain v3 tables.
Outcome definitions follow config/math-momentum-v1.0.1.json (primary provider binance_spot, native 1m closes):
  15m: r = ln(close@target_end / close@cutoff); UP if r > +0.25%, DOWN if r < -0.25%, else RANGE.
  session_close: r = close@target_end (12:00 Toronto) / close@last completed hour <= cutoff - 1; +/-0.5%.
Session forecasts whose target_end <= cutoff (a bug in the first v1.0.0 06:00 run) are left unresolved and reported as INVALID.
"""
import argparse, datetime as dt, json, math, os, sqlite3

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(HERE))
SYM = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}
H1 = 3600000
BAND = {"15m": 0.0025, "session_close": 0.005}


def ms(s):
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)


def close_at(con, sym, end_ms):
    r = con.execute("SELECT close FROM market_data WHERE provider='binance_spot' AND instrument=? AND timeframe='1m' "
                    "AND derivation='native_1m' AND candle_end_ms=? AND received_ts IS NOT NULL", (sym, end_ms)).fetchone()
    return float(r[0]) if r else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "captain.db"))
    ap.add_argument("--shadow", default=os.path.join(HERE, "shadow.db"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    sh = sqlite3.connect(a.shadow)
    now = dt.datetime.now(dt.timezone.utc); now_ms = int(now.timestamp() * 1000)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    res = {"resolved_now": 0, "pending_horizon": 0, "missing_bar": 0, "invalid_target": []}
    rows = sh.execute("SELECT forecast_id, market, horizon, cutoff_ts, target_end_ts FROM forecasts WHERE outcome IS NULL").fetchall()
    for fid, m, hz, c_ts, t_ts in rows:
        c_ms, t_ms = ms(c_ts), ms(t_ts)
        if t_ms <= c_ms:
            res["invalid_target"].append(fid); continue
        if t_ms > now_ms:
            res["pending_horizon"] += 1; continue
        base_ms = c_ms if hz == "15m" else (c_ms // H1) * H1
        c0, c1 = close_at(con, SYM[m], base_ms), close_at(con, SYM[m], t_ms)
        if c0 is None or c1 is None:
            res["missing_bar"] += 1; continue
        r = math.log(c1 / c0) if hz == "15m" else c1 / c0 - 1
        b = BAND[hz]
        out = "UP" if r > b else "DOWN" if r < -b else "RANGE"
        if not a.dry_run:
            sh.execute("UPDATE forecasts SET outcome=?, outcome_return=?, resolved_ts=? WHERE forecast_id=? AND outcome IS NULL",
                       (out, r, now_iso, fid))
        res["resolved_now"] += 1
    if not a.dry_run:
        sh.commit()
    tally = {}
    for m in SYM:
        n15 = sh.execute("SELECT COUNT(*) FROM forecasts WHERE market=? AND horizon='15m' AND outcome IS NOT NULL", (m,)).fetchone()[0]
        ses = sh.execute("SELECT COUNT(DISTINCT substr(cutoff_ts,1,10)) FROM forecasts WHERE market=? AND outcome IS NOT NULL", (m,)).fetchone()[0]
        nsc = sh.execute("SELECT COUNT(*) FROM forecasts WHERE market=? AND horizon='session_close' AND outcome IS NOT NULL", (m,)).fetchone()[0]
        # Brier on resolved 15m
        br = sh.execute("SELECT p_up,p_range,p_down,outcome FROM forecasts WHERE market=? AND horizon='15m' AND outcome IS NOT NULL AND p_up IS NOT NULL AND p_range IS NOT NULL AND p_down IS NOT NULL", (m,)).fetchall()
        brier = None
        if br:
            tot = 0.0
            for pu, pr, pd, o in br:
                y = {"UP": (1, 0, 0), "RANGE": (0, 1, 0), "DOWN": (0, 0, 1)}[o]
                tot += (pu - y[0]) ** 2 + (pr - y[1]) ** 2 + (pd - y[2]) ** 2
            brier = tot / len(br)
        oc = dict(sh.execute("SELECT outcome,COUNT(*) FROM forecasts WHERE market=? AND horizon='15m' AND outcome IS NOT NULL GROUP BY outcome", (m,)).fetchall())
        tally[m] = {"resolved_15m": n15, "gate_250": f"{n15}/250", "resolved_session_close": nsc,
                    "session_dates": ses, "gate_60": f"{ses}/60", "brier_15m": brier, "outcomes_15m": oc}
    res["invalid_target_count"] = len(res["invalid_target"])
    res["tally"] = tally
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
