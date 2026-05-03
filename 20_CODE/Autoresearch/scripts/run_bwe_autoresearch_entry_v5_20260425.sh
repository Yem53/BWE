#!/usr/bin/env bash
set -euo pipefail

cd /Users/ye/Desktop/Github/Autoresearch
/Users/ye/.hermes/runtime-venv/bin/python3 -m bwe_autoresearch.feature_v5 \
  --package-dir /Users/ye/Downloads/bwe_entry_research_v5_package \
  --feature-dir /Users/ye/.hermes/research/bwe_three_channel_fullrun3/binance_event_features_20260425_30d \
  --out-dir /Users/ye/.hermes/research/bwe_autoresearch_entry_v5_20260425 \
  --max-candidates-per-template 15000 \
  --score-limit 6000 \
  --medium-top 1000 \
  --deep-top 300 \
  --max-manifest-items 30
