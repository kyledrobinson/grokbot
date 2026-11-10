# Morning tags — EARLY READ (small sample, NO conclusions)

Net R after modeled/real fees. Any cell with n < 30 is INCONCLUSIVE. Tags are context labels only; nothing here changes any rule.

## Captain v3 skipped signals (resolved hypothetical outcomes): 251 resolved
(daily tags built from bars received on time ('live'): 51; event tags live: 224; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 251 | -0.32R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 27 | +0.09R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 37 | -0.65R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | not clean | 187 | -0.31R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 133 | -0.25R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | london_reversed_asia = false (reversal day) | 113 | -0.37R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | unlabelled (flat/missing) | 5 | -0.64R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 130 | -0.19R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | partial | 68 | -0.36R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | diverge | 53 | -0.58R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 30 | -0.13R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset, fresh breaks only | partial | 48 | -0.37R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset, fresh breaks only | diverge | 173 | -0.33R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 102 | -0.39R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = false | 149 | -0.26R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

## Captain v3 official paper trades: 53 resolved
(daily tags built from bars received on time ('live'): 10; event tags live: 47; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 53 | -0.47R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 12 | -0.25R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 4 | -0.49R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 37 | -0.54R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 24 | -0.55R | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = false (reversal day) | 28 | -0.43R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 1 | +0.28R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 29 | -0.36R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | partial | 11 | -0.44R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 13 | -0.74R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 7 | -0.45R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 12 | -0.57R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 34 | -0.44R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 19 | -0.65R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 34 | -0.37R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

