"""Read-only Jupiter cost inputs. ONLY /workspace/perps-fees/quote and /workspace/perps-fees/borrow are invoked.
quote -> POST positions/increase for a public address; the returned unsigned tx is never signed (tool drops it)."""
import json, os, subprocess
from .util import now_utc, iso

ALLOWED = {"/workspace/perps-fees/quote", "/workspace/perps-fees/borrow"}


def _run(tool, args, timeout=60):
    assert tool in ALLOWED, "only the read-only quote/borrow tools may be called"
    if os.environ.get("CAPTAIN_OFFLINE_COSTS"):
        raise RuntimeError("offline cost mode (tests)")
    p = subprocess.run([tool] + args, capture_output=True, text=True, timeout=timeout, cwd="/workspace/perps-fees")
    return p.returncode, p.stdout, p.stderr[-2000:]


def quote(cfg, asset, side, collateral_usd, leverage, hold_hours):
    args = [asset, side, "--usd", f"{collateral_usd:.2f}", "--leverage", f"{leverage:.2f}", "--hold-hours", f"{max(hold_hours, 0):.4f}",
            "--collateral", cfg["costs"]["quote_collateral"], "--slippage-bps", str(cfg["costs"]["quote_slippage_bps"])]
    t = now_utc()
    try:
        code, out, err = _run(cfg["costs"]["quote_tool"], args)
        data = json.loads(out) if code == 0 and out.strip() else None
    except Exception as e:
        code, out, err, data = -1, "", repr(e), None
    return {"requested": {"tool": cfg["costs"]["quote_tool"], "args": args}, "quoted_ts": iso(t), "exit_code": code, "response": data, "stderr": err}


def borrow(cfg):
    t = now_utc()
    try:
        code, out, err = _run(cfg["costs"]["borrow_tool"], [])
        data = json.loads(out) if code == 0 else None
    except Exception as e:
        code, data, err = -1, None, repr(e)
    return {"fetched_ts": iso(t), "exit_code": code, "response": data, "stderr": err}


def quote_cost_components(q):
    """Split a quote into labeled cost components. Open-side values = quote; close-side = estimate."""
    f = q["fees"]
    comps = [
        ("open_fee", f["openFeeUsd"], "quote", "positions/increase openFeeUsd", "open"),
        ("open_price_impact", f["openPriceImpactFeeUsd"], "quote", "positions/increase openPriceImpactFeeUsd", "open"),
        ("network_open", f["network"].get("transactionFeeUsd") or 0.0, "quote", "txMetadata transactionFeeLamports x SOL price", "open"),
        ("collateral_conversion", max(0.0, q.get("inputToCollateralDiffUsd") or 0.0), "quote", "derived inputToCollateralDiffUsd (swap fee approx.)", "open"),
        ("close_fee", f["closeFee"]["baseFeeUsd"], "estimate", f["closeFee"]["method"][:200], "close"),
        ("close_price_impact", f["closeFee"]["priceImpactFeeUsd_assumed"], "estimate", "assumed equal to open impact", "close"),
        ("network_close", f["network"].get("transactionFeeUsd") or 0.0, "estimate", "assumed equal to open tx fee", "close"),
    ]
    return comps
