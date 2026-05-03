#!/usr/bin/env bash
set -euo pipefail

cd /Volumes/T9/BWE_codex

read -r -s -p "BINANCE_DEMO_API_KEY: " BINANCE_DEMO_API_KEY
printf "\n"
read -r -s -p "BINANCE_DEMO_API_SECRET: " BINANCE_DEMO_API_SECRET
printf "\n"
read -r -s -p "BWE_TRADE_TEST_BOT_TOKEN: " BWE_TRADE_TEST_BOT_TOKEN
printf "\n"
read -r -p "BWE_TRADE_TEST_CHAT_ID: " BWE_TRADE_TEST_CHAT_ID

export BINANCE_DEMO_API_KEY
export BINANCE_DEMO_API_SECRET
export BWE_TRADE_TEST_BOT_TOKEN
export BWE_TRADE_TEST_CHAT_ID

python3 paper_test/v6_982b322524d6a28283/scripts/v6_paper_demo_runner.py \
  --mode loop \
  --start-at-end \
  --demo-orders \
  --telegram \
  --notional-usdt "${BWE_PAPER_NOTIONAL_USDT:-10}"
