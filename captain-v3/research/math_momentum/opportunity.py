"""Structure 6: opportunity queue Q = LCB(EV) / (ES95 + costs) * CalibrationQuality * DataQuality."""


def calib_quality(ece):
    if ece != ece:
        return 0.0
    return max(0.0, min(1.0, 1.0 - ece / 0.10))


def q_score(lcb, es95_usd, cost_usd, cq, dq):
    den = es95_usd + cost_usd
    return (lcb / den) * cq * dq if den > 0 else 0.0


def rank(opps):
    return sorted(opps, key=lambda o: -o["Q"])
