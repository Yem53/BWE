#!/usr/bin/env zsh
set -euo pipefail

ROOT="/Volumes/T9/BWE_codex/paper_test/v6_multi_8"
STATE_DIR="$ROOT/runtime"
PID_FILE="$STATE_DIR/multi_runner.pid"
LOG_FILE="$STATE_DIR/logs/multi_runner.log"
TMUX_BIN="${TMUX_BIN:-/Users/ye/.local/bin/tmux}"
TMUX_SESSION="bwe_multi8_paper"

if "$TMUX_BIN" has-session -t "$TMUX_SESSION" 2>/dev/null; then
  pid="$("$TMUX_BIN" list-panes -t "$TMUX_SESSION" -F '#{pane_pid}' | head -1)"
  echo "tmux=running session=$TMUX_SESSION pid=${pid:-pending}"
elif [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  echo "tmux=not_running session=$TMUX_SESSION"
else
  pid=""
  echo "tmux=not_running session=$TMUX_SESSION"
fi

if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
  echo "process=running pid=$pid"
  ps -p "$pid" -o pid=,stat=,etime=,command=
else
  echo "process=not_running pid=${pid:-none}"
fi

python3 - <<'PY'
import json
from pathlib import Path

state_path = Path("/Volumes/T9/BWE_codex/paper_test/v6_multi_8/runtime/state.json")
if not state_path.exists():
    print("state=missing")
else:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    print(
        "state="
        + json.dumps(
            {
                "events": state.get("total_events_parsed", 0),
                "pending": len(state.get("pending_entries") or []),
                "open": len(state.get("open_positions") or []),
                "closed": len(state.get("closed_positions") or []),
                "api_failures": state.get("api_failures", 0),
                "api_fallback": state.get("api_fallback_count", 0),
                "orders_ok": int(state.get("demo_orders_placed") or 0)
                + int(state.get("demo_close_orders_placed") or 0),
                "orders_failed": int(state.get("demo_orders_failed") or 0)
                + int(state.get("demo_close_orders_failed") or 0),
                "notifications": state.get("notifications_sent", 0),
                "stale_signals": (state.get("skip_reasons") or {}).get("skip_scanner_stale_bar", 0),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
PY

if [[ -f "$LOG_FILE" ]]; then
  echo "log_tail:"
  tail -n 8 "$LOG_FILE"
fi
