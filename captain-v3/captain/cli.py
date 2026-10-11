"""captain CLI. PAPER ONLY."""
import argparse, datetime as dt, json, os, sys
from . import config, db, jobs, runs, export, collector, ledger
from .util import now_utc, iso, et, parse_ts, toronto_dt, toronto_date, canon, TZ, ROOT, home

EXPERIMENTS = [
    ("EXP-A1", "Setup A overnight-breakout-continuation (A-1.0.0) has positive net expectancy after costs on 06:00-12:00 Toronto", "breakouts of the overnight range with hourly trend alignment continue intraday"),
    ("EXP-B1", "Setup B failed-overnight-breakout (B-1.0.0) has positive net expectancy after costs", "failed probes beyond the overnight range revert"),
    ("EXP-F1", "Session class-frequency baseline (rolling 365, Laplace 1) is better calibrated (lower Brier) than expanding-history and prior-session rule", "base rates are the honest prior"),
    ("EXP-FEAT-RS1", "Requiring alt-minus-BTC 1h relative strength to agree with signal side improves net R vs all signals (same signals, same periods)", "relative strength persistence; descriptive only, never gated"),
]
TRIALS = {
    "EXP-A1": [("A-1.0.0-official", {"setup": "A-1.0.0"}, None), ("A-1.0.0-hypothetical", {"setup": "A-1.0.0", "source": "skipped signals"}, None)],
    "EXP-B1": [("B-1.0.0-official", {"setup": "B-1.0.0"}, None), ("B-1.0.0-hypothetical", {"setup": "B-1.0.0", "source": "skipped signals"}, None)],
    "EXP-F1": [("freq_rolling365_laplace1", {"window": 365, "alpha": 1}, None), ("freq_expanding_laplace1", {"alpha": 1}, None), ("prior_session_rule_onehot", {}, None)],
    "EXP-FEAT-RS1": [("baseline_all_signals", {}, "without"), ("rs1h_agrees_with_side", {"feature": "ALT-BTC_1h", "rule": "sign agrees with side"}, "with")],
}
TRAIN_CUTOFF = {"EXP-A1": "none: seed parameters, not fitted", "EXP-B1": "none: seed parameters, not fitted",
                "EXP-F1": "expanding: sessions strictly before each target date", "EXP-FEAT-RS1": "none: not fitted"}
FORWARD_START = "2026-09-26"


def _init(con, cfg):
    db.init(con, cfg["risk"]["initial_paper_capital_usd"])
    with db.writer_lock(), db.tx(con):
        for eid, h, mech in EXPERIMENTS:
            con.execute("INSERT OR IGNORE INTO experiments(experiment_id,hypothesis,mechanism,registered_params,data_splits,trial_count,results,status,created_ts) VALUES(?,?,?,?,?,?,?,?,?)",
                        (eid, h, mech, canon({"config_version": cfg["config_version"], "config_hash": cfg["_hash"]}),
                         canon({"development": "none (seed hypotheses, not fitted)", "evaluation": "forward sessions from first live decide run"}), 1, None, "REGISTERED_FROZEN", iso(now_utc())))
            trials = TRIALS[eid]
            con.execute("UPDATE experiments SET trial_count=?, trial_count_total=?, train_cutoff=COALESCE(train_cutoff,?), forward_start=COALESCE(forward_start,?), forward_end=COALESCE(forward_end,?), comparison_design=COALESCE(comparison_design,?) WHERE experiment_id=?",
                        (len(trials), len(trials), TRAIN_CUTOFF[eid], FORWARD_START, "open: first review at >=60 forward sessions and >=100 closed trades",
                         "with-vs-without on identical signal set and periods" if eid == "EXP-FEAT-RS1" else "variants evaluated on identical forward sessions", eid))
            for v, params, fs in trials:
                con.execute("INSERT OR IGNORE INTO experiment_trials(trial_id,experiment_id,variant,params,feature_set,registered_ts,train_cutoff,forward_start,forward_end,status) VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (f"TRIAL-{eid}-{v}", eid, v, canon(params), fs, iso(now_utc()), TRAIN_CUTOFF[eid], FORWARD_START, None, "REGISTERED"))


def minute(d):
    return d.replace(second=0, microsecond=0)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="captain")
    ap.add_argument("cmd")
    ap.add_argument("target", nargs="?", help="trade/decision/hypothetical ID for `replay`")
    ap.add_argument("--market"); ap.add_argument("--side"); ap.add_argument("--note")
    ap.add_argument("--at", help="scheduled time (ISO, or HH:MM Toronto today)")
    ap.add_argument("--session", help="forecast target session date YYYY-MM-DD")
    ap.add_argument("--date")
    ap.add_argument("--db")
    ap.add_argument("--from", dest="src")
    ap.add_argument("--to")
    ap.add_argument("--trigger", default="manual")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    cfg = config.load()
    con = db.connect()
    _init(con, cfg)

    def sched(default):
        if not a.at:
            return default
        if len(a.at) <= 5:
            return toronto_dt(toronto_date(now_utc()), a.at)
        return parse_ts(a.at)

    n = now_utc()
    q = a.quiet
    if a.cmd == "init":
        print("initialized", db.db_path(), config.version_tag(cfg))
    elif a.cmd == "collect":
        r = runs.execute(con, cfg, "collect", sched(minute(n)), jobs.job_collect, a.trigger, quiet=q)
    elif a.cmd == "audit":
        r = runs.execute(con, cfg, "audit", sched(minute(n)), jobs.job_audit, a.trigger, quiet=q)
    elif a.cmd == "forecast":
        sd = dt.date.fromisoformat(a.session) if a.session else None
        r = runs.execute(con, cfg, "forecast", sched(minute(n)), lambda c: jobs.job_forecast(c, sd), a.trigger, quiet=q)
    elif a.cmd == "decide":
        ms = int(n.timestamp()) // 900 * 900
        r = runs.execute(con, cfg, "decide", sched(dt.datetime.fromtimestamp(ms, dt.timezone.utc)), jobs.job_decide, a.trigger, quiet=q)
    elif a.cmd == "risk-monitor":
        r = runs.execute(con, cfg, "risk-monitor", sched(minute(n)), jobs.job_risk_monitor, a.trigger, quiet=q)
    elif a.cmd == "close":
        r = runs.execute(con, cfg, "close", sched(toronto_dt(toronto_date(n), "12:00")), jobs.job_close, a.trigger, quiet=q)
    elif a.cmd == "report":
        r = runs.execute(con, cfg, "report", sched(toronto_dt(toronto_date(n), "12:10")), jobs.job_report, a.trigger, quiet=q)
    elif a.cmd == "weekly":
        r = runs.execute(con, cfg, "weekly", sched(minute(n)), jobs.job_weekly, a.trigger, quiet=q)
    elif a.cmd == "backup":
        print(json.dumps(export.backup(con, "manual"), indent=1))
    elif a.cmd == "restore":
        print(json.dumps(export.restore(a.src, a.to), indent=1))
    elif a.cmd == "replay" and a.target:
        from . import tradereplay
        print(tradereplay.render(con, cfg, a.target))
    elif a.cmd == "replay":
        print(json.dumps(export.replay(a.db or db.db_path(), cfg), indent=1, default=str))
    elif a.cmd == "hindsight":
        hid = f"HS-{now_utc().strftime('%Y%m%dT%H%M%S')}-{a.market}-{a.side}"
        with db.writer_lock(), db.tx(con):
            con.execute("INSERT INTO hypothetical_outcomes(hyp_id,kind,session_date,market,side,created_ts,status,note) VALUES(?,?,?,?,?,?,?,?)",
                        (hid, "HINDSIGHT", str(toronto_date(n)), a.market, a.side, iso(n), "RESEARCH_HYPOTHESIS_ONLY", "HINDSIGHT (logged after the fact): " + (a.note or "")))
        print("logged hindsight hypothesis (excluded from all official and prospective results):", hid)
    elif a.cmd == "export":
        sd = dt.date.fromisoformat(a.date) if a.date else toronto_date(n)
        s = export.daily_summary(con, cfg, sd)
        print(json.dumps(export.export_day(con, cfg, sd, s), indent=1))
    elif a.cmd == "ack":
        with db.writer_lock(), db.tx(con):
            con.execute("UPDATE deliveries SET acknowledged_ts=?, status='acknowledged' WHERE delivery_id=?", (iso(now_utc()), a.src))
        print("acknowledged", a.src)
    elif a.cmd == "status":
        print(status(con, cfg))
    elif a.cmd == "scheduler":
        from . import scheduler
        scheduler.loop()
    else:
        ap.error(f"unknown command {a.cmd}")
        return 2
    if a.cmd in ("collect", "audit", "forecast", "decide", "risk-monitor", "close", "report", "weekly"):
        return 0 if r["status"].startswith(("SUCCESS", "NOOP")) else 1
    return 0


def status(con, cfg):
    L = [f"Crypto Captain v3 status at {et(now_utc())} | config {config.version_tag(cfg)}"]
    for r in con.execute("SELECT job, status, MAX(finished_ts), COUNT(*) FROM runs GROUP BY job, status ORDER BY job").fetchall():
        L.append(f"  {r[0]:<13} {r[1]:<10} n={r[3]:<5} last={et(parse_ts(r[2])) if r[2] else '-'}")
    s = ledger.saved(con)
    L.append(f"  ledger: trading ${s['trading_cash']:.4f} reserve ${s['reserve']:.4f} | recon diff ${ledger.reconcile(con, cfg['risk']['initial_paper_capital_usd'])['diff_usd']:.6f}")
    hb = os.path.join(home(), "state", "scheduler-heartbeat.json")
    if os.path.exists(hb):
        h = json.load(open(hb))
        L.append(f"  scheduler heartbeat: {et(parse_ts(h['ts']))} pid {h.get('pid')} next: {h.get('next')}")
    else:
        L.append("  scheduler heartbeat: none")
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
