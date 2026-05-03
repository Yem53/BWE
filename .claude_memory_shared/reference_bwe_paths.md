---
name: BWE 关键路径速查
description: BWE 项目在 H:\ 下的核心目录、文档、代码、数据的绝对路径索引（2026-04-27 已清理掉过时的根级 BWE_autoresearch / BWE_data_backups）
type: reference
originSessionId: 9aa9a58b-6062-4d43-83be-5004328027b2
---
## 顶层目录
**所有 BWE 内容统一在 `H:/BWE/` 下** —— 之前的 `H:/BWE_autoresearch/` 和 `H:/BWE_data_backups/` 已于 2026-04-27 清理（前者全是已迁移到 30_DATA 的纯重复，后者是 Round 2 旧 runtime）。两个旧索引文件保留在 `90_SOURCE_POINTERS/` 下作历史参考。

- `H:/BWE/` — 唯一的 BWE 主项目根

## 文档（H:/BWE/00_PROJECT_REQUIREMENTS/）
- `docs/00_project_scope_v6.md` — 项目范围、完整策略定义
- `docs/01_data_contract_v6.md` — 字段分区、未来函数禁止
- `docs/02_data_inventory_and_transfer.md` — 数据清单、迁移指南
- `docs/04_complete_strategy_search_space.md` — 入场/退出维度
- `docs/05_llm_autoresearch_loop.md` — 每轮流程、LLM 预算
- `docs/06_5090_execution_plan.md` — smoke/medium/max_alpha 阶段
- `prompts/CODEX_*.md` — 6 个 Codex 角色提示
- `configs/` — 搜索空间和指标合约配置
- `runbooks/` — 5090 机器启动指南
- `manifests/data_manifest.json` — 数据清单

## 三频道流程详解
- `H:/BWE/20_CODE/Autoresearch/BWE_THREE_CHANNEL_AUTORESEARCH_FLOW.md`

## 核心代码（H:/BWE/20_CODE/Autoresearch/bwe_autoresearch/）
- `bwe_loop.py` — Karpathy-style 主 loop（GPU first-touch，5090 上跑）
- `bwe_loop_score_metric.py` — legacy p25 指标 + GPU 矢量化
- `bwe_loop_score_v2.py` — v2 指标（mean_net_pct / kelly / p25_capped_tail）
- `bwe_loop_exit_kernels.py` — 5 种 exit kernel（fixed / time_only / breakeven / trail / multi_tp）
- `bwe_loop_entry_filter.py` — entry filter DSL
- `bwe_loop_data_loader.py` — kline 解析（H:/BWE/30_DATA/reference/legacy_market_cache）
- `bwe_loop_llm_team.py` — LLM team orchestrator (11 roles, all Opus-4-7)
- `v6_complete_strategy.py` / `deep_autoresearch.py` / `discovery.py` — 旧版（仍存在但当前 loop 不依赖）

## 数据（H:/BWE/30_DATA/）
**单一 source of truth**，当前所有代码都从这里读：

```
30_DATA/
├── input/
│   └── binance_event_features_20260425_30d/   # BWE 事件 + binance features (275 MB)
│       ├── bwe_events_recent_base.parquet         # 7353 BWE 原始事件
│       ├── bwe_events_recent_binance_features.parquet  # 7317 行带 features
│       ├── bwe_forward_recent_binance_features_merged.parquet  # 73170 forward path/label
│       └── raw/
│           ├── mark_price_1m.parquet              # 4M rows
│           ├── premium_index_1m.parquet           # 4M rows
│           ├── open_interest_hist.parquet         # 746K rows
│           ├── funding_rate.parquet
│           ├── taker_buy_sell_volume.parquet
│           └── basis_perpetual.parquet
├── reference/
│   ├── bwe_autoresearch_entry_v5_20260425/    # 67 MB
│   ├── bwe_entry_research_v5_package/         # 1 MB schemas + prompts
│   └── legacy_market_cache/                   # 22.4 GB, 10 sub-runs, 30K+ JSON kline files
│       ├── bwe_phase1_smoke2 / bwe_phase1_run1
│       ├── bwe_three_channel_run1..5 / fullrun1
│       └── bwe_v2_run1..2
└── cache/
    ├── normalized/trade_kline_1m_event_windows.parquet  # 主要 kline 数据
    ├── binance_trade_klines_1m_raw/
    └── legacy_unified/
```

**bwe_loop.py 默认读取的两条路径：**
- `KLINE_PARQUET = H:/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows.parquet`
- `EVENTS_PARQUET = H:/BWE/30_DATA/input/binance_event_features_20260425_30d/bwe_events_recent_binance_features.parquet`

## 实验产物（H:/BWE/40_EXPERIMENTS/）
```
40_EXPERIMENTS/
├── hypothesis_registry.jsonl   # 523 archetypes (200E + 100X + 120F + 40R + 60C + 3 LLM-accepted)
├── results.tsv                 # 每个 combo 的 loop 结果
├── combo_cursor.json           # loop 进度游标
├── coverage_map.html
├── analysis/                   # per-channel/exit-family 统计 + rescore_v2
├── debates/<ts>/               # LLM debate 产物（per-proposal 5-role critic）
├── paper_shadow/               # paper-shadow 模拟结果
├── paper_candidates/           # 候选 archetype 列表
├── all_runs_archive/           # 历史 run 归档（含 robocopy 日志）
└── morning_brief_latest.md     # 中文每日 brief（auto-generated）
```

## 历史索引（H:/BWE/90_SOURCE_POINTERS/）
- `source_paths.json` — 当前活跃路径的程序可读清单
- `FILE_INDEX_legacy_BWE_autoresearch.md` — 已删除的旧 BWE_autoresearch 文件索引（仅历史参考）
- `DATA_SNAPSHOT_INDEX_legacy_BWE_autoresearch.md` — 已删除的旧 BWE_autoresearch 数据快照索引

## 管理目录（H:/BWE/99_ADMIN/）
- `day1_active_plan.md` — 当前活跃计划入口（必读）
- `loop_run.pid` / `loop_run.log` / `loop_run.err`
- `round3_pipeline.log` / `round3_launcher.out.log`

## 跨机器记忆
- `H:/BWE/CLAUDE.md` — 项目级永久记忆，Claude Code 自动加载
- `H:/BWE/.claude_memory_shared/` — 用户级结构化记忆镜像（跨 Mac mini ↔ 5090 携带）

## Telegram 原始导出（在 Mac mini 上，未传到 5090）
- pricechange: `/Users/ye/Desktop/Telegram/方程式价格异动监测_history/result.json`
- OI&Price: `/Users/ye/Desktop/Telegram/方程式OI&Prce异动_history/result.json`
- Reserved6: `/Users/ye/Desktop/Telegram/方程式重大行情提醒 Important Price Alerts Only_history/result.json`

## 已知缺失（开放问题）
- Telegram 原始导出未复制到 5090（在 Mac mini）
- Live 日志（journal penalty 用）未在快照中
