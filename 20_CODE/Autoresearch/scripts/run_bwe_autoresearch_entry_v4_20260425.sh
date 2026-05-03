#!/usr/bin/env bash
set -euo pipefail

cd /Users/ye/Desktop/Github/Autoresearch
/Users/ye/.hermes/runtime-venv/bin/python3 -m bwe_autoresearch.feature_v4 \
  --feature-dir /Users/ye/.hermes/research/bwe_three_channel_fullrun3/binance_event_features_20260425_30d \
  --out-dir /Users/ye/.hermes/research/bwe_autoresearch_entry_v4_20260425 \
  --max-rules-per-context 180 \
  --top-rules 180 \
  --top-diagnostics 40 \
  --max-manifest-items 10
