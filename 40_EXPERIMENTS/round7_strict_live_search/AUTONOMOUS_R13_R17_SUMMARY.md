# Autonomous Loop Summary — R13 → R17

**Date**: 2026-05-16
**Status**: ✅ Exit conditions exceeded
- Tier S: **61 found** (target: 10)
- Tier A: **658 found** (target: 50)

---

## What changed each round

| Round | Directions | New Tier S | Cumulative | Key learning |
|-------|-----------|-----------:|-----------:|--------------|
| R13   | D76-D79 (d71 push + multi-TP + ts sweep + filter add) | 0 | 1 | Pure variations on existing winners saturated |
| R14   | D80 multi-TP d71b, D81 multi-TP d71a/c, D82 filter, D83 long scout | +1 | 2 | Multi-TP on d71b unlocked one new; long-side ZERO alpha in 30d |
| R15   | D84-D87 (tighten d72, d71+hours, multi-TP d72/d71) | 0 | 2 | More variations on same alpha bases yields nothing |
| **R16** | **D88 long (fixed), D89 atr regime, D90 ret60 cap, D91 rejection** | **+3** | **5** | **`ret60_atr_max=8` cap on d71b unlocked 3 new Tier S** |
| **R17** | **D92-D95: scale ret60 cap × all bases + multi-TP combo** | **+56** | **61** | **multi-TP + ret60 cap is the dominant alpha** |

## The two bugs I found mid-loop

1. **`ret60_atr_max` silently ignored** by `build_entry_mask` — every prior round that tested an upper-cap on `ret60` was a no-op. Fixed in R16.
2. **`pullback_pct_min` silently ignored** — broke D83 long scout entirely. Fixed in R16, re-tested in D88 (still zero alpha for longs).

Patch added these to `loop_search_framework.py`:
- `ret60_atr_max`, `pullback_pct_min`, `atr_pct_min`, `atr_pct_max`.

## The key insight (in plain language)

**Capping pump extremity unlocks short-side alpha.**

When `ret60 / ATR > 10`, the pump is so violent that the snap-back hits your stop before TP. Filtering those out (cap at 8-10) lifts WR by ~5 percentage points across the board — enough to push 56 strategies from Tier A 5/6 into Tier S 6/6.

Combined with multi-target TP (sell half at +3 ATR, rest at +7-8 ATR), this is the dominant alpha:

```
ENTRY (d71b base):
  short when:
    ret60 / atr >= 3.5  AND  ret60 / atr <= 9.0   ← the cap
    pullback <= -3.5%
    ret5 / atr <= -0.2
    vol_zs >= 1.0
    rsi >= 65

EXIT (multi-TP example):
  TP1 = +3 ATR @ 45% size
  TP2 = +7-8 ATR @ 55% size
  SL  = -2.2 ATR
  time_stop = 240 min
```

## 10 strategies recommended for paper/live (max diversity)

See `DEPLOYMENT_TOP10_v15.json` for full configs.

| Slot | Base + cap | Exit | Sum% | WR% | n  | syms |
|------|-----------|------|----:|----:|---:|-----:|
| S1 | d71b cap=9.0 | multi 3.0(45%)+7.0(55%) SL2.2 | +214 | 60 | 43 | 33 |
| S2 | d71b cap=9.0 | multi 3.0(60%)+7.5(40%) SL2.5 | +197 | 67 | 42 | 33 |
| S3 | d71b cap=9.0 | multi 3.0(65%)+7.0(35%) SL2.2 | +202 | 65 | 43 | 33 |
| S4 | d71b cap=9.0 | multi 3.0(40%)+7.0(60%) SL2.5 | +203 | 57 | 42 | 33 |
| S5 | d71b cap=9.0 | multi 3.0(45%)+8.0(55%) SL2.0 | +197 | 58 | 43 | 33 |
| S6 | d71b cap=8.0 | multi 3.0(40%)+8.0(60%) SL2.2 | +180 | 56 | 39 | 32 |
| S7 | d71b cap=8.0 | multi 3.0(60%)+7.5(40%) SL2.5 | +160 | 63 | 38 | 32 |
| S8 | d71b cap=10.0 | multi 3.0(45%)+7.0(55%) SL2.0 ts300 | +160 | 57 | 44 | 35 |
| S9 | h15-20 + cap=10 | single TP4.8 SL2.5 | +157 | 55 | 74 | 50 |
| S10 | h14-19 (no cap, original) | single TP4.8 SL2.5 | +154 | 55 | 76 | 51 |

## Correlation warning

S1-S8 share the **same entry signal** (d71b family) — they will fire on the same coin at the same minute, just with different exits. The portfolio simulator caps concurrent positions at 3, so real exposure is bounded, but:

- **For paper deployment**: deploy 3-4 of S1-S8 (different exits) + S9 + S10 = 5-6 active strategies. They'll converge to ~3 active positions.
- **S9 and S10 use the hours filter** (`h14-19` / `h15-20`) → fewer signals, more spaced out → lower correlation with d71b family. Excellent diversifiers.

## What I did NOT do

- **No long-side strategy survived** — confirms Round 7 finding that 30-day long alpha is structurally absent in these 200 syms.
- **No OI / funding integration** — network was unreliable, user said skip. The current Tier S set uses only price+volume+RSI+ATR features.
- **No paper-live re-validation yet** — these strategies are backtest-only. Before any live capital, run `live_runner.py` in paper mode for 5-7 days to confirm execution alignment.

## Files written

- `loop_search_r13.py`-`loop_search_r17.py` — five new search scripts (each chains from the previous)
- `round13_robust.json`-`round17_robust.json` — cumulative robust set per round
- `final_top_candidates_v10.json`-`v14.json` — deduped Tier S/A snapshots
- `DEPLOYMENT_TOP10_v15.json` — final 10-strategy diversified deployment slate
- `loop_search_framework.py` — patched to support `ret60_atr_max`, `pullback_pct_min`, `atr_pct_min/max`

## Next actions (user decision)

1. **Review the 10 strategies** in `DEPLOYMENT_TOP10_v15.json`
2. **Pick a subset** for paper deployment (recommend S1, S2, S6, S8, S9, S10 — 6 strategies covering both bases × 3 cap levels × 2 exit families)
3. **Run paper-shadow** for 5-7 days on EC2 before any live capital
4. **Replace** the lookahead-inflated `B_ASIA_AM_STRICT` currently live with one of S9 or S10 (proper hours-filtered with strict as-of features)
