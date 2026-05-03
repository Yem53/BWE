# BWE Autoresearch — Project Context (auto-loaded)

> This file lives on the **H: drive** and is auto-loaded by Codex on any
> machine where the project is opened. It contains stable project-level
> memory that persists across machines (5090 Windows ↔ Mac mini macOS).
>
> Auto-learned per-conversation memory mirrors to `.claude_memory_shared/`
> on this drive in addition to each machine's local `~/.Codex/projects/...`.

## Project identity

**BWE = Binance Whale Event** — Telegram-driven crypto trading research
project. Goal: find optimal **(entry × exit) strategy combinations** by
combining BWE channel messages + corresponding kline + Binance trading
data, using a **Karpathy-style autoresearch loop** that maxes out the 5090
GPU.

**User's exact words (2026-04-26):**
> "结合 BWE 的消息，加上消息对应时间的交易对 K 线图和 binance 其它的交易数据，
> 然后使用 GitHub 项目 auto research 的架构，榨干 5090 的算力，然后去寻找
> 最优的开仓和平仓的策略组合。"

Everything must align to four scoring dimensions:
1. **Data completeness** — message + kline + other Binance data joined
2. **Architecture fidelity** — Karpathy autoresearch loop (single-file
   discipline, fixed time budget, NEVER STOP, results.tsv per-experiment
   commit)
3. **5090 utilization** — GPU actively scoring, not 90%+ idle
4. **Optimization depth** — true joint search of entry × exit, not just
   one-sided

## Capital + risk posture

- **$1000 USDT** trading capital
- **5-10% per-trade sizing**
- "正收益就上 live" — any positive expectancy → promote (after gates)
- User trades from Mac mini, **not** from 5090

## Three Telegram channels

| Channel | Behavior | Default side |
|---|---|---|
| `BWE_OI_Price_monitor` (方程式 OI&Price 异动) | OI 异动 + 价格变化 | mostly short |
| `BWE_pricechange_monitor` (方程式价格异动监测) | Price moves | long+short mix |
| `BWE_Reserved6` (方程式重大行情提醒) | 180s 内 8-15% 极端行情 | mostly short |

## Hard rules (sandbox-only)

1. NEVER read or print API keys / tokens / secrets
2. NEVER edit live autotrader configs
3. NEVER call Binance/OKX order endpoints (testnet included, unless
   explicitly authorized)
4. NEVER auto-promote a backtest winner to live — must pass paper-shadow
   + journal penalty + **explicit user confirmation**
5. All experiment artifacts go under `40_EXPERIMENTS/<run_id>/`,
   reports under `50_ANALYSIS_REPORTS/`, never the H:\ root
6. Stability over absolute return — primary sort key is `stability_score`,
   not `mean_return`

## Cross-machine workflow

**H: drive (4TB exFAT, label "T9") is the canonical project location.**
It travels between machines:

```
[Mac mini, 24/7 main]                      [5090 Windows, on-demand]
  H: as /Volumes/T9                          H: as H:\
  - Live Binance trading bot                 - 20K-class GPU loop
  - BWE Telegram listener                    - LLM debate pipeline
  - Codex primary                      - Heavy backtest scoring
  - Read morning_brief / decide              - (H: only when computing)
  - Paper shadow + small analyses            - Pull H: out → Mac when done
```

Default workflow:
1. H: stays on Mac mini for daily work
2. When a major loop is needed: pause live bot → move H: to 5090 → run →
   move back → resume bot
3. Code edits happen on Mac mini (via Codex on `/Volumes/T9/BWE`)

## LLM debate config (Round 4+)

All `Codex -p` subprocess calls in `bwe_autoresearch/bwe_loop_llm_team.py`
use **maximum-quality** config by default:

- `--model Codex-opus-4-7` (1M context, 64K output)
- `--effort max` (deepest extended-thinking budget)
- `--exclude-dynamic-system-prompt-sections` (better cache reuse)
- Override per-run via `BWE_LLM_EFFORT=low` env var if needed

User has Max $200/mo plan with plenty of headroom — do NOT downgrade
"to save money" or "to be faster".

Round 3 (the in-flight debate at the moment this file was created) did
not have `--effort max` — that was intentional to not interrupt a
running pipeline. Round 4+ defaults to max.

## Key paths

```
H:/BWE/
├── 00_PROJECT_REQUIREMENTS/    # docs, prompts, configs, runbooks
├── 20_CODE/Autoresearch/       # main code
│   ├── bwe_autoresearch/       # core loop + LLM team
│   ├── prompts/                # 11 LLM role prompts (TEAM_PHILOSOPHY.md)
│   └── scripts/                # analyze, rescore, paper_shadow, brief
├── 30_DATA/                    # raw + cached data
├── 40_EXPERIMENTS/             # results.tsv, debates/, paper_shadow/
│   ├── hypothesis_registry.jsonl   # 523 archetypes (200E + 100X + 120F + 40R + 60C + 3 LLM)
│   ├── results.tsv             # per-combo loop output
│   ├── analysis/               # per-channel/exit-family stats + rescore_v2
│   ├── debates/<ts>/           # LLM debate artifacts per run
│   └── morning_brief_latest.md # daily Chinese summary (auto-generated)
├── 50_ANALYSIS_REPORTS/
├── 60_NEXT_ROUND/
├── 90_SOURCE_POINTERS/
├── 99_ADMIN/                   # day1_active_plan.md, pid files, logs
├── .claude_memory_shared/      # mirror of ~/.Codex memory (portable)
├── README.md
└── 中文导航.md
```

External (not on H:):
- Karpathy autoresearch original: `https://github.com/karpathy/autoresearch`
- Local clone (Mac): `/Users/ye/Desktop/Github/Autoresearch`
- Local snapshot (H:): `H:/BWE/20_CODE/Autoresearch/`
- Telegram raw exports (Mac only):
  - `/Users/ye/Desktop/Telegram/方程式价格异动监测_history/result.json`
  - `/Users/ye/Desktop/Telegram/方程式OI&Prce异动_history/result.json`
  - `/Users/ye/Desktop/Telegram/方程式重大行情提醒 Important Price Alerts Only_history/result.json`

## Active plan + current state

**Read this first when entering a new conversation:**
👉 `H:/BWE/99_ADMIN/day1_active_plan.md`

This file is the single source of truth for which Day / Round / phase
we're in. As of 2026-04-27 the project has finished its 20K loop
and is mid-Round 3 deep debate.

## Plugin preferences

User prefers `Codex-mem@thedotmack` and
`superpowers@superpowers-marketplace`. If their slash commands
(`/brainstorm`, `/execute-plan`, `/write-plan`, `/mem-search`,
`/smart-explore`) don't appear, suggest restarting Codex.

## Auto-memory sync rule (critical)

When saving any new auto-memory file (`feedback_*.md`, `project_*.md`,
`reference_*.md`, etc.), **always write it to BOTH locations**:

1. `~/.Codex/projects/<machine-specific-hash>/memory/<file>.md`
   (Codex's local cache — needed for auto-load on this machine)
2. `H:/BWE/.claude_memory_shared/<file>.md`
   (canonical, travels with the H: drive between machines)

Same applies to `MEMORY.md` (the index). Both copies must stay in sync.

When opening Codex on a new machine where `~/.Codex/projects/<hash>/memory/`
is empty, copy the contents of `H:/BWE/.claude_memory_shared/` into it
once before starting real work — that bootstraps the local cache. Going
forward, every edit goes to both locations.

User's exact request (2026-04-27):
> "现在就做，然后之后的每一步都需要将这些memory注入到硬盘中"


<claude-mem-context>
# Memory Context

# [BWE] recent context, 2026-05-02 4:53pm EDT

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (24,749t read) | 1,158,241t work | 98% savings

### May 1, 2026
290 12:10p 🔵 PnL calculation discrepancies discovered in legacy v2/v3 exit engine
### May 2, 2026
301 11:15a 🔵 MCP startup failures on session initialization
302 11:16a 🔵 MCP server configuration audit for failing claude_mem and cloudflare-api
303 11:17a 🔵 claude_mem MCP failure root cause: wrapper script points to deleted Desktop path instead of plugin cache
304 " 🔵 Stale claude_mem wrapper script failure confirmed and traced to incomplete April 22 upgrade
305 11:18a 🔴 Fixed claude_mem MCP wrapper to auto-discover plugin location instead of hardcoded stale path
306 11:19a 🔵 claude_mem wrapper fix verified; cloudflare-api cannot be removed via codex mcp remove
307 " 🔴 Disabled cloudflare plugin to resolve OAuth token refresh startup failure
308 11:20a 🔵 claude_mem MCP handshake verified successful with protocol smoke test
309 " 🔵 End-to-end codex exec verification successful - no MCP startup errors
310 11:22a ✅ Upgraded codex CLI from 0.125.0 to 0.128.0 latest release
311 " 🔵 Codex 0.128.0 upgrade verified working with fixed MCP configuration
312 11:25a 🔵 Goal tracking system not available in current environment
313 11:26a 🔵 TeamCreate and TaskCreate are Claude Code built-in tools, not goal registry
314 11:27a 🔵 Claude environment has tasks but no active teams; goal registry never existed in current setup
315 11:33a 🔵 Codex goals feature flag exists but CLI interface not yet implemented
316 11:34a 🔵 Codex goals feature fully implemented but gated behind feature flag
317 " 🔵 Codex thread_goals database schema confirmed with status lifecycle states
318 11:35a 🔵 Codex goals feature successfully activated in interactive TUI after enabling flag
319 11:45a 🔵 BWE project architecture and cross-machine workflow discovered
320 " 🔵 Claude Code workflow rules and safety boundaries identified
321 11:47a 🔵 BWE project data-driven design rules and historical mistakes catalog
322 " 🔵 Round 6 architecture audit reveals fundamental BWE design flaw and 6 structural errors
323 " 🔵 BWE project current scale and Round 5 paper-LIVE-testnet validation status
324 11:52a 🔵 BWE infrastructure process inventory
325 11:53a 🔵 SQLite database query timeout and locking issue
326 " 🔵 BWE matrix monitor architecture and channel configuration
327 11:58a 🔵 Obsidian vault integration with Claude Code automation rules
328 12:09p 🟣 BWE Codex auxiliary workspace initialized
329 12:13p 🔵 T9 external drive infrastructure verified
330 " 🔵 T9 drive I/O performance benchmarked with SQLite journal mode trade-offs
331 12:14p 🔵 Live Binance collector database has 12GB WAL file posing operational risk
332 " ✅ T9 infrastructure audit report and cross-agent handoff created
333 12:17p 🔵 Internal APFS performance benchmarked, showing 2.8x faster sequential I/O but unexpected WAL behavior
334 " 🔵 Single-connection SQLite benchmark reveals APFS is 38-43x faster than exFAT for commits
335 12:18p ⚖️ SQLite storage architecture decision documented with APFS migration recommendation
336 12:29p 🔵 BWE strategy research current state and methodology review
337 12:30p ⚖️ Microsoft Qlib evaluated as sidecar research tool for BWE, not pipeline replacement
338 12:39p 🔵 T9 external drive configured as 4TB exFAT with 309GB used and 154GB in recycle bin
339 1:05p ⚖️ BWE notifications are informational only, no scoring needed
340 1:07p 🔴 Paper shadow live runner crashed on Binance testnet API failure
341 " 🔵 Round5 paper shadow has 13 live strategies with mixed testnet performance
342 1:09p 🔵 V4 drift-fixed backtest shows +10-12% mean across 3800 events over 30 days
343 " 🔵 Paper shadow live ran 10.5 hours with -4.1% mean and -$89.83 testnet PnL across 13 strategies
344 1:10p 🔵 Morning briefing documented early +$22.50 profit, session ended 10 hours later at -$89.83
345 " 🔵 D15 implicit look-ahead bias hypothesis estimates 7-9% performance degradation from backtest to live
346 " ✅ Created round5 paper strategy snapshot reports documenting backtest vs live performance gap
350 4:49p 🔵 Memory retrieval for recent session context
351 4:51p 🔵 Investigation of session failure after folder migration to T9_COLD
352 " 🔵 Confirmed path migration from /Volumes/T9/BWE to /Volumes/T9_COLD/BWE

Access 1158k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>