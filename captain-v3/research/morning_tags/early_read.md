# Morning tags — EARLY READ (small sample, NO conclusions)

Net R after modeled/real fees. Any cell with n < 30 is INCONCLUSIVE. Tags are context labels only; nothing here changes any rule.

## Captain v3 skipped signals (resolved hypothetical outcomes): 182 resolved
(daily tags built from bars received on time ('live'): 51; event tags live: 166; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 182 | -0.23R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 19 | +0.09R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 27 | -0.55R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 136 | -0.21R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 111 | -0.20R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | london_reversed_asia = false (reversal day) | 71 | -0.26R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 99 | -0.14R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | partial | 39 | -0.10R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | diverge | 44 | -0.54R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 27 | -0.21R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 31 | -0.32R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset, fresh breaks only | diverge | 124 | -0.21R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 78 | -0.32R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = false | 104 | -0.16R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

## Captain v3 official paper trades: 38 resolved
(daily tags built from bars received on time ('live'): 10; event tags live: 35; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 38 | -0.42R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 9 | -0.27R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 2 | -0.09R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 27 | -0.50R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 19 | -0.53R | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = false (reversal day) | 19 | -0.32R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 23 | -0.40R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | partial | 4 | +0.18R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 11 | -0.69R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 6 | -0.36R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 7 | -0.37R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 25 | -0.45R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = true | 13 | -0.70R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 25 | -0.28R | INCONCLUSIVE (n<30) |

