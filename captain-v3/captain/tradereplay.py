"""`captain replay <TRADE_ID|HY-...>`: decision-time inputs, gates, reason, fills, costs with sources, PnL math."""
import json
from . import ledger


def _j(x):
    try:
        return json.loads(x) if isinstance(x, str) else x
    except Exception:
        return x


def render(con, cfg, tid):
    L = []
    hyp = tid.startswith("HY-") or tid.startswith("HS-")
    t = con.execute("SELECT * FROM hypothetical_outcomes WHERE hyp_id=?" if hyp else "SELECT * FROM trades WHERE trade_id=? OR decision_id=?", (tid,) if hyp else (tid, tid)).fetchone()
    if not t:
        return f"not found: {tid}"
    t = dict(t)
    did = t.get("decision_id")
    d = dict(con.execute("SELECT * FROM decisions WHERE decision_id=?", (did,)).fetchone()) if did else {}
    sg = dict(con.execute("SELECT * FROM signals WHERE signal_id=?", (d.get("signal_id"),)).fetchone()) if d.get("signal_id") else {}
    sn = dict(con.execute("SELECT * FROM snapshots WHERE snapshot_id=?", (d.get("snapshot_id"),)).fetchone()) if d.get("snapshot_id") else {}
    L.append(f"=== {'HYPOTHETICAL (excluded from official PnL) ' if hyp else ''}{tid} ===")
    L.append(f"market/side/setup: {t.get('market')} {t.get('side')} {t.get('setup')} | status {t.get('status')} | synthetic={t.get('synthetic')}")
    if sn:
        f = _j(sn["features"])
        L.append(f"\n-- snapshot {sn['snapshot_id']} (cutoff {sn['cutoff_ts']}, features_hash {sn['features_hash'][:16]}, calc {sn['calc_versions']})")
        for k in ("signal_bar_end", "overnight", "atr14", "signal_bar", "prev_close", "h1_close", "ema50", "ema50_3back", "condition_labels", "gates"):
            if k in f:
                L.append(f"  {k}: {json.dumps(f[k], default=str)}")
        L.append(f"  freshness: {json.dumps(_j(sn['freshness']).get('gates'), default=str)}")
    if sg:
        L.append(f"\n-- signal {sg['signal_id']} trigger bar {sg['trigger_bar_start_ts']}..{sg['trigger_bar_end_ts']}")
        L.append(f"  levels: {sg['levels']}\n  gates: {sg['gates']}\n  condition_labels: {sg.get('condition_labels')}\n  descriptive_features: {sg.get('descriptive_features')}")
    if d:
        L.append(f"\n-- decision {d['decision_id']} action {d['action']} reason {d['reason_code']} committed {d['committed_ts']} run {d['run_id']}")
        L.append(f"  risk_model: {d['risk_model']}")
    L.append(f"\n-- sizing: notional ${t.get('notional_usd')} collateral {t.get('collateral_usd')} lev {t.get('leverage')} | initial R ${t.get('initial_risk_usd')}")
    L.append(f"-- fills: commit {t.get('commit_ts')} | entry {t.get('entry_ts')} @ {t.get('entry_price')} (proxy open {t.get('proxy_entry_open')}) | stop {t.get('stop_price')} target {t.get('target_price')} | exit {t.get('exit_ts')} @ {t.get('exit_price')} reason {t.get('exit_reason')} ambiguous={t.get('ambiguous')}")
    L.append(f"-- excursions: MAE ${t.get('mae_usd')} ({t.get('mae_r')} R) at {t.get('mae_ts')} | MFE ${t.get('mfe_usd')} ({t.get('mfe_r')} R) at {t.get('mfe_ts')}")
    if not hyp:
        L.append("\n-- costs (component | $ | status | phase | source)")
        for c in con.execute("SELECT component, amount_usd, status, phase, source, interval_start, interval_end FROM costs WHERE trade_id=? ORDER BY phase, component", (t["trade_id"],)).fetchall():
            L.append(f"  {c[0]:<22} {c[1]:>10.6f} {c[2]:<9} {c[3]:<10} {c[4]} [{c[5]}..{c[6]}]")
        L.append("\n-- ledger events")
        for e in con.execute("SELECT event_id, event_type, event_ts, price, trading_cash_delta, reserve_delta FROM trade_events WHERE trade_id=? ORDER BY recorded_ts", (t["trade_id"],)).fetchall():
            L.append(f"  {e[0]} {e[1]} {e[2]} px={e[3]} trading{e[4]:+.6f} reserve{e[5]:+.6f}")
        for q in con.execute("SELECT quote_id, quoted_ts, exit_code FROM quotes WHERE decision_ref=?", (did,)).fetchall():
            L.append(f"  quote evidence: {q[0]} at {q[1]} exit {q[2]}")
    else:
        L.append(f"\n-- modeled cost fractions: {t.get('cost_fractions')} | size flag {t.get('size_flag')}")
    if t.get("gross_pnl") is not None:
        side = t["side"]
        L.append("\n-- PnL calculation")
        L.append(f"  gross = notional x ({'exit/entry - 1' if side == 'long' else '1 - exit/entry'}) = {t['notional_usd']:.6f} x ({t['exit_price']:.6f} vs {t['entry_price']:.6f}) = {t['gross_pnl']:.6f}")
        costs = t.get("total_costs") if not hyp else (t["fees_usd"] + t["financing_usd"])
        L.append(f"  fees {t.get('fees_usd')} + financing {t.get('financing_usd')} = costs {costs} ; slippage embedded in fills {t.get('slippage_usd')}")
        L.append(f"  net = gross - costs = {t['net_pnl']:.6f} ; net R = net / R = {t['net_pnl']:.6f} / {t.get('initial_risk_usd')} = {t.get('net_r')}")
        L.append(f"  cost sensitivity (net under 1x/1.5x/2x/3x): {t.get('cost_sensitivity')}")
    return "\n".join(L)
