# Morning tags — EARLY READ (small sample, NO conclusions)

Net R after modeled/real fees. Any cell with n < 30 is INCONCLUSIVE. Tags are context labels only; nothing here changes any rule.

## Captain v3 skipped signals (resolved hypothetical outcomes): 215 resolved
(daily tags built from bars received on time ('live'): 51; event tags live: 196; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 215 | -0.30R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 23 | -0.07R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 32 | -0.60R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | not clean | 160 | -0.28R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 124 | -0.26R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | london_reversed_asia = false (reversal day) | 91 | -0.35R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 106 | -0.16R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | partial | 61 | -0.35R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | diverge | 48 | -0.54R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 27 | -0.21R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 36 | -0.36R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset, fresh breaks only | diverge | 152 | -0.30R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 90 | -0.37R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = false | 125 | -0.25R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

## Captain v3 official paper trades: 43 resolved
(daily tags built from bars received on time ('live'): 10; event tags live: 40; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 43 | -0.48R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 9 | -0.27R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 3 | -0.40R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 31 | -0.55R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 21 | -0.55R | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = false (reversal day) | 22 | -0.41R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 24 | -0.43R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | partial | 7 | -0.26R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 12 | -0.72R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 6 | -0.36R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 9 | -0.46R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 28 | -0.51R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = true | 16 | -0.76R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 27 | -0.32R | INCONCLUSIVE (n<30) |

