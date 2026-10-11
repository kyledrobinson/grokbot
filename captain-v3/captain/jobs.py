"""Scheduled jobs. Each job: gather inputs (network) -> one atomic write transaction that also marks the run
COMMITTED and queues deliveries -> runs.finalize verifies and emits the receipt."""
import datetime as dt, json, os, shutil, time
from . import collector, costs as costmod, forecast as fc, ledger, risk, signals, trades, export
from .db import tx, writer_lock
from .runs import JobFailed
from .util import iso, now_utc, et, from_ms, to_ms, parse_ts, toronto_dt, toronto_date, canon, sha256_text, code_version, ROOT, home, TZ

MIN = 60_000
OFFLINE = lambda: bool(os.environ.get("CAPTAIN_NO_NETWORK"))


def _collect(ctx, wait_for_end_ms=None, deadline_s=75):
    if OFFLINE():
        return {"offline": True}
    t0 = time.time()
    while True:
        s = collector.collect(ctx.con, ctx.cfg)
        if wait_for_end_ms is None:
            return s
        ok = all(ctx.con.execute("SELECT COUNT(*) FROM market_data WHERE provider=? AND instrument=? AND timeframe='1m' AND derivation='native_1m' AND candle_start_ms>=? AND candle_end_ms<=?",
                                 (ctx.cfg["markets"][m]["primary"]["provider"], ctx.cfg["markets"][m]["primary"]["symbol"], wait_for_end_ms - 15 * MIN, wait_for_end_ms)).fetchone()[0] == 15
                 for m in ctx.cfg["market_order"])
        if ok or time.time() - t0 > deadline_s:
            return s
        time.sleep(5)


def _borrow_snapshot(ctx, force=False):
    """Fetch ./borrow if any position exists (or forced) and the last snapshot is >= 14 min old."""
    con = ctx.con
    if not force and not trades.open_positions(con):
        return None
    last = con.execute("SELECT MAX(fetched_ts) FROM borrow_snapshots").fetchone()[0]
    if not force and last and (now_utc() - parse_ts(last)).total_seconds() < 14 * 60:
        return None
    if os.environ.get("CAPTAIN_OFFLINE_COSTS"):
        return None
    b = costmod.borrow(ctx.cfg)
    if b["exit_code"] != 0 or not b["response"]:
        ctx.notes.append(f"borrow fetch failed: {b['stderr'][:200]}")
        return None
    return b


def _store_borrow(con, ctx, b):
    if not b:
        return []
    ids = []
    for a, r in b["response"]["assets"].items():
        cur = con.execute("INSERT INTO borrow_snapshots(fetched_ts,asset,long_hourly_pct,short_hourly_pct,source,run_id,raw,synthetic) VALUES(?,?,?,?,?,?,?,?)",
                          (b["response"]["fetchedAt"].replace("Z", "Z"), a, r["longHourlyBorrowPct"], r["shortHourlyBorrowPct"], b["response"]["source"], ctx.run_id, canon(r), ctx.synthetic))
        ids.append(cur.lastrowid)
    return ids


# ---------------------------------------------------------------- collect
def job_collect(ctx):
    s = _collect(ctx)
    with writer_lock(), tx(ctx.con):
        ctx.commit_writes({"market_data_summary": s}, data_cutoff=now_utc())


# ---------------------------------------------------------------- audit
def job_audit(ctx):
    con, cfg = ctx.con, ctx.cfg
    s = _collect(ctx)
    now = now_utc()
    res = {"collect": s}
    res["integrity_check"] = con.execute("PRAGMA integrity_check").fetchone()[0]
    res["journal_mode"] = con.execute("PRAGMA journal_mode").fetchone()[0]
    res["counts"] = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in
                     ("runs", "market_data", "snapshots", "forecasts", "signals", "decisions", "trades", "trade_events", "costs", "scores", "experiments", "deliveries")}
    cov = {}
    for m in cfg["market_order"]:
        for role in ("primary", "secondary"):
            p = cfg["markets"][m][role]
            r = con.execute("SELECT COUNT(*), MIN(candle_start_ms), MAX(candle_end_ms) FROM market_data WHERE provider=? AND instrument=? AND timeframe='1m' AND derivation='native_1m'", (p["provider"], p["symbol"])).fetchone()
            since = to_ms(now) - 24 * 60 * MIN
            n24 = con.execute("SELECT COUNT(*) FROM market_data WHERE provider=? AND instrument=? AND timeframe='1m' AND derivation='native_1m' AND candle_start_ms>=?", (p["provider"], p["symbol"], since)).fetchone()[0]
            cov[f"{m}/{role}/{p['provider']}:{p['symbol']}"] = {"rows_1m": r[0], "first": iso(from_ms(r[1])) if r[1] else None, "last_end": iso(from_ms(r[2])) if r[2] else None,
                                                               "age_s": (to_ms(now) - r[2]) / 1000 if r[2] else None, "last24h_present": n24, "last24h_expected": 1440}
    res["coverage"] = cov
    hb = os.path.join(home(), "state", "scheduler-heartbeat.json")
    res["scheduler"] = json.load(open(hb)) if os.path.exists(hb) else {"status": "NO_HEARTBEAT_FILE"}
    if "ts" in res["scheduler"]:
        res["scheduler"]["heartbeat_age_s"] = (now - parse_ts(res["scheduler"]["ts"])).total_seconds()
    res["reconciliation"] = ledger.reconcile(con, cfg["risk"]["initial_paper_capital_usd"])
    res["open_positions"] = [r["trade_id"] for r in trades.open_positions(con)]
    res["last_runs"] = {r[0]: {"status": r[1], "finished": r[2]} for r in con.execute("SELECT job, status, MAX(finished_ts) FROM runs GROUP BY job").fetchall()}
    res["backups"] = sorted(os.listdir(os.path.join(home(), "backups")))[-3:] if os.path.isdir(os.path.join(home(), "backups")) else []
    res["code_version"] = code_version()
    res["config"] = {"path": cfg["_path"], "hash": cfg["_hash"]}
    res["quote_tool_present"] = os.path.exists(cfg["costs"]["quote_tool"])
    qc = None
    if not os.environ.get("CAPTAIN_OFFLINE_COSTS"):
        # read-only adapter health check: small SOL long quote (unsigned tx is dropped by the tool)
        qc = costmod.quote(cfg, "SOL", "long", 12.0, 2.0, 1.0)
        if qc["exit_code"] == 0 and qc["response"]:
            try:
                fr = risk.cost_fractions_from_quote(qc["response"])
                res["quote_check"] = {"ok": True, "positionSizeUsd": qc["response"]["positionSizeUsd"], "open_fee_bps": round(fr["open_fee"] * 1e4, 3),
                                      "impact_bps": round(fr["open_impact"] * 1e4, 3), "close_fee_bps_est": round(fr["close_fee"] * 1e4, 3), "network_usd": fr["net_open"],
                                      "borrow_pct_h": qc["response"]["fees"]["borrow"]["hourlyRatePct"], "components": [c[:3] for c in costmod.quote_cost_components(qc["response"])]}
            except Exception as e:
                res["quote_check"] = {"ok": False, "error": repr(e)}
        else:
            res["quote_check"] = {"ok": False, "exit_code": qc["exit_code"], "stderr": qc["stderr"][-300:]}
    res["disk_free_gb"] = round(shutil.disk_usage(ROOT).free / 1e9, 1)
    problems = []
    if res["integrity_check"] != "ok": problems.append("DB_INTEGRITY")
    if abs(res["reconciliation"]["diff_usd"]) > 1e-6: problems.append("LEDGER_RECONCILIATION")
    for k, v in cov.items():
        if v["age_s"] is None or v["age_s"] > 180: problems.append(f"STALE:{k}")
    if res["scheduler"].get("heartbeat_age_s", 1e9) > 180: problems.append("SCHEDULER_HEARTBEAT_STALE")
    if qc is not None and not res.get("quote_check", {}).get("ok"): problems.append("QUOTE_ADAPTER_FAILED")
    res["status"] = "HEALTHY" if not problems else "DEGRADED"
    res["problems"] = problems
    sid = f"SN-{ctx.run_id}-audit"
    with writer_lock(), tx(con):
        ledger.ensure_day(con, toronto_date(ctx.scheduled_dt), ctx.synthetic)
        con.execute("INSERT OR REPLACE INTO snapshots(snapshot_id,run_id,market,cutoff_ts,created_ts,freshness,features,calc_versions,features_hash,synthetic) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (sid, ctx.run_id, None, iso(now), iso(now), canon(cov), canon(res), canon({"audit": "v1"}), sha256_text(canon(res)), ctx.synthetic))
        if qc is not None:
            con.execute("INSERT OR IGNORE INTO quotes(quote_id,decision_ref,run_id,requested,response,stderr,exit_code,quoted_ts,synthetic) VALUES(?,?,?,?,?,?,?,?,?)",
                        (f"QT-{ctx.run_id}-audit", "AUDIT_HEALTH_CHECK", ctx.run_id, canon(qc["requested"]), canon(qc["response"]), qc["stderr"][-1000:], qc["exit_code"], qc["quoted_ts"], ctx.synthetic))
        ctx.notes.append(f"audit status {res['status']} problems={problems}")
        ctx.commit_writes({"snapshots": [sid]}, data_cutoff=now, data_quality={"status": res["status"], "problems": problems})
    return res


# ---------------------------------------------------------------- forecast
def target_session(cutoff):
    loc = cutoff.astimezone(TZ)
    d = loc.date()
    return d if loc.hour < 6 else d + dt.timedelta(days=1)


def job_forecast(ctx, session_date=None):
    con, cfg = ctx.con, ctx.cfg
    if not OFFLINE():
        collector.backfill_native_1h(con, cfg)
    _collect(ctx)
    cutoff = now_utc()
    sd = session_date or target_session(cutoff)
    t_start = toronto_dt(sd, cfg["session"]["session_start"])
    t_end = toronto_dt(sd, cfg["session"]["session_end"])
    if cutoff >= t_start:
        raise JobFailed(f"cutoff {iso(cutoff)} is not before target start {iso(t_start)}: refusing to create a non-forward forecast")
    fcfg = cfg["forecast"]
    snaps, fids, sids, problems = [], [], [], []
    rows = []
    for m in cfg["market_order"]:
        p = cfg["markets"][m]["primary"]
        fr = collector.freshness(con, cfg, m, cutoff)
        if not fr["gates"]["latest_price_fresh"]["pass"]:
            problems.append(f"{m}:STALE_PRIMARY")
        sess = fc.eligible_sessions(con, p["provider"], p["symbol"], fcfg["threshold_pct"], before_date=sd)
        if len(sess) < 30:
            problems.append(f"{m}:INSUFFICIENT_HISTORY({len(sess)})")
        partial = signals.overnight_levels(con, cfg, m, sd, cutoff, through_dt=cutoff) if cutoff > toronto_dt(sd, "00:00") else {"label": "overnight window not started at cutoff"}
        rows.append((m, fr, sess, partial))
    if problems:
        raise JobFailed("prerequisites failed, no official forecast: " + ", ".join(problems))
    # score prior forecasts with complete reference data
    score_ids = _score_due(con, cfg, ctx, cutoff, write=False)
    with writer_lock(), tx(con):
        for m, fr, sess, partial in rows:
            p = cfg["markets"][m]["primary"]
            sid = f"SN-{ctx.run_id}-{m}"
            feats = {"session_date": str(sd), "overnight_through_cutoff": partial, "eligible_sessions": len(sess),
                     "history_first": str(sess[0]["date"]), "history_last": str(sess[-1]["date"]), "latest_primary": fr.get("latest_primary")}
            con.execute("INSERT OR REPLACE INTO snapshots(snapshot_id,run_id,market,cutoff_ts,created_ts,freshness,features,calc_versions,features_hash,synthetic) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (sid, ctx.run_id, m, iso(cutoff), iso(now_utc()), canon(fr), canon(feats), canon({"forecast": fcfg["model_version"]}), sha256_text(canon(feats)), ctx.synthetic))
            sids.append(sid)
            for model_id, b in fc.baselines(sess, cfg).items():
                fid = f"FC-{sd.strftime('%Y%m%d')}-{m}-{model_id}-{fcfg['model_version']}"
                exists = con.execute("SELECT forecast_id, created_ts FROM forecasts WHERE session_date=? AND market=? AND model_id=? AND model_version=?", (str(sd), m, model_id, fcfg["model_version"])).fetchone()
                if exists:
                    ctx.notes.append(f"{exists[0]} already committed at {exists[1]}; retained unchanged (no overwrite)")
                    continue
                pr = b["probs"]
                assert abs(sum(pr.values()) - 1) < 1e-12
                con.execute("INSERT INTO forecasts(forecast_id,run_id,market,model_id,model_version,is_official,created_ts,cutoff_ts,session_date,target_start_ts,target_end_ts,outcome_definition,p_up,p_down,p_range,probabilities_available,sample_count,sample_first_date,sample_last_date,smoothing,evidence,snapshot_id,synthetic) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?,?,?,?,?)",
                            (fid, ctx.run_id, m, model_id, fcfg["model_version"], b["official"], iso(now_utc()), iso(cutoff), str(sd), iso(t_start), iso(t_end), fcfg["definition"],
                             pr["UP"], pr["DOWN"], pr["RANGE"], b["sample_count"], b["first"], b["last"], b["smoothing"],
                             canon({"class_counts": b["counts"], "source": f"{p['provider']}:{p['symbol']} native_1h", "snapshot": sid}), sid, ctx.synthetic))
                fids.append(fid)
        score_ids = _score_due(con, cfg, ctx, cutoff, write=True)
        ctx.commit_writes({"forecasts": fids, "snapshots": sids, "scores": score_ids}, data_cutoff=cutoff,
                          data_quality={m: {"latest_age_s": fr.get("latest_primary", {}).get("age_s"), "provider_diff_pct": fr["gates"].get("provider_agreement", {}).get("diff_pct")} for m, fr, _, _ in rows},
                          deliveries=[("kyle-chat:not-configured", {"forecasts": fids})])
        con.execute("UPDATE deliveries SET status='not_configured', error='no authorized external channel; view exports/DB' WHERE run_id=? AND destination LIKE 'kyle-chat%'", (ctx.run_id,))


def _score_due(con, cfg, ctx, cutoff, write):
    ids = []
    rows = con.execute("SELECT f.* FROM forecasts f LEFT JOIN scores s ON s.forecast_id=f.forecast_id AND s.kind='session_forecast' WHERE (s.score_id IS NULL OR s.status='UNSCORED') AND f.target_end_ts<=?", (iso(cutoff),)).fetchall()
    for f in rows:
        sd = dt.date.fromisoformat(f["session_date"])
        refs, why = fc.reference_prices(con, cfg, f["market"], sd, iso(cutoff))
        sid = f"SC-{f['forecast_id']}"
        if not write:
            ids.append(sid)
            continue
        if refs is None:
            con.execute("INSERT OR REPLACE INTO scores(score_id,kind,forecast_id,status,scored_ts,exclusion_reason,run_id,synthetic) VALUES(?,?,?,?,?,?,?,?)",
                        (sid, "session_forecast", f["forecast_id"], "UNSCORED", iso(now_utc()), why, ctx.run_id, f["synthetic"]))
        else:
            r = refs["end"] / refs["start"] - 1
            outcome = fc.classify(r, cfg["forecast"]["threshold_pct"])
            probs = {"UP": f["p_up"], "DOWN": f["p_down"], "RANGE": f["p_range"]}
            b = fc.brier(probs, outcome)
            con.execute("INSERT OR REPLACE INTO scores(score_id,kind,forecast_id,status,outcome,ref_start_price,ref_end_price,return_pct,brier,scored_ts,data_refs,run_id,synthetic) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (sid, "session_forecast", f["forecast_id"], "SCORED", outcome, refs["start"], refs["end"], r * 100, b, iso(now_utc()), canon(refs), ctx.run_id, f["synthetic"]))
        ids.append(sid)
    return ids


# ---------------------------------------------------------------- decide
def job_decide(ctx, allow_late=False):
    con, cfg = ctx.con, ctx.cfg
    T = ctx.scheduled_dt
    loc = T.astimezone(TZ)
    sd = loc.date()
    first = toronto_dt(sd, cfg["session"]["decision_first"])
    last = toronto_dt(sd, cfg["session"]["decision_last"])
    if not (first <= T <= last) or loc.minute % 15 or loc.second:
        raise JobFailed(f"{et(T)} is not a registered decision time")
    if (now_utc() - T).total_seconds() > 600 and not allow_late:
        raise JobFailed(f"LATE_RUN: now {et(now_utc())} > scheduled {et(T)} + 10 min; missed decisions are not executed late")
    t_end = signals.floor15(T)
    coll = _collect(ctx, wait_for_end_ms=t_end)
    b = _borrow_snapshot(ctx)
    ev_ids = []
    with writer_lock(), tx(con):
        _store_borrow(con, ctx, b)
        day = ledger.ensure_day(con, sd, ctx.synthetic)
        e, n = trades.process_trades(con, cfg, ctx.run_id, now_utc(), ctx.synthetic)
        trades.process_hypotheticals(con, cfg, now_utc())
        ev_ids += e
        ctx.notes += n
    cutoff = now_utc()
    rs = signals.relative_strength(con, cfg, T, cutoff)
    per_market, cands = {}, []
    for m in cfg["market_order"]:
        fr = collector.freshness(con, cfg, m, cutoff, expected_bar_end_ms=t_end)
        ev = signals.evaluate_market(con, cfg, m, T, cutoff)
        per_market[m] = (fr, ev)
        for c in ev["candidates"]:
            c["market"] = m
            c["fresh"] = fr["pass"]
            cands.append(c)
    # portfolio state
    day = dict(con.execute("SELECT * FROM day_state WHERE session_date=?", (str(sd),)).fetchone())
    s = ledger.saved(con)
    open_pos = trades.open_positions(con)
    entries_today = con.execute("SELECT COUNT(*) FROM trades WHERE session_date=? AND status NOT IN ('EXPIRED','CANCELLED')", (str(sd),)).fetchone()[0]
    realized_today = (s["trading_cash"] + s["reserve"]) - (day["start_trading_equity"] + day["start_reserve"])
    locked = bool(day["locked"]) or realized_today <= -cfg["risk"]["daily_loss_lockout_pct"] / 100 * day["start_trading_equity"]
    hours_left = (toronto_dt(sd, cfg["session"]["session_end"]) - cutoff).total_seconds() / 3600
    borrow_now = con.execute("SELECT asset,long_hourly_pct,short_hourly_pct FROM borrow_snapshots ORDER BY fetched_ts DESC LIMIT 3").fetchall()
    bmap = {r[0]: (r[1], r[2]) for r in borrow_now}
    fr_mod = risk.cost_fractions_modeled(cfg)
    markets_sides = {}
    for c in cands:
        markets_sides.setdefault(c["market"], set()).add(c["side"])
    for c in cands:
        g = {}
        g["data_fresh"] = c["fresh"]
        g["trend_or_exclusion_gate"] = c["trend_gate"]
        g["no_contradictory_direction"] = len(markets_sides[c["market"]]) == 1
        g["one_per_setup_market_side_session"] = con.execute("SELECT COUNT(*) FROM trades WHERE session_date=? AND market=? AND setup=? AND side=?", (str(sd), c["market"], c["setup"], c["side"])).fetchone()[0] == 0
        g["no_open_position"] = len(open_pos) < cfg["risk"]["max_open_positions"]
        g["entries_today_below_max"] = entries_today < cfg["risk"]["max_entries_per_day"]
        g["not_locked_out"] = not locked
        asset = cfg["markets"][c["market"]]["jupiter_asset"]
        bp = bmap.get(asset, (0.0015, 0.0015))
        c["borrow_pct_h"] = bp[0] if c["side"] == "long" else bp[1]
        sz = risk.size(s["trading_cash"], c["stop_distance_frac_at_signal"], fr_mod, c["borrow_pct_h"], hours_left, cfg)
        c["sizing_modeled"] = sz
        g["risk_budget"] = bool(sz["ok"])
        c["gates"] = g
        c["passed"] = all(g.values())
        if sz.get("notional"):
            rt = sz["notional"] * (fr_mod["open_fee"] + fr_mod["open_impact"] + fr_mod["close_fee"] + fr_mod["close_impact"]) + 2 * fr_mod["net_open"]
            reward = sz["notional"] * c["target_r"] * c["stop_distance_frac_at_signal"] - rt
            c["rank_ratio"] = reward / sz["planned_loss"]["total"] if sz.get("planned_loss") else None
        else:
            c["rank_ratio"] = None
        c["reason"] = "PASS" if c["passed"] else next(("RISK_BUDGET_TOO_SMALL" if k == "risk_budget" else {"data_fresh": "STALE_OR_MISSING_DATA", "trend_or_exclusion_gate": "TREND_FILTER_OR_EXCLUSION",
                        "no_contradictory_direction": "CONTRADICTORY_DIRECTIONS", "one_per_setup_market_side_session": "ALREADY_ENTERED_THIS_SESSION", "no_open_position": "POSITION_ALREADY_OPEN",
                        "entries_today_below_max": "MAX_ENTRIES_REACHED", "not_locked_out": "DAILY_LOCKOUT"}[k]) for k, v in g.items() if not v)
    passing = sorted([c for c in cands if c["passed"]], key=lambda c: (-(c["rank_ratio"] or -1e9), c["setup"], c["market"]))
    selected, quote_records = None, []
    if passing:
        top = passing[0]
        asset = cfg["markets"][top["market"]]["jupiter_asset"]
        sz = top["sizing_modeled"]
        q = costmod.quote(cfg, asset, top["side"], sz["collateral"], sz["leverage"], hours_left)
        quote_records.append(q)
        if q["exit_code"] == 0 and q["response"]:
            frq = risk.cost_fractions_from_quote(q["response"])
            sz2 = risk.size(s["trading_cash"], top["stop_distance_frac_at_signal"], frq, q["response"]["fees"]["borrow"]["hourlyRatePct"], hours_left, cfg)
            if sz2["ok"] and abs(sz2["notional"] - q["response"]["positionSizeUsd"]) / q["response"]["positionSizeUsd"] > 0.02:
                q = costmod.quote(cfg, asset, top["side"], sz2["collateral"], sz2["leverage"], hours_left)
                quote_records.append(q)
                if q["exit_code"] == 0 and q["response"]:
                    frq = risk.cost_fractions_from_quote(q["response"])
                    sz2 = risk.size(s["trading_cash"], top["stop_distance_frac_at_signal"], frq, q["response"]["fees"]["borrow"]["hourlyRatePct"], hours_left, cfg)
            if q["exit_code"] == 0 and q["response"] and sz2["ok"]:
                qn = q["response"]["positionSizeUsd"]
                pl = risk.planned_loss(qn, top["stop_distance_frac_at_signal"], frq, q["response"]["fees"]["borrow"]["hourlyRatePct"], hours_left, cfg)
                if pl["total"] <= sz2["budget_usd"] + 1e-9:
                    top["sizing_quoted"] = dict(sz2, quoted_notional=qn, planned_loss_at_quoted=pl)
                    selected = top
                else:
                    top["passed"], top["reason"] = False, "RISK_BUDGET_TOO_SMALL"
                    top["sizing_quoted"] = dict(sz2, quoted_notional=qn, planned_loss_at_quoted=pl)
            elif q["exit_code"] == 0 and q["response"]:
                top["passed"], top["reason"], top["sizing_quoted"] = False, "RISK_BUDGET_TOO_SMALL", sz2
            else:
                top["passed"], top["reason"] = False, "QUOTE_UNAVAILABLE"
        else:
            top["passed"], top["reason"] = False, "QUOTE_UNAVAILABLE"
        for c in passing[1:]:
            c["reason"] = "RANKED_BELOW_SELECTED"
    # ---- atomic commit: snapshots, signals, decisions, trade+event, costs, quotes, delivery
    hhmm = loc.strftime("%H%M")
    w = {"snapshots": [], "signals": [], "decisions": [], "trades": [], "trade_events": list(ev_ids), "costs": []}
    alerts = []
    with writer_lock(), tx(con):
        commit_ts = now_utc()
        for m in cfg["market_order"]:
            fr, ev = per_market[m]
            sid = f"SN-{ctx.run_id}-{m}"
            feats = dict(ev["features"], relative_strength=rs if m == "BTC" else None, freshness=fr)
            con.execute("INSERT OR REPLACE INTO snapshots(snapshot_id,run_id,market,cutoff_ts,created_ts,freshness,features,calc_versions,features_hash,synthetic) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (sid, ctx.run_id, m, iso(cutoff), iso(commit_ts), canon(fr), canon(feats), canon(ev["calc_versions"]), ev["features_hash"], ctx.synthetic))
            w["snapshots"].append(sid)
            mc = [c for c in cands if c["market"] == m]
            if not fr["pass"]:
                alerts.append(f"{m} data gate failed: {[k for k, v in fr['gates'].items() if not v['pass']]}")
            if not mc:
                gates = ev["gates"]
                if not fr["pass"]:
                    reason = "DATA_GATE_FAIL"
                elif not gates.get("post_0600_bar"):
                    reason = "NO_POST_0600_COMPLETED_BAR"
                elif not all(gates.values()):
                    reason = "WARMUP_OR_OVERNIGHT_INCOMPLETE:" + ",".join(k for k, v in gates.items() if not v)
                else:
                    reason = "NO_SETUP_TRIGGERED"
                did = f"DC-{sd.strftime('%Y%m%d')}-{hhmm}-{m}-NONE"
                con.execute("INSERT INTO decisions(decision_id,run_id,signal_id,market,action,reason_code,detail,snapshot_id,risk_model,cost_model,committed_ts,synthetic) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                            (did, ctx.run_id, None, m, "NO_SIGNAL", reason, canon({"gates": gates, "freshness_pass": fr["pass"], "setup_checks": ev["features"].get("setup_checks")}), sid, None, None, iso(commit_ts), ctx.synthetic))
                w["decisions"].append(did)
            for c in mc:
                sgid = f"SG-{sd.strftime('%Y%m%d')}-{hhmm}-{m}-{c['setup']}-{c['side']}"
                levels = {k: c[k] for k in ("signal_price", "stop", "target_r", "level", "atr14", "stop_distance_frac_at_signal")}
                labels = ev["features"].get("condition_labels")
                desc = dict(rs["relative"], whale_lean=None, whale_lean_status="NO_REPRODUCIBLE_FEED", note="descriptive only; not a gate")
                con.execute("INSERT INTO signals(signal_id,run_id,snapshot_id,market,setup,setup_version,side,trigger_bar_start_ts,trigger_bar_end_ts,decision_ts,levels,horizon_ts,gates,passed,rank,synthetic,condition_labels,labels_version,descriptive_features) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (sgid, ctx.run_id, sid, m, c["setup"], c["setup_version"], c["side"], c["trigger_bar_start"], c["trigger_bar_end"], iso(T), canon(levels),
                             iso(toronto_dt(sd, cfg["session"]["session_end"])), canon(c["gates"]), 1 if c["passed"] else 0,
                             (passing.index(c) + 1) if c in passing else None, ctx.synthetic, canon(labels), (labels or {}).get("version"), canon(desc)))
                w["signals"].append(sgid)
                did = f"DC-{sd.strftime('%Y%m%d')}-{hhmm}-{m}-{c['setup']}-{c['side']}"
                action = "ENTER" if c is selected else "SKIP"
                con.execute("INSERT INTO decisions(decision_id,run_id,signal_id,market,action,reason_code,detail,snapshot_id,risk_model,cost_model,committed_ts,synthetic) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                            (did, ctx.run_id, sgid, m, action, "ENTER_SELECTED" if action == "ENTER" else c["reason"], canon({"gates": c["gates"], "rank_ratio": c["rank_ratio"]}), sid,
                             canon({"modeled": c["sizing_modeled"], "quoted": c.get("sizing_quoted")}), canon({"label": cfg["costs"]["experiment_label"], "quotes": len(quote_records) if (passing and c is passing[0]) else 0}), iso(commit_ts), ctx.synthetic))
                w["decisions"].append(did)
                if passing and c is passing[0]:
                    for i, q in enumerate(quote_records):
                        qid = f"QT-{did}-{i+1}"
                        con.execute("INSERT INTO quotes(quote_id,decision_ref,run_id,requested,response,stderr,exit_code,quoted_ts,synthetic) VALUES(?,?,?,?,?,?,?,?,?)",
                                    (qid, did, ctx.run_id, canon(q["requested"]), canon(q["response"]), q["stderr"][-1000:], q["exit_code"], q["quoted_ts"], ctx.synthetic))
                if action == "SKIP":
                    hm = cfg["measurement"]["hypothetical_skips"]
                    szm = c["sizing_modeled"]
                    if szm.get("ok"):
                        hn, flag = szm["notional"], "modeled_sizing"
                    else:
                        hn, flag = hm["standard_notional_usd"], "standardized_notional_sizing_failed"
                    hR = risk.planned_loss(hn, c["stop_distance_frac_at_signal"], fr_mod, c["borrow_pct_h"], hours_left, cfg)["total"]
                    hid = f"HY-{did}"
                    con.execute("INSERT OR IGNORE INTO hypothetical_outcomes(hyp_id,kind,signal_id,decision_id,skip_reason,session_date,market,setup,side,created_ts,commit_ts,expires_ts,status,notional_usd,size_flag,initial_risk_usd,stop_price,target_r,cost_fractions,condition_labels,note,synthetic) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (hid, "SKIPPED_PROSPECTIVE", sgid, did, c["reason"], str(sd), m, c["setup"], c["side"], iso(commit_ts), iso(commit_ts), iso(T + dt.timedelta(minutes=15)),
                                 "PENDING_FILL", hn, flag, hR, c["stop"], c["target_r"], canon(dict(fr_mod, borrow_pct_h=c["borrow_pct_h"])), canon(labels),
                                 "HYPOTHETICAL: excluded from official PnL; modeled costs", ctx.synthetic))
                    w.setdefault("hypothetical_outcomes", []).append(hid)
                if action == "ENTER":
                    tid = f"TR-{sd.strftime('%Y%m%d')}-{hhmm}-{m}-{c['setup']}-{c['side']}"
                    qr = quote_records[-1]["response"]
                    sq = c["sizing_quoted"]
                    con.execute("INSERT INTO trades(trade_id,decision_id,session_date,market,side,setup,status,notional_usd,collateral_usd,leverage,stop_price,target_r,stop_rule,commit_ts,expires_ts,synthetic,initial_risk_usd,condition_labels) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (tid, did, str(sd), m, c["side"], c["setup"], "PENDING_FILL", qr["positionSizeUsd"], sq["collateral"], sq["leverage"], c["stop"], c["target_r"],
                                 cfg["fills"]["stop_rule"], iso(commit_ts), iso(T + dt.timedelta(minutes=15)), ctx.synthetic, sq["planned_loss_at_quoted"]["total"], canon(labels)))
                    w["trades"].append(tid)
                    eid, _ = ledger.add_event(con, tid, "DECISION_ENTER", iso(commit_ts), ctx.run_id, amounts={"notional_usd": qr["positionSizeUsd"], "collateral_usd": sq["collateral"], "leverage": sq["leverage"],
                                              "stop": c["stop"], "planned_loss": sq["planned_loss_at_quoted"], "budget": sq["budget_usd"], "jupiter_quote_entry": qr["entryPriceUsd"]},
                                              evidence={"quote_id": f"QT-{did}-{len(quote_records)}", "signal_id": sgid}, synthetic=ctx.synthetic)
                    w["trade_events"].append(eid)
                    for comp, amt, status, src, phase in costmod.quote_cost_components(qr):
                        cid = f"CS-{tid}-{comp}"
                        con.execute("INSERT INTO costs(cost_id,trade_id,decision_id,component,amount_usd,status,phase,source,interval_start,interval_end,evidence,synthetic) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                    (cid, tid, did, comp, amt, status, phase, src, quote_records[-1]["quoted_ts"], None, canon({"quote_id": f"QT-{did}-{len(quote_records)}"}), ctx.synthetic))
                        w["costs"].append(cid)
                    alerts.append(f"PAPER ENTRY {tid} {c['side']} {m} setup {c['setup']} notional ${qr['positionSizeUsd']:.2f} stop {c['stop']:.4f}")
        dls = [("kyle-chat:not-configured", {"alerts": alerts})] if alerts else []
        ctx.commit_writes(w, data_cutoff=cutoff, data_quality={m: {"age_s": per_market[m][0].get("latest_primary", {}).get("age_s"), "gates_pass": per_market[m][0]["pass"]} for m in cfg["market_order"]},
                          deliveries=dls)
        con.execute("UPDATE deliveries SET status='not_configured', error='no authorized external channel' WHERE run_id=? AND destination LIKE 'kyle-chat%'", (ctx.run_id,))
        ctx.notes += alerts


# ---------------------------------------------------------------- risk monitor / close
def job_risk_monitor(ctx):
    con, cfg = ctx.con, ctx.cfg
    b = _borrow_snapshot(ctx)
    with writer_lock(), tx(con):
        _store_borrow(con, ctx, b)
        e, n = trades.process_trades(con, cfg, ctx.run_id, now_utc(), ctx.synthetic)
        hy = trades.process_hypotheticals(con, cfg, now_utc())
        ctx.notes += n
        dls = [("kyle-chat:not-configured", {"events": e, "notes": n})] if n else []
        ctx.commit_writes({"trade_events": e, "hypothetical_outcomes": hy}, data_cutoff=now_utc(), deliveries=dls)
        con.execute("UPDATE deliveries SET status='not_configured' WHERE run_id=? AND destination LIKE 'kyle-chat%'", (ctx.run_id,))


def job_close(ctx):
    con, cfg = ctx.con, ctx.cfg
    sd = toronto_date(ctx.scheduled_dt)
    noon = toronto_dt(sd, cfg["session"]["session_end"])
    if (trades.open_positions(con) or trades.open_hypotheticals(con)) and not OFFLINE():
        t0 = time.time()
        while time.time() - t0 < 240:
            collector.collect(con, cfg)
            if all(con.execute("SELECT 1 FROM market_data WHERE provider=? AND instrument=? AND timeframe='1m' AND derivation='native_1m' AND candle_start_ms=?",
                               (cfg["markets"][m]["primary"]["provider"], cfg["markets"][m]["primary"]["symbol"], to_ms(noon))).fetchone() for m in cfg["market_order"]):
                break
            time.sleep(10)
    b = _borrow_snapshot(ctx)
    with writer_lock(), tx(con):
        _store_borrow(con, ctx, b)
        e, n = trades.process_trades(con, cfg, ctx.run_id, now_utc(), ctx.synthetic)
        trades.process_hypotheticals(con, cfg, now_utc())
        still = [r["trade_id"] for r in trades.open_positions(con)]
        if still:
            ctx.notes.append(f"positions not yet closed (post-noon price not available): {still}; risk-monitor continues")
        ctx.notes += n
        ctx.commit_writes({"trade_events": e}, data_cutoff=now_utc(), data_quality={"open_after_close": still})


# ---------------------------------------------------------------- report
def job_report(ctx):
    con, cfg = ctx.con, ctx.cfg
    sd = toronto_date(ctx.scheduled_dt)
    _collect(ctx)
    cutoff = now_utc()
    with writer_lock(), tx(con):
        e, n = trades.process_trades(con, cfg, ctx.run_id, cutoff, ctx.synthetic)
        trades.process_hypotheticals(con, cfg, cutoff)
        sc = _score_due(con, cfg, ctx, cutoff, write=True)
        ctx.notes += n
    summary = export.daily_summary(con, cfg, sd)
    exp = export.export_day(con, cfg, sd, summary)
    bk = export.backup(con, tag=f"session-{sd}")
    with writer_lock(), tx(con):
        ctx.notes.append(f"report status {summary['report_status']}; backup {bk['path']}")
        ctx.commit_writes({"trade_events": e, "scores": sc}, data_cutoff=cutoff, data_quality={"report_status": summary["report_status"], "unresolved": summary["unresolved"]},
                          export_path=exp["dir"], deliveries=[(f"local:{exp['dir']}", {"manifest_sha256": exp["manifest_sha256"]}), ("kyle-chat:not-configured", {"summary": exp["dir"]})])
        con.execute("UPDATE deliveries SET status='written_unacknowledged', attempted_ts=?, receipt=? WHERE run_id=? AND destination LIKE 'local:%'", (iso(now_utc()), exp["manifest_sha256"], ctx.run_id))
        con.execute("UPDATE deliveries SET status='not_configured' WHERE run_id=? AND destination LIKE 'kyle-chat%'", (ctx.run_id,))


def job_weekly(ctx):
    con, cfg = ctx.con, ctx.cfg
    end = toronto_date(ctx.scheduled_dt)
    rep = export.weekly_review(con, cfg, end)
    with writer_lock(), tx(con):
        ctx.notes.append("weekly review: no strategy change (no versioned experiment result meets a promotion criterion)")
        ctx.commit_writes({}, data_cutoff=now_utc(), export_path=rep["path"])
