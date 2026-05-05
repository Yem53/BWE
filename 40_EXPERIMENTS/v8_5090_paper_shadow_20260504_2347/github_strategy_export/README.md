---
type: github-export
status: published-candidate
run_id: v8_5090_paper_shadow_20260504_2347
paper_only: true
order_endpoints_allowed: false
---

# V8 5090 Strategy Export

This folder contains the 20 strict live-aligned paper-shadow candidates selected from the V8 5090 search: 10 long and 10 short.

Hard conditions removed: `14d as-of universe`, `unique_days >= 20/30`. All other prior gates remain active.

Execution contract: completed 5m signal, next 1m open entry, TP close-confirm, SL touch-immediate, same-bar risk priority. This export is signal-only paper-shadow and does not authorize live/testnet/demo order endpoints.

## Metrics Summary

| ID | Side | Strategy | Exit | WR | Monthly | Mean % | Sum % | Trades | Final Mean % | Final WR | Symbols | Top5 Share |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V8P_LONG_01 | long | `L_LIVEF_T8_A4_S1706_SEL125_MPS3_ALL_P30C3` | `trail_tp8.0_tp250.0_sl10.0_tr8.0_f0.25_c1_t1440` | 0.8693 | 362.52 | 6.976 | 2616.18 | 375 | 10.561 | 1.0000 | 125 | 0.0400 |
| V8P_LONG_02 | long | `L_LIVEF_T8_A4_S1706_SEL125_MPS3_ALL_P30C3` | `trail_tp8.0_tp250.0_sl10.0_tr8.0_f0.15_c1_t1440` | 0.8693 | 362.52 | 7.035 | 2638.25 | 375 | 10.895 | 1.0000 | 125 | 0.0400 |
| V8P_LONG_03 | long | `L_LIVEF_T8_A4_S1706_SEL125_MPS3_ALL_P30C3` | `trail_tp8.0_tp230.0_sl10.0_tr8.0_f0.25_c1_t1440` | 0.8693 | 362.52 | 7.140 | 2677.37 | 375 | 10.561 | 1.0000 | 125 | 0.0400 |
| V8P_LONG_04 | long | `L_LIVEF_T8_A4_S1706_SEL125_MPS3_ALL_P30C3` | `trail_tp8.0_tp250.0_sl10.0_tr8.0_f0.1_c1_t1440` | 0.8693 | 362.52 | 7.065 | 2649.28 | 375 | 11.063 | 1.0000 | 125 | 0.0400 |
| V8P_LONG_05 | long | `L_LIVEF_T8_A4_S1706_SEL125_MPS3_ALL_P30C3` | `trail_tp8.0_tp230.0_sl10.0_tr8.0_f0.15_c1_t1440` | 0.8693 | 362.52 | 7.220 | 2707.59 | 375 | 10.895 | 1.0000 | 125 | 0.0400 |
| V8P_LONG_06 | long | `L_LIVEF_T8_A4_S1706_SEL175_MPS2_ALL_P30C2` | `trail_tp8.0_tp230.0_sl8.0_tr8.0_f0.1_c1_t1440` | 0.7622 | 337.39 | 5.925 | 2067.96 | 349 | 11.063 | 1.0000 | 175 | 0.0287 |
| V8P_LONG_07 | long | `L_LIVEF_T8_A4_S1706_SEL175_MPS2_ALL_P30C2` | `trail_tp8.0_tp230.0_sl8.0_tr8.0_f0.15_c1_t1440` | 0.7622 | 337.39 | 5.867 | 2047.70 | 349 | 10.895 | 1.0000 | 175 | 0.0287 |
| V8P_LONG_08 | long | `L_LIVEF_T8_A4_S1706_SEL175_MPS2_ALL_P30C2` | `trail_tp8.0_tp230.0_sl10.0_tr8.0_f0.1_c1_t1440` | 0.7650 | 337.39 | 6.008 | 2096.94 | 349 | 11.063 | 1.0000 | 175 | 0.0287 |
| V8P_LONG_09 | long | `L_LIVEF_T8_A4_S1706_SEL175_MPS2_ALL_P30C2` | `trail_tp8.0_tp230.0_sl8.0_tr8.0_f0.25_c1_t1440` | 0.7622 | 337.39 | 5.751 | 2007.18 | 349 | 10.561 | 1.0000 | 175 | 0.0287 |
| V8P_LONG_10 | long | `L_LIVEF_T8_A4_S1706_SEL175_MPS2_ALL_P30C2` | `trail_tp8.0_tp230.0_sl10.0_tr8.0_f0.15_c1_t1440` | 0.7650 | 337.39 | 5.950 | 2076.68 | 349 | 10.895 | 1.0000 | 175 | 0.0287 |
| V8P_SHORT_01 | short | `S_PREMOON_T5_A8_MW0.9_MPS1_P1_SEL190_min_funding_z0.35_min_oi60_z-0.2_min_ret60_z1_XP60` | `trail_tp8.0_tp230.0_sl10.0_tr8.0_f0.25_c1_t1440` | 0.9310 | 309.51 | 6.117 | 1951.21 | 319 | 5.816 | 0.8904 | 190 | 0.1755 |
| V8P_SHORT_02 | short | `S_PREMOON_T5_A8_MW0.9_MPS1_P1_SEL190_min_funding_z0.35_min_oi60_z0_min_ret60_z1_XP60` | `trail_tp8.0_tp230.0_sl10.0_tr8.0_f0.25_c1_t1440` | 0.9308 | 308.54 | 6.107 | 1941.95 | 318 | 5.693 | 0.8889 | 190 | 0.1730 |
| V8P_SHORT_03 | short | `S_PREMOON_T5_A8_MW0.9_MPS1_P1_SEL190_min_funding_z0.4_min_oi60_z-0.2_min_ret60_z1_XP60` | `trail_tp8.0_tp230.0_sl10.0_tr8.0_f0.25_c1_t1440` | 0.9172 | 304.66 | 6.087 | 1911.22 | 314 | 5.638 | 0.8529 | 190 | 0.1688 |
| V8P_SHORT_04 | short | `S_PREMOON_T5_A8_MW0.9_MPS1_P1_SEL195_min_funding_z0.35_min_oi60_z-0.2_min_ret60_z1_XP50` | `scale_tp8.0_tp250.0_sl6.0_f0.25_c1_t1440` | 0.8513 | 306.60 | 5.605 | 1771.09 | 316 | 5.912 | 0.8133 | 195 | 0.1772 |
| V8P_SHORT_05 | short | `S_PREMOON_T5_A8_MW0.9_MPS1_P1_SEL195_min_funding_z0.35_min_oi60_z-0.2_min_ret60_z1_XP60` | `scale_tp8.0_tp250.0_sl6.0_f0.25_c1_t1440` | 0.8497 | 316.31 | 5.612 | 1829.62 | 326 | 5.912 | 0.8133 | 195 | 0.1718 |
| V8P_SHORT_06 | short | `S_PREMOON_T5_A8_MW0.9_MPS1_P1_SEL195_min_funding_z0.35_min_oi60_z0_min_ret60_z1_XP50` | `scale_tp8.0_tp250.0_sl6.0_f0.25_c1_t1440` | 0.8476 | 305.63 | 5.545 | 1746.60 | 315 | 5.794 | 0.8108 | 195 | 0.1746 |
| V8P_SHORT_07 | short | `S_PREMOON_T5_A8_MW0.9_MPS1_P1_SEL195_min_funding_z0.35_min_oi60_z0_min_ret60_z1_XP60` | `scale_tp8.0_tp250.0_sl6.0_f0.25_c1_t1440` | 0.8431 | 315.34 | 5.493 | 1785.32 | 325 | 5.794 | 0.8108 | 195 | 0.1692 |
| V8P_SHORT_08 | short | `S_PREMOON_T5_A8_MW0.9_MPS1_P1_SEL190_min_funding_z0.35_min_oi60_z0.2_min_ret60_z1_XP60` | `scale_tp8.0_tp250.0_sl6.0_f0.25_c1_t1440` | 0.8439 | 304.66 | 5.419 | 1701.67 | 314 | 5.778 | 0.8235 | 190 | 0.1656 |
| V8P_SHORT_09 | short | `S_PREMOON_T5_A8_MW0.9_MPS1_P1_SEL190_min_funding_z0.35_min_oi60_z-0.2_min_ret60_z1_XP60` | `trail_tp8.0_tp250.0_sl10.0_tr8.0_f0.25_c1_t1440` | 0.9310 | 309.51 | 6.117 | 1951.21 | 319 | 5.816 | 0.8904 | 190 | 0.1755 |
| V8P_SHORT_10 | short | `S_PREMOON_T5_A8_MW0.9_MPS1_P1_SEL190_min_funding_z0.35_min_oi60_z-0.2_min_ret60_z1_XP60` | `trail_tp8.0_tp220.0_sl10.0_tr8.0_f0.25_c1_t1440` | 0.9310 | 309.51 | 6.114 | 1950.26 | 319 | 5.816 | 0.8904 | 190 | 0.1755 |

## Files

- [strategies_wr_monthly_mean_sum.csv](strategies_wr_monthly_mean_sum.csv)
- [strategies_manifest.json](strategies_manifest.json)
- [source combined candidates](../paper_candidates_combined.csv)
- [completion audit](../completion_audit.md)
