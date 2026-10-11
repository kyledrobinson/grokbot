"""Minimal long-running scheduler (no cron/systemd on this box). America/Toronto, DST-aware.
Singleton via flock. Heartbeat: state/scheduler-heartbeat.json. Log: logs/scheduler.log.
Missed slots past their grace are recorded as MISSED runs (never executed late, except close/report
which must still reconcile)."""
import datetime as dt, fcntl, json, os, subprocess, sys, time, traceback
from . import config, db
from .util import ROOT, home, TZ, UTC, iso, et, now_utc, toronto_dt, parse_ts

STATE = os.path.join(home(), "state")
LOG = os.path.join(home(), "logs", "scheduler.log")
BIN = os.path.join(ROOT, "bin", "captain")
GRACE_MIN = {"audit": 20, "forecast": None, "decide": 10, "close": None, "report": None, "weekly": 120}


def log(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{et(now_utc())} | {msg}\n")


def slots_for_day(d):
    """All scheduled (job, utc_dt) for Toronto date d."""
    s = [("audit", toronto_dt(d, "05:35")), ("forecast", toronto_dt(d, "05:43"))]
    t = toronto_dt(d, "06:00")
    for i in range(24):
        s.append(("decide", t + dt.timedelta(minutes=15 * i)))
    s += [("close", toronto_dt(d, "12:00")), ("report", toronto_dt(d, "12:10"))]
    if d.weekday() == 6:
        s.append(("weekly", toronto_dt(d, "13:00")))
    return s


def next_slots(now, n=6):
    d = now.astimezone(TZ).date()
    out = []
    for k in range(0, 3):
        for j, t in slots_for_day(d + dt.timedelta(days=k)):
            if t > now:
                out.append((j, t))
    out.sort(key=lambda x: x[1])
    return out[:n]


def grace_deadline(job, t):
    if job == "forecast":
        return toronto_dt(t.astimezone(TZ).date(), "06:00")
    g = GRACE_MIN.get(job)
    return None if g is None else t + dt.timedelta(minutes=g)


def run_status(con, cfg, job, t):
    r = con.execute("SELECT status FROM runs WHERE job=? AND scheduled_ts=? AND strategy_version=?", (job, iso(t), cfg["strategy_version"])).fetchone()
    return r[0] if r else None


def mark_missed(con, cfg, job, t, why):
    from .runs import run_id_for
    with db.writer_lock(), db.tx(con):
        con.execute("INSERT OR IGNORE INTO runs(run_id,job,scheduled_ts,strategy_version,config_version,config_hash,code_version,status,attempt,started_ts,finished_ts,error,trigger,failure_class) VALUES(?,?,?,?,?,?,?,?,0,?,?,?,?,'MISSED')",
                    (run_id_for(job, t, cfg), job, iso(t), cfg["strategy_version"], cfg["config_version"], cfg["_hash"], None, "MISSED", None, iso(now_utc()), why, "scheduler"))
    log(f"MISSED {job} {et(t)}: {why}")


def spawn(args, tag):
    os.makedirs(os.path.join(home(), "logs", "jobs"), exist_ok=True)
    lf = open(os.path.join(home(), "logs", "jobs", f"{now_utc().astimezone(TZ).date()}.log"), "a")
    lf.write(f"\n==== {et(now_utc())} {tag}: {' '.join(args)}\n")
    lf.flush()
    return subprocess.Popen([BIN] + args, stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT, start_new_session=True)


def loop():
    os.makedirs(STATE, exist_ok=True)
    lockf = open(os.path.join(STATE, "scheduler.lock"), "w")
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("scheduler already running", file=sys.stderr)
        sys.exit(3)
    lockf.write(str(os.getpid()))
    lockf.flush()
    cfg = config.load()
    con = db.connect()
    inst_p = os.path.join(STATE, "installed_at.txt")
    if not os.path.exists(inst_p):
        open(inst_p, "w").write(iso(now_utc()))
    installed = parse_ts(open(inst_p).read().strip())
    log(f"scheduler start pid={os.getpid()} installed_at={et(installed)} config={cfg['config_version']}#{cfg['_hash']}")
    running = {}
    last_minute = None
    while True:
        try:
            now = now_utc()
            # reap
            for k, p in list(running.items()):
                rc = p.poll()
                if rc is not None:
                    if not k.startswith("collect"):
                        log(f"finished {k} rc={rc}")
                    del running[k]
            minute = now.replace(second=0, microsecond=0)
            if minute != last_minute and now.second >= 3:
                last_minute = minute
                # due scheduled slots (today and yesterday for close/report catch-up)
                d = now.astimezone(TZ).date()
                for day in (d - dt.timedelta(days=1), d):
                    for job, t in slots_for_day(day):
                        if t > now or t < installed:
                            continue
                        st = run_status(con, cfg, job, t)
                        if st in ("SUCCESS", "MISSED"):
                            continue
                        key = f"{job}@{iso(t)}"
                        if key in running:
                            continue
                        dl = grace_deadline(job, t)
                        if st is None and dl is not None and now > dl:
                            mark_missed(con, cfg, job, t, "not started before grace deadline (scheduler down or late)")
                            continue
                        att = con.execute("SELECT attempt FROM runs WHERE job=? AND scheduled_ts=? AND strategy_version=?", (job, iso(t), cfg["strategy_version"])).fetchone()
                        if st == "FAILED" and att and att[0] >= 5:
                            continue
                        if st == "FAILED" and job in ("decide", "forecast", "audit"):
                            # retry transient failures only inside the grace window, at most every minute
                            if dl is not None and now > dl:
                                continue
                        running[key] = spawn([job, "--at", iso(t), "--trigger", "scheduler"], key)
                        log(f"spawned {key} pid={running[key].pid}")
                # minute collection (not while a previous collect runs)
                if not any(k.startswith("collect") for k in running):
                    running[f"collect@{iso(minute)}"] = spawn(["collect", "--at", iso(minute), "--trigger", "scheduler", "--quiet"], "collect")
                # risk monitor while positions exist
                n_open = con.execute("SELECT (SELECT COUNT(*) FROM trades WHERE status IN ('PENDING_FILL','OPEN','UNRESOLVED')) + (SELECT COUNT(*) FROM hypothetical_outcomes WHERE status IN ('PENDING_FILL','OPEN','UNRESOLVED'))").fetchone()[0]
                if n_open and not any(k.startswith("risk-monitor") for k in running):
                    key = f"risk-monitor@{iso(minute)}"
                    running[key] = spawn(["risk-monitor", "--at", iso(minute), "--trigger", "scheduler"], key)
                    log(f"spawned {key} (open positions: {n_open})")
                nxt = [f"{j} {et(t)}" for j, t in next_slots(now)]
                hb = {"ts": iso(now), "pid": os.getpid(), "running": list(running.keys()), "next": nxt, "open_positions": n_open}
                tmp = os.path.join(STATE, "scheduler-heartbeat.json.tmp")
                with open(tmp, "w") as f:
                    json.dump(hb, f)
                os.replace(tmp, os.path.join(STATE, "scheduler-heartbeat.json"))
                if minute.minute % 30 == 0:
                    log(f"heartbeat running={list(running.keys())} next={nxt[:3]}")
        except Exception:
            log("ERROR " + traceback.format_exc()[-1500:])
        time.sleep(1)
