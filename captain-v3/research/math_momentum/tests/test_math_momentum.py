"""Unit tests for the math-momentum shadow module only (synthetic inputs; never touches captain.db)."""
import datetime as dt, os, sqlite3, tempfile, unittest
import numpy as np
from research.math_momentum import data as D, features as F, persistence as PZ, probability as PR, uncertainty as UC
from research.math_momentum import ev as EV, joint_state as JS, switching as SW, opportunity as OP, evaluation as EVL, null_test as NT


class T(unittest.TestCase):
    def test_cutoff_is_last_completed_block(self):
        now = dt.datetime(2026, 10, 10, 22, 29, 59, tzinfo=dt.timezone.utc)
        self.assertEqual(D.completed_block_cutoff(now), dt.datetime(2026, 10, 10, 22, 15, tzinfo=dt.timezone.utc))
        now = dt.datetime(2026, 10, 10, 22, 30, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(D.completed_block_cutoff(now), dt.datetime(2026, 10, 10, 22, 30, tzinfo=dt.timezone.utc))

    def test_load_bars_is_timestamp_safe(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.db"); c = sqlite3.connect(p)
            c.execute("CREATE TABLE market_data(provider,instrument,timeframe,derivation,candle_start_ms,candle_end_ms,open,high,low,close,volume,received_ts,is_final,synthetic)")
            rows = [("b", "S", "1m", "native_1m", 0, 60000, 1, 1, 1, 1, 1, "1970-01-01T00:01:02.000Z", 1, 0),
                    ("b", "S", "1m", "native_1m", 60000, 120000, 2, 2, 2, 2, 1, "1970-01-01T00:02:02.000Z", 1, 0),   # closes after cutoff
                    ("b", "S", "1m", "native_1m", -60000, 0, 3, 3, 3, 3, 1, "1970-01-01T00:05:00.000Z", 1, 0)]       # received late
            c.executemany("INSERT INTO market_data VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows); c.commit(); c.close()
            ro = D.connect_ro(p)
            b = D.load_bars(ro, "b", "S", "1m", "native_1m", 60000, "1970-01-01T00:02:00.000Z")
            self.assertEqual(b["n"], 1); self.assertEqual(b["c"][0], 1)
            with self.assertRaises(sqlite3.OperationalError):
                ro.execute("INSERT INTO market_data(provider) VALUES('x')")

    def test_agg_15m_requires_complete_blocks(self):
        start = np.arange(0, 30 * 60000, 60000, dtype=np.int64)
        b1 = {"n": 30, "start": start, "end": start + 60000, "o": np.arange(30.), "h": np.arange(30.) + 1, "l": np.arange(30.) - 1,
              "c": np.arange(30.) + 0.5, "v": np.ones(30)}
        b1["start"] = np.delete(b1["start"], 20); [b1.__setitem__(k, np.delete(b1[k], 20)) for k in ("end", "o", "h", "l", "c", "v")]
        k = F.agg_15m(b1, np.array([900000, 1800000], dtype=np.int64))
        self.assertEqual(k["o"][0], 0); self.assertEqual(k["c"][0], 14.5); self.assertEqual(k["v"][0], 15)
        self.assertTrue(np.isnan(k["c"][1]))

    def test_norm_uses_training_rows_only_and_winsorizes(self):
        X = np.array([[0.], [1.], [2.], [1000.]])
        med, mad = F.fit_norm(X, np.array([True, True, True, False]))
        self.assertEqual(med[0], 1.0)
        Z = F.apply_norm(X, med, mad, 3.0)
        self.assertEqual(Z[3, 0], 3.0)

    def test_classify_band(self):
        y = PR.classify(np.array([0.003, 0.001, -0.003, np.nan]), 0.0025)
        self.assertEqual(y.tolist(), [0, 1, 2, -1])

    def test_softmax_ridge_learns_signal(self):
        rng = np.random.default_rng(0); x = rng.normal(size=3000)
        y = np.where(x > 0.8, 0, np.where(x < -0.8, 2, 1))
        X = np.column_stack([x, np.ones_like(x)])
        W = PR.fit_softmax_ridge(X, y, 1.0)
        P = PR.softmax(X @ W)
        self.assertGreater((P.argmax(1) == y).mean(), 0.85)
        self.assertTrue(np.allclose(P.sum(1), 1))

    def test_conformal_and_wilson(self):
        q = UC.conformal_quantile(np.linspace(0, 1, 101), 0.1)
        self.assertAlmostEqual(q, 0.91, places=6)
        self.assertEqual(UC.conformal_set(np.array([0.95, 0.04, 0.01]), 0.5), ["UP"])
        self.assertEqual(len(UC.conformal_set(np.array([0.4, 0.3, 0.3]), 0.9)), 3)
        lo, hi = UC.wilson(5, 10); self.assertTrue(0 < lo < 0.5 < hi < 1)

    def test_ballistic_bounds(self):
        n = 200; c = np.exp(np.linspace(0, 0.1, n))
        f = {"close": c, "dEMA50_1h": np.ones(n), "dVWAP": np.ones(n), "sigma15": np.full(n, 0.001)}
        lc = np.log(c)
        for name, k in (("r15m", 1), ("r30m", 2), ("r1h", 4), ("r2h", 8), ("r4h", 16)):
            f[name] = F.lagret(lc, k)
        B, E, BP = PZ.ballistic(f, {"15m": 1, "30m": 2, "1h": 4, "2h": 8, "4h": 16}, 16)
        self.assertAlmostEqual(E[-1], 1.0); self.assertTrue(0.5 < BP[-1] <= 1.0)

    def test_ev_and_costs(self):
        q = {"positionSizeUsd": 50.0, "inputToCollateralDiffUsd": 0.01,
             "fees": {"openFeeUsd": 0.03, "openPriceImpactFeeUsd": 0.005, "network": {"transactionFeeUsd": 0.002},
                      "closeFee": {"baseFeeUsd": 0.03, "priceImpactFeeUsd_assumed": 0.005}, "borrow": {"hourlyRatePct": 0.0014}}}
        ecfg = {"hold_hours": 0.25, "modeled_adverse_slippage_bps_per_side": 5, "stress_close_multiplier": 2.0, "stress_financing_multiplier": 3.0}
        c = EV.cost_breakdown(q, ecfg)
        self.assertAlmostEqual(c["modeled_slippage"], 0.05)
        self.assertGreater(c["total_stressed"], c["total_base"])
        stats = [{"mean": 0.004, "se": 0.0002}, {"mean": 0.0, "se": 0.00002}, {"mean": -0.004, "se": 0.0002}]
        e = EV.ev_surface(np.array([0.1, 0.8, 0.1]), stats, 1.0, 50.0, c["total_stressed"], c["total_stressed"], 300, 1.645)
        self.assertAlmostEqual(e["gross_long_usd"], 0.0, places=9)
        self.assertLess(e["ev_long_lcb"], e["ev_long_net"]); self.assertEqual(e["ev_wait"], 0.0)

    def test_joint_states_27_and_limit(self):
        Sig = np.eye(3) * 1e-6
        st = JS.enumerate_states([0.003, -0.001, -0.001], [-0.001] * 3, Sig, 10, 0, 0.5)
        self.assertEqual(len(st), 27)
        best = next(s for s in st if s["feasible"]); self.assertEqual(best["state"], [1, 0, 0])
        self.assertTrue(all(sum(map(abs, s["state"])) <= 1 for s in st if s["feasible"]))
        S2 = JS.stress_corr(np.array([[1, 0.2, 0], [0.2, 1, 0], [0, 0, 1.]]), 0.5)
        self.assertAlmostEqual(S2[0, 1], 0.6)

    def test_switching_and_q(self):
        self.assertFalse(SW.switch_decision(-0.1, 0.0, 0.0, 0.01)["passes"])
        self.assertTrue(SW.switch_decision(0.05, 0.0, 0.0, 0.01)["passes"])
        self.assertLess(OP.q_score(-0.1, 0.5, 0.2, 1.0, 1.0), 0)
        self.assertEqual(OP.calib_quality(0.2), 0.0)

    def test_neff_and_null(self):
        rng = np.random.default_rng(1); x = rng.normal(size=2000)
        ne, _ = EVL.n_eff(x); self.assertGreater(ne, 1500)
        ar = np.zeros(2000)
        for i in range(1, 2000):
            ar[i] = 0.9 * ar[i - 1] + rng.normal()
        self.assertLess(EVL.n_eff(ar)[0], 400)
        y = rng.integers(0, 3, 300)
        self.assertGreater(NT.fixed_margin_accuracy_test(rng.permutation(y), y, 200)["p_null"], 0.01)
        self.assertLess(NT.fixed_margin_accuracy_test(y.copy(), y, 200)["p_null"], 0.01)


if __name__ == "__main__":
    unittest.main()
