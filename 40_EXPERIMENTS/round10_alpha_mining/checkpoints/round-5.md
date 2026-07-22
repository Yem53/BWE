# Round10 Checkpoint 5 — FINAL (iter8 + SEALED-TEST REVEAL — 157 experiments)

**Time**: 20:59 UTC (loop deadline 12:50 passed ~8h ago — autonomous window closed; this is the
convergence/report capstone run after user resumed the session). Sealed test REVEALED here (once).

## iter8 — advanced exit types on h8-12 entry (DEV)
All 8 gate. Best dev calmar = `trail_t4_arm5_cap12` (cal 10.21, maxdd 20.9, +213%) vs single ref
(cal 7.53, +216%). BUT trailing's **older flips −17** (single older +8) → yellow flag (dev-fit).

## ★ SEALED-TEST REVEAL (last 21d, 04-25→05-16, NEVER used for selection) ★
| strategy | DEV | **TEST (sealed)** |
|---|---|---|
| h8-12 + single tp8/sl3 (PRIMARY) | +216% / 6/6 / cal7.5 | **−25.3% / 2/6 / cal−0.52 / wr24%** |
| h8-12 + trailing t4/arm5 | +213% / cal10.2 | **−30.0% / cal−0.78** |
| h8-12 + multi 5/8/11 | +140% / cal6.7 | **−28.3% / cal−0.66** |
| LIVE B_US_PM_PULLBACK | +50% / cal0.9 | **+72.3% / 5/6 / cal3.04** |
| LIVE D_ASIA_LATE_CONFIRM | +40% / cal0.65 | **+49.2% / cal1.18** |
| LIVE C_PULLBACK_STRICT | +47% | +5.7% |

**Primary candidate t-stat**: DEV t=2.51 p=0.0060 → **TEST t=−0.72 p=0.76** (no edge OOS).
Bonferroni α(m=157)=0.00032 → candidate fails correction EVEN on dev (0.006≫0.00032).

## VERDICT: the h8-12 "alpha" is a FALSE POSITIVE (overfit to Feb–Apr dev regime)
Despite every in-dev robustness check passing (27/28 param plateau, all-regime-positive WITHIN dev,
older +8, broad 40 syms / top_share 7%), it LOST money on the unseen 21d. The reversion edge in the
h8-12 block was regime-conditional and did not persist. **DO NOT DEPLOY.**

## The real signal: the sealed test VALIDATED the existing live strategies
B (+72%, cal3.0) and D (+49%) — mediocre on dev — were the out-of-sample winners. This round's
honest contribution: (1) the anti-overfit machinery caught a losing strategy before deployment;
(2) increased confidence in keeping B/D unchanged.

## Lesson (→ LEARNINGS)
In-sample robustness (plateau + multi-regime-within-window + older-period) is NECESSARY but NOT
SUFFICIENT. A single dev period can share a regime with "older" data and still break on the next
window. Only a truly sealed forward window decides. Next time: walk-forward with MULTIPLE rolling
OOS windows, not one dev + one 21d test.

## Disclosure: 157 exp · 83 gated on dev · 0 anomalies · 0 errors · 9 directions screened.
Directions DEAD/NO-GO: long, micro-window, confluence. NO standalone edge: OI, lifecycle.
Ensemble: uncorrelated w/ D (0.042) but moot now. experiments.jsonl = dev/older only; test in
test_reveal.json (kept separate to preserve sealed-discipline record).
