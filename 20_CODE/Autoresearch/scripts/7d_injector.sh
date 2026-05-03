#!/bin/bash
# 7d hold injector — monitors Mac 7d builder, scp result to 5090, set sentinel flag.
# Once sentinel set, orchestrator's next epoch restart will use 7d hold mode.

set -u
SSH_TARGET="Admin@192.168.1.155"
LOG=/Volumes/T9/BWE/40_EXPERIMENTS/round4/99_logs/7d_injector.log
BUILDER_LOG=/tmp/build_7d.log
SEVEN_D_PARQUET=/Volumes/T9/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows_7d.parquet

log() {
    echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"
}

log "=== 7d injector start ==="
log "polling builder log: $BUILDER_LOG"

# Wait for builder to finish (max 90 min)
MAX_WAIT_SEC=5400
START=$(date +%s)
while true; do
    NOW=$(date +%s)
    if [ $((NOW - START)) -gt $MAX_WAIT_SEC ]; then
        log "TIMEOUT 90 min, builder not done — abort 7d injection"
        exit 1
    fi

    if grep -q "BUILD COMPLETE" "$BUILDER_LOG" 2>/dev/null; then
        log "builder done"
        break
    fi

    if ! ps -p "$(cat /tmp/build_7d.pid 2>/dev/null)" >/dev/null 2>&1; then
        # Builder PID died without completing
        if ! grep -q "BUILD COMPLETE" "$BUILDER_LOG" 2>/dev/null; then
            log "builder PID died without completion — abort 7d injection"
            exit 1
        fi
    fi

    log "still waiting (parsed=$(grep -c 'parsed' "$BUILDER_LOG" 2>/dev/null || echo 0))"
    sleep 60
done

if [ ! -f "$SEVEN_D_PARQUET" ]; then
    log "ERROR: 7d parquet $SEVEN_D_PARQUET not found after build complete"
    exit 1
fi

SIZE_MB=$(ls -lh "$SEVEN_D_PARQUET" | awk '{print $5}')
log "7d parquet ready: $SIZE_MB"

# Push to 5090
log "scp pushing to 5090..."
T0=$(date +%s)
scp -q "$SEVEN_D_PARQUET" $SSH_TARGET:'C:/bwe_compute/30_DATA/cache/normalized/trade_kline_1m_event_windows_7d.parquet'
T1=$(date +%s)
log "scp done in $((T1 - T0))s"

# Verify on 5090
ssh $SSH_TARGET "powershell -NoProfile -Command \"(Get-Item C:\\bwe_compute\\30_DATA\\cache\\normalized\\trade_kline_1m_event_windows_7d.parquet).Length / 1MB\"" 2>&1 | tee -a "$LOG"

# Set sentinel flag — next launcher invocation will use 7d mode
ssh $SSH_TARGET "powershell -NoProfile -Command \"Set-Content -Path C:\\bwe_compute\\use_7d_hold.flag -Value '7d hold mode enabled $(Get-Date -Format yyyy-MM-dd_HH:mm:ss)'\"" 2>&1 | tee -a "$LOG"

log "=== 7d injection COMPLETE — next epoch restart will use 7d hold ==="
exit 0
