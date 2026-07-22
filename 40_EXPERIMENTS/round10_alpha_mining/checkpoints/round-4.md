# Round10 Checkpoint 4 (iteration 7, lifecycle — 149 experiments total)

**Time**: 06:41 UTC (deadline 12:50). 149/200. Distinct hypothesis space ~exhausted.

## iter7 — 妖币 lifecycle / repeated pump-dump: NO incremental alpha (confirms simpler is better)
Gated the validated h8-12 entry on `prior_pump_count ≥ K in trailing N days` (pump = ≥5% on
1h/180s alert; no look-ahead). Pump-history corpus: 189 symbols, 11,204 pumps.

| variant | n | dev_sum | calmar | vs plain |
|---|---|---|---|---|
| **h8-12 plain (ref)** | **54** | **+216.2** | **7.53** | — |
| pump≥1_in14d | 41 | +170.3 | 7.63 | calmar ~flat, fewer trades/syms, +conc |
| pump≥1_in7d | 41 | +153.4 | 4.17 | worse |
| pump≥2/3 (7d/14d) | 24-35 | +86–146 | 2.6–3.9 | worse |

**Verdict**: the lifecycle gate only *removes* trades without raising per-trade quality →
h8-12 ENTRIES ALREADY SELECT REPEAT-PUMPER 妖币 implicitly (pumping in h8-12 at ret60≥3.5 IS the
repeat-pump signature). Explicit gate is redundant + concentrating. **Plain h8-12 stays superior.**

## Direction scoreboard (9 screened → 1 alpha)
DEAD: long · micro-window(3s/60s/180s) · confluence.
NO STANDALONE EDGE (re-confirm h8-12 only): OI-driven · lifecycle.
KEY MECHANISMS: time-of-day **h8-12** · **multi-day wide exit** (tight exit flips winners negative).
ROBUST: h8-12 param plateau (27/28) · multi-regime + · uncorrelated w/ D (0.042).
NOT TESTED (by design): funding-rate (not in npz; 30d parquet overlaps sealed edge → data risk
not worth it vs an already-confirmed candidate). taker-flow already covered (iter4 +taker0.6→cal11).

## Anti-overfit
149 exp → BH-FDR in final report. Sealed test (last 21d) STILL NOT READ. Candidate stress-tested
from 3 independent angles, convergent. No looks-too-good leak (wr 46%, calmar 7.5 @ n54).

## Next (iter8 → converge)
- **iter8 (last refinement)**: advanced EXIT TYPES on the h8-12 winner — trailing / be_after_tp1 /
  multi_target / time_decay vs the current `single tp8/sl3/ts2880`. The exit was the core edge;
  iter3 only grid-searched `single`. Read advanced_exit_engine.py for exact params first.
- Then **CONVERGE**: search space exhausted → final checkpoint + `autoresearch-report` to REVEAL
  the sealed test for the h8-12 candidate, give honest final summary, STOP the loop (quality over
  filling budget — do NOT manufacture noise to reach 200/12:50).
