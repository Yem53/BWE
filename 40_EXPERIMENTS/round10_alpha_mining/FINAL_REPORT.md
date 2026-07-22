# Round10 Alpha Mining — Final Report

**Run**: 2026-05-24, 7h autonomous protocol (read-only). 157 experiments, 9 directions.
**Splits**: DEV (select) = Feb15–Apr25 (69d) · OLDER (flag) = Nov–Feb15 · **TEST = last 21d
(Apr25–May16) SEALED**, revealed once here. Objective: find a short-the-pump alpha beating live B/D.

## 1. Headline
The round's leading candidate — **h8-12 UTC entry + multi-day wide exit** — looked spectacular on
DEV (+216%, 6/6 windows, calmar 7.5) and survived every in-sample robustness check, **but lost
−25% on the sealed test**. It is a FALSE POSITIVE (overfit to the Feb–Apr regime). **Do not deploy.**
The sealed test instead **validated the existing live strategies B (+72%) and D (+49%)**.

## 2-3. Full disclosure (no cherry-picking)
157 experiments · 83 gated on DEV · 0 anomalies · 0 errors · 0 protocol violations (test never
touched for selection). Direction scoreboard:

| Direction | n | gated | result |
|---|---|---|---|
| long side | 7 | 0 | DEAD (−1100/−1560%) |
| hour sweep / h8-12 / h16-20 grids | 43 | 10 | h8-12 best on dev |
| multi-day exit grids (h8-12) | 30 | 27 | wide exit = dev edge |
| robustness perturb | 28 | 27 | dev plateau (knife-edge ruled out) |
| OI-driven (oi_price_1h) | 6 | 1 | no standalone edge; oi_chg filter hurts |
| micro-window 3s/60s/180s | 6 | 0 | NO-GO |
| confluence (≥2 windows) | 4 | 0 | NO-GO |
| lifecycle (repeat pump) | 6 | 6 | redundant, no incremental edge |
| ensemble (h812⊕D) | 1 | 1 | corr 0.042 (independent) but moot |
| exit refine (advanced types) | 8 | 8 | trailing best dev calmar (older −17) |

## 4-5. Top-K + SEALED-TEST reveal (train→test decay)
| config | DEV sum / calmar | **TEST sum / calmar** | decay |
|---|---|---|---|
| h8-12 + single tp8/sl3 | +216% / 7.53 | **−25.3% / −0.52** | total collapse |
| h8-12 + trailing t4/arm5 | +213% / 10.21 | **−30.0% / −0.78** | total collapse |
| h8-12 + multi 5/8/11 | +140% / 6.71 | **−28.3% / −0.66** | total collapse |
| LIVE B | +50% / 0.90 | **+72.3% / 3.04** | IMPROVED OOS |
| LIVE D | +40% / 0.65 | **+49.2% / 1.18** | IMPROVED OOS |

🔴 Decay >100% (positive→negative) on all 3 candidates → overfit confirmed by the sealed window.

## 6. Multiple-comparison correction
Primary candidate per-trade t-stat: DEV t=2.51, p=0.0060 → **TEST t=−0.72, p=0.76**.
Bonferroni α (m=157) = 0.00032. The candidate **fails Bonferroni even on DEV** (0.0060 ≫ 0.00032).
(Caveat: 83 gated configs are mostly correlated grid-neighbors, so the effective # independent
tests ≪ 157; Bonferroni is over-conservative — but the point stands: dev significance was weak and
test significance is absent.)

## 7-8. Patterns + overfit self-check
- Effective dims: time-of-day (h8-12) + a WIDE multi-day exit drove all dev gains; tight exits
  flipped every winner negative. OI magnitude, micro-windows, confluence, pump-history: no edge.
- Overfit signal: 47/83 gated were even positive on OLDER (Nov–Feb) — i.e. the dev edge looked
  2-period-robust — yet still failed the forward 21d. **In-sample robustness ≠ OOS validity.**
- Data-leakage: none (entries use closed-bar features, exits use forward klines; self-validated
  event engine reproduced eval_window exactly).

## 9. Quant specifics
- Frequency: candidate ~54 trades/69d on dev (≈0.8/day), broad across 40 symbols (top_share 7%) —
  NOT single-symbol luck, yet still overfit to the period.
- Regime: candidate was all-regime-positive WITHIN dev but its TEST losses concentrated in bullish
  sub-periods (shorting pumps got run over when the tape turned up).

## 10. Recommendation
1. **Keep B and D live, unchanged** — they just passed the hardest out-of-sample test of the round.
2. **Do NOT deploy h8-12 / any round10 candidate.**
3. This round's real value = the anti-overfit protocol caught a losing strategy before it cost money.
4. Next round: use **walk-forward with MULTIPLE rolling OOS windows** (not one dev + one 21d test);
   require a candidate to win on several consecutive forward windows before it earns trust.

## 11. Integrity note
experiments.jsonl holds dev/older only; the sealed test lives in test_reveal.json, evaluated for
the first and only time in §5. No selection ever used the test window.
