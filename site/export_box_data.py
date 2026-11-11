#!/usr/bin/env python3
"""Step 1 of the site pipeline: write data/*.json straight from the box's source files. Paper only.

    python3 site/export_box_data.py [--no-schedule]

Reads (read-only):
  /workspace/sports-picks/picks.jsonl            every logged pick + settlement (via sp_common.fold)
  /workspace/sports-picks/board-latest.json      Polymarket prices + DraftKings no-vig (fetch_board.py)
  /workspace/sports-picks/consensus-latest.json  the board's BET / WAIT call per game (consensus.py)
  /workspace/dashboard/build_decision.py         the box's own summary numbers (Crypto Captain ledger and
                                                 votes, Captain v3 and math-momentum, all read-only)
  ESPN public scoreboard                         schedule snapshot (fallback for the page's live load)
Writes only: data/sports/ledger.json, data/sports/upcoming.json, data/sports/schedule_snapshot.psv,
data/crypto/box_summary.json, data/export_manifest.json.
Never writes under captain-v3/. No keys, no signing, no orders, no bets. Stdlib only."""
import datetime as dt, hashlib, io, json, os, sys, urllib.request
from contextlib import redirect_stdout
from urllib.parse import quote
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SP = os.environ.get("SP_DIR", "/workspace/sports-picks")
DASH = os.environ.get("DASH_DIR", "/workspace/dashboard")
ET, UTC = ZoneInfo("America/Toronto"), dt.timezone.utc
INBOX = "robinson@mail.grokbot.com"
BOARD_MAX_AGE_H = 12          # same rule as the box page: an older board is not shown
SEED_LABEL = "Kyle (Sports Captain-seeded locks, Oct 1-6)"
sys.path.insert(0, SP); sys.path.insert(0, DASH)
import sp_common as spc        # noqa: E402
import callers_section as cb   # noqa: E402

NOW = dt.datetime.now(UTC)
Z = lambda d: d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def write(rel, text):
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, p)
    return {"path": rel, "bytes": len(text.encode()), "sha256": hashlib.sha256(text.encode()).hexdigest()}


def jdump(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def is_seed(p):
    return p["source"] == "kyle" and str(p.get("origin") or "").startswith("seed:sports-captain")


# ---------------- sports ledger ----------------
def ledger(picks):
    """Same payload the box's 'Who's calling it best' section embeds, with Kyle's own picks and the
    Sports Captain-seeded locks split into two clearly labelled rows."""
    relab = [dict(p, source="kyle_sc_seed") if is_seed(p) else p for p in picks]
    D = cb.build_payload(spc, relab)
    for f in D["F"]:
        if f["name"] == "kyle_sc_seed":
            f["name"], f["k"] = SEED_LABEL, "kyle_seed"
    out = cb.compact(D)
    own = spc.stats([p for p in picks if p["source"] == "kyle" and not is_seed(p)])
    seed = spc.stats([p for p in picks if is_seed(p)])
    out["kyle_check"] = {"source": "picks.jsonl via sp_common.fold",
                         "own": {k: own[k] for k in ("picks", "w", "l", "p", "graded", "net_usd", "pending")},
                         "sc_seeded": {k: seed[k] for k in ("picks", "w", "l", "p", "graded", "net_usd", "pending")}}
    return out


# ---------------- upcoming games ----------------
def pick_link(g, side, as_of, bd):
    st = bd.iso_et(g["start"]).strftime("%a %-I:%M %p")
    if side is None:
        r = f"Unsure: {' vs '.join(g['outcomes'])} ({st})"
        m = f"PICK v1 | sport={g['sport']} | game_id={g['game_id']} | side=UNSURE | team= | price= | shown_at={as_of}"
    else:
        t, o, c = g["outcomes"][side], g["outcomes"][1 - side], g["prices_cents"][side]
        r = f"{t} to win vs {o}, {c:g}c ({st})"
        m = f"PICK v1 | sport={g['sport']} | game_id={g['game_id']} | side={g['codes'][side].upper()} | team={t} | price={c:g} | shown_at={as_of}"
    return {"k": "u" if side is None else str(side), "r": r, "m": m, "href": bd.mailto(g, side, as_of)}


def upcoming(picks, bd):
    board = jload(os.path.join(SP, "board-latest.json"))
    cons = jload(os.path.join(SP, "consensus-latest.json")) if os.path.exists(os.path.join(SP, "consensus-latest.json")) else {}
    as_of = board.get("as_of")
    age_h = (NOW - spc.parse_dt(as_of)).total_seconds() / 3600 if as_of else 1e9
    games = []
    if age_h <= BOARD_MAX_AGE_H:
        for g in board.get("games", []):
            if spc.parse_dt(g["start"]) <= NOW:
                continue
            ga = g.get("price_as_of") or as_of
            dk = (g.get("dk") or {}).get("novig_cents")
            tracked = []
            for p in picks:
                if p.get("game_id") != g["game_id"] or p.get("superseded_by"):
                    continue
                src = "kyle_sc_seed" if is_seed(p) else p["source"]
                name = SEED_LABEL if src == "kyle_sc_seed" else spc.source_label(src)
                tracked.append({"name": name, "kind": cb._kind(p["source"]), "call": p.get("call"), "side": p.get("team"),
                                "price": p.get("paper_cents"), "prob": p.get("prob") if isinstance(p.get("prob"), (int, float)) else None,
                                "post": p.get("post_url") or None})
            c = (cons.get("games") or {}).get(g["game_id"])
            games.append({"id": g["game_id"], "sport": g["sport"], "title": g.get("title") or " vs ".join(g["outcomes"]), "start_utc": Z(spc.parse_dt(g["start"])),
                          "market_id": g.get("market_id"), "price_as_of": ga,
                          "sides": [{"team": g["outcomes"][i], "code": g["codes"][i], "pm": g["prices_cents"][i], "dk": dk[i] if dk else None,
                                     "link": pick_link(g, i, ga, bd)} for i in (0, 1)],
                          "unsure": pick_link(g, None, ga, bd), "tracked": tracked,
                          "board": None if not c else {k: c.get(k) for k in ("market_a", "combined_a", "edge_cents", "edge_side", "action", "bet_side", "bet_price", "price_as_of")}
                          | {"qualified_sources": sum(1 for s in c.get("sources", []) if s.get("qualified"))}})
    games.sort(key=lambda g: g["start_utc"])
    return {"prices_as_of_utc": Z(spc.parse_dt(as_of)) if as_of else None, "board_source": board.get("source"), "board_note": board.get("note"),
            "board_age_hours": round(age_h, 2), "board_shown": age_h <= BOARD_MAX_AGE_H,
            "consensus_as_of_utc": Z(spc.parse_dt(cons["as_of"])) if cons.get("as_of") else None, "hurdle_cents": cons.get("hurdle_cents", 3),
            "min_graded": cons.get("min_graded", spc.MIN_GRADED), "consensus_record": cons.get("record"), "games": games}


# ---------------- schedule snapshot (ESPN public scoreboard) ----------------
LG = (("nfl", "football/nfl", ""), ("cfb", "football/college-football", "&groups=80&limit=300"), ("nba", "basketball/nba", ""), ("nhl", "hockey/nhl", ""))


def schedule():
    days, d = [], NOW.astimezone(ET).date()
    for i in range(8):
        days.append(d + dt.timedelta(days=i))
        if days[-1].weekday() == 6:
            break
    rows, seen, ok = [], set(), 0
    for lg, path, extra in LG:
        for day in days:
            u = f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={day.strftime('%Y%m%d')}{extra}"
            try:
                sb = spc.http_json(u); ok += 1
            except Exception as e:
                print(f"[export] ESPN {lg} {day}: {e}", file=sys.stderr); continue
            for ev in sb.get("events", []):
                if ev["id"] in seen:
                    continue
                seen.add(ev["id"])
                c = ev["competitions"][0]; o = (c.get("odds") or [{}])[0]; ml = o.get("moneyline") or {}
                t = {x["homeAway"]: x["team"] for x in c["competitors"]}
                g = lambda ha: ((ml.get(ha) or {}).get("close") or {}).get("odds") or ""
                cell = lambda s: str(s if s is not None else "").replace("|", "/")
                rows.append("|".join(cell(x) for x in (lg, ev["id"], ev["date"], t["away"].get("shortDisplayName") or t["away"].get("displayName"),
                                                       t["home"].get("shortDisplayName") or t["home"].get("displayName"), t["away"].get("abbreviation"),
                                                       t["home"].get("abbreviation"), o.get("details"), o.get("overUnder"), g("away"), g("home"))))
    if not ok:
        return None
    rows.sort(key=lambda r: (r.split("|")[2], r))
    head = ["# source=ESPN public scoreboard API (site.api.espn.com), odds provider as returned=DraftKings",
            f"# fetched_utc={Z(NOW)}  window={days[0]}..{days[-1]} (US Eastern days)",
            "# league|espn_id|start_utc|away|home|away_abbr|home_abbr|line|total|ml_away|ml_home"]
    return "\n".join(head + rows) + "\n"


# ---------------- crypto summary (the box's own numbers, no HTML scraping) ----------------
def box_summary():
    import build_decision as bd
    with redirect_stdout(io.StringIO()):
        rows = bd.grade_votes()
        vs = bd.vote_summary(rows) if rows else None
        X = bd.build_sections(bd.mm_data(), bd.v3_data(), bd.jload(bd.LEDGER), rows, vs)
    return bd, {"morning_tags_html": X.get("morning_tags_html") or "", "open_positions_html": X.get("open_positions_html") or "",
                "sections": [{"n": n, "title": t, "html": h} for n, t, h in X["sections"] if n != 1]}


def main():
    meta = {"source": "box source files (export_box_data.py)", "generated_utc": Z(NOW),
            "generated_text": NOW.astimezone(ET).strftime("%a %b %-d, %Y %-I:%M %p ET")}
    picks = spc.fold()
    bd, box = box_summary()
    out = [write("data/sports/ledger.json", jdump({"meta": meta, **ledger(picks)})),
           write("data/sports/upcoming.json", jdump({"meta": meta, **upcoming(picks, bd)})),
           write("data/crypto/box_summary.json", jdump({"meta": meta, **box}))]
    if "--no-schedule" not in sys.argv:
        s = schedule()
        if s:
            out.append(write("data/sports/schedule_snapshot.psv", s))
        else:
            print("[export] ESPN schedule unavailable; keeping the previous snapshot", file=sys.stderr)
    write("data/export_manifest.json", json.dumps({"meta": meta, "files": out}, indent=1) + "\n")
    print(json.dumps({"exported": [o["path"] for o in out], "generated": meta["generated_text"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
