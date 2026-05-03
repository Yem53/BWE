# Paper/Demo Setup Status

Generated: 2026-05-03
Updated: 2026-05-02 23:32 EDT

## Strategy

- Strategy: `v6_982b322524d6a28283`
- Side: long
- Trigger: BWE post stream, pump event, not full-market scanner
- Entry delay: 180 seconds
- Exit: failed-continuation, 1m high/low stop-first
- Status: paper only, live not allowed

## Implemented Files

- `paper_test/v6_982b322524d6a28283/scripts/v6_paper_demo_runner.py`
- `paper_test/v6_982b322524d6a28283/scripts/run_with_secret_prompts.sh`
- `paper_test/v6_982b322524d6a28283/tests/test_v6_paper_demo_runner.py`
- `paper_test/v6_982b322524d6a28283/config/strategy_v6_982b322524d6a28283.json`
- `paper_test/v6_982b322524d6a28283/runtime/state.json`
- `paper_test/v6_982b322524d6a28283/runtime/notifications.jsonl`

## Verification

- Component tests: pass
- Python compile check: pass
- Signal-only dry-run initialization: pass
- Binance public mark price smoke check: pass
- Codex vault sync: pass

## Current Runtime State

The runner was initialized at the current end of the BWE post stream in signal-only mode:

- Pending entries: `0`
- Open positions: `0`
- Closed positions: `0`
- Demo orders placed: `0`
- Demo orders failed: `0`

No Binance order endpoint was called during setup because credentials are not present in environment variables.

Telegram status:

- Bot API `getMe`: ok
- Webhook: not set
- Chat discovery: ok after user sent a message to the bot
- Runner Telegram test: `telegram_test_sent=true`
- Token persistence: no token written to files

## Required Before Demo Orders

Use environment variables or the interactive prompt script. Do not write secrets to files.

Required values:

- `BINANCE_DEMO_API_KEY`
- `BINANCE_DEMO_API_SECRET`
- `BWE_TRADE_TEST_BOT_TOKEN`
- `BWE_TRADE_TEST_CHAT_ID`

If chat id is unknown, send `/start` to the bot first, then run the runner with `--discover-telegram-chat-id` after the Telegram token is present in the environment.

## Safety Gates

- Missing market cap is skipped.
- Missing or stale top/global long-short ratios are skipped.
- Demo order mode uses Binance futures demo/testnet endpoint only.
- Mainnet/live order endpoints are not used.
- No secrets are persisted in files.
