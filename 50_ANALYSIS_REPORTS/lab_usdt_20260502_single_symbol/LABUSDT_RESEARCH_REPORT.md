# LABUSDT Single-Symbol Entry/Exit Research - 2026-05-02
## Verdict
Best scanned case-study rule: `L_pullback_ema_reclaim` `long` with exit activation `25%`, giveback `0.5`, hard stop `12%`, max hold `240m`.
Scan stats: trades `48`, mean `14.15%`, median `11.89%`, p10 `-12.00%`, win rate `58.3%`, mean MFE `32.72%`, capture `43.2%`.
This is a LABUSDT-only case study on one extreme regime, not a live promotion. It should seed a cross-symbol rerun before any trading decision.

Scan scoring excludes right-censored entries that have not reached their max-hold window unless stop/trailing exit already fired.

## Data Used
- `symbol`: `LABUSDT`
- `rows_1m`: `14244`
- `first_1m_utc`: `2026-04-23 00:00:00`
- `last_1m_utc`: `2026-05-02 21:12:00`
- `listing_utc`: `2025-10-17 14:30:00`
- `bwe_events`: `177`
- `bwe_first_utc`: `2026-04-23 11:14:52`
- `bwe_last_utc`: `2026-05-02 17:10:14`
- `latest_close`: `2.901`
- `latest_close_vs_first_1m_pct`: `408.2340574632095`
- `sample_high`: `3.455`
- `sample_high_utc`: `2026-05-02 16:23:00`
- `sample_low`: `0.564`
- `sample_low_utc`: `2026-04-23 00:23:00`
- `latest_24h_change_pct`: `129.605`
- `latest_24h_high`: `3.455`
- `latest_24h_low`: `0.7115`
- `latest_24h_quote_volume`: `2652164246.40332`
- `latest_mark_price`: `2.89768508`
- `latest_funding_rate`: `nan`
- `latest_oi`: `23199276.0`
- `latest_oi_chg_15m_pct`: `0.7737230919246718`
- `latest_taker_buy_sell_ratio`: `1.0668`
- `latest_top_position_ls`: `1.2953`
- `latest_ret_15m_pct`: `11.79190751445085`
- `latest_ret_60m_pct`: `34.212352532963195`
- `latest_breakout_20`: `False`
- `latest_bwe_event_count_1m`: `0`
- BWE event count by source: `{'BWE_pricechange_monitor': 162, 'BWE_OI_Price_monitor': 9, 'BWE_Reserved6': 5, 'BWE_tier2_monitor': 1}`

## Strategy Shape
The strongest practical shape is not instant chase on every alert. It is a two-stage long framework: enter only when LAB breaks or reclaims momentum with abnormal volume and non-collapsing OI, then use a delayed trailing exit that starts only after meaningful MFE. For 'eat full before exit', the exit should tolerate large noise early and tighten only after the move pays.

Recommended LAB-specific candidate:

1. Entry A - momentum continuation: close above prior 20-minute high, 5m return >= 4%, 20-bar quote-volume z-score >= 1, OI 15m change > -2%, taker buy/sell >= 0.95.
2. Entry B - hot pullback reclaim: previous 30m impulse >= 18%, current pullback from recent high between 3% and 18%, price reclaims EMA5, taker ratio not weak.
3. Exit - eat-full trailing: hard stop around 9-12%, do not trail until +12% to +18% MFE, then allow 35-50% giveback of peak gains, max hold 120-240m. Exit earlier if OI drops hard and taker ratio flips below 1 while price loses EMA5.

## Current Read

As of `2026-05-02 21:12:00` UTC, close is `2.9010`, 15m return `11.79%`, 60m return `34.21%`, 20m breakout flag `False`, taker buy/sell `1.0668`, OI 15m change `0.77%`, top-position long/short `1.2953`.

That combination is a bounce with top-trader positioning still net long, but taker flow below 1.0. It is not a clean fresh long trigger under the scanned rules; the cleaner entry is either a new high-volume breakout above the recent 20m high with taker recovery, or a controlled pullback/reclaim.

## Top Scanned Rules

| rule                   | side   |   activation |   giveback |   hard_stop |   max_hold |   trades |   mean_exit_ret |   median_exit_ret |   p10_exit_ret |   p25_exit_ret |   win_rate |   mean_mfe |   mean_mae |   capture_ratio |     score |
|:-----------------------|:-------|-------------:|-----------:|------------:|-----------:|---------:|----------------:|------------------:|---------------:|---------------:|-----------:|-----------:|-----------:|----------------:|----------:|
| L_pullback_ema_reclaim | long   |           25 |       0.5  |          12 |        240 |       48 |        14.1501  |          11.8877  |            -12 |       -12      |   0.583333 |    32.7174 |   -18.3121 |        0.432494 |  2.15009  |
| L_pullback_ema_reclaim | long   |           35 |       0.5  |          12 |        240 |       48 |        13.1207  |           1.57144 |            -12 |       -12      |   0.5      |    32.7174 |   -18.3121 |        0.401032 |  1.12073  |
| L_pullback_ema_reclaim | long   |           18 |       0.5  |          12 |        240 |       48 |        12.7263  |           9.25336 |            -12 |       -12      |   0.604167 |    32.7174 |   -18.3121 |        0.388975 |  0.726269 |
| L_pullback_ema_reclaim | long   |           25 |       0.65 |          12 |        240 |       48 |        12.3522  |           1.57144 |            -12 |       -12      |   0.5      |    32.7174 |   -18.3121 |        0.377541 |  0.352173 |
| L_pullback_ema_reclaim | long   |           12 |       0.65 |          12 |        240 |       49 |        12.345   |           3.61386 |            -12 |       -12      |   0.612245 |    33.0423 |   -17.9619 |        0.373613 |  0.345034 |
| L_pullback_ema_reclaim | long   |           35 |       0.25 |          12 |        240 |       53 |        11.9785  |          16.9286  |            -12 |       -12      |   0.566038 |    35.5997 |   -16.9139 |        0.336478 | -0.021453 |
| L_pullback_ema_reclaim | long   |           12 |       0.5  |          12 |        240 |       49 |        11.8959  |           5.37246 |            -12 |       -12      |   0.653061 |    33.0423 |   -17.9619 |        0.360019 | -0.104143 |
| L_pullback_ema_reclaim | long   |           25 |       0.25 |          12 |        240 |       55 |        11.8128  |          18.4125  |            -12 |       -12      |   0.654545 |    35.5726 |   -16.4188 |        0.332077 | -0.187158 |
| L_pullback_ema_reclaim | long   |           35 |       0.65 |          12 |        240 |       48 |        11.743   |          -7.59376 |            -12 |       -12      |   0.458333 |    32.7174 |   -18.3121 |        0.358923 | -0.256955 |
| L_pullback_ema_reclaim | long   |           18 |       0.65 |          12 |        240 |       48 |        11.5343  |           2.29766 |            -12 |       -12      |   0.520833 |    32.7174 |   -18.3121 |        0.352544 | -0.465676 |
| L_pullback_ema_reclaim | long   |            8 |       0.5  |          12 |        240 |       50 |        11.2802  |           3.45691 |            -12 |        -2.7477 |   0.68     |    33.6897 |   -17.7494 |        0.334827 | -0.719769 |
| L_pullback_ema_reclaim | long   |           35 |       0.25 |           6 |        120 |       54 |         5.16468 |          -6       |             -6 |        -6      |   0.37037  |    23.0152 |   -14.2023 |        0.224403 | -0.835318 |

## Recent 1m Bars

| utc                 |   open |   high |    low |   close |   quote_volume |   trade_count |    ret_1m |    ret_5m |   ret_15m |   sum_open_interest |   buy_sell_ratio |   top_position_ls |
|:--------------------|-------:|-------:|-------:|--------:|---------------:|--------------:|----------:|----------:|----------:|--------------------:|-----------------:|------------------:|
| 2026-05-02 21:07:00 | 2.8208 | 2.8285 | 2.7537 |  2.8023 |    1.89539e+06 |         17614 | -0.634707 |  1.90552  |   3.44408 |         2.29294e+07 |           0.8382 |            1.3109 |
| 2026-05-02 21:08:00 | 2.8018 | 2.838  | 2.7648 |  2.7826 |    2.13351e+06 |         19245 | -0.702994 |  0.702085 |   5.37757 |         2.29294e+07 |           0.8382 |            1.3109 |
| 2026-05-02 21:09:00 | 2.7821 | 2.8268 | 2.7796 |  2.8044 |    1.32027e+06 |         12931 |  0.78344  | -0.679983 |   7.52655 |         2.29294e+07 |           0.8382 |            1.3109 |
| 2026-05-02 21:10:00 | 2.8038 | 2.8925 | 2.7907 |  2.8703 |    4.00628e+06 |         30836 |  2.34988  |  1.68993  |   8.73996 |         2.31993e+07 |           1.0668 |            1.2953 |
| 2026-05-02 21:11:00 | 2.8705 | 2.9475 | 2.8463 |  2.8973 |    4.0591e+06  |         28159 |  0.940668 |  2.73385  |  13.9862  |         2.31993e+07 |           1.0668 |            1.2953 |
| 2026-05-02 21:12:00 | 2.8969 | 2.933  | 2.8928 |  2.901  |    1.98434e+06 |         13561 |  0.127705 |  3.52211  |  11.7919  |         2.31993e+07 |           1.0668 |            1.2953 |

## Important Caveats
- Only minute-level OHLC was available locally/fetched; no true local 1s LABUSDT bars were found.
- Single-symbol, single-regime scans are overfit-prone. Treat this as mechanism discovery, then validate on other hot listings/pumps.
- The current Hermes symlinks for BWE logs and collector DB point to old `/Volumes/T9/BWE/...` hot paths; actual live data used here is under `/Volumes/T9_HOT`.
- No Binance/OKX order endpoint was called.
