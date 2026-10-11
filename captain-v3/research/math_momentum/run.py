"""Run ONE math-momentum shadow block for the most recently completed 15m block (paper only).

    cd /workspace/captain-v3 && python3 -m research.math_momentum.run [--offline-quotes] [--dry-run]

Reads captain.db read-only (sqlite URI mode=ro). Writes only research/math_momentum/shadow.db and records/<run_id>.json.
Never imports or alters captain/* code, config v3.1.1, or official tables. No keys, signatures, swaps or orders."""
import argparse, datetime as dt, glob, hashlib, json, math, os, sqlite3, sys
import numpy as np

from .data import (M1, M15, H1, TZ, UTC, iso, from_ms, to_ms, toronto_str, completed_block_cutoff, connect_ro, load_bars,
                   excluded_after_cutoff)
from . import features as F, persistence as PZ, probability as PR, uncertainty as UC, ev as EV
from . import joint_state as JS, switching as SW, opportunity as OP, null_test as NT, evaluation as EVL

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CFG_PATH = os.path.join(ROOT, "config", "math-momentum-v1.0.0.json")
DAY = 86_400_000


def sha(s):
    return hashlib.sha256(s.encode() if isinstance(s, str) else s).hexdigest()


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), default=lambda x: None if (isinstance(x, float) and not math.isfinite(x)) else str(x))


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        f = float(o); return f if math.isfinite(f) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    return o


def code_hash():
    h = hashlib.sha256()
    for p in sorted(glob.glob(os.path.join(HERE, "*.py"))):
        h.update(open(p, "rb").read())
    return h.hexdigest()


SHADOW_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, cutoff_ts TEXT NOT NULL UNIQUE, cutoff_toronto TEXT, knowledge_ts TEXT,
  created_ts TEXT, config_version TEXT, config_hash TEXT, code_hash TEXT, training_cutoff_ts TEXT, action TEXT, action_market TEXT,
  decisive_gate TEXT, reason TEXT, record_path TEXT, record_sha256 TEXT, shadow_only INTEGER NOT NULL DEFAULT 1 CHECK(shadow_only=1));
CREATE TABLE IF NOT EXISTS forecasts(forecast_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, market TEXT NOT NULL, horizon TEXT NOT NULL,
  event_ts TEXT, received_ts TEXT, cutoff_ts TEXT, target_end_ts TEXT, training_cutoff_ts TEXT, p_up REAL, p_range REAL, p_down REAL,
  conformal_set TEXT, uphill_score REAL, uphill_slope REAL, ballistic_persistence REAL, model_disagreement REAL, effective_sample_size REAL,
  ev_long_net REAL, ev_short_net REAL, ev_wait REAL, ev_lcb REAL, abstention_reason TEXT, config_version TEXT, features_hash TEXT,
  outcome TEXT, outcome_return REAL, resolved_ts TEXT, UNIQUE(run_id, market, horizon));
CREATE TABLE IF NOT EXISTS alternatives(run_id TEXT NOT NULL, market TEXT NOT NULL, side TEXT NOT NULL, q REAL, ev_lcb REAL, chosen INTEGER,
  failed_gates TEXT, gates TEXT, PRIMARY KEY(run_id, market, side));
CREATE TABLE IF NOT EXISTS joint_states(run_id TEXT NOT NULL, state TEXT NOT NULL, j REAL, mu REAL, var REAL, tail_es95 REAL, feasible INTEGER,
  PRIMARY KEY(run_id, state));
CREATE TABLE IF NOT EXISTS research_position(id INTEGER PRIMARY KEY CHECK(id=1), market TEXT, side TEXT, since_cutoff_ts TEXT, note TEXT);
"""


def open_shadow(path):
    s = sqlite3.connect(path); s.executescript(SHADOW_SCHEMA)
    if s.execute("SELECT COUNT(*) FROM research_position").fetchone()[0] == 0:
        s.execute("INSERT INTO research_position VALUES(1, NULL, 'FLAT', NULL, 'research book starts flat; separate from Captain v3 and Crypto Captain ledgers')")
        s.commit()
    return s


def session_close_samples(hend, hclose, sample_clock_ms_of_day, thr, cutoff_ms):
    """Daily samples at the same Toronto clock time as the cutoff; outcome to the next 12:00 Toronto close."""
    idx = {int(e): i for i, e in enumerate(hend)}
    samples = []
    if len(hend) == 0:
        return samples
    d = from_ms(int(hend[0])).astimezone(TZ).date(); dlast = from_ms(cutoff_ms).astimezone(TZ).date()
    hh, mm = divmod(sample_clock_ms_of_day // 60000, 60)
    while d <= dlast:
        t = to_ms(dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=TZ))
        noon = to_ms(dt.datetime(d.year, d.month, d.day, 12, 0, tzinfo=TZ))
        if noon <= t:
            nd = d + dt.timedelta(days=1); noon = to_ms(dt.datetime(nd.year, nd.month, nd.day, 12, 0, tzinfo=TZ))
        if t <= cutoff_ms and t in idx and (t - 4 * H1) in idx:
            c0 = hclose[idx[t]]; b = float(np.sign(c0 / hclose[idx[t - 4 * H1]] - 1))
            y, r = -1, None
            if noon <= cutoff_ms and noon in idx:
                r = hclose[idx[noon]] / c0 - 1
                y = 0 if r > thr else 2 if r < -thr else 1
            samples.append({"t_ms": t, "end_ms": noon, "resolved_ms": noon, "bucket": b, "y": y, "r": r})
        d += dt.timedelta(days=1)
    return samples


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "captain.db"))
    ap.add_argument("--shadow", default=os.path.join(HERE, "shadow.db"))
    ap.add_argument("--records", default=os.path.join(HERE, "records"))
    ap.add_argument("--offline-quotes", action="store_true", help="skip live read-only quotes; use latest stored real quotes (STALE)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    cfg_text = open(CFG_PATH).read(); cfg = json.loads(cfg_text)
    markets = list(cfg["markets"].keys())
    run_started = dt.datetime.now(UTC)
    cutoff = completed_block_cutoff(run_started); cutoff_ms = to_ms(cutoff)
    grace = cfg["timestamp_safety"]["knowledge_grace_s"]
    knowledge = cutoff + dt.timedelta(seconds=grace); knowledge_iso = iso(knowledge)
    run_id = "MM-" + cutoff.astimezone(TZ).strftime("%Y%m%d-%H%M") + "-v1.0.0"

    shadow = None
    if not a.dry_run:
        shadow = open_shadow(a.shadow)
        if shadow.execute("SELECT 1 FROM runs WHERE cutoff_ts=?", (iso(cutoff),)).fetchone():
            print(json.dumps({"status": "ALREADY_RECORDED", "cutoff": iso(cutoff), "note": "no re-runs / no backfill"})); return 2

    con = connect_ro(a.db)
    # ---------------- data (timestamp-safe) ----------------
    b1, b1h, cb, audit = {}, {}, {}, {}
    for m in markets:
        sym = cfg["markets"][m]
        b1[m] = load_bars(con, "binance_spot", sym, "1m", "native_1m", cutoff_ms, knowledge_iso)
        b1h[m] = load_bars(con, "binance_spot", sym, "1h", "native_1h", cutoff_ms, knowledge_iso, start_ms=cutoff_ms - 420 * DAY)
        cb[m] = load_bars(con, "coinbase_exchange", cfg["secondary_symbols"][m], "1m", "native_1m", cutoff_ms, knowledge_iso,
                          start_ms=cutoff_ms - 2 * H1)
        audit[m] = {"rows_1m_used": b1[m]["n"], "rows_1h_native_used": b1h[m]["n"],
                    "rows_1m_excluded_after_cutoff_or_received_late": excluded_after_cutoff(con, "binance_spot", sym, cutoff_ms, knowledge_iso),
                    "first_1m": iso(from_ms(int(b1[m]["start"][0]))) if b1[m]["n"] else None,
                    "last_1m_end": iso(from_ms(int(b1[m]["end"][-1]))) if b1[m]["n"] else None,
                    "max_received_ts_used": b1[m]["received_max"]}
    g0 = max(int(b1[m]["start"][0]) for m in markets)
    g0 = (g0 // M15 + 1) * M15 + M15
    grid = np.arange(g0, cutoff_ms + 1, M15, dtype=np.int64)
    raw = {m: F.asset_raw(b1[m], b1h[m], grid, cutoff_ms, cfg) for m in markets}
    raw = F.build_panel(raw, markets)
    pc = cfg["persistence"]
    for m in markets:
        B, E, BP = PZ.ballistic(raw[m], pc["horizons_blocks"], pc["efficiency_H_blocks"])
        raw[m]["B"], raw[m]["E"], raw[m]["BP"] = B, E, BP
        rn = np.full(len(grid), np.nan); rn[:-1] = raw[m]["r15m"][1:]
        raw[m]["r_next"] = rn
        raw[m]["y"] = PR.classify(rn, cfg["outcomes"]["15m"]["band_pct"] / 100.0)

    Xu = {m: F.mat(raw[m], F.UPHILL_COLS) for m in markets}
    Xp = {m: F.mat(raw[m], F.PROB_COLS) for m in markets}
    n = len(grid); A = len(markets); w = cfg["features"]["winsor_z"]; kU = cfg["uphill"]["slope_k_blocks"]
    lam = cfg["probability"]["ridge_lambda"]
    SUB = {"price": [0, 1, 2, 3, 4], "regime": [5, 6], "relative": [7, 8]}

    def fit_predict(train_T_max, test_idx_by_asset):
        """Fit normalization + models on rows with T <= train_T_max (labels resolved by then); predict given rows."""
        tr = grid <= train_T_max
        Zp, Zu, U, S, BPs, design, ys, rows = {}, {}, {}, {}, {}, [], [], []
        stats = {}
        for ai, m in enumerate(markets):
            fin_u = np.all(np.isfinite(Xu[m]), axis=1); fin_p = np.all(np.isfinite(Xp[m]), axis=1)
            med_u, mad_u = F.fit_norm(Xu[m], tr & fin_u); med_p, mad_p = F.fit_norm(Xp[m], tr & fin_p)
            Zu[m] = F.apply_norm(Xu[m], med_u, mad_u, w); Zp[m] = F.apply_norm(Xp[m], med_p, mad_p, w)
            U[m], S[m] = F.uphill(Zu[m], kU)
            ok_tr = tr & fin_u & np.isfinite(U[m]) & np.isfinite(S[m])
            stats[m] = {"theta_U": float(np.quantile(U[m][ok_tr], cfg["uphill"]["theta_U_quantile"])),
                        "theta_S": float(np.quantile(S[m][ok_tr], cfg["uphill"]["theta_S_quantile"])),
                        "theta_U_short": float(np.quantile(U[m][ok_tr], cfg["uphill"]["short_quantile"])),
                        "theta_S_short": float(np.quantile(S[m][ok_tr], cfg["uphill"]["short_quantile"])),
                        "median_atr_pct": float(np.nanmedian(raw[m]["atr_pct"][tr])), "norm": {"median": med_u, "mad": mad_u}}
        def design_rows(m, ai, idx):
            Z = Zp[m][idx]; bp = raw[m]["BP"][idx]
            D = np.zeros((len(idx), A)); D[:, ai] = 1.0
            return Z, bp, D
        Xs = {"main": [], "price": [], "regime": [], "relative": []}; Y = []; Aidx = []
        for ai, m in enumerate(markets):
            idx = np.where(tr & np.all(np.isfinite(Zp[m]), axis=1) & np.isfinite(raw[m]["BP"]) & (raw[m]["y"] >= 0))[0]
            Z, bp, D = design_rows(m, ai, idx)
            Xs["main"].append(np.hstack([Z, D])); Xs["price"].append(np.hstack([Z[:, SUB["price"]], D]))
            Xs["regime"].append(np.hstack([Z[:, SUB["regime"]], bp[:, None], D])); Xs["relative"].append(np.hstack([Z[:, SUB["relative"]], D]))
            Y.append(raw[m]["y"][idx]); Aidx.append(np.full(len(idx), ai))
        Y = np.concatenate(Y); Aidx = np.concatenate(Aidx)
        W = {k: PR.fit_softmax_ridge(np.vstack(v), Y, lam) for k, v in Xs.items()}
        base = {m: PR.freq_probs(Y[Aidx == ai]) for ai, m in enumerate(markets)}
        out = {}
        for ai, m in enumerate(markets):
            idx = np.asarray(test_idx_by_asset.get(m, []), dtype=int)
            if len(idx) == 0:
                continue
            Z, bp, D = design_rows(m, ai, idx)
            L = PR.logits(np.hstack([Z, D]), W["main"])
            Pp = PR.softmax(PR.logits(np.hstack([Z[:, SUB["price"]], D]), W["price"]))
            Pg = PR.softmax(PR.logits(np.hstack([Z[:, SUB["regime"]], bp[:, None], D]), W["regime"]))
            Pr = PR.softmax(PR.logits(np.hstack([Z[:, SUB["relative"]], D]), W["relative"]))
            Pb = np.tile(base[m], (len(idx), 1))
            out[m] = {"idx": idx, "logits": L, "P_price": Pp, "P_regime": Pg, "P_relative": Pr, "P_base": Pb,
                      "D": PR.disagreement([Pp, Pg, Pr, Pb]), "U": U[m][idx], "S": S[m][idx], "Zu": Zu[m][idx], "Zp": Zp[m][idx]}
        return out, stats, base, int(len(Y)), W

    # ---------------- walk-forward out-of-fold predictions ----------------
    emb = cfg["timestamp_safety"]["embargo_15m_minutes"] * M1
    nf = cfg["probability"]["walk_forward_folds"]
    folds = []
    for j in range(nf):
        fe = cutoff_ms - (nf - 1 - j) * DAY; fs = fe - DAY
        test = {}
        for m in markets:
            ok = (grid > fs) & (grid <= fe) & (grid + M15 <= cutoff_ms) & np.all(np.isfinite(Xp[m]), axis=1) & np.isfinite(raw[m]["BP"]) & (raw[m]["y"] >= 0)
            test[m] = np.where(ok)[0]
        pred, _, _, ntr, _ = fit_predict(fs - M15 - emb, test)
        folds.append({"j": j, "fs": fs, "fe": fe, "pred": pred, "n_train": ntr})
    oos = {k: [] for k in ("fold", "asset", "T", "logits", "Pb", "D", "y", "r", "Pp", "Pg", "Pr")}
    for f in folds:
        for ai, m in enumerate(markets):
            if m not in f["pred"]:
                continue
            p = f["pred"][m]; idx = p["idx"]
            oos["fold"].append(np.full(len(idx), f["j"])); oos["asset"].append(np.full(len(idx), ai)); oos["T"].append(grid[idx])
            oos["logits"].append(p["logits"]); oos["Pb"].append(p["P_base"]); oos["D"].append(p["D"]); oos["y"].append(raw[m]["y"][idx])
            oos["r"].append(raw[m]["r_next"][idx]); oos["Pp"].append(p["P_price"]); oos["Pg"].append(p["P_regime"]); oos["Pr"].append(p["P_relative"])
    oos = {k: np.concatenate(v) for k, v in oos.items()}
    # rolling temperature (fold j uses folds < j)
    Pcal = np.zeros((len(oos["y"]), 3)); temps = {}
    for j in range(nf):
        mj = oos["fold"] == j; prior = oos["fold"] < j
        T = PR.fit_temperature(oos["logits"][prior], oos["y"][prior]) if j >= 2 else 1.0
        temps[j] = T; Pcal[mj] = PR.softmax(oos["logits"][mj] / T)
    T_live = PR.fit_temperature(oos["logits"], oos["y"])
    Mo = PR.margin(Pcal)
    theta_M = float(np.quantile(Mo, 0.75)); theta_D = float(np.quantile(oos["D"], 0.50))
    alpha = cfg["conformal"]["alpha"]
    scores = 1.0 - Pcal[np.arange(len(oos["y"])), oos["y"]]
    recent = oos["fold"] >= nf - cfg["conformal"]["calibration_folds"]
    q_live = UC.conformal_quantile(scores[recent], alpha)
    fids = list(range(nf))
    cov, ncov, cov_detail = UC.rolling_coverage(fids, {j: scores[oos["fold"] == j] for j in fids}, {j: Pcal[oos["fold"] == j] for j in fids},
                                                {j: oos["y"][oos["fold"] == j] for j in fids}, alpha, cfg["conformal"]["calibration_folds"])
    cov_lo, cov_hi = UC.wilson(cov, ncov)
    conformal_ok = not (cov_hi < 1 - alpha)
    cov_by_asset = {}
    for ai, m in enumerate(markets):
        mm = (oos["asset"] == ai) & (oos["fold"] >= 2)
        # per-asset coverage using the rolling quantiles
        c = 0; nn = 0
        for d in cov_detail:
            sel = (oos["asset"] == ai) & (oos["fold"] == d["fold"])
            c += int((scores[sel] <= d["q"]).sum()); nn += int(sel.sum())
        cov_by_asset[m] = {"coverage": c / nn if nn else None, "n": nn}

    # OOS diagnostics per asset
    diag = {}
    for ai, m in enumerate(markets):
        s = oos["asset"] == ai; y = oos["y"][s]
        br = PR.brier(Pcal[s], y); bb = PR.brier(oos["Pb"][s], y)
        ne, K = EVL.n_eff(br - br.mean()); stab = EVL.n_eff_stability(br)
        diag[m] = {"n_oos": int(s.sum()), "brier_model": float(br.mean()), "brier_baseline": float(bb.mean()),
                   "brier_skill_vs_baseline": float(1 - br.mean() / bb.mean()), "logloss_model": float(PR.logloss(Pcal[s], y).mean()),
                   "logloss_baseline": float(PR.logloss(oos["Pb"][s], y).mean()), "ece_top": PR.ece_top(Pcal[s], y),
                   "class_freq_oos": (np.bincount(y, minlength=3) / len(y)).tolist(), "n_eff": ne, "n_eff_K": K, "n_eff_stability": stab,
                   "oos_dates": len({from_ms(int(t)).astimezone(TZ).date() for t in oos["T"][s]})}
    null = NT.fixed_margin_accuracy_test(Pcal.argmax(axis=1), oos["y"])

    # ---------------- live fit (train labels resolved <= cutoff - embargo) ----------------
    train_T_max = cutoff_ms - M15 - emb
    live_idx = {m: [n - 1] for m in markets}
    pred, ustats, base, n_train, W = fit_predict(train_T_max, live_idx)
    tr = grid <= train_T_max
    ecfg = cfg["ev"]; z = ecfg["z_lcb"]
    # ---------------- costs: live read-only Jupiter quotes; fallback = latest stored real quote (STALE) ----------------
    costs, quotes = {}, {}
    for m in markets:
        for side in ("long", "short"):
            q = None if a.offline_quotes else EV.live_quote(m, side, ecfg)
            if q and q["status"] == "LIVE":
                resp = q["response"]; quotes[(m, side)] = {"status": "LIVE", "quoted_at": resp.get("quotedAt"), "args": q["args"]}
            else:
                st = EV.stored_quote(con, m, side)
                if st is None:
                    quotes[(m, side)] = {"status": "UNAVAILABLE", "error": (q or {}).get("stderr")}; costs[(m, side)] = None; continue
                resp = st["response"]
                quotes[(m, side)] = {"status": "STALE", "quote_id": st["quote_id"], "quoted_at": st["quoted_ts"],
                                     "live_error": (q or {}).get("stderr") if q else "offline mode"}
            notional = ecfg["collateral_usd"] * ecfg["leverage"] if quotes[(m, side)]["status"] == "STALE" else None
            costs[(m, side)] = EV.cost_breakdown(resp, ecfg, notional)
            costs[(m, side)]["entry_price_quote"] = resp.get("entryPriceUsd")

    # ---------------- per-asset live assessment ----------------
    dq_cfg = {"tol": 0.35}
    sess = cfg["risk"]
    loc = cutoff.astimezone(TZ); in_window = (dt.time(6, 0) <= loc.time() <= dt.time(11, 45))
    R15 = np.column_stack([raw[m]["r15m"] for m in markets])
    win = (grid <= cutoff_ms) & np.all(np.isfinite(R15), axis=1)
    Rw = R15[win][-672:]
    Sig, Csample, rbar = JS.shrink_cov(Rw, cfg["joint_state"]["shrinkage_delta"])
    atr_ranks = [float(raw[m]["ATRrank_raw"][-1]) for m in markets]
    stressed = any(r > cfg["joint_state"]["stress_atr_rank"] for r in atr_ranks if r == r)
    SigS = JS.stress_corr(Sig, cfg["joint_state"]["stress_toward_one"]) if stressed else Sig
    assets = {}
    for ai, m in enumerate(markets):
        f = raw[m]; p = pred[m]; t = n - 1
        P = PR.softmax(p["logits"] / T_live)[0]
        cset = UC.conformal_set(P, q_live)
        M = float(PR.margin(P[None, :])[0]); Dm = float(p["D"][0])
        U, S = float(p["U"][0]), float(p["S"][0]); st = ustats[m]
        trend_up = f["dEMA50_1h"][t] >= 0; trend_dn = f["dEMA50_1h"][t] <= 0
        cand = "LONG" if (U > st["theta_U"] and S > st["theta_S"] and trend_up) else "SHORT" if (U < st["theta_U_short"] and S < st["theta_S_short"] and trend_dn) else "NONE"
        # data quality
        last_end = int(b1[m]["end"][-1]) if b1[m]["n"] else None
        need = 96 * 15 + 30
        tail = b1[m]["start"][-need:]
        gaps = int((np.diff(tail) != M1).sum()) if len(tail) > 1 else None
        cb_close = float(cb[m]["c"][-1]) if cb[m]["n"] and int(cb[m]["end"][-1]) == cutoff_ms else None
        bn_close = float(b1[m]["c"][-1]) if last_end == cutoff_ms else None
        disag = abs(bn_close / cb_close - 1) * 100 if (cb_close and bn_close) else None
        feats_live = {c: float(f[c][t]) for c in F.UPHILL_COLS + F.PROB_COLS + ["close", "vwap", "atr_pct", "BP", "B", "E", "trend50", "trend200", "hour_age_min"]}
        dq = {"latest_bar_at_cutoff": last_end == cutoff_ms,
              "no_missing_1m_in_24h_lookback": gaps == 0,
              "secondary_provider_present": cb_close is not None,
              "provider_disagreement_pct": disag,
              "provider_disagreement_ok": disag is not None and disag <= dq_cfg["tol"],
              "features_finite": all(np.isfinite(v) for k, v in feats_live.items() if k not in ("trend200",)),
              "hourly_bar_fresh": np.isfinite(f["hour_age_min"][t]) and f["hour_age_min"][t] <= 60}
        dq["pass"] = all(v for k, v in dq.items() if isinstance(v, (bool, np.bool_)))
        # EV
        sel = np.where(tr & (f["y"] >= 0) & np.isfinite(f["r_next"]))[0]
        cstats = EV.class_stats(f["r_next"][sel], f["y"][sel])
        scale = float(f["atr_pct"][t] / st["median_atr_pct"]) if st["median_atr_pct"] > 0 else 1.0
        ne = diag[m]["n_eff"]
        cl, cs = costs.get((m, "long")), costs.get((m, "short"))
        notional = (cl or cs or {}).get("notional_usd", ecfg["collateral_usd"] * ecfg["leverage"])
        evs = EV.ev_surface(P, cstats, scale, notional, cl["total_stressed"] if cl else float("inf"), cs["total_stressed"] if cs else float("inf"), ne, z)
        evs_base = EV.ev_surface(P, cstats, scale, notional, cl["total_base"] if cl else float("inf"), cs["total_base"] if cs else float("inf"), ne, z)
        # prob LCB gate (per side)
        s_a = oos["asset"] == ai; Pa = Pcal[s_a]; ya = oos["y"][s_a]
        plcb = {}
        for side, k in (("LONG", 0), ("SHORT", 2)):
            near = np.abs(Pa[:, k] - P[k]) <= cfg["probability"]["prob_lcb_window"]
            nn = int(near.sum()); hits = int((ya[near] == k).sum())
            lo, hi = UC.wilson(hits, nn)
            plcb[side] = {"p_cal": float(P[k]), "bin_n": nn, "bin_hits": hits, "wilson_lcb": lo, "base_rate": float(base[m][k]),
                          "passes": nn >= cfg["probability"]["prob_lcb_min_obs"] and lo > base[m][k]}
        sd = float(np.sqrt(SigS[ai, ai]))
        es95_usd = JS.ES95_NORMAL * sd * notional
        cq = OP.calib_quality(diag[m]["ece_top"])
        qstat = {"LONG": quotes.get((m, "long"), {}).get("status"), "SHORT": quotes.get((m, "short"), {}).get("status")}
        opps = {}
        for side, key, cost in (("LONG", "ev_long_lcb", cl), ("SHORT", "ev_short_lcb", cs)):
            dqf = 0.0 if not dq["pass"] or cost is None else (1.0 if qstat[side] == "LIVE" else 0.5)
            lcb = evs[key]
            opps[side] = {"market": m, "side": side, "ev_lcb": lcb, "ev_net": evs["ev_long_net" if side == "LONG" else "ev_short_net"],
                          "es95_usd": es95_usd, "cost_stressed_usd": cost["total_stressed"] if cost else None,
                          "calibration_quality": cq, "data_quality": dqf,
                          "Q": OP.q_score(lcb, es95_usd, cost["total_stressed"], cq, dqf) if cost else float("-inf")}
        planned_loss = notional * f["atr_pct"][t] + max((cl or {}).get("total_stressed", 0), (cs or {}).get("total_stressed", 0))
        assets[m] = {"P": P, "cset": cset, "M": M, "D": Dm, "U": U, "S": S, "cand": cand, "dq": dq, "cstats": cstats, "scale": scale,
                     "ev": evs, "ev_base_costs": evs_base, "plcb": plcb, "opps": opps, "feats": feats_live, "ustats": st,
                     "planned_loss": planned_loss, "notional": notional,
                     "sub": {"price": p["P_price"][0], "regime": p["P_regime"][0], "relative": p["P_relative"][0], "baseline": p["P_base"][0]}}

    # ---------------- joint state (27) ----------------
    mu_l = [assets[m]["opps"]["LONG"]["ev_lcb"] / assets[m]["notional"] for m in markets]
    mu_s = [assets[m]["opps"]["SHORT"]["ev_lcb"] / assets[m]["notional"] for m in markets]
    jc = cfg["joint_state"]
    states = JS.enumerate_states(mu_l, mu_s, SigS, jc["lambda_var"], jc["gamma_turnover"], jc["rho_tail"], (0, 0, 0), sess["max_open_positions"])
    best_any = states[0]; best_feas = next(s for s in states if s["feasible"])
    flat = next(s for s in states if s["state"] == [0, 0, 0])

    # ---------------- gates for every asset/side; candidate = top Q ----------------
    queue = OP.rank([o for m in markets for o in assets[m]["opps"].values()])
    h0 = cfg["switching"]["hysteresis_h0_frac_of_roundtrip"]
    gate_rows = []
    for o in queue:
        m, side = o["market"], o["side"]; s = assets[m]; k = 0 if side == "LONG" else 2
        cost = costs.get((m, side.lower()))
        H = SW.hysteresis(h0 * (cost["total_base"] if cost else 0), atr_ranks[markets.index(m)], s["D"], theta_D, 0)
        sw = SW.switch_decision(o["ev_lcb"], 0.0, 0.0, H)
        g = {"data_quality": bool(s["dq"]["pass"]) and cost is not None,
             "ev_lcb_positive": o["ev_lcb"] > 0,
             "conformal_singleton": conformal_ok and s["cset"] == [PR.CLASSES[k]],
             "prob_above_lcb": s["plcb"][side]["passes"],
             "margin": s["M"] >= theta_M and int(np.argmax(s["P"])) == k,
             "disagreement": s["D"] <= theta_D,
             "uphill_candidate": s["cand"] == side,
             "risk": in_window and s["planned_loss"] <= sess["research_equity_usd"] * sess["max_planned_loss_pct_equity"] / 100 and ecfg["leverage"] <= sess["max_leverage"],
             "switching": sw["passes"]}
        failed = [x for x in cfg["gates_order"] if not g[x]]
        gate_rows.append({"market": m, "side": side, "Q": o["Q"], "ev_lcb": o["ev_lcb"], "gates": g, "failed": failed, "switch": sw})
    top = gate_rows[0]
    action = f"{top['side']} {top['market']}" if not top["failed"] else "WAIT"
    decisive = None if not top["failed"] else top["failed"][0]

    s = assets[top["market"]]
    explain = {
        "data_quality": f"{top['market']} data-quality check failed ({[k for k, v in s['dq'].items() if v is False]}).",
        "ev_lcb_positive": f"The best opportunity ({top['side']} {top['market']}) has a conservative net EV of ${top['ev_lcb']:+.3f} after real Jupiter costs (stressed), which is below zero, so WAIT has the higher value.",
        "conformal_singleton": f"The conformal set for {top['market']} is {s['cset']}, not a single direction.",
        "prob_above_lcb": f"{top['market']}'s calibrated probability is not reliably above its base rate.",
        "margin": f"{top['market']}'s probability margin {s['M']:.3f} is below the threshold {theta_M:.3f} or the top class is not the trade direction.",
        "disagreement": f"Sub-model disagreement {s['D']:.4f} exceeds the threshold {theta_D:.4f}.",
        "uphill_candidate": f"{top['market']} is not an uphill {top['side'].lower()} candidate.",
        "risk": "Outside the 06:00-11:45 Toronto decision window or planned loss exceeds 2% of research equity.",
        "switching": "Gain over the current position does not clear switching cost plus hysteresis.",
    }
    reason = "ALL_GATES_PASSED" if decisive is None else decisive.upper()

    # ---------------- session-close horizon (reported only) ----------------
    sc = {}
    thr = cfg["outcomes"]["session_close"]["threshold_pct"] / 100
    loc_h = cutoff.astimezone(TZ); clock = ((loc_h.hour * 60 + loc_h.minute) // 60) * 60 * 60000
    for m in markets:
        hend, hclose = F.hourly_series(b1h[m], b1[m], cutoff_ms)
        smp = session_close_samples(hend, hclose, clock, thr, cutoff_ms)
        o = PR.session_close_model(smp)
        live = smp[-1] if smp and smp[-1]["t_ms"] == max(x["t_ms"] for x in smp) else None
        prior = [q for q in smp[-366:-1] if q["y"] >= 0 and q["resolved_ms"] <= cutoff_ms]
        bucket = live["bucket"] if live else 0.0
        same = np.array([q["y"] for q in prior if q["bucket"] == bucket] or [-1])
        p_live = PR.freq_probs(same)
        sc_scores = [1 - x["p"][x["y"]] for x in o[-120:]]
        qsc = UC.conformal_quantile(sc_scores, alpha)
        yb = np.array([x["y"] for x in o]); Pm = np.array([x["p"] for x in o]); Pb = np.array([x["p_base"] for x in o])
        sc[m] = {"sample_ts": iso(from_ms(live["t_ms"])) if live else None, "target_end_ts": iso(from_ms(live["end_ms"])) if live else None,
                 "momentum_bucket_4h": bucket, "p_up": p_live[0], "p_range": p_live[1], "p_down": p_live[2],
                 "conformal_set": UC.conformal_set(p_live, qsc), "n_prior_samples": len(prior), "n_oos": len(o),
                 "oos_brier_model": float(PR.brier(Pm, yb).mean()) if len(o) else None,
                 "oos_brier_unconditional": float(PR.brier(Pb, yb).mean()) if len(o) else None}

    # ---------------- assemble record ----------------
    fb = EVL.feature_budget(np.vstack([np.column_stack([Xp[m][tr]]) for m in markets]), F.PROB_COLS)
    total_ne = sum(diag[m]["n_eff"] for m in markets)
    fb.update({"training_observations_pooled": n_train, "n_eff_oos_sum": total_ne, "n_eff_over_d": total_ne / 9.0,
               "variants_tried": cfg["diagnostics"]["variants_tried"], "threshold_sets_tried": 1})
    resolved, sessions = {}, {}
    if shadow:
        for m in markets:
            resolved[m] = shadow.execute("SELECT COUNT(*) FROM forecasts WHERE market=? AND horizon='15m' AND outcome IS NOT NULL", (m,)).fetchone()[0]
            sessions[m] = shadow.execute("SELECT COUNT(DISTINCT substr(cutoff_ts,1,10)) FROM forecasts WHERE market=? AND outcome IS NOT NULL", (m,)).fetchone()[0]
    else:
        resolved = {m: 0 for m in markets}; sessions = {m: 0 for m in markets}
    promo = EVL.promotion_gates(resolved, sessions, cfg)

    per_asset = {}
    for m in markets:
        s = assets[m]; P = s["P"]
        fh = sha(canon({"market": m, "cutoff": iso(cutoff), "config": cfg["config_version"], "features": s["feats"]}))
        best_side = max(("LONG", "SHORT"), key=lambda sd: s["opps"][sd]["ev_lcb"])
        kel = EV.kelly_display(s["plcb"][best_side]["wilson_lcb"], abs(s["cstats"][0 if best_side == "LONG" else 2]["mean"]) * s["scale"],
                               abs(s["cstats"][2 if best_side == "LONG" else 0]["mean"]) * s["scale"])
        cl, cs = costs.get((m, "long")), costs.get((m, "short"))
        per_asset[m] = {
            "market": m, "cutoff_ts": iso(cutoff), "horizon": "15m", "target_end_ts": iso(from_ms(cutoff_ms + M15)),
            "event_ts": iso(cutoff), "received_ts": b1[m]["received_max"], "training_cutoff_ts": iso(from_ms(train_T_max + M15)),
            "p_up": P[0], "p_flat": P[1], "p_range": P[1], "p_down": P[2],
            "sub_model_probs": {k: v.tolist() for k, v in s["sub"].items()},
            "uphill_score": s["U"], "uphill_slope": s["S"], "uphill_thresholds": {k: v for k, v in s["ustats"].items() if k != "norm"},
            "uphill_candidate": s["cand"],
            "ballistic_persistence": s["feats"]["BP"], "ballistic_B": s["feats"]["B"], "path_efficiency_4h": s["feats"]["E"],
            "conformal_set": s["cset"], "confidence_margin": s["M"], "model_disagreement": s["D"],
            "effective_sample_size": diag[m]["n_eff"],
            "ev_long_net": s["ev"]["ev_long_net"], "ev_short_net": s["ev"]["ev_short_net"], "ev_wait": 0.0,
            "ev_long_lcb": s["ev"]["ev_long_lcb"], "ev_short_lcb": s["ev"]["ev_short_lcb"],
            "ev_lcb": max(s["ev"]["ev_long_lcb"], s["ev"]["ev_short_lcb"]),
            "ev_with_base_costs": {k: s["ev_base_costs"][k] for k in ("ev_long_net", "ev_short_net", "ev_long_lcb", "ev_short_lcb")},
            "ev_detail": {"class_stats_15m_logret": s["cstats"], "atr_scale": s["scale"], "expected_return": s["ev"]["expected_return"],
                          "expected_return_se": s["ev"]["expected_return_se"], "notional_usd": s["notional"], "se_usd": s["ev"]["se_usd"]},
            "costs_long": cl, "costs_short": cs,
            "quote_long": quotes.get((m, "long")), "quote_short": quotes.get((m, "short")),
            "prob_lcb": s["plcb"], "opportunity": s["opps"], "kelly_display_only": kel,
            "switch_cost_usd": min(x["total_base"] for x in (cl, cs) if x) if (cl or cs) else None,
            "hysteresis_buffer": next(g["switch"]["hysteresis_buffer"] for g in gate_rows if g["market"] == m),
            "data_quality": s["dq"], "planned_loss_usd": s["planned_loss"],
            "absent_inputs": {k: None for k in cfg["absent_inputs"]},
            "context_labels": {"ema50_1h": "above" if s["feats"]["trend50"] > 0 else "below", "ema200_1h": "above" if s["feats"]["trend200"] > 0 else "below" if s["feats"]["trend200"] < 0 else None},
            "features_raw": s["feats"],
            "session_close": sc[m],
            "action": action if action.endswith(m) else "WAIT",
            "reason": reason, "config_version": cfg["config_version"], "features_hash": fh,
            "outcome": None, "resolved_ts": None,
        }
    record = {
        "run_id": run_id, "shadow_only": True, "paper_only": True, "affects_official_v3": False,
        "cutoff_ts": iso(cutoff), "cutoff_toronto": toronto_str(cutoff_ms), "knowledge_ts": knowledge_iso,
        "run_started_ts": iso(run_started), "created_ts": iso(dt.datetime.now(UTC)),
        "config_version": cfg["config_version"], "config_hash": sha(cfg_text), "code_hash": code_hash(),
        "spec": cfg["spec"], "training_cutoff_ts": iso(from_ms(train_T_max + M15)),
        "action": action, "decisive_gate": decisive, "reason": reason,
        "decisive_gate_explanation": "Every gate passed." if decisive is None else explain[decisive],
        "research_position_before": "FLAT", "research_position_after": "FLAT" if action == "WAIT" else action,
        "position_choice_note": "Research book starts FLAT. Crypto Captain's separate paper ledger ETH long (opened 2026-10-10 10:34 ET @ 2,503.93) is not this research book's position; it belongs to a different ledger and strategy, and inheriting it would mix books.",
        "assets": per_asset,
        "opportunity_queue": [{k: g[k] for k in ("market", "side", "Q", "ev_lcb", "failed")} for g in gate_rows],
        "gates_by_alternative": gate_rows,
        "thresholds": {"theta_M": theta_M, "theta_D": theta_D, "conformal_q": q_live, "temperature_live": T_live, "temperatures_by_fold": temps},
        "conformal": {"alpha": alpha, "rolling_coverage": cov / ncov if ncov else None, "n": ncov, "wilson95": [cov_lo, cov_hi],
                      "action_permission": conformal_ok, "by_asset": cov_by_asset, "by_fold": cov_detail},
        "joint_state": {"best_feasible": best_feas, "best_any": best_any, "flat": flat, "covariance_window_blocks": int(len(Rw)),
                        "sample_corr": Csample.tolist(), "mean_corr": rbar, "stressed_toward_one": stressed, "atr_ranks": atr_ranks,
                        "all_states": states},
        "walk_forward": {"folds": [{"j": f["j"], "test_start": iso(from_ms(f["fs"])), "test_end": iso(from_ms(f["fe"])), "n_train": f["n_train"]} for f in folds],
                         "oos_diagnostics": diag, "fixed_margin_null_test": null},
        "history_used": {"grid_start": iso(from_ms(int(grid[0]))), "grid_end": iso(cutoff), "blocks_per_asset": int(n), "audit": audit},
        "feature_budget": fb, "promotion_gates": promo,
        "timestamp_safety": cfg["timestamp_safety"], "absent_inputs": cfg["absent_inputs"],
        "notes": ["Costs are read-only Jupiter quotes taken at run time (execution-time cost), not market data for prediction.",
                  "Action horizon is 15m; session-close probabilities are reported only.",
                  "Walk-forward results are backtest diagnostics, not resolved shadow forecasts; promotion counts only resolved shadow records."],
    }
    record = clean(record)
    out = json.dumps(record, indent=1, sort_keys=False)
    if a.dry_run:
        print(out); return 0
    os.makedirs(a.records, exist_ok=True)
    rp = os.path.join(a.records, run_id + ".json")
    with open(rp, "w") as fh_:
        fh_.write(out)
    rsha = sha(out)
    with shadow:
        shadow.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)", (run_id, record["cutoff_ts"], record["cutoff_toronto"], knowledge_iso,
                       record["created_ts"], cfg["config_version"], record["config_hash"], record["code_hash"], record["training_cutoff_ts"],
                       action, None if action == "WAIT" else top["market"], decisive, reason, rp, rsha))
        for m, r in per_asset.items():
            shadow.execute("INSERT INTO forecasts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                f"{run_id}-{m}-15m", run_id, m, "15m", r["event_ts"], r["received_ts"], r["cutoff_ts"], r["target_end_ts"], r["training_cutoff_ts"],
                r["p_up"], r["p_range"], r["p_down"], json.dumps(r["conformal_set"]), r["uphill_score"], r["uphill_slope"], r["ballistic_persistence"],
                r["model_disagreement"], r["effective_sample_size"], r["ev_long_net"], r["ev_short_net"], 0.0, r["ev_lcb"], reason,
                cfg["config_version"], r["features_hash"], None, None, None))
            scm = r["session_close"]
            shadow.execute("INSERT INTO forecasts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                f"{run_id}-{m}-session", run_id, m, "session_close", r["event_ts"], r["received_ts"], r["cutoff_ts"], scm["target_end_ts"],
                r["training_cutoff_ts"], scm["p_up"], scm["p_range"], scm["p_down"], json.dumps(scm["conformal_set"]), None, None, None, None, None,
                None, None, None, None, "REPORTED_ONLY", cfg["config_version"], r["features_hash"], None, None, None))
        for g in gate_rows:
            shadow.execute("INSERT INTO alternatives VALUES(?,?,?,?,?,?,?,?)", (run_id, g["market"], g["side"], clean(g["Q"]), clean(g["ev_lcb"]),
                           int(action == f"{g['side']} {g['market']}"), json.dumps(g["failed"]), json.dumps(clean(g["gates"]))))
        for st in states:
            shadow.execute("INSERT INTO joint_states VALUES(?,?,?,?,?,?,?)", (run_id, json.dumps(st["state"]), st["J"], st["mu"], st["var"], st["tail_es95"], int(st["feasible"])))
        if action != "WAIT":
            shadow.execute("UPDATE research_position SET market=?, side=?, since_cutoff_ts=? WHERE id=1", (top["market"], top["side"], record["cutoff_ts"]))
    print(json.dumps({"run_id": run_id, "record": rp, "action": action, "decisive_gate": decisive}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
