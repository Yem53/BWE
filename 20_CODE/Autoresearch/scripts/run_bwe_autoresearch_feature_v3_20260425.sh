#!/bin/zsh
set -euo pipefail

/Users/ye/.hermes/runtime-venv/bin/python3 -m bwe_autoresearch.feature_v3 \
  --feature-dir /Users/ye/.hermes/research/bwe_three_channel_fullrun3/binance_event_features_20260425_30d \
  --out-dir /Users/ye/.hermes/research/bwe_autoresearch_feature_v3_20260425 \
  --round2-manifest /Users/ye/.hermes/research/bwe_deep_autoresearch_20260425/round2_post/paper_experiment_manifest_round2.json
