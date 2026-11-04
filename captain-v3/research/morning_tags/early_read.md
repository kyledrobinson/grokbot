# Morning tags — EARLY READ (small sample, NO conclusions)

Net R after modeled/real fees. Any cell with n < 30 is INCONCLUSIVE. Tags are context labels only; nothing here changes any rule.

## Captain v3 skipped signals (resolved hypothetical outcomes): 222 resolved
(daily tags built from bars received on time ('live'): 51; event tags live: 201; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 222 | -0.29R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 25 | +0.05R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 34 | -0.62R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | not clean | 163 | -0.27R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 128 | -0.26R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | london_reversed_asia = false (reversal day) | 94 | -0.34R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 113 | -0.15R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | partial | 61 | -0.35R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | diverge | 48 | -0.54R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 27 | -0.21R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 38 | -0.39R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset, fresh breaks only | diverge | 157 | -0.28R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 92 | -0.38R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = false | 130 | -0.22R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

## Captain v3 official paper trades: 45 resolved
(daily tags built from bars received on time ('live'): 10; event tags live: 41; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 45 | -0.46R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 11 | -0.20R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 3 | -0.40R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 31 | -0.55R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 22 | -0.57R | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = false (reversal day) | 23 | -0.34R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 26 | -0.39R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | partial | 7 | -0.26R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 12 | -0.72R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 7 | -0.45R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 9 | -0.46R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 29 | -0.45R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = true | 16 | -0.76R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 29 | -0.29R | INCONCLUSIVE (n<30) |

