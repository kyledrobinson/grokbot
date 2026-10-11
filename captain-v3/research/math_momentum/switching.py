"""Structure 8: switching-cost + hysteresis controller."""


def hysteresis(h0_usd, atr_rank, D, theta_D, recent_turnover):
    return h0_usd * (1.0 + (atr_rank if atr_rank == atr_rank else 1.0) + (D / theta_D if theta_D > 0 else 1.0) + recent_turnover)


def switch_decision(lcb_new, lcb_current, c_switch_incremental, H):
    gap = lcb_new - lcb_current
    return {"lcb_new": lcb_new, "lcb_current": lcb_current, "gap": gap, "c_switch_incremental": c_switch_incremental,
            "hysteresis_buffer": H, "required": c_switch_incremental + H, "passes": gap > c_switch_incremental + H}
