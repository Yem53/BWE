# Scanner vs BWE — Accuracy & Alignment (oi_price_1h dimension)

**Date**: 2026-05-24 · **Method**: recommended path (a) — independently replay my scanner's
`detect_oi_price_1h` over data.binance.vision history (1m klines + 5m metrics/OI) for exactly the
582 symbols × 204 days BWE alerted on, then match against BWE's real `oi_price` channel messages.
Read-only; reuses deployed `detectors.py`; downloads cached under `cache/`. Script: `recall_oi_price.py`.

## Bottom line — 准确 + 对齐 + 超过 all confirmed (for the OI&price dimension)

| Question | Answer |
|---|---|
| **准确度 (accuracy)** | ✅ My independent recompute matches BWE's reported numbers to **median 1.07pp (price), 0.69pp (OI)**. Both are accurate. |
| **对齐 (alignment/recall)** | ✅ **93.1%** of BWE's 12,754 oi_price events would fire my scanner at current 5% threshold. |
| **超过 (exceeds)** | ✅ On the same symbol-days my scanner produced **11.3× more** stored detections (144,291 vs 12,754); 98,157 had no BWE event nearby. |
| **blind spots?** | ❌ None. **0 misses from missing data**; all 885 misses are real moves measured at <5% (524 were 3–5% = BWE simply uses a looser threshold). |

## Recall = 11,869 / 12,754 = 93.1%  (±10 min, threshold 5%)
- 0 events lost to missing/delisted data → binance.vision covers all 582 symbols.
- Neighborhood insensitive: ±5m 92.6% · ±10m 93.1% · ±30m 93.9% (so misses are NOT timing artifacts).
- By month: 2025-09 100% · 10 99.5% · 11 89.5% · 12 90.9% · 2026-01 90.4% · 02 85.4% · 03 88.4% · 04 94.8%.
  (Dips in calmer months = more BWE events land in the 3–5% band below my 5% floor.)

## The misses are a THRESHOLD choice, not a capability gap → tunable in one line
Recall on covered events if my `oi_price_1h` threshold were:

| threshold | recall |
|---|---|
| ≥3% | **97.1%** |
| ≥4% | 94.6% |
| **≥5% (current)** | **93.1%** |
| ≥6% | 91.5% |
| ≥8% | 86.0% |

→ To **match/exceed BWE** on this dimension, lower `config.json oi_price_1h.price_thr_pct/oi_thr_pct`
from 5.0 → ~3–4 (cost: more volume; fine for a research collector). *Recommendation only — not changed.*

## Honest scope & caveats
1. **Only the OI&price 1h dimension is validated here.** BWE's `pricechange` channel (68,029 msgs,
   the 3s/60s/180s micro-windows) CANNOT be reconstructed from 1-minute historical data (needs
   tick/aggTrades). Its alignment is unverified by this method — would need a live-forward A/B or
   tick-level replay.
2. **"11.3×" is raw stored-detection rows on shared symbol-days**, not distinct anomalies (a sustained
   move re-fires after the 10-min cooldown). It shows the scanner casts a much wider net; exact
   "distinct extra anomalies" needs episode-clustering + a full-universe replay.
3. Match is **capability-based** ("would my detector fire at BWE's time"), the right question for
   alignment; it abstracts away the deployed cooldown/push-filter.

## Artifacts
`recall_oi_price.py` (re-runnable, cached) · `recall_summary.json` (machine-readable) ·
`misses_with_data.jsonl` (the 885 sub-5% misses for inspection) · `cache/` (binance.vision dumps).
