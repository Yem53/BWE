# Per-Symbol 妖币策略 — Design Spec v1

> **Status**: Draft v1, 等用户 review 后进入 writing-plans
> **Date**: 2026-04-28
> **Author**: BWE brainstorm session
> **Context**: 此 spec 不 implement 任何代码,纯设计。Live bot / paper bot 在 spec approve 之前不动。

---

## 1. Context

BWE 妖币策略目前是 "一刀切" — 同一个 ExitConfig + 同一组 entry filter 跑所有币。
数据告诉我们这个假设错了:

- 226 个市场妖币事件中,**轻妖币 win 86%、极妖币只 win 58%** — 妖性分类是有效信号
- 80 个 Hermes live 单中,**KAT 33% 利润全跑 / TRADOOR 65% 退出在 13%** — 一刀切退出 leak alpha
- 30+100 个 deep-dive 妖币中,**4 个 (APE/PLAY/ESPORTS/SPK) 应该 follow 而不是 fade** — 部分妖币行为反直觉

我们需要 **每个币按它自己的行为特征触发不同的入场/退出决策**,但不要 hardcode tier 表 (会僵化)。

数据驱动的解决方案: **规则引擎 + 实时 feature 计算**。

## 2. Goals & Non-goals

### Goals

- **G1**: 每次入场都按当前 features + 累积妖性数据决策 (不依赖 stored static tier)
- **G2**: 7 条数据驱动的规则覆盖 90%+ 决策路径,每条规则有明确 evidence 支撑
- **G3**: 不同决策路径触发不同 exit 配置 (fade 用 exit_v2 baseline,follow 用 wider trail)
- **G4**: 系统能自适应 — 一个币的 lifecycle/reaction 随时间变化,决策跟着变
- **G5**: 完全 backwards-compatible — 一个 config flag 关闭整个 system,回到当前 logic

### Non-goals

- **NG1**: 不做 cluster-based 自动分类 (5d 数据样本不稳)
- **NG2**: 不做 LLM 实时入场决策 (latency 不可接受)
- **NG3**: 不做新 entry signal 发现 (依然由 BWE Telegram + 实时市场扫描触发)
- **NG4**: 不动 BWE 现有 strategy 配置 (oi_overcrowded_crash_follow_short 等保持现状)

## 3. Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                      DATA LAYER (passive, batch)                        │
│  ┌────────────────────────────┐    ┌──────────────────────────────┐    │
│  │ binance_futures_1m.sqlite3 │    │ binance_extended_history.sqlite3│
│  │ (live collector, active)   │    │ (codex 30d batch, frozen)    │    │
│  │ 5.6d × 535 symbols         │    │ 30d × 100+ symbols            │    │
│  └────────────────────────────┘    └──────────────────────────────┘    │
└────────────────────────────────┬───────────────────────────────────────┘
                                 ↓
┌────────────────────────────────────────────────────────────────────────┐
│              FEATURE EXTRACTION (daily batch + on-demand)               │
│  Per-symbol (daily, 14d rolling):                                      │
│    yaobi_score, lifecycle_label, reaction_label, n_waves_14d, ...      │
│  Per-event (on-demand, ~10ms):                                         │
│    wave_duration, pre_vol_ratio, magnitude, peak_sign                  │
└────────────────────────────────┬───────────────────────────────────────┘
                                 ↓
┌────────────────────────────────────────────────────────────────────────┐
│                  RULE ENGINE (synchronous, called per entry)            │
│  Input:  symbol, current bar context, BWE signal                       │
│  Output: { action: SKIP|FADE|FOLLOW, position_pct: 3|5|8, reason }     │
│  7 rules in priority order, first match wins                            │
└────────────────────────────────┬───────────────────────────────────────┘
                                 ↓
┌────────────────────────────────────────────────────────────────────────┐
│              EXIT LAYER (existing exit_v2.py + per-thesis config)       │
│  FADE  → exit_v2 baseline (current ExitConfig)                          │
│  FOLLOW → exit_v2 wider trail + G2 always-on                           │
└────────────────────────────────────────────────────────────────────────┘
```

## 4. Data Layer

### 4.1 现有 (不动)

- `/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3`
- 5.6d × 535 symbols × 1m kline
- live collector 在 active 写入,**绝不改 schema 或锁这个 DB**

### 4.2 新增: extended history (codex 后台拉中)

- `/Volumes/T9/BWE/30_DATA/cache/binance_extended_history.sqlite3`
- 由 codex 后台脚本 `pull_binance_extended_history.py` 拉取一次性写入
- 30d × top 100 妖币 + 4 reference (BTC/ETH/SOL/BNB)
- 三张表 (schema 见 codex prompt):
  - `klines_1m` (30d × 100+ × 1440 = ~4.3M bars)
  - `funding_rate` (90d × 100+ × ~3 events/day)
  - `open_interest_hist` (30d × 100+ × 24 hours)

### 4.3 Feature 数据流向

- Daily batch job 每 24 小时跑一次:
  - 读两个 DB 合并 (active 5d + extended 30d 取并集,extended 优先用于 deep history)
  - 算 per-symbol features → 存到 `symbol_features` 表
- On-demand 实时计算:
  - 入场触发时拉该 symbol 最近 60 分钟 1m 数据
  - 算 wave_duration / pre_vol / magnitude

## 5. Feature Extraction

### 5.1 Per-symbol features (每天 rolling 14d 重算)

| Feature | 算法 | 用途 |
|---|---|---|
| `yaobi_score` | Composite 4 维: 5min ±8% 大波动次数 (35w) + max_daily_range (25w) + avg_atr (25w) + (1 - vol_rank) (15w) | 妖性总分 0-100 |
| `n_waves_14d` | 14d 内 ±8% 大波动 cluster (15min gap) 数 | Skip 数据不足的币 |
| `lifecycle` | 14d 内 events 时间分布: spike_decay / sustained / late_burst / single_burst / quiet | 决策维度 |
| `reaction` | 14d 内 events 后 60min 价格走势分类: mean_revert / trend_continue / mixed | 决策维度 (主) |
| `historical_fade_winrate` | 14d 内 events 模拟 fade 入场的胜率 | 评估规则适用性 |
| `historical_follow_winrate` | 14d 内 events 模拟 follow 入场的胜率 | 评估规则适用性 |

### 5.2 Per-event features (on-demand, ~10ms)

| Feature | 算法 | 用途 |
|---|---|---|
| `current_wave_duration_min` | 当前 wave 起始到现在的分钟数 | 死亡区间过滤 |
| `pre_vol_ratio` | 入场前 5min 平均成交量 / 入场前 30min baseline 平均成交量 | flip 阈值 |
| `magnitude` | 触发 wave 的 5min 内 abs(return) % | 入场强度 |
| `peak_sign` | "pump" (正) 或 "dump" (负) | 决定 fade/follow 是空还是多 |

### 5.3 Reaction 重算频率

- `lifecycle` 每天重算 (变化快)
- `reaction` 每周重算 (相对稳定,变化慢)
- 实现: daily batch 也算 reaction 但只在每周一覆盖到 SQLite,其他天保留旧值

## 6. Rule Engine

7 条规则按 **优先级顺序** 跑,**第一条 match 的决定行为**。每条规则附带数据 evidence。

### 规则 A — 数据不足跳过

```
IF n_waves_14d < 3:
  RETURN { action: SKIP, reason: "insufficient_history" }
```

**Evidence**: 30 个 quiet 币 + 38 个 single_burst 中,样本太少导致行为不可预测。需要至少 3 个历史 events 来支撑 fade/follow 判断。

### 规则 B — 强 follow 信号

```
IF reaction == "trend_continue" AND duration ∈ [3, 20]:
  RETURN { action: FOLLOW, position_pct: 5, reason: "trend_continue_window" }
```

**Evidence**: `reaction == trend_continue` 单维 follow_win 86.4% (Δ +31.6 pp, n=22)。
配合 duration 3-20min 提升到 win 91.7% (n=12 with duration 3-6) / 73.1% (n=26 with duration 10-20)。

### 规则 C — Prime fade (核心金矿)

```
IF reaction == "mean_revert" AND lifecycle ∈ ("sustained", "single_burst"):
  RETURN { action: FADE, position_pct: 8, reason: "prime_fade" }
```

**Evidence**:
- `sustained × mean_revert`: fade win **100%** (n=15), mean +5.03%
- `single_burst × mean_revert`: fade win **100%** (n=30), mean +4.35%

合计 n=45 大样本,胜率 100%,是数据中最强的 fade 信号。

### 规则 D — 高分妖币 + 低 pre-vol = 强 fade

```
IF yaobi_score >= 80 AND pre_vol_ratio < 2.5:
  RETURN { action: FADE, position_pct: 8, reason: "high_score_low_prevol" }
```

**Evidence**: `score >= 80 AND pre_vol < 1.5x`: fade win 93.2%, mean +6.05%, n=44 (大样本)。

### 规则 E — 死亡区间跳过

```
IF duration ∈ [3, 6]:
  RETURN { action: SKIP, reason: "fade_dead_zone" }
```

**简化说明**: 跑到规则 E 意味着规则 A/B/C/D 都没 match (B 已经处理过 trend_continue 的 follow 路径),
所以剩下的默认是 fade — 但 fade 在 3-6 min 是死亡区间,直接 skip。

**Evidence**: duration 3-6min 的 wave fade win 降到 69.8% (Δ -8.3 pp,基线 78.1%)。

### 规则 F — 高 pre-vol 行为 (PENDING 30d data 最终决定)

**当前状态**: 5d 数据 simulation 显示 3 个变体差距 < 1% (噪音区间),需要 30d 数据 break tie。
Codex task `task-moitvq73-z2oq6v` 后台拉数据中,回来后 re-run `rule_engine_simulation.py`
3 个变体决定 final 行为。

**3 个候选行为** (在 5d simulation 上):

```
变体 II (FOLLOW):     pre_vol >= 7x → FOLLOW 5%       Cap PnL: +43.44%
变体 II (SKIP):       pre_vol >= 7x → SKIP            Cap PnL: +43.71% ⭐️ 5d 最优
变体 III (条件):       pre_vol >= 7x AND late_burst → FOLLOW, ELSE SKIP   Cap PnL: +42.69%
```

**初始 evidence (5d, 14 trades on F)**: pre_vol >= 7x 时 fade win 70.8% (Δ -7.3 pp), 
follow win 62.5% (Δ +7.8 pp) — single-feature 看 follow 略好,但 deployment 验证 follow -0.28% cap。

**Phase 1 决策点**: 用 30d 数据重新 simulate 3 个变体,选 PnL 最高 + 胜率最高的版本。
若 3 个仍然差距 < 1%,默认选 SKIP (最保守,最少操作)。

### 规则 G — 兜底默认 fade

```
RETURN { action: FADE, position_pct: 5, reason: "default_fade" }
```

**Evidence**: baseline fade_win **78.1%**, mean +2.73%。大多数妖币默认 fade 已经够好。

### 6.1 规则触发顺序与 evidence 摘要

| Order | Rule | Action | n (evidence) | Win% | Δwin |
|---|---|---|---|---|---|
| 1 | A. n_waves < 3 | SKIP | — | — | — |
| 2 | B. trend_continue + duration | FOLLOW | 22-12 | 86-92% | +32 to +37 pp |
| 3 | C. mean_revert + sustained/single_burst | FADE big | 45 | 100% | +22 pp |
| 4 | D. score>=80 + pre_vol<2.5 | FADE big | 44 | 93% | +15 pp |
| 5 | E. duration 3-6 | SKIP | 96 | 70% | -8 pp |
| 6 | F. pre_vol>=7x | **PENDING** (II/SKIP/III) | 48 | TBD on 30d | TBD |
| 7 | G. default | FADE | 265 baseline | 78% | 0 |

### 6.2 仓位 sizing

| Confidence | 仓位 % capital | 触发规则 |
|---|---|---|
| 大 | 8% | 规则 C, D (见 Open Question 4 — 是否要保守到 5%) |
| 标准 | 5% | 规则 B, G |
| 小 | 3% | (preserved for future use, e.g., LLM uncertainty signal) |

## 7. Per-Thesis Exit Configuration

### 7.1 FADE → exit_v2 baseline (current production)

```python
fade_exit_config = ExitConfig()  # default
# trail_tiers=((5,4),(10,7),(25,12),(50,18),(100,25))
# hard_stop_min_pct=5, hard_stop_atr_mult=2.5
# tradoor_saver_enabled=True (G2 conditional)
# volume_confirm_enabled=True
```

### 7.2 FOLLOW → wider trail + G2 always-on

```python
follow_exit_config = ExitConfig(
    trail_tiers=((5, 6), (10, 12), (25, 20), (50, 30), (100, 40)),  # wider
    tradoor_saver_enabled=True,
    tradoor_saver_hw_threshold=15.0,  # 提前激活 (vs 25)
    tradoor_saver_max_hw_age_min=20.0,  # 更宽 (vs 10)
)
```

理由: follow 是跟趋势,需要更宽 trail 让趋势跑;G2 在 hw 15 就激活避免早退。

## 8. Storage

### 8.1 Symbol features 表

```sql
CREATE TABLE symbol_features (
  symbol TEXT PRIMARY KEY,
  yaobi_score REAL NOT NULL,
  n_waves_14d INTEGER NOT NULL,
  lifecycle TEXT NOT NULL,         -- spike_decay/sustained/late_burst/single_burst/quiet
  reaction TEXT NOT NULL,          -- mean_revert/trend_continue/mixed/n_a
  historical_fade_winrate REAL,
  historical_follow_winrate REAL,
  computed_at_ms INTEGER NOT NULL,
  reaction_computed_at_ms INTEGER NOT NULL  -- separate ts since reaction is weekly
);
```

### 8.2 决策日志表 (audit trail)

```sql
CREATE TABLE entry_decisions (
  trade_id TEXT PRIMARY KEY,
  symbol TEXT, ts_ms INTEGER,
  bwe_signal_id TEXT,
  features_json TEXT,           -- snapshot of features at decision time
  rule_triggered TEXT,          -- "A", "B", ..., "G"
  action TEXT,                  -- SKIP/FADE/FOLLOW
  position_pct REAL,
  reason TEXT
);
```

### 8.3 每天导出 JSON 给人 review

每天 daily batch 跑完后 dump:
- `/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/daily_symbol_features.json`
- 含全部 symbols 的 features + 触发的 rule 统计 (e.g., 今天 60% 入场触发规则 G,15% 触发 C ...)

## 9. Integration with Bot

### 9.1 Entry hook

在 `bwe_live_autotrader.py` 的 `_can_open_position` 或 `_open_position` 里:

```python
def _check_per_symbol_rules(self, symbol, bwe_signal, recent_bars):
    if not self.config.get('per_symbol_engine', {}).get('enabled', False):
        return None  # 走原 logic

    features = self._compute_features(symbol, recent_bars)
    decision = PER_SYMBOL_RULE_ENGINE.decide(features, bwe_signal)
    self._log_decision(symbol, features, decision)

    if decision.action == "SKIP":
        return False
    return {
        'override_position_pct': decision.position_pct,
        'override_thesis': decision.action,  # FADE or FOLLOW
        'override_exit_config': decision.exit_config,
    }
```

### 9.2 Exit hook

在 `_handle_with_v2_engine` (新加,见 exit_v2/integration_spec.md) 里按 `pos['thesis']` 选 exit_config:

```python
exit_config = (FOLLOW_EXIT_CONFIG if pos.get('thesis') == 'FOLLOW'
                else FADE_EXIT_CONFIG)
engine = ExitEngine(exit_config)
decision = engine.decide(...)
```

### 9.3 Backwards compat

```yaml
# config.yaml
per_symbol_engine:
  enabled: false  # paper 验证后切 true
exit_engine:
  use_v2: false   # 已有 flag,见 exit_v2/integration_spec.md
```

两个 flag 独立 — 可以单独启用 exit_v2 而不启用 per_symbol_engine,反之亦然。

## 10. Rollout Plan

| Phase | 内容 | 时间 | Pass criterion |
|---|---|---|---|
| **1** Data + Tools | (1) Codex 30d 数据回来 → 验证 (2) 写 daily batch 脚本 (3) 用 30d 数据 re-calibrate 7 条规则的阈值 | 2-3 天 | 30d data loaded + features 表 populated + rules calibrated |
| **2** Paper validation | Paper bot enable per_symbol_engine + exit_v2,跑 5-7 天 | 1 周 | Paper PnL 3 天移动均值 > 0,胜率 > 60% |
| **3** Single-strategy live | Live bot 单一 strategy (DAM/ZKJ 类 prime fade) 启用 per_symbol_engine,5-10 单 | 1 周 | Total positive,无连续 3 单 catastrophe |
| **4** Full live | 全 strategy 切,启用 entry filter (规则 A/E/F skip 路径) | iterative | Weekly review winrate vs baseline |
| **5** Black swan & 进阶 | (依赖更多数据) 加 funding/OI 维度做新 entry signal,LLM 辅助决策 | 后续 | TBD |

## 11. Verification

### 11.1 Paper validation (Phase 2)

| 指标 | 当前 paper | per_symbol_engine 期望 |
|---|---|---|
| Total raw PnL | -361% | > +50% |
| Win rate | 22% | > 60% |
| n_skipped (规则 A/E/F) | 0 | 30-50% trades |
| Largest catastrophe | -50% | > -25% |

### 11.2 Live validation (Phase 3)

5-10 单后看:
- Total PnL > 0
- 无连续 3 单 catastrophe (signal logic 严重错误的指示)
- 决策日志 (entry_decisions 表) 显示规则分布与 paper 一致

### 11.3 Rollback

- `per_symbol_engine.enabled = false` 立即回到当前 logic
- 完全 backwards compatible, 不影响其它 strategy

## 12. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 30d 数据 re-calibration 后规则阈值变化大 | 推迟 Phase 2 | calibration script 留 diff log,人工 review 大改 |
| Reaction 标签每周更新太慢,妖币行为变化没赶上 | 决策错误 | Phase 2 监控 reaction-stale 触发的 catastrophe,> 5% 改成每天 |
| n_waves_14d < 3 跳过太多入场 | Hermes 几乎不入场 | Phase 2 看 SKIP 比例,超过 60% 降阈值到 2 |
| 规则 F (pre_vol>=7x) flip 错 | 单笔大亏 | Phase 2 看 follow 触发的 catastrophe |
| 自动 daily batch failed | 用 stale features 决策 | batch 失败时 alert + 旧 features 7 天 expire,过期后该 symbol 一律 SKIP |
| BWE collector 数据 gap | features 计算错误 | 用 staleness check, gap > 1 hour 该 symbol SKIP |

## 13. Open Questions (need answer in Phase 1)

1. **30d 数据 calibration 后哪些阈值变了?** 写一个 diff 报告
2. **BWE strategy 的 short/long 方向跟 fade/follow 的关系?** e.g., `oi_overcrowded_crash_follow_short` 本身就是 short — 它跟 dump-event-fade-as-long 有冲突吗?
3. **Phase 2 paper 通过条件**: 还要不要细化 (e.g., 加 max drawdown / Sharpe)?
4. ~~规则 C 给 8% 仓位是不是太大?~~ **Resolved 2026-04-28**: 维持 8% (用户决定)
5. **Funding rate / OI 数据回来后**: 加成第 5 个/第 6 个 feature 的优先级?
6. ~~规则 F (高 pre_vol) 是否将来改为 FOLLOW~~ **Resolved 2026-04-28**: 已直接定为 FOLLOW (用户决定)

## 14. Out of Scope (留给将来)

- LLM 辅助决策 (e.g., 入场时 LLM 调一个判断,latency 接受 1-2s)
- Cluster-based 自动分类 (KMeans/DBSCAN, 等数据到 30d+ 再说)
- Cross-exchange (OKX/Bybit) 信号融合
- 多空账户比 / taker buy/sell volume 数据 — 等 Phase 5

## 15. Appendix: Evidence files

- `/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_score_v0.json` — 妖性分 + 535 symbols ranking
- `/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_market_attached.json` — 226 市场事件 + 妖性分
- `/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/yaobi_per_symbol_dive.json` — top 100 deep dive
- `/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/rule_discovery.json` — 规则发现结果
- `/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/exit_v2_backtest_results.json` — exit_v2 13 个 config 回测
- `/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/market_scan_exit_v2.json` — 226 事件 exit_v2 验证
- `/Volumes/T9/BWE/40_EXPERIMENTS/round4/exit_v2/exit_v2.py` — production exit module (含 G2)
- `/Volumes/T9/BWE/40_EXPERIMENTS/round4/exit_v2/通俗解释_策略改进.md` — exit_v2 通俗解释
