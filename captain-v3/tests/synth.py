"""SYNTHETIC TEST DATA ONLY. Every row is written with synthetic=1 into a throwaway temp DB/home.
Never used for performance or forecasts (eligible_sessions and summaries filter synthetic=0)."""
import datetime as dt, math, os, tempfile
from captain import db, config
from captain.util import toronto_dt, to_ms, iso, from_ms

MIN = 60_000


def fresh_env():
    d = tempfile.mkdtemp(prefix="captain-test-")
    os.environ["CAPTAIN_HOME"] = d
    os.environ["CAPTAIN_DB"] = os.path.join(d, "test.db")
    os.environ["CAPTAIN_NO_NETWORK"] = "1"
    os.environ["CAPTAIN_OFFLINE_COSTS"] = "1"
    os.environ.pop("CAPTAIN_FAKE_NOW", None)
    cfg = config.load()
    con = db.connect()
    db.init(con, cfg["risk"]["initial_paper_capital_usd"])
    return d, cfg, con


def insert_1m(con, provider, symbol, rows, synthetic=1, received_lag_s=1):
    """rows: list of (start_ms, o, h, l, c)."""
    with db.tx(con):
        for s, o, h, l, c in rows:
            con.execute("INSERT OR IGNORE INTO market_data(provider,instrument,timeframe,derivation,candle_start_ms,candle_end_ms,open,high,low,close,volume,received_ts,is_final,raw_ref,synthetic) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,'SYNTHETIC',?)",
                        (provider, symbol, "1m", "native_1m", s, s + MIN, o, h, l, c, 1.0, iso(from_ms(s + MIN + received_lag_s * 1000)), synthetic))


def path_rows(start_ms, prices, wick=0.02):
    rows = []
    prev = prices[0]
    for i, c in enumerate(prices):
        o = prev
        rows.append((start_ms + i * MIN, o, max(o, c) + wick, min(o, c) - wick, c))
        prev = c
    return rows


def build_session(con, cfg, session_date, markets=("BTC", "ETH", "SOL"), post_prices=None, breakout=True, hours_before=160, end_local="12:05", secondary=True):
    """Rising trend -> flat overnight near 100 -> 06:00-06:15 bar breaks above overnight high (setup A long)."""
    on_start = toronto_dt(session_date, "00:00")
    s06 = toronto_dt(session_date, "06:00")
    start = on_start - dt.timedelta(hours=hours_before)
    end = toronto_dt(session_date, end_local)
    n_pre = int((on_start - start).total_seconds() // 60)
    n_on = int((s06 - on_start).total_seconds() // 60)
    prices = [90 + 10 * i / n_pre for i in range(n_pre)]
    prices += [100 + 0.03 * math.sin(i / 3) for i in range(n_on)]
    if breakout:
        prices += [100 + 1.5 * (i + 1) / 15 for i in range(15)]
    else:
        prices += [100 + 0.03 * math.sin(i / 3) for i in range(15)]
    n_post = int((end - s06).total_seconds() // 60) - 15
    post = post_prices or []
    post = (post + [post[-1] if post else prices[-1]] * n_post)[:n_post]
    prices += post
    rows = path_rows(to_ms(start), prices)
    for m in markets:
        p, s = cfg["markets"][m]["primary"], cfg["markets"][m]["secondary"]
        insert_1m(con, p["provider"], p["symbol"], rows)
        if secondary:
            insert_1m(con, s["provider"], s["symbol"], rows)
    from captain import collector
    with db.tx(con):
        for m in markets:
            p = cfg["markets"][m]["primary"]
            collector.aggregate(con, p["provider"], p["symbol"], 15, since_ms=to_ms(start), synthetic=1)
            collector.aggregate(con, p["provider"], p["symbol"], 60, since_ms=to_ms(start), synthetic=1)
    return {"start": start, "s06": s06, "rows": rows}


def synthetic_quote(asset, side, collateral, leverage, open_fee_bps=6, impact_bps=2, net_usd=0.002, conv=0.0):
    size = collateral * leverage
    return {"requested": {"tool": "SYNTHETIC", "args": [asset, side, collateral, leverage]}, "quoted_ts": "SYNTHETIC", "exit_code": 0, "stderr": "",
            "response": {"SYNTHETIC": True, "entryPriceUsd": 0.0, "positionSizeUsd": size, "inputToCollateralDiffUsd": conv,
                         "fees": {"openFeeUsd": size * open_fee_bps / 1e4, "openPriceImpactFeeUsd": size * impact_bps / 1e4,
                                  "closeFee": {"baseFeeUsd": size * 6 / 1e4, "priceImpactFeeUsd_assumed": size * impact_bps / 1e4, "method": "SYNTHETIC"},
                                  "borrow": {"hourlyRatePct": 0.0015}, "network": {"transactionFeeUsd": net_usd}}}}
