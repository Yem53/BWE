# Round10 Checkpoint 2 (iteration 4, robustness — 126 experiments total)

**Time**: 06:19 UTC (deadline 12:50). 

## Top candidate CONFIRMED ROBUST (not a knife-edge)
Entry `hours[8-12], ret60_atr_min ~3.5-4, vol_zs_min 1.5, rsi_min 70, pullback_pct_max -0.02`
+ exit `single, tp 7-8 ATR, sl 3 ATR, time_stop 2880 (2d)`:

- **27/28 one-dim perturbations stayed gated** — stable plateau across ret60 (3.5-5), vol_zs
  (1.25-2), rsi (68-75), pullback (-0.015 to -0.03), exit tp (7-9), sl (2.5-3.5).
- Best p_ret60=3.5: **dev +216%, 6/6 windows, calmar 7.5, top_share 7.4%, 40 syms, 40 days**.
- **Multi-regime positive**: bull +20 / chop +90 / **bear +107** (n14/26/14) — not a single-regime
  fluke; shorting pumps shines in bear.
- Older-data (Nov–Feb) positive across the plateau → regime-robust.
- Adding extra confirms (taker_max 0.6 → calmar 11; body_neg; upper_wick) keeps it gated (optional).

→ This is the leading alpha. Pending **sealed-test (last 21d) confirmation** in the final report.

## Anti-overfit status
- Sealed test still NOT read. top_share 7% (well under 35 gate). 27/28 plateau = not overfit.
- calmar up to 11-12 on a couple low-n variants — note for sealed-test scrutiny; main candidate
  calmar ~7.5 at n~51 is fine. No looks-too-good leak (wr 42-50%, no wr>90).

## Next (iterations 5+)
- **OI-driven** (join): does an OI filter improve the h8-12 candidate / is there standalone OI alpha?
- **Micro-window reversion** (join): 3s/60s/180s alerts → multi-day exit.
- **Multi-window confluence** (join): ≥2 windows same symbol within T.
- **Ensemble**: h8-12-multiday + D (h0-4) — correlation + combined portfolio.
