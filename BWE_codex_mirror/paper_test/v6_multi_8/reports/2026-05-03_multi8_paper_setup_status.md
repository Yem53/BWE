# Multi-9 Paper Setup Status

Created: 2026-05-03
Scope: `/Volumes/T9/BWE_codex/paper_test/v6_multi_8`

## Status

The 9-strategy paper/demo runner is implemented under Codex write scope only.
It is launched in a detached `tmux` session named `bwe_multi8_paper` because
plain `nohup` children were reclaimed after the Codex command session ended.

Strategies:

- Long: `PS0_V6_982_ORIG`, `L1_TAKER_TOP_QV`, `L2_MOVE_TOP_300S`, `L3_MOVE7_GLOBAL`, `L4_LOW_QV_TOP`
- Short: `S1_COMBO_MEAN9`, `S2_COMBO_FREQ`, `S3_FAILED_WICK`, `S4_PULLBACK`

## Drift Controls Applied

- Entry does not use 1m close as fill.
- Long entries expire if due-time processing is missed.
- Scanner bars require completed and fresh 1m data.
- Short PnL uses `(entry - exit) / entry`.
- Short adaptive trailing is stop-first and does not use a same-bar low to arm a same-bar high exit.
- Testnet open/close ACKs are journaled before relying on in-memory state.
- Open/close order failures are included in the Telegram heartbeat.
- Heartbeat cadence is 1 hour after the restart confirmation heartbeat.
- One-position-per-symbol and same-strategy/same-symbol cooldown are enforced in the runner, not only documented in config.
- Hybrid entry-feature fallback is enabled for long BWE entries: DB remains primary, but stale/missing public fields are refreshed from Binance REST before the entry decision.

## Files

- `config/strategies_9.json`
- `scripts/multi_paper_runner.py`
- `scripts/start_multi_runner.sh`
- `scripts/status_multi_runner.sh`
- `scripts/stop_multi_runner.sh`
- `tests/test_multi_paper_runner.py`
- `runtime/state.json`
- `runtime/logs/multi_runner.log`

## Verification

- Unit tests: `python3 paper_test/v6_multi_8/tests/test_multi_paper_runner.py`
- Compile check: `python3 -m py_compile ...`
- Public REST fallback smoke: BTCUSDT returned top/global/top-position ratios, 24h quote volume, and mark freshness.
- Dry run: `--mode once --start-at-end --heartbeat-now`
- Telegram heartbeat: sent through the configured bot, with the 9-row strategy table.
- Process status: `scripts/status_multi_runner.sh` reports `tmux=running`.

## Operator Note

Scanner shorts deliberately reject stale local 1m bars. If the Binance 1m collector lags, the runner should stay flat rather than fabricate current-market signals from old candles.
