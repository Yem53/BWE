#!/usr/bin/env zsh
set -euo pipefail

ROOT="/Volumes/T9/BWE_codex"
RUN_ROOT="$ROOT/paper_test/v6_multi_8"
STATE_DIR="$RUN_ROOT/runtime"
LOG_DIR="$STATE_DIR/logs"
PID_FILE="$STATE_DIR/multi_runner.pid"
RUNNER="$RUN_ROOT/scripts/multi_paper_runner.py"
SECRET_ENV="$RUN_ROOT/secrets.env"
PYTHON="${PYTHON:-/Users/ye/.homebrew/bin/python3}"
TMUX_BIN="${TMUX_BIN:-/Users/ye/.local/bin/tmux}"
TMUX_SESSION="bwe_multi8_paper"

mkdir -p "$LOG_DIR"

if [[ ! -x "$TMUX_BIN" ]]; then
  echo "missing_tmux=$TMUX_BIN"
  exit 2
fi

if "$TMUX_BIN" has-session -t "$TMUX_SESSION" 2>/dev/null; then
  pid="$("$TMUX_BIN" list-panes -t "$TMUX_SESSION" -F '#{pane_pid}' | head -1)"
  echo "$pid" > "$PID_FILE"
  echo "already_running session=$TMUX_SESSION pid=$pid"
  exit 0
fi

"$TMUX_BIN" new-session -d -s "$TMUX_SESSION" \
  "$PYTHON -u $RUNNER --mode loop --start-at-end --demo-orders --telegram --heartbeat-now --heartbeat-seconds ${HEARTBEAT_SECONDS:-3600} --poll-seconds ${POLL_SECONDS:-15} --scanner-seconds ${SCANNER_SECONDS:-60} --scanner-max-bar-age-seconds ${SCANNER_MAX_BAR_AGE_SECONDS:-180} --max-entry-lag-seconds ${MAX_ENTRY_LAG_SECONDS:-45} --one-position-per-symbol --same-strategy-symbol-cooldown-min ${SAME_STRATEGY_SYMBOL_COOLDOWN_MIN:-60} --enable-binance-fallback --fallback-timeout-seconds ${FALLBACK_TIMEOUT_SECONDS:-5} --ticker-max-age-ms ${TICKER_MAX_AGE_MS:-600000} --secret-env $SECRET_ENV --state-dir $STATE_DIR >> $LOG_DIR/multi_runner.log 2>&1"

sleep 2
pid="$("$TMUX_BIN" list-panes -t "$TMUX_SESSION" -F '#{pane_pid}' | head -1)"
echo "$pid" > "$PID_FILE"
echo "started session=$TMUX_SESSION pid=$pid log=$LOG_DIR/multi_runner.log"
