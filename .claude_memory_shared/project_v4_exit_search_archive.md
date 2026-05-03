# V4 Exit Search Archive — 40 Rounds (2026-04-30)

## Methodology
40 rounds iterative search on yao base set (5-10% pricechange-pump + prior_pumps>=3, n=261 events).
Constraint: SL ≤ -20% bounded (futures-friendly).
Metric: SUM (total return across all events).
After 10 rounds without breakthrough → reflect + pivot direction.

## Final 4 Best Exit Strategies (产出)

### EP_AGGRESSIVE: 60min ATR×10 time-decay extreme lock (Phase 4 winner)
- **Hold**: 60 min max
- **SL**: entry × ATR × 10 (auto-scales per coin volatility, ~20-30% effective)
- **Extreme lock**: time-decaying threshold
  - At t=0min: MFE >= 35% triggers lock
  - At t=60min (end): MFE >= 18% triggers lock
  - Linear interp between
  - Lock at +12% profit
- **Stats**: n=261, sum +1783, mean +6.83%, win 70%, capture 34%
- **Risk**: ATR×10 = ~20-30% loss when SL hits. **3x leverage OK**

### EP_BALANCED: 60min ATR×10 + MFE>=25% lock@15
- **Hold**: 60 min
- **SL**: entry × ATR × 10
- **Extreme lock**: MFE >= 25% triggers lock at +15% profit
- **Stats**: n=261, sum +1682, mean +6.45%, win 70%, capture 32%
- **Risk**: 3x leverage OK

### EP_SAFE: 60min ATR×10 + anti-wick + cap@30 + MFE>=25 lock@15
- **Hold**: 60 min
- **SL**: min(entry × ATR × 10, 30% hard cap)
- **Anti-wick**: SL hit only if close above SL for 2 consecutive bars (or hi >= 1.5x SL)
- **Extreme lock**: same as EP_BALANCED
- **Stats**: n=261, sum +1746, mean +6.69%, win 71%, capture 33%
- **Risk**: hard cap 30% = **5x leverage OK**

### EP_SAFEST: 60min ATR×8 + anti-wick (3-bar sustain) + MFE>=30 lock@20
- **Hold**: 60 min
- **SL**: entry × ATR × 8 (~16-24% effective)
- **Anti-wick**: 3-bar sustained close
- **Extreme lock**: MFE >= 30% lock at +20%
- **Stats**: n=261, sum +1722, mean +6.60%, win 71%, capture 33%
- **Risk**: ATR×8 + sustain = **5x leverage OK**

## Search Journey (每 phase 主要发现)

### Phase 1 (R1-10): standard mechanisms WITH SL
**Discovery**: hold 1h SL-20% beats hold 4h SL-15%. Sub-hour holds reduce SL hit rate.
- Best: hold 1h SL-20% sum +1391 (was baseline +1089)
- 10 truly distinct mechanisms: time hold / ATR trail / MFE staged / TP ladder / two-phase partial / trailing SL / vol decay / counter-pump / BTC aware / CVD reversal

### Phase 2 (R11-20): sub-hour + magnetic SL
**Discovery**: ATR-based SL beats fixed % SL (adapts to coin volatility).
- Best: hold 60min ATR×10 sum +1621
- ⚠ Some rounds were variations of time-hold; not all 10 distinct

### Phase 3 (R21-30): ATR optimization + volatility regime
**Discovery**: Adding extreme MFE lock at MFE>=25% → +15% catches runners.
- Best: 60min ATR×10 + MFE>=25 lock@15 sum +1682
- ⚠ Most rounds focused on ATR variants

### Phase 4 (R31-40): anti-wick + ensemble + tuning
**Discovery**: Time-decaying extreme lock threshold (35→18) catches more events.
- Best: 60min ATR×10 + extr 35→18 lock@12 sum +1783
- ⚠ Mostly fine-tuning of existing winner

## Total Improvement
```
BASELINE:     hold 4h SL-15%                           sum +1089  cap 21%
FINAL:        60min ATR×10 + extr 35→18 lock@12        sum +1783  cap 34%
                                                       ━━━━━━━━━━
                                                       +694 (+64%, capture +13pp)
```

## Mechanisms That FAILED (not worth retrying)
- TP ladder (any config): caps profit, kills runners
- Counter-pump exit: yao coins fire too often, triggers prematurely
- Volume normalization: too noisy for clean signal
- ATR normalization (vol returning to baseline): same noise issue
- Pre-pump baseline target: semantic issues for upside-baseline events
- Re-entry on bounce: complex + small marginal gain
- Static long holds (8h+): reversal already past, bounce-back hurts

## Mechanisms NOT YET TESTED (next round candidates)
- Funding flip trigger (real flip detection vs threshold)
- OI unwind cascade detection
- Mark-spot premium exit
- Liquidation cluster proximity
- Bayesian red-K accumulator with multiple votes
- Sector-momentum exit
- Multi-bar momentum exhaustion
- Pre-bar-close vs intra-bar SL semantics
- Adaptive trail width (per-coin learned)
- Per-entry-condition exit mapping
