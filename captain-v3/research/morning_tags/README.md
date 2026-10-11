# Morning tags v1.0.0 (research, read-only, context labels only)

Logged context labels for BTC/ETH/SOL inspired by the "one 4h candle at 6 AM + correlation sweep" post.
**They are never entry rules.** Nothing in Captain v3.1.1 or math-momentum v1.0.0 reads them. Paper/research only.

- Reads `captain.db` and `research/math_momentum/shadow.db` with SQLite `mode=ro`.
- Writes only `research/morning_tags/tags.db` (+ `early_read.md/json`).
- Config: `morning-tags-v1.0.0.json` (thresholds live there; sha256 stored per run).

## Run
```
cd /workspace/captain-v3
python3 -m research.morning_tags.run               # backfill missing + tag latest session and new signals; idempotent
python3 -m research.morning_tags.run --early-read  # also writes early_read.md / early_read.json
python3 -m unittest research.morning_tags.tests.test_morning_tags
```
Rows with status `ok` are final and never rewritten (use `--recompute` to rebuild everything). `pending`/`missing_data` rows are retried.

## Timestamp safety
Every tag uses only bars that **ended** at or before the moment it describes. Each row also records whether every bar used was
**received** within 60 s of that moment (`knowledge='live'`) or arrived later via backfill/catch-up (`knowledge='reconstructed'`;
same final prices, but the tag could not actually have been known in real time). Pre-2026-09-18 history uses Binance native 1h bars
(`c4_source='1h_native'`), always `reconstructed`.

## Daily tags (`daily_tags`, one row per asset per Toronto session date, moment = 06:00 ET)
1. **6 AM 4h candle** = 02:00–06:00 ET built from 240 Binance 1m bars: direction, body/upper-wick/lower-wick as % of range,
   close location in range (0 = low, 1 = high), range as % of open, range ÷ median of the same window over the prior 20 days
   (needs ≥10 days). **clean** = body > 50% of range AND opposing wick (upper wick on an up candle, lower on a down candle) < 25%.
2. **Session profile**: Asia (prior day 18:00 → 02:00 ET) direction vs London-ish (02:00 → 06:00) direction.
   `london_reversed_asia` = they differ. Per the post: reversed → `continuation_day`, not reversed → `reversal_day`. Flat → unlabelled.
3. **Prior-day gap level**: most recent unfilled 1h fair-value gap (3-candle imbalance; third candle formed during the prior ET calendar
   day; min gap 0.05%; "filled" = later 1h bar traded fully through it, checked through 06:00). Stores zone, whether it sits
   above/below/around the 06:00 price, and signed distance to its nearest edge in % and in 1h ATR(14) units. Just a level.

## Event tags (`event_tags`, keyed by (source, record_id))
Sources: `v3_signal` (signal_id), `v3_hypothetical` (hyp_id), `v3_trade` (trade_id), `math_momentum` (`<run_id>:<market>`).
Break direction: v3 setup A long / B short → ONH ("up"); A short / B long → ONL ("down"). ONH/ONL = v3's 00:00–06:00 ET 15m bars.
Window = previous, trigger and next 15m bar (±15 min); the full label is known at trigger end + 15 min (`known_at_ts`).
- `confirm_label`: how many of the other two coins traded beyond their own ONH/ONL (same direction) in the window:
  2 → `all_confirm`, 1 → `partial`, 0 → `diverge`. `confirm_at_signal` = same using only bars closed at signal time.
- `confirm_fresh_label`: same, but counting only coins whose *first* session break happened inside the window.
- `strongest`: coin furthest beyond its level (in %) at signal time; `strength_switch` = that coin's next 15m bar closed back inside.
- Math-momentum records are not breakouts: each market is tagged in whichever direction it is beyond its level at the cutoff, else `no_break`.

## Early read
`early_read.md`: v3 resolved hypothetical outcomes (and official trades) — n and mean net R per cell. Any cell n < 30 = INCONCLUSIVE.
