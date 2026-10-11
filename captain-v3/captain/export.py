"""Daily exports (CSV/JSON + manifest with sha256), DB backup, restore and deterministic replay."""
import csv, datetime as dt, json, os, shutil, sqlite3, statistics
from . import ledger, signals, forecast as fc
from .db import connect
from .util import ROOT, home, iso, now_utc, et, sha256_file, sha256_text, canon, toronto_dt, parse_ts, TZ

TABLES_DAY = {
    "runs": "SELECT * FROM runs WHERE (scheduled_ts>=? AND scheduled_ts<? AND job!='collect') OR run_id IN (SELECT run_id FROM forecasts WHERE target_start_ts>=? AND target_start_ts<?) ORDER BY scheduled_ts",
    "runs_collect_summary": "SELECT status, COUNT(*) AS n, MIN(scheduled_ts) AS first, MAX(scheduled_ts) AS last FROM runs WHERE job='collect' AND scheduled_ts>=? AND scheduled_ts<? GROUP BY status",
    "forecasts": "SELECT * FROM forecasts WHERE (target_start_ts>=? AND target_start_ts<?) OR (created_ts>=? AND created_ts<?) ORDER BY forecast_id",
    "scores": "SELECT s.* FROM scores s JOIN forecasts f ON f.forecast_id=s.forecast_id WHERE f.target_start_ts>=? AND f.target_start_ts<? ORDER BY s.score_id",
    "snapshots": "SELECT snapshot_id,run_id,market,cutoff_ts,created_ts,features_hash,calc_versions,freshness,features FROM snapshots WHERE (cutoff_ts>=? AND cutoff_ts<?) OR run_id IN (SELECT run_id FROM forecasts WHERE target_start_ts>=? AND target_start_ts<?) ORDER BY cutoff_ts",
    "signals": "SELECT * FROM signals WHERE decision_ts>=? AND decision_ts<? ORDER BY signal_id",
    "decisions": "SELECT * FROM decisions WHERE committed_ts>=? AND committed_ts<? ORDER BY decision_id",
    "trades": "SELECT * FROM trades WHERE commit_ts>=? AND commit_ts<? ORDER BY trade_id",
    "trade_events": "SELECT * FROM trade_events WHERE recorded_ts>=? AND recorded_ts<? ORDER BY recorded_ts",
    "costs": "SELECT c.* FROM costs c JOIN trades t ON t.trade_id=c.trade_id WHERE t.commit_ts>=? AND t.commit_ts<? ORDER BY c.cost_id",
    "deliveries": "SELECT * FROM deliveries WHERE queued_ts>=? AND queued_ts<? ORDER BY queued_ts",
    "hypothetical_outcomes": "SELECT * FROM hypothetical_outcomes WHERE created_ts>=? AND created_ts<? ORDER BY hyp_id",
    "run_timeline": "SELECT run_id, job, scheduled_ts, started_ts, finished_ts, duration_s, status, attempt, failure_class, trigger, data_quality, substr(error,1,300) AS error FROM runs WHERE scheduled_ts>=? AND scheduled_ts<? ORDER BY scheduled_ts",
    "corrections": "SELECT * FROM corrections WHERE recorded_ts>=? AND recorded_ts<? OR entity_id IN (SELECT forecast_id FROM forecasts WHERE target_start_ts>=? AND target_start_ts<?) ORDER BY recorded_ts",
}


def _day_bounds(sd):
    a = toronto_dt(sd, "00:00")
    b = toronto_dt(sd + dt.timedelta(days=1), "00:00")
    return iso(a), iso(b)


def daily_summary(con, cfg, sd):
    a, b = _day_bounds(sd)
    s = ledger.saved(con)
    rec = ledger.reconcile(con, cfg["risk"]["initial_paper_capital_usd"])
    runs = con.execute("SELECT job, status, COUNT(*) FROM runs WHERE scheduled_ts>=? AND scheduled_ts<? AND job!='collect' GROUP BY job, status", (a, b)).fetchall()
    dec_expected = 24
    dec_ok = con.execute("SELECT COUNT(*) FROM runs WHERE job='decide' AND status='SUCCESS' AND scheduled_ts>=? AND scheduled_ts<?", (a, b)).fetchone()[0]
    trs = [dict(r) for r in con.execute("SELECT * FROM trades WHERE session_date=? AND synthetic=0", (str(sd),)).fetchall()]
    closed = [t for t in trs if t["status"] == "CLOSED"]
    unresolved = [t["trade_id"] for t in trs if t["status"] in ("OPEN", "UNRESOLVED", "PENDING_FILL")]
    fcs = [dict(r) for r in con.execute("SELECT f.forecast_id,f.market,f.model_id,f.is_official,f.p_up,f.p_down,f.p_range,f.sample_count,s.status,s.outcome,s.return_pct,s.brier,s.exclusion_reason FROM forecasts f LEFT JOIN scores s ON s.forecast_id=f.forecast_id WHERE f.session_date=? AND f.synthetic=0 ORDER BY f.market,f.model_id", (str(sd),)).fetchall()]
    rej = con.execute("SELECT reason_code, COUNT(*) FROM decisions WHERE committed_ts>=? AND committed_ts<? AND synthetic=0 GROUP BY reason_code", (a, b)).fetchall()
    day = con.execute("SELECT * FROM day_state WHERE session_date=?", (str(sd),)).fetchone()
    start_total = (day["start_trading_equity"] + day["start_reserve"]) if day else None
    unscored = [f["forecast_id"] for f in fcs if f["status"] != "SCORED"]
    out = {
        "session_date": str(sd), "generated_ts": iso(now_utc()), "generated_et": et(now_utc()),
        "report_status": "PROVISIONAL" if (unresolved or unscored or abs(rec["diff_usd"]) > 1e-6) else "FINAL",
        "operating": {"runs_by_job_status": [list(r) for r in runs], "decide_expected": dec_expected, "decide_success": dec_ok},
        "forecasts": fcs, "unscored_forecasts": unscored,
        "decision_reason_counts": dict(rej),
        "trades": trs, "closed_count": len(closed), "unresolved": unresolved,
        "ambiguous_count": sum(t["ambiguous"] for t in closed),
        "gross_pnl": sum(t["gross_pnl"] or 0 for t in closed), "total_costs": sum(t["total_costs"] or 0 for t in closed), "net_pnl": sum(t["net_pnl"] or 0 for t in closed),
        "equity": {"trading_cash": s["trading_cash"], "reserve": s["reserve"], "total": s["trading_cash"] + s["reserve"], "start_of_day_total": start_total},
        "reconciliation": rec,
        "strategy_change": "no strategy change (no versioned experiment promoted)",
        "learning_claim": "none: no learning artifacts exist yet",
        "labels": {"experiment": cfg["costs"]["experiment_label"], "synthetic_excluded": True},
    }
    from . import analytics
    from .db import writer_lock, tx as _tx
    with writer_lock(), _tx(con):
        analytics.refresh_trials(con, cfg)
    out["analytics"] = analytics.full(con, cfg)
    out["drawdown"] = out["analytics"]["drawdown"]
    out["hypothetical_skips_today"] = [dict(r) for r in con.execute("SELECT hyp_id, skip_reason, status, net_pnl, net_r FROM hypothetical_outcomes WHERE session_date=?", (str(sd),)).fetchall()]
    return out


def _write_csv(path, rows):
    with open(path, "w", newline="") as f:
        if not rows:
            f.write("")
            return
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)


def export_day(con, cfg, sd, summary):
    d = os.path.join(home(), "exports", str(sd))
    os.makedirs(d, exist_ok=True)
    a, b = _day_bounds(sd)
    files = {}
    for name, q in TABLES_DAY.items():
        args = (a, b, a, b) if q.count("?") == 4 else (a, b)
        rows = [dict(r) for r in con.execute(q, args).fetchall()]
        p = os.path.join(d, f"{name}.csv")
        _write_csv(p, rows)
        files[f"{name}.csv"] = len(rows)
    from . import analytics
    pts, _ = analytics.equity_curve(con, cfg)
    _write_csv(os.path.join(d, "equity_curve.csv"), pts)
    _write_csv(os.path.join(d, "experiment_trials.csv"), [dict(r) for r in con.execute("SELECT * FROM experiment_trials ORDER BY trial_id").fetchall()])
    _write_csv(os.path.join(d, "calibration_points.csv"), [dict(r) for r in con.execute("SELECT f.forecast_id, f.session_date, f.market, f.model_id, f.is_official, f.p_up, f.p_down, f.p_range, s.status, s.outcome, s.brier FROM forecasts f LEFT JOIN scores s ON s.forecast_id=f.forecast_id WHERE f.synthetic=0 ORDER BY f.session_date, f.forecast_id").fetchall()])
    with open(os.path.join(d, "analytics.json"), "w") as f:
        json.dump(summary.get("analytics"), f, indent=1, default=str)
    with open(os.path.join(d, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1, default=str)
    rec = [r[0] for r in con.execute("SELECT receipt FROM runs WHERE receipt IS NOT NULL AND ((scheduled_ts>=? AND scheduled_ts<? AND job!='collect') OR run_id IN (SELECT run_id FROM forecasts WHERE target_start_ts>=? AND target_start_ts<?)) ORDER BY scheduled_ts", (a, b, a, b)).fetchall()]
    with open(os.path.join(d, "receipts.txt"), "w") as f:
        f.write("\n\n".join(rec))
    with open(os.path.join(d, "report.md"), "w") as f:
        f.write(render_md(summary))
    manifest = {"session_date": str(sd), "created_ts": iso(now_utc()), "db": os.path.join(home(), "captain.db"), "files": {}}
    for fn in sorted(os.listdir(d)):
        if fn == "manifest.json":
            continue
        p = os.path.join(d, fn)
        manifest["files"][fn] = {"sha256": sha256_file(p), "bytes": os.path.getsize(p), "rows": files.get(fn)}
    mp = os.path.join(d, "manifest.json")
    with open(mp, "w") as f:
        json.dump(manifest, f, indent=1)
    latest = os.path.join(home(), "exports", "latest")
    if os.path.islink(latest) or os.path.exists(latest):
        os.remove(latest)
    os.symlink(str(sd), latest)
    return {"dir": d, "manifest_sha256": sha256_file(mp)}


def render_md(s):
    L = [f"# Crypto Captain v3 daily evidence — {s['session_date']} ({s['report_status']})", "", f"Generated {s['generated_et']}. PAPER ONLY. {s['labels']['experiment']}", ""]
    L += ["## Operating status", f"- decide runs: {s['operating']['decide_success']}/{s['operating']['decide_expected']} successful",
          f"- runs by job/status: {s['operating']['runs_by_job_status']}", f"- reconciliation difference: ${s['reconciliation']['diff_usd']:.6f}", ""]
    L += ["## Forecasts (06:00–12:00 Toronto, UP/DOWN/RANGE ±0.5%)", "| id | official | P(UP) | P(DOWN) | P(RANGE) | n | status | outcome | return % | Brier |", "|---|---|---|---|---|---|---|---|---|---|"]
    for f in s["forecasts"]:
        L.append(f"| {f['forecast_id']} | {f['is_official']} | {f['p_up']:.4f} | {f['p_down']:.4f} | {f['p_range']:.4f} | {f['sample_count']} | {f['status'] or 'PENDING'} | {f['outcome'] or ''} | {'' if f['return_pct'] is None else round(f['return_pct'],4)} | {'' if f['brier'] is None else round(f['brier'],4)} |")
    L += ["", "## Decisions", f"- reason counts: {s['decision_reason_counts']}", "", "## Trades"]
    if not s["trades"]:
        L.append("- none")
    for t in s["trades"]:
        L.append(f"- {t['trade_id']} {t['status']} entry {t['entry_price']} exit {t['exit_price']} ({t['exit_reason']}) gross {t['gross_pnl']} costs {t['total_costs']} net {t['net_pnl']} ambiguous={t['ambiguous']}")
    e = s["equity"]
    L += ["", "## Equity", f"- trading ${e['trading_cash']:.4f} | reserve ${e['reserve']:.4f} | total ${e['total']:.4f} | start-of-day total {e['start_of_day_total']}",
          f"- closed trades {s['closed_count']}, gross {s['gross_pnl']:.4f}, costs {s['total_costs']:.4f}, net {s['net_pnl']:.4f}", "",
          f"- drawdown (from events): max ${s['drawdown']['max_drawdown_usd']:.4f} ({100*s['drawdown']['max_drawdown_pct']:.2f}%), current ${s['drawdown']['current_drawdown_usd']:.4f}, underwater since {s['drawdown']['underwater_since']}", "",
          "## Skipped signals — HYPOTHETICAL, excluded from official PnL"] + ([f"- {h['hyp_id']} {h['skip_reason']} {h['status']} net_R={h['net_r']}" for h in s["hypothetical_skips_today"]] or ["- none"]) + ["",
          "## Expectancy in R (official) by setup", f"- {json.dumps({k: {kk: v.get(kk) for kk in ('n','mean','ci','reliable')} for k, v in s['analytics']['official']['expectancy_r_by_setup'].items()}, default=str) or 'no closed trades'}", "",
          f"Strategy: {s['strategy_change']}. Learning: {s['learning_claim']}.", ""]
    return "\n".join(L)


def backup(con, tag="manual"):
    d = os.path.join(home(), "backups")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"captain-{now_utc().strftime('%Y%m%dT%H%M%SZ')}-{tag}.db")
    dst = sqlite3.connect(p)
    con.backup(dst)
    dst.close()
    h = sha256_file(p)
    with open(p + ".sha256", "w") as f:
        f.write(f"{h}  {os.path.basename(p)}\n")
    return {"path": p, "sha256": h}


def replay(db_file, cfg):
    """Restore-check + deterministic replay on a DB file: integrity, ledger rebuild vs saved, Brier recompute,
    and re-evaluation of every stored decision snapshot from stored market data (features hash must match)."""
    con = connect(db_file)
    out = {"db": db_file, "integrity": con.execute("PRAGMA integrity_check").fetchone()[0]}
    out["ledger"] = ledger.reconcile(con, cfg["risk"]["initial_paper_capital_usd"])
    bad = 0
    n = 0
    for r in con.execute("SELECT s.score_id, s.outcome, s.brier, f.p_up, f.p_down, f.p_range FROM scores s JOIN forecasts f ON f.forecast_id=s.forecast_id WHERE s.status='SCORED'").fetchall():
        n += 1
        b = fc.brier({"UP": r[3], "DOWN": r[4], "RANGE": r[5]}, r[1])
        if abs(b - r[2]) > 1e-12:
            bad += 1
    out["scores"] = {"checked": n, "mismatch": bad}
    n = m = 0
    mism = []
    for r in con.execute("SELECT sn.snapshot_id, sn.market, sn.cutoff_ts, sn.features_hash, ru.scheduled_ts FROM snapshots sn JOIN runs ru ON ru.run_id=sn.run_id WHERE ru.job='decide' AND sn.market IS NOT NULL").fetchall():
        n += 1
        ev = signals.evaluate_market(con, cfg, r[1], parse_ts(r[4]), parse_ts(r[2]))
        if ev["features_hash"] != r[3]:
            m += 1
            mism.append(r[0])
    out["signal_replay"] = {"snapshots_replayed": n, "hash_mismatch": m, "mismatched_ids": mism[:10]}
    ev = con.execute("SELECT trade_id, event_type, trading_cash_delta, reserve_delta FROM trade_events ORDER BY recorded_ts, event_id").fetchall()
    tc = cfg["risk"]["initial_paper_capital_usd"]
    rs = 0.0
    for e in ev:
        tc += e[2]
        rs += e[3]
    out["event_replay"] = {"events": len(ev), "trading_cash": tc, "reserve": rs, "total": tc + rs}
    out["counts"] = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("runs", "forecasts", "decisions", "signals", "trades", "trade_events", "costs", "scores", "market_data")}
    out["ok"] = out["integrity"] == "ok" and abs(out["ledger"]["diff_usd"]) < 1e-9 and bad == 0 and m == 0
    con.close()
    return out


def restore(backup_file, target):
    shutil.copyfile(backup_file, target)
    exp = open(backup_file + ".sha256").read().split()[0] if os.path.exists(backup_file + ".sha256") else None
    return {"restored_to": target, "sha256_expected": exp, "sha256_restored": sha256_file(target), "match": exp == sha256_file(target) if exp else None}


def weekly_review(con, cfg, end_date):
    start = end_date - dt.timedelta(days=6)
    a = iso(toronto_dt(start, "00:00"))
    b = iso(toronto_dt(end_date + dt.timedelta(days=1), "00:00"))
    trs = [dict(r) for r in con.execute("SELECT * FROM trades WHERE commit_ts>=? AND commit_ts<? AND synthetic=0 AND status='CLOSED'", (a, b)).fetchall()]
    sc = [dict(r) for r in con.execute("SELECT f.model_id, f.market, s.brier, s.outcome FROM scores s JOIN forecasts f ON f.forecast_id=s.forecast_id WHERE s.status='SCORED' AND f.target_start_ts>=? AND f.target_start_ts<? AND f.synthetic=0", (a, b)).fetchall()]
    by_model = {}
    for s in sc:
        by_model.setdefault(s["model_id"], []).append(s["brier"])
    nets = [t["net_pnl"] for t in trs]
    rep = {"window": [str(start), str(end_date)], "closed_trades": len(trs),
           "net_expectancy_per_trade": (sum(nets) / len(nets)) if nets else None,
           "sample_note": "far below the 60-session/100-trade research checkpoint; no inference possible" ,
           "brier_by_model": {k: {"n": len(v), "mean": sum(v) / len(v)} for k, v in by_model.items()},
           "experiments": [dict(r) for r in con.execute("SELECT experiment_id,hypothesis,status,trial_count FROM experiments").fetchall()],
           "decision": "no strategy change; incumbent frozen"}
    d = os.path.join(home(), "exports", "weekly")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"weekly-{end_date}.json")
    with open(p, "w") as f:
        json.dump(rep, f, indent=1, default=str)
    return {"path": p, "report": rep}
