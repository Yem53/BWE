#!/usr/bin/env bash
set -euo pipefail
cd /Users/ye/Desktop/GitHub/Autoresearch

# Requires: codex login with ChatGPT/Codex subscription first.
# This is intentionally high-permission because the user requested it, but the prompt still forbids
# live trading, secrets, orders, launchd restarts, and live config edits.
codex exec \
  --dangerously-bypass-approvals-and-sandbox \
  "$(cat prompts/codex_bwe_autoresearch_round1.md)"
