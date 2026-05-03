# BWE Loop Results Analysis (2026-04-27 09:06:16)

- Total rows: 2,654
- Successful (keep/discard): 2,418
- Crashes: 236
- Skips: 0

## Per Channel × Side

| Channel/Side | n | mean | median | p75 | max | n_pos |
|---|---:|---:|---:|---:|---:|---:|
| */both | 39 | -0.0596 | -0.2800 | +0.2530 | +0.2530 | 15 |
| */long | 312 | -0.0596 | -0.2800 | +0.2530 | +0.2530 | 120 |
| */short | 234 | -0.0734 | -0.2800 | +0.2172 | +0.2172 | 90 |
| OI_Price/both | 40 | -0.1332 | -0.2571 | +0.0070 | +0.1074 | 10 |
| OI_Price/long | 313 | -0.1310 | -0.2618 | +0.0560 | +0.1903 | 95 |
| OI_Price/short | 408 | -0.1481 | -0.2649 | -0.0019 | +0.1070 | 95 |
| Reserved6/both | 26 | -0.0791 | -0.2770 | +0.2015 | +0.2015 | 10 |
| Reserved6/long | 143 | -0.0775 | -0.1399 | +0.2015 | +0.2015 | 55 |
| Reserved6/short | 195 | -0.1188 | -0.2800 | +0.1092 | +0.1292 | 75 |
| pricechange/both | 52 | -0.0607 | -0.2427 | +0.2903 | +0.2903 | 20 |
| pricechange/long | 356 | -0.0449 | -0.2800 | +0.2903 | +0.3946 | 135 |
| pricechange/short | 300 | -0.0674 | -0.2800 | +0.2636 | +0.2678 | 115 |

## Per Exit Family (kernel)

| Exit family | n | mean | median | p75 | max | n_pos |
|---|---:|---:|---:|---:|---:|---:|
| breakeven | 183 | -0.0955 | -0.0801 | -0.0800 | -0.0800 | 0 |
| fixed | 915 | +0.1755 | +0.2172 | +0.2530 | +0.3946 | 835 |
| multi_tp | 1,320 | -0.2755 | -0.2800 | -0.2799 | -0.0937 | 0 |

## Top 20 Entry Archetypes (by best score across all exits)

| # | id | archetype | ch/side | n_exits | best | best_exit (family) | best_tp | best_sl | trig |
|---:|---|---|---|---:|---:|---|---:|---:|---:|
| 1 | E126 | pc_pump_taker_buy_extreme_long | pricechange/long | 13 | +0.3946 | fixed_tp1_sl1_symmetric (fixed) | 0.51 | 6.00 | 3443 |
| 2 | E064 | pc_pump_taker_buy_dominant_long | pricechange/long | 13 | +0.3572 | fixed_tp1_sl1_symmetric (fixed) | 0.47 | 6.00 | 3619 |
| 3 | E148 | pc_pump_global_short_high_long | pricechange/long | 13 | +0.3496 | fixed_tp1_sl1_symmetric (fixed) | 0.47 | 6.00 | 988 |
| 4 | E051 | pc_high_liquidity_long | pricechange/long | 13 | +0.3472 | fixed_tp1_sl1_symmetric (fixed) | 0.47 | 6.00 | 2157 |
| 5 | E066 | pc_crash_taker_buy_long | pricechange/long | 13 | +0.3393 | fixed_tp1_sl1_symmetric (fixed) | 0.43 | 6.00 | 3684 |
| 6 | E036 | pc_first_signal_immediate_long | pricechange/long | 14 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 7 | E038 | pc_first_signal_30s_long | pricechange/long | 14 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 8 | E039 | pc_first_signal_1m_long | pricechange/long | 14 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 9 | E040 | pc_first_signal_3m_long | pricechange/long | 14 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 10 | E041 | pc_second_signal_cont_long | pricechange/long | 14 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 11 | E046 | pc_burst_seq_4plus_avoid | pricechange/both | 13 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 12 | E047 | pc_pretrend_aligned_long | pricechange/long | 13 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 13 | E049 | pc_pretrend_against_long | pricechange/long | 13 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 14 | E053 | pc_btc_correlated_long | pricechange/long | 13 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 15 | E054 | pc_low_btc_correl_long | pricechange/long | 13 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 16 | E055 | pc_short_event_hold_1m_long | pricechange/long | 13 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 17 | E056 | pc_short_event_hold_3m_long | pricechange/long | 13 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 18 | E057 | pc_pump_low_premium_long | pricechange/long | 13 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 19 | E062 | pc_pump_oi_rising_long | pricechange/long | 13 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 20 | E067 | pc_pump_btc_bull_long | pricechange/long | 13 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |

## Top 20 crash sources (entries that filter to <30 events)

| id | archetype | ch | n_crashes | novel_dim |
|---|---|---|---:|---|
| E019 | oi_crash_high_funding_long | OI_Price | 14 | oi_change_pct<=-8; funding>=0.02pct |
| E020 | oi_crash_negative_funding_short | OI_Price | 14 | oi_change_pct<=-8; funding<=-0.05pct |
| E060 | pc_crash_high_funding_long | pricechange | 13 | side_signal=crash; funding>=0.02pct |
| E061 | pc_crash_negative_funding_short | pricechange | 13 | side_signal=crash; funding<=-0.05pct |
| E069 | pc_pump_market_cap_small_long | pricechange | 13 | side_signal=pump; market_cap_bucket=small |
| E070 | pc_pump_market_cap_large_long | pricechange | 13 | side_signal=pump; market_cap_bucket=large |
| E083 | r6_pump_low_liq_avoid | Reserved6 | 13 | liquidity_bucket=low |
| E085 | r6_pump_premium_extreme_short | Reserved6 | 13 | side_event=pump; premium_bps>=50 |
| E112 | oi_pump_funding_extreme_pos_short | OI_Price | 13 | oi_change_pct>=8; funding>=0.1pct |
| E113 | oi_pump_funding_extreme_neg_long | OI_Price | 13 | oi_change_pct>=8; funding<=-0.1pct |
| E122 | oi_pump_volume_pct_ranked_long | OI_Price | 13 | oi_change_pct>=8; volume_pct_top_decile |
| E137 | pc_pump_funding_extreme_pos_short | pricechange | 13 | side_signal=pump; funding>=0.1pct |
| E138 | pc_pump_funding_extreme_neg_long | pricechange | 13 | side_signal=pump; funding<=-0.1pct |
| E154 | r6_pump_funding_extreme_pos_short | Reserved6 | 13 | side_event=pump; funding>=0.1pct |
| E155 | r6_pump_funding_extreme_neg_long | Reserved6 | 13 | side_event=pump; funding<=-0.1pct |
| E158 | r6_pump_top_trader_long_short | Reserved6 | 13 | side_event=pump; top_trader_position_ratio_high |
| E159 | r6_pump_global_long_extreme_short | Reserved6 | 13 | side_event=pump; global_long_ratio_extreme |
| E160 | r6_pump_global_short_extreme_long | Reserved6 | 13 | side_event=pump; global_short_ratio_extreme |
