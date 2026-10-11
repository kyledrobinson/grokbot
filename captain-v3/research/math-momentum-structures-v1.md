# Math-inspired uphill momentum structures — v1.1

Original date: 2026-10-07  
Reevaluated: 2026-10-08  
Scope: paper-only research for BTC, ETH, and SOL; later reusable for stocks, futures, prediction markets, and sports betting.  
Status: design and preregistration proposal. Nothing in this document changes the frozen Captain v3.1.1 strategy.

## Decision summary

The useful lesson from the OpenAI math collection is not that markets can be made deterministic. The useful lesson is to separate four problems that the current bot partly mixes together:

1. Is the environment moving persistently in one direction?
2. Is the evidence strong enough to act rather than abstain?
3. Which joint BTC/ETH/SOL position has the best net expected value after dependence and costs?
4. How much capital can be assigned without unacceptable drawdown or ruin risk?

Captain v3 already supplies the right experimental foundation: timestamped market data, frozen configurations, deterministic fills, costs, calibration, Brier scores, hypothetical skipped trades, drawdown, and paper-only risk controls. The next version should add a research layer beside v3, not silently alter its entry rules.

The current evidence is not sufficient for promotion. As of the 2026-10-07 final report, there are 7 closed official trades with mean net R of -0.508, and 9 scored forecasts per model. All setup and condition cells are marked unreliable. The proposed structures therefore begin as shadow forecasts and hypothetical actions.

The 2026-10-08 reevaluation re-read the shared conversation and searched the official 372-family catalogue. The shared conversation contains no later response beyond the original proposal. Five additional catalogue families are relevant as research analogies: 093, 110, 115, 131, and 140. Families 139, 145, and 154 are interesting but lower priority because their assumptions are difficult to justify for short-horizon markets.

## What transfers from the math collection

The referenced result families are useful as architectural analogies:

- Family 104, stochastic mean-payoff games: choose an action for a probabilistic state to maximize long-run reward.
- Family 220, random-environment ballisticity: distinguish persistent directional travel from diffusion. Its theorem assumptions do not transfer to markets; only the measurement idea does.
- Families 221 and 234, spin-glass/free-energy formulations: score interacting joint positions rather than three independent asset calls.
- Family 222, perceptron thresholds: create an explicit abstention region when the available evidence is weak or contradictory.
- Family 111, online selection/prophet inequalities: ration scarce capital among opportunities rather than taking every positive-looking signal.
- Family 110, online randomized k-server: reason about repeated state changes when moving between positions has a cost.
- Family 115, exact sampling of contingency tables with fixed margins: construct conditional null tests for apparent prediction or betting skill.
- Family 131, Markov-chain mixing: motivates checking how dependent observations reduce effective sample size before trusting a backtest.
- Family 140, memory-sample lower bounds for Gaussian regression: reinforces that feature dimension, retained state, and sample size must be budgeted together.
- Family 093, logarithmic Sobolev concentration for subgaussian log-concave measures: motivates uncertainty bounds only when distributional diagnostics support them.

These results do not prove any trading edge. Every derived feature and decision rule below must earn its place through chronological out-of-sample testing.

## Structure 1: Uphill Momentum Vector

For asset \(i\) at time \(t\), build a feature vector using only data received by the cutoff:

\[
x_{i,t} = [r_{15m}, r_{1h}, r_{4h}, \Delta EMA_{50}, d_{VWAP}, volRatio,
ATRrank, relBTC_{1h}, relBTC_{24h}]
\]

Normalize every component by a rolling median and MAD fitted on the training window. Orient each feature so positive values represent bullish evidence. Define:

\[
U_{i,t} = w^T z_{i,t}
\]

where weights are fitted only on past data and constrained with ridge regularization. A simpler preregistered baseline uses equal weights after winsorization.

Price being up is insufficient. Uphill momentum requires the score itself to be rising:

\[
SlopeU_{i,t} = U_{i,t} - U_{i,t-k}
\]

Candidate long: \(U > \theta_U\), \(SlopeU > \theta_S\), and the 1h trend is not down. Candidate short uses the symmetric negative conditions. Otherwise abstain.

This structure can be computed now from the stored price, EMA, VWAP, volume, ATR, and relative-strength data. Order flow, open interest, funding, liquidations, and basis should remain absent until the repository contains reproducible timestamped feeds for them.

## Structure 2: Ballistic Persistence Score

Measure whether direction survives across horizons rather than relying on a single bar. For signed, volatility-scaled returns:

\[
q_h = \tanh\left(\frac{r_h}{\sigma_h}\right), \quad h \in \{15m,30m,1h,2h,4h\}
\]

Let \(a_h\) be whether the return, EMA slope, and VWAP displacement agree in direction. Define:

\[
B_{i,t} = \frac{\sum_h \omega_h q_h a_h}{\sum_h \omega_h}
\]

and a path-efficiency term:

\[
E_{i,t}(H) = \frac{|P_t-P_{t-H}|}{\sum_{j=t-H+1}^{t}|P_j-P_{j-1}|}
\]

The final persistence score is:

\[
BP_{i,t} = B_{i,t}\sqrt{E_{i,t}}
\]

It lies approximately in [-1, 1]. High magnitude means directional and efficient; values near zero indicate chop. Initial thresholds must be quantiles learned inside each training fold, not hand-tuned on the full history.

Use the score as a context variable first. Do not make it an entry gate until each sign/quantile bucket has at least 100 resolved shadow observations across at least 30 independent session dates.

## Structure 3: Evidence Threshold and Abstention

Each model emits a calibrated probability distribution for a fixed outcome definition. For the existing 06:00–12:00 session:

\[
p = [P(UP), P(RANGE), P(DOWN)]
\]

Define confidence margin and disagreement:

\[
M = p_{(1)} - p_{(2)}
\]

\[
D = \operatorname{Var}(p^{price}, p^{regime}, p^{relative}, p^{baseline})
\]

Action is allowed only when all of these hold:

- the chosen action has positive net expected value after fees, impact, slippage, and financing;
- calibrated probability exceeds its rolling lower confidence bound;
- margin \(M\) is above a training-fold threshold;
- disagreement \(D\) is below a training-fold threshold;
- data-quality and Captain risk gates pass.

This is the practical version of a perceptron-style feasibility boundary. It makes WAIT a first-class output and prevents a forced prediction from becoming a forced bet.

## Structure 4: Net Expected Value Surface

For each action \(a \in \{long, short, wait\}\), estimate outcome probabilities over explicit return bins rather than only green/red:

\[
EV(a|s) = \sum_k P(R_k|s,a)\,PnL(R_k,a) - C(a,s)
\]

\(C\) includes the same costs and stress multipliers used by Captain v3. WAIT has EV 0. A trade qualifies only if its conservative value is positive:

\[
LCB(EV) = \widehat{EV} - z\,SE(\widehat{EV}) > 0
\]

For prediction markets and sports bets with decimal odds \(o\), the analogous unit-stake value is:

\[
EV = p(o-1) - (1-p)
\]

Use no-vig probabilities when comparing against a sportsbook. Costs include commission, exchange spread, expected slippage, and limits. For Polymarket-style binary contracts bought at price \(m\), the simple hold-to-resolution value is \(p-m\) before costs.

## Structure 5: Joint BTC/ETH/SOL State Optimizer

Enumerate the 27 joint states \(s_i \in \{-1,0,+1\}\) for BTC, ETH, and SOL. Score each state:

\[
J(s)=\mu^Ts-\lambda s^T\Sigma s-\gamma Turnover(s)-Costs(s)-\rho TailLoss(s)
\]

where \(\mu\) is the vector of conservative net expected returns and \(\Sigma\) is a shrinkage covariance matrix fitted on the training window. Choose the state with the highest positive score, subject to the current one-position limit during the first experiment.

This turns the spin-glass analogy into a transparent finite search. With only three assets, enumeration is exact and easier to audit than a complex optimizer. The state score must use lagged covariance estimates and stress correlation toward 1 during high volatility.

## Structure 6: Opportunity Queue

Rank every currently eligible opportunity by:

\[
Q = \frac{LCB(EV)}{ExpectedShortfall_{95}+Costs} \times CalibrationQuality \times DataQuality
\]

Allocate the one available position to the highest positive \(Q\). Keep a shadow record of rejected alternatives and their subsequent outcomes. This applies equally to crypto, stocks, futures, sports bets, and prediction markets, but probabilities and payoff functions must be calibrated separately for each domain.

## Structure 7: Survival-weighted sizing

Kelly sizing is allowed only after calibrated probabilities and positive out-of-sample EV exist. For a binary payoff with net odds \(b\):

\[
f^* = \frac{bp-(1-p)}{b}
\]

Use a conservative probability \(p_{LCB}\), then cap sizing:

\[
f = \min(0.25 f^*(p_{LCB}), f_{risk}, f_{drawdown})
\]

Before the promotion gates are met, retain Captain's existing fixed planned-loss sizing. A Kelly display may be calculated in shadow mode but must not control position size.

## Structure 8: Switching-Cost and Hysteresis Controller

Family 110 concerns online movement between states when movement itself is costly. For GrokBot, a state is the current portfolio position and movement cost is spread, fees, impact, financing reset, and lost queue position.

Let the best new action at time \(t\) be \(a^*_t\), and the existing position be \(a_{t-1}\). Switch only when:

\[
LCB(EV(a^*_t))-LCB(EV(a_{t-1})) > C_{switch}+H_t
\]

where \(H_t\) is a hysteresis buffer that increases with volatility, model disagreement, and recent turnover. Exiting to WAIT uses the same comparison but may have a smaller safety buffer when the existing position's conservative EV is negative.

This module is more directly useful than trying to implement the k-server algorithm itself. Its purpose is to prevent a noisy score from generating fee-heavy long/short oscillation.

## Structure 9: Exact Conditional Skill Test

Family 115 suggests a clean way to test whether apparent success exceeds chance while holding nuisance totals fixed. Build a contingency table such as:

```text
                 outcome up   range   down
predicted up
predicted range
predicted down
```

Condition on the row totals and column totals, sample tables from the fixed-margin null distribution, and compare the observed score with the null distribution. Candidate statistics include accuracy, net EV, Brier improvement, or directional hit surplus.

For sports betting, hold fixed the number of bets by sport, odds bucket, and side. For trading, hold fixed the number of actions and realized outcome counts within a session or volatility block. Report:

\[
p_{null}=\frac{1+\#\{T^*\ge T_{observed}\}}{1+N_{samples}}
\]

This is a research-validity check, not an entry signal. It helps distinguish genuine information from a favorable class mix.

## Structure 10: Dependence and Effective Sample Size Gate

Families 131, 145, and 154 concern mixing and long-run averaging under specific mathematical assumptions. Those theorems do not certify market data. Their practical lesson is that adjacent 15-minute predictions are not independent observations.

Estimate the autocorrelation of forecast errors and net returns inside each training fold. Use a conservative effective sample size:

\[
n_{eff}=\frac{n}{1+2\sum_{k=1}^{K}\rho_k}
\]

with a preregistered truncation rule for \(K\). Bootstrap complete Toronto session dates or multi-session blocks rather than individual trades. Promotion thresholds apply to both raw sample count and \(n_{eff}\). If \(n_{eff}\) is unstable across reasonable block lengths, mark the result inconclusive.

Family 131's polynomial mixing result applies to a particular graph-switch chain, not to prices. It must not be cited as evidence that market observations mix quickly.

## Structure 11: Feature-Dimension Budget

Family 140 is a lower-bound result in a noiseless Gaussian setting, so its formula does not transfer directly. The design lesson is still valuable: adding features without adding independent observations can make precise recovery impossible.

For every experiment, log:

- raw feature count \(d\);
- effective feature count after collinearity pruning;
- training observations and \(n_{eff}\);
- ratio \(n_{eff}/d\);
- number of tried variants and thresholds.

The v1 baseline is limited to the existing nine-feature vector. Any new feature must replace an existing feature or wait for a new version unless it passes a preregistered ablation test. Do not add order flow, funding, open interest, news, or whale variables merely because they are available later.

## Structure 12: Distribution-Free Prediction Set

This process is not a direct consequence of one OpenAI family, but it is a stronger practical uncertainty layer than assuming normal returns. Use rolling conformal calibration on past, time-ordered residuals to produce a return interval or a set of plausible classes:

\[
\Gamma_t(\alpha)=\{y: score(x_t,y)\le q_{1-\alpha,t}\}
\]

Example outputs are `{UP}`, `{UP,RANGE}`, or `{UP,RANGE,DOWN}`. Trade only when the set is a singleton and the corresponding action has positive conservative EV. Use weighted or block conformal calibration so recent regimes receive more relevance while preserving a fully specified historical-only cutoff.

Coverage should be measured overall and by asset, volatility state, and month. If observed coverage falls below the target beyond its binomial confidence interval, disable this gate's action permission and return WAIT until recalibrated.

## Interesting but deferred processes

- Family 093 concentration bounds: crypto returns are commonly heavy-tailed and dependent, so subgaussian/log-concave bounds are allowed only after explicit diagnostics and sensitivity comparisons. Empirical or conformal bounds remain the default.
- Family 139 log-concave sampling: could support a future scenario generator for a well-conditioned convex posterior, but no such posterior exists in GrokBot today.
- Families 145 and 154 ergodic averages: useful as a warning about dependence, but they do not justify treating time averages as stable without market-specific tests.
- Family 277 threshold repetition: do not count correlated agents or indicators as independent confirmations. The theorem concerns a different setting; its useful reminder is handled by the model-disagreement and effective-sample-size gates.

## One common output contract

Each 15-minute decision should eventually emit one auditable record per asset plus a portfolio choice:

```json
{
  "market": "BTC",
  "cutoff_ts": "...",
  "horizon": "15m",
  "p_up": 0.00,
  "p_flat": 0.00,
  "p_down": 0.00,
  "uphill_score": 0.00,
  "uphill_slope": 0.00,
  "ballistic_persistence": 0.00,
  "conformal_set": ["UP", "RANGE", "DOWN"],
  "model_disagreement": 0.00,
  "effective_sample_size": 0.00,
  "ev_long_net": 0.00,
  "ev_short_net": 0.00,
  "ev_wait": 0.00,
  "ev_lcb": 0.00,
  "switch_cost_usd": 0.00,
  "hysteresis_buffer": 0.00,
  "action": "WAIT",
  "reason": "EVIDENCE_BELOW_THRESHOLD",
  "config_version": "math-momentum-v1.0.0",
  "features_hash": "..."
}
```

The dashboard should show probability, expected return distribution, expected range, persistence, disagreement, net EV by action, chosen position, risk budget, and invalidation. Avoid a single green/red confidence bar because it hides range risk, costs, calibration, and abstention.

## Research implementation boundary

Add the experiment beside the frozen engine:

```text
captain-v3/
  research/
    math_momentum/
      features.py
      persistence.py
      probability.py
      joint_state.py
      opportunity.py
      switching.py
      uncertainty.py
      null_test.py
      evaluation.py
  config/
    math-momentum-v1.0.0.json
```

Write results to new experiment tables or separate research artifacts. Do not reuse official trade rows. Every record needs event time, received time, cutoff, model/config version, training cutoff, features hash, action probabilities, net EV, abstention reason, and resolved outcome.

## Test plan and promotion gates

Use expanding or rolling walk-forward folds. Fit normalization, weights, quantiles, calibration, and covariance only on data before the test fold. Include an embargo of at least the forecast horizon between train and test samples. Compare against Captain's existing frequency model, always-WAIT, simple time-series momentum, and current setups A/B.

Primary metrics:

- log loss and multiclass Brier score;
- calibration error and reliability curves;
- net expectancy in R after all costs;
- maximum drawdown and expected shortfall;
- coverage: fraction of observations on which the model acts;
- turnover and cost share of gross profit;
- probability of backtest overfit across tested variants.

Minimum gates before a feature can affect paper entries:

- at least 250 resolved chronological shadow forecasts and 60 independent session dates per asset;
- positive net EV lower confidence bound overall and no catastrophic asset-specific cell;
- improvement over preregistered baselines in both Brier/log loss and net expectancy;
- stable results under 1.5x and 2x cost stress;
- no single month or asset supplies more than half of total profit;
- thresholds and model version frozen before the final holdout begins.

Minimum gates before any sizing change:

- all paper-entry gates pass;
- at least 100 closed paper trades under the frozen action policy;
- calibration remains acceptable in the probability region used for betting;
- drawdown and expected shortfall stay within preregistered limits.

## Recommended build order

1. Produce shadow-only uphill and persistence scores from existing stored data.
2. Add fixed-horizon probability forecasts and explicit WAIT thresholds.
3. Evaluate net EV with the existing cost engine.
4. Add exact enumeration of the 27 BTC/ETH/SOL states.
5. Add the opportunity queue across those assets.
6. Add switching-cost hysteresis, conformal prediction sets, dependence diagnostics, and the conditional skill test.
7. Only after crypto passes its gates, adapt the same interfaces to stocks/futures and then to sports/prediction markets with domain-specific data, odds, and settlement rules.

The first experiment should remain deliberately small: BTC, ETH, SOL; 15-minute decisions; fixed 15-minute and session-close horizons; price/volume/volatility/VWAP/relative-strength inputs already available in the repository. This is enough to test whether the architecture adds signal without importing unverifiable feeds or multiplying degrees of freedom.

## Basic GrokBot operator prompts

These prompts instruct GrokBot to use the proposed structure without giving it permission to trade or modify the frozen Captain strategy. Replace bracketed values when needed.

### 1. Start-of-session research prompt

```text
Run the math-momentum research analysis for BTC, ETH, and SOL for the [DATE] Toronto session. Use only information with received timestamps at or before the cutoff. Keep Captain v3.1.1 unchanged and paper-only.

For each asset report: UP/RANGE/DOWN probabilities for the 15-minute and session-close horizons; Uphill Momentum score and slope; Ballistic Persistence score; conformal prediction set; model disagreement; net EV and lower confidence bound for LONG, SHORT, and WAIT; data-quality failures; and the precise reason for the action.

Then evaluate all 27 BTC/ETH/SOL joint states, apply costs, correlation stress, the one-position limit, and the switching-cost rule. Choose at most one paper action. Return WAIT unless every evidence, EV, calibration, data-quality, and risk gate passes. Save the shadow forecast and config/features hashes even when the result is WAIT.
```

### 2. Fifteen-minute decision prompt

```text
Evaluate the newly completed 15-minute block ending [CUTOFF, AMERICA/TORONTO]. Do not use later data and do not rerun a missed block retroactively.

Update the BTC/ETH/SOL uphill, persistence, probability, conformal-set, disagreement, and net-EV fields. Compare the best eligible action with the current paper position after full switching costs and hysteresis. Choose LONG, SHORT, HOLD, EXIT, or WAIT. Explain the decision in one sentence using the failed or passed gates. Store all three asset forecasts and rejected alternatives.
```

### 3. Opportunity-ranking prompt

```text
Rank the current BTC, ETH, and SOL paper opportunities by conservative opportunity score: EV lower confidence bound divided by expected shortfall plus costs, multiplied by calibration quality and data quality.

Show the raw score components, effective sample size, conformal set, current-position switching cost, and correlation stress. Allocate no capital when the best conservative score is zero or negative. Do not infer missing order-flow, funding, open-interest, liquidation, news, or whale data.
```

### 4. End-of-session review prompt

```text
Resolve today's stored shadow forecasts without changing historical records. Report Brier score, log loss, conformal coverage, net hypothetical R after costs, action coverage, turnover, switching costs, MAE/MFE, and calibration by asset and volatility state.

Run the fixed-margin conditional skill test and dependence-aware block bootstrap only if their preregistered minimum sample requirements are met. Report raw n and effective n separately. Mark every underpowered result INCONCLUSIVE. Do not promote, tune, or replace a strategy from one day's results.
```

### 5. Weekly research prompt

```text
Run the frozen weekly walk-forward evaluation for math-momentum version [VERSION]. Train and calibrate only on observations before each test fold, preserve the embargo, and include all costs.

Compare against always-WAIT, the official frequency forecast, simple time-series momentum, and Captain setups A/B. Report performance after 1x, 1.5x, and 2x costs; Brier/log loss; conformal coverage; net expectancy in R; drawdown; expected shortfall; turnover; effective sample size; fixed-margin null p-value; results by asset/month/regime; and the number of variants tried.

State PASS, FAIL, or INCONCLUSIVE for each preregistered promotion gate. Never recommend promotion when any required gate is inconclusive.
```

### Short everyday prompt

```text
Run the latest paper-only BTC/ETH/SOL math-momentum block using timestamp-safe data. Score uphill momentum, persistence, calibrated probabilities, conformal uncertainty, net EV, switching cost, joint-position risk, and opportunity rank. Choose at most one action and default to WAIT when a gate fails. Save the complete shadow record and explain the decisive gate.
```
