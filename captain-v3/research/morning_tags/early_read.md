# Morning tags — EARLY READ (small sample, NO conclusions)

Net R after modeled/real fees. Any cell with n < 30 is INCONCLUSIVE. Tags are context labels only; nothing here changes any rule.

## Captain v3 skipped signals (resolved hypothetical outcomes): 79 resolved
(daily tags built from bars received on time ('live'): 51; event tags live: 74; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 79 | -0.26R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 7 | -0.33R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 15 | -0.36R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 57 | -0.22R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 50 | -0.26R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | london_reversed_asia = false (reversal day) | 29 | -0.25R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 50 | -0.13R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | partial | 9 | -0.43R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 20 | -0.51R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 11 | -0.51R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 11 | -0.35R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 57 | -0.19R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 26 | -0.29R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 53 | -0.24R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

## Captain v3 official paper trades: 23 resolved
(daily tags built from bars received on time ('live'): 10; event tags live: 21; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 23 | -0.42R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & aligned with signal | 5 | -0.54R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 1 | +0.82R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 17 | -0.45R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 14 | -0.48R | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = false (reversal day) | 9 | -0.31R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 15 | -0.38R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | partial | 1 | +1.67R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 7 | -0.78R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 3 | -0.60R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 4 | +0.02R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 16 | -0.49R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = true | 5 | -0.93R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 18 | -0.28R | INCONCLUSIVE (n<30) |

