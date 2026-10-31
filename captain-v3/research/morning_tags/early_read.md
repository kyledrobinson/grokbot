# Morning tags — EARLY READ (small sample, NO conclusions)

Net R after modeled/real fees. Any cell with n < 30 is INCONCLUSIVE. Tags are context labels only; nothing here changes any rule.

## Captain v3 skipped signals (resolved hypothetical outcomes): 199 resolved
(daily tags built from bars received on time ('live'): 51; event tags live: 182; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 199 | -0.27R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 22 | -0.05R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 32 | -0.60R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | not clean | 145 | -0.23R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 111 | -0.20R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | london_reversed_asia = false (reversal day) | 88 | -0.34R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 101 | -0.14R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | partial | 53 | -0.28R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | diverge | 45 | -0.52R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 27 | -0.21R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 32 | -0.34R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset, fresh breaks only | diverge | 140 | -0.26R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 82 | -0.33R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = false | 117 | -0.22R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

## Captain v3 official paper trades: 40 resolved
(daily tags built from bars received on time ('live'): 10; event tags live: 37; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 40 | -0.45R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 9 | -0.27R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 3 | -0.40R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 28 | -0.51R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 19 | -0.53R | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = false (reversal day) | 21 | -0.38R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 23 | -0.40R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | partial | 5 | -0.05R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 12 | -0.72R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 6 | -0.36R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 7 | -0.37R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 27 | -0.49R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = true | 14 | -0.73R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 26 | -0.30R | INCONCLUSIVE (n<30) |

