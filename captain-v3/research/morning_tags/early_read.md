# Morning tags — EARLY READ (small sample, NO conclusions)

Net R after modeled/real fees. Any cell with n < 30 is INCONCLUSIVE. Tags are context labels only; nothing here changes any rule.

## Captain v3 skipped signals (resolved hypothetical outcomes): 167 resolved
(daily tags built from bars received on time ('live'): 51; event tags live: 153; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 167 | -0.24R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 15 | -0.03R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 23 | -0.50R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 129 | -0.22R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 106 | -0.22R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | london_reversed_asia = false (reversal day) | 61 | -0.28R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 94 | -0.16R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | partial | 31 | -0.08R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | diverge | 42 | -0.55R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 27 | -0.21R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 27 | -0.36R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 113 | -0.22R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 74 | -0.31R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = false | 93 | -0.19R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

## Captain v3 official paper trades: 35 resolved
(daily tags built from bars received on time ('live'): 10; event tags live: 32; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 35 | -0.42R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 7 | -0.31R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 2 | -0.09R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 26 | -0.48R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 18 | -0.49R | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = false (reversal day) | 17 | -0.35R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 22 | -0.38R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | partial | 2 | +0.50R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 11 | -0.69R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 6 | -0.36R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 6 | -0.24R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 23 | -0.49R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = true | 13 | -0.70R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 22 | -0.26R | INCONCLUSIVE (n<30) |

