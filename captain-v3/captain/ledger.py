"""Event-sourced paper ledger. trading_cash and reserve are derived from trade_events; ledger_state is the
saved balance and must reconcile to the event sum. Internal reserve transfers cancel in total equity."""
from .util import iso, now_utc, canon


def balances_from_events(con, synthetic=None):
    q = "SELECT COALESCE(SUM(trading_cash_delta),0), COALESCE(SUM(reserve_delta),0) FROM trade_events"
    tc, rs = con.execute(q).fetchone()
    return tc, rs


def saved(con):
    r = con.execute("SELECT trading_cash, reserve, last_event_id FROM ledger_state WHERE id=1").fetchone()
    return {"trading_cash": r[0], "reserve": r[1], "last_event_id": r[2]}


def reconcile(con, initial):
    tc, rs = balances_from_events(con)
    s = saved(con)
    rebuilt_tc = initial + tc
    return {"rebuilt_trading_cash": rebuilt_tc, "rebuilt_reserve": rs, "saved_trading_cash": s["trading_cash"], "saved_reserve": s["reserve"],
            "diff_usd": round((rebuilt_tc + rs) - (s["trading_cash"] + s["reserve"]), 10),
            "diff_trading": round(rebuilt_tc - s["trading_cash"], 10), "diff_reserve": round(rs - s["reserve"], 10)}


def next_seq(con, trade_id, event_type):
    r = con.execute("SELECT COALESCE(MAX(seq),0) FROM trade_events WHERE trade_id IS ? AND event_type=?", (trade_id, event_type)).fetchone()
    return r[0] + 1


def add_event(con, trade_id, event_type, event_ts, run_id, price=None, amounts=None, trading_delta=0.0, reserve_delta=0.0,
              evidence=None, seq=1, synthetic=0, supersedes=None):
    """Insert an event (idempotent by trade_id+type+seq) and update saved balances in the same transaction."""
    eid = f"EV-{trade_id or 'BOOK'}-{event_type}-{seq}"
    cur = con.execute("INSERT OR IGNORE INTO trade_events(event_id,trade_id,seq,event_type,event_ts,recorded_ts,price,amounts,trading_cash_delta,reserve_delta,evidence,run_id,supersedes,synthetic) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (eid, trade_id, seq, event_type, event_ts, iso(now_utc()), price, canon(amounts or {}), trading_delta, reserve_delta, canon(evidence or {}), run_id, supersedes, synthetic))
    if cur.rowcount:
        con.execute("UPDATE ledger_state SET trading_cash=trading_cash+?, reserve=reserve+?, updated_ts=?, last_event_id=? WHERE id=1",
                    (trading_delta, reserve_delta, iso(now_utc()), eid))
    return eid, bool(cur.rowcount)


def ensure_day(con, session_date, synthetic=0):
    r = con.execute("SELECT * FROM day_state WHERE session_date=?", (str(session_date),)).fetchone()
    if r:
        return dict(r)
    s = saved(con)
    # Start-of-day trading equity = trading cash (no open positions are carried overnight: intraday only).
    con.execute("INSERT INTO day_state(session_date,start_trading_equity,start_reserve,created_ts,synthetic) VALUES(?,?,?,?,?)",
                (str(session_date), s["trading_cash"], s["reserve"], iso(now_utc()), synthetic))
    return dict(con.execute("SELECT * FROM day_state WHERE session_date=?", (str(session_date),)).fetchone())
