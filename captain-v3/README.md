# Crypto Captain v3 — paper-trading research core

**PAPER ONLY.** No private keys, wallet imports, signing, swaps, transactions or order commands.
The only Jupiter calls are the read-only `/workspace/perps-fees/quote` (POST positions/increase for public
address 3PhJ…FCq; the unsigned tx is dropped by the tool and never signed) and `/workspace/perps-fees/borrow`.
`captain/costs.py` refuses any other executable (`ALLOWED` set). This is a **generic perpetual proxy**
(Binance spot prices + Jupiter quote costs) and is not venue-ready performance.

Runs alongside the existing Crypto Captain votes; it does not read or write `/workspace/crypto-captain-votes/`.

## Layout
| Path | What |
|---|---|
| `config/strategy-v3.0.0.json` | Frozen, versioned config (setups A/B, forecast definition, risk ceilings, gates). Hash is stamped into every run. |
| `captain/` | Python 3.13 stdlib-only code: `db` (schema, WAL, flock single writer), `collector`, `providers`, `indicators`, `signals`, `risk`, `sim`, `trades`, `ledger`, `forecast`, `jobs`, `runs` (receipts), `export`, `scheduler`, `cli` |
| `captain.db` | Authoritative SQLite ledger (WAL, synchronous=FULL) |
| `exports/YYYY-MM-DD/` | Daily CSV/JSON + `report.md` + `receipts.txt` + `manifest.json` (sha256 per file); `exports/latest` symlink |
| `backups/` | SQLite online backups + `.sha256` (report job backs up after each session) |
| `logs/` | `scheduler.log`, `jobs/<date>.log`, `receipts/<run_id>.txt` |
| `raw/` | Gzipped raw provider responses referenced by `market_data.raw_ref` |
| `tests/` | Gate-3 tests; SYNTHETIC data in throwaway temp DBs only (`synthetic=1`) |

## Commands (`./bin/captain <cmd>`)
`audit`, `forecast [--session YYYY-MM-DD]`, `decide [--at ISO]`, `risk-monitor`, `close`, `report`, `weekly`,
`collect`, `status`, `export --date D`, `backup`, `restore --from B --to T`, `replay --db F`, `ack --from DELIVERY_ID`,
`scheduler` (long-running loop; start with `./bin/captain-scheduler-ensure`).
Each job emits the section-4 receipt only after its atomic write transaction commits and the written IDs are re-read.

## Data
- Primary: Binance spot USDT 1m klines via `data-api.binance.vision` (api.binance.com returns HTTP 451 from this box;
  fallback api.binance.us). BTCUSDT/ETHUSDT/SOLUSDT. Completed 15m/1h bars are aggregated only from complete sets of 1m bars.
- Secondary (cross-check only, stored separately, never blended): Coinbase Exchange BTC-USD/ETH-USD/SOL-USD 1m.
- Forecast history: native Binance 1h klines (derivation `native_1h`) since listing (BTC/ETH 2017-08-17, SOL 2020-08-11).
- Every candle stores event time (candle start/end) and `received_ts`; all decisions filter `received_ts <= cutoff`.
- Gates: latest price <= 60 s old, expected 15m bar complete, no gaps in lookback (ATR 100 bars, EMA 150 bars),
  Binance-vs-Coinbase disagreement <= 0.35 % (preregistered engineering default, to be validated).

## Definitions
- Overnight = 00:00–06:00 America/Toronto (DST-aware: 20/24/28 fifteen-minute bars). Locked at 06:00.
- ATR(14): Wilder, seeded with SMA of first 14 TRs, 100-bar warmup on completed 15m bars.
- EMA(50): seeded with SMA of first 50 closes, 150-bar warmup on completed 1h bars.
- Float tolerance: eps = 1e-9 × max(|a|,|b|).
- Forecast: r = close(11:59 1m) / open(06:00 1m) − 1 on Binance; UP > +0.5 %, DOWN < −0.5 %, else RANGE.
  Official model `freq_rolling365_laplace1` (last 365 eligible sessions before the target date, add-1 per class);
  comparisons `freq_expanding_laplace1` and `prior_session_rule_onehot`. Brier = Σ_classes (p − o)².
- Fills: open of the first 1m bar starting ≥ commit + 5 s, 5 bps adverse; stop-first on ambiguous bars; gap stops at
  the open; targets exactly at target; noon close at the 12:00 bar open; missing bars → UNRESOLVED.
- Costs: open fee / impact / network / collateral conversion = `quote`; close fee / close impact / close network = `estimate`
  (from the same quote); borrow = `estimate` integrated piecewise over `./borrow` snapshots (every ~15 min while open).
  Jupiter charges impact as an explicit fee at oracle price, so it is not also embedded in the proxy fill; the 5 bps
  slippage is a modeled proxy-vs-execution allowance.
- Risk: $50 paper, ≤2×, 1 position, 3 entries/day, planned loss ≤2 % incl. slippage, open costs, 2× stressed close costs
  and 3× stressed financing; collateral $10–$25; 5 % daily lockout; 50 % of each net winner to an internal USD reserve.

## Scheduler
No cron, crontab, systemd, or `at` exists on this box. `captain scheduler` is a singleton (flock) long-running loop
started detached with `setsid nohup`. It survives shell/agent sessions but **not a box reboot/restart**; nothing
restarts it automatically. After a reboot run `./bin/captain-scheduler-ensure`. Missed slots past grace are recorded
as `MISSED` runs, never executed late (close/report still run late to reconcile).

## Measurement (config v3.1.0, `measurement` section; setups/risk/fills identical to v3.0.0)
- **R**: `trades.initial_risk_usd` = planned loss at decision time (quoted notional); `net_r` = net PnL after all costs / R.
- **MAE/MFE**: `mae_*`/`mfe_*` ($, R, timestamp) from post-entry 1m bars only; exit bar contributes only the exit price.
- **Condition labels** (`cond-v1.1.0`, frozen on every signal/trade/hypothetical): trend TREND_UP/TREND_DOWN/RANGE from 1h close vs EMA50 + 3-bar slope; HIGH_VOL/LOW_VOL from ATR14 percentile vs trailing 480 15m ATR values; volume ABOVE_AVG/BELOW_OR_EQ_AVG = 15m trigger-bar volume vs mean of prior 20 15m bars (plus `volume_beats_avg` bool and `volume_ratio`); VWAP from Toronto 00:00 (`overnight_start`) through signal end on 1m typical price (`price_vs_vwap` above|below|at, value, distance); `trend_50`/`trend_200` = above|below latest 1h close vs EMA50/EMA200. All labels are context only — they do not change entry/exit/sizing.
- **Cost sensitivity**: `cost_sensitivity` JSON = net PnL at 1×/1.5×/2×/3× fees, slippage and financing.
- **Drawdown**: `analytics.equity_curve` rebuilt from trade_events → `exports/<date>/equity_curve.csv` + summary.
- **Descriptive features** on every signal (`descriptive_features`): SOL−BTC / ETH−BTC 1h & 24h; `whale_lean` = null (no reproducible feed). Never gated.
- **Skipped signals**: `hypothetical_outcomes` (kind SKIPPED_PROSPECTIVE, committed atomically with the SKIP decision; CHECK constraints force hypothetical=1, excluded_from_official=1). `captain hindsight --market X --side long --note ...` logs HINDSIGHT hypotheses, excluded everywhere.
- **Calibration**: `exports/<date>/calibration_points.csv` + `analytics.json` reliability bins (count, mean p, observed, Wilson 95%) and Brier.
- **Experiments**: `experiments` (+ trial_count_total, train_cutoff, forward window) and `experiment_trials` (every variant; n, mean R, sd, Sharpe, skew, kurtosis = Deflated-Sharpe inputs).
- **Run timeline**: `runs.status/attempt/duration_s/failure_class/data_quality/error` → `exports/<date>/run_timeline.csv` (MISSED rows from the scheduler).
- **Trade replay**: `./bin/captain replay <TRADE_ID|HY-...>`.
- Expectancy in R per setup / condition cell uses a session-block bootstrap (2000 resamples, seed 20260926, 90% CI); below 20 trades or 10 session blocks it is reported UNRELIABLE with no CI.
