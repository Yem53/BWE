---
type: experiment
status: paper_shadow_signal_only_queued
run_id: v8_5090_paper_shadow_20260504_2347
paper_only: true
live_allowed: false
order_endpoints_allowed: false
---

# V8 5090 Paper Shadow Gate - v8_5090_paper_shadow_20260504_2347

## Decision

Paper gate is open for 20 signal-only candidates: 10 long and 10 short.
No Binance/OKX order endpoint, including testnet/demo, is authorized or called by this package.

## Removed Hard Conditions

- unique_days >= 20/30
- 14d as-of universe

## Active Hard Gates

- raw_mean_pct >= 5
- raw_wr >= 0.75
- monthly >= 300
- sum_return_pct >= 1000
- train_mean_pct > 0 and dev_mean_pct > 0
- final_holdout_mean_pct >= 5 and final_holdout_wr >= 0.75
- traded_symbols >= 50 and traded_over_eligible >= 0.25
- top_symbol_share <= 0.20 and top_5_symbol_share <= 0.50
- coverage_grade in candidate-general/strong-general

## Counts

- Long hard-pass rows in source sweep: 180
- Short hard-pass rows in strict top30 source: 30
- Paper candidates: 10 long + 10 short
- Historical live-aligned replay trades: 7,991

## Live Alignment Contract

- Signal bar: latest completed 5m bar only.
- Entry fill: next 1m open after signal decision time.
- TP: close-confirmed with configured confirm bars.
- SL: touch-immediate using 1m high/low.
- Same 1m bar collision: risk/SL priority.
- Features: as-of/trailing only; no post-signal values.
- Paper mode: signal/account journal only; no order endpoints.

## Files

- [[completion_audit|Completion Audit]]
- [GitHub Strategy Export](github_strategy_export/README.md)
- [paper_candidates_combined.csv](paper_candidates_combined.csv)
- [paper_candidates_long.csv](paper_candidates_long.csv)
- [paper_candidates_short.csv](paper_candidates_short.csv)
- [paper_gate_metrics_summary.csv](paper_gate_metrics_summary.csv)
- [paper_manifest_v8_5090.json](paper_manifest_v8_5090.json)
- [paper_shadow_historical_replay_summary.csv](paper_shadow_historical_replay_summary.csv)
- [paper_shadow_historical_trades.csv](paper_shadow_historical_trades.csv)
- [paper_shadow_state.json](paper_runtime_signal_only/paper_shadow_state.json)
- [paper_journal.csv](paper_runtime_signal_only/paper_journal.csv)
- [historical_replay_journal.csv](paper_runtime_signal_only/historical_replay_journal.csv)
