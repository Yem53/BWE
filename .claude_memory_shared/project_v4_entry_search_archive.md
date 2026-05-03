# V4 Entry Search Archive — 40 Rounds (2026-04-30)

## Methodology
40 rounds iterative search on candidate pool: 3-15% pricechange-pumps (n=833 events).
Fixed exit: `60min ATR×10 + extr 35→18 lock@12` (Phase 4 winner from exit search).
Metric: SUM (total return).
Min sample: n>=30 events for round to be valid.

## Final Best Entry Strategy

### V4_ENTRY_CHAMPION
```
Filter:        magnitude 3-13% pricechange-pump
              AND top_trader_long_short_ratio > 0.9
              AND funding_rate > 0
              
NO yao filter (data-disproven important)
NO has_dump
NO lifecycle filter
NO BTC concurrent direction
NO volume range
```
**Stats**: n=525, sum +4177, mean +7.96%, win 74%, capture 63% of ideal MFE
**Frequency**: ~17 trades/day (high frequency)

## Top 5 Alternative Entries (also strong)

| # | Filter | n | sum | mean | win | cap |
|---|---|---|---|---|---|---|
| 🥇 | 3-13% + LS>0.9 + fund>0 | 525 | +4177 | +7.96% | 74% | 63% |
| 🥈 | 2-12% + LS>0.9 + fund>0 | 520 | +4113 | +7.91% | 74% | 63% |
| 🥉 | 3-10% + LS>0.9 + fund>0 | 511 | +4032 | +7.89% | 74% | 64% |
| 4 | 3-12% + LS>0.9 + fund>0 | 520 | +4113 | +7.91% | 74% | 63% |
| 5 | 3-10% + LS>0.9 + fund>-0.0001 | 532 | +4079 | +7.66% | 75% | 63% |

All within ~2% sum of each other. All viable.

## Search Journey

### Phase 1 (R1-10): single-feature filters [✅ truly 10 distinct dimensions]
**Discovery 1 (R1, MASSIVE)**: With new exit (60min ATR×10), `mag 3-10% NO YAO filter` beats baseline +2035 → +3636. The yao filter was a v3-era construct; with the new exit, fresh pumps also produce profit.
- Tested: mag / yao / has_dump / vol / lifecycle / funding / OI / top_LS / taker_buy / BTC

### Phase 2 (R11-20): combinations on wide base [⚠ 6/10 truly new]
**Discovery 2 (R13)**: `top_LS > 1` boosts mean while keeping high n. n=609, sum +3876.

### Phase 3 (R21-30): top_LS optimization [⚠ mostly variations of one mechanism]
**Discovery 3 (R25)**: `top_LS>=0.9 + funding>0` combined: n=511, sum +4032.

### Phase 4 (R31-40): refinement [⚠ all fine-tuning, not new mechanisms]
**Discovery 4 (R37)**: `mag widened to 3-13%` keeps gains. n=525, sum +4177.

## Total Improvement
```
BASELINE:     yao>=3 + 5-10% pricechange-pump            sum +1783  cap 52%
FINAL:        3-13% + top_LS>0.9 + funding>0             sum +4177  cap 63%
                                                         ━━━━━━━━━━
                                                         +2394 (+134%, capture +11pp)
                                                         frequency: 260→525 trades (2x)
```

## Filter Dimensions Tested vs NOT Tested

### Tested in 40 rounds:
- magnitude bucket
- prior_pumps_24h (yao depth)
- has_dump_24h
- vol_24h range
- lifecycle classification
- funding rate snapshot
- OI 5min change
- top_trader_LS_ratio
- taker_buy_ratio
- BTC concurrent direction
- hour of day (UTC)
- combinations of above

### NOT tested (next round candidates):
- listing_age_days (new vs old coin)
- symbol category (top10 vs alt vs micro)
- pump_rapidity (% per minute)
- recent_atr_percentile (volatility regime)
- pre_pump_volume_baseline
- top_trader L/S DELTA (rising vs falling)
- funding rate TREND (rising/falling 24h)
- funding 24h average
- OI 24h % change
- OI velocity (rate of change)
- cross-channel resonance (R6 + OI co-fire)
- pump-dump-pump pattern detection
- wick structure of pump bar
- multi-bar volume profile
- mark-spot premium

## Robustness Check Notes

**Potential overfitting concerns**:
- Single 30-day sample, no out-of-sample test
- top_LS > 0.9 threshold: tested 0.5/0.7/0.9/1.0/1.2/1.5 — 0.9 likely robust
- Magnitude 3-13%: tested adjacent buckets — minor sensitivity
- Funding > 0: very loose threshold, almost any non-negative value works

**To verify**: split data 70/30, test stability. Or wait for paper-shadow to validate.
