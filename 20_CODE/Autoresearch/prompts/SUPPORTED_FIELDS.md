# BWE Filter DSL — Supported Fields & Syntax

This document is the **single source of truth** for what `novel_dim` fields
the live filter parser (`bwe_loop_entry_filter.py`) actually understands.

The Round 1 Generator output a lot of conditions like `"pretrend_5m_pos"` and
`"burst_count_5m>=3"` that are NOT in our parser. The parser silently treats
them as pass-through (no narrowing), which makes the archetype indistinguishable
from a no-filter baseline.

**Rule of thumb for LLM team:** if you cannot find the exact field name and
operator pattern in this document, do NOT use it. Pick a SUPPORTED alternative
or omit the condition.

---

## 1. Supported numeric comparisons

Format: `<field><op><value>` — example `oi_change_pct>=15`

Operators: `>=`, `<=`, `>`, `<`, `=`, `==`, `!=`

Numeric values may end with `pct`, `%`, or `bps` suffixes (parser strips them).

### 1.A Direct numeric columns (events parquet)

| Field | Column | Units |
|---|---|---|
| `oi_change_pct` | oi_change_pct | percent |
| `oi_usd` | oi_usd | USD |
| `oi_ratio_pct` | oi_ratio_pct | percent |
| `funding` / `funding_rate` | funding_rate | rate (e.g. 0.0001 = 0.01%) |
| `listing_age_days` | listing_age_days | days |
| `taker_buy_ratio_5m` / `taker_buy_sell_ratio` | taker_buy_sell_volume__buySellRatio | ratio |
| `day_change_pct` | day_change_pct | percent |
| `quote_volume_24h` | quote_volume_24h | USD |
| `move_pct` | move_pct | percent |
| `marketcap` | marketcap | USD |
| `top_trader_position_ratio` | top_trader_long_short_position_ratio__longShortRatio | ratio |
| `top_trader_account_ratio` | top_trader_long_short_account_ratio__longShortRatio | ratio |
| `global_long_short_ratio` | global_long_short_account_ratio__longShortRatio | ratio |
| `global_long_ratio` | global_long_short_account_ratio__longAccount | fraction |
| `global_short_ratio` | global_long_short_account_ratio__shortAccount | fraction |
| `basis` | basis_perpetual__basis | absolute |
| `basis_rate` | basis_perpetual__basisRate | rate |
| `premium_pct` | mark_minus_index_proxy_pct | percent |

### 1.B Special: premium in basis points

`premium_bps>=20` is parsed as `(mark_minus_index_proxy_pct * 100) >= 20`. So
`premium_bps>=20` means the perp is trading 20 bps (=0.20%) above index.

### 1.C Derived from event timestamp (added at load time)

| Field | Values | Source |
|---|---|---|
| `hour_utc` | 0..23 | `(ts_ms // 3,600,000) % 24` |
| `weekday` | string `Mon`, `Tue`, ..., `Sun` | derived |
| `session` | string `US`, `Asian`, `European`, `Other` | UTC hour ranges |

Session UTC ranges (overlapping):
- `US` = hour 13..20
- `Asian` = hour 0..7
- `European` = hour 7..14

### 1.D Categorical equality

| Field | Allowed values |
|---|---|
| `liquidity_bucket` | `low`, `mid`, `high` (data-defined) |
| `marketcap_bucket` / `market_cap_bucket` | `small`, `mid`, `large` (data-defined) |
| `event_type` | `pump`, `crash` |
| `event_family` | (channel-derived) |
| `channel` | `BWE_OI_Price_monitor`, `BWE_pricechange_monitor`, `BWE_Reserved6` |
| `session` | `US`, `Asian`, `European`, `Other` |
| `weekday` | `Mon`, `Tue`, `Wed`, `Thu`, `Fri`, `Sat`, `Sun` |

Examples: `session=US`, `weekday=Sat`, `liquidity_bucket=high`, `event_type=pump`.

---

## 2. Supported flag tokens (no operator, just bare token)

Format: just the bare token, no `=` or `>=`.
Effect: parser computes the percentile threshold from the cached events
DataFrame and applies the corresponding inequality.

| Flag token | Effective condition |
|---|---|
| `top_trader_position_ratio_high` | top_trader_long_short_position_ratio__longShortRatio >= p75 |
| `top_trader_position_ratio_low` / `_dec` | <= p25 |
| `top_trader_account_ratio_high` | account_ratio >= p75 |
| `top_trader_account_ratio_low` | <= p25 |
| `global_long_short_ratio_high` | global longShortRatio >= p75 |
| `global_long_ratio_high` | global longAccount >= p75 |
| `global_long_ratio_extreme` | >= p90 |
| `global_short_ratio_high` | global shortAccount >= p75 |
| `global_short_ratio_extreme` | >= p90 |
| `volume_pct_top_decile` | quote_volume_24h >= p90 |
| `volume_pct_above_p75` | >= p75 |
| `volume_pct_below_p25` | <= p25 |
| `funding_pct_top_decile` | funding_rate >= p90 |
| `oi_pct_top_decile` | oi_change_pct >= p90 |
| `funding_abs_high` | abs(funding_rate) >= p75 |
| `funding_abs_extreme` | abs(funding_rate) >= p90 |
| `premium_extreme` | abs(mark_minus_index_proxy_pct) >= p90 |

---

## 3. NOT supported (will be silently skipped — pass-through)

Do NOT use these. They will be parsed but treated as no-op, making your
archetype identical to a no-filter version.

- `pretrend_3m_*`, `pretrend_5m_*`, `pretrend_15m_*`, `pretrend_30m_*`,
  `pretrend_2h_*` — needs rolling-window pre-event computation
- `burst_count_5m`, `burst_seq_5m`, `burst_density_*` — cross-event chain
  analysis not implemented
- `btc_24h_pct`, `btc_correlation_30d`, `btc_atr_*`, `btc_dom_*`,
  `btc_realized_vol_*` — needs external BTC daily/hourly data join
- `near_macro_event`, `no_fed_in_24h`, `no_cpi_in_24h` — needs macro
  calendar data
- `basis_widening`, `basis_narrowing`, `oi_change_5m_pos`,
  `oi_change_5m_neg`, `oi_continues_rising`, `oi_recovers_within_60s` —
  needs delta computation between consecutive events for same symbol
- `book_imbalance_*`, `aggressive_buy_*`, `aggressive_sell_*`, `iceberg`,
  `aggregator_active`, `spread_bps`, `depth_rank` — needs L2 order book data
- `volume_2x_avg`, `volume_5x_baseline`, `volume_below_baseline` — needs
  per-symbol baseline; use `volume_pct_top_decile` etc. instead
- `realized_vol_30m`, `regime_*`, `alt_season`, `eth_dominance_*` —
  external regime data
- `ema_*`, `rsi_*`, `atr_*` — indicator computation not implemented
- `sector`, `symbol_blacklist`, `symbol_rotation`, `geographic_*` —
  symbol metadata not in events parquet
- Cross-channel patterns (`pc_then_oi_*`, `oi_then_pc_*`,
  `all_three_*`, `confirm_within_*`, `multi_signal_*`) — orchestration
  layer, not events filter

---

## 4. Skipped as "parameters" (these belong to entry/exit search space, not filter)

These look like conditions but are not — they describe variants the
backtest engine sweeps automatically. Do NOT include in `novel_dim`.

- `delay_seconds=*`, `fixed_hold_minutes=*`, `max_hold=*`
- `side_signal=*`, `side_event=*`, `side_change=*` (use `event_type=` for
  filter; side itself comes from the entry archetype's `side` field)
- `tp_pct=*`, `sl_pct=*`, `tp1=*`, `tp2=*`, `trail=*`, `trail_pct=*`,
  `trail_atr=*`, `be_trigger=*`, `be_at_*`, `hard_stop=*`, `ladder*`
- `size=*`, `max_open_positions=*`, `max_per_*`, `max_trades_per_day`,
  `daily_loss_stop`, `cooldown_*`

---

## 5. Examples — DOs and DON'Ts for Generator output

### ✅ Good (will actually filter events)

```json
"novel_dim": ["oi_change_pct>=15", "premium_bps>=20", "session=US"]
```

```json
"novel_dim": ["taker_buy_ratio_5m>=0.65", "global_short_ratio_high"]
```

```json
"novel_dim": ["funding<=-0.05", "event_type=crash", "liquidity_bucket=high"]
```

```json
"novel_dim": ["top_trader_position_ratio_high", "weekday=Mon", "oi_change_pct>=10"]
```

### ❌ Bad (will silently fall through to no-filter, archetype becomes indistinguishable)

```json
"novel_dim": ["pretrend_5m_pos", "burst_count_5m>=2"]   // both unsupported
```

```json
"novel_dim": ["btc_24h_pct>=0", "near_macro_event"]   // both unsupported
```

```json
"novel_dim": ["premium_bps", "funding", "oi_change_pct"]   // bare field names, no operators — parser can't infer threshold
```

```json
"novel_dim": ["volume_2x_avg", "spread_bps<=5"]   // unsupported aggregations
```

---

## 6. How the LLM team should use this

**Generator**: every condition you propose MUST appear verbatim (or with
allowed value substitution) in section 1, 1.B, 1.C, 1.D, or 2 above. If
you want to express a domain hypothesis that needs an unsupported field
(e.g. burst_count), find the closest supported proxy or omit it.

**Quant Analyst**: validate by mentally parsing each `novel_dim` against
this doc. Flag in `uncomputable_fields` anything that doesn't appear
here. Reject if more than half the conditions are uncomputable.

**Synthesizer**: do NOT accept any archetype where ALL `novel_dim`
conditions fall through (they would equal a no-filter baseline and
produce duplicate scores in the loop).

**Risk Critic**: still scan for future-function leakage even within
supported fields (e.g. `mark_minus_index_proxy_pct` is computed at T0
from 1m bars — confirm the timestamp alignment).
