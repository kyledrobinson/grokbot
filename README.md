# GrokBot swarm home

Paper only. No keys, no live trading.

- `index.html` is the GrokBot decision page (crypto shadow block, sports board, track record), served by GitHub Pages. It is written only by `site/build.py`.
- `captain-v3/` is the Crypto Captain v3 paper core (config v3.1.1). Its `research/math_momentum/` folder holds the math-momentum shadow research layer, and `research/math-momentum-structures-v1.md` is the spec.

Databases, raw API dumps, logs and backups are kept off the repo.

## Site pipeline (`site/`, `data/`)

`index.html` is rebuilt from saved records, never edited by hand. Paper only; nothing here can trade or bet, and nothing writes under `captain-v3/` (the routine only adds new official `MM-*.json` records the box's own math-momentum runner produced).

The box runs it daily with `/workspace/dashboard/refresh_site.sh`, in this order:

```
git pull --ff-only
python3 /workspace/dashboard/build_decision.py        # box summary numbers, archive.html, grading
python3 sports-picks/fetch_board.py && consensus.py    # fresh Polymarket/DraftKings prices + the board's BET/WAIT
python3 site/export_box_data.py                        # write data/ from source files (no HTML scraping)
cp -n <box>/captain-v3/research/math_momentum/records/MM-*.json captain-v3/research/math_momentum/records/
python3 site/build.py                                  # rebuild + validate index.html; refuses to write on failure
# commit + push only if build.py exits 0 and captain-v3/ shows only new MM-*.json files
```

- `data/sports/ledger.json` every logged pick, with each bettor's record, FOLLOW / FADE verdict and against-crowd record (same numbers as the box's "Who's calling it best"). Kyle's own logged picks and the Sports Captain-seeded locks are separate rows.
- `data/sports/upcoming.json` price board (Polymarket, DraftKings no-vig) and the board's BET / WAIT call per game.
- `data/sports/schedule_snapshot.psv` ESPN schedule fallback; the page loads NFL, CFB, NBA and NHL live from ESPN in the browser.
- `data/crypto/box_summary.json` the box's track-record tables.
- `data/site/build.json` what each build read, its hashes, the sports verdict, the Kyle record check and validation results.
- Sports verdict = the board's BET / WAIT (consensus.py rules). A BET whose price is over 60 minutes old is shown as unverified.
