# v6_982b322524d6a28283 Paper/Demo Runner

Codex-owned runner for the strict-passing long strategy.

Write scope:

- Writes only under `/Volumes/T9/BWE_codex/paper_test/v6_982b322524d6a28283`.
- Reads BWE posts from `/Volumes/T9_HOT/bwe_logs/bwe_matrix_posts.jsonl`.
- Reads local Binance collector DB from `/Volumes/T9_HOT/binance_collectors_runtime/binance_futures_1m.sqlite3`.
- Does not modify `/Volumes/T9/BWE` or Obsidian.

Trigger:

- BWE post, not full-market scanner.
- Pump only.
- Entry delay: 180 seconds after BWE event timestamp.
- Market cap must be present and `<= 71M`; missing market cap is skipped.
- Top trader account long/short ratio and global account long/short ratio are read from the local SQLite feature tables at entry due time.

Exit:

- Long failed-continuation state machine.
- 1m high/low stop-first replay.
- Initial stop: `-5%`.
- At 10 minutes, if close return is worse than `-1.75%`, exit as failed continuation.
- Otherwise time exit at 240 minutes.

Secrets:

- Never put keys or tokens in files.
- Binance demo/testnet credentials are read from `BINANCE_DEMO_API_KEY` and `BINANCE_DEMO_API_SECRET`, with `BINANCE_TESTNET_API_KEY` and `BINANCE_TESTNET_SECRET` as fallback names.
- Telegram token/chat are read from `BWE_TRADE_TEST_BOT_TOKEN` and `BWE_TRADE_TEST_CHAT_ID`, with `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as fallback names.

Commands:

```bash
cd /Volumes/T9/BWE_codex

# Component tests
python3 paper_test/v6_982b322524d6a28283/tests/test_v6_paper_demo_runner.py

# Initialize cursor at current end of BWE stream, signal-only, no orders
python3 paper_test/v6_982b322524d6a28283/scripts/v6_paper_demo_runner.py --mode once --start-at-end

# Send Telegram test after env vars are set and chat_id is known
python3 paper_test/v6_982b322524d6a28283/scripts/v6_paper_demo_runner.py --telegram-test

# Discover chat_id after sending /start to the bot
python3 paper_test/v6_982b322524d6a28283/scripts/v6_paper_demo_runner.py --discover-telegram-chat-id

# Real Binance futures demo/testnet order mode
python3 paper_test/v6_982b322524d6a28283/scripts/v6_paper_demo_runner.py --mode loop --start-at-end --demo-orders --telegram --notional-usdt 10
```

The runner will refuse demo order mode if Binance credentials are not present in environment variables.
