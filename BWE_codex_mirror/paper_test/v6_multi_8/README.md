# v6 Multi-9 Paper/Demo Runner

Codex-owned paper runner for 9 candidate strategies: the original `v6_982b322524d6a28283` plus 8 added candidates. It now tracks 5 long BWE-triggered strategies and 4 short scanner strategies.

## Guardrails

- Writes only under `/Volumes/T9/BWE_codex/paper_test/v6_multi_8`.
- Entry fill uses Binance mark/testnet fill price, never future 1m close.
- Long pending entries expire if they cannot be processed close to due time.
- Scanner signals require completed local 1m bars and reject stale bars.
- Long BWE entries use local DB first, then Binance public REST fallback only when required entry features are missing or stale.
- Indicators are read at or before decision time.
- PnL is recomputed from prices with side-specific formulas.
- Short trailing exits are stop-first inside each 1m bar.
- Testnet order ACKs are written to `runtime/order_journal.jsonl` for crash recovery.
- Runtime enforces one open position per symbol plus same-strategy/same-symbol cooldown to keep paper/testnet exposure aligned.

## Commands

```bash
cd /Volumes/T9/BWE_codex

python3 paper_test/v6_multi_8/tests/test_multi_paper_runner.py

paper_test/v6_multi_8/scripts/start_multi_runner.sh
paper_test/v6_multi_8/scripts/status_multi_runner.sh
paper_test/v6_multi_8/scripts/stop_multi_runner.sh
```

Default heartbeat cadence is 1 hour. `start_multi_runner.sh` still sends one immediate heartbeat on restart so Telegram confirms the active table.

Hybrid fallback defaults:

- Enabled by default: `enable_binance_fallback=true`.
- REST timeout: `fallback_timeout_seconds=5`.
- 24h ticker freshness guard: `ticker_max_age_ms=600000`.
- Fallback covers long-entry public features only: top trader account ratio, global account ratio, top trader position ratio, 24h quote volume, and mark-price freshness.
- Fallback does not replace the fill model: entry still uses real-time mark price and then demo/testnet market-order `avgPrice` when available.

Runtime state:

- `runtime/state.json`
- `runtime/trades.jsonl`
- `runtime/events.jsonl`
- `runtime/decisions.jsonl`
- `runtime/errors.jsonl`
- `runtime/order_journal.jsonl`
- `runtime/notifications.jsonl`
- `runtime/logs/multi_runner.log`

Secrets are loaded from `secrets.env`, which is intentionally not linked or printed.
