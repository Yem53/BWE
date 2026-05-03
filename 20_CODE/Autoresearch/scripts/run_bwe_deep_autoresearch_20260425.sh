#!/bin/zsh
set -euo pipefail

/Users/ye/.hermes/runtime-venv/bin/python3 -m bwe_autoresearch.deep_autoresearch \
  --forward-parquet /Users/ye/.hermes/research/bwe_three_channel_fullrun3/forward.parquet \
  --hourly-parquet /Users/ye/.hermes/research/bwe_three_channel_fullrun3/event_hourly_2h_pre_48h_post.parquet \
  --path-5m-parquet /Users/ye/.hermes/research/bwe_live_exit_optimization_run5/all4_event_5m_72h.parquet \
  --out-dir /Users/ye/.hermes/research/bwe_deep_autoresearch_20260425 \
  --fallback-out-dir /Users/ye/Desktop/Github/Autoresearch/runs/bwe_deep_autoresearch_20260425 \
  --stage-c-max-seconds 180
