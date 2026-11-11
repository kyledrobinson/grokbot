#!/usr/bin/env python3
"""Step 2 of the site pipeline: rebuild index.html from saved records. Paper only.

    python3 site/export_box_data.py   # step 1: write data/ from the box's source files
    python3 site/build.py             # step 2: rebuild + validate index.html (refuses to write on failure)

Reads only: the newest official record in captain-v3/research/math_momentum/records/, data/crypto/, data/sports/,
and (to verify Kyle's record) /workspace/sports-picks/picks.jsonl. Writes only: index.html, data/site/build.json.
Never writes under captain-v3/. Stdlib only, no network."""
import datetime as dt, glob, hashlib, html, json, math, os, re, shutil, subprocess, sys, tempfile
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ET, UTC = ZoneInfo("America/Toronto"), dt.timezone.utc
REPO = "https://github.com/kyledrobinson/grokbot"
PAGES_URL = "https://kyledrobinson.github.io/grokbot/"
MM = "captain-v3/research/math_momentum"

# ---- sports page rules (the box's approved rules; nothing here sizes or places a bet) ----
PRICE_MAX_AGE_MIN = 60   # a price older than this is stale -> the board's BET is shown as unverified
PRICE_AGREE_CENTS = 3.0  # Polymarket vs live DraftKings further apart than this -> conflicting odds
VERDICT_MIN = 10         # FOLLOW / FADE verdicts need 10+ graded picks (callers_section.py)
TRUSTED_MIN = 30         # a source counts for the board only after 30 graded picks (consensus.py)
PICKS_JSONL = os.environ.get("PICKS_JSONL", "/workspace/sports-picks/picks.jsonl")


def rd(rel):
    return open(os.path.join(ROOT, rel), encoding="utf-8").read()


def jl(rel):
    return json.loads(rd(rel))


def sha(text):
    return hashlib.sha256(text.encode() if isinstance(text, str) else text).hexdigest()


def git(*a):
    try:
        return subprocess.run(("git",) + a, cwd=ROOT, capture_output=True, text=True, timeout=20,
                              env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}).stdout.strip()
    except Exception:
        return ""


def esc(x):
    return html.escape(str(x), quote=True)


def parse_z(s):
    return dt.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC) if len(s) > 17 else dt.datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)


def et(s, fmt="%a %b %-d, %-I:%M %p ET"):
    return parse_z(s).astimezone(ET).strftime(fmt)


def money(x, nd=2):
    if x is None:
        return "–"
    return ("−$" if x < 0 else "+$" if x > 0 else "$") + f"{abs(x):.{nd}f}"


def pct(x, nd=0):
    return "–" if x is None else f"{x * 100:.{nd}f}%"


def cls(x):
    return "pos" if (x or 0) > 0 else "neg" if (x or 0) < 0 else ""


def table(head, rows, klass=""):
    """rows: list of cell lists, or (raw_tr_attrs, cells) tuples."""
    h = "".join(f'<th class="{c}">{t}</th>' for t, c in head)
    b = ""
    for r in rows:
        attrs, cells = r if isinstance(r, tuple) else ("", r)
        b += f"<tr{attrs}>" + "".join(f'<td class="{head[i][1]}">{v}</td>' for i, v in enumerate(cells)) + "</tr>"
    return f'<div class="tw"><table class="{klass}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


def chip(text, kind):
    return f'<span class="chip {kind}">{esc(text)}</span>'


# ======================= crypto shadow block =======================
CLASS_TXT = {"UP": "UP (above +{b}%)", "RANGE": "RANGE (within ±{b}%)", "DOWN": "DOWN (below −{b}%)"}
GATE_TXT = {"data_quality": "Data", "ev_lcb_positive": "EV>0", "conformal_singleton": "Conformal", "prob_above_lcb": "Prob", "margin": "Margin",
            "disagreement": "Agree", "uphill_candidate": "Momentum", "risk": "Risk", "switching": "Hysteresis"}
GATE_HELP = {"data_quality": "bars at cutoff, no gaps, Binance vs Coinbase within 0.35%, cost quote present", "ev_lcb_positive": "cautious net EV after stressed costs above $0",
             "conformal_singleton": "conformal set is one direction and coverage is on target", "prob_above_lcb": "calibrated probability reliably above base rate",
             "margin": "top-class margin above its 75th percentile, in the trade direction", "disagreement": "sub-models agree (below median disagreement)",
             "uphill_candidate": "uphill momentum score and slope past threshold with the 1h trend (regime)", "risk": "inside 06:00–11:45 ET, planned loss ≤ 2% of $50, ≤ 2×",
             "switching": "gain over current position clears switch cost plus hysteresis buffer"}


def crypto(cfg):
    recs = sorted(glob.glob(os.path.join(ROOT, MM, "records", "MM-*.json")))
    rp = recs[-1]
    raw = open(rp, encoding="utf-8").read()
    r = json.loads(raw)
    rel = os.path.relpath(rp, ROOT).replace(os.sep, "/")
    band = cfg["outcomes"]["15m"]["band_pct"]
    code_h = hashlib.sha256()
    for p in sorted(glob.glob(os.path.join(ROOT, MM, "*.py"))):
        code_h.update(open(p, "rb").read())
    checks = {"config_hash_matches_repo": r["config_hash"] == sha(rd("captain-v3/config/math-momentum-v1.0.1.json")),
              "code_hash_matches_repo": r["code_hash"] == code_h.hexdigest(),
              "states_enumerated": len(r["joint_state"]["all_states"]),
              "shadow_only": r.get("shadow_only") is True and r.get("affects_official_v3") is False}
    mk = list(r["assets"])
    # recompute the one-leg state mu from the per-asset record (independent consistency check)
    ok = True
    for st in r["joint_state"]["all_states"]:
        legs = [(i, s) for i, s in enumerate(st["state"]) if s]
        if len(legs) == 1:
            i, s = legs[0]; a = r["assets"][mk[i]]
            mu = a["opportunity"]["LONG" if s > 0 else "SHORT"]["ev_lcb"] / a["ev_detail"]["notional_usd"]
            ok &= abs(mu - st["mu"]) < 1e-9
        ok &= st["feasible"] == (sum(abs(x) for x in st["state"]) <= cfg["risk"]["max_open_positions"])
    checks["joint_state_recomputed_from_assets"] = bool(ok)
    non_wait = [g for g in r["gates_by_alternative"] if not g["failed"]]
    checks["at_most_one_action"] = (r["action"] == "WAIT" and not non_wait) or (r["action"] != "WAIT" and len(r["action"].split()) == 2)

    rows, evrows, scrows = [], [], []
    for m in mk:
        a = r["assets"][m]
        P = {"UP": a["p_up"], "RANGE": a["p_range"], "DOWN": a["p_down"]}
        top = max(P, key=P.get)
        cset = "/".join(x[0] + x[1:].lower() for x in a["conformal_set"])
        conf = "low" if len(a["conformal_set"]) > 1 else "single-direction set"
        rows.append([f"<b>{m}</b>", CLASS_TXT[top].format(b=band), pct(P["UP"]), pct(P["RANGE"]), pct(P["DOWN"]),
                     f'{a["confidence_margin"]:.2f} <span class="muted">({conf}: {cset})</span>',
                     f'15 min → {et(a["target_end_ts"], "%-I:%M %p ET")}'])
        for side, ck in (("LONG", "costs_long"), ("SHORT", "costs_short")):
            c = a[ck]; net = a["ev_" + side.lower() + "_net"]; lcb = a["ev_" + side.lower() + "_lcb"]
            gross = net + c["total_stressed"]
            fees = c["open_fee"] + c["close_fee_est"]
            spread = c["open_price_impact"] + c["close_price_impact_est"] + c["collateral_conversion"]
            other = c["network_open"] + c["network_close_est"] + c["borrow_hold"] + (c["total_stressed"] - c["total_base"])
            evrows.append([f"{m} {side.lower()}", money(gross, 3), money(-fees, 3), money(-spread, 3), money(-c["modeled_slippage"], 3), money(-other, 3),
                           f'<span class="{cls(net)}">{money(net, 3)}</span>', money(lcb - net, 3), f'<b class="{cls(lcb)}">{money(lcb, 3)}</b>',
                           a["quote_" + side.lower()]["status"]])
        s = a["session_close"]
        scrows.append([m, pct(s["p_up"]), pct(s["p_range"]), pct(s["p_down"]), "/".join(x.title() for x in s["conformal_set"]), et(s["target_end_ts"], "%a %-I:%M %p ET")])
    order = cfg["gates_order"]
    grows = []
    for g in r["gates_by_alternative"]:
        cells = []
        for k in order:
            passed = g["gates"][k]
            first = g["failed"] and g["failed"][0] == k
            cells.append(f'<span class="{"ok" if passed else "no"}{" first" if first else ""}" title="{esc(GATE_HELP[k])}">{"✓" if passed else "✗"}</span>')
        grows.append([f'{g["market"]} {g["side"].lower()}', money(g["ev_lcb"], 3), f'{money(g["switch"]["required"], 3)[1:]}'] + cells +
                     [f'{len(order) - len(g["failed"])}/{len(order)}'])
    lab = lambda st: " ".join(f'{m}{"▲" if s > 0 else "▼" if s < 0 else "·"}' for m, s in zip(mk, st))
    srows = [((' class="flat"' if not any(s["state"]) else ""), [i + 1, lab(s["state"]), f'{s["J"] * 1e4:+.1f}', f'{s["mu"] * 1e4:+.1f}', f'{math.sqrt(s["var"]) * 1e4:.1f}',
              f'{s["tail_es95"] * 1e4:.1f}', "yes" if s["feasible"] else "no (over 1 position)"]) for i, s in enumerate(r["joint_state"]["all_states"])]
    feas = sum(1 for s in r["joint_state"]["all_states"] if s["feasible"])
    best_non_flat = next(s for s in r["joint_state"]["all_states"] if any(s["state"]) and s["feasible"])
    js = r["joint_state"]
    best = max(((m, sd, r["assets"][m]["ev_" + sd + "_lcb"]) for m in mk for sd in ("long", "short")), key=lambda x: x[2])
    return {"record": r, "rel": rel, "sha": sha(raw), "checks": checks, "band": band, "asset_rows": rows, "ev_rows": evrows, "sc_rows": scrows,
            "gate_rows": grows, "state_rows": srows, "feasible": feas, "best_non_flat": (lab(best_non_flat["state"]), best_non_flat["J"]),
            "best_lcb": best, "stress": js["stressed_toward_one"], "mean_corr": js["mean_corr"]}


# ======================= sports =======================
VERDICT = {"follow": ("FOLLOW", "good"), "fade": ("FADE", "bad"), "neutral": ("NEUTRAL", "neutral"), "small": ("small sample", "warn")}
TIER_RANK = {"30+": 0, "10-29": 1, "<10": 2}


def tier(g):
    return "30+" if g >= TRUSTED_MIN else "10-29" if g >= VERDICT_MIN else "<10"


def parse_pick_ts(s, as_of):
    d = dt.datetime.strptime(f"{as_of.year} {s.upper()}", "%Y %b %d %I:%M%p").replace(tzinfo=ET)
    if d > as_of + dt.timedelta(days=2):
        d = d.replace(year=as_of.year - 1)
    return d


def verify_kyle(led):
    """Recount Kyle's own logged picks straight from picks.jsonl (independent of sp_common) and compare
    with the ledger row the page shows. Any mismatch is a validation failure."""
    if not os.path.exists(PICKS_JSONL):
        return {"ok": False, "why": f"{PICKS_JSONL} not found"}
    picks, settle, repl = {}, {}, set()
    for line in open(PICKS_JSONL, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("type") == "pick" and r.get("pick_id") not in picks:
            picks[r["pick_id"]] = r
            if r.get("replaces"):
                repl.add(r["replaces"])
        elif r.get("type") == "settle" and r.get("pick_id") not in settle:
            settle[r["pick_id"]] = r
    own = [p for k, p in picks.items() if p.get("source") == "kyle" and k not in repl and (p.get("call") or "side") == "side"]
    res = [settle[p["pick_id"]] for p in own if p["pick_id"] in settle]
    w = sum(1 for s in res if s.get("result") == "W"); l = sum(1 for s in res if s.get("result") == "L")
    pnl = round(sum(s.get("pnl_usd") or 0 for s in res), 2)
    K = led["K"]
    row = next((dict(zip(K, f[3])) for f in led["F"] if f[1] == "kyle"), None)
    shown = {"w": row["w"], "l": row["l"], "pnl": row["pnl"]} if row else None
    ok = bool(row) and (w, l) == (row["w"], row["l"]) and abs(pnl - (row["pnl"] or 0)) < 0.005
    return {"ok": ok, "picks_jsonl": {"picks": len(own), "w": w, "l": l, "pnl": pnl}, "page": shown}


def sports():
    led = jl("data/sports/ledger.json")
    up = jl("data/sports/upcoming.json")
    as_of = parse_z(led["meta"]["generated_utc"]).astimezone(ET)
    K, G = led["K"], led["G"]
    by = {}
    for p in led["P"]:
        by.setdefault(p[0], []).append({"g": p[1], "sport": G[p[1]][1], "ts": parse_pick_ts(p[2], as_of) if p[2] else None, "side": p[3], "price": p[4],
                                        "res": p[5], "pnl": p[6], "url": p[7], "crowd": p[8]})
    bettors = []
    for i, f in enumerate(led["F"]):
        o = dict(zip(K, f[3]))
        sp = {s: dict(zip(K, v)) for s, v in f[4].items()} if f[4] else {s: o for s in o["sp"]}
        bettors.append({"i": i, "name": f[0], "kind": f[1], "x": f[2] or None, "o": o, "sports": sp})
    key = lambda o: (TIER_RANK[tier(o["g"])], -(o["roi"] if o["roi"] is not None else -9), -o["g"])
    ranked = sorted([b for b in bettors if b["o"]["g"]], key=lambda b: key(b["o"]))
    for k, b in enumerate(ranked):
        b["rank"] = k + 1
    idx = {b["name"]: b for b in bettors}
    games = []
    for g in up["games"]:
        tr = []
        for t in g["tracked"]:
            b = idx.get(t["name"])
            tr.append(dict(t, v=b["o"]["v"] if b else "small", g=b["o"]["g"] if b else 0))
        games.append(dict(g, tracked=tr))
    pend = []
    for b in bettors:
        for p in by.get(b["i"], []):
            if p["res"] == "":
                pend.append({"name": b["name"], "x": p["url"] or b["x"], "game": G[p["g"]][0], "sport": p["sport"], "side": p["side"], "price": p["price"],
                             "made": p["ts"].strftime("%b %-d %-I:%M %p") if p["ts"] else "", "v": b["o"]["v"], "g": b["o"]["g"]})
    done = []
    for b in bettors:
        for p in by.get(b["i"], []):
            if p["res"] in ("W", "L", "P") and p["ts"]:
                done.append((p["ts"], b["name"], G[p["g"]][0], p["sport"], p["side"], p["price"], p["res"], p["pnl"], p["url"]))
    done.sort(key=lambda x: (x[0], x[1]), reverse=True)
    sched, smeta = [], {}
    for line in rd("data/sports/schedule_snapshot.psv").split("\n"):
        if line.startswith("#"):
            for k, v in re.findall(r"(\w+)=(\S+)", line):
                smeta[k] = v
        elif line:
            c = line.split("|")
            sched.append({"lg": c[0], "id": c[1], "t": c[2], "a": c[3], "h": c[4], "aa": c[5], "ha": c[6], "line": c[7], "ou": c[8], "mla": c[9], "mlh": c[10]})
    vc = {v: sum(1 for b in ranked if b["o"]["v"] == v) for v in VERDICT}
    return {"led": led, "up": up, "bettors": bettors, "ranked": ranked, "games": games, "pending": pend, "done": done, "sched": sched, "sched_meta": smeta,
            "kyle": verify_kyle(led), "counts": {"forecasters": len(led["F"]), "with_graded": len(ranked), "picks": len(led["P"]), "graded": len(done), "games": len(G),
                                                 "follow": vc["follow"], "fade": vc["fade"], "neutral": vc["neutral"], "small": vc["small"]}}


def board_call(g, now):
    """The board's own call (consensus.py: BET needs a 3c edge and a source with 30+ graded picks), checked for freshness."""
    b = g.get("board")
    started = parse_z(g["start_utc"]) <= now
    if not b:
        return {"state": "none", "started": started, "age_min": None}
    age = (now - parse_z(b["price_as_of"])).total_seconds() / 60 if b.get("price_as_of") else 1e9
    st = "started" if started else ("bet" if b["action"] == "BET" and age <= PRICE_MAX_AGE_MIN else "bet_stale" if b["action"] == "BET" else "wait")
    return {"state": st, "started": started, "age_min": round(age)}


# ======================= page =======================
def age_span(ts, max_min, now, prefix=""):
    """Age text rendered at build time; the browser refreshes it on every view."""
    m = (now - parse_z(ts)).total_seconds() / 60
    txt = "just now" if m < 1 else f"{round(m)} min old" if m < 90 else f"{m / 60:.1f} h old" if m < 2880 else f"{round(m / 1440)} days old"
    return (f'<span data-age="{esc(ts)}" data-max="{max_min}" data-prefix="{esc(prefix)}">{esc(prefix)}{txt} '
            f'{chip("fresh" if m <= max_min else "stale", "good" if m <= max_min else "bad")}</span>')


def vchip(v, g=None):
    t, k = VERDICT.get(v, VERDICT["small"])
    return chip(t, k) + (f' <span class="muted">{g} graded</span>' if g is not None else "")


def name_cell(b):
    if b["x"]:
        return f'<a href="{esc(b["x"])}" target="_blank" rel="noopener">{esc(b["name"])}</a>'
    tag = {"kyle": "you", "kyle_seed": "seeded", "sc": "agent"}.get(b["kind"], "")
    return esc(b["name"]) + (f' <span class="tag">{tag}</span>' if tag else "")


def wl(w, l):
    return f"{w}-{l}" if (w or l) else "–"


def bettor_row(b, sport=None, rank=None):
    o = b["sports"].get(sport) if sport else b["o"]
    froi = o["froi"]
    return [rank or b["rank"], name_cell(b), o["g"], f'{o["w"]}-{o["l"]}' + (f'-{o["p"]}' if o["p"] else ""), pct(o["wp"]),
            f'<span class="{cls(o["roi"])}">{pct(o["roi"])}</span>', "–" if o["clv"] is None else f'<span class="{cls(o["clv"])}">{o["clv"]:+.2f}¢</span>',
            wl(o["aw"], o["al"]), f'{o["fw"]}-{o["fl"]} <span class="{cls(froi)}">{pct(froi)}</span>' if froi is not None else "–",
            vchip(o["v"]), " ".join(x.upper() for x in o["sp"]), (o["last"] or "")[5:]]


BET_HEAD = [("#", "n"), ("Bettor", ""), ("Graded", "n"), ("W-L", "n"), ("Win", "n"), ("ROI", "n"), ("CLV", "n hide-s"), ("Against crowd W-L", "n"),
            ("Fade W-L · ROI", "n hide-s"), ("Verdict", ""), ("Sports", "hide-s"), ("Last", "n hide-s")]


def v3_changes():
    """Working-tree changes under captain-v3/, ignoring new official MM-*.json records synced from the box (they are additions, not edits)."""
    out = []
    for line in git("status", "--porcelain", "--", "captain-v3").splitlines():
        if re.match(r"^\?\? captain-v3/research/math_momentum/records/MM-[0-9]{8}-[0-9]{4}-v[0-9.]+\.json$", line):
            continue
        out.append(line)
    return out


def main():
    now = dt.datetime.now(UTC)
    cfg = jl("captain-v3/config/math-momentum-v1.0.1.json")
    C = crypto(cfg)
    r = C["record"]
    box = jl("data/crypto/box_summary.json")
    S = sports()
    up = S["up"]
    commit = git("rev-parse", "HEAD")
    v3_dirty = v3_changes()
    v3_hash = sha(rd("captain-v3/config/strategy-v3.1.1.json"))
    calls = {g["id"]: board_call(g, now) for g in S["games"]}

    # ---- NOW cards ----
    q0 = r["opportunity_queue"][0]
    b_m, b_s, b_v = q0["market"], q0["side"].lower(), q0["ev_lcb"]
    crypto_now = (f'<div class="card"><div class="lab">Crypto · math-momentum shadow</div><div class="big {"wait" if r["action"] == "WAIT" else r["action"].split()[0].lower()}">{esc(r["action"])}</div>'
                  f'<p>Best offer {b_m} {b_s}: cautious net EV <b class="{cls(b_v)}">{money(b_v)}</b> vs $0 for waiting. First failed gate: <b>{GATE_TXT.get(r["decisive_gate"], "none")}</b>.</p>'
                  f'<p class="muted">Block {et(r["cutoff_ts"])} · {age_span(r["cutoff_ts"], 22, now)} · decision window 06:00–11:45 ET, WAIT outside it</p></div>')
    bets = [g for g in S["games"] if calls[g["id"]]["state"] == "bet"]
    stale = [g for g in S["games"] if calls[g["id"]]["state"] == "bet_stale"]
    open_g = [g for g in S["games"] if not calls[g["id"]]["started"]]
    if bets:
        g = bets[0]
        sports_big, sports_txt = "BET (paper)", f'{esc(g["board"]["bet_side"])} at {g["board"]["bet_price"]:g}¢ · board edge {g["board"]["edge_cents"]:+.1f}¢' + (f" · {len(bets) - 1} more below" if len(bets) > 1 else "")
    else:
        sports_big = "NO QUALIFYING BET / WAIT"
        if not up["board_shown"]:
            sports_txt = f'The price board is {up["board_age_hours"]:.0f} h old, so no games are shown.'
        elif not open_g:
            sports_txt = "No tracked game is still upcoming."
        elif stale:
            sports_txt = f'The board had a BET on {esc(stale[0]["board"]["bet_side"])}, but its price is over {PRICE_MAX_AGE_MIN} min old (unverified).'
        else:
            sports_txt = f'The board has no BET on any of {len(open_g)} upcoming game{"s" if len(open_g) != 1 else ""}: none has an edge of {up["hurdle_cents"]:g}¢ or more backed by a source with {TRUSTED_MIN}+ graded picks.'
    sports_now = (f'<div class="card"><div class="lab">Sports · paper picks</div><div class="big {"go" if bets else "wait"}" id="sp-big">{sports_big}</div><p id="sp-why">{sports_txt}</p>'
                  f'<p class="muted">{len(open_g)} upcoming games · {len(S["pending"])} pending picks · <a href="#upcoming">details</a></p></div>')

    # ---- freshness ----
    lm = S["led"]["meta"]
    fres = [
        ["Shadow block (latest official)", f'<a href="{REPO}/blob/{commit}/{C["rel"]}">{r["run_id"]}</a>', et(r["cutoff_ts"]), age_span(r["cutoff_ts"], 22, now)],
        ["Captain v3.1.1 (official paper)", "frozen · " + ("unchanged vs commit" if not v3_dirty else "MODIFIED"), "summary " + box["meta"]["generated_text"], age_span(box["meta"]["generated_utc"], 1560, now)],
        ["Sports ledger (picks.jsonl)", '<a href="data/sports/ledger.json">ledger.json</a>', lm["generated_text"], age_span(lm["generated_utc"], 1560, now)],
        ["Polymarket / DraftKings no-vig prices", "fetch_board.py", et(up["prices_as_of_utc"]) if up["prices_as_of_utc"] else "–",
         age_span(up["prices_as_of_utc"], PRICE_MAX_AGE_MIN, now) if up["prices_as_of_utc"] else chip("missing", "bad")],
        ["Board BET / WAIT calls", "consensus.py", et(up["consensus_as_of_utc"]) if up["consensus_as_of_utc"] else "–",
         age_span(up["consensus_as_of_utc"], PRICE_MAX_AGE_MIN, now) if up["consensus_as_of_utc"] else chip("missing", "bad")],
        ["Schedules + live lines (ESPN, DraftKings)", '<span id="live-src">snapshot</span>', f'<span id="live-ts">{et(S["sched_meta"]["fetched_utc"])}</span>',
         age_span(S["sched_meta"]["fetched_utc"], PRICE_MAX_AGE_MIN, now).replace("<span data-age", '<span id="live-age" data-age', 1)],
        ["Page calculations", f'build <a href="{REPO}/commit/{commit}">{commit[:7]}</a> + working tree', now.astimezone(ET).strftime("%a %b %-d, %-I:%M %p ET"),
         age_span(now.strftime("%Y-%m-%dT%H:%M:%SZ"), 1560, now)],
    ]
    fresh_html = table([("Source", ""), ("Record", ""), ("As of", "n hide-s"), ("Status", "n")], fres, "fresh")

    # ---- crypto section ----
    ck = C["checks"]
    th = r["thresholds"]; cf = r["conformal"]
    crypto_html = (
        f'<p class="why"><b>{esc(r["action"])}</b> — {esc(r["decisive_gate_explanation"])} At most one paper action is ever allowed.</p>'
        + table([("Asset", ""), ("Direction (most likely)", ""), ("P up", "n"), ("P range", "n"), ("P down", "n"), ("Confidence (margin)", ""), ("Horizon", "n")], C["asset_rows"])
        + "<h3>Expected value per $50 paper position (after every deduction)</h3>"
        + table([("Trade", ""), ("Gross", "n"), ("Fees", "n"), ("Spread + impact", "n hide-s"), ("Slippage", "n hide-s"), ("Network, borrow, stress", "n hide-s"), ("Net EV", "n"),
                 ("Uncertainty", "n"), ("Cautious EV", "n"), ("Quote", "n hide-s")], C["ev_rows"])
        + '<p class="muted">Net EV = gross − stressed costs from the read-only Jupiter quote. Cautious EV = net − 1.645 × standard error. WAIT = $0.00 and wins unless a cautious EV is above zero.</p>'
        + f'<details><summary>Gate audit: {sum(1 for g in r["gates_by_alternative"] if not g["failed"])} of {len(r["gates_by_alternative"])} long/short alternatives passed all {len(cfg["gates_order"])} gates</summary>'
        + table([("Alternative", ""), ("Cautious EV", "n"), ("Hysteresis need", "n hide-s")] + [(GATE_TXT[k], "c") for k in cfg["gates_order"]] + [("Passed", "n")], C["gate_rows"], "gates")
        + f'<p class="muted">✗ outlined = the first gate that stopped it. Thresholds this block: margin ≥ {th["theta_M"]:.2f}, disagreement ≤ {th["theta_D"]:.4f}, '
          f'conformal coverage {pct(cf["rolling_coverage"], 1)} (target {pct(1 - cf["alpha"])}; action permission {"on" if cf["action_permission"] else "off"}). Hover a mark for the rule.</p></details>'
        + f'<details><summary>All 27 long / neutral / short states ({C["feasible"]} feasible under the one-position limit; best is flat at 0.0, best non-flat {C["best_non_flat"][0]} at {C["best_non_flat"][1] * 1e4:+.1f} bp)</summary>'
        + table([("#", "n"), ("State", ""), ("J (bp)", "n"), ("Net μ (bp)", "n"), ("σ (bp)", "n"), ("ES95 (bp)", "n"), ("Feasible", "")], C["state_rows"], "states")
        + f'<p class="muted">J = cautious net return − 10·variance − 0.5·ES95, in basis points of notional. ▲ long, ▼ short, · neutral. Mean correlation {C["mean_corr"]:.2f}; '
          f'{"correlations stressed halfway to 1 (high volatility)" if C["stress"] else "no correlation stress"}; shrinkage 0.3.</p></details>'
        + "<details><summary>Session-close forecast (reported only, never drives the action)</summary>"
        + table([("Asset", ""), ("P up >+0.5%", "n"), ("P range", "n"), ("P down", "n"), ("Conformal set", ""), ("Target", "n")], C["sc_rows"]) + "</details>")
    crypto_html += (f'{box["morning_tags_html"] or ""}<p class="muted"><b>Open paper positions:</b> {re.sub(r"</?p>", "", box["open_positions_html"] or "–")} '
                    f'<b>Captain v3.1.1:</b> frozen and separate; this page reads it and never writes to it.</p>'
                    f'<p class="muted">Reproduce: commit <a href="{REPO}/commit/{commit}"><code>{commit[:12]}</code></a> · run <code>{r["run_id"]}</code> · cutoff <code>{r["cutoff_ts"]}</code> · '
                    f'knowledge <code>{r["knowledge_ts"]}</code> · config <code>{r["config_hash"][:12]}</code> {"✓" if ck["config_hash_matches_repo"] else "✗"} · '
                    f'code <code>{r["code_hash"][:12]}</code> {"✓" if ck["code_hash_matches_repo"] else "✗"} · record sha256 <code>{C["sha"][:12]}</code></p>')

    # ---- sports: upcoming games ----
    price_ts = up["prices_as_of_utc"]
    urows = []
    for g in S["games"]:
        c = calls[g["id"]]; b = g.get("board")
        matchup = " vs ".join(esc(s["team"]) for s in g["sides"])
        price = " · ".join(f'{esc(s["team"])} <b>{s["pm"]:g}¢</b>' + (f' <span class="muted">DK {s["dk"]:g}</span>' if s["dk"] is not None else "") for s in g["sides"])
        side_picks = []
        for s in g["sides"]:
            who = [t for t in g["tracked"] if t["call"] == "side" and t["side"] == s["team"]]
            if who:
                side_picks.append(f'<b>{esc(s["team"])}</b>: ' + ", ".join(
                    (f'<a href="{esc(t["post"])}" target="_blank" rel="noopener">{esc(t["name"])}</a>' if t["post"] and t["post"].startswith("https://x.com/") else esc(t["name"]))
                    + (" " + vchip(t["v"]) if t["v"] != "small" else "") for t in who))
        uns = [t for t in g["tracked"] if t["call"] == "unsure"]
        if any(t["v"] == "small" for t in g["tracked"] if t["call"] == "side"):
            side_picks.append(f'<span class="muted">no chip = under {VERDICT_MIN} graded picks, no verdict</span>')
        if uns:
            side_picks.append("Unsure: " + ", ".join(esc(t["name"]) for t in uns))
        if b:
            if c["state"] == "bet":
                call = chip(f'BET {b["bet_side"]} {b["bet_price"]:g}¢', "good")
            elif c["state"] == "bet_stale":
                call = chip(f'BET {b["bet_side"]}', "warn") + "<br>" + chip("price stale · unverified", "bad")
            elif c["state"] == "started":
                call = chip("STARTED", "neutral")
            else:
                call = chip("WAIT", "neutral")
            why = (f'market {b["market_a"]:g}% → combined {b["combined_a"]:g}% for {esc(g["sides"][0]["team"])}; '
                   f'edge {b["edge_cents"]:+.1f}¢ on {esc(b["edge_side"])} · {b["qualified_sources"]} trusted source{"s" if b["qualified_sources"] != 1 else ""}')
        else:
            call, why = (chip("STARTED", "neutral") if c["started"] else chip("WAIT", "neutral")), "no board call for this game"
        call = f'<span data-verdict>{call}</span><br><span class="muted">{why}</span>'
        links = "".join(f'<a class="pick" data-g="{esc(g["id"])}" data-k="{esc(s["link"]["k"])}" data-r="{esc(s["link"]["r"])}" data-m="{esc(s["link"]["m"])}" href="{esc(s["link"]["href"])}">{esc(s["team"])}</a>'
                        for s in g["sides"])
        u = g["unsure"]
        links += f'<a class="pick unsure" data-g="{esc(g["id"])}" data-k="u" data-r="{esc(u["r"])}" data-m="{esc(u["m"])}" href="{esc(u["href"])}">Unsure</a>'
        urows.append((f' data-game="{esc(g["id"])}"', [
            f'<b>{matchup}</b> <span class="tag">{g["sport"].upper()}</span><br><span class="muted">{et(g["start_utc"], "%a %-I:%M %p ET")} · Moneyline</span>',
            f'{price}<br><span class="muted">Polymarket · {et(g["price_as_of"], "%-I:%M %p")}</span>',
            '<span data-live><span class="muted">loads in browser</span></span>',
            "<br>".join(side_picks) if side_picks else '<span class="muted">no tracked picks</span>',
            call, f'<span class="calls">{links}</span>']))
    up_head = [("Game · start", ""), ("Price (Polymarket, DK no-vig)", "n"), ("Live line (DraftKings)", "n hide-s"), ("Tracked picks · verdict", ""), ("Board call", ""), ("Your paper call", "")]
    up_html = table(up_head, urows, "up") if urows else '<p class="muted">No upcoming games on the board.</p>'
    pend_rows = [[f'<a href="{esc(p["x"])}" target="_blank" rel="noopener">{esc(p["name"])}</a>' if p["x"] else esc(p["name"]), esc(p["game"]) + f' <span class="tag">{p["sport"].upper()}</span>',
                  f'<b>{esc(p["side"])}</b>', f'{p["price"]}¢', p["made"], vchip(p["v"], p["g"])] for p in sorted(S["pending"], key=lambda p: (p["game"], p["side"]))]
    done_rows = [[d[0].strftime("%b %-d"), f'<a href="{esc(d[8])}" target="_blank" rel="noopener">{esc(d[1])}</a>' if d[8] else esc(d[1]), esc(d[2]) + f' <span class="tag">{d[3].upper()}</span>',
                  esc(d[4]), f"{d[5]}¢", f'<span class="{"pos" if d[6] == "W" else "neg" if d[6] == "L" else ""}">{d[6]}</span>', f'<span class="{cls(d[7])}">{money(d[7])}</span>'] for d in S["done"][:15]]
    cnt = S["counts"]

    # ---- Kyle's record (own logged picks; seeded locks shown separately) ----
    K = S["led"]["K"]
    kb = next((b for b in S["bettors"] if b["kind"] == "kyle"), None)
    sb = next((b for b in S["bettors"] if b["kind"] == "kyle_seed"), None)
    kv = S["kyle"]
    if kb:
        o = kb["o"]
        kyle_html = (f'<div class="cand"><b>Kyle (your own logged picks): {o["w"]}-{o["l"]}' + (f'-{o["p"]}' if o["p"] else "") + f', <span class="{cls(o["pnl"])}">{money(o["pnl"])}</span></b> '
                     f'over {o["g"]} graded at $10 flat · ROI {pct(o["roi"])} · verdict {vchip(o["v"])} · fading you would be {o["fw"]}-{o["fl"]} ({pct(o["froi"])}). '
                     f'<span class="muted">Checked against picks.jsonl at build: {"✓ matches" if kv["ok"] else "✗ MISMATCH"}.</span></div>')
        if sb:
            so = sb["o"]
            kyle_html += (f'<p class="muted">Counted separately: {so["g"]} Sports Captain-seeded locks from Oct 1–6, {so["w"]}-{so["l"]}, {money(so["pnl"])}. '
                          f'They are not in your record above. Other tallies of your picks (for example Sports Captain\'s own count) are not used on this page.</p>')
    else:
        kyle_html = '<p class="muted">No picks logged for Kyle.</p>'

    def sport_board(s):
        L = [b for b in S["ranked"] if s in b["sports"] and b["sports"][s]["g"]]
        L.sort(key=lambda b: key_s(b["sports"][s]))
        rows = [bettor_row(b, s, k + 1) for k, b in enumerate(L[:8])]
        ne = sum(1 for b in L if b["sports"][s]["g"] >= TRUSTED_MIN)
        return f'<details><summary>{s.upper()} leaderboard: {len(L)} bettors, {ne} with {TRUSTED_MIN}+ graded</summary>' + table(BET_HEAD, rows) + "</details>"
    key_s = lambda o: (TIER_RANK[tier(o["g"])], -(o["roi"] if o["roi"] is not None else -9), -o["g"])

    sports_sorted = sorted({s for b in S["ranked"] for s in b["sports"]})
    data = {"built": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "price_ts": price_ts, "sched_ts": S["sched_meta"]["fetched_utc"],
            "cfg": {"max_age": PRICE_MAX_AGE_MIN, "agree": PRICE_AGREE_CENTS, "verdict_min": VERDICT_MIN, "trusted_min": TRUSTED_MIN, "hurdle": up["hurdle_cents"]},
            "games": [{"id": g["id"], "sport": g["sport"], "start": g["start_utc"],
                       "bet": ({"side": g["board"]["bet_side"], "price": g["board"]["bet_price"], "edge": g["board"]["edge_cents"], "ts": g["board"]["price_as_of"]}
                               if g.get("board") and g["board"]["action"] == "BET" else None),
                       "sides": [{"team": s["team"], "pm": s["pm"], "dk": s["dk"]} for s in g["sides"]]} for g in S["games"]],
            "sched": S["sched"], "sports": sports_sorted}

    track = "".join(f'<details{" open" if s["n"] == 2 else ""}><summary>{esc(s["title"])}</summary>{s["html"]}</details>' for s in box["sections"])
    css, js = rd("site/style.css"), rd("site/app.js")
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    cr = up.get("consensus_record") or {}
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="generator" content="grokbot-site-builder 1.1"><meta name="robots" content="noindex">
<title>GrokBot decisions</title><style>{css}</style></head><body><main>
<header><h1>GrokBot <span class="paper">PAPER ONLY · no real trades or bets</span></h1>
<nav><a href="#now">Now</a><a href="#crypto">Crypto block</a><a href="#upcoming">Upcoming bets</a><a href="#bettors">Bettors</a><a href="#completed">Completed</a><a href="#schedule">Schedules</a><a href="#track">Track record</a><a href="#fresh">Freshness</a></nav></header>
<section id="now"><h2>Now</h2><div class="cards">{crypto_now}{sports_now}</div></section>
<section id="crypto"><h2>Crypto: math-momentum shadow block <span class="sub">{et(r["cutoff_ts"])}</span></h2>{crypto_html}</section>
<section id="upcoming"><h2>Upcoming / pending bets</h2>
<div class="cand" id="cand"><b id="cand-h">{sports_big}</b> <span id="cand-t">{sports_txt}</span></div>
{up_html}
<p class="muted">Board call = the box's consensus (consensus.py): <b>BET</b> only when the combined estimate beats the Polymarket price by {up["hurdle_cents"]:g}¢ or more and a source with {TRUSTED_MIN}+ graded picks is behind it; otherwise WAIT. A BET whose price is over {PRICE_MAX_AGE_MIN} min old is shown as unverified. Verdicts: FOLLOW = positive ROI and a win rate above the prices they took; FADE = betting the other side would have made money; {VERDICT_MIN}+ graded picks needed. Prices as of {age_span(price_ts, PRICE_MAX_AGE_MIN, now, et(price_ts) + " · ") if price_ts else "–"}. Paper calls are logged by email at the price shown and rejected after kickoff. Board record so far: {cr.get("bets", 0)} BETs ({cr.get("w", 0)}-{cr.get("l", 0)}, {money(cr.get("net_usd", 0))}) over {cr.get("games_graded", 0)} graded games.</p>
<h3>Pending picks ({len(S["pending"])})</h3>{table([("Bettor", ""), ("Game", ""), ("Pick", ""), ("Price", "n"), ("Made (ET)", "n hide-s"), ("Verdict", "")], pend_rows) if pend_rows else '<p class="muted">None.</p>'}
</section>
<section id="bettors"><h2>Bettors: follow or fade <span class="sub">{cnt["with_graded"]:,} with graded picks · {cnt["follow"]} FOLLOW · {cnt["fade"]} FADE · {cnt["neutral"]} neutral · {cnt["small"]:,} under {VERDICT_MIN} graded</span></h2>
{kyle_html}
<div class="cbf"><input id="bq" type="search" placeholder="Search a name or @handle" aria-label="Search bettor"><select id="bsport" aria-label="Sport"><option value="">All sports</option>{"".join(f'<option value="{s}">{s.upper()}</option>' for s in sports_sorted)}</select>
<select id="btier" aria-label="Verdict"><option value="">Any verdict</option><option value="follow">FOLLOW</option><option value="fade">FADE</option><option value="neutral">NEUTRAL</option><option value="small">Small sample</option></select>
<button id="bmore" type="button">Show all</button></div>
<div id="btable">{table(BET_HEAD, [(f' data-i="{b["i"]}"', bettor_row(b)) for b in S["ranked"][:15]])}</div><p class="muted" id="bcount">Top 15 of {len(S["ranked"]):,}. Tap a row for that bettor's picks.</p>
{"".join(sport_board(s) for s in sports_sorted)}
<p class="muted">Ranked by sample first ({TRUSTED_MIN}+ graded, then {VERDICT_MIN}–{TRUSTED_MIN - 1}, then under {VERDICT_MIN}), then ROI, so a 2–0 record never outranks a 30-pick one. $10 flat per pick at the Polymarket price when it was posted. CLV = closing price minus pick price. Against crowd = their record when they went against the majority of 3+ other tracked handicappers. Fade = $10 on the other side at 100 minus their price.</p></section>
<section id="completed"><h2>Completed picks <span class="sub">latest 15 of {cnt["graded"]:,} graded</span></h2>
{table([("Date", "n"), ("Bettor", ""), ("Game", ""), ("Pick", ""), ("Price", "n"), ("Result", "n"), ("P&amp;L ($10)", "n")], done_rows)}
<p class="muted">Graded from Polymarket results. Every pick is in <a href="data/sports/ledger.json">ledger.json</a> (opened by the bettor table, not shown raw).</p></section>
<section id="schedule"><h2>Schedules <span class="sub" id="sched-note">Eastern time · snapshot {et(S["sched_meta"]["fetched_utc"])}</span></h2>
<div class="tabs" id="sched-tabs"></div><div id="sched-body"><p class="muted">Loading live schedules…</p></div>
<p class="muted">NFL, college football (FBS), NBA and NHL from ESPN's public scoreboard; lines are DraftKings as relayed by ESPN and are shown for reference only. A game is tagged <span class="tag pk">tracked</span> when it is on the price board. If the live load fails, the saved snapshot is shown and marked stale.</p></section>
<section id="track"><h2>Track record <span class="sub">box summary {esc(box["meta"]["generated_text"])}</span></h2>{track}</section>
<section id="fresh"><h2>Data freshness and sources</h2>{fresh_html}<p class="muted">Status is recomputed in your browser each time the page opens. Anything past its limit is labelled stale and cannot support a decision.</p></section>
<footer><b>Paper only. Live trading off. No real trade, wallet, signing or bet is possible from this page.</b><br>
Built {now.astimezone(ET).strftime("%a %b %-d, %Y %-I:%M %p ET")} from <a href="{REPO}/commit/{commit}">{commit[:7]}</a> · <a href="archive.html">Full archive (old dashboard)</a> · <a href="{REPO}/tree/main/{MM}/records">all shadow records</a> · <a href="{REPO}/blob/main/captain-v3/research/math-momentum-structures-v1.md">spec</a> · <a href="data/site/build.json">build record</a></footer>
</main><div id="pickbar" hidden><div id="pickbtns"></div><button id="pickclear" type="button">Clear</button></div>
<script type="application/json" id="gb-data">{data_json}</script>
<script>{js}</script></body></html>
"""
    # ---- validate before writing ----
    v = validate(page)
    if not kv["ok"]:
        v["issues"].append(f"Kyle's record on the page does not match picks.jsonl: {kv}"); v["ok"] = False
    if v3_dirty:
        v["issues"].append(f"captain-v3/ has changes other than new MM- records: {v3_dirty[:5]}"); v["ok"] = False
    if not all(ck.values()):
        v["issues"].append(f"shadow record checks failed: {ck}"); v["ok"] = False
    verdict = sports_big + (f": {sports_txt}" if not bets else f" {sports_txt}")
    manifest = {"built_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "commit": commit, "pages_url": PAGES_URL,
                "captain_v3": {"version": "v3.1.1", "config_sha256": v3_hash, "working_tree_changes": v3_dirty or "none"},
                "shadow": {"latest_complete": {"run_id": r["run_id"], "path": C["rel"], "sha256": C["sha"], "cutoff_ts": r["cutoff_ts"], "action": r["action"],
                                               "decisive_gate": r.get("decisive_gate"), "checks": ck}},
                "sports": {"verdict": re.sub(r"<[^>]+>", "", verdict), "board_calls": {k: c["state"] for k, c in calls.items()}, "counts": cnt, "kyle_check": kv,
                           "price_snapshot_utc": price_ts, "consensus_utc": up["consensus_as_of_utc"], "schedule_snapshot_utc": S["sched_meta"]["fetched_utc"], "schedule_games": len(S["sched"])},
                "inputs": {p: sha(open(os.path.join(ROOT, p), "rb").read()) for p in ["data/sports/ledger.json", "data/sports/upcoming.json", "data/sports/schedule_snapshot.psv",
                                                                                   "data/crypto/box_summary.json"]},
                "output": {"index_html_bytes": len(page.encode()), "index_html_sha256": sha(page)}, "validation": v}
    os.makedirs(os.path.join(ROOT, "data", "site"), exist_ok=True)
    with open(os.path.join(ROOT, "data/site/build.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=1)
    if not v["ok"]:
        print(json.dumps(v, indent=1)); print("VALIDATION FAILED: index.html not written"); return 1
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print(json.dumps({"index_html_bytes": len(page.encode()), "crypto_action": r["action"], "decisive_gate": r.get("decisive_gate"), "shadow_checks": ck,
                      "sports_verdict": manifest["sports"]["verdict"], "kyle_check": kv, "counts": cnt, "validation": v}, indent=1))
    return 0


class _P(HTMLParser):
    VOID = {"meta", "br", "input", "img", "link", "hr"}

    def __init__(self):
        super().__init__(); self.stack, self.ids, self.hrefs, self.err = [], [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a: self.ids.append(a["id"])
        if tag == "a" and "href" in a: self.hrefs.append(a["href"])
        if tag not in self.VOID: self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID: return
        if not self.stack or self.stack[-1] != tag: self.err.append(f"unbalanced </{tag}> (open: {self.stack[-3:]})")
        else: self.stack.pop()


def validate(page):
    p = _P(); p.feed(page)
    issues = list(p.err[:5]) + [f"unclosed <{t}>" for t in p.stack]
    dup = sorted({i for i in p.ids if p.ids.count(i) > 1})
    if dup: issues.append(f"duplicate ids {dup}")
    local, ext, anchors = set(), set(), set()
    for h in p.hrefs:
        if h.startswith("#"): anchors.add(h[1:])
        elif h.startswith("mailto:"): pass
        elif re.match(r"https?://", h): ext.add(h)
        else: local.add(h.split("#")[0])
    for a in anchors:
        if a not in p.ids: issues.append(f"anchor #{a} has no target")
    for l in local:
        if l.startswith("/"): issues.append(f"root-absolute link {l} breaks under /grokbot/")
        if l != "data/site/build.json" and not os.path.exists(os.path.join(ROOT, l)): issues.append(f"missing local file {l}")
    for h in ext:
        m = re.match(re.escape(REPO) + r"/(?:blob|tree)/[^/]+/(.+)$", h)
        if m and not os.path.exists(os.path.join(ROOT, m.group(1))): issues.append(f"repo link to missing path {m.group(1)}")
    if re.search(r'(src|href)="/(?!/)', page): issues.append("root-absolute asset path")
    if "http://" in re.sub(r"http://www\.w3\.org", "", page): issues.append("insecure http:// reference (mixed content on Pages)")
    js_ok = None
    if shutil.which("node"):
        scripts = re.findall(r"<script>(.*?)</script>", page, re.S)
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write("\n;".join(scripts)); tmp = f.name
        js_ok = subprocess.run(["node", "--check", tmp], capture_output=True, text=True).returncode == 0
        os.remove(tmp)
        if not js_ok: issues.append("inline script failed node --check")
    try:
        json.loads(re.search(r'id="gb-data">(.*?)</script>', page, re.S).group(1).replace("<\\/", "</"))
    except Exception as e:
        issues.append(f"embedded data not valid JSON: {e}")
    return {"ok": not issues, "issues": issues, "ids": len(p.ids), "anchors_checked": len(anchors), "local_links_checked": sorted(local), "external_links": len(ext),
            "repo_links_checked": sum(1 for h in ext if h.startswith(REPO)), "js_syntax_ok": js_ok, "has_viewport_meta": 'name="viewport"' in page,
            "relative_urls_only": not re.search(r'(src|href)="/(?!/)', page), "tables_scroll_wrapped": page.count("<table") == page.count('<div class="tw"><table') }


if __name__ == "__main__":
    sys.exit(main())
