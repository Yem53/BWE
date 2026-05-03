# BWE Binance Event Feature Backfill

- events: `7317`
- unique_symbols: `327`
- range_utc: `2026-03-21 15:59:09+00:00` -> `2026-04-20 15:30:36+00:00`
- raw_rows: `{"open_interest_hist": 746037, "global_long_short_account_ratio": 746041, "top_trader_long_short_account_ratio": 745035, "top_trader_long_short_position_ratio": 744535, "taker_buy_sell_volume": 744417, "basis_perpetual": 796406}`
- funding_rows: `19050`
- local_kline_rows: `0`

## Feature coverage
- basis_perpetual__age_ms: 98.565%
- basis_perpetual__basis: 98.565%
- basis_perpetual__basisRate: 98.565%
- basis_perpetual__futuresPrice: 98.565%
- basis_perpetual__indexPrice: 98.565%
- funding_age_ms: 99.9863%
- funding_mark_price: 99.9863%
- funding_rate: 99.9863%
- funding_ts_ms: 99.9863%
- global_long_short_account_ratio__age_ms: 91.9366%
- global_long_short_account_ratio__longAccount: 91.9366%
- global_long_short_account_ratio__longShortRatio: 91.9366%
- global_long_short_account_ratio__shortAccount: 91.9366%
- open_interest_hist__CMCCirculatingSupply: 91.9366%
- open_interest_hist__age_ms: 91.9366%
- open_interest_hist__sumOpenInterest: 91.9366%
- open_interest_hist__sumOpenInterestValue: 91.9366%
- taker_buy_sell_volume__age_ms: 91.8819%
- taker_buy_sell_volume__buySellRatio: 91.8819%
- taker_buy_sell_volume__buyVol: 91.8819%
- taker_buy_sell_volume__sellVol: 91.8819%
- top_trader_long_short_account_ratio__age_ms: 91.9093%
- top_trader_long_short_account_ratio__longAccount: 91.9093%
- top_trader_long_short_account_ratio__longShortRatio: 91.9093%
- top_trader_long_short_account_ratio__shortAccount: 91.9093%
- top_trader_long_short_position_ratio__age_ms: 91.8819%
- top_trader_long_short_position_ratio__longAccount: 91.8819%
- top_trader_long_short_position_ratio__longShortRatio: 91.8819%
- top_trader_long_short_position_ratio__shortAccount: 91.8819%

## Mark/Premium kline coverage
- mark_1m_open_time_ms: 100.0%
- mark_1m_open: 100.0%
- mark_1m_high: 100.0%
- mark_1m_low: 100.0%
- mark_1m_close: 100.0%
- mark_1m_close_time_ms: 100.0%
- mark_1m_age_ms: 100.0%
- premium_1m_open_time_ms: 100.0%
- premium_1m_open: 100.0%
- premium_1m_high: 100.0%
- premium_1m_low: 100.0%
- premium_1m_close: 100.0%
- premium_1m_close_time_ms: 100.0%
- premium_1m_age_ms: 100.0%
- mark_minus_index_proxy_pct: 98.565%
