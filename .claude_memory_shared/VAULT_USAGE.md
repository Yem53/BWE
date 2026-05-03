---
type: guide
tags: [moc, guide, obsidian]
created: 2026-05-02
---

# 📖 BWE Vault 使用指南

> 把 BWE 项目 folder 升级成 Obsidian vault 之后, 怎么用 + 它给你的能力提升.

## 🗺 Vault 结构

```
/Volumes/T9/BWE/                ← Vault root (整个 BWE 项目就是 vault)
├── 00_INDEX.md                 ← HOME, vault 入口
├── CLAUDE.md                   ← 项目级 Claude 指令 + sync rule
├── AGENTS.md                   ← agent 编排规则
├── README.md                   ← 项目 overview
├── VAULT_USAGE.md              ← 本文件
├── Templates/                  ← Note templates
│   ├── Daily_Note_Template.md
│   ├── Strategy_Template.md
│   ├── Drift_Template.md
│   ├── Plan_Template.md
│   └── Experiment_Template.md
├── 00_PROJECT_REQUIREMENTS/    ← 业务需求 + safety rules
│   └── 00_PROJECT_REQUIREMENTS_MOC.md
├── 20_CODE/                    ← Autoresearch + LLM team
│   └── 20_CODE_MOC.md
├── 30_DATA/                    ← Binance kline + BWE messages
│   ├── 30_DATA_MOC.md
│   ├── binance_collectors_runtime/  (T9 12GB DB)
│   └── bwe_logs/
├── 40_EXPERIMENTS/             ← Round 1-5 + paper-shadow
│   ├── 40_EXPERIMENTS_MOC.md
│   └── round5/
│       ├── specs/              (设计文档 + drift log)
│       ├── plans/              (实施计划)
│       ├── src/                (主代码)
│       └── paper_shadow/       (paper trader 跑步中)
├── 50_ANALYSIS_REPORTS/        ← Stage 输出 + cross-round 对比
│   └── 50_ANALYSIS_REPORTS_MOC.md
├── 60_NEXT_ROUND/              ← V5 + Round 6 计划
│   └── 60_NEXT_ROUND_MOC.md
├── 90_SOURCE_POINTERS/         ← 外部数据 source
│   └── 90_SOURCE_POINTERS_MOC.md
├── 99_ADMIN/                   ← Daily notes + active plans
│   ├── 99_ADMIN_MOC.md
│   └── daily/                  (每日 log)
├── .obsidian/                  ← Obsidian 配置
│   ├── core-plugins.json
│   ├── templates.json          (Templates folder pointer)
│   ├── daily-notes.json        (daily folder + format)
│   ├── hotkeys.json            (快捷键)
│   └── graph.json              (graph view config)
└── .claude_memory_shared/      ← Claude 跨会话记忆
    └── MEMORY.md
```

## 🔧 怎么打开 vault

```bash
# 1. 打开 Obsidian app
# 2. "Open folder as vault"
# 3. 选 /Volumes/T9/BWE/
# 4. Vault 加载 561 个 .md files
# 5. 从 00_INDEX.md 开始 navigate
```

## ⌨ 关键 Hotkeys (已配置)

| 快捷键 | 功能 |
|---|---|
| `Cmd+O` | Quick switcher — 跳到任何 note |
| `Cmd+Shift+F` | Global search 全文 + tag |
| `Cmd+G` | Graph view — 看 knowledge graph |
| `Cmd+Shift+B` | Backlinks — 看谁引用当前 note |
| `Cmd+T` | Insert template |
| `Cmd+Alt+D` | 新 daily note |
| `Cmd+P` | Command palette |
| `[[` | Wiki link autocomplete |
| `#` | Tag autocomplete |

## 📝 新建 Note 的 5 种工作流

### 1. 新策略
```
Cmd+O → 输入 "Templates/Strategy_Template" → Cmd+Enter copy
改 frontmatter (type, tags, status, side, hold_min)
保存到 40_EXPERIMENTS/round5/specs/2026-MM-DD-strategy-name.md
在 40_EXPERIMENTS_MOC.md 加 [[link]]
```

### 2. 新 drift
```
用 Templates/Drift_Template
保存到 40_EXPERIMENTS/round5/specs/PAPER_BACKTEST_DRIFT_LOG.md (现有)
加 D__ section
更新主 drift log
```

### 3. 新 plan
```
用 Templates/Plan_Template
保存到 40_EXPERIMENTS/round5/plans/YYYY-MM-DD-plan-name.md
在 60_NEXT_ROUND_MOC.md 加 link
```

### 4. 新 experiment
```
用 Templates/Experiment_Template
保存到 40_EXPERIMENTS/round5/experiments/YYYY-MM-DD-experiment.md
在 40_EXPERIMENTS_MOC.md 加 link
```

### 5. Daily note
```
Cmd+Alt+D → 自动用 Daily_Note_Template
保存到 99_ADMIN/daily/YYYY-MM-DD.md
记录今天的发现 + 决策
```

## 🏷 Tags 系统 (用于过滤 + graph 着色)

```
#strategy        策略文件 (entry/exit)
#drift           一致性 drift 记录
#experiment      单次实验
#plan            实施计划
#spec            设计文档
#archive         老版本归档 (status: archived)
#live            实时运行中
#paper           paper trading
#testnet         testnet 真实下单
#moc             Map of Content
#wip             进行中
#blocked         被阻塞
#priority/high   高优先
#daily/YYYY-MM   每日 log (自动按月分组)
```

## 🤖 Claude 自动 sync (CLAUDE.md 里的规则)

每次 Claude 做以下操作, 自动 vault sync:

| 操作 | Claude 自动做 |
|---|---|
| 新策略 | 用 Strategy_Template + 加 MOC link |
| 删/归档策略 | status: archived + #archive tag (不删文件) |
| Round 切换 | 改 00_INDEX.md "Quick Links" + 99_ADMIN_MOC |
| 大方向调整 | daily note + 60_NEXT_ROUND_MOC 移项 |
| 新代码文件 | 加到 20_CODE_MOC |
| 数据迁移 | 加到 30_DATA_MOC + 写 migration log |
| 修 drift | 加到 PAPER_BACKTEST_DRIFT_LOG |

## 🚀 这个升级给你带来的 6 大提升

### 1. **Knowledge Graph (图谱)**
- Cmd+G 看到所有 561 个 .md 之间的引用关系
- 哪个 strategy 用了哪个 drift fix? 一目了然
- 孤儿 note 自动 highlight (orphan), 知道哪些没 link 进系统

### 2. **Backlinks (反向引用)**
- 打开任何 note, 自动看谁引用了它
- 例: Drift Log 显示 paper-LIVE / V4 archive / Round 6 audit 都 reference 它
- 改一个 drift 知道影响哪些 specs

### 3. **快速搜索 + Tag 过滤**
- Cmd+Shift+F: 全文 + frontmatter 搜索
- 例: "tag:#strategy AND tag:#live AND status:wip"
- Tag pane 一键看所有 #drift / #experiment

### 4. **Templates 提速 note 创建**
- 一致 frontmatter 格式 → 数据驱动 query
- Daily note 一键新建, 不用 boilerplate
- Strategy/drift/plan 模板一键 fill

### 5. **Daily Notes 时序记录**
- 每日 log 的 99_ADMIN/daily/YYYY-MM-DD.md
- Claude 跨会话 push 重要决策到 daily
- 一周后回看一周做了什么 (Cmd+Alt+D)

### 6. **跨设备 sync (vault 在 T9)**
- Vault 在 T9 移动盘, Mac/Win 跨设备访问
- iPad 也能装 Obsidian, 阅读项目随时随地
- iCloud / OneDrive sync 不需要 (T9 是 portable)

## 🔄 项目工作流变化对比

### Before (没 vault)
```
- 561 个 .md 散在各文件夹
- 用 grep 查找
- Drift / strategy / plan 各自孤立
- 需要记忆哪个在哪
- Round 切换信息散乱
```

### After (vault 化)
```
+ 单个 HOME (00_INDEX.md) 入口
+ 9 个 MOC 区域导航
+ Wikilink + backlink 自动 cross-reference
+ 5 个 templates 一键 fill
+ Tags 多维度过滤
+ Graph view 看全局结构
+ Daily note 时序记录
+ Claude 自动 sync (CLAUDE.md rule)
+ 跨设备 + 移动端阅读
```

## 🧪 验证 vault 工作的 5 个 quick test

```
1. 打开 Obsidian → 加载 vault → 打开 00_INDEX.md
   → 应看到 HOME 页面 + 所有 MOC links

2. Cmd+G → 看 graph view
   → 应看到节点 + 边 (links)

3. Cmd+Shift+F → 搜 "drift"
   → 应找到 PAPER_BACKTEST_DRIFT_LOG + 14+ drift entries

4. 打开 PAPER_BACKTEST_DRIFT_LOG.md → Cmd+Shift+B
   → 应看到 backlinks (谁引用此 drift log)

5. Cmd+T → insert Daily_Note_Template
   → 应弹出 template list
```

## 📚 进阶 (可选 plugins)

未来可以装 community plugins:

- **Dataview**: 跑 SQL-style query 在 vault (例: "list all strategy with WR > 70%")
- **Templater**: 高级模板 with JS
- **Calendar**: 月历 view daily notes
- **Kanban**: 看板 view (todo)
- **Excalidraw**: 手绘 architecture diagrams

但目前 6 个核心 plugins 已 enable, 够用。

## 🔗 Related

- [[00_INDEX|HOME]]
- [[CLAUDE]] — Claude project rules + sync rule
- [[Templates/Daily_Note_Template]]
- [[.claude_memory_shared/MEMORY|Auto-memory index]]
