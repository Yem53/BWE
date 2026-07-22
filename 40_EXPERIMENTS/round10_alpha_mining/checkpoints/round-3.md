# Round10 Checkpoint 3 (iterations 5–6, joins+ensemble — 143 experiments total)

**Time**: 06:33 UTC (deadline 12:50). 143/200 experiments. Self-validated event engine.

## All big directions now screened — h8-12 multi-day stands ALONE as the alpha

| Direction | Verdict | Evidence |
|---|---|---|
| Long side | DEAD | iter1: −1100/−1560% dev, 0/6 |
| Time-of-day | **h8-12 = prize** | iter1-2 |
| Multi-day wide exit | **key mechanism** | iter2-3; tight exit (SX) flips winners negative |
| h8-12 robustness | **CONFIRMED plateau** | iter4: 27/28 perturbations gated, multi-regime + |
| **OI-driven** (oi_price_1h) | **no standalone alpha** | iter5 below |
| **Micro-window** (3s/60s/180s) | **NO-GO** | iter5 below |
| **Confluence** (≥2 windows) | **NO-GO** | iter6 below |
| **Ensemble** (h812 ⊕ D) | uncorrelated but D dilutes | iter5 below |

## iter5 — event-driven joins (BWE alert archive → entry mask → SAME eval_window downstream)
**Self-check**: new annotate→simulate_portfolio→metrics path reproduces `calibrate.eval_window`
EXACTLY (n=54, sum=216.21 both) — event/ensemble numbers are apples-to-apples.

- **OI (oi_price_1h, 24.8k universe∩grid events)**: only `oi1h_p8_h8-12_md` gated (n53, +80.7%,
  calmar 1.14) — i.e. just the h8-12 time-edge re-expressed. Adding `oi_chg≥10` HURT (+87→−48).
  Tight exit `SX` → −158. **OI magnitude carries no edge beyond price×hour.**
- **Micro (180s-extreme/60s/3s)**: every config negative (−18 to −194). Spike-fade has no edge in
  the liquid top-200 universe (caveat: micro-cap 妖币 outside the 200-sym npz not tested).
- **Ensemble (DEV)**: h812_md +216%/cal7.5/dd29 · D +40%/cal0.65/dd61 · COMBINED +256%/cal3.2/dd80.
  **corr(h812,D)=0.042** → genuinely independent edges, but equal-weight blend dilutes h812's
  risk-adjusted quality. Run both for diversification, but size h812 heavier; don't equal-weight.

## iter6 — confluence: NO-GO (all negative, even h8-12-restricted −24.8). Multiple-window
confirmation adds concentration/noise, not signal.

## Anti-overfit status
- 143 exp (well past 30 → FDR burden noted; final report applies BH-FDR). Sealed test still NOT read.
- The leading alpha is unchanged & now stress-tested from 3 independent angles (param plateau, OI
  event re-derivation, regime split) — convergent, not a single lucky slice. top_share 5.7–7.4%.

## Next (iter7+, then converge)
- **妖币 lifecycle** (repeated pump-dump): count prior alerts/pumps per symbol from archive → does
  fading repeat-offenders beat plain h8-12? (last genuinely-novel direction, data already loaded)
- **Funding-rate join** ONLY if clean data available (not in npz; 30d parquet overlaps sealed edge → skip if risky)
- Then **converge**: search space largely exhausted → final checkpoint + `autoresearch-report`
  to REVEAL sealed-test (last 21d) performance of the h8-12 candidate.
