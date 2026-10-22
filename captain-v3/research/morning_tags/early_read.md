# Morning tags — EARLY READ (small sample, NO conclusions)

Net R after modeled/real fees. Any cell with n < 30 is INCONCLUSIVE. Tags are context labels only; nothing here changes any rule.

## Captain v3 skipped signals (resolved hypothetical outcomes): 127 resolved
(daily tags built from bars received on time ('live'): 51; event tags live: 118; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 127 | -0.26R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 15 | -0.03R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 23 | -0.50R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 89 | -0.23R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 81 | -0.21R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | london_reversed_asia = false (reversal day) | 46 | -0.34R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 70 | -0.13R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | partial | 23 | -0.18R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 34 | -0.58R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 15 | -0.24R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 22 | -0.55R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 90 | -0.19R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 46 | -0.35R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = false | 81 | -0.20R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

## Captain v3 official paper trades: 28 resolved
(daily tags built from bars received on time ('live'): 10; event tags live: 26; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 28 | -0.45R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & aligned with signal | 5 | -0.54R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 2 | -0.09R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 21 | -0.46R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 17 | -0.55R | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = false (reversal day) | 11 | -0.29R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 18 | -0.46R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | partial | 1 | +1.67R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 9 | -0.65R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 3 | -0.60R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 6 | -0.24R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 19 | -0.49R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = true | 9 | -0.76R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 19 | -0.30R | INCONCLUSIVE (n<30) |

