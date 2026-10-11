"""Structure 4: net EV surface for LONG/SHORT/WAIT with real Jupiter costs (read-only quotes) and an LCB.
Only /workspace/perps-fees/quote is invoked (public wallet, unsigned tx dropped by the tool, nothing submitted)."""
import json, math, subprocess
import numpy as np

QUOTE_TOOL = "/workspace/perps-fees/quote"


def live_quote(asset, side, ecfg, timeout=60):
    args = [asset, side, "--usd", f"{ecfg['collateral_usd']:.2f}", "--leverage", f"{ecfg['leverage']:.2f}",
            "--hold-hours", f"{ecfg['hold_hours']:.4f}", "--collateral", ecfg["quote_collateral"],
            "--slippage-bps", str(ecfg["quote_slippage_bps"])]
    try:
        p = subprocess.run([QUOTE_TOOL] + args, capture_output=True, text=True, timeout=timeout, cwd="/workspace/perps-fees")
        if p.returncode == 0 and p.stdout.strip():
            return {"status": "LIVE", "args": args, "response": json.loads(p.stdout), "stderr": p.stderr[-500:]}
        return {"status": "FAILED", "args": args, "response": None, "stderr": (p.stderr or "")[-500:], "exit_code": p.returncode}
    except Exception as e:
        return {"status": "FAILED", "args": args, "response": None, "stderr": repr(e)}


def stored_quote(con, asset, side):
    """Most recent stored real quote (captain.db, read-only) for this asset/side."""
    for qid, req, resp, ts in con.execute("SELECT quote_id, requested, response, quoted_ts FROM quotes WHERE exit_code=0 AND synthetic=0 "
                                          "ORDER BY quoted_ts DESC"):
        try:
            a = json.loads(req)["args"]
            if a[0] == asset and a[1] == side and resp:
                return {"status": "STALE", "quote_id": qid, "quoted_ts": ts, "response": json.loads(resp)}
        except Exception:
            continue
    return None


def cost_breakdown(q, ecfg, notional=None):
    """USD costs from a quote response. Fee items scale with notional if a different notional is requested."""
    f = q["fees"]; size = q["positionSizeUsd"]; s = (notional / size) if notional else 1.0
    hold = ecfg["hold_hours"]
    borrow = size * s * f["borrow"]["hourlyRatePct"] / 100.0 * hold
    c = {
        "open_fee": f["openFeeUsd"] * s, "open_price_impact": f["openPriceImpactFeeUsd"] * s,
        "network_open": f["network"].get("transactionFeeUsd") or 0.0,
        "collateral_conversion": max(0.0, q.get("inputToCollateralDiffUsd") or 0.0) * s,
        "close_fee_est": f["closeFee"]["baseFeeUsd"] * s, "close_price_impact_est": f["closeFee"]["priceImpactFeeUsd_assumed"] * s,
        "network_close_est": f["network"].get("transactionFeeUsd") or 0.0,
        "borrow_hold": borrow, "borrow_hourly_pct": f["borrow"]["hourlyRatePct"],
        "modeled_slippage": 2 * ecfg["modeled_adverse_slippage_bps_per_side"] / 1e4 * size * s,
    }
    close = c["close_fee_est"] + c["close_price_impact_est"] + c["network_close_est"]
    open_ = c["open_fee"] + c["open_price_impact"] + c["network_open"] + c["collateral_conversion"]
    c["total_base"] = open_ + close + borrow + c["modeled_slippage"]
    c["total_stressed"] = open_ + ecfg["stress_close_multiplier"] * close + ecfg["stress_financing_multiplier"] * borrow + c["modeled_slippage"]
    c["open_side"] = open_
    c["notional_usd"] = size * s
    return c


def class_stats(r, y, scale_atr=None):
    """Per-class mean / SE of next-block log return."""
    out = []
    for k in range(3):
        rk = r[y == k]
        out.append({"mean": float(rk.mean()) if len(rk) else 0.0, "se": float(rk.std(ddof=1) / math.sqrt(len(rk))) if len(rk) > 1 else 0.0,
                    "n": int(len(rk))})
    return out


def ev_surface(p, stats, scale, notional, cost_long, cost_short, n_eff, z):
    m = np.array([s["mean"] for s in stats]) * scale; se = np.array([s["se"] for s in stats]) * scale
    er = float(p @ m)
    var_p = max(float(p @ (m ** 2)) - er ** 2, 0.0) / max(n_eff, 1.0)
    var_m = float((p ** 2) @ (se ** 2))
    se_r = math.sqrt(var_p + var_m)
    gross_long = notional * er; se_usd = notional * se_r
    evL = gross_long - cost_long; evS = -gross_long - cost_short
    return {"expected_return": er, "expected_return_se": se_r, "class_means_scaled": m.tolist(),
            "gross_long_usd": gross_long, "gross_short_usd": -gross_long,
            "ev_long_net": evL, "ev_short_net": evS, "ev_wait": 0.0,
            "ev_long_lcb": evL - z * se_usd, "ev_short_lcb": evS - z * se_usd, "se_usd": se_usd}


def kelly_display(p_win_lcb, win_ret, loss_ret):
    """Display only. Binary approximation f* = (b p - (1-p)) / b with b = |win|/|loss|."""
    if loss_ret == 0 or win_ret <= 0:
        return None
    b = abs(win_ret) / abs(loss_ret)
    f = (b * p_win_lcb - (1 - p_win_lcb)) / b
    return {"b": b, "p_lcb": p_win_lcb, "f_star": f, "quarter_kelly": 0.25 * f, "controls_size": False}
