"""Run lifecycle: unique (job, scheduled_ts, strategy_version); idempotent retries; crash recovery;
receipts generated only after committed writes are verified."""
import json, os, traceback
from . import ledger
from .config import version_tag
from .db import tx, writer_lock
from .util import iso, now_utc, et, code_version, sha256_text, canon, ROOT, home

PREFIX_TABLE = {"EV-": "trade_events", "CS-": "costs", "FC-": "forecasts", "SN-": "snapshots", "SG-": "signals", "DC-": "decisions",
                "TR-": "trades", "SC-": "scores", "DL-": "deliveries", "HY-": "hypothetical_outcomes"}


def normalize_writes(writes):
    """Regroup ID lists by their stable ID prefix so receipts and verification use the right table."""
    out = {}
    for k, v in writes.items():
        if not isinstance(v, list):
            out[k] = v
            continue
        for i in v:
            t = next((tb for pf, tb in PREFIX_TABLE.items() if isinstance(i, str) and i.startswith(pf)), k)
            out.setdefault(t, []).append(i)
        out.setdefault(k, out.get(k, []))
    return out


TABLE_KEYS = {"forecasts": "forecast_id", "decisions": "decision_id", "signals": "signal_id", "trade_events": "event_id",
              "snapshots": "snapshot_id", "scores": "score_id", "costs": "cost_id", "trades": "trade_id", "deliveries": "delivery_id", "hypothetical_outcomes": "hyp_id"}


class JobFailed(Exception):
    pass


def pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class Ctx:
    def __init__(self, con, cfg, job, scheduled_dt, run_id, trigger, synthetic):
        self.con, self.cfg, self.job, self.scheduled_dt, self.run_id = con, cfg, job, scheduled_dt, run_id
        self.trigger, self.synthetic = trigger, synthetic
        self.ledger_before = ledger.saved(con)
        self.notes = []

    def commit_writes(self, writes, data_cutoff=None, data_quality=None, export_path=None, deliveries=None):
        """Call INSIDE the job's write transaction: marks the run COMMITTED atomically with its writes and
        queues deliveries in the same transaction."""
        con = self.con
        writes = normalize_writes(writes)
        payload = {"writes": writes, "ledger_before": self.ledger_before, "data_quality": data_quality, "export_path": export_path, "notes": self.notes}
        for dest, body in (deliveries or []):
            h = sha256_text(canon(body))
            did = f"DL-{self.run_id}-{dest.split(':')[0]}-{h[:8]}"
            con.execute("INSERT OR IGNORE INTO deliveries(delivery_id,run_id,payload_hash,destination,queued_ts,status) VALUES(?,?,?,?,?,?)",
                        (did, self.run_id, h, dest, iso(now_utc()), "queued"))
            writes.setdefault("deliveries", []).append(did)
        con.execute("UPDATE runs SET status='COMMITTED', rows_written=?, data_cutoff_ts=? WHERE run_id=?",
                    (canon(payload), iso(data_cutoff) if data_cutoff else None, self.run_id))


def run_id_for(job, scheduled_dt, cfg):
    return f"RUN-{job}-{scheduled_dt.strftime('%Y%m%dT%H%MZ')}-{cfg['strategy_version']}"


def execute(con, cfg, job, scheduled_dt, fn, trigger="manual", synthetic=0, quiet=False):
    rid = run_id_for(job, scheduled_dt, cfg)
    sv = cfg["strategy_version"]
    with writer_lock(), tx(con):
        row = con.execute("SELECT * FROM runs WHERE job=? AND scheduled_ts=? AND strategy_version=?", (job, iso(scheduled_dt), sv)).fetchone()
        if row and row["status"] in ("SUCCESS", "MISSED"):
            if not quiet:
                print(f"[idempotent] {rid} already {row['status']}; no new writes.\n" + (row["receipt"] or ""))
            return {"status": "NOOP_" + row["status"], "run_id": row["run_id"], "receipt": row["receipt"]}
        if row and row["status"] == "RUNNING" and pid_alive(row["pid"]) and row["pid"] != os.getpid():
            return {"status": "BUSY", "run_id": row["run_id"]}
        now = iso(now_utc())
        if row and row["status"] == "COMMITTED":
            pass
        elif row:
            prev = row["status"]
            con.execute("UPDATE run_attempts SET status=CASE WHEN status='RUNNING' THEN 'CRASHED_RECOVERED' ELSE status END, finished_ts=COALESCE(finished_ts,?) WHERE run_id=? AND attempt=?",
                        (now, row["run_id"], row["attempt"]))
            con.execute("UPDATE runs SET status='RUNNING', attempt=attempt+1, pid=?, started_ts=?, error=?, trigger=? WHERE run_id=?",
                        (os.getpid(), now, f"previous attempt {row['attempt']} ended {prev}: {row['error'] or 'process died before commit'}", trigger, row["run_id"]))
            con.execute("INSERT INTO run_attempts(run_id,attempt,pid,started_ts,status) VALUES(?,?,?,?,'RUNNING')", (row["run_id"], row["attempt"] + 1, os.getpid(), now))
        else:
            con.execute("INSERT INTO runs(run_id,job,scheduled_ts,strategy_version,config_version,config_hash,code_version,status,attempt,pid,started_ts,trigger,synthetic) VALUES(?,?,?,?,?,?,?,?,1,?,?,?,?)",
                        (rid, job, iso(scheduled_dt), sv, cfg["config_version"], cfg["_hash"], code_version(), "RUNNING", os.getpid(), now, trigger, synthetic))
            con.execute("INSERT INTO run_attempts(run_id,attempt,pid,started_ts,status) VALUES(?,1,?,?,'RUNNING')", (rid, os.getpid(), now))
        row = con.execute("SELECT * FROM runs WHERE run_id=?", (rid,)).fetchone()
    ctx = Ctx(con, cfg, job, scheduled_dt, rid, trigger, synthetic)
    if row["status"] != "COMMITTED":
        try:
            fn(ctx)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            tb = traceback.format_exc()[-3000:]
            with writer_lock(), tx(con):
                fc = "LATE_RUN" if "LATE_RUN" in err else ("DATA_UNAVAILABLE" if "prerequisites failed" in err else type(e).__name__)
                con.execute("UPDATE runs SET status='FAILED', finished_ts=?, error=?, failure_class=?, duration_s=(julianday(?)-julianday(started_ts))*86400 WHERE run_id=?", (iso(now_utc()), err + "\n" + tb, fc, iso(now_utc()).replace('Z',''), rid))
                con.execute("UPDATE run_attempts SET status='FAILED', finished_ts=?, error=? WHERE run_id=? AND status='RUNNING'", (iso(now_utc()), err, rid))
            receipt = f"Run: {rid} | scheduled/finished: {et(scheduled_dt)} / {et(now_utc())} | status: FAILED\nError: {err}\nNo official output was produced by this run."
            _write_receipt(rid, receipt)
            if not quiet:
                print(receipt)
            return {"status": "FAILED", "run_id": rid, "error": err, "receipt": receipt}
    return finalize(con, cfg, rid, quiet=quiet)


def finalize(con, cfg, rid, quiet=False):
    row = con.execute("SELECT * FROM runs WHERE run_id=?", (rid,)).fetchone()
    if row["status"] != "COMMITTED":
        raise JobFailed(f"cannot finalize {rid} in status {row['status']}")
    payload = json.loads(row["rows_written"] or "{}")
    writes = payload.get("writes", {})
    missing = []
    for table, ids in writes.items():
        key = TABLE_KEYS.get(table)
        if not key or not isinstance(ids, list):
            continue
        for i in ids:
            if not con.execute(f"SELECT 1 FROM {table} WHERE {key}=?", (i,)).fetchone():
                missing.append(f"{table}:{i}")
    rec = ledger.reconcile(con, cfg["risk"]["initial_paper_capital_usd"])
    s = ledger.saved(con)
    finished = now_utc()
    dq = payload.get("data_quality") or {}
    dl = con.execute("SELECT destination,status FROM deliveries WHERE run_id=?", (rid,)).fetchall()
    dl_txt = "; ".join(f"{d[0]}={d[1]}" for d in dl) or "no handoff queued (no external recipient configured)"
    counts = {t: len(v) for t, v in writes.items() if isinstance(v, list)}
    ids_show = {t: (v[:6] + ([f"...+{len(v)-6}"] if len(v) > 6 else [])) for t, v in writes.items() if isinstance(v, list) and v}
    status = "SUCCESS" if not missing else "FAILED_VERIFY"
    lb = payload.get("ledger_before") or {}
    receipt = "\n".join([
        f"Run: {rid} | scheduled/finished: {et(_p(row['scheduled_ts']))} / {et(finished)} | status: {status}",
        f"Data cutoff: {et(_p(row['data_cutoff_ts'])) if row['data_cutoff_ts'] else 'n/a'} | age/gaps: {canon(dq) if dq else 'n/a'}",
        f"Writes: {canon(counts)} | IDs: {canon(ids_show)}",
        f"Ledger before/after: trading ${lb.get('trading_cash', float('nan')):.4f} reserve ${lb.get('reserve', float('nan')):.4f} -> trading ${s['trading_cash']:.4f} reserve ${s['reserve']:.4f} | reconciliation difference: ${rec['diff_usd']:.6f}",
        f"Strategy/config: {version_tag(cfg)} code {row['code_version']} | evidence export: {payload.get('export_path') or os.path.join(home(), 'captain.db') + ' runs/' + rid}",
        f"Delivery: {dl_txt}",
    ] + ([f"Notes: {'; '.join(payload.get('notes'))}"] if payload.get("notes") else []) + ([f"VERIFY MISSING: {missing}"] if missing else []))
    with writer_lock(), tx(con):
        dur = (finished - _p(row["started_ts"])).total_seconds() if row["started_ts"] else None
        con.execute("UPDATE runs SET status=?, finished_ts=?, receipt=?, error=?, duration_s=?, data_quality=?, failure_class=? WHERE run_id=?",
                    (status, iso(finished), receipt, (f"missing {missing}" if missing else None), dur, canon(dq), ("VERIFY" if missing else None), rid))
        con.execute("UPDATE run_attempts SET status=?, finished_ts=? WHERE run_id=? AND status='RUNNING'", (status, iso(finished), rid))
    if row["job"] != "collect":
        _write_receipt(rid, receipt)
    if not quiet:
        print(receipt)
    return {"status": status, "run_id": rid, "receipt": receipt, "writes": writes}


def _p(s):
    from .util import parse_ts
    return parse_ts(s)


def _write_receipt(rid, text):
    d = os.path.join(home(), "logs", "receipts")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, rid + ".txt"), "a") as f:
        f.write(text + "\n\n")
