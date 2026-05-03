# Codex Task #0 — Find Historical Max Forward Return for TP Cap Empirical

## Mission

Read `/Volumes/T9/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows.parquet` (71 MB) and compute the empirical distribution of **max forward return per event** to inform Round 4 TP grid upper bound.

This is for the BWE Autoresearch project's Round 4 hygiene phase. The user trades small-cap manipulator-driven coins ("妖币") and needs to know: across the historical event windows, how big are the typical max-favorable excursions, so we can size the TP grid (currently capped at 500%).

## Hard safety rules

- **Read-only on the parquet file.** Do not modify.
- Do not call any exchange API / Binance / OKX / order endpoints.
- Do not read or print secrets, API keys, .env files.
- Do not touch `/Users/ye/.hermes/` (that's the live trading bot — out of scope).
- Write outputs **only** under `/Volumes/T9/BWE/40_EXPERIMENTS/round4/00_planning/`.
- This is a research analysis task, not a trading task.

## Inputs

- **Primary**: `/Volumes/T9/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows.parquet` (71 MB)
- **Schema**: Unknown — discover it yourself with `pyarrow.parquet.read_schema()` or `polars.scan_parquet().collect_schema()`.
- **Reference context** (read-only, optional): `/Volumes/T9/BWE/40_EXPERIMENTS/morning_brief_latest.md` for Round 3 vocabulary

## What to compute

Per-event, within the forward window from `entry_price`:

1. `max_fav_pct` = (max(high) over forward window − entry_price) / entry_price × 100
2. Same for backward window if schema includes pre-entry bars (label as `max_pre_pct`)
3. Aggregate distribution across all events:
   - count of events
   - mean / median / p25 / p50 / p75 / p90 / p95 / p99 / p99.9 / max
   - distribution by hold horizon if schema has multiple horizons (60min vs 24h vs 72h etc)
   - distribution by channel if schema has channel column (`BWE_OI_Price_monitor`, `BWE_pricechange_monitor`, `BWE_Reserved6`)

## Output (mandatory)

Write `/Volumes/T9/BWE/40_EXPERIMENTS/round4/00_planning/02_max_forward_return.md` with these sections:

```markdown
# Round 4 D1 Empirical — Historical Max Forward Return

## 1. Parquet Schema
[full pyarrow / polars schema dump]
- Total rows: N
- Distinct events: N
- Hold horizons: [list]
- Channels (if present): [list]

## 2. Distribution of max_fav_pct (all events)
| Stat | Value (%) |
| count | ... |
| mean  | ... |
| median| ... |
| p75   | ... |
| p90   | ... |
| p95   | ... |
| p99   | ... |
| p99.9 | ... |
| max   | ... |

## 3. Per-channel breakdown (if applicable)
[table per channel × hold horizon]

## 4. TP cap recommendation
Based on the p99 / p99.9 / max values, recommend Round 4 TP grid upper bound.
Current Round 4 plan: TP grid `np.geomspace(0.5, 500.0, 60)`.
- If p99 < 200%, current 500% cap is generous (OK)
- If p99 ≥ 500%, recommend extending grid up to p99.5 × 1.3
- Output: ≤200 words conclusion in 中文

## 5. Sanity checks done
- [list any data quality issues found]
```

If the parquet doesn't contain forward-return data directly (e.g. it's just kline tuples), reconstruct from OHLC: for each event, find rows where `is_event=true` (or equivalent), then compute max(high) over the next N bars.

## Environment notes

- Mac, Python 3.12 (Homebrew Python — PEP 668 externally-managed)
- pyarrow / polars / pandas may not be installed system-wide
- **You can use `uv pip install --system pyarrow polars` OR a venv in `/tmp/codex_round4_venv/` OR `pip install --break-system-packages` if needed**
- Working dir: `/Volumes/T9/BWE/40_EXPERIMENTS/round4/`

## Success criteria

1. `02_max_forward_return.md` exists with all 5 sections filled
2. Numbers are concrete (not "N/A" or "unknown")
3. TP cap recommendation is a specific %  (e.g. "建议保持 500% 不变" or "建议上调到 800%")
4. No live trading paths or secrets touched

## Output format for your final response

Concise 中文, 4 sections:
- 完成情况：file written, schema discovered, N events analyzed
- 关键发现：max_fav_pct p50 / p99 / max
- TP cap 建议：具体百分比
- 是否触动 live：确认 `~/.hermes/` 未触动
