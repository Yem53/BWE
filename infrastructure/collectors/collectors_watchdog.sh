#!/bin/bash
# Watchdog — keeps Binance collectors alive across VPN toggles, Mac sleep, etc.
#
# Run via cron every 1 minute:
#   * * * * * /Users/ye/.hermes/scripts/collectors_watchdog.sh > /dev/null 2>&1
#
# Self-healing layers:
#   1. Process death: if process not running → relaunch
#   2. Stale data: if last DB write > THRESHOLD min ago AND process appears
#      hung (connectivity ok but no progress) → kill + relaunch
#   3. VPN-down: if internet/Binance unreachable → log + skip restart
#      (let existing collectors retry-loop until VPN back)

set +e

PYTHON=/Users/ye/.hermes/runtime-venv/bin/python3
SCRIPT_DIR=/Users/ye/.hermes/scripts
RUNTIME_DIR=/Users/ye/.hermes/research/binance_futures_1m_collector_runtime
DB=$RUNTIME_DIR/binance_futures_1m.sqlite3
LOG_DIR=$RUNTIME_DIR/logs
WATCHDOG_LOG=$LOG_DIR/watchdog.log

NOW_MS=$(($(date +%s) * 1000))
STALE_KLINE_MS=$((10 * 60 * 1000))      # 10 min for 1m collector
STALE_METRIC_MS=$((20 * 60 * 1000))     # 20 min for metric collector (slow cycle)
STALE_TICKER_MS=$((15 * 60 * 1000))     # 15 min for 24h ticker

mkdir -p $LOG_DIR

log() {
    local line="[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [WATCHDOG] $1"
    echo "$line" >> $WATCHDOG_LOG
}

# Quick connectivity check — used to distinguish "VPN down" from "collector hung"
check_binance_reachable() {
    local code=$(curl -sS --max-time 5 -x http://127.0.0.1:7897 -o /dev/null -w "%{http_code}" \
        "https://fapi.binance.com/fapi/v1/exchangeInfo" 2>/dev/null)
    [[ "$code" == "200" ]]
}

# launch_collector NAME SCRIPT_NAME EXTRA_ARGS_QUOTED
launch_collector() {
    local name=$1
    local script=$2
    shift 2
    local extra_args="$@"

    log "$name LAUNCH ($script $extra_args)"
    nohup $PYTHON "$SCRIPT_DIR/$script" $extra_args \
        >> "$LOG_DIR/${name}.log" 2>&1 &
    disown 2>/dev/null
    sleep 1
}

restart_if_dead_or_stale() {
    local name=$1
    local script=$2
    local table=$3
    local ts_col=$4
    local stale_threshold=$5
    shift 5
    local extra_args="$@"

    if ! pgrep -f "$script" > /dev/null 2>&1; then
        log "$name DEAD"
        launch_collector "$name" "$script" $extra_args
        return
    fi

    # Process alive — check freshness
    local last_ts=$(sqlite3 "$DB" "SELECT MAX($ts_col) FROM $table;" 2>/dev/null)
    if [[ -z "$last_ts" || "$last_ts" == "" ]]; then
        return
    fi

    local age_ms=$((NOW_MS - last_ts))
    if [[ "$age_ms" -gt "$stale_threshold" ]]; then
        # Stale — but is it because VPN is down (acceptable) or stuck?
        if check_binance_reachable; then
            local age_min=$((age_ms / 60000))
            log "$name STALE ${age_min}min (Binance reachable → restarting stuck process)"
            pkill -f "$script" 2>/dev/null
            sleep 3
            launch_collector "$name" "$script" $extra_args
        else
            local age_min=$((age_ms / 60000))
            log "$name stale ${age_min}min but Binance unreachable (VPN down? skip restart)"
        fi
    fi
}

# 1m collector
restart_if_dead_or_stale \
    "1m_collector" \
    "binance_futures_1m_collector.py" \
    "klines_1m" \
    "open_time_ms" \
    "$STALE_KLINE_MS" \
    "--config $SCRIPT_DIR/binance_futures_1m_collector_config.json --runtime-dir $RUNTIME_DIR"

# Metric collector
restart_if_dead_or_stale \
    "metric_collector" \
    "binance_futures_metric_collector.py" \
    "mark_price_1m" \
    "ts_ms" \
    "$STALE_METRIC_MS" \
    "--config $SCRIPT_DIR/binance_futures_metric_collector_config.json --runtime-dir $RUNTIME_DIR"

# 24h ticker collector
restart_if_dead_or_stale \
    "ticker_24h_collector" \
    "binance_24h_ticker_collector.py" \
    "ticker_24h" \
    "ts_ms" \
    "$STALE_TICKER_MS" \
    ""
