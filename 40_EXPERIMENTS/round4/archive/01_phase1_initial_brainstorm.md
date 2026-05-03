# Phase 1 — Initial Brainstorm (2026-04-28)

> 5d Hermes data → exit_v2 module → rule discovery → first spec v1

## 起点

**用户痛点** (实盘观察):
- 实盘 Hermes 80 单 -65.9% 总 PnL,胜率 35.8%
- 个案: KAT 涨到 +33% 没锁住,跌回 -7% 才退 — 33% 利润全跑
- 个案: TRADOOR 等候 black swan 但提前退,只锁 +13% 而非 +65%

## 数据基础

### Hermes 数据 (5d × 535 syms)
- 80 closed live trades + 176 closed paper trades
- 1m kline DB 已存在 (`/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3`)

### 妖性分公式 (decision #1)
4 维 weighted score (基于 5d 数据):
- 35w: 5min ±8% 大波动次数 (直接行为)
- 25w: max 单日高低范围 %
- 25w: 平均 ATR % (30min window)
- 15w: 1 - 24h 成交额排名 (低 vol 加分)

**Sanity check 通过**:
- TRADOOR: rank 1 (score 85.5)
- DAM: rank 2 (85.2)
- BTC/ETH/SOL: bottom 4 (score < 5)

## exit_v2 模块开发

3 个 fix 落地:
1. **G2 TRADOOR-saver**: high_water > 25% AND fresh < 10min AND volume confirms → 暂停 trail
2. **ATR-aware hard stop**: max(2.5%, 2.5×ATR)
3. **Volume-confirmed breakdown**: 退场前看 5min vol vs 30min baseline 是否 >= 1.5x (洗盘检测)

### Backtest 结果 (Hermes 81 live × 9 ExitConfig 变体)
- v2_baseline: **LIVE -65.9% → +150.7% raw** (+216% improvement!)
- v2_baseline: **PAPER -361.1% → +132.6% raw** (+494% improvement!)
- 13 个 variants 全部正,sensitivity 显示 robust

## Rule Discovery (data-driven)

### 1407 waves (top 100 yao coins, 5d) 单变量 winrate scan
- **`reaction == trend_continue`**: follow win 86.4% (+31.6 pp vs baseline)
- **`reaction == mean_revert`**: fade win 86.0% (+7.8 pp)
- **`pre_vol >= 7x`**: fade win **70.8% (-7.3 pp)** ← 反向 signal
- **`duration 3-6min`**: fade win **69.8% (-8.3 pp)** ← 死亡区
- **`duration 6-9min`**: fade win 88.9% (+10.8 pp) ← 甜点
- **`score >= 80`**: fade win 86.4% (+8.3 pp)

### 7 条规则 (first match wins)

| Order | Rule | Action | n waves | Win % |
|---|---|---|---|---|
| 1 | A. n_waves < 3 | SKIP | — | — |
| 2 | B. trend_continue + dur 3-20 | FOLLOW 5% | 22-12 | 86-92% |
| 3 | C. mean_revert + sustained/single_burst | FADE 8% | 45 | **100%** ⭐️ |
| 4 | D. score≥80 + pre_vol<2.5 | FADE 8% | 44 | 93% |
| 5 | E. duration 3-6 | SKIP | 96 | 70% (-8 pp) |
| 6 | F. pre_vol≥7x | SKIP | 48 | 71% |
| 7 | G. default | FADE 5% | 265 | 78% |

## L1-L4 概念建立 (Hermes only,5d data)

### LIVE 81 trades 三层对比
| Layer | total_raw | win % | mean/trade |
|---|---|---|---|
| L1 原始 buggy | -65.9% | 35.8% | -0.81% |
| L2 exit_v2 only | **+150.7%** | 65.4% | +1.86% |
| L3 + rule SKIP | **+170.3%** | 70.1% | +2.54% |
| L4 full (per-thesis + dir-check) | +45.7% | 59% | +1.17% ❌ |

### Spec v1 写出
路径: `archive/per_symbol_design_v1.md` (已归档)

包含 7 条规则、4-tier 系统、5 phase rollout。

---

## Phase 1 关键文件 (raw outputs)

- `05_audits/yaobi_score_v0.json` — 5d × 535 syms 妖性分
- `05_audits/yaobi_per_symbol_dive.json` — 5d 100 top 妖币 deep dive
- `05_audits/rule_discovery.json` — single + pair feature winrate scan
- `05_audits/rule_engine_simulation.json` — 7-rule engine sim on 265 waves
- `05_audits/exit_v2_backtest_results.json` — 13 ExitConfig variants
- `05_audits/market_scan_exit_v2.json` — 226 broader-market events scan
- `exit_v2/exit_v2.py` — production module (with G2)
- `exit_v2/通俗解释_策略改进.md` — 中文 plain explanation
- `exit_v2/integration_spec.md` — live bot 接入 plan

## Phase 1 → Phase 2 trigger

5d 数据样本不足:
- TRADOOR 86 events 但实际 5 天 → 极端值
- KAT 18 events 看起来 高峰,实际是 5d 偶然
- 用户决策 #5: 全市场 30d backfill,验证 5d 结论是否 robust
