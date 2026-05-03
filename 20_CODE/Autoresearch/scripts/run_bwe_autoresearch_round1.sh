#!/usr/bin/env bash
set -euo pipefail
cd /Users/ye/Desktop/GitHub/Autoresearch
OUT_DIR="${1:-/Users/ye/.hermes/research/bwe_autoresearch_sandbox_20260424/local_round1}"
/Users/ye/.hermes/runtime-venv/bin/python3 -m bwe_autoresearch.discovery \
  --forward-parquet /Users/ye/.hermes/research/bwe_three_channel_fullrun3/forward.parquet \
  --out-dir "$OUT_DIR" \
  --max-hypotheses 120 \
  --min-sample 60
