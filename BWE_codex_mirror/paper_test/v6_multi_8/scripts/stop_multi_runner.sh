#!/usr/bin/env zsh
set -euo pipefail

STATE_DIR="/Volumes/T9/BWE_codex/paper_test/v6_multi_8/runtime"
PID_FILE="$STATE_DIR/multi_runner.pid"
TMUX_BIN="${TMUX_BIN:-/Users/ye/.local/bin/tmux}"
TMUX_SESSION="bwe_multi8_paper"

if "$TMUX_BIN" has-session -t "$TMUX_SESSION" 2>/dev/null; then
  "$TMUX_BIN" kill-session -t "$TMUX_SESSION"
  echo "stopped session=$TMUX_SESSION"
  exit 0
fi

if [[ ! -f "$PID_FILE" ]]; then
  echo "not_running no_pid_file"
  exit 0
fi

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ -z "${pid:-}" ]] || ! kill -0 "$pid" 2>/dev/null; then
  echo "not_running stale_pid=${pid:-}"
  exit 0
fi

kill "$pid"
echo "stopped pid=$pid"
