"""Position sizing for a linear USD perp proxy (spec section 9). Stop is chosen first, then size.

planned_loss(n) = n*(stop_frac + adverse_slip) + n*(open_fee+open_impact) + net_open
                + stress_close*(n*(close_fee+close_impact) + net_close) + n*borrow_rate_per_h*hours*stress_fin
Solved linearly for n, then capped by leverage/collateral limits. Fractions are per unit notional."""


def cost_fractions_modeled(cfg):
    c = cfg["costs"]
    return {"open_fee": c["modeled_open_fee_bps"] / 1e4, "open_impact": c["modeled_impact_bps"] / 1e4,
            "close_fee": c["modeled_close_fee_bps"] / 1e4, "close_impact": c["modeled_impact_bps"] / 1e4,
            "net_open": c["modeled_network_usd"], "net_close": c["modeled_network_usd"], "conversion": 0.0, "source": "modeled"}


def cost_fractions_from_quote(q):
    size = q["positionSizeUsd"]
    f = q["fees"]
    net = f["network"].get("transactionFeeUsd") or 0.0
    conv = max(0.0, q.get("inputToCollateralDiffUsd") or 0.0)
    return {"open_fee": f["openFeeUsd"] / size, "open_impact": f["openPriceImpactFeeUsd"] / size,
            "close_fee": f["closeFee"]["baseFeeUsd"] / size, "close_impact": f["closeFee"]["priceImpactFeeUsd_assumed"] / size,
            "net_open": net, "net_close": net, "conversion": conv, "source": "quote"}


def planned_loss(n, stop_frac, fr, borrow_pct_h, hours, cfg):
    r = cfg["risk"]
    slip = r["adverse_slippage_bps"] / 1e4
    parts = {
        "price_loss": n * stop_frac,
        "adverse_slippage": n * slip,
        "open_costs": n * (fr["open_fee"] + fr["open_impact"]) + fr["net_open"] + fr["conversion"],
        "stressed_close_costs": r["stress_close_multiplier"] * (n * (fr["close_fee"] + fr["close_impact"]) + fr["net_close"]),
        "stressed_financing": n * borrow_pct_h / 100 * hours * r["stress_financing_multiplier"],
    }
    parts["total"] = sum(parts.values())
    return parts


def size(equity_trading, stop_frac, fr, borrow_pct_h, hours, cfg):
    r = cfg["risk"]
    budget = equity_trading * r["max_planned_loss_pct_equity"] / 100
    slip = r["adverse_slippage_bps"] / 1e4
    per_n = stop_frac + slip + fr["open_fee"] + fr["open_impact"] + r["stress_close_multiplier"] * (fr["close_fee"] + fr["close_impact"]) \
        + borrow_pct_h / 100 * hours * r["stress_financing_multiplier"]
    fixed = fr["net_open"] + fr["conversion"] + r["stress_close_multiplier"] * fr["net_close"]
    out = {"budget_usd": budget, "stop_frac": stop_frac, "per_unit_loss": per_n, "fixed_costs": fixed, "cost_source": fr["source"]}
    if stop_frac <= 0:
        out.update(ok=False, reason="INVALID_STOP")
        return out
    n_budget = (budget - fixed) / per_n if budget > fixed else 0.0
    n_cap = min(r["max_leverage"] * equity_trading, r["max_collateral_usd"] * r["max_leverage"], r["max_leverage"] * min(equity_trading, r["max_collateral_usd"]))
    n = min(n_budget, n_cap)
    n_min = r["min_collateral_usd"] * r["min_leverage"]
    out.update(n_budget=n_budget, n_cap=n_cap, n_min=n_min)
    if n < n_min:
        out.update(ok=False, reason="RISK_BUDGET_TOO_SMALL", notional=n)
        return out
    if n >= r["min_collateral_usd"] * r["max_leverage"]:
        lev = r["max_leverage"]
        coll = n / lev
    else:
        coll = r["min_collateral_usd"]
        lev = n / coll
    lev = round(lev, 2)
    coll = round(min(coll, r["max_collateral_usd"]), 2)
    n = coll * lev
    pl = planned_loss(n, stop_frac, fr, borrow_pct_h, hours, cfg)
    stress = n * (stop_frac + r["legacy_stress_adverse_pct"] / 100)
    out.update(ok=pl["total"] <= budget + 1e-9, reason=None if pl["total"] <= budget + 1e-9 else "RISK_BUDGET_TOO_SMALL",
               notional=n, collateral=coll, leverage=lev, planned_loss=pl,
               legacy_stress_scenario={"label": "STRESS SCENARIO (not a bound): stop + 2% adverse move, before fees", "loss_usd": stress})
    return out
