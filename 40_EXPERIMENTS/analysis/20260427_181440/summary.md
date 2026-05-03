# BWE Loop Results Analysis (2026-04-27 18:14:40)

- Total rows: 20,000
- Successful (keep/discard): 18,210
- Crashes: 1,790
- Skips: 0

## Per Channel × Side

| Channel/Side | n | mean | median | p75 | max | n_pos |
|---|---:|---:|---:|---:|---:|---:|
| */both | 297 | -0.0788 | -0.0800 | +0.2530 | +0.2530 | 120 |
| */long | 2,382 | -0.0788 | -0.0800 | +0.2530 | +0.2530 | 960 |
| */short | 1,786 | -0.1235 | -0.0800 | +0.2172 | +0.2172 | 720 |
| OI_Price/both | 298 | -0.1281 | -0.1305 | +0.1074 | +0.1074 | 80 |
| OI_Price/long | 2,292 | -0.1324 | -0.1247 | +0.0560 | +0.1903 | 760 |
| OI_Price/short | 2,988 | -0.1693 | -0.1429 | +0.0361 | +0.1070 | 760 |
| Reserved6/both | 198 | -0.1233 | -0.0824 | +0.2015 | +0.2015 | 80 |
| Reserved6/long | 1,098 | -0.1330 | -0.0824 | +0.2015 | +0.2015 | 440 |
| Reserved6/short | 1,494 | -0.1701 | -0.1061 | +0.1092 | +0.1292 | 600 |
| pricechange/both | 398 | -0.0777 | -0.0868 | +0.2903 | +0.2903 | 160 |
| pricechange/long | 2,690 | -0.0667 | -0.0800 | +0.2903 | +0.3946 | 1080 |
| pricechange/short | 2,289 | -0.1373 | -0.0835 | +0.2636 | +0.2678 | 920 |

## Per Exit Family (kernel)

| Exit family | n | mean | median | p75 | max | n_pos |
|---|---:|---:|---:|---:|---:|---:|
| breakeven | 1,923 | -0.0956 | -0.0805 | -0.0800 | -0.0800 | 0 |
| fixed | 7,320 | +0.1755 | +0.2172 | +0.2530 | +0.3946 | 6680 |
| multi_tp | 3,111 | -0.2756 | -0.2800 | -0.2799 | -0.0937 | 0 |
| time_only | 2,745 | -0.7308 | -0.6952 | -0.5894 | -0.1133 | 0 |
| trail | 3,111 | -0.1496 | -0.1528 | -0.1456 | -0.0062 | 0 |

## Top 50 Entry Archetypes (by best score across all exits)

| # | id | archetype | ch/side | n_exits | best | best_exit (family) | best_tp | best_sl | trig |
|---:|---|---|---|---:|---:|---|---:|---:|---:|
| 1 | E126 | pc_pump_taker_buy_extreme_long | pricechange/long | 99 | +0.3946 | fixed_tp1_sl1_symmetric (fixed) | 0.51 | 6.00 | 3443 |
| 2 | E064 | pc_pump_taker_buy_dominant_long | pricechange/long | 100 | +0.3572 | fixed_tp1_sl1_symmetric (fixed) | 0.47 | 6.00 | 3619 |
| 3 | E148 | pc_pump_global_short_high_long | pricechange/long | 99 | +0.3496 | fixed_tp1_sl1_symmetric (fixed) | 0.47 | 6.00 | 988 |
| 4 | E051 | pc_high_liquidity_long | pricechange/long | 100 | +0.3472 | fixed_tp1_sl1_symmetric (fixed) | 0.47 | 6.00 | 2157 |
| 5 | E066 | pc_crash_taker_buy_long | pricechange/long | 100 | +0.3393 | fixed_tp1_sl1_symmetric (fixed) | 0.43 | 6.00 | 3684 |
| 6 | E036 | pc_first_signal_immediate_long | pricechange/long | 100 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 7 | E038 | pc_first_signal_30s_long | pricechange/long | 100 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 8 | E039 | pc_first_signal_1m_long | pricechange/long | 100 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 9 | E040 | pc_first_signal_3m_long | pricechange/long | 100 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 10 | E041 | pc_second_signal_cont_long | pricechange/long | 100 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 11 | E046 | pc_burst_seq_4plus_avoid | pricechange/both | 100 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 12 | E047 | pc_pretrend_aligned_long | pricechange/long | 100 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 13 | E049 | pc_pretrend_against_long | pricechange/long | 100 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 14 | E053 | pc_btc_correlated_long | pricechange/long | 100 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 15 | E054 | pc_low_btc_correl_long | pricechange/long | 100 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 16 | E055 | pc_short_event_hold_1m_long | pricechange/long | 100 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 17 | E056 | pc_short_event_hold_3m_long | pricechange/long | 100 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 18 | E057 | pc_pump_low_premium_long | pricechange/long | 100 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 19 | E062 | pc_pump_oi_rising_long | pricechange/long | 100 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 20 | E067 | pc_pump_btc_bull_long | pricechange/long | 100 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 21 | E129 | pc_pump_basis_align_long | pricechange/long | 99 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 22 | E131 | pc_pump_4th_or_more_avoid | pricechange/both | 99 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 23 | E132 | pc_pump_btc_extreme_correlated_long | pricechange/long | 99 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 24 | E133 | pc_pump_btc_no_correlation_long | pricechange/long | 99 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 25 | E136 | pc_pump_funding_resetting_long | pricechange/long | 99 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 26 | E139 | pc_pump_volume_5x_baseline_long | pricechange/long | 99 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 27 | E144 | pc_pump_macro_event_avoid | pricechange/both | 99 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 28 | E149 | pc_pump_aggressive_buy_immediate_lo | pricechange/long | 99 | +0.2903 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 6.00 | 5000 |
| 29 | E146 | pc_pump_top_trader_short_long | pricechange/long | 99 | +0.2834 | fixed_tp1_sl1_symmetric (fixed) | 0.39 | 5.81 | 989 |
| 30 | E127 | pc_pump_taker_buy_extreme_against_p | pricechange/short | 99 | +0.2678 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 3443 |
| 31 | E037 | pc_first_signal_immediate_short | pricechange/short | 100 | +0.2636 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 32 | E042 | pc_second_signal_cont_short | pricechange/short | 100 | +0.2636 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 33 | E043 | pc_second_signal_reversal_short | pricechange/short | 100 | +0.2636 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 34 | E044 | pc_third_plus_overheat_short | pricechange/short | 100 | +0.2636 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 35 | E045 | pc_third_plus_high_vol_short | pricechange/short | 100 | +0.2636 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 36 | E048 | pc_pretrend_aligned_short | pricechange/short | 100 | +0.2636 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 37 | E050 | pc_pretrend_against_short | pricechange/short | 100 | +0.2636 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 38 | E059 | pc_crash_low_premium_short | pricechange/short | 100 | +0.2636 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 39 | E063 | pc_pump_oi_falling_short | pricechange/short | 100 | +0.2636 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 40 | E068 | pc_pump_btc_bear_short | pricechange/short | 100 | +0.2636 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 41 | E128 | pc_pump_basis_diverge_short | pricechange/short | 99 | +0.2636 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 42 | E130 | pc_pump_2nd_within_30s_overheated_s | pricechange/short | 99 | +0.2636 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 43 | E140 | pc_pump_volume_below_baseline_short | pricechange/short | 99 | +0.2636 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 44 | E143 | pc_pump_weekend_short | pricechange/short | 99 | +0.2636 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 45 | E150 | pc_pump_aggressive_sell_short | pricechange/short | 99 | +0.2636 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 46 | E091 | cc_pc_then_oi_5m_long | */long | 100 | +0.2530 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 47 | E092 | cc_oi_then_pc_5m_long | */long | 100 | +0.2530 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 48 | E094 | cc_oi_pc_simultaneous_long | */long | 100 | +0.2530 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 49 | E095 | cc_three_channel_within_5m_long | */long | 100 | +0.2530 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |
| 50 | E099 | cc_pc_crash_no_r6_long | */long | 100 | +0.2530 | fixed_tp1_sl1_symmetric (fixed) | 0.36 | 6.00 | 5000 |

## Top 20 crash sources (entries that filter to <30 events)

| id | archetype | ch | n_crashes | novel_dim |
|---|---|---|---:|---|
| E019 | oi_crash_high_funding_long | OI_Price | 100 | oi_change_pct<=-8; funding>=0.02pct |
| E020 | oi_crash_negative_funding_short | OI_Price | 100 | oi_change_pct<=-8; funding<=-0.05pct |
| E060 | pc_crash_high_funding_long | pricechange | 100 | side_signal=crash; funding>=0.02pct |
| E061 | pc_crash_negative_funding_short | pricechange | 100 | side_signal=crash; funding<=-0.05pct |
| E069 | pc_pump_market_cap_small_long | pricechange | 100 | side_signal=pump; market_cap_bucket=small |
| E070 | pc_pump_market_cap_large_long | pricechange | 100 | side_signal=pump; market_cap_bucket=large |
| E083 | r6_pump_low_liq_avoid | Reserved6 | 100 | liquidity_bucket=low |
| E085 | r6_pump_premium_extreme_short | Reserved6 | 100 | side_event=pump; premium_bps>=50 |
| E112 | oi_pump_funding_extreme_pos_short | OI_Price | 99 | oi_change_pct>=8; funding>=0.1pct |
| E113 | oi_pump_funding_extreme_neg_long | OI_Price | 99 | oi_change_pct>=8; funding<=-0.1pct |
| E122 | oi_pump_volume_pct_ranked_long | OI_Price | 99 | oi_change_pct>=8; volume_pct_top_decile |
| E137 | pc_pump_funding_extreme_pos_short | pricechange | 99 | side_signal=pump; funding>=0.1pct |
| E138 | pc_pump_funding_extreme_neg_long | pricechange | 99 | side_signal=pump; funding<=-0.1pct |
| E154 | r6_pump_funding_extreme_pos_short | Reserved6 | 99 | side_event=pump; funding>=0.1pct |
| E155 | r6_pump_funding_extreme_neg_long | Reserved6 | 99 | side_event=pump; funding<=-0.1pct |
| E158 | r6_pump_top_trader_long_short | Reserved6 | 99 | side_event=pump; top_trader_position_ratio_high |
| E159 | r6_pump_global_long_extreme_short | Reserved6 | 99 | side_event=pump; global_long_ratio_extreme |
| E160 | r6_pump_global_short_extreme_long | Reserved6 | 99 | side_event=pump; global_short_ratio_extreme |
