#!/usr/bin/env python3
"""Watchdog for the BWE public Telegram matrix collector.

Keeps the channel-message collector alive without producing Telegram heartbeat spam.
- Monitors bwe_matrix_monitor.py process presence.
- Monitors health-log freshness; if stale, restarts the collector.
- Avoids duplicate collectors by terminating extras.
- Writes JSONL audit records to ~/.hermes/logs/bwe_matrix_watchdog.log.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

HOME = Path.home()
PYTHON_BIN = os.environ.get("BWE_MATRIX_PYTHON", "python3")
MONITOR_SCRIPT = HOME / ".hermes" / "scripts" / "bwe_matrix_monitor.py"
STATE_PATH = HOME / ".hermes" / "state" / "bwe_matrix_monitor_state.json"
POSTS_LOG = Path("/Volumes/T9/BWE/30_DATA/bwe_logs/bwe_matrix_posts.jsonl")
HEALTH_LOG = Path("/Volumes/T9/BWE/30_DATA/bwe_logs/bwe_matrix_health.jsonl")
STDOUT_LOG = HOME / ".hermes" / "logs" / "bwe_matrix_monitor.out"
STDERR_LOG = HOME / ".hermes" / "logs" / "bwe_matrix_monitor.err"
PID_FILE = HOME / ".hermes" / "logs" / "bwe_matrix_monitor.pid"
WATCHDOG_LOG = HOME / ".hermes" / "logs" / "bwe_matrix_watchdog.log"

INTERVAL_SECONDS = os.environ.get("BWE_MATRIX_INTERVAL", "1")
HEARTBEAT_SECONDS = os.environ.get("BWE_MATRIX_HEARTBEAT_SECONDS", "30")
STALE_HEALTH_SECONDS = int(os.environ.get("BWE_MATRIX_STALE_HEALTH_SECONDS", "180"))

PROCESS_MARKERS = [
    str(MONITOR_SCRIPT),
    "--posts-log",
    str(POSTS_LOG),
    "--health-log",
    str(HEALTH_LOG),
]


def now_ms() -> int:
    return int(time.time() * 1000)


def log_event(event: Dict) -> None:
    WATCHDOG_LOG.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts_ms": now_ms(), **event}
    with WATCHDOG_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def process_matches() -> List[Dict[str, str]]:
    try:
        out = subprocess.check_output(["ps", "-axo", "pid=,command="], text=True, stderr=subprocess.STDOUT)
    except Exception as exc:
        log_event({"type": "ps_error", "error": str(exc)})
        return []
    rows: List[Dict[str, str]] = []
    me = os.getpid()
    for line in out.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(maxsplit=1)
        if len(parts) != 2:
            continue
        pid_s, cmd = parts
        try:
            pid = int(pid_s)
        except ValueError:
            continue
        if pid == me:
            continue
        if all(marker in cmd for marker in PROCESS_MARKERS):
            rows.append({"pid": str(pid), "cmd": cmd})
    rows.sort(key=lambda r: int(r["pid"]))
    return rows


def file_age_seconds(path: Path) -> float | None:
    if not path.exists():
        return None
    return time.time() - path.stat().st_mtime


def terminate_pid(pid: int, reason: str) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
        log_event({"type": "terminate", "pid": pid, "reason": reason})
    except ProcessLookupError:
        log_event({"type": "terminate_missing", "pid": pid, "reason": reason})
    except Exception as exc:
        log_event({"type": "terminate_error", "pid": pid, "reason": reason, "error": str(exc)})


def start_monitor(reason: str) -> int:
    MONITOR_SCRIPT.parent.mkdir(parents=True, exist_ok=True)
    POSTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_LOG.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STDOUT_LOG.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        PYTHON_BIN,
        str(MONITOR_SCRIPT),
        "--interval",
        INTERVAL_SECONDS,
        "--heartbeat-seconds",
        HEARTBEAT_SECONDS,
        "--state",
        str(STATE_PATH),
        "--posts-log",
        str(POSTS_LOG),
        "--health-log",
        str(HEALTH_LOG),
    ]
    env = os.environ.copy()
    # Proxy intentionally unset: data pulls use Proton VPN at the system route level.
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy", "BINANCE_HTTPS_PROXY"):
        env.pop(key, None)
    with STDOUT_LOG.open("a", encoding="utf-8") as out, STDERR_LOG.open("a", encoding="utf-8") as err:
        proc = subprocess.Popen(
            cmd,
            stdout=out,
            stderr=err,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
    PID_FILE.write_text(str(proc.pid) + "\n", encoding="utf-8")
    log_event({"type": "start", "pid": proc.pid, "reason": reason, "cmd": " ".join(cmd)})
    return proc.pid


def main() -> int:
    matches = process_matches()
    health_age = file_age_seconds(HEALTH_LOG)

    # If duplicates exist, keep the oldest PID and terminate the extras.
    if len(matches) > 1:
        keep = matches[0]
        for extra in matches[1:]:
            terminate_pid(int(extra["pid"]), "duplicate_monitor")
        matches = [keep]

    stale = health_age is None or health_age > STALE_HEALTH_SECONDS
    if not matches:
        start_monitor("not_running")
        print(json.dumps({"status": "restarted", "reason": "not_running"}, ensure_ascii=False))
        return 0

    pid = int(matches[0]["pid"])
    if stale:
        terminate_pid(pid, f"stale_health_age={health_age}")
        time.sleep(2)
        start_monitor("stale_health")
        print(json.dumps({"status": "restarted", "reason": "stale_health", "old_pid": pid, "health_age_seconds": health_age}, ensure_ascii=False))
        return 0

    PID_FILE.write_text(str(pid) + "\n", encoding="utf-8")
    log_event({"type": "ok", "pid": pid, "health_age_seconds": round(health_age or 0, 3)})
    print(json.dumps({"status": "ok", "pid": pid, "health_age_seconds": round(health_age or 0, 3)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
