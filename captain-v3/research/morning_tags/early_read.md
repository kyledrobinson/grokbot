# Morning tags — EARLY READ (small sample, NO conclusions)

Net R after modeled/real fees. Any cell with n < 30 is INCONCLUSIVE. Tags are context labels only; nothing here changes any rule.

## Captain v3 skipped signals (resolved hypothetical outcomes): 69 resolved
(daily tags built from bars received on time ('live'): 45; event tags live: 69; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 69 | -0.30R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | clean & aligned with signal | 7 | -0.33R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 13 | -0.48R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 49 | -0.25R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 43 | -0.28R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| session profile | london_reversed_asia = false (reversal day) | 26 | -0.34R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 40 | -0.17R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| cross-asset (+/-15m) | partial | 9 | -0.43R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 20 | -0.51R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 9 | -0.41R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 11 | -0.35R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 49 | -0.27R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |
| strength switch | strength_switch = true | 19 | -0.32R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 50 | -0.29R | EARLY (n>=30 but ~2 weeks, one regime; no conclusion) |

## Captain v3 official paper trades: 19 resolved
(daily tags built from bars received on time ('live'): 8; event tags live: 18; the rest are reconstructed from backfilled bars)

| Group | Cell | n | Mean net R | Verdict |
|---|---|---:|---:|---|
| all | all resolved | 19 | -0.42R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & aligned with signal | 4 | -0.39R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | clean & opposed to signal | 1 | +0.82R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | not clean | 14 | -0.51R | INCONCLUSIVE (n<30) |
| 6AM 4h candle | no tag | 0 |  | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = true (continuation day) | 11 | -0.55R | INCONCLUSIVE (n<30) |
| session profile | london_reversed_asia = false (reversal day) | 8 | -0.23R | INCONCLUSIVE (n<30) |
| session profile | unlabelled (flat/missing) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | all_confirm | 11 | -0.37R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | partial | 1 | +1.67R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | diverge | 7 | -0.78R | INCONCLUSIVE (n<30) |
| cross-asset (+/-15m) | not labelled (missing/pending) | 0 |  | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | all_confirm | 1 | +0.35R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | partial | 4 | +0.02R | INCONCLUSIVE (n<30) |
| cross-asset, fresh breaks only | diverge | 14 | -0.60R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = true | 3 | -0.86R | INCONCLUSIVE (n<30) |
| strength switch | strength_switch = false | 16 | -0.33R | INCONCLUSIVE (n<30) |

