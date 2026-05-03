# Recent Yaobi Volatility Scan

Date: 2026-05-02
Scope: read-only scan of local BWE market database and BWE post log.

## Data Sources

- Kline DB: `/Volumes/T9_HOT/binance_collectors_runtime/binance_futures_1m.sqlite3`
- Tables: `klines_1m`, `symbol_features`, `ticker_24h`
- BWE post log: `/Volumes/T9_HOT/bwe_logs/bwe_matrix_posts.jsonl`

No BWE or Obsidian files were modified.

## Method

Window: latest available 1m kline minus 24h.

Filter:

- `interval = '1m'`
- at least 180 bars in the 24h window
- 24h high/low range at least 12%

Behavior metrics:

- `range24_pct`: 24h high/low range
- `range3h_pct`: last 3h high/low range
- `pump5_cnt` / `dump5_cnt`: count of 5m close-to-close moves >= +3% / <= -3%
- `pump15_cnt` / `dump15_cnt`: count of 15m close-to-close moves >= +8% / <= -8%
- `one_min_2pct_cnt`: count of 1m candles with high/low range >= 2%
- `yaobi_score`, `n_waves_14d`, `lifecycle`, `reaction`: from `symbol_features`

## Strongest Candidates

| Rank | Symbol | Why It Matters |
|---:|---|---|
| 1 | `LABUSDT` | Extreme outlier: 24h range 316.98%, 3h range 132.95%, ret24 +304.73%, quote volume 3134M, 308 pump5 and 197 dump5 events. BWE log had 137 recent mentions across price, OI, and Reserved6. |
| 2 | `TAGUSDT` | 24h range 135.35%, ret24 +43.56%, 102 pump5 and 89 dump5 events, high intraday oscillation. BWE log had 5 recent price triggers. |
| 3 | `UBUSDT` | 24h range 62.73%, ret24 +31.62%, quote volume 579M, 110 pump5 and 96 dump5 events. BWE log had 71 recent mentions including OI and Reserved6. |
| 4 | `BSBUSDT` | 24h range 61.89%, ret24 +39.28%, yaobi_score 75.93, 52 pump5 and 29 dump5 events. Strong market-only candidate in this window. |
| 5 | `BIOUSDT` | 24h range 65.75%, ret24 +42.67%, quote volume 499M. BWE log had 4 recent mentions including OI monitor. |
| 6 | `XNYUSDT` | 24h range 64.78%, ret24 +46.09%, sustained mean-revert profile, but BWE log did not show strong recent trigger count in the checked 24h post window. |
| 7 | `SKYAIUSDT` | 24h range 54.38%, ret24 +43.61%, quote volume 485M, yaobi_score 75.65, BWE log had 1 recent trigger. |
| 8 | `BUSDT` | 24h range 40.20%, ret24 +20.84%, quote volume 550M, BWE log had 5 recent price triggers. |
| 9 | `ORDIUSDT` | 24h range 44.97%, ret24 +28.41%, quote volume 271M, BWE log had 8 recent mentions, mostly OI monitor. |
| 10 | `NAORISUSDT` | 24h range 44.28%, ret24 +29.03%, sustained mean-revert profile, BWE log had 1 recent trigger. |

## Other Watchlist Names

- `AIOTUSDT`: yaobi_score 84.30, 77 waves/14d, 24h range 31.23%, ret24 -13.36%, 37 pump5 and 25 dump5.
- `KNCUSDT`: 24h range 40.79%, ret24 +23.53%, BWE log had 3 recent mentions.
- `TACUSDT`: 24h range 45.33%, ret24 +19.13%, 23 pump5 and 25 dump5.
- `PLAYUSDT`: yaobi_score 77.94, 24h range 30.35%, BWE log had 4 recent price triggers.
- `ZEREBROUSDT`: 24h range 28.39%, ret24 -18.04%, BWE log had 2 recent triggers.

## Interpretation

Best immediate "妖币 with live behavior" target is `LABUSDT`. It is not just a 24h gainer; it has repeated fast pumps and dumps, high quote volume, high BWE trigger density, OI monitor presence, and a Reserved6 extreme-move trigger.

Best next tier:

- `UBUSDT`: strong BWE-confirmed oscillation and OI involvement.
- `TAGUSDT`: violent fast oscillation, but fewer BWE triggers than LAB/UB.
- `BIOUSDT`: strong 24h market movement plus OI mentions.
- `BSBUSDT` / `SKYAIUSDT`: strong market movement, but weaker recent BWE confirmation in the checked post window.

## Caveats

- This is not a live-trade recommendation.
- BWE post log latest timestamp in the checked file was `2026-05-02T17:10:14Z`, while 1m kline data continued later, so BWE trigger counts may lag the kline window.
- The scan intentionally does not define "妖币" by market cap. It uses behavior: repeated waves, intraday range, fast pump/dump counts, lifecycle, reaction, and BWE trigger density.

