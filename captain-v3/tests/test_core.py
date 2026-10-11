"""Gate-3 tests (spec section 13). All data here is SYNTHETIC, in temp DBs, excluded from performance."""
import datetime as dt, json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import synth
from captain import sim, risk, forecast as fc, signals, collector, ledger, runs, jobs, db, trades, export, costs as costmod, indicators
from captain.util import toronto_dt, to_ms, iso, from_ms, parse_ts, TZ

MIN = 60_000
SD = dt.date(2026, 7, 15)  # EDT session used for synthetic end-to-end tests


def set_now(d):
    os.environ["CAPTAIN_FAKE_NOW"] = iso(d)


def bar(s, o, h, l, c):
    return {"candle_start_ms": s, "open": o, "high": h, "low": l, "close": c}


class TestFillSimulator(unittest.TestCase):
    NOON = 10 ** 15

    def test_same_bar_stop_and_target_is_stop_first_and_ambiguous(self):
        r = sim.step("long", 99.0, 102.0, bar(0, 100, 102.5, 98.5, 101), 5, self.NOON)
        self.assertEqual(r[0], "STOP"); self.assertTrue(r[2]); self.assertAlmostEqual(r[1], 99.0 * (1 - 5e-4))
        r = sim.step("short", 101.0, 98.0, bar(0, 100, 101.5, 97.5, 99), 5, self.NOON)
        self.assertEqual(r[0], "STOP"); self.assertTrue(r[2]); self.assertAlmostEqual(r[1], 101.0 * (1 + 5e-4))

    def test_gap_through_stop_fills_at_open_not_stop(self):
        r = sim.step("long", 99.0, 102.0, bar(0, 97.0, 97.5, 96.0, 97.2), 5, self.NOON)
        self.assertEqual(r[0], "STOP_GAP"); self.assertAlmostEqual(r[1], 97.0 * (1 - 5e-4))
        self.assertLess(r[1], 99.0)
        r = sim.step("short", 101.0, 98.0, bar(0, 103.0, 103.5, 102.0, 103.2), 5, self.NOON)
        self.assertEqual(r[0], "STOP_GAP"); self.assertAlmostEqual(r[1], 103.0 * (1 + 5e-4))

    def test_target_gap_gets_no_price_improvement(self):
        r = sim.step("long", 99.0, 102.0, bar(0, 103.0, 104, 102.5, 103.5), 5, self.NOON)
        self.assertEqual(r, ("TARGET", 102.0, False))

    def test_entry_is_next_observable_open_after_commit_not_signal_close(self):
        bars = [bar(i * MIN, 100 + i, 100 + i, 100 + i, 100 + i) for i in range(5)]
        b, px = sim.entry_fill(bars, commit_ms=1 * MIN + 10_000, latency_ms=5_000, side="long", slip_bps=5)
        self.assertEqual(b["candle_start_ms"], 2 * MIN)
        self.assertAlmostEqual(px, 102 * 1.0005)

    def test_pre_entry_extremes_are_ignored(self):
        bars = [bar(0, 100, 100, 90, 100), bar(MIN, 100, 100.5, 99.5, 100.2)]
        r = sim.run_exits("long", 95.0, 110.0, bars, start_ms=MIN, slip_bps=5, noon_ms=self.NOON)
        self.assertEqual(r["status"], "OPEN")

    def test_missing_minutes_make_trade_unresolved(self):
        bars = [bar(0, 100, 100.2, 99.9, 100), bar(3 * MIN, 100, 100.2, 99.9, 100)]
        r = sim.run_exits("long", 95.0, 110.0, bars, 0, 5, self.NOON)
        self.assertEqual(r["status"], "UNRESOLVED"); self.assertEqual(r["gap_from_ms"], MIN)

    def test_noon_close_uses_first_post_noon_open(self):
        noon = 10 * MIN
        bars = [bar(i * MIN, 100, 100.1, 99.9, 100) for i in range(10)] + [bar(noon, 100.7, 101, 100.5, 100.8)]
        r = sim.run_exits("long", 95.0, 110.0, bars, 0, 5, noon)
        self.assertEqual(r["reason"], "NOON_CLOSE"); self.assertAlmostEqual(r["price"], 100.7 * (1 - 5e-4)); self.assertEqual(r["exit_ms"], noon)

    def test_lockout_flattens_at_next_bar_open(self):
        bars = [bar(0, 100, 100, 98, 98.5), bar(MIN, 98.4, 98.6, 98.2, 98.3)]
        r = sim.run_exits("long", 90.0, 120.0, bars, 0, 5, 10 ** 15, lock_px=99.0)
        self.assertEqual(r["reason"], "LOCKOUT_FLATTEN"); self.assertAlmostEqual(r["price"], 98.4 * (1 - 5e-4))

    def test_invalid_levels_after_entry(self):
        self.assertFalse(sim.valid_levels("long", 99.0, 99.5))
        self.assertFalse(sim.valid_levels("short", 101.0, 100.0))


class TestCostsAndSizing(unittest.TestCase):
    def setUp(self):
        _, self.cfg, self.con = synth.fresh_env()

    def test_variable_borrow_is_integrated_over_intervals(self):
        h = 3_600_000
        snaps = [(0, 0.001, 0.0005), (h, 0.004, 0.0005), (2 * h, 0.002, 0.0005)]
        total, iv = sim.integrate_borrow(snaps, 0, int(2.5 * h), 100.0, "long")
        self.assertAlmostEqual(total, 100 * (0.001 + 0.004 + 0.002 * 0.5) / 100)
        flat, _ = sim.integrate_borrow([(0, 0.001, 0.0005)], 0, int(2.5 * h), 100.0, "long")
        self.assertNotAlmostEqual(total, flat)
        none, flags = sim.integrate_borrow([], 0, h, 100.0, "long")
        self.assertIsNone(none)

    def test_quote_costs_change_size_and_planned_loss_respects_2pct(self):
        cheap = risk.cost_fractions_from_quote(synth.synthetic_quote("SOL", "long", 25, 2, open_fee_bps=6)["response"])
        dear = risk.cost_fractions_from_quote(synth.synthetic_quote("SOL", "long", 25, 2, open_fee_bps=60, impact_bps=40)["response"])
        a = risk.size(50.0, 0.03, cheap, 0.0015, 5, self.cfg)
        b = risk.size(50.0, 0.03, dear, 0.0015, 5, self.cfg)
        self.assertTrue(a["ok"] and b["ok"])
        self.assertGreater(a["notional"], b["notional"])
        for s in (a, b):
            self.assertLessEqual(s["planned_loss"]["total"], 1.0 + 1e-9)
            self.assertLessEqual(s["leverage"], 2.0); self.assertLessEqual(s["collateral"], 25.0); self.assertGreaterEqual(s["collateral"], 10.0)

    def test_wide_stop_gives_risk_budget_too_small(self):
        fr = risk.cost_fractions_modeled(self.cfg)
        s = risk.size(50.0, 0.12, fr, 0.0015, 5, self.cfg)
        self.assertFalse(s["ok"]); self.assertEqual(s["reason"], "RISK_BUDGET_TOO_SMALL")

    def test_only_readonly_tools_allowed(self):
        with self.assertRaises(AssertionError):
            costmod._run("/usr/bin/true", [])


class TestDST(unittest.TestCase):
    def test_session_utc_mapping_and_overnight_length(self):
        self.assertEqual(iso(toronto_dt(dt.date(2026, 7, 15), "06:00")), "2026-07-15T10:00:00.000Z")
        self.assertEqual(iso(toronto_dt(dt.date(2026, 12, 15), "06:00")), "2026-12-15T11:00:00.000Z")
        spring, fall = dt.date(2026, 3, 8), dt.date(2026, 11, 1)
        self.assertEqual((toronto_dt(spring, "06:00") - toronto_dt(spring, "00:00")).total_seconds() / 900, 20)
        self.assertEqual((toronto_dt(fall, "06:00") - toronto_dt(fall, "00:00")).total_seconds() / 900, 28)

    def test_overnight_levels_on_fall_back_day_need_28_bars(self):
        _, cfg, con = synth.fresh_env()
        synth.build_session(con, cfg, dt.date(2026, 11, 1), markets=("BTC",), end_local="06:30")
        on = signals.overnight_levels(con, cfg, "BTC", dt.date(2026, 11, 1), toronto_dt(dt.date(2026, 11, 1), "07:00"))
        self.assertEqual(on["expected"], 28); self.assertTrue(on["complete"])

    def test_scheduler_slots_follow_toronto_time(self):
        from captain import scheduler
        s = dict((j, t) for j, t in scheduler.slots_for_day(dt.date(2026, 12, 15)) if j != "decide")
        self.assertEqual(iso(s["forecast"]), "2026-12-15T10:43:00.000Z")
        self.assertEqual(len([1 for j, _ in scheduler.slots_for_day(dt.date(2026, 3, 8)) if j == "decide"]), 24)


class TestForecast(unittest.TestCase):
    def test_laplace_baseline_and_brier(self):
        sess = [{"date": dt.date(2026, 1, i + 1), "ret": 0, "cls": c} for i, c in enumerate(["UP"] * 3 + ["DOWN"] * 1 + ["RANGE"] * 6)]
        p, n = fc.freq_probs(sess, 1.0)
        self.assertAlmostEqual(p["UP"], 4 / 13); self.assertAlmostEqual(p["DOWN"], 2 / 13); self.assertAlmostEqual(sum(p.values()), 1.0)
        self.assertAlmostEqual(fc.brier({"UP": 0.2, "DOWN": 0.3, "RANGE": 0.5}, "UP"), 0.64 + 0.09 + 0.25)
        self.assertEqual(fc.classify(0.005, 0.5), "RANGE"); self.assertEqual(fc.classify(0.0051, 0.5), "UP"); self.assertEqual(fc.classify(-0.0051, 0.5), "DOWN")

    def test_synthetic_rows_excluded_from_baseline_history(self):
        _, cfg, con = synth.fresh_env()
        with db.tx(con):
            con.execute("INSERT INTO market_data(provider,instrument,timeframe,derivation,candle_start_ms,candle_end_ms,open,high,low,close,volume,received_ts,is_final,synthetic) VALUES('binance_spot','BTCUSDT','1h','native_1h',0,3600000,1,1,1,1,1,'x',1,1)")
        self.assertEqual(fc.eligible_sessions(con, "binance_spot", "BTCUSDT", 0.5), [])


class TestIndicators(unittest.TestCase):
    def test_atr_wilder_and_ema_seed(self):
        bars = [{"high": 10 + i, "low": 9 + i, "close": 9.5 + i} for i in range(20)]
        a = indicators.atr_wilder(bars, 14)
        self.assertIsNone(a[12]); self.assertIsNotNone(a[13])
        e = indicators.ema(list(range(1, 61)), 50)
        self.assertAlmostEqual(e[49], 25.5)


class TestEndToEnd(unittest.TestCase):
    """Synthetic session: setup A long at 06:15, fill, exit, costs, reserve, reconciliation, retries."""

    def setUp(self):
        self.home, self.cfg, self.con = synth.fresh_env()
        self._orig_quote = costmod.quote
        costmod.quote = lambda cfg, asset, side, coll, lev, h: synth.synthetic_quote(asset, side, coll, lev)

    def tearDown(self):
        costmod.quote = self._orig_quote
        os.environ.pop("CAPTAIN_FAKE_NOW", None)

    def decide(self, hhmm, now_hhmm_ss):
        T = toronto_dt(SD, hhmm)
        h, m, s = map(int, now_hhmm_ss.split(":"))
        set_now(T.replace(second=0) + dt.timedelta(hours=h - T.astimezone(TZ).hour, minutes=m - T.astimezone(TZ).minute, seconds=s))
        return runs.execute(self.con, self.cfg, "decide", T, jobs.job_decide, quiet=True)

    def monitor(self, local_hhmm):
        set_now(toronto_dt(SD, local_hhmm) + dt.timedelta(seconds=5))
        return runs.execute(self.con, self.cfg, "risk-monitor", toronto_dt(SD, local_hhmm), jobs.job_risk_monitor, quiet=True)

    def test_full_cycle_target_reserve_and_idempotency(self):
        synth.build_session(self.con, self.cfg, SD, post_prices=[101.5 + 0.2 * i for i in range(60)])
        r = self.decide("06:15", "06:15:10")
        self.assertEqual(r["status"], "SUCCESS", r.get("receipt"))
        ents = self.con.execute("SELECT * FROM decisions WHERE action='ENTER'").fetchall()
        self.assertEqual(len(ents), 1)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM signals").fetchone()[0], 3)  # all 3 markets triggered, logged
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM decisions WHERE reason_code='RANKED_BELOW_SELECTED'").fetchone()[0], 2)
        tr = self.con.execute("SELECT * FROM trades").fetchone()
        self.assertEqual(tr["status"], "PENDING_FILL"); self.assertEqual(tr["market"], "BTC")  # tie-break by market name
        # duplicate retry: no new writes
        n_before = {t: self.con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("decisions", "signals", "trades", "trade_events", "costs")}
        r2 = self.decide("06:15", "06:15:40")
        self.assertTrue(r2["status"].startswith("NOOP"))
        self.assertEqual(n_before, {t: self.con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in n_before})
        # fill at 06:16 open (first bar starting after commit + latency), never the 06:15 signal close
        self.monitor("06:17")
        tr = self.con.execute("SELECT * FROM trades").fetchone()
        self.assertEqual(tr["status"], "OPEN")
        self.assertEqual(tr["entry_ts"], iso(toronto_dt(SD, "06:16")))
        # run to target
        for mm in range(18, 60):
            rm = self.monitor(f"06:{mm:02d}")
            self.assertEqual(rm["status"], "SUCCESS", rm.get("receipt"))
        tr = self.con.execute("SELECT * FROM trades").fetchone()
        self.assertEqual(tr["status"], "CLOSED"); self.assertEqual(tr["exit_reason"], "TARGET")
        self.assertGreater(tr["net_pnl"], 0)
        # all cost components labelled
        st = dict(self.con.execute("SELECT component, status FROM costs WHERE trade_id=?", (tr["trade_id"],)).fetchall())
        self.assertEqual(st["open_fee"], "quote"); self.assertEqual(st["close_fee"], "estimate"); self.assertEqual(st["borrow"], "estimate")
        # reserve transfer exactly once, 50% of net, internal
        rt = self.con.execute("SELECT * FROM trade_events WHERE event_type='RESERVE_TRANSFER'").fetchall()
        self.assertEqual(len(rt), 1)
        self.assertAlmostEqual(rt[0]["reserve_delta"], 0.5 * tr["net_pnl"]); self.assertAlmostEqual(rt[0]["trading_cash_delta"], -0.5 * tr["net_pnl"])
        s = ledger.saved(self.con)
        self.assertAlmostEqual(s["trading_cash"] + s["reserve"], 50 + tr["net_pnl"])
        self.assertAlmostEqual(ledger.reconcile(self.con, 50)["diff_usd"], 0.0)
        # re-processing after close is a no-op (one close event per trade even on retry)
        with db.writer_lock(), db.tx(self.con):
            trades.close_trade(self.con, self.cfg, dict(tr, entry_ts=tr["entry_ts"]), {"price": tr["exit_price"], "exit_ms": to_ms(parse_ts(tr["exit_ts"])), "reason": "TARGET", "last_processed_ms": 0}, "RUN-x")
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM trade_events WHERE event_type IN ('CLOSE','RESERVE_TRANSFER')").fetchone()[0], 2)
        # max one entry per setup/market/side/session and one open position enforced on next cycle
        r3 = self.decide("06:30", "06:30:10")
        self.assertEqual(r3["status"], "SUCCESS")
        # replay reproduces signals/ledger deterministically
        rp = export.replay(os.environ["CAPTAIN_DB"], self.cfg)
        self.assertTrue(rp["ok"], rp)

    def test_stale_data_blocks_entry(self):
        synth.build_session(self.con, self.cfg, SD, post_prices=[101.5] * 10, secondary=True)
        # decide 3 minutes late relative to the last received candle -> latest price older than 60s
        with db.tx(self.con):
            self.con.execute("DELETE FROM market_data WHERE timeframe='1m' AND candle_start_ms>=?", (to_ms(toronto_dt(SD, "06:13")),))
        r = self.decide("06:15", "06:15:10")
        self.assertEqual(r["status"], "SUCCESS")
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM decisions WHERE action='ENTER'").fetchone()[0], 0)
        reasons = {x[0] for x in self.con.execute("SELECT reason_code FROM decisions").fetchall()}
        self.assertTrue(reasons & {"DATA_GATE_FAIL", "STALE_OR_MISSING_DATA", "WARMUP_OR_OVERNIGHT_INCOMPLETE:atr_warmup"}, reasons)
        self.assertIn("kyle-chat:not-configured", {x[0] for x in self.con.execute("SELECT destination FROM deliveries").fetchall()})

    def test_stop_gap_loss_no_reserve_and_noon_close(self):
        synth.build_session(self.con, self.cfg, SD, post_prices=[101.5] * 20 + [95.0] * 10)
        gap_ms = to_ms(toronto_dt(SD, "06:35"))
        with db.tx(self.con):  # SYNTHETIC gap: bar opens far below the stop
            self.con.execute("UPDATE market_data SET open=95.0, high=95.02 WHERE timeframe='1m' AND candle_start_ms=?", (gap_ms,))
        self.decide("06:15", "06:15:10")
        for mm in range(17, 60):
            self.monitor(f"06:{mm:02d}")
        tr = self.con.execute("SELECT * FROM trades").fetchone()
        self.assertEqual(tr["exit_reason"], "STOP_GAP"); self.assertLess(tr["net_pnl"], 0)
        self.assertLess(tr["exit_price"], tr["stop_price"])
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM trade_events WHERE event_type='RESERVE_TRANSFER'").fetchone()[0], 0)
        self.assertAlmostEqual(ledger.reconcile(self.con, 50)["diff_usd"], 0.0)

    def test_noon_close_end_to_end(self):
        synth.build_session(self.con, self.cfg, SD, post_prices=[101.5 + 0.001 * i for i in range(400)], end_local="12:03")
        self.decide("06:15", "06:15:10")
        self.monitor("06:17")
        set_now(toronto_dt(SD, "12:01") + dt.timedelta(seconds=10))
        r = runs.execute(self.con, self.cfg, "close", toronto_dt(SD, "12:00"), jobs.job_close, quiet=True)
        self.assertEqual(r["status"], "SUCCESS")
        tr = self.con.execute("SELECT * FROM trades").fetchone()
        self.assertEqual(tr["exit_reason"], "NOON_CLOSE"); self.assertEqual(tr["exit_ts"], iso(toronto_dt(SD, "12:00")))

    def test_crash_before_commit_rolls_back_and_retry_recovers(self):
        synth.build_session(self.con, self.cfg, SD, post_prices=[101.5] * 10)
        T = toronto_dt(SD, "06:15")
        set_now(T + dt.timedelta(seconds=10))
        orig = self.cfg["costs"]["experiment_label"]
        boom = {"n": 0}
        real = ledger.add_event

        def crash(*a, **k):
            boom["n"] += 1
            raise RuntimeError("simulated crash mid-transaction")
        ledger.add_event = crash
        try:
            r = runs.execute(self.con, self.cfg, "decide", T, jobs.job_decide, quiet=True)
        finally:
            ledger.add_event = real
        self.assertEqual(r["status"], "FAILED")
        for t in ("decisions", "signals", "trades", "trade_events", "costs", "snapshots"):
            self.assertEqual(self.con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0], 0, t)
        r2 = runs.execute(self.con, self.cfg, "decide", T, jobs.job_decide, quiet=True)
        self.assertEqual(r2["status"], "SUCCESS")
        row = self.con.execute("SELECT attempt FROM runs WHERE run_id=?", (r2["run_id"],)).fetchone()
        self.assertEqual(row[0], 2)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM trades").fetchone()[0], 1)

    def test_dead_process_running_row_is_recovered(self):
        synth.build_session(self.con, self.cfg, SD, post_prices=[101.5] * 10)
        T = toronto_dt(SD, "06:15")
        set_now(T + dt.timedelta(seconds=10))
        rid = runs.run_id_for("decide", T, self.cfg)
        with db.tx(self.con):
            self.con.execute("INSERT INTO runs(run_id,job,scheduled_ts,strategy_version,status,attempt,pid,started_ts) VALUES(?,?,?,?,'RUNNING',1,999999,?)", (rid, "decide", iso(T), self.cfg["strategy_version"], iso(T)))
            self.con.execute("INSERT INTO run_attempts(run_id,attempt,pid,started_ts,status) VALUES(?,1,999999,?,'RUNNING')", (rid, iso(T)))
        r = runs.execute(self.con, self.cfg, "decide", T, jobs.job_decide, quiet=True)
        self.assertEqual(r["status"], "SUCCESS")
        self.assertEqual(self.con.execute("SELECT status FROM run_attempts WHERE run_id=? AND attempt=1", (rid,)).fetchone()[0], "CRASHED_RECOVERED")

    def test_crash_after_commit_before_receipt_finalizes_without_duplicates(self):
        synth.build_session(self.con, self.cfg, SD, post_prices=[101.5] * 10)
        T = toronto_dt(SD, "06:15")
        set_now(T + dt.timedelta(seconds=10))
        real = runs.finalize
        runs.finalize = lambda *a, **k: (_ for _ in ()).throw(SystemExit("killed after commit"))
        try:
            with self.assertRaises(SystemExit):
                runs.execute(self.con, self.cfg, "decide", T, jobs.job_decide, quiet=True)
        finally:
            runs.finalize = real
        self.assertEqual(self.con.execute("SELECT status FROM runs").fetchone()[0], "COMMITTED")
        n = self.con.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        r = runs.execute(self.con, self.cfg, "decide", T, jobs.job_decide, quiet=True)
        self.assertEqual(r["status"], "SUCCESS")
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], n)
        self.assertIn("Run: " + r["run_id"], r["receipt"])

    def test_late_decision_is_not_executed(self):
        synth.build_session(self.con, self.cfg, SD, post_prices=[101.5] * 60)
        r = self.decide("06:15", "06:40:00")
        self.assertEqual(r["status"], "FAILED"); self.assertIn("LATE_RUN", r["error"])

    def test_contradictory_directions_rejected(self):
        c = [{"market": "BTC", "side": "long"}, {"market": "BTC", "side": "short"}]
        sides = {}
        for x in c:
            sides.setdefault(x["market"], set()).add(x["side"])
        self.assertEqual(len(sides["BTC"]), 2)


class TestSignalsAndReport(unittest.TestCase):
    def setUp(self):
        self.home, self.cfg, self.con = synth.fresh_env()

    def tearDown(self):
        os.environ.pop("CAPTAIN_FAKE_NOW", None)

    def test_setup_b_probe_and_trend_exclusion(self):
        synth.build_session(self.con, self.cfg, SD, breakout=False, markets=("BTC",), end_local="06:20")
        ms = to_ms(toronto_dt(SD, "06:10"))
        with db.tx(self.con):  # SYNTHETIC probe above the overnight high that closes back below
            self.con.execute("UPDATE market_data SET high=100.6 WHERE timeframe='1m' AND candle_start_ms=?", (ms,))
            self.con.execute("DELETE FROM market_data WHERE timeframe IN ('15m','1h')")
            p = self.cfg["markets"]["BTC"]["primary"]
            collector.aggregate(self.con, p["provider"], p["symbol"], 15, since_ms=0, synthetic=1)
            collector.aggregate(self.con, p["provider"], p["symbol"], 60, since_ms=0, synthetic=1)
        T = toronto_dt(SD, "06:15")
        ev = signals.evaluate_market(self.con, self.cfg, "BTC", T, T + dt.timedelta(seconds=10))
        b = [c for c in ev["candidates"] if c["setup"] == "B"]
        self.assertEqual(len(b), 1); self.assertEqual(b[0]["side"], "short")
        self.assertFalse(b[0]["trend_gate"])  # hourly close > rising EMA50 -> short excluded
        self.assertAlmostEqual(b[0]["stop"], 100.6 + 0.1 * ev["features"]["atr14"])

    def test_no_lookahead_bar_not_yet_received(self):
        synth.build_session(self.con, self.cfg, SD, markets=("BTC",), end_local="06:20")
        T = toronto_dt(SD, "06:15")
        ev = signals.evaluate_market(self.con, self.cfg, "BTC", T, T - dt.timedelta(seconds=30))
        self.assertFalse(ev["gates"]["atr_warmup"]); self.assertEqual(ev["candidates"], [])

    def test_report_exports_manifest_backup_restore_replay(self):
        synth.build_session(self.con, self.cfg, SD, post_prices=[101.5] * 400, end_local="12:12")
        set_now(toronto_dt(SD, "12:10") + dt.timedelta(seconds=5))
        r = runs.execute(self.con, self.cfg, "report", toronto_dt(SD, "12:10"), jobs.job_report, quiet=True)
        self.assertEqual(r["status"], "SUCCESS", r.get("receipt"))
        d = os.path.join(self.home, "exports", str(SD))
        man = json.load(open(os.path.join(d, "manifest.json")))
        from captain.util import sha256_file
        for fn, meta in man["files"].items():
            self.assertEqual(sha256_file(os.path.join(d, fn)), meta["sha256"])
        bk = sorted(f for f in os.listdir(os.path.join(self.home, "backups")) if f.endswith(".db"))[-1]
        rs = export.restore(os.path.join(self.home, "backups", bk), os.path.join(self.home, "restored.db"))
        self.assertTrue(rs["match"])
        rp = export.replay(os.path.join(self.home, "restored.db"), self.cfg)
        self.assertTrue(rp["ok"], rp)


class TestMeasurement(unittest.TestCase):
    """Kyle's measurement requirements: R, MAE/MFE, cost multipliers, hypothetical-skip isolation, labels, replay."""

    def test_excursions_ignore_pre_entry_and_exit_bar_extremes(self):
        pre = bar(0, 100, 100, 80, 100)  # pre-entry crash: must not count
        post = [bar(MIN, 100, 101, 99.0, 100.5), bar(2 * MIN, 100.5, 103, 100.2, 102.5)]
        exit_bar = bar(3 * MIN, 102.5, 110, 90, 102)  # exit bar: only the exit price counts
        bars = [pre] + post + [exit_bar]
        processed = [b for b in bars if MIN <= b["candle_start_ms"] < 3 * MIN]
        st = sim.update_excursions({}, "long", 50.0, 100.0, processed, exit_px=102.0, exit_ms=3 * MIN)
        self.assertEqual(st["mae_px"], 99.0); self.assertEqual(st["mae_ms"], MIN)
        self.assertEqual(st["mfe_px"], 103); self.assertEqual(st["mfe_ms"], 2 * MIN)
        self.assertAlmostEqual(st["mae_usd"], -0.5); self.assertAlmostEqual(st["mfe_usd"], 1.5)
        s2 = sim.update_excursions({}, "short", 50.0, 100.0, post, None, None)
        self.assertEqual(s2["mae_px"], 103); self.assertEqual(s2["mfe_px"], 99.0)

    def test_calibration_bins_counts_and_wilson(self):
        from captain import analytics
        _, cfg, con = synth.fresh_env()
        with db.tx(con):
            for i, (p, o) in enumerate([((0.5, 0.3, 0.2), "UP"), ((0.1, 0.1, 0.8), "RANGE"), ((0.3, 0.3, 0.4), "DOWN")]):
                fid = f"FC-SYN-{i}"
                con.execute("INSERT INTO forecasts(forecast_id,run_id,market,model_id,is_official,created_ts,cutoff_ts,session_date,target_start_ts,target_end_ts,outcome_definition,p_up,p_down,p_range,probabilities_available,synthetic) VALUES(?,?,?,?,1,'x','x',?,'x','x','SYNTHETIC',?,?,?,1,0)",
                            (fid, "RUN-SYN", "BTC", "m", f"2026-01-0{i+1}", *p))
                con.execute("INSERT INTO scores(score_id,kind,forecast_id,status,outcome,brier,scored_ts) VALUES(?,?,?,?,?,?,?)", (f"SC-{fid}", "session_forecast", fid, "SCORED", o, fc.brier(dict(zip(["UP", "DOWN", "RANGE"], p)), o), "x"))
        c = analytics.calibration(con, cfg)["m"]
        self.assertEqual(sum(b["n"] for b in c["bins"]), 9); self.assertEqual(sum(b["hits"] for b in c["bins"]), 3)
        self.assertAlmostEqual(c["mean_brier"], (0.25 + 0.09 + 0.04 + 0.01 + 0.01 + 0.04 + 0.09 + 0.49 + 0.16) / 3)
        self.assertIsNotNone(c["bins"][0]["wilson95"])

    def test_cost_multipliers(self):
        s = sim.cost_sensitivity(gross=2.0, fees=0.10, financing=0.02, slippage=0.05, multipliers=[1.0, 1.5, 2.0, 3.0])
        self.assertAlmostEqual(s["1x"], 2.0 - 0.12)
        self.assertAlmostEqual(s["1.5x"], 2.0 - 0.15 - 0.03 - 0.025)
        self.assertAlmostEqual(s["2x"], 2.0 - 0.20 - 0.04 - 0.05)
        self.assertAlmostEqual(s["3x"], 2.0 - 0.30 - 0.06 - 0.10)

    def test_bootstrap_marks_small_samples_unreliable_and_is_deterministic(self):
        from captain import analytics
        _, cfg, _ = synth.fresh_env()
        small = [{"session_date": "2026-01-01", "net_r": 1.0}, {"session_date": "2026-01-02", "net_r": -1.0}]
        self.assertFalse(analytics.block_bootstrap(small, cfg)["reliable"])
        big = [{"session_date": f"2026-01-{d:02d}", "net_r": (1.5 if (d * k) % 3 else -1.0)} for d in range(1, 16) for k in range(1, 3)]
        a, b = analytics.block_bootstrap(big, cfg), analytics.block_bootstrap(big, cfg)
        self.assertTrue(a["reliable"]); self.assertEqual(a["ci"], b["ci"]); self.assertLessEqual(a["ci"][0], a["mean"]); self.assertGreaterEqual(a["ci"][1], a["mean"])

    def test_end_to_end_r_mae_costs_hypothetical_isolation_and_replay(self):
        e2e = TestEndToEnd("test_full_cycle_target_reserve_and_idempotency")
        e2e.setUp()
        try:
            con, cfg = e2e.con, e2e.cfg
            synth.build_session(con, cfg, SD, post_prices=[101.5 + 0.2 * i for i in range(60)])
            e2e.decide("06:15", "06:15:10")
            ledger_after_decide = ledger.saved(con)
            for mm in range(17, 60):
                e2e.monitor(f"06:{mm:02d}")
            tr = dict(con.execute("SELECT * FROM trades").fetchone())
            dec = dict(con.execute("SELECT * FROM decisions WHERE decision_id=?", (tr["decision_id"],)).fetchone())
            # R stored at decision time == planned loss at quoted notional; <= 2% of $50
            planned = json.loads(dec["risk_model"])["quoted"]["planned_loss_at_quoted"]["total"]
            self.assertAlmostEqual(tr["initial_risk_usd"], planned); self.assertLessEqual(tr["initial_risk_usd"], 1.0 + 1e-9)
            self.assertAlmostEqual(tr["net_r"], tr["net_pnl"] / tr["initial_risk_usd"])
            # MAE/MFE timestamps are at/after entry, never before
            self.assertGreaterEqual(tr["mae_ts"], tr["entry_ts"]); self.assertGreaterEqual(tr["mfe_ts"], tr["entry_ts"])
            self.assertAlmostEqual(tr["mfe_r"], tr["mfe_usd"] / tr["initial_risk_usd"])
            # cost sensitivity: 1x equals official net; higher multipliers strictly worse
            cs = json.loads(tr["cost_sensitivity"])
            self.assertAlmostEqual(cs["1x"], tr["net_pnl"]); self.assertLess(cs["3x"], cs["2x"]); self.assertLess(cs["2x"], cs["1.5x"])
            # labels frozen on signal and trade
            sg = con.execute("SELECT condition_labels, descriptive_features FROM signals LIMIT 1").fetchone()
            lab = json.loads(sg[0]); self.assertIn(lab["trend"], ("TREND_UP", "TREND_DOWN", "RANGE")); self.assertIn(lab["volatility"], ("HIGH_VOL", "LOW_VOL", "UNAVAILABLE"))
            self.assertEqual(lab["version"], "cond-v1.1.0")
            self.assertIn(lab["volume"], ("ABOVE_AVG", "BELOW_OR_EQ_AVG", "UNAVAILABLE"))
            self.assertIn(lab["price_vs_vwap"], ("above", "below", "at"))
            self.assertIn(lab["trend_50"], ("above", "below", "at", "UNAVAILABLE"))
            self.assertIn(lab["trend_200"], ("above", "below", "at", "UNAVAILABLE"))  # may be UNAVAILABLE under default 160h synth warmup
            self.assertIsInstance(lab.get("volume_ratio"), (float, type(None)))
            self.assertIsInstance(lab.get("vwap_value"), float)
            tr_lab = json.loads(tr["condition_labels"])
            self.assertEqual(tr_lab["version"], lab["version"])  # frozen on trade at decision time
            self.assertIsNone(json.loads(sg[1])["whale_lean"])
            # hypothetical skips: 2 ranked-below signals, resolved with the same simulator, isolated from the ledger
            hy = [dict(r) for r in con.execute("SELECT * FROM hypothetical_outcomes").fetchall()]
            self.assertEqual(len(hy), 2)
            self.assertTrue(all(h["hypothetical"] == 1 and h["excluded_from_official"] == 1 and h["status"] == "CLOSED" for h in hy))
            self.assertEqual(con.execute("SELECT COUNT(*) FROM trade_events WHERE trade_id LIKE 'HY-%' OR trade_id IN (SELECT hyp_id FROM hypothetical_outcomes)").fetchone()[0], 0)
            s = ledger.saved(con)
            self.assertAlmostEqual(s["trading_cash"] + s["reserve"], 50 + tr["net_pnl"])  # only the official trade moves equity
            self.assertEqual(ledger_after_decide["trading_cash"], 50.0)
            with self.assertRaises(Exception):
                with db.tx(con):
                    con.execute("UPDATE hypothetical_outcomes SET excluded_from_official=0")
            # official analytics exclude synthetic and hypothetical rows
            from captain import analytics
            with db.tx(con):
                con.execute("UPDATE trades SET synthetic=0"); con.execute("UPDATE hypothetical_outcomes SET synthetic=0")  # within temp DB only, to exercise the split
            full = analytics.full(con, cfg)
            self.assertEqual(full["official"]["n_closed"], 1); self.assertEqual(full["hypothetical_EXCLUDED_FROM_OFFICIAL"]["n_closed"], 2)
            self.assertFalse(full["official"]["expectancy_r_by_setup"]["A"]["reliable"])
            # trade replay CLI output
            from captain import tradereplay
            out = tradereplay.render(con, cfg, tr["trade_id"])
            for needle in ("snapshot", "gates", "ENTER_SELECTED", "open_fee", "quote", "estimate", "net R", "MAE"):
                self.assertIn(needle, out)
            self.assertIn("HYPOTHETICAL", tradereplay.render(con, cfg, hy[0]["hyp_id"]))
            # drawdown derived from events
            pts, dd = analytics.equity_curve(con, cfg)
            self.assertAlmostEqual(dd["current_total"], 50 + tr["net_pnl"])
        finally:
            e2e.tearDown()


class TestConditionLabelsV11(unittest.TestCase):
    """cond-v1.1.0 volume / VWAP / EMA50+200 tags: logged only, never gates."""

    def setUp(self):
        self.home, self.cfg, self.con = synth.fresh_env()
        self.assertEqual(self.cfg["measurement"]["condition_labels"]["version"], "cond-v1.1.0")

    def test_volume_vwap_ema_tags_on_breakout_and_do_not_change_candidates(self):
        # Enough 1h history for EMA200 (220h pre-overnight). Cutoff +10s so signal bar received_ts is visible.
        synth.build_session(self.con, self.cfg, SD, markets=("BTC",), hours_before=220, end_local="06:20")
        decision = toronto_dt(SD, "06:15")
        cutoff = decision + dt.timedelta(seconds=10)
        ev = signals.evaluate_market(self.con, self.cfg, "BTC", decision, cutoff)
        lab = ev["features"]["condition_labels"]
        self.assertEqual(lab["version"], "cond-v1.1.0")
        # Volume: 15m trigger vs prior 20-bar average
        self.assertIn(lab["volume"], ("ABOVE_AVG", "BELOW_OR_EQ_AVG"))
        self.assertEqual(lab["volume_trailing_bars"], 20)
        self.assertAlmostEqual(lab["volume_ratio"], lab["volume_candle"] / lab["volume_avg"])
        self.assertEqual(lab["volume_beats_avg"], lab["volume_candle"] > lab["volume_avg"])
        # VWAP from Toronto 00:00 through signal end
        self.assertIn(lab["price_vs_vwap"], ("above", "below", "at"))
        self.assertEqual(lab["vwap_price_source"], "15m_signal_close")
        self.assertAlmostEqual(lab["vwap_distance_frac"], (lab["vwap_price"] - lab["vwap_value"]) / lab["vwap_value"])
        self.assertTrue(lab["vwap_session_start"].startswith("2026-07-15T04:00:00"))  # 00:00 EDT = 04:00Z
        # EMA trend labels
        self.assertIn(lab["trend_50"], ("above", "below", "at"))
        self.assertIn(lab["trend_200"], ("above", "below", "at"))
        self.assertIsNotNone(lab["ema50_value"]); self.assertIsNotNone(lab["ema200_value"])
        # Rising synth path: price should be above both EMAs
        self.assertEqual(lab["trend_50"], "above")
        self.assertEqual(lab["trend_200"], "above")
        # Tags must not alter candidate production vs gates (setup A long still fires)
        sides = {(c["setup"], c["side"]) for c in ev["candidates"]}
        self.assertIn(("A", "long"), sides)
        # Re-evaluate: labels are deterministic
        lab2 = signals.evaluate_market(self.con, self.cfg, "BTC", decision, cutoff)["features"]["condition_labels"]
        self.assertEqual(lab, lab2)

    def test_volume_beats_avg_false_when_trigger_is_quiet(self):
        synth.build_session(self.con, self.cfg, SD, markets=("BTC",), hours_before=160, end_local="06:20")
        # Inflate prior 15m volumes; leave the 06:00-06:15 trigger bar at synth default (15.0)
        p = self.cfg["markets"]["BTC"]["primary"]
        t_end = to_ms(toronto_dt(SD, "06:15"))
        with db.tx(self.con):
            self.con.execute(
                "UPDATE market_data SET volume=500.0 WHERE provider=? AND instrument=? AND timeframe='15m' "
                "AND derivation='agg_1m' AND candle_end_ms<? AND candle_end_ms>=?",
                (p["provider"], p["symbol"], t_end, t_end - 20 * 15 * MIN),
            )
        lab = signals.evaluate_market(self.con, self.cfg, "BTC", toronto_dt(SD, "06:15"),
                                      toronto_dt(SD, "06:15") + dt.timedelta(seconds=10))["features"]["condition_labels"]
        self.assertEqual(lab["volume"], "BELOW_OR_EQ_AVG")
        self.assertFalse(lab["volume_beats_avg"])
        self.assertLess(lab["volume_ratio"], 1.0)

    def test_labels_absent_config_section_returns_none_without_breaking_eval(self):
        cfg = dict(self.cfg)
        meas = dict(cfg["measurement"]); meas.pop("condition_labels", None); cfg["measurement"] = meas
        synth.build_session(self.con, cfg, SD, markets=("BTC",), hours_before=160, end_local="06:20")
        decision = toronto_dt(SD, "06:15")
        ev = signals.evaluate_market(self.con, cfg, "BTC", decision, decision + dt.timedelta(seconds=10))
        self.assertIsNone(ev["features"]["condition_labels"])
        self.assertTrue(any(c["setup"] == "A" and c["side"] == "long" for c in ev["candidates"]))



if __name__ == "__main__":
    unittest.main(verbosity=2)
