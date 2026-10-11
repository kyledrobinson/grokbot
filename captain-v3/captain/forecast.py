"""Morning forecast baselines and multiclass Brier scoring (spec section 7)."""
import datetime as dt
from .util import TZ, UTC, from_ms, to_ms, toronto_dt, iso

CLASSES = ["UP", "DOWN", "RANGE"]


def classify(ret, thr_pct):
    if ret > thr_pct / 100:
        return "UP"
    if ret < -thr_pct / 100:
        return "DOWN"
    return "RANGE"


def eligible_sessions(con, provider, symbol, thr_pct, before_date=None):
    """Sessions (Toronto date) where all six native 1h primary bars 06:00..11:00 local exist.
    Return = close(11:00 bar) / open(06:00 bar) - 1 (identical to the 1m definition on the same provider)."""
    rows = con.execute("SELECT candle_start_ms, open, close FROM market_data WHERE provider=? AND instrument=? AND timeframe='1h' AND derivation='native_1h' AND synthetic=0 ORDER BY candle_start_ms",
                       (provider, symbol)).fetchall()
    by_day = {}
    for s, o, c in rows:
        loc = from_ms(s).astimezone(TZ)
        if 6 <= loc.hour <= 11 and loc.minute == 0:
            by_day.setdefault(loc.date(), {})[loc.hour] = (s, o, c)
    out = []
    for d in sorted(by_day):
        if before_date and d >= before_date:
            continue
        h = by_day[d]
        if all(k in h for k in range(6, 12)) and h[6][0] == to_ms(toronto_dt(d, "06:00")):
            r = h[11][2] / h[6][1] - 1
            out.append({"date": d, "ret": r, "cls": classify(r, thr_pct)})
    return out


def freq_probs(sessions, alpha):
    n = {c: 0 for c in CLASSES}
    for s in sessions:
        n[s["cls"]] += 1
    tot = len(sessions) + alpha * len(CLASSES)
    p = {c: (n[c] + alpha) / tot for c in CLASSES}
    p["RANGE"] = 1.0 - p["UP"] - p["DOWN"]
    return p, n


def baselines(sessions, cfg):
    fc = cfg["forecast"]
    out = {}
    om = fc["official_model"]
    win = sessions[-om["window_sessions"]:]
    if win:
        p, n = freq_probs(win, om["laplace_alpha"])
        out[om["id"]] = {"probs": p, "counts": n, "sample_count": len(win), "first": str(win[0]["date"]), "last": str(win[-1]["date"]),
                         "smoothing": f"Laplace add-{om['laplace_alpha']} per class over last {om['window_sessions']} eligible sessions", "official": 1}
    for m in fc["comparison_models"]:
        if m["id"] == "freq_expanding_laplace1" and sessions:
            p, n = freq_probs(sessions, m["laplace_alpha"])
            out[m["id"]] = {"probs": p, "counts": n, "sample_count": len(sessions), "first": str(sessions[0]["date"]), "last": str(sessions[-1]["date"]),
                            "smoothing": f"Laplace add-{m['laplace_alpha']} per class, expanding history", "official": 0}
        if m["id"] == "prior_session_rule_onehot" and sessions:
            last = sessions[-1]
            p = {c: 1.0 if c == last["cls"] else 0.0 for c in CLASSES}
            out[m["id"]] = {"probs": p, "counts": None, "sample_count": 1, "first": str(last["date"]), "last": str(last["date"]),
                            "smoothing": "none: preregistered rule 'same class as prior eligible session', one-hot probabilities", "official": 0}
    return out


def brier(probs, outcome):
    return sum((probs[c] - (1.0 if c == outcome else 0.0)) ** 2 for c in CLASSES)


def reference_prices(con, cfg, market, session_date, cutoff_ts):
    """06:00 open and 12:00 (close of 11:59 bar) from primary 1m; None with reason if missing."""
    p = cfg["markets"][market]["primary"]
    s = to_ms(toronto_dt(session_date, "06:00"))
    e = to_ms(toronto_dt(session_date, "12:00"))
    a = con.execute("SELECT open, received_ts, raw_ref FROM market_data WHERE provider=? AND instrument=? AND timeframe='1m' AND derivation='native_1m' AND candle_start_ms=? AND received_ts<=?",
                    (p["provider"], p["symbol"], s, cutoff_ts)).fetchone()
    b = con.execute("SELECT close, received_ts, raw_ref FROM market_data WHERE provider=? AND instrument=? AND timeframe='1m' AND derivation='native_1m' AND candle_start_ms=? AND received_ts<=?",
                    (p["provider"], p["symbol"], e - 60_000, cutoff_ts)).fetchone()
    if not a or not b:
        return None, ("MISSING_06:00_REFERENCE" if not a else "MISSING_12:00_REFERENCE")
    return {"start": a[0], "end": b[0], "start_ref": {"candle_start": iso(from_ms(s)), "raw_ref": a[2], "received_ts": a[1]},
            "end_ref": {"candle_start": iso(from_ms(e - 60_000)), "raw_ref": b[2], "received_ts": b[1]}}, None
