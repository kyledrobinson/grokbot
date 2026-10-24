# Morning tags — EARLY READ (small sample, NO conclusions)

Net R after modeled/real fees. Any cell with n < 30 is INCONCLUSIVE. Tags are context labels only; nothing here changes any rule.

## Captain v3 skipped signals (resolved hypothetical outcomes): 145 resolved
(daily tags built from bars received on time ('live'): 51; event tags live: 135; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 145 | -0.28R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 15 | -0.03R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 23 | -0.50R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 107 | -0.27R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 96 | -0.27R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | london_reversed_asia = false (reversal day) | 49 | -0.30R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 81 | -0.15R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | partial | 26 | -0.21R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 38 | -0.60R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 19 | -0.22R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 22 | -0.55R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 104 | -0.23R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 58 | -0.39R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = false | 87 | -0.20R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

## Captain v3 official paper trades: 31 resolved
(daily tags built from bars received on time ('live'): 10; event tags live: 29; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 31 | -0.37R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 7 | -0.31R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 2 | -0.09R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 22 | -0.42R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 18 | -0.49R | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = false (reversal day) | 13 | -0.20R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 20 | -0.33R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | partial | 2 | +0.50R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 9 | -0.65R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 4 | -0.13R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 6 | -0.24R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 21 | -0.45R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = true | 10 | -0.64R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 21 | -0.24R | INCONCLUSIVE (n<30) |

