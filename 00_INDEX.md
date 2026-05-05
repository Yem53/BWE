---
type: home
tags: [moc, home]
created: 2026-05-02
status: active
---

# 🌐 BWE Project — Vault HOME

**Binance Whale Event** 自动研究项目 — Telegram 消息触发 + binance K 线 + GPU 搜索 → 找最优 entry × exit 策略组合.

> **当前状态**: Round 5 paper-LIVE-testnet 验证中 (2026-05-02). 真实 alpha 待 1 周数据确认.

---

## 🗺 Map of Content (按 9 大区域)

| 区域 | 内容 | MOC |
|---|---|---|
| 📌 **00 项目需求** | 业务目标 / 资金 / 安全规则 | [[00_PROJECT_REQUIREMENTS_MOC]] |
| 💻 **20 代码** | autoresearch loop + LLM team | [[20_CODE_MOC]] |
| 📊 **30 数据** | binance kline + BWE 消息 + caches | [[30_DATA_MOC]] |
| 🔬 **40 实验** | Round 1-5 + paper-shadow + V4 archives | [[40_EXPERIMENTS_MOC]] |
| 📝 **50 分析报告** | Stage 输出 + cross-round 对比 | [[50_ANALYSIS_REPORTS_MOC]] |
| 🚀 **60 下一轮** | V5 search prompt + Round 6 audit | [[60_NEXT_ROUND_MOC]] |
| 🔗 **90 源数据指针** | 外部数据 source 索引 | [[90_SOURCE_POINTERS_MOC]] |
| 🛠 **99 管理** | active plans + 会话日志 | [[99_ADMIN_MOC]] |
| 🧠 **Auto Memory** | Claude 跨会话记忆 | [[.claude_memory_shared/MEMORY]] |

---

## 🔥 Quick Links — 当前 Active

### 🟢 实时运行 (Paper-LIVE + Testnet)
- [[40_EXPERIMENTS/round5/paper_shadow/MORNING_BRIEFING|Morning Briefing]] — 整夜运行总结
- [[40_EXPERIMENTS/round5/specs/PAPER_BACKTEST_DRIFT_LOG|Paper-Backtest Drift Log]] — 14+ drift 持续追踪
- [[30_DATA/binance_collectors_runtime/MIGRATION_LOG|Migration Log]] — Mac → T9 迁移记录
- [[40_EXPERIMENTS/v8_5090_paper_shadow_20260504_2347/paper_gate_summary|V8 5090 paper gate]] — 20 signal-only candidates; no order endpoints

### 📋 当前 Round 计划
- [[40_EXPERIMENTS/round5/specs/2026-05-01-v5-search-prompt|V5 Search Prompt]] — 下一轮 30d backtest 设计
- [[40_EXPERIMENTS/round5/specs/2026-04-30-v4-entry-search-archive|V4 Entry Archive]] — winner: CHAMP +7.96% mean
- [[40_EXPERIMENTS/round5/specs/2026-04-30-v4-exit-search-archive|V4 Exit Archive]] — 4 best exits

### 🛡 设计原则 (必读)
- [[40_EXPERIMENTS/round5/specs/BWE_PROJECT_DESIGN_RULES|BWE Project Design Rules]] — 10 核心原则 + Rule #0 数据驱动
- [[CLAUDE|CLAUDE.md]] — 项目级 Claude 指令
- [[AGENTS|AGENTS.md]] — agent 编排规则

### 📊 数据状态 (T9)
- 39 GB total in `30_DATA/`
- 1m/3m/5m/15m/1h klines: 30 day complete
- 1s klines: backfilling 30d (~12h to complete)
- BWE Telegram messages: 2 MB live + 21 MB monitoring

---

## 🎯 关键策略 / Concepts

### Strategy taxonomy
- **SHORT-fade-pump**: BWE 检测 pump → SHORT 等回落 (主力策略)
- **LONG-trend-follow**: 妖币 trending → 跟随做多 (条件化, 未测足)
- **Wick reversion**: 1m bar 上影针刺 → 反转 (实验中)
- **Range trading**: 庄家拉爆多空 → 双向收割 (设计中)

### 13 Active Paper Strategies
- [[40_EXPERIMENTS/round5/paper_shadow/STRATEGIES_LIVE|strategies_live.json (13 strategies)]]
  - 4 Legacy: ST15v2/v3, ST8, ST9
  - 9 V4 matrix: BROAD/CHAMP/QUAL × AGG/SAFE/SAFEST

### Frequency / Cadence
- BWE event arrival: ~5-15 events/h (varies by regime)
- Paper-LIVE poll: 1s
- 1m collector poll: 60s
- Heartbeat: 5min to Telegram

---

## 🧪 测试 + 验证

### 已修复 14+ Drifts (paper ↔ backtest 一致性)
1-7: D1-D7 (entry/ATR/PnL/look-ahead in BT)
8-14: D8-D14 (paper kline write delay, max_concurrent, ATR formula, etc.)
15: D15 — Paper-LIVE mark price API mode (NEW)
16: D16 — Testnet real order placement (NEW)

### 性能基准
- Backtest CHAMP 30d (含 look-ahead): mean +10%, sum +16,016%
- Paper-LIVE testnet 7h: mean -3.46%, sum -110.8% (single-coin LABUSDT 集中)
- 真实 live alpha 估计: +1~3% mean per trade (after friction)

---

## 🔧 工具 + 命令

### Daily 启动
```bash
# 重启 paper-LIVE
bash /Volumes/T9/BWE/40_EXPERIMENTS/round5/paper_shadow/restart_live.sh

# 重启所有 collector
bash /Volumes/T9/BWE/30_DATA/binance_collectors_runtime/restart_all_collectors.sh

# 看 paper-LIVE 状态
ps -p $(cat /Volumes/T9/BWE/40_EXPERIMENTS/round5/paper_shadow/runtime_live/paper_shadow_live.pid)

# Tail logs
tail -f /Volumes/T9/BWE/40_EXPERIMENTS/round5/paper_shadow/runtime_live/logs/paper_shadow_live.log
```

### SQL 查 DB
```bash
sqlite3 /Volumes/T9/BWE/30_DATA/binance_collectors_runtime/binance_futures_1m.sqlite3
# 然后:
SELECT interval, COUNT(*) FROM klines_1m GROUP BY interval;
```

---

## 📚 Templates

新建 note 时用 [[Templates/Strategy_Template]] / [[Templates/_FOLDER_INDEX|All Templates]] /  [[Templates/Drift_Template]] / [[Templates/Daily_Note_Template]] / [[Templates/Plan_Template]]

---

## 🏷 Tags 系统

| Tag | 含义 |
|---|---|
| #strategy | 策略文件 (entry/exit) |
| #drift | 一致性 drift 记录 |
| #experiment | 单次实验 |
| #plan | 实施计划 |
| #spec | 设计文档 |
| #archive | 老版本归档 |
| #live | 实时运行中 |
| #paper | paper trading 数据 |
| #testnet | testnet 真实下单 |
| #moc | Map of Content (导航) |
| #wip | 进行中 |
| #blocked | 被阻塞 |
| #priority/high #priority/med #priority/low | 优先级 |

---

## 🌐 跨设备同步

Vault 在 `/Volumes/T9/BWE/` (4TB exFAT, 跨 Mac/Win 通用). Claude memory 在 `.claude_memory_shared/` 跟 Mac local `~/.claude/projects/` 双向 sync.

---

## 🤖 Claude Code 集成

CLAUDE.md 配置: 任何 *新建 / 删除 / 大方向调整* 操作, Claude 自动同步到此 vault. 见 [[CLAUDE]] 详细规则.
