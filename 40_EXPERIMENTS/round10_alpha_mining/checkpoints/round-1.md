# Round10 Checkpoint 1 (iterations 1–3, 98 experiments)

**Loop**: started 2026-05-24 05:50 UTC, 7h deadline 12:50 UTC. Recent-focus.
**Splits**: dev = Feb15–Apr25 (69d) · older (flag) = Nov01–Feb15 · TEST = last 21d (Apr25–May16) **SEALED, not peeked**.

## Findings so far

1. **LONG side = dead** (D2). Every long config (momentum + oversold bounce): −1100 to −1560% dev,
   wr 27%, 0/6 windows, thousands of trades. Hard NO-GO → dropped. Confirms "妖币 = short-only".
2. **Time-of-day is the key dimension.** Short-fade all-hours = −88%; but **h8-12 UTC** and h16-20
   are positive. h8-12 is the prize block (not currently used live — B is h15-19, D is h0-4).
3. **TOP CANDIDATE (regime-robust)** — h8-12 entry + multi-day wide exit:
   - Entry: `hours [8,9,10,11], ret60_atr_min 4.0, vol_zs_min 1.5, rsi_min 70, pullback_pct_max -0.02`
   - Exit: `single, tp_atr 8.0, sl_atr 3.0, time_stop 2880 (2d), confirm 1`
   - **dev +201%, 6/6 windows, calmar 7.88, older +16 (positive out-of-regime!)**, n=51.
   - 22/24 exit-grid configs gated. The win is the EXIT: wider SL (3-4 ATR) + 6-8 ATR TP + 1-2 day
     hold. The live 4h/tp5/sl2.5 strangles the reversion. Matches LEARNINGS "妖币 = wide TP + let it run".
4. **Multi-day wide exit rescues all-hours** (−88 → +89) and h16-20 (+39), but **hurts D (−53) and
   B (−50)** — their specific entries want a tighter exit. So exit must match entry.
5. Baselines on this dev: B +50 (2/6, fails consistency), D +40 (4/6, gated).

## Anti-overfit status
- Sealed test (last 21d) NOT read. Older-data POSITIVE on top candidate (+16) = robustness signal.
- Top candidate calmar 7.9 is high but wr 45% / n 51 / 6-6 windows → not a leak (no wr>90, no perfect).
- 40 gated winners; multiple-comparison risk noted → final claim needs sealed-test confirmation (report).

## Next (iterations 4+)
- **Robustness-perturb** the top candidate (vary entry params ±, hold/TP/SL ± ) — confirm not knife-edge.
- **Join-directions**: OI-driven (alert oi_chg / metrics), micro-window reversion (3s/60s/180s alerts),
  multi-window confluence (alert archive).
- **Ensemble** of gated winners (h8-12 + D + others) — correlation / combined portfolio.
- Then `autoresearch-report` reveals the sealed test for the survivors.
