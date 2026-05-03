#!/bin/bash
# Round 4 — 10 小时端到端 Pipeline Orchestrator
# - 5090 主 main loop on GPU (smart_priority cycling)
# - Mac 只做轻量级 orchestration: ssh / scp / claude -p subprocess
# - Memory footprint on Mac < 500 MB sustained (NO polars rebuild, NO ProcessPoolExecutor)
#
# Phases (loop until 10h budget exhausted):
#   epoch -> LLM debate cycle (max effort, opus-4-7 11 roles) -> append archetypes -> restart epoch
#
# Orchestrator runs in background, writes status to log, idempotent (resume-safe).

set -u
PIPELINE_START=$(date +%s)
DEADLINE_HOURS=${R4_DEADLINE_HOURS:-10}
DEADLINE=$((PIPELINE_START + DEADLINE_HOURS * 3600))

SSH_TARGET="Admin@192.168.1.155"
T9="/Volumes/T9/BWE"
DEBATES_DIR="$T9/40_EXPERIMENTS/debates"
REGISTRY="$T9/40_EXPERIMENTS/hypothesis_registry.jsonl"
RESULTS_TSV="$T9/20_CODE/Autoresearch/results.tsv"
BEST_SCORE="$T9/20_CODE/Autoresearch/best_score.json"
PYTHON="/tmp/codex_round4_venv/bin/python"
LOG="$T9/40_EXPERIMENTS/round4/99_logs/pipeline_$(date +%Y%m%d_%H%M%S).log"
STATUS="$T9/40_EXPERIMENTS/round4/99_logs/pipeline_status.txt"

mkdir -p "$T9/40_EXPERIMENTS/round4/99_logs"

log() {
    local now=$(date '+%H:%M:%S')
    local elapsed_min=$(( ($(date +%s) - PIPELINE_START) / 60 ))
    echo "[$now T+${elapsed_min}m] $*" | tee -a "$LOG"
    echo "[$now T+${elapsed_min}m] $*" > "$STATUS"
}

ssh_check() {
    ssh -o ConnectTimeout=10 -o ServerAliveInterval=15 $SSH_TARGET "$1" 2>/dev/null
}

is_main_loop_alive() {
    local result
    result=$(ssh_check 'powershell -NoProfile -Command "$pid_=Get-Content C:\bwe_compute\round4.pid -ErrorAction SilentlyContinue; if ($pid_ -and (Get-Process -Id $pid_ -ErrorAction SilentlyContinue)) {\"ALIVE\"} else {\"DONE\"}"' | tr -d '\r ')
    [ "$result" = "ALIVE" ]
}

get_results_count() {
    ssh_check 'powershell -NoProfile -Command "(Get-Content C:\bwe_compute\20_CODE\Autoresearch\results.tsv -ErrorAction SilentlyContinue).Count"' | tr -d '\r '
}

get_cursor() {
    ssh_check 'type C:\bwe_compute\40_EXPERIMENTS\combo_cursor.json' 2>/dev/null | grep -oE '[0-9]+' | head -1
}

deadline_reached() {
    [ $(date +%s) -gt $DEADLINE ]
}

wait_for_epoch_done() {
    local epoch_label=$1
    local last_count=0
    local stall_count=0
    log "WAIT for $epoch_label main loop to finish"
    while true; do
        if deadline_reached; then
            log "DEADLINE 10h reached during $epoch_label wait, breaking pipeline"
            return 1
        fi
        if ! is_main_loop_alive; then
            log "$epoch_label main loop DONE (results.tsv rows=$(get_results_count))"
            return 0
        fi
        local count=$(get_results_count)
        local cur=$(get_cursor)
        log "$epoch_label progress: rows=$count cursor=$cur"
        if [ "$count" = "$last_count" ]; then
            stall_count=$((stall_count + 1))
            if [ $stall_count -ge 6 ]; then
                log "WARNING: $epoch_label stalled 30+ min at row $count"
            fi
        else
            stall_count=0
            last_count=$count
        fi
        sleep 300
    done
}

run_llm_cycle() {
    local cycle=$1
    log "=== LLM cycle $cycle BEGIN (max effort, opus-4-7, 11 roles) ==="

    log "pulling results.tsv + best_score.json from 5090"
    scp -q $SSH_TARGET:'C:/bwe_compute/20_CODE/Autoresearch/results.tsv' "$RESULTS_TSV" 2>&1 | tee -a "$LOG"
    scp -q $SSH_TARGET:'C:/bwe_compute/20_CODE/Autoresearch/best_score.json' "$BEST_SCORE" 2>&1 | tee -a "$LOG"
    local rows=$(wc -l < "$RESULTS_TSV" | tr -d ' ')
    log "results.tsv pulled, $rows rows"

    log "starting LLM debate (BWE_LLM_EFFORT=max, model claude-opus-4-7)"
    cd "$T9/20_CODE/Autoresearch"
    BWE_LLM_EFFORT=max "$PYTHON" -m bwe_autoresearch.bwe_loop_llm_team 2>&1 | tee -a "$LOG"
    local rc=$?

    if [ $rc -ne 0 ]; then
        log "ERROR: LLM cycle $cycle failed with code $rc"
        return 1
    fi

    local latest=$(ls -dt "$DEBATES_DIR"/debate_* 2>/dev/null | head -1)
    if [ -z "$latest" ] || [ ! -f "$latest/new_archetypes.jsonl" ]; then
        log "WARN: no new_archetypes.jsonl produced by LLM cycle $cycle"
        return 0
    fi

    local new_count=$(wc -l < "$latest/new_archetypes.jsonl" | tr -d ' ')
    log "LLM cycle $cycle produced $new_count new archetypes ($latest)"

    cp "$REGISTRY" "$T9/40_EXPERIMENTS/registry_backups/hypothesis_registry_pre_llm_cycle_${cycle}_$(date +%Y%m%d_%H%M%S).jsonl"
    cat "$latest/new_archetypes.jsonl" >> "$REGISTRY"
    log "merged $new_count archetypes into registry, total now $(wc -l < "$REGISTRY" | tr -d ' ')"

    log "pushing updated registry + results to 5090"
    scp -q "$REGISTRY" $SSH_TARGET:'C:/bwe_compute/40_EXPERIMENTS/hypothesis_registry.jsonl'

    log "=== LLM cycle $cycle END ==="
    return 0
}

restart_main_loop() {
    local epoch=$1
    log "=== Restart main loop for epoch $epoch (smart_priority, cursor=0) ==="

    echo '{"cursor": 0}' > /tmp/cursor_zero.json
    scp -q /tmp/cursor_zero.json $SSH_TARGET:'C:/bwe_compute/40_EXPERIMENTS/combo_cursor.json'

    ssh_check "powershell -NoProfile -Command \"Copy-Item C:\\bwe_compute\\20_CODE\\Autoresearch\\results.tsv C:\\bwe_compute\\20_CODE\\Autoresearch\\results_r4_epoch_$((epoch-1)).tsv -Force; Set-Content C:\\bwe_compute\\20_CODE\\Autoresearch\\results.tsv 'commit\tval_score\ttriggers\tstatus\tdescription'\""

    ssh_check 'powershell -ExecutionPolicy Bypass -File C:\bwe_compute\launch_main_loop_v2.ps1' | tee -a "$LOG"
    sleep 5
    if is_main_loop_alive; then
        log "epoch $epoch main loop launched ✓"
        return 0
    else
        log "ERROR: failed to launch epoch $epoch"
        return 1
    fi
}

run_paper_shadow() {
    log "=== paper_shadow on top-30 keeps ==="
    cd "$T9/20_CODE/Autoresearch"

    local top_entries=$(awk -F'\t' '$4=="keep"' "$RESULTS_TSV" | sort -t$'\t' -k2 -gr | head -30 | grep -oE 'E=E[0-9]+' | sed 's/E=//' | sort -u)
    log "top entries: $top_entries"

    for entry in $top_entries; do
        log "paper_shadow $entry"
        timeout 120 "$PYTHON" scripts/paper_shadow_sim.py "$entry" 2>&1 | tee -a "$LOG" || log "WARN: paper_shadow $entry timed out / failed"
    done
}

generate_morning_brief() {
    log "=== Generate Round 4 morning brief ==="
    cd "$T9/20_CODE/Autoresearch"
    if [ -f scripts/generate_morning_brief.py ]; then
        timeout 600 "$PYTHON" scripts/generate_morning_brief.py 2>&1 | tee -a "$LOG"
    else
        log "WARN: generate_morning_brief.py not found, skipping"
    fi
}

# ============================================================================
# Main pipeline
# ============================================================================

log "PIPELINE START — deadline = +${DEADLINE_HOURS}h"
log "5090 status: $(if is_main_loop_alive; then echo ALIVE; else echo NOT_RUNNING; fi)"
log "results.tsv rows: $(get_results_count) | cursor: $(get_cursor)"

EPOCH=1
LLM_CYCLE_COUNT=0

while ! deadline_reached; do
    log "--- Epoch $EPOCH (current main loop) ---"

    if is_main_loop_alive; then
        wait_for_epoch_done "epoch $EPOCH" || break
    else
        log "main loop not running, restart?"
        if [ $EPOCH -eq 1 ]; then
            log "epoch 1 not running, launching now"
            restart_main_loop $EPOCH || break
            wait_for_epoch_done "epoch $EPOCH" || break
        fi
    fi

    if deadline_reached; then break; fi

    LLM_CYCLE_COUNT=$((LLM_CYCLE_COUNT + 1))
    run_llm_cycle $LLM_CYCLE_COUNT || log "LLM cycle $LLM_CYCLE_COUNT had issues, continuing"

    if deadline_reached; then break; fi

    EPOCH=$((EPOCH + 1))

    NOW=$(date +%s)
    REMAINING_MIN=$(( (DEADLINE - NOW) / 60 ))
    if [ $REMAINING_MIN -lt 90 ]; then
        log "remaining $REMAINING_MIN min < 90, skip another epoch, go to final phase"
        break
    fi

    restart_main_loop $EPOCH || break
done

log "=== FINAL PHASE ==="
run_paper_shadow
generate_morning_brief

log "PIPELINE COMPLETE: $LLM_CYCLE_COUNT LLM cycles, $((EPOCH - 1)) epochs"
log "Total elapsed: $(( ($(date +%s) - PIPELINE_START) / 60 )) min"
