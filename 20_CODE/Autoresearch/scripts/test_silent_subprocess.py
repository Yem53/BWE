"""Smoke test: verify strong patch fully suppresses claude.exe console window.
Runs 3 quick claude -p calls and reports timing. Watch for flashing windows.
"""
import os, sys, shutil, subprocess, time

# Mirror the patch logic from bwe_loop_llm_team.py
def _find_claude_bin():
    """Mirror v3 patch from bwe_loop_llm_team.py: prefer the bundled claude.exe."""
    if sys.platform == "win32":
        from pathlib import Path
        npm_candidates = [
            Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe",
            Path("C:/Program Files/nodejs/node_modules/@anthropic-ai/claude-code/bin/claude.exe"),
        ]
        for cand in npm_candidates:
            if cand.exists():
                return str(cand)
        cmd = shutil.which("claude.cmd")
        if cmd:
            return cmd
    return shutil.which("claude") or "claude"

CLAUDE_BIN = _find_claude_bin()
print(f"CLAUDE_BIN = {CLAUDE_BIN}")

creationflags = 0
startupinfo = None
if sys.platform == "win32":
    creationflags = subprocess.CREATE_NO_WINDOW
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

env = os.environ.copy()
env["CLAUDE_CODE_GIT_BASH_PATH"] = env.get("CLAUDE_CODE_GIT_BASH_PATH", r"E:\Git\usr\bin\bash.exe")

cmd = [
    CLAUDE_BIN, "-p", "ping", "--output-format", "json", "--max-turns", "1",
    "--model", "claude-haiku-4-5-20251001",
    "--no-session-persistence",
    "--disallowedTools", "Bash,Edit,Write,Read,Grep,Glob",
]

print("\nLaunching 3 claude calls with stronger window suppression...")
print("Watch closely — should be ZERO black-window flashes.\n")

for i in range(3):
    t0 = time.time()
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=60, encoding="utf-8",
        env=env, creationflags=creationflags, startupinfo=startupinfo,
    )
    elapsed = time.time() - t0
    ok = proc.returncode == 0
    print(f"  call {i+1}: rc={proc.returncode} elapsed={elapsed:.1f}s  ok={ok}")

print("\nIf you saw NO flashes, the patch works. Restart Round 4 to apply.")
