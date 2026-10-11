"""Trade processing (risk-monitor core): pending fills, exits, lockout, borrow integration, reserve skim.
Caller holds the writer lock and an open transaction."""
import json
from . import ledger, sim
from .util import iso, now_utc, from_ms, to_ms, parse_ts, toronto_dt, toronto_date, canon

MIN = 60_000


def primary(cfg, market):
    return cfg["markets"][market]["primary"]


def _bars_after(con, cfg, market, start_ms, now_dt):
    p = primary(cfg, market)
    rows = con.execute("SELECT candle_start_ms,open,high,low,close FROM market_data WHERE provider=? AND instrument=? AND timeframe='1m' AND derivation='native_1m' AND candle_start_ms>=? AND candle_end_ms<=? AND received_ts<=? ORDER BY candle_start_ms",
                       (p["provider"], p["symbol"], start_ms, to_ms(now_dt), iso(now_dt))).fetchall()
    return [dict(r) for r in rows]


def trade_costs(con, trade_id):
    return con.execute("SELECT component, amount_usd, status, phase FROM costs WHERE trade_id=?", (trade_id,)).fetchall()


def open_positions(con):
    return con.execute("SELECT * FROM trades WHERE status IN ('PENDING_FILL','OPEN','UNRESOLVED') ORDER BY commit_ts").fetchall()


def process_trades(con, cfg, run_id, now_dt, synthetic=0):
    ev_ids, notes = [], []
    f = cfg["fills"]
    for t in open_positions(con):
        t = dict(t)
        tid = t["trade_id"]
        sd = parse_ts(t["commit_ts"])
        noon_ms = to_ms(toronto_dt(toronto_date(sd), cfg["session"]["session_end"]))
        if t["status"] == "PENDING_FILL":
            commit_ms = to_ms(parse_ts(t["commit_ts"]))
            bars = _bars_after(con, cfg, t["market"], commit_ms, now_dt)
            b, px = sim.entry_fill(bars, commit_ms, f["latency_s"] * 1000, t["side"], f["slippage_bps"])
            exp_ms = to_ms(parse_ts(t["expires_ts"]))
            if b is None or b["candle_start_ms"] >= min(exp_ms, noon_ms):
                if to_ms(now_dt) >= min(exp_ms, noon_ms) or (b is not None):
                    eid, _ = ledger.add_event(con, tid, "EXPIRE", iso(from_ms(min(exp_ms, noon_ms))), run_id, amounts={"reason": "NOT_FILLED_BEFORE_NEXT_DECISION_CYCLE_OR_NOON"}, synthetic=synthetic)
                    con.execute("UPDATE trades SET status='EXPIRED', exit_reason='EXPIRED_UNFILLED' WHERE trade_id=?", (tid,))
                    _drop_uncharged_costs(con, tid)
                    ev_ids.append(eid)
                continue
            if not sim.valid_levels(t["side"], px, t["stop_price"]):
                eid, _ = ledger.add_event(con, tid, "CANCEL", iso(from_ms(b["candle_start_ms"])), run_id, price=px,
                                          amounts={"reason": "INVALID_STOP_TARGET_ORDER_AFTER_ENTRY", "stop": t["stop_price"]}, synthetic=synthetic)
                con.execute("UPDATE trades SET status='CANCELLED', exit_reason='INVALID_LEVELS_AFTER_ENTRY' WHERE trade_id=?", (tid,))
                _drop_uncharged_costs(con, tid)
                ev_ids.append(eid)
                continue
            tgt = sim.target_price(t["side"], px, t["stop_price"], t["target_r"])
            open_costs = sum(c[1] for c in trade_costs(con, tid) if c[3] == "open")
            eid, _ = ledger.add_event(con, tid, "OPEN", iso(from_ms(b["candle_start_ms"])), run_id, price=px,
                                      amounts={"notional_usd": t["notional_usd"], "collateral_usd": t["collateral_usd"], "leverage": t["leverage"],
                                               "stop": t["stop_price"], "target": tgt, "proxy_open": b["open"], "slippage_bps": f["slippage_bps"], "open_costs_usd": open_costs},
                                      trading_delta=-open_costs, evidence={"entry_bar_start": iso(from_ms(b["candle_start_ms"])), "rule": f["entry_rule"]}, synthetic=synthetic)
            con.execute("UPDATE trades SET status='OPEN', entry_ts=?, entry_price=?, target_price=?, last_processed_ms=?, proxy_entry_open=? WHERE trade_id=?",
                        (iso(from_ms(b["candle_start_ms"])), px, tgt, b["candle_start_ms"] - MIN, b["open"], tid))
            ev_ids.append(eid)
            t = dict(con.execute("SELECT * FROM trades WHERE trade_id=?", (tid,)).fetchone())
        # OPEN / UNRESOLVED
        start = t["last_processed_ms"] + MIN
        bars = _bars_after(con, cfg, t["market"], start, now_dt)
        day = ledger.ensure_day(con, toronto_date(sd), synthetic)
        lock_px = _lock_price(con, cfg, t, day)
        res = sim.run_exits(t["side"], t["stop_price"], t["target_price"], bars, start, f["slippage_bps"], noon_ms,
                            lock_px=lock_px, lock_pending=bool(day["locked"]))
        if res.get("lock_pending") and not day["locked"]:
            con.execute("UPDATE day_state SET locked=1, lock_ts=?, lock_reason=? WHERE session_date=?",
                        (iso(now_dt), "DAILY_LOSS_5PCT_BREACH_ON_BAR_CLOSE", day["session_date"]))
            eid, _ = ledger.add_event(con, None, "LOCKOUT", iso(now_dt), run_id, amounts={"session_date": day["session_date"], "trade_id": tid}, seq=ledger.next_seq(con, None, "LOCKOUT"), synthetic=synthetic)
            ev_ids.append(eid)
            notes.append(f"LOCKOUT breached on {tid}; flatten at next bar open")
        _store_excursions(con, "trades", "trade_id", t, bars, start, res)
        if res["status"] == "EXIT":
            ev_ids += close_trade(con, cfg, t, res, run_id, synthetic)
            if res["reason"] == "LOCKOUT_FLATTEN":
                notes.append(f"{tid} flattened by daily lockout")
        elif res["status"] == "UNRESOLVED":
            gap = f"{iso(from_ms(res['gap_from_ms']))}..{iso(from_ms(res['gap_to_ms']))}"
            if t["status"] != "UNRESOLVED":
                eid, _ = ledger.add_event(con, tid, "UNRESOLVED", iso(now_dt), run_id, amounts={"reason": res["reason"], "gap": gap}, seq=ledger.next_seq(con, tid, "UNRESOLVED"), synthetic=synthetic)
                ev_ids.append(eid)
            con.execute("UPDATE trades SET status='UNRESOLVED', last_processed_ms=COALESCE(?, last_processed_ms) WHERE trade_id=?", (res["last_processed_ms"], tid))
            notes.append(f"{tid} UNRESOLVED: missing 1m bars {gap}")
        else:
            if res["last_processed_ms"] is not None:
                con.execute("UPDATE trades SET status='OPEN', last_processed_ms=? WHERE trade_id=?", (res["last_processed_ms"], tid))
    return ev_ids, notes


def _processed_bars(bars, start, res):
    if res["status"] == "EXIT":
        return [b for b in bars if start <= b["candle_start_ms"] < res["exit_ms"]]
    lp = res.get("last_processed_ms")
    return [b for b in bars if lp is not None and start <= b["candle_start_ms"] <= lp]


def _store_excursions(con, table, key, t, bars, start, res):
    st = {"mae_px": t.get("mae_px"), "mae_ms": to_ms(parse_ts(t["mae_ts"])) if t.get("mae_ts") else None,
          "mfe_px": t.get("mfe_px"), "mfe_ms": to_ms(parse_ts(t["mfe_ts"])) if t.get("mfe_ts") else None}
    ex = res["status"] == "EXIT"
    st = sim.update_excursions(st, t["side"], t["notional_usd"], t["entry_price"], _processed_bars(bars, start, res),
                               res["price"] if ex else None, res["exit_ms"] if ex else None)
    if st.get("mae_px") is None:
        return
    R = t.get("initial_risk_usd")
    con.execute(f"UPDATE {table} SET mae_px=?, mae_ts=?, mfe_px=?, mfe_ts=?, mae_usd=?, mfe_usd=?, mae_r=?, mfe_r=? WHERE {key}=?",
                (st["mae_px"], iso(from_ms(st["mae_ms"])), st["mfe_px"], iso(from_ms(st["mfe_ms"])), st["mae_usd"], st["mfe_usd"],
                 st["mae_usd"] / R if R else None, st["mfe_usd"] / R if R else None, t[key]))


def _drop_uncharged_costs(con, tid):
    # Decision-time quote/estimate rows stay as evidence but are re-labelled not charged (phase suffix), never deleted.
    con.execute("UPDATE costs SET phase=phase||'_not_charged' WHERE trade_id=? AND phase IN ('open','close')", (tid,))


def _lock_price(con, cfg, t, day):
    """Price at which total equity change today reaches -5% of start trading equity (incl. est. close costs)."""
    s = ledger.saved(con)
    allowance = cfg["risk"]["daily_loss_lockout_pct"] / 100 * day["start_trading_equity"] + \
        ((s["trading_cash"] + s["reserve"]) - (day["start_trading_equity"] + day["start_reserve"]))
    close_est = sum(c[1] for c in trade_costs(con, t["trade_id"]) if c[3] == "close")
    allowance -= close_est
    n, e = t["notional_usd"], t["entry_price"]
    if allowance <= 0:
        return e * 10 if t["side"] == "long" else 0.0  # already breached -> any close triggers
    return e * (1 - allowance / n) if t["side"] == "long" else e * (1 + allowance / n)


def close_trade(con, cfg, t, res, run_id, synthetic=0):
    tid = t["trade_id"]
    exit_px = res["price"]
    exit_ms = res["exit_ms"]
    gross = sim.gross_pnl(t["side"], t["notional_usd"], t["entry_price"], exit_px)
    asset = cfg["markets"][t["market"]]["jupiter_asset"]
    snaps = [(to_ms(parse_ts(r[0])), r[1], r[2]) for r in con.execute("SELECT fetched_ts,long_hourly_pct,short_hourly_pct FROM borrow_snapshots WHERE asset=? ORDER BY fetched_ts", (asset,)).fetchall()]
    entry_ms = to_ms(parse_ts(t["entry_ts"]))
    borrow, intervals = sim.integrate_borrow(snaps, entry_ms, exit_ms, t["notional_usd"], t["side"])
    ids = []
    if borrow is None:
        borrow = 0.0
        flag = "NO_BORROW_SNAPSHOTS_BORROW_UNKNOWN"
    else:
        flag = None
    cid = f"CS-{tid}-borrow"
    con.execute("INSERT OR IGNORE INTO costs(cost_id,trade_id,decision_id,component,amount_usd,status,phase,source,interval_start,interval_end,evidence,synthetic) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (cid, tid, t["decision_id"], "borrow", borrow, "estimate", "hold", "integrated ./borrow snapshots (piecewise constant)", t["entry_ts"], iso(from_ms(exit_ms)),
                 canon({"intervals": intervals, "flag": flag}), synthetic))
    ids.append(cid)
    comps = trade_costs(con, tid)
    close_costs = sum(c[1] for c in comps if c[3] in ("close", "hold"))
    total_costs = sum(c[1] for c in comps if c[3] in ("open", "close", "hold"))
    net = gross - total_costs
    eid, new = ledger.add_event(con, tid, "CLOSE", iso(from_ms(exit_ms)), run_id, price=exit_px,
                                amounts={"reason": res["reason"], "gross_pnl": gross, "close_costs": close_costs, "total_costs": total_costs, "net_pnl": net,
                                         "ambiguous": res.get("ambiguous", False), "proxy_bar": res.get("bar")},
                                trading_delta=gross - close_costs, evidence={"fill_rule": cfg["fills"]}, synthetic=synthetic)
    ids.append(eid)
    if new and net > 0:
        skim = net * cfg["risk"]["winner_skim_pct_to_reserve"] / 100
        eid2, _ = ledger.add_event(con, tid, "RESERVE_TRANSFER", iso(from_ms(exit_ms)), run_id, amounts={"net_pnl": net, "skim_pct": cfg["risk"]["winner_skim_pct_to_reserve"], "amount": skim},
                                   trading_delta=-skim, reserve_delta=skim, evidence={"note": "internal transfer; not an expense or profit"}, synthetic=synthetic)
        ids.append(eid2)
    fees = sum(c[1] for c in comps if c[3] in ("open", "close"))
    slip_bps = cfg["fills"]["slippage_bps"]
    slippage = sim.entry_slippage_usd(t["notional_usd"], t["entry_price"], t["proxy_entry_open"] or t["entry_price"]) + \
        sim.exit_slippage_usd(t["side"], t["notional_usd"], t["entry_price"], exit_px, res["reason"], slip_bps)
    mults = cfg.get("measurement", {}).get("cost_multipliers", [1.0])
    sens = sim.cost_sensitivity(gross, fees, borrow, slippage, mults)
    R = t.get("initial_risk_usd")
    con.execute("UPDATE trades SET status='CLOSED', exit_ts=?, exit_price=?, exit_reason=?, ambiguous=?, last_processed_ms=?, gross_pnl=?, total_costs=?, net_pnl=?, net_r=?, fees_usd=?, financing_usd=?, slippage_usd=?, cost_sensitivity=? WHERE trade_id=?",
                (iso(from_ms(exit_ms)), exit_px, res["reason"], 1 if res.get("ambiguous") else 0, res["last_processed_ms"], gross, total_costs, net,
                 net / R if R else None, fees, borrow, slippage, canon(sens), tid))
    return ids


# ------------------------------------------------------------------ hypothetical (skipped-signal) outcomes
# Isolation: this code never calls ledger.add_event, never touches trades/costs/trade_events/ledger_state.

def process_hypotheticals(con, cfg, now_dt):
    f = cfg["fills"]
    done = []
    for h in con.execute("SELECT * FROM hypothetical_outcomes WHERE kind='SKIPPED_PROSPECTIVE' AND status IN ('PENDING_FILL','OPEN','UNRESOLVED')").fetchall():
        h = dict(h)
        hid = h["hyp_id"]
        sd = parse_ts(h["commit_ts"])
        noon_ms = to_ms(toronto_dt(toronto_date(sd), cfg["session"]["session_end"]))
        if h["status"] == "PENDING_FILL":
            commit_ms = to_ms(sd)
            bars = _bars_after(con, cfg, h["market"], commit_ms, now_dt)
            b, px = sim.entry_fill(bars, commit_ms, f["latency_s"] * 1000, h["side"], f["slippage_bps"])
            exp_ms = to_ms(parse_ts(h["expires_ts"]))
            if b is None or b["candle_start_ms"] >= min(exp_ms, noon_ms):
                if to_ms(now_dt) >= min(exp_ms, noon_ms) or b is not None:
                    con.execute("UPDATE hypothetical_outcomes SET status='EXPIRED', exit_reason='EXPIRED_UNFILLED' WHERE hyp_id=?", (hid,))
                    done.append(hid)
                continue
            if not sim.valid_levels(h["side"], px, h["stop_price"]):
                con.execute("UPDATE hypothetical_outcomes SET status='CANCELLED', exit_reason='INVALID_LEVELS_AFTER_ENTRY', entry_price=? WHERE hyp_id=?", (px, hid))
                done.append(hid)
                continue
            tgt = sim.target_price(h["side"], px, h["stop_price"], h["target_r"])
            con.execute("UPDATE hypothetical_outcomes SET status='OPEN', entry_ts=?, entry_price=?, proxy_entry_open=?, target_price=?, last_processed_ms=? WHERE hyp_id=?",
                        (iso(from_ms(b["candle_start_ms"])), px, b["open"], tgt, b["candle_start_ms"] - MIN, hid))
            h = dict(con.execute("SELECT * FROM hypothetical_outcomes WHERE hyp_id=?", (hid,)).fetchone())
        start = h["last_processed_ms"] + MIN
        bars = _bars_after(con, cfg, h["market"], start, now_dt)
        res = sim.run_exits(h["side"], h["stop_price"], h["target_price"], bars, start, f["slippage_bps"], noon_ms)
        _store_excursions(con, "hypothetical_outcomes", "hyp_id", h, bars, start, res)
        if res["status"] == "EXIT":
            fr = json.loads(h["cost_fractions"])
            n = h["notional_usd"]
            gross = sim.gross_pnl(h["side"], n, h["entry_price"], res["price"])
            fees = n * (fr["open_fee"] + fr["open_impact"] + fr["close_fee"] + fr["close_impact"]) + fr["net_open"] + fr["net_close"] + fr.get("conversion", 0)
            asset = cfg["markets"][h["market"]]["jupiter_asset"]
            snaps = [(to_ms(parse_ts(r[0])), r[1], r[2]) for r in con.execute("SELECT fetched_ts,long_hourly_pct,short_hourly_pct FROM borrow_snapshots WHERE asset=? ORDER BY fetched_ts", (asset,)).fetchall()]
            fin, _ = sim.integrate_borrow(snaps, to_ms(parse_ts(h["entry_ts"])), res["exit_ms"], n, h["side"])
            if fin is None:
                fin = n * fr.get("borrow_pct_h", 0) / 100 * (res["exit_ms"] - to_ms(parse_ts(h["entry_ts"]))) / 3_600_000
            slip = sim.entry_slippage_usd(n, h["entry_price"], h["proxy_entry_open"]) + sim.exit_slippage_usd(h["side"], n, h["entry_price"], res["price"], res["reason"], f["slippage_bps"])
            net = gross - fees - fin
            sens = sim.cost_sensitivity(gross, fees, fin, slip, cfg["measurement"]["cost_multipliers"])
            R = h["initial_risk_usd"]
            con.execute("UPDATE hypothetical_outcomes SET status='CLOSED', exit_ts=?, exit_price=?, exit_reason=?, ambiguous=?, last_processed_ms=?, gross_pnl=?, fees_usd=?, financing_usd=?, slippage_usd=?, net_pnl=?, net_r=?, cost_sensitivity=? WHERE hyp_id=?",
                        (iso(from_ms(res["exit_ms"])), res["price"], res["reason"], 1 if res["ambiguous"] else 0, res["last_processed_ms"], gross, fees, fin, slip, net, net / R if R else None, canon(sens), hid))
            done.append(hid)
        elif res["status"] == "UNRESOLVED":
            con.execute("UPDATE hypothetical_outcomes SET status='UNRESOLVED', last_processed_ms=COALESCE(?, last_processed_ms) WHERE hyp_id=?", (res["last_processed_ms"], hid))
        elif res["last_processed_ms"] is not None:
            con.execute("UPDATE hypothetical_outcomes SET status='OPEN', last_processed_ms=? WHERE hyp_id=?", (res["last_processed_ms"], hid))
    return done


def open_hypotheticals(con):
    return con.execute("SELECT COUNT(*) FROM hypothetical_outcomes WHERE status IN ('PENDING_FILL','OPEN','UNRESOLVED')").fetchone()[0]
