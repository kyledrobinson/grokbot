# Morning tags — EARLY READ (small sample, NO conclusions)

Net R after modeled/real fees. Any cell with n < 30 is INCONCLUSIVE. Tags are context labels only; nothing here changes any rule.

## Captain v3 skipped signals (resolved hypothetical outcomes): 134 resolved
(daily tags built from bars received on time ('live'): 51; event tags live: 124; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 134 | -0.29R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 15 | -0.03R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 23 | -0.50R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 96 | -0.28R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 87 | -0.26R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | london_reversed_asia = false (reversal day) | 47 | -0.33R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 73 | -0.16R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | partial | 24 | -0.18R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 36 | -0.59R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 1 | -0.93R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 17 | -0.32R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 22 | -0.55R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 94 | -0.21R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 49 | -0.39R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = false | 84 | -0.22R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

## Captain v3 official paper trades: 29 resolved
(daily tags built from bars received on time ('live'): 10; event tags live: 27; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 29 | -0.45R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & aligned with signal | 6 | -0.57R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 2 | -0.09R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 21 | -0.46R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 17 | -0.55R | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = false (reversal day) | 12 | -0.32R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 18 | -0.46R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | partial | 2 | +0.50R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 9 | -0.65R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 3 | -0.60R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 6 | -0.24R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 20 | -0.50R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = true | 9 | -0.76R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 20 | -0.32R | INCONCLUSIVE (n<30) |

