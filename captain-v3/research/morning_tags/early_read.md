# Morning tags — EARLY READ (small sample, NO conclusions)

Net R after modeled/real fees. Any cell with n < 30 is INCONCLUSIVE. Tags are context labels only; nothing here changes any rule.

## Captain v3 skipped signals (resolved hypothetical outcomes): 243 resolved
(daily tags built from bars received on time ('live'): 51; event tags live: 217; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 243 | -0.30R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 26 | +0.08R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 34 | -0.62R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | not clean | 183 | -0.30R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 133 | -0.25R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | london_reversed_asia = false (reversal day) | 105 | -0.35R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | unlabelled (flat/missing) | 5 | -0.64R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 123 | -0.16R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | partial | 68 | -0.36R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | diverge | 52 | -0.57R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 29 | -0.15R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 47 | -0.37R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset, fresh breaks only | diverge | 167 | -0.31R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 101 | -0.38R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = false | 142 | -0.24R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

## Captain v3 official paper trades: 51 resolved
(daily tags built from bars received on time ('live'): 10; event tags live: 46; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 51 | -0.47R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 11 | -0.20R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 4 | -0.49R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 36 | -0.55R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 24 | -0.55R | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = false (reversal day) | 26 | -0.43R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 1 | +0.28R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 27 | -0.36R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | partial | 11 | -0.44R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 13 | -0.74R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 7 | -0.45R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 11 | -0.55R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 33 | -0.45R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 19 | -0.65R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 32 | -0.36R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

