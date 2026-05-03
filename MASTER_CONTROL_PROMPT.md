# 🎛 BWE Master Control Prompt — Windows Bootstrap

> **复制粘贴整个文件内容作为 Claude Code 的第一句话, 然后让它执行.** Agent 会自动 clone、装依赖、配代理、启动收集器、跟你确认运行模式.

---

## 0. Agent identity & context

You are setting up the **BWE (Binance Whale Event) trading research infrastructure** on a fresh Windows machine. This is a port from a Mac mini that has been running 24/7 as the primary host.

**Repo (PRIVATE)**: https://github.com/Yem53/BWE

The Mac runs:
- 13 binance/OKX/bybit collectors writing to a 22 GB SQLite DB
- BWE Telegram listener (3 channels)
- Codex paper-LIVE testnet
- Watchdog daemon
- WAL checkpointer
- Clash Verge proxy (Tier1 → Tier2 → Tier3 fallback for binance fapi REST)

You will replicate all of this on Windows. The user wants either **Mirror** mode (Mac stays primary, Windows is read-only research) or **Active replica** (both run independently).

---

## 1. 工作目录 + clone

```powershell
# Run as ADMIN PowerShell
$WORK = "D:\BWE"
mkdir $WORK -Force
cd D:\

# git clone via gh (uses Yem53 auth)
gh auth login   # browser flow if not authenticated
gh repo clone Yem53/BWE D:\BWE
cd D:\BWE

# verify
git log --oneline | Select-Object -First 3
```

If `gh` is not installed yet:
```powershell
winget install --silent GitHub.cli
winget install --silent Git.Git
# Reload shell
```

---

## 2. 必装工具 (winget admin)

```powershell
$tools = @(
    'Python.Python.3.11',
    'Git.Git',
    'GitHub.cli',
    'ClashVergeRev.ClashVergeRev',
    'Microsoft.WindowsTerminal',
    'NSSM.NSSM'
)
foreach ($t in $tools) {
    winget install --silent --accept-package-agreements --accept-source-agreements --id $t
}
# Optional for Mac↔Windows DB sync:
# winget install --silent --id Tailscale.Tailscale
```

Verify all installed:
```powershell
foreach ($cmd in 'python','git','gh','nssm') {
    & $cmd --version
}
```

---

## 3. Python venv + dependencies

```powershell
cd D:\BWE
python -m venv .\runtime-venv
.\runtime-venv\Scripts\Activate.ps1
python -m pip install --upgrade pip wheel

pip install `
    websocket-client `
    requests `
    pyyaml `
    pandas `
    numpy `
    python-socks `
    aiohttp `
    "telethon>=1.34" `
    cryptg `
    pyarrow `
    scikit-learn `
    lz4
```

Verify:
```powershell
python -c "import websocket, requests, yaml, pandas, telethon; print('all ok')"
```

---

## 4. Clash Verge — 复用 Mac 已有配置

The repo includes the **actual** Clash Verge profile from Mac (with Proton VPN credentials + WgetCloud subscription). Since the repo is private, this is OK.

```powershell
# 4.1 Stop Clash Verge if running
Get-Process | Where-Object { $_.Name -like "*clash*" } | Stop-Process -Force

# 4.2 Find Clash Verge profile dir on Windows
$VERGE_DIR = "$env:APPDATA\io.github.clash-verge-rev.clash-verge-rev"
mkdir "$VERGE_DIR\profiles" -Force

# 4.3 Copy our private profiles
Copy-Item D:\BWE\infrastructure\clashverge\private\LProtonCrypto.yaml `
    "$VERGE_DIR\profiles\LProtonCrypto.yaml" -Force

Copy-Item D:\BWE\infrastructure\clashverge\private\clash-verge-main.yaml `
    "$VERGE_DIR\clash-verge.yaml" -Force

# 4.4 Start Clash Verge
Start-Process "C:\Program Files\Clash Verge\Clash Verge.exe"
Start-Sleep 8

# 4.5 Enable Tun mode via API (port 9090 default for clashverge ext-controller)
# OR open GUI → Settings → Tun Mode → ON
```

If GUI shows the imported profile but Tun isn't enabled, manually toggle: **Settings → Tun Mode → ON → Restart core**.

### Verify proxy works

```powershell
curl --max-time 5 -o $null -w "fapi: %{http_code}`n" https://fapi.binance.com/fapi/v1/exchangeInfo
# Expected: 200

curl --max-time 5 -o $null -w "okx: %{http_code}`n" https://www.okx.com/api/v5/public/instruments?instType=SWAP
# Expected: 200 (note: OKX needs proxy too in US)

# Direct connection (for OKX / Bybit liquidation WS, no proxy)
$env:HTTP_PROXY=""; $env:HTTPS_PROXY=""
curl --max-time 5 -o $null -w "okx_direct: %{http_code}`n" https://www.okx.com/api/v5/public/time
# Expected: 200
```

If `fapi` returns 451, Clash Verge / Tun mode not active. Don't proceed until 200.

---

## 5. .env file (the only secret you must transfer manually)

Copy `~/.hermes/.env` from your Mac (encrypted USB, 1Password, Bitwarden, signal note-to-self, etc.).

```powershell
mkdir $env:USERPROFILE\.hermes -Force
notepad $env:USERPROFILE\.hermes\.env
# Paste contents from Mac's ~/.hermes/.env
```

The template is at `D:\BWE\infrastructure\.env.example`. Required keys for collectors:
- `BWE_TRADE_TEST_BOT_TOKEN`, `BWE_TRADE_TEST_CHAT_ID` (Telegram alerts)
- `TG_API_ID`, `TG_API_HASH`, `TG_PHONE` (BWE matrix listener)
- `HTTP_PROXY=http://127.0.0.1:7897` (Clash Verge mixed port)
- `BINANCE_TESTNET_API_KEY`, `BINANCE_TESTNET_SECRET` (only if running paper-LIVE)

---

## 6. Path adjustment Mac → Windows

Mac configs use `/Volumes/T9/BWE/...`. Windows uses `D:\BWE\...`.

```powershell
$collectorConfigs = Get-ChildItem D:\BWE\infrastructure\collectors\configs -Filter *.json
foreach ($f in $collectorConfigs) {
    $content = Get-Content $f.FullName -Raw
    $patched = $content `
        -replace '/Volumes/T9/BWE/30_DATA', 'D:/BWE/30_DATA' `
        -replace '/Volumes/T9_HOT/binance_collectors_runtime', 'D:/BWE/30_DATA/binance_collectors_runtime' `
        -replace '/Volumes/T9/BWE', 'D:/BWE'
    Set-Content $f.FullName -Value $patched -NoNewline
}

# Verify
findstr /S /M "/Volumes/T9" D:\BWE\infrastructure\collectors\configs\*.json
# Expected: 0 hits
```

Also create runtime dirs:
```powershell
mkdir D:\BWE\30_DATA\binance_collectors_runtime\logs -Force
mkdir D:\BWE\30_DATA\bwe_logs -Force
```

---

## 7. Telegram session (BWE matrix monitor first run)

Mac's Telegram session file (`bwe_matrix_state.json`) contains a phone-authenticated session token. Either:

**Option A: copy from Mac**
```powershell
# scp from Mac (if Tailscale / SSH set up)
scp ye@mac:/Users/ye/.hermes/state/bwe_matrix_monitor_state.json `
    $env:USERPROFILE\.hermes\state\
```

**Option B: re-authenticate on Windows** (Telegram allows multiple sessions)
```powershell
mkdir $env:USERPROFILE\.hermes\state -Force
.\runtime-venv\Scripts\python.exe D:\BWE\infrastructure\collectors\bwe_matrix_monitor.py `
    --interval 1 --heartbeat-seconds 30 `
    --state $env:USERPROFILE\.hermes\state\bwe_matrix_monitor_state.json `
    --posts-log D:\BWE\30_DATA\bwe_logs\bwe_matrix_posts.jsonl `
    --health-log D:\BWE\30_DATA\bwe_logs\bwe_matrix_health.jsonl
# First run: enter phone code from Telegram SMS, then ctrl+c
```

---

## 8. 启动 collectors (stagger 30s 防 Binance 418)

```powershell
$LOG = "D:\BWE\30_DATA\binance_collectors_runtime\logs"
$PY = "D:\BWE\runtime-venv\Scripts\python.exe"
$SCRIPTS = "D:\BWE\infrastructure\collectors"
$env:HTTP_PROXY = "http://127.0.0.1:7897"
$env:HTTPS_PROXY = "http://127.0.0.1:7897"

# Kline collectors (1m, 3m, 5m, 15m, 1h)
foreach ($itv in '1m','3m','5m','15m','1h') {
    Start-Process -FilePath $PY -ArgumentList @(
        "$SCRIPTS\binance_futures_1m_collector.py",
        "--config", "$SCRIPTS\configs\binance_futures_${itv}_collector_config.json"
    ) -WindowStyle Hidden -RedirectStandardOutput "$LOG\${itv}_collector.log" -RedirectStandardError "$LOG\${itv}_collector.err"
    Write-Host "  ${itv} started, sleep 30..."
    Start-Sleep 30
}

# Metric / 24h_ticker / index_price (proxy required)
Start-Process -FilePath $PY -ArgumentList @(
    "$SCRIPTS\binance_futures_metric_collector.py",
    "--config", "$SCRIPTS\configs\binance_futures_metric_collector_config.json"
) -WindowStyle Hidden -RedirectStandardOutput "$LOG\metric.log" -RedirectStandardError "$LOG\metric.err"
Start-Sleep 30

Start-Process -FilePath $PY -ArgumentList @("$SCRIPTS\binance_24h_ticker_collector.py") `
    -WindowStyle Hidden -RedirectStandardOutput "$LOG\ticker24h.log" -RedirectStandardError "$LOG\ticker24h.err"

Start-Process -FilePath $PY -ArgumentList @("$SCRIPTS\binance_index_price_collector.py") `
    -WindowStyle Hidden -RedirectStandardOutput "$LOG\index.log" -RedirectStandardError "$LOG\index.err"

# OKX + Bybit liquidation (DIRECT, no proxy)
$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""
Start-Process -FilePath $PY -ArgumentList @("$SCRIPTS\okx_liquidation_collector.py") `
    -WindowStyle Hidden -RedirectStandardOutput "$LOG\okx_liq.log" -RedirectStandardError "$LOG\okx_liq.err"
Start-Process -FilePath $PY -ArgumentList @("$SCRIPTS\bybit_liquidation_collector.py") `
    -WindowStyle Hidden -RedirectStandardOutput "$LOG\bybit_liq.log" -RedirectStandardError "$LOG\bybit_liq.err"

# BWE matrix monitor (proxy NOT needed; Telegram has its own MTProto)
Start-Process -FilePath $PY -ArgumentList @(
    "$SCRIPTS\bwe_matrix_monitor.py",
    "--interval", "1", "--heartbeat-seconds", "30",
    "--state", "$env:USERPROFILE\.hermes\state\bwe_matrix_monitor_state.json",
    "--posts-log", "D:\BWE\30_DATA\bwe_logs\bwe_matrix_posts.jsonl",
    "--health-log", "D:\BWE\30_DATA\bwe_logs\bwe_matrix_health.jsonl"
) -WindowStyle Hidden -RedirectStandardOutput "$LOG\bwe_matrix.log" -RedirectStandardError "$LOG\bwe_matrix.err"

Write-Host ""
Write-Host "=== Verify all collectors running ==="
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq "" } | Format-Table Id, ProcessName, StartTime
```

For 24/7 service registration via NSSM:
```powershell
foreach ($itv in '1m','3m','5m','15m','1h') {
    $svcName = "BWE-${itv}-Collector"
    nssm install $svcName $PY "$SCRIPTS\binance_futures_1m_collector.py --config $SCRIPTS\configs\binance_futures_${itv}_collector_config.json"
    nssm set $svcName AppEnvironmentExtra "HTTP_PROXY=http://127.0.0.1:7897" "HTTPS_PROXY=http://127.0.0.1:7897"
    nssm set $svcName AppStdout "$LOG\${itv}_collector.log"
    nssm set $svcName AppStderr "$LOG\${itv}_collector.err"
    nssm set $svcName AppRotateFiles 1
    nssm start $svcName
}
# Repeat similarly for metric / ticker / OKX / Bybit / BWE matrix
```

---

## 9. Verification (each must pass)

```powershell
$ErrorActionPreference = 'Continue'

Write-Host "=== Health checks ==="

# 1. Proxy
$fapiCode = (Invoke-WebRequest -Uri "https://fapi.binance.com/fapi/v1/exchangeInfo" -UseBasicParsing -TimeoutSec 5 -Proxy "http://127.0.0.1:7897" -ErrorAction Continue).StatusCode
Write-Host "fapi via proxy: $fapiCode  (expect 200)"

# 2. OKX direct
$okxCode = (Invoke-WebRequest -Uri "https://www.okx.com/api/v5/public/time" -UseBasicParsing -TimeoutSec 5).StatusCode
Write-Host "OKX direct: $okxCode  (expect 200)"

# 3. SQLite DB created + growing
$db = "D:\BWE\30_DATA\binance_collectors_runtime\binance_futures_1m.sqlite3"
if (Test-Path $db) {
    $size = (Get-Item $db).Length / 1MB
    Write-Host "DB exists: $size MB"
} else {
    Write-Host "DB not yet — wait 60s for first collector cycle"
}

# 4. BWE jsonl
$jsonl = "D:\BWE\30_DATA\bwe_logs\bwe_matrix_posts.jsonl"
if (Test-Path $jsonl) {
    $lines = (Get-Content $jsonl).Count
    Write-Host "BWE jsonl: $lines lines"
} else {
    Write-Host "BWE jsonl not yet — Telegram listener may need first auth"
}

# 5. Process count
$pyProcs = (Get-Process python -ErrorAction SilentlyContinue).Count
Write-Host "Python processes running: $pyProcs (expect ~10-13)"
```

---

## 10. Modes — agent should ASK user which one

After verification passes, prompt the user:

> Setup verified. Choose run mode:
>
> **A. Mirror (read-only research)**
>    - No collectors run on Windows — only read repo content
>    - Mac stays primary collector
>    - Use this for vault editing / research / backtest only
>
> **B. Active replica (parallel)**
>    - Both Mac + Windows collect independently
>    - Two separate DBs (no sync; both will have same data within seconds)
>    - Best for HA + dev work on Windows without disturbing Mac
>
> **C. Takeover (Mac stops)**
>    - Mac collectors are stopped via SSH
>    - Windows becomes the new primary
>    - Use this if you're moving the trading workstation
>
> Type A / B / C.

If A: skip step 8 entirely, just confirm clone + repo open.
If B: run step 8.
If C: SSH into Mac, run `pkill -f binance_futures` etc., then run step 8 here.

---

## 11. Continuous syncing (after first deploy)

```powershell
# Mac → GitHub: any code/config changes
cd /Volumes/T9/BWE
git add . && git commit -m "..." && git push

# Windows → GitHub: pull updates
cd D:\BWE
git pull
# Restart any service whose code changed
```

For binance live data sync, no git involvement — both machines query same exchanges and converge to same state.

---

## 12. ⚠ Guardrails (mirror Mac CLAUDE.md, mandatory)

- 🚫 Never enter live API keys or trade real funds without per-trade explicit user confirmation
- 🚫 Never auto-promote a backtest winner to live trading
- 🚫 Never edit `.env` to commit credentials
- 🚫 Never run paper-LIVE on Windows AND Mac simultaneously (would double-submit testnet orders)
- ✅ Always sandbox-only: outputs to `40_EXPERIMENTS/<run_id>/`, reports to `50_ANALYSIS_REPORTS/`
- ✅ Stability over absolute return (sort by stability_score, not mean_return)
- ✅ All experiments are explorable via `00_INDEX.md` Obsidian graph

---

## End of master prompt

Agent: when you reach this line, do the following in order:

1. Confirm `D:\BWE` clone succeeded
2. Run all install commands (sections 2-3)
3. Configure Clash Verge (section 4) and verify HTTP 200 on fapi
4. Read `infrastructure/README.md` and `CLAUDE.md` for project rules
5. Patch paths (section 6)
6. Set up Telegram session (section 7)
7. **Pause and ask user mode (section 10) before starting collectors**
8. Once user confirms mode, proceed with section 8
9. Run verification (section 9), report status of all checks

Take your time. If any step fails, stop and report exact error to user before continuing.
