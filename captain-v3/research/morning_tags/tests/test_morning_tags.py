"""Unit tests for morning tags (synthetic data only; never touches the real captain.db)."""
import datetime as dt, json, os, sqlite3, tempfile, unittest
from research.morning_tags import tags as T, run as R
from research.morning_tags.data import et_ms, iso, M1, M15, H1


class Pure(unittest.TestCase):
    def test_candle_shape_clean(self):
        s = T.candle_shape(100, 110, 99, 109)  # up, body 9/11, upper wick 1/11
        self.assertEqual(s["dir"], "up"); self.assertTrue(s["clean"])
        self.assertAlmostEqual(s["opposing_wick_frac"], 1 / 11); self.assertAlmostEqual(s["close_loc"], 10 / 11)

    def test_candle_shape_not_clean_big_opposing_wick(self):
        s = T.candle_shape(100, 110, 99, 104)  # up but long upper wick 6/11
        self.assertFalse(s["clean"])
        d = T.candle_shape(109, 110, 99, 100)  # down, lower wick 1/11, body 9/11
        self.assertEqual(d["dir"], "down"); self.assertTrue(d["clean"]); self.assertAlmostEqual(d["opposing_wick_frac"], 1 / 11)

    def test_flat_and_zero_range(self):
        self.assertFalse(T.candle_shape(100, 100, 100, 100)["clean"])
        self.assertFalse(T.candle_shape(100, 101, 99, 100)["clean"])

    def test_range_vs_median_needs_min_days(self):
        self.assertEqual(T.range_vs_median(2, [1] * 9, 10)[0], None)
        r, n, med = T.range_vs_median(2, [1] * 10 + [None, 0], 10)
        self.assertEqual((r, n, med), (2.0, 10, 1))

    def test_session_profile_mapping(self):
        self.assertEqual(T.session_profile("up", "down"), (True, "continuation_day"))
        self.assertEqual(T.session_profile("up", "up"), (False, "reversal_day"))
        self.assertEqual(T.session_profile("flat", "up"), (None, None))

    def test_fvg_bullish_unfilled_and_filled(self):
        mk = lambda i, o, h, l, c: {"start": i * H1, "o": o, "h": h, "l": l, "c": c}
        bars = [mk(0, 100, 101, 99, 100.5), mk(1, 100.5, 105, 100.4, 104.8), mk(2, 104.8, 106, 102, 105.5), mk(3, 105.5, 106, 103, 104)]
        g = T.find_fvgs(bars, 0, 10 * H1)
        self.assertEqual(len(g), 1); self.assertEqual((g[0]["type"], g[0]["low"], g[0]["high"]), ("bullish", 101, 102)); self.assertFalse(g[0]["filled"])
        bars.append(mk(4, 104, 104, 100.9, 101))
        self.assertTrue(T.find_fvgs(bars, 0, 10 * H1)[0]["filled"])
        self.assertEqual(T.find_fvgs(bars, 3 * H1, 10 * H1), [])  # formation window excludes it
        d = T.fvg_distance(g[0], 104, 2.0)
        self.assertEqual(d["position"], "below_price"); self.assertAlmostEqual(d["dist_pct"], -2 / 104 * 100); self.assertAlmostEqual(d["dist_atr"], -1.0)

    def test_fvg_bearish_and_min_gap(self):
        mk = lambda i, h, l: {"start": i * H1, "o": l, "h": h, "l": l, "c": l}
        bars = [mk(0, 101, 100), mk(1, 100, 98), mk(2, 99.95, 97)]
        g = T.find_fvgs(bars, 0, 10 * H1)
        self.assertEqual(g[0]["type"], "bearish"); self.assertEqual((g[0]["low"], g[0]["high"]), (99.95, 100))
        self.assertEqual(T.find_fvgs(bars, 0, 10 * H1, min_gap_pct=0.1), [])

    def test_atr_wilder(self):
        bars = [(10, 11, 9, 10)] * 20
        self.assertAlmostEqual(T.atr_wilder(bars, 14), 2.0)
        self.assertIsNone(T.atr_wilder(bars[:14], 14))

    def _b(self, h, l, c):
        return {"h": h, "l": l, "c": c}

    def test_cross_asset_labels(self):
        per = {"BTC": {"level": 100, "pre": [self._b(99, 98, 99), self._b(101, 99, 100.5)], "next": self._b(101, 99, 100.2)},
               "ETH": {"level": 10, "pre": [self._b(9.9, 9.8, 9.9), self._b(10.3, 9.9, 10.2)], "next": self._b(10.2, 9.9, 9.95)},
               "SOL": {"level": 50, "pre": [self._b(49, 48, 49), self._b(49.9, 49, 49.5)], "next": self._b(49.8, 49, 49.5)}}
        r = T.cross_asset("BTC", "up", per)
        self.assertEqual(r["confirm_label"], "partial"); self.assertEqual(r["n_confirm"], 1)
        self.assertEqual(r["strongest"], "ETH")          # 3% beyond vs BTC 1%
        self.assertTrue(r["strength_switch"])            # ETH next bar closed back under 10
        per["SOL"]["next"] = self._b(50.5, 49.5, 50.4)
        self.assertEqual(T.cross_asset("BTC", "up", per)["confirm_label"], "all_confirm")
        self.assertEqual(T.cross_asset("BTC", "up", per)["confirm_at_signal"], "partial")  # SOL only breaks in the next bar

    def test_cross_asset_diverge_down_and_pending(self):
        per = {"BTC": {"level": 100, "pre": [self._b(101, 100.5, 101), self._b(101, 99, 99.5)], "next": None},
               "ETH": {"level": 10, "pre": [self._b(10.2, 10.1, 10.1), self._b(10.2, 10.05, 10.1)], "next": None},
               "SOL": {"level": 50, "pre": [self._b(51, 50.5, 51), self._b(51, 50.2, 50.3)], "next": None}}
        r = T.cross_asset("BTC", "down", per)
        self.assertEqual(r["confirm_at_signal"], "diverge"); self.assertIsNone(r["confirm_label"]); self.assertFalse(r["complete"])
        self.assertIsNone(r["strength_switch"])


def _synth_db(path, late_received_after=None, spike_after_six=True):
    """Three markets of 1m + 15m agg bars for 2026-10-01..2026-10-03 (Toronto)."""
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE market_data(id INTEGER PRIMARY KEY, provider,instrument,timeframe,derivation,candle_start_ms,candle_end_ms,open,high,low,close,volume,received_ts,is_final,raw_ref,synthetic)")
    s0 = et_ms(dt.date(2026, 9, 30), "00:00"); s1 = et_ms(dt.date(2026, 10, 3), "12:00")
    six = et_ms(dt.date(2026, 10, 2), "06:00")
    rows = []
    for sym, base in (("BTCUSDT", 100.0), ("ETHUSDT", 10.0), ("SOLUSDT", 50.0)):
        m1 = []
        for t in range(s0, s1, M1):
            k = (t - s0) // M1
            o = base * (1 + 0.001 * ((k % 240) / 240))
            c_ = o * 1.0001
            h, l = max(o, c_) * 1.0002, min(o, c_) * 0.9998
            if spike_after_six and six <= t < six + 30 * M1:
                h *= 1.05  # big move AFTER 06:00 must never leak into the 06:00 tag
            recv = iso(t + M1 + 3000)
            if late_received_after is not None and t >= late_received_after:
                recv = iso(t + 3 * 86400_000)
            m1.append((t, o, h, l, c_, recv))
            rows.append(("binance_spot", sym, "1m", "native_1m", t, t + M1, o, h, l, c_, 1, recv, 1, None, 0))
        for i in range(0, len(m1) - 14, 15):
            g = m1[i:i + 15]
            rows.append(("binance_spot", sym, "15m", "agg_1m", g[0][0], g[0][0] + M15, g[0][1], max(x[2] for x in g), min(x[3] for x in g), g[-1][4], 1, max(x[5] for x in g), 1, None, 0))
    c.executemany("INSERT INTO market_data(provider,instrument,timeframe,derivation,candle_start_ms,candle_end_ms,open,high,low,close,volume,received_ts,is_final,raw_ref,synthetic) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    c.execute("CREATE TABLE signals(signal_id,market,setup,side,trigger_bar_end_ts,synthetic)")
    c.execute("CREATE TABLE hypothetical_outcomes(hyp_id,signal_id,status,net_r,side,synthetic)")
    c.execute("CREATE TABLE trades(trade_id,decision_id,status,net_r,side,synthetic)")
    c.execute("CREATE TABLE decisions(decision_id,signal_id)")
    t0 = iso(et_ms(dt.date(2026, 10, 2), "06:15"))
    c.execute("INSERT INTO signals VALUES('SG-1','BTC','A','long',?,0)", (t0,))
    c.execute("INSERT INTO hypothetical_outcomes VALUES('HY-1','SG-1','CLOSED',-0.5,'long',0)")
    c.commit(); c.close()


class Integration(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory(); self.src = os.path.join(self.d.name, "c.db"); self.tags = os.path.join(self.d.name, "t.db")
        self.cfg = R.load_cfg(); self.cfg["candle_6am"]["range_median_min_days"] = 1
        self.now = et_ms(dt.date(2026, 10, 3), "12:00")

    def tearDown(self):
        self.d.cleanup()

    def _run(self, now=None):
        return R.run(self.cfg, now=now or self.now, src_db=self.src, mm_db=os.path.join(self.d.name, "none.db"), tags_db=self.tags, log=lambda *a: None)

    def test_no_lookahead_idempotent_and_readonly_source(self):
        _synth_db(self.src)
        self._run()
        c = sqlite3.connect(self.tags)
        r = c.execute("SELECT status,knowledge,c4_high,c4_close,c4_source FROM daily_tags WHERE session_date='2026-10-02' AND asset='BTC'").fetchone()
        self.assertEqual(r[0], "ok"); self.assertEqual(r[1], "live"); self.assertEqual(r[4], "1m")
        self.assertLess(r[2], 100 * 1.01)  # the +5% spike after 06:00 is not in the 02:00-06:00 candle
        ev = c.execute("SELECT status, confirm_label, knowledge FROM event_tags WHERE source='v3_hypothetical' AND record_id='HY-1'").fetchone()
        self.assertEqual(ev[0], "ok"); self.assertEqual(ev[1], "all_confirm")
        before = c.execute("SELECT COUNT(*), MAX(computed_ts) FROM daily_tags").fetchone(); c.close()
        self.assertEqual(self._run(), (0, 0))  # second run: nothing rewritten
        c = sqlite3.connect(self.tags); self.assertEqual(c.execute("SELECT COUNT(*), MAX(computed_ts) FROM daily_tags").fetchone(), before); c.close()
        ro = R.connect_ro(self.src)
        with self.assertRaises(sqlite3.OperationalError):
            ro.execute("DELETE FROM market_data")

    def test_late_received_is_reconstructed(self):
        _synth_db(self.src, late_received_after=et_ms(dt.date(2026, 10, 2), "05:00"))
        self._run()
        c = sqlite3.connect(self.tags)
        self.assertEqual(c.execute("SELECT knowledge FROM daily_tags WHERE session_date='2026-10-02' AND asset='ETH'").fetchone()[0], "reconstructed")
        self.assertEqual(c.execute("SELECT knowledge FROM daily_tags WHERE session_date='2026-10-01' AND asset='ETH'").fetchone()[0], "live")

    def test_not_written_before_0601_and_event_pending(self):
        _synth_db(self.src)
        self._run(now=et_ms(dt.date(2026, 10, 2), "06:16"))
        c = sqlite3.connect(self.tags)
        self.assertIsNone(c.execute("SELECT 1 FROM daily_tags WHERE session_date='2026-10-03'").fetchone())
        self.assertEqual(c.execute("SELECT status FROM event_tags WHERE record_id='HY-1'").fetchone()[0], "pending")  # next bar not closed
        c.close()
        self._run(now=et_ms(dt.date(2026, 10, 2), "06:32"))
        c = sqlite3.connect(self.tags)
        self.assertEqual(c.execute("SELECT status FROM event_tags WHERE record_id='HY-1'").fetchone()[0], "ok")

    def test_break_dir_mapping(self):
        self.assertEqual(R.v3_break_dir("A", "long"), "up"); self.assertEqual(R.v3_break_dir("A", "short"), "down")
        self.assertEqual(R.v3_break_dir("B", "short"), "up"); self.assertEqual(R.v3_break_dir("B", "long"), "down")


if __name__ == "__main__":
    unittest.main()
