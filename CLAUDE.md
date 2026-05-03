# BWE Autoresearch — Project Context (auto-loaded)

> This file lives on the **H: drive** and is auto-loaded by Claude Code on any
> machine where the project is opened. It contains stable project-level
> memory that persists across machines (5090 Windows ↔ Mac mini macOS).
>
> Auto-learned per-conversation memory mirrors to `.claude_memory_shared/`
> on this drive in addition to each machine's local `~/.claude/projects/...`.

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
[Mac mini, 24/7 PRIMARY]                  [5090 Windows, GPU on-demand]
  H: as /Volumes/T9                          H: as H:\ (only when computing)
  - All LLM debate rounds                    - 20K-class GPU loop
  - All pipeline orchestration               - GPU first-touch scoring
  - Live Binance trading bot                 - (Plug H: in only for the run)
  - BWE Telegram listener
  - Claude Code primary
  - Read morning_brief / decide
  - Paper shadow + analyses
```

**Default workflow** (post-2026-04-27 migration to Mac mini):
1. H: stays on Mac mini for ~all work
2. When a major GPU loop is needed: pause live bot → move H: to 5090 →
   run → move back → resume bot
3. Code edits happen on Mac mini (via Claude Code on `/Volumes/T9/BWE`)
4. Round N LLM debates run silently on Mac (no Windows console flashing)

**Mac setup**: see `20_CODE/Autoresearch/MAC_MIGRATION.md` for full details.
Quick start on Mac:
```
cd /Volumes/T9/BWE/20_CODE/Autoresearch
bash scripts/mac_setup.sh
```

**Cross-platform path resolution**: all scripts use `bwe_autoresearch.bwe_paths`
which auto-detects `BWE_ROOT` from the env var, file location, or common
mount points. No hardcoded `H:/BWE/...` paths remain in critical scripts.

## LLM debate config (Round 4+)

All `claude -p` subprocess calls in `bwe_autoresearch/bwe_loop_llm_team.py`
use **maximum-quality** config by default:

- `--model claude-opus-4-7` (1M context, 64K output)
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
├── .claude_memory_shared/      # mirror of ~/.claude memory (portable)
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

User prefers `claude-mem@thedotmack` and
`superpowers@superpowers-marketplace`. If their slash commands
(`/brainstorm`, `/execute-plan`, `/write-plan`, `/mem-search`,
`/smart-explore`) don't appear, suggest restarting Claude Code.

## Auto-memory sync rule (critical)

When saving any new auto-memory file (`feedback_*.md`, `project_*.md`,
`reference_*.md`, etc.), **always write it to BOTH locations**:

1. `~/.claude/projects/<machine-specific-hash>/memory/<file>.md`
   (Claude Code's local cache — needed for auto-load on this machine)
2. `H:/BWE/.claude_memory_shared/<file>.md`
   (canonical, travels with the H: drive between machines)

Same applies to `MEMORY.md` (the index). Both copies must stay in sync.

When opening Claude Code on a new machine where `~/.claude/projects/<hash>/memory/`
is empty, copy the contents of `H:/BWE/.claude_memory_shared/` into it
once before starting real work — that bootstraps the local cache. Going
forward, every edit goes to both locations.

User's exact request (2026-04-27):
> "现在就做，然后之后的每一步都需要将这些memory注入到硬盘中"

## 🌐 Obsidian Vault sync rule (2026-05-02 加)

### Vault 位置
`/Volumes/T9/BWE/` 整个目录是 Obsidian vault (`.obsidian/` 已配置).
HOME = `00_INDEX.md`. 9 个 MOC 在每个区域目录 (`00_PROJECT_REQUIREMENTS_MOC.md`, `20_CODE_MOC.md`, etc).

### 核心 sync rule (默认行为)

每当 Claude 在 BWE 项目里做以下任一操作, **必须自动同步更新对应 vault entry**:

1. **新建 strategy / spec / plan / drift entry**:
   - Use `Templates/Strategy_Template.md` / `Templates/Plan_Template.md` / `Templates/Drift_Template.md` / `Templates/Experiment_Template.md` 作模板
   - 添加 frontmatter (type, tags, created, status)
   - 用 ``[[wikilink]]`` 互相 link 相关 notes
   - 在对应区域 MOC 里加引用 (例如新 strategy 加到 `40_EXPERIMENTS_MOC.md`)

2. **删除 / 归档 strategy / spec / plan**:
   - 改 frontmatter `status: archived` 或 `status: deleted`
   - 加 tag `#archive`
   - 不直接 rm 文件 (Obsidian backlinks 会断)
   - 在对应 MOC 里的 link 加 ``[[xxx]]` #archive` 标记

3. **大方向调整 / Round 切换 / 关键决策**:
   - 更新 `00_INDEX.md` 的 "🔥 Quick Links — 当前 Active" 区
   - 更新 `99_ADMIN_MOC.md` 的 "当前状态" 区
   - 写 daily note (`99_ADMIN/daily/YYYY-MM-DD.md`) 用 `Templates/Daily_Note_Template`
   - 在 `60_NEXT_ROUND_MOC.md` 的 "待启动 Items" 加 / 移项

4. **新代码文件 / 删代码文件**:
   - 更新 `20_CODE_MOC.md`
   - 在相关 spec / plan 里 backlink

5. **数据迁移 / 文件系统改动**:
   - 更新 `30_DATA_MOC.md`
   - 写 migration log (例 `MIGRATION_LOG.md`)
   - 更新 `00_INDEX.md` data status 区

### Sync 工作流 (具体命令)

```python
# 1. 新建 note 时, 用 frontmatter 模板:
"""
---
type: strategy / drift / plan / experiment / daily
tags: [tag1, tag2]
created: YYYY-MM-DD
status: design / wip / done / archived
priority: high / med / low
---

# Title
...
"""

# 2. Wikilink 跨 note 引用:
"[[../40_EXPERIMENTS/round5/specs/PAPER_BACKTEST_DRIFT_LOG|Drift Log]]"

# 3. 对应 MOC 必更新:
# - 新策略 → 40_EXPERIMENTS_MOC.md
# - 新数据 → 30_DATA_MOC.md
# - 新计划 → 60_NEXT_ROUND_MOC.md
# - 新会话 → 99_ADMIN/daily/

# 4. .claude_memory_shared/MEMORY.md 也同步加 link
```

### 不要做的事

- ❌ 不要直接 rm vault note (backlinks 断, 用 status: archived 替代)
- ❌ 不要建 note in vault root 顶层 (放对应区域子目录)
- ❌ 不要写 frontmatter 里 type 但 不加 tag (graph view 会乱)
- ❌ 不要忘 update 对应 MOC (孤儿 note 不被找到)

### 用户使用指引

- HOME: `00_INDEX.md` 是 vault 入口, navigate 全靠这个
- Cmd+O: quick switcher 跳到任何 note
- Cmd+Shift+F: global search 全文 + tag
- Cmd+G: graph view 看 knowledge graph
- Cmd+Shift+B: backlinks 看谁引用了当前 note
- Cmd+T: insert template (with template plugin)
- 新 daily note: Cmd+Alt+D

