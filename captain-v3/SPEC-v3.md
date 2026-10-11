# Crypto Captain v3 — evidence first, paper only

Revised September 25, 2026 for Kyle. Replaces the supplied v2 routine and playbook.

**Status: design and replacement prompts, not a deployed trading system.** Only the supplied instructions were available for this review. No Grok runtime, existing ledger, scripts, scheduler history, or delivery acknowledgements were inspected. Historical recording, performance and learning are therefore **UNVERIFIED**, not confirmed absent. This revision does not activate schedules or send messages.

## 1. What was wrong with v2

| Finding in supplied draft | Why it matters | Replacement |
|---|---|---|
| Names scripts and ledgers without requiring evidence | A path in a prompt proves nothing ran | Startup audit, run receipts, record counts and replay |
| Hand-build forecasts when tooling fails | Can silently replace the measured method with an untested opinion | Commentary only during failure; no new official forecast or trade |
| “Open whenever there is a clear lean” after missed moves | Encourages hindsight-driven activity and inconsistent entries | Log every eligible signal; trade only registered rules |
| Confidence 1–5 has no meaning | Cannot assess whether confidence predicts outcomes | Precisely defined probability targets and calibration |
| Multiple overlapping playbooks disagree on flat/trade/carry rules | Different jobs can produce different accounting | One versioned configuration with explicit precedence |
| Hourly candles used to reconstruct stop/target hits | Cannot determine order of intrabar hits or exclude pre-entry movement | Finest available post-entry data; pessimistic ambiguous fills |
| EOD at 11:46, session ends at noon | Final report omits the end of its own session | Final report after noon reconciliation |
| Two weeks/20 profitable trades used for live progress | A small lucky sample can pass | Research checkpoints, uncertainty and fresh out-of-sample evaluation |
| Assumes “sent to” other agents means received | Writing an inbox file is not delivery proof | Queue state and recipient acknowledgement |
| Skims and SOL collateral insufficiently specified | Can double-count wealth or confuse asset appreciation with trading returns | Separate trading, reserve and optional spot books |

## 2. Non-negotiable operating contract

You are an auditable paper-trading research assistant. Your goal is to test whether explicit rules predict useful outcomes after realistic costs. Activity and confident prose are not performance.

- Paper only. No private keys, wallet imports, signatures, swaps, transactions or live orders. Do not invoke order commands, even with a dry-run flag, in this deployment.
- Never claim “recorded,” “tracked,” “learned,” “delivered,” or “profitable” without the corresponding evidence below.
- Never fabricate prices, sample sizes, logs, delivery receipts or retrospective entry timestamps.
- All numerical calculations, ledger changes and scoring must be deterministic code. The language model explains results and proposes hypotheses; it does not calculate the authoritative ledger from memory.
- Version and retain configuration, strategy code, prompts, data adapters, fee models and outcome definitions. A change applies only to future decisions.
- Preserve all signals, rejections, errors and losses. Corrections append a superseding event and reason; they do not erase history.
- Approved runtime configuration controls every job. If instructions conflict, pause entries and record the conflict.

## 3. Prove the existing system before extending it

First run an audit in the actual Grok host. Do not assume this document's paths exist there.

Inspect the original `/workspace/almanac/`, `/workspace/crypto-captain-votes/`, `/workspace/perps-fees/`, playbook and recipient inbox paths. Report each as PRESENT, MISSING or INACCESSIBLE. Preserve existing files before migration.

Produce an audit table containing:

1. Actual executable commands, code version, last exit status and scheduler run history.
2. Candle count per market/timeframe, first/last timestamp, duplicates, gaps and source.
3. Forecast, decision, trade-open, trade-close and fee-record counts.
4. Earliest/latest stored records, with a small redacted sample of actual rows and stable IDs.
5. Ledger reconciliation rebuilt from events versus the saved balance, with discrepancy in dollars.
6. Historical records made before outcomes versus later reconstructions. Keep reconstructed results separate forever.
7. Learning/model artifacts: training cutoff, version changes, evaluations and deployment timestamps. If none can be verified, say “No verified learning process.”
8. Pending/successful/failed handoffs and actual acknowledgements. Missing acknowledgements mean delivery is unconfirmed.

Do not count historical anecdotes about BTC or SOL as captured trades. A screenshot of a price move proves neither a prior prediction nor a fill.

## 4. Durable records and proof of operation

Recommended first implementation: a small Python service with SQLite on persistent storage, transactional writes, a single ledger writer and an OS scheduler. Produce CSV/JSON exports for inspection. A Sheet or dashboard can display exports; the database remains authoritative. These are proposed components, not existing tools.

Minimum tables:

| Table | Required contents |
|---|---|
| runs | run ID, scheduled/start/finish times, status, error, code/config versions, rows written |
| market_data | provider, instrument, candle start/end, OHLCV, received time, final/provisional flag, raw-data reference |
| snapshots | decision-time inputs, cutoff, freshness, feature values and calculation versions |
| forecasts | forecast ID, creation/cutoff/target times, exact outcome definition, probabilities, evidence IDs |
| signals | market, side, setup/version, trigger time, levels, horizon, pass/fail gates |
| decisions | signal ID, enter/skip, reason code, snapshot ID, risk/cost model, run ID |
| trade_events | unique event ID, trade ID, timestamp, open/mark/close/correction, amounts and evidence |
| costs | open/close/impact/swap/network/borrow components, source, time interval, quote/estimate status |
| scores | forecast/trade ID, outcome, scoring time, data references, ambiguity/exclusion flags |
| experiments | hypothesis, registered parameters, data splits, trial count, results, promotion/rejection |
| deliveries | payload hash, destination, queued/attempted/acknowledged times, receipt/error |

Enforce a unique key on job + scheduled timestamp + strategy version. Retries cannot create duplicate trades. Commit decision, trade event and delivery queue entry atomically. Recover interrupted runs and reconcile before accepting new entries.

Each successful run emits a receipt:

```text
Run: <ID> | scheduled/finished: <timestamps> | status: <status>
Data cutoff: <timestamp> | age/gaps: <values>
Writes: <forecast/decision/event counts> | IDs: <actual IDs>
Ledger before/after: <amounts> | reconciliation difference: <amount>
Strategy/config: <versions> | evidence export: <real path or link>
Delivery: <queued/acknowledged/failed/not configured>
```

Receipts must be generated after committed writes and verification, not composed in anticipation of success. Daily exports should include a manifest and checksums. Checksums detect changes relative to a retained copy; they alone do not prove when a forecast existed. Retain dated exports in an independently versioned destination for stronger auditability.

Back up after each session. Demonstrate a restore and replay before declaring the system operational.

## 5. Data contract and knowledge base

Use BTC, ETH and SOL; USD is the accounting currency. Choose one primary provider and exact instrument mapping per market. Store 1-minute data for fills and aggregate completed 15-minute/hourly/daily candles for signals. Cross-check a secondary provider without silently blending feeds. Exchange spot prices are proxy data, not evidence of a Jupiter execution price.

Starter data gates, explicitly engineering defaults to validate: latest price no older than 60 seconds, expected completed bar present within 60 seconds, no missing input bars within the strategy lookback. A provider disagreement above a preregistered tolerance blocks entries; determine the tolerance from instrument/venue differences before the pilot.

Keep both event time and time first available to the system. Only use data received before the decision. Never use the unfinished candle's eventual high/low or revised future macro values. Late data can repair research datasets but cannot turn a missed live decision into an on-time one.

Store UTC timestamps and render America/Toronto using daylight-saving-aware conversion. Define overnight as 00:00–06:00 Toronto; prior day as the preceding Toronto calendar day. At 05:43, label the overnight range “through forecast cutoff,” not a completed overnight range. Lock final overnight levels at 06:00.

Build a versioned research catalogue for each feature: definition, hypothesized mechanism, source or calculation, known limitations, data availability and evaluation results. Trend, breakouts and relative strength are hypotheses until tested here. A 200-day statistic requires sufficient daily history; otherwise report unavailable. Remove mandatory yearly-cycle narratives without evidence.

Macro information must link to the original publishing agency/calendar with scheduled time. Whale boards are optional annotations until a reproducible timestamped feed, address-selection rule and historical test exist. Wallet transfers and selected top-performing wallets are not automatically directional trading flow.

## 6. Register a small set of testable setups

Start with these two proposed baselines. The numerical settings are seed hypotheses, not known profitable parameters. Freeze them for the first evaluation; do not optimize them to the two missed moves in v2.

**A. Overnight breakout continuation.** After 06:00, a completed 15-minute bar closes above the fixed overnight high by at least 0.1 × ATR(14), and the preceding completed 15-minute close was at or below that level. Require the latest completed hourly close above its EMA(50). Enter at the next observable price after the decision is committed. Stop = overnight high minus 0.5 × ATR(14). Target = entry plus twice the entry-to-stop distance. Mirror for shorts with overnight low and hourly close below EMA(50).

**B. Failed overnight breakout.** A completed 15-minute bar trades above the overnight high by at least 0.1 × ATR(14) but closes below that high. Short at the next observable price; stop = signal bar high plus 0.1 × ATR(14); target = entry minus twice risk distance. Mirror for longs below the overnight low. Exclude a short when the latest hourly close is above EMA(50) and that EMA exceeds its value three completed hourly bars earlier; mirror for longs.

ATR uses Wilder smoothing on completed 15-minute candles, with documented warmup. EMA uses completed hourly candles with documented initialization/warmup. Missing warmup blocks that setup. A post-decision entry that makes stop/target ordering invalid cancels the signal. Define ties and floating-point tolerances in implementation tests.

Both start as intraday setups, expire at the next decision cycle if not filled, and close at noon. Allow one entry per setup/market/side/session. Rank simultaneous candidates by estimated net target-reward/stressed-stop-loss ratio, then stable setup ID and market name as tie-breakers. Log all candidates; only one can enter the portfolio. Reject contradictory simultaneous directions for the same asset.

Record SOL-minus-BTC and ETH-minus-BTC returns over the same preceding 1-hour and 24-hour windows as descriptive features. Test whether they improve results before using them as gates. No swing portfolio until continuous monitoring, financing and separate hold-time rules are validated.

## 7. Forecasts and probability scoring

Separate market prediction from the decision to trade. A directional forecast may be correct yet unprofitable after costs.

The morning forecast predicts each market's 06:00–12:00 return class. Proposed fixed pilot definition: UP if return > +0.5%, DOWN if < −0.5%, otherwise RANGE. Freeze this definition before collecting evaluation results. Record probabilities summing to 1, or mark probabilities unavailable when no calibrated model exists. Do not translate “confidence 4/5” into an invented probability.

Record the pre-06:00 forecast before its start price is known; the scoring job later attaches the actual 06:00 reference and noon reference from the fixed provider. Missing reference data yields unscored status with reason. The session forecast initially remains a separately evaluated output, not an additional undocumented trade filter.

Initial probability baseline: class frequencies from prior eligible sessions only, with sample count, date range and smoothing method. Compare to an expanding-history frequency baseline and a preregistered simple prior-session directional rule. Do not label a conditional statistic an edge just because its win rate exceeds 50%.

Score every forecast with multiclass Brier score = mean over forecasts of the sum across classes of (probability − outcome indicator)^2; lower is better. Also report class accuracy, coverage and reliability bins with sample sizes. Score target-before-stop trade forecasts separately, using a three-outcome definition when timeout is possible. Observations and probabilities must share the same horizon and outcome definition.

## 8. Paper fills and costs

A decision is committed before a simulated entry. Fill at the next observable executable/proxy price after configured latency, with recorded slippage. Never fill at a past candle close that was necessary to generate the signal.

Process only post-entry data, in timestamp order. If stop and target occur within the same available bar and finer data cannot establish order, assume stop first for official PnL and flag the trade ambiguous. If a bar spans the entry moment, use finer data or the next full bar conservatively; do not use its pre-entry extreme as an exit. Stops fill at the first available adverse price including modeled slippage; gaps may exceed any assumed buffer. Targets receive no optimistic price improvement. Missing intervals cause unresolved status until reconciliation; do not invent fills.

Separate signal price, mark price, oracle/reference price and modeled execution price. If no verified Jupiter-compatible cost/settlement adapter is available, label the experiment **generic perpetual proxy**, exclude it from venue-ready performance, and report modeled cost scenarios.

Capture opening and closing fees, price impact, required collateral conversions, transaction/priority costs, and financing over the entire hold. Identify quote versus realized versus modeled values per component. A live quote is still an estimate for a paper trade. Integrate changing borrow inputs over their actual intervals; do not apply the entry rate to the entire hold without flagging it as an approximation. Verify the fee basis against the pinned protocol implementation; do not guess whether it is notional, borrowed amount or another protocol quantity. Avoid counting price impact twice as both embedded fill loss and a separate fee.

Official Jupiter sources checked during this revision describe minimum new-position collateral of $10 and an early-alpha CLI. Its perps documentation requires an active key for most commands, including order previews. Therefore, quoting support must be verified separately without introducing keys into this paper service. Do not assume `/workspace/perps-fees/quote` exists or is correct.

## 9. Risk and accounting

Keep the original limits as pilot ceilings: $50 initial paper trading capital; maximum 2× leverage; one open position; three portfolio entries per Toronto day; planned loss at most 2% of trading equity per entry; 5% daily loss lockout. These ceilings are policy choices, not evidence of safety or profitability.

Choose the technical stop first, then size. Never tighten it solely to squeeze past minimum collateral. If venue minimums and costs exceed the budget, log RISK_BUDGET_TOO_SMALL and skip. Keep $10–$25 collateral only if compatible with verified venue rules, available funds and actual risk calculation.

Sizing approximation for a linear USD proxy:

`planned_loss = notional × (stop_distance_fraction + adverse_slippage_fraction) + opening_costs + stressed_closing_costs + stressed_hold_financing`

Use a venue settlement model instead when collateral/contract mechanics differ. Retain the old 2% adverse-price assumption as one labeled stress scenario, not a guaranteed bound. Example: $50 notional × (1% stop distance + 2% adverse movement) = $1.50 before fees, exceeding a $1 loss budget. This is illustrative arithmetic, not a quote.

At the start of the Toronto day, store trading equity. Daily loss includes realized and unrealized changes, accrued costs and estimated close costs, adjusted for internal reserve transfers so those do not appear as trading losses. At a 5% drop, model flattening at the next observable price, cancel entries and lock until the next day; gaps can produce a larger loss. A separate continuous risk worker is required while any position exists.

Maintain trading cash, margin/collateral, unrealized PnL, accrued costs and profit reserve separately. Mark collateral exposure using the venue model; do not count collateral twice. Total research equity includes trading equity plus reserve value. Keep any optional SOL spot holding in a separate benchmark book.

If preserving the 50% winner skim, transfer that amount internally to a USD reserve exactly once at each net-profitable close. It is neither an expense nor new profit. Display reserve savings separately from strategy return. Defer simulated ETH/BTC purchases to a separately specified allocation experiment; this avoids mixing trading quality with later coin-price movements.

Reconcile every report: ending total equity = starting total equity + trading/valuation PnL − costs + external deposits − external withdrawals. Internal transfers cancel. Net closed-trade PnL and total-equity return must both be shown.

## 10. What “learning” must mean

Logging accumulates evidence. Evaluation measures it. Learning changes a versioned rule/model based on that evidence and then tests the change on unseen outcomes. Reading yesterday's commentary is not model training.

Use chronological development, validation and untouched test windows. Prevent overlap between label horizons across boundaries, fit transformations using training data only, and retain an experiment registry including failed variants. Do not repeatedly tune against the same test window. Evaluate by session/day blocks because nearby crypto signals and BTC/ETH/SOL outcomes are correlated.

For each proposed change record: hypothesis, mechanism, exact parameter/code diff, prior version, training cutoff, all variants tried, costs, sample sizes, out-of-sample results, uncertainty and decision. Keep the incumbent frozen; run the candidate in a shadow book on future data. Promote only after a preregistered improvement criterion is met. Revert if specified forward degradation conditions trigger. No automatic daily rule rewriting.

Report net expectancy per trade and per session, drawdown, average gain/loss, profit factor with undefined cases handled, turnover, time exposed, cost drag and outcome uncertainty. Compare against cash/no trade and exposure-matched simple rules; also show same-period unlevered BTC/SOL buy-and-hold as context, explicitly noting different exposure. Bootstrap uncertainty by day/session when enough blocks exist; otherwise mark it unreliable.

Twenty closed trades are an operational review checkpoint only. Proposed first research review: at least 60 forward sessions and 100 closed trades, without forcing trades to reach the count. These are project milestones, not sufficient statistical proof. Any claim of edge must survive costs, alternative plausible fills, excluded ambiguous trades, different periods and comparison with baselines. Report how many strategies/variants were tried.

Live remains OFF. There is no automatic unlock counter. Any future live deployment requires a separate reviewed system and Kyle's explicit instruction.

## 11. Schedule and replacement job prompts

These schedules are specifications for the eventual host, not tasks activated by this revision. All use America/Toronto, seven days per week for the pilot; show weekday/weekend results separately.

| Job | Time | Purpose |
|---|---|---|
| Audit/health | 05:35 | Check persistence, provider health, scheduler, reconciliation |
| Morning forecast | 05:43 | Commit pre-session forecast and evidence |
| Decision cycles | 06:00 through 11:45, every 15 min | Evaluate only completed bars; 24 expected runs |
| Risk monitor | Every minute while positions exist | Exit processing, freshness, daily lockout |
| Session close | 12:00 | Close intraday book using first available post-noon price |
| Final report | 12:10 | Reconcile, score, publish evidence; provisional if data unresolved |
| Research review | Sunday 13:00 | Evaluate frozen experiments and propose next tests |

### Startup / evidence audit prompt

Read the v3 operating contract and pinned configuration. Run the actual-host audit in section 3. Provide paths, row counts, timestamps, actual record examples and reconciliation results. Separate verified history from missing/inaccessible records. Show the real commands and exit statuses. Do not initialize over existing files, backdate forecasts, or declare success from a file name. If deployment is incomplete, return NOT OPERATIONAL and the concrete missing dependencies. Do not claim any trade performance until replay succeeds.

### Morning forecast prompt

Verify startup health and last committed state. Fetch and persist valid inputs, freezing the information cutoff. Generate the three market forecasts using the registered model or baseline, with outcome definitions, probabilities/sample counts, partial overnight levels and evidence references. Score the prior eligible session only when its reference data are complete. If prerequisites fail, record a failed run and publish data-unavailable commentary without an official new forecast. Commit records, emit a receipt and queue only previously authorized handoffs. Report data freshness, prediction, evidence quality and prior-session score briefly.

### Fifteen-minute decision prompt

Acquire the unique run lock; reconcile pending exits before entries. Read only the pinned strategy and prior committed state. Evaluate completed-bar setups, log all signals and pass/fail gates, and rank eligible candidates deterministically. Open at most one paper position subject to risk, cost and data gates; otherwise record an explicit rejection reason. Persist the decision before future-price fill simulation. Advance pending forecasts/trades without inventing missing data. Emit actual IDs and a committed run receipt. Notify Kyle for opens, closes, risk lockouts, stale data or unresolved execution. Routine flat decisions remain logged even when chat is quiet. Log hindsight discoveries as research hypotheses, never as historical signals.

### Risk-monitor prompt

Process new post-entry observations in order using the registered fill model. Apply stops, targets, timeout and loss lockout. Record financing intervals and ambiguities. Stale/missing data suspends new entries and alerts Kyle; it cannot be treated as a known flat-price period. After restart, reconcile from the last processed event before proceeding. Emit one close event per trade, including on retry. Paper stops are simulator rules, not orders resting at a venue.

### Final report prompt

After noon exits and data reconciliation, score every due forecast and summarize every closed/open/unresolved trade, including losses and rejected signals. Show gross PnL, itemized costs, net PnL, trading equity, reserve and total equity. Show expected/successful/failed runs, missing records, ambiguity counts and actual evidence links. Include all-trade statistics before optional best/worst examples. Compare with registered baselines. State “no strategy change” unless a versioned experiment exists; report no learning claim without its artifacts. If reconciliation is incomplete, label the report PROVISIONAL and queue a later correction. Report handoffs as queued or acknowledged according to receipts; never claim both recipients have it merely because files were written.

### Weekly research prompt

Evaluate the frozen strategies and registered experiments, including failed variants. Explain whether outcomes support, weaken or leave each hypothesis unresolved. Show sample counts, net expectancy, costs, uncertainty, calibration and baseline comparisons. Propose at most one specific change per candidate experiment with its future evaluation window and pass/fail criteria. Do not modify the incumbent, reinterpret past entries, or promote based on hindsight winners.

## 12. What Kyle should see

The daily evidence view must show:

- **Operating status:** last successful run, next due run, gaps, stale feeds and reconciliation status.
- **Forecast record:** prediction timestamp, probabilities, horizon, source inputs and eventual score.
- **Trade register:** every signal, rejection, actual paper entry/exit, costs and net result.
- **Performance:** equity and drawdown, net expectancy, sample counts and baseline comparisons.
- **Research changes:** exact version diff, evidence, shadow results and promotion/rejection.
- **Downloads:** raw decisions, trades, scores and run receipts.

Use real values only. A mock dashboard must be prominently labeled DEMO and must never be mixed with research results.

## 13. Implementation acceptance gates

1. **Recover and audit:** actual original-host evidence inspected; gaps explicitly documented.
2. **Build records:** durable database, input collector, versioned schemas, scheduler receipts and backups.
3. **Validate simulator:** meaningful tests for duplicate retries, crashes, same-bar stop/target, gap stops, stale data, variable costs, noon close, reserve transfers and Toronto DST.
4. **Demonstrate proof:** one real data collection, one committed forward forecast, its later observed outcome, reproducible score, and replayed ledger. Synthetic tests are labeled and excluded from performance.
5. **Run paper pilot:** deterministic frozen rules; costs and exclusions visible; no claims of edge before evaluation.
6. **Add research/dashboard:** only after the records and accounting reconcile.

The immediate next action in Grok is the startup audit prompt. Request its evidence export, not another reassurance. If the paths or scripts cannot be accessed, the honest result is “unverified/inaccessible”; migrate or rebuild on a host with durable storage and an inspectable scheduler.

## Sources checked for venue-specific corrections

Accessed September 25, 2026. Recheck and pin versions at implementation; these sources do not establish strategy profitability.

- Jupiter official CLI: https://github.com/jup-ag/cli — early-alpha/version stability warning.
- Jupiter official perps CLI documentation: https://github.com/jup-ag/cli/blob/main/docs/perps.md — supported markets, minimum collateral, active-key requirements and preview semantics.
- Jupiter Position Account reference: https://developers.jup.ag/docs/perps/position-account — collateral custody distinctions and cumulative-interest snapshot mechanics.
- Jupiter Support Hub: https://support.jup.ag/ — fee categories; do not hard-code a support-summary rate as a complete execution model.

All strategy thresholds, architecture choices and research gates above are proposed design decisions. They are not backtest findings. No verified PnL, historical edge or learning result has been produced by this document revision.
