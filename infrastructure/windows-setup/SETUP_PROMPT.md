# BWE Windows Machine Setup Prompt

> Paste this entire file as the **first message** to Claude Code (or any capable AI agent) on your Windows machine. The agent will read it and bootstrap the full BWE infrastructure.

---

## Goal

Replicate the **complete BWE trading research infrastructure** from the Mac mini (where it currently runs) onto this Windows machine, so I can develop / monitor from either machine.

The Mac is currently running these collectors + paper systems 24/7. I want this Windows box to either:

1. **Mirror** the Mac (read-only research / vault editing), OR
2. **Take over** as the primary collector (Mac stops, Windows runs)

The agent should ask which mode I want at the end.

---

## Source of truth (read first)

Repo: **https://github.com/Yem53/BWE**

Clone it to a fast local SSD path, e.g. `D:\BWE\` (NOT inside `C:\Users\...` cloud-synced folders).

```powershell
git clone https://github.com/Yem53/BWE.git D:\BWE
cd D:\BWE
```

Inside the repo, **read these in order** before doing anything:

1. `README.md` — top-level overview
2. `CLAUDE.md` — project rules (BWE-specific guardrails)
3. `infrastructure/README.md` — infra map (what runs where)
4. `infrastructure/windows-setup/SETUP_PROMPT.md` — this file
5. `infrastructure/.env.example` — secrets template

Crucial absolute paths (Mac uses `/Volumes/T9/BWE`; Windows should use `D:\BWE`).
The agent must search-and-replace **on local copy**, not in the repo.

---

## What the agent must install on Windows

### A. Required tools

| Tool | Purpose | Install command (PowerShell as admin) |
|---|---|---|
| **Python 3.11 or 3.12** | All collectors + paper | `winget install Python.Python.3.11` |
| **git** | Repo sync | `winget install Git.Git` |
| **Clash Verge Rev** | Proxy (mandatory in US for binance fapi REST) | `winget install --id ClashVergeRev.ClashVergeRev` |
| **GitHub CLI** | gh auth + push back | `winget install GitHub.cli` |
| **Windows Terminal** | Better shell | `winget install Microsoft.WindowsTerminal` |
| **Tailscale** (optional) | Sync DB back to Mac | `winget install Tailscale.Tailscale` |

### B. Python deps

```powershell
cd D:\BWE
python -m venv .\runtime-venv
.\runtime-venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install websocket-client requests pyyaml pandas numpy python-socks
# For paper-LIVE backtest research:
pip install scikit-learn pyarrow lz4
```

---

## What the agent must configure

### 1. Clash Verge proxy

Mac currently uses a `LProtonCrypto.yaml` profile with:
- Proton VPN nodes (Tier1/2/3 fallback chain) for binance REST
- Wgetcloud subscription nodes for binance fstream WS (didn't work — kept as fallback)
- Routing rules to send `binance.com` and `okx.com` etc through proxy

**Repo includes**: `infrastructure/clashverge/LProtonCrypto.template.yaml`
- Proxy structure (proxy-groups + rules) is intact
- Proton credentials (username/password/uuid) are `<REDACTED>`
- Subscription URL is `<YOUR_SUBSCRIPTION_URL_HERE>`

**Windows side must:**

1. Open Clash Verge Rev → Profiles → New (URL or Local)
2. Either:
   - **Option A (recommended)**: Import your **personal Proton VPN OpenVPN config** subscription URL (you got from Proton dashboard → Downloads → OpenVPN/IKEv2). Clash Verge converts it.
   - **Option B**: Manually add Proton credentials into the template's `proxies:` block (replace `<REDACTED>` with your Proton VPN OpenVPN username/password).
3. Copy the proxy-groups + rules from `LProtonCrypto.template.yaml` into your imported profile.
4. Apply + enable Tun mode (Settings → Tun Mode → ON).

After setup, verify:
```powershell
curl --max-time 5 -o $null -w "fapi: %{http_code}`n" https://fapi.binance.com/fapi/v1/exchangeInfo
# Should be 200. If 451, proxy not working.
```

### 2. .env file

```powershell
mkdir $env:USERPROFILE\.hermes
copy D:\BWE\infrastructure\.env.example $env:USERPROFILE\.hermes\.env
notepad $env:USERPROFILE\.hermes\.env
# Fill in: Binance/OKX/Telegram keys (get from your password manager / Mac's .env)
```

⚠ **Sync .env from Mac**: `.env` is gitignored. Manually transfer via 1Password / Bitwarden / encrypted USB.

### 3. Data directory

The Mac runs collectors writing to `/Volumes/T9_HOT/binance_collectors_runtime/binance_futures_1m.sqlite3` (22 GB DB).

**Windows options:**
- Fresh DB: collectors will recreate from Binance + backfill last 30 days (~1-2 hours)
- Copy from Mac: rsync or USB stick (22 GB; not ideal)

If fresh DB:
```powershell
mkdir D:\BWE\30_DATA\binance_collectors_runtime\logs
mkdir D:\BWE\30_DATA\bwe_logs
```

The Python collectors will create the SQLite tables on first run.

### 4. Update path in configs

All Mac configs reference `/Volumes/T9/BWE/...` paths. Agent must:

```powershell
# Find all files referencing Mac paths
findstr /s /i /m "/Volumes/T9" D:\BWE\infrastructure\collectors\configs\*.json D:\BWE\infrastructure\launchd\*.plist

# Replace with Windows paths
$files = Get-ChildItem -Path D:\BWE\infrastructure\collectors\configs -Filter *.json
foreach ($f in $files) {
    (Get-Content $f.FullName) -replace '/Volumes/T9/BWE', 'D:/BWE' | Set-Content $f.FullName
}
```

Verify by re-running findstr — should find 0 matches in `D:\BWE\infrastructure\collectors\configs\`.

### 5. BWE Telegram listener

The Mac runs `bwe_matrix_monitor.py` which uses `tdlib` / `telethon` to listen to BWE channels. Windows needs:

- Telegram API credentials (api_id, api_hash) — get from https://my.telegram.org → Apps
- Phone-based login (Telegram sends SMS code on first run)

Add to `.env`:
```
TG_API_ID=<your_telegram_api_id>
TG_API_HASH=<your_telegram_api_hash>
TG_PHONE=<your_phone_with_country_code>
```

First run will prompt for SMS code interactively.

### 6. Run modes

| Mode | Purpose | Command |
|---|---|---|
| **Mirror** (read-only) | Just clone repo + watch Mac via rsync | (no collectors run on Windows) |
| **Active replica** (parallel) | Both Mac + Windows collect (duplicate data, gets dedup'd via PRIMARY KEY) | Run all collectors |
| **Takeover** (Mac stops) | Windows is the new primary | Run all + stop Mac collectors via SSH |

**Recommended: start with Mirror mode**, verify everything cloned correctly, then escalate.

---

## Collectors to run (in order)

```powershell
$LOG = "D:\BWE\30_DATA\binance_collectors_runtime\logs"
$PY = "D:\BWE\runtime-venv\Scripts\python.exe"
$SCRIPTS = "D:\BWE\infrastructure\collectors"
$ENV:HTTP_PROXY = "http://127.0.0.1:7897"
$ENV:HTTPS_PROXY = "http://127.0.0.1:7897"

# 1. BWE matrix listener (writes bwe_matrix_posts.jsonl)
Start-Process -NoNewWindow $PY @($SCRIPTS\bwe_matrix_monitor.py, "--posts-log", "D:\BWE\30_DATA\bwe_logs\bwe_matrix_posts.jsonl", "--health-log", "D:\BWE\30_DATA\bwe_logs\bwe_matrix_health.jsonl") -RedirectStandardOutput $LOG\bwe_matrix.log

# Wait 30 sec between each collector to avoid 418 ban burst

# 2. Binance kline collectors (1m / 3m / 5m / 15m / 1h)
foreach ($itv in '1m','3m','5m','15m','1h') {
    Start-Process -NoNewWindow $PY @($SCRIPTS\binance_futures_1m_collector.py, "--config", "$SCRIPTS\configs\binance_futures_${itv}_collector_config.json") -RedirectStandardOutput "$LOG\${itv}_collector.log"
    Start-Sleep 30
}

# 3. Binance metric / 24h_ticker / index_price
Start-Process -NoNewWindow $PY @($SCRIPTS\binance_futures_metric_collector.py, "--config", "$SCRIPTS\configs\binance_futures_metric_collector_config.json") -RedirectStandardOutput $LOG\metric.log
Start-Sleep 30
Start-Process -NoNewWindow $PY @($SCRIPTS\binance_24h_ticker_collector.py) -RedirectStandardOutput $LOG\ticker24h.log
Start-Process -NoNewWindow $PY @($SCRIPTS\binance_index_price_collector.py) -RedirectStandardOutput $LOG\index_price.log

# 4. OKX + Bybit liquidation (DIRECT, no proxy)
$ENV:HTTP_PROXY = ""
$ENV:HTTPS_PROXY = ""
Start-Process -NoNewWindow $PY @($SCRIPTS\okx_liquidation_collector.py) -RedirectStandardOutput $LOG\okx_liq.log
Start-Process -NoNewWindow $PY @($SCRIPTS\bybit_liquidation_collector.py) -RedirectStandardOutput $LOG\bybit_liq.log
```

For 24/7 operation, use **Windows Task Scheduler** or **NSSM** (Non-Sucking Service Manager):
```powershell
winget install nssm.nssm
nssm install BWE-1m-Collector "D:\BWE\runtime-venv\Scripts\python.exe" "D:\BWE\infrastructure\collectors\binance_futures_1m_collector.py --config ..."
# repeat for each collector
```

---

## Verification checklist

Agent must verify each ✅:

- [ ] `git clone` succeeds, `D:\BWE` populated
- [ ] Python 3.11+ installed, venv created
- [ ] websocket-client + requests + pyyaml + pandas installed
- [ ] Clash Verge running, Tun mode ON
- [ ] `curl https://fapi.binance.com/fapi/v1/exchangeInfo` → HTTP 200
- [ ] `curl https://www.okx.com/api/v5/public/instruments?instType=SWAP` → 200 direct (no proxy)
- [ ] BWE Telegram session authenticated (`bwe_matrix_state.json` exists)
- [ ] All collectors started (10+ Python processes)
- [ ] `D:\BWE\30_DATA\binance_collectors_runtime\binance_futures_1m.sqlite3` created and growing
- [ ] `bwe_matrix_posts.jsonl` receiving new lines (telegram listener alive)
- [ ] OKX liquidations table accumulating rows

---

## Sync data Mac ↔ Windows (optional)

Two ways to keep Mac & Windows DBs in sync:

### Option A: Tailscale + rsync

1. Install Tailscale on both machines
2. Sign in same account
3. Mac IP: `tailscale ip -4` → `100.x.x.x`
4. Windows can `rsync mac:/Volumes/T9_HOT/binance_collectors_runtime/binance_futures_1m.sqlite3 ...` periodically

### Option B: GitHub-only (this approach)

DBs aren't in git. Both machines collect independently. They diverge but converge over time as both have same incoming data (binance/OKX/bybit are the source of truth).

**Recommended: Option B** — simpler, no sync overhead, both machines stay independent.

---

## What's intentionally NOT in this repo (must transfer separately)

| Item | Size | How to transfer |
|---|---|---|
| `~/.hermes/.env` | small | password manager / encrypted USB |
| Mac BWE Telegram session file | small | scp from Mac → Windows |
| `binance_futures_1m.sqlite3` (live) | ~22 GB | optional via Tailscale rsync; otherwise let Windows backfill 30d (1-2 hours) |
| `30_DATA/cache`, `30_DATA/reference` | 46 GB | Mac-only research caches; not needed on Windows |
| `40_EXPERIMENTS/all_runs_archive` | 10 GB | Mac-only historical experiments; not needed |
| Clash Verge full profile (with creds) | small | manually configure via Proton account on Windows |

---

## After setup is confirmed, ask user:

1. **Mode**: Mirror / Active replica / Takeover?
2. **Telegram channels**: same channels as Mac, or new set?
3. **Paper-LIVE**: run on Windows too, or Mac-only?
4. **Backtest research**: run heavy `BWE_codex/` jobs here?

Then proceed accordingly.

---

## Important guardrails (mirror Mac CLAUDE.md)

- 🚫 **Never trade live with real funds without explicit user confirmation per trade**
- 🚫 **Never edit `.env` to commit credentials**
- 🚫 **Never auto-promote a backtest winner to live**
- ✅ **Always use testnet for paper validation**
- ✅ **Stability over absolute return** (sort by stability_score, not mean_return)
- ✅ **Sandbox-only**: experiments under `40_EXPERIMENTS/<run_id>/`, reports under `50_ANALYSIS_REPORTS/`

---

## End of prompt — agent should now:

1. Read all the docs listed above
2. Run the install commands
3. Configure proxy + .env
4. Test each verification step
5. Ask user which mode (mirror/replica/takeover) before starting collectors
6. Report back with status of all checks
