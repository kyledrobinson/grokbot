# Morning tags — EARLY READ (small sample, NO conclusions)

Net R after modeled/real fees. Any cell with n < 30 is INCONCLUSIVE. Tags are context labels only; nothing here changes any rule.

## Captain v3 skipped signals (resolved hypothetical outcomes): 89 resolved
(daily tags built from bars received on time ('live'): 51; event tags live: 84; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 89 | -0.25R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 13 | -0.05R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 16 | -0.39R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 60 | -0.25R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 60 | -0.25R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | london_reversed_asia = false (reversal day) | 29 | -0.25R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 59 | -0.12R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | partial | 9 | -0.43R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 21 | -0.53R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 13 | -0.38R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 14 | -0.42R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 62 | -0.18R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 31 | -0.26R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = false | 58 | -0.24R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

## Captain v3 official paper trades: 25 resolved
(daily tags built from bars received on time ('live'): 10; event tags live: 23; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 25 | -0.46R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & aligned with signal | 5 | -0.54R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 2 | -0.09R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 18 | -0.47R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 16 | -0.54R | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = false (reversal day) | 9 | -0.31R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 17 | -0.45R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | partial | 1 | +1.67R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 7 | -0.78R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 3 | -0.60R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 5 | -0.15R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 17 | -0.52R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = true | 7 | -0.93R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 18 | -0.28R | INCONCLUSIVE (n<30) |

