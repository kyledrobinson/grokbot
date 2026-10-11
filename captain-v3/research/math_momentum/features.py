"""Structure 1: Uphill Momentum Vector (equal-weight winsorized baseline) on a 15m grid."""
import numpy as np
from .data import M1, M15, H1, toronto_day_starts

FEATURES = ["r15m", "r1h", "r4h", "dEMA50_1h", "dVWAP", "volRatio", "ATRrank", "relBTC_1h", "relBTC_24h"]


def agg_15m(b1, grid_end):
    """Complete 15m blocks (15 x 1m) from 1m bars, on grid of block END ms. Incomplete -> NaN."""
    n = len(grid_end)
    out = {k: np.full(n, np.nan) for k in ("o", "h", "l", "c", "v")}
    if b1["n"] == 0:
        return out
    blk_end = (b1["start"] // M15) * M15 + M15
    idx = np.searchsorted(grid_end, blk_end)
    ok = (idx < n) & (grid_end[np.clip(idx, 0, n - 1)] == blk_end)
    cnt = np.bincount(idx[ok], minlength=n)
    full = cnt == 15
    # bars are time-sorted, so first/last occurrence per block give open/close
    order = np.where(ok)[0]
    ii = idx[order]
    first = {}
    last = {}
    for pos, blk in zip(order, ii):
        if blk not in first:
            first[blk] = pos
        last[blk] = pos
    hi = np.full(n, -np.inf); lo = np.full(n, np.inf); vol = np.zeros(n)
    np.maximum.at(hi, ii, b1["h"][order]); np.minimum.at(lo, ii, b1["l"][order]); np.add.at(vol, ii, b1["v"][order])
    for blk in np.where(full)[0]:
        out["o"][blk] = b1["o"][first[blk]]; out["c"][blk] = b1["c"][last[blk]]
        out["h"][blk] = hi[blk]; out["l"][blk] = lo[blk]; out["v"][blk] = vol[blk]
    return out


def hourly_series(b1h_native, b1, cutoff_ms):
    """Native 1h closes, extended with complete 1h bars aggregated from 1m after the native series ends."""
    starts = list(b1h_native["start"]); closes = list(b1h_native["c"])
    last_native = starts[-1] if starts else -1
    if b1["n"]:
        hstart = (b1["start"] // H1) * H1
        for hs in np.unique(hstart):
            if hs <= last_native or hs + H1 > cutoff_ms:
                continue
            m = hstart == hs
            if m.sum() == 60:
                starts.append(int(hs)); closes.append(float(b1["c"][m][-1]))
    starts = np.array(starts, dtype=np.int64); closes = np.array(closes)
    return starts + H1, closes  # (end_ms, close)


def ema(values, period):
    out = np.full(len(values), np.nan)
    if len(values) < period:
        return out
    e = values[:period].mean(); out[period - 1] = e; k = 2.0 / (period + 1)
    for i in range(period, len(values)):
        e = values[i] * k + e * (1 - k); out[i] = e
    return out


def atr_wilder_nan(h, l, c, period=14):
    """Wilder ATR over valid (non-NaN) blocks only; NaN blocks are skipped (treated as absent)."""
    out = np.full(len(c), np.nan); a = None; trs = []; prev = None
    for i in range(len(c)):
        if np.isnan(c[i]):
            continue
        tr = h[i] - l[i] if prev is None else max(h[i] - l[i], abs(h[i] - prev), abs(l[i] - prev))
        prev = c[i]
        if a is None:
            trs.append(tr)
            if len(trs) == period:
                a = sum(trs) / period; out[i] = a
        else:
            a = (a * (period - 1) + tr) / period; out[i] = a
    return out


def trailing_rank(x, window, min_n):
    """Percentile rank of x[t] among the previous `window` finite values (strictly earlier)."""
    out = np.full(len(x), np.nan)
    for t in range(len(x)):
        if np.isnan(x[t]):
            continue
        prev = x[max(0, t - window):t]; prev = prev[np.isfinite(prev)]
        if len(prev) >= min_n:
            out[t] = (prev < x[t]).mean() + 0.5 * (prev == x[t]).mean()
    return out


def lagret(lc, k):
    out = np.full(len(lc), np.nan); out[k:] = lc[k:] - lc[:-k]; return out


def trailing_std(x, window, min_n=96):
    out = np.full(len(x), np.nan)
    for t in range(len(x)):
        prev = x[max(0, t - window):t]; prev = prev[np.isfinite(prev)]
        if len(prev) >= min_n:
            out[t] = prev.std(ddof=1)
    return out


def asset_raw(b1, b1h, grid_end, cutoff_ms, cfg):
    fc = cfg["features"]
    k = agg_15m(b1, grid_end)
    c = k["c"]; lc = np.log(c)
    f = {"close": c, "volume": k["v"]}
    f["r15m"] = lagret(lc, 1); f["r30m"] = lagret(lc, 2); f["r1h"] = lagret(lc, 4); f["r2h"] = lagret(lc, 8)
    f["r4h"] = lagret(lc, 16); f["r24h"] = lagret(lc, 96)
    # 1h EMA50/EMA200 (last completed hour at or before block end)
    hend, hclose = hourly_series(b1h, b1, cutoff_ms)
    e50 = ema(hclose, 50); e200 = ema(hclose, 200); L = fc["ema"]["slope_lookback_bars"]
    hi = np.searchsorted(hend, grid_end, side="right") - 1
    d = np.full(len(grid_end), np.nan); t50 = np.full(len(grid_end), np.nan); t200 = np.full(len(grid_end), np.nan)
    stale_h = np.full(len(grid_end), np.nan)
    for t, j in enumerate(hi):
        if j >= L and np.isfinite(e50[j]) and np.isfinite(e50[j - L]):
            d[t] = (e50[j] - e50[j - L]) / e50[j]
            t50[t] = np.sign(hclose[j] - e50[j])
            t200[t] = np.sign(hclose[j] - e200[j]) if np.isfinite(e200[j]) else np.nan
            stale_h[t] = (grid_end[t] - hend[j]) / 60000.0
    f["dEMA50_1h"] = d; f["trend50"] = t50; f["trend200"] = t200; f["hour_age_min"] = stale_h
    # VWAP from 00:00 Toronto through block end (typical price, 1m)
    vw = np.full(len(grid_end), np.nan)
    if b1["n"]:
        ds = toronto_day_starts(int(b1["start"][0]), int(b1["start"][-1]))
        day = np.searchsorted(ds, b1["start"], side="right") - 1
        tpv = (b1["h"] + b1["l"] + b1["c"]) / 3.0 * b1["v"]
        cum_tpv = np.zeros(len(tpv)); cum_v = np.zeros(len(tpv))
        for i in range(len(tpv)):
            same = i > 0 and day[i] == day[i - 1]
            cum_tpv[i] = tpv[i] + (cum_tpv[i - 1] if same else 0.0)
            cum_v[i] = b1["v"][i] + (cum_v[i - 1] if same else 0.0)
        pos = np.searchsorted(b1["end"], grid_end)
        for t, p in enumerate(pos):
            if p < len(b1["end"]) and b1["end"][p] == grid_end[t] and cum_v[p] > 0:
                vw[t] = cum_tpv[p] / cum_v[p]
    f["vwap"] = vw; f["dVWAP"] = c / vw - 1.0
    # volume ratio vs prior 20 blocks
    n = fc["volume_ratio_trailing_bars"]; vr = np.full(len(c), np.nan); v = k["v"]
    for t in range(n, len(c)):
        prev = v[t - n:t]
        if np.isfinite(v[t]) and np.all(np.isfinite(prev)) and prev.mean() > 0:
            vr[t] = v[t] / prev.mean()
    f["volRatio_raw"] = vr
    atr = atr_wilder_nan(k["h"], k["l"], c, fc["atr"]["period"])
    f["atr"] = atr; f["atr_pct"] = atr / c
    f["ATRrank_raw"] = trailing_rank(f["atr_pct"], fc["atr_rank_trailing_bars"], fc["atr_rank_min_bars"])
    f["sigma15"] = trailing_std(f["r15m"], cfg["persistence"].get("sigma_window", 672))
    return f


def build_panel(raw, markets):
    """Adds relative-strength vs BTC and the oriented/unsigned variants. raw: {mkt: dict of arrays}."""
    btc = raw["BTC"]
    for m in markets:
        f = raw[m]
        f["relBTC_1h"] = f["r1h"] - btc["r1h"] if m != "BTC" else np.where(np.isfinite(f["r1h"]), 0.0, np.nan)
        f["relBTC_24h"] = f["r24h"] - btc["r24h"] if m != "BTC" else np.where(np.isfinite(f["r24h"]), 0.0, np.nan)
        lv = np.log(f["volRatio_raw"])
        f["volRatio_u"] = lv; f["ATRrank_u"] = f["ATRrank_raw"] - 0.5
        f["volRatio_s"] = np.sign(f["r15m"]) * lv
        f["ATRrank_s"] = (f["ATRrank_raw"] - 0.5) * np.sign(f["r1h"])
    return raw


UPHILL_COLS = ["r15m", "r1h", "r4h", "dEMA50_1h", "dVWAP", "volRatio_s", "ATRrank_s", "relBTC_1h", "relBTC_24h"]
PROB_COLS = ["r15m", "r1h", "r4h", "dEMA50_1h", "dVWAP", "volRatio_u", "ATRrank_u", "relBTC_1h", "relBTC_24h"]


def fit_norm(X, train_mask):
    """Median / 1.4826*MAD per column on training rows only."""
    Xt = X[train_mask]
    med = np.nanmedian(Xt, axis=0)
    mad = 1.4826 * np.nanmedian(np.abs(Xt - med), axis=0)
    return med, mad


def apply_norm(X, med, mad, w):
    with np.errstate(invalid="ignore", divide="ignore"):
        Z = np.where(mad > 1e-15, (X - med) / mad, 0.0)
    Z = np.where(np.isfinite(X), Z, np.nan)
    return np.clip(Z, -w, w)


def uphill(Z, k):
    U = np.mean(Z, axis=1)  # equal weights
    S = np.full(len(U), np.nan); S[k:] = U[k:] - U[:-k]
    return U, S


def mat(f, cols):
    return np.column_stack([f[c] for c in cols])
