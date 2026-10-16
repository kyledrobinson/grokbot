# Morning tags — EARLY READ (small sample, NO conclusions)

Net R after modeled/real fees. Any cell with n < 30 is INCONCLUSIVE. Tags are context labels only; nothing here changes any rule.

## Captain v3 skipped signals (resolved hypothetical outcomes): 104 resolved
(daily tags built from bars received on time ('live'): 51; event tags live: 96; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 104 | -0.24R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 14 | +0.01R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 16 | -0.39R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 74 | -0.26R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 69 | -0.22R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | london_reversed_asia = false (reversal day) | 35 | -0.28R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 64 | -0.07R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | partial | 13 | -0.37R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 27 | -0.57R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 15 | -0.24R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 15 | -0.44R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 74 | -0.20R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 37 | -0.28R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = false | 67 | -0.22R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

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

