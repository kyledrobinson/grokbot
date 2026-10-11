# Morning tags — EARLY READ (small sample, NO conclusions)

Net R after modeled/real fees. Any cell with n < 30 is INCONCLUSIVE. Tags are context labels only; nothing here changes any rule.

## Captain v3 skipped signals (resolved hypothetical outcomes): 60 resolved
(daily tags built from bars received on time ('live'): 45; event tags live: 60; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 60 | -0.36R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 7 | -0.33R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 13 | -0.48R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 40 | -0.32R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 34 | -0.37R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | london_reversed_asia = false (reversal day) | 26 | -0.34R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 31 | -0.24R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | partial | 9 | -0.43R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 20 | -0.51R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 7 | -0.59R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 8 | -0.34R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 45 | -0.33R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 19 | -0.32R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 41 | -0.38R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

## Captain v3 official paper trades: 15 resolved
(daily tags built from bars received on time ('live'): 8; event tags live: 14; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 15 | -0.33R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & aligned with signal | 4 | -0.39R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 1 | +0.82R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 10 | -0.43R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 8 | -0.40R | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = false (reversal day) | 7 | -0.26R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 8 | -0.29R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | partial | 1 | +1.67R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 6 | -0.73R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 1 | +0.35R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 2 | +0.53R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 12 | -0.53R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = true | 2 | -0.72R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 13 | -0.27R | INCONCLUSIVE (n<30) |

