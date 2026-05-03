# Per-Symbol 妖币策略 — Design Spec v2 (FINAL)

> **Status**: 2026-04-29 finalized (post 30d data validation + optimization)
> **Replaces**: per_symbol_design.md (now archived as `archive/per_symbol_design_v1.md`)
> **Context**: 整合 Phase 1-4 全部 brainstorm 决策 + 数据验证

---

## 1. Context

经过 4 个 phase 的迭代 + 数据驱动 brainstorm,我们定下:**双源混合策略架构**。

### 1.1 关键 insight (post 30d data + 1425 broader-market events)

1. **exit_v2 是绝对的核心 alpha 来源** (Hermes LIVE +218%, PAPER +449% vs 原始 buggy logic)
2. **Rule SKIP 在 BWE-pre-filtered 数据上是 net negative** — BWE Telegram 已经过滤,不要重复过滤
3. **Rule directional 在 broader market 上是 +14% alpha** — 没有外部方向信号时,rule 决定是真 alpha
4. **不同信号源用不同 layer**:
   - BWE Telegram 信号 → L2 (exit_v2 with per-lifecycle 调优)
   - 直接市场扫描 ±8% events → L4 (rule directional + 4-tier pos sizing)
5. **数据基建已就绪**:30d × 530 syms × 多维度 (klines/funding/OI/long-short/taker/basis/24h-ticker) + watchdog

### 1.2 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│              DATA LAYER (实时,自检 + 自愈)                    │
│  • binance_futures_1m_collector       (1m kline,realtime)   │
│  • binance_futures_metric_collector   (mark/funding/OI/LS/  │
│                                        taker/basis 5m)      │
│  • binance_24h_ticker_collector       (24h ticker, 5min)    │
│  • binance_extended_history.sqlite3   (30d backfill)        │
│  • collectors_watchdog.sh             (cron 每分钟自检)       │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│           FEATURE EXTRACTION (daily batch + on-demand)       │
│  • yaobi_score (4维 + 30d window) — 每天重算                  │
│  • lifecycle (sustained/late_burst/spike_decay/single_burst) │
│  • reaction (mean_revert/trend_continue/mixed) — 每周重算    │
│  • per-event: pre_vol / wave_duration / magnitude            │
└──────────────┬─────────────────────────┬────────────────────┘
               ↓                         ↓
┌────────────────────────┐  ┌────────────────────────────────┐
│  ENTRY SOURCE A:        │  │  ENTRY SOURCE B:               │
│  BWE Telegram 信号       │  │  Direct market scan ±8% events │
│  (oi_overcrowded /       │  │  (530 syms × 5min check)       │
│   pc_crash_bounce / 等)  │  │  ~50 events/天 全市场           │
└──────────┬─────────────┘  └─────────────┬──────────────────┘
           ↓                                ↓
┌────────────────────────┐  ┌────────────────────────────────┐
│  L2 — exit_v2 with      │  │  L4-tier — rule directional    │
│  per-lifecycle ExitConfig│  │  + 4-tier 仓位 (3/5/8/12%)     │
│  (no entry rule)         │  │                                │
│  • sustained/late_burst:│  │  Rules:                         │
│      wider trail         │  │   A: insufficient → SKIP       │
│  • spike_decay:          │  │   B: trend_continue → FOLLOW   │
│      tighter trail       │  │   C: mean_revert + sus → FADE  │
│  • default: baseline     │  │   D: score≥80 + low pre-vol →  │
│                          │  │      FADE (12% if sc≥85)       │
│  Position: 5%            │  │   E: dur 3-6 → SKIP            │
│                          │  │   F: pre_vol≥7x → FOLLOW       │
│                          │  │   G: default → FADE 5%         │
│                          │  │       (3% if sc<50)            │
└──────────┬─────────────┘  └────────────────────────────────┘
           ↓                                ↓
                ┌──────────────────────┐
                │  EXIT: exit_v2 module │
                │  (含 G2 TRADOOR-saver)│
                └──────────────────────┘
```

## 2. Goals & Non-goals

### Goals

- **G1**: BWE 信号 trade 用 L2-per-lifecycle (PAPER 30d 数据 +144% raw / +7.21% cap)
- **G2**: 直接市场扫描 trade 用 L4-tier (1425 events 30d +1147.6% raw / +89.70% cap)
- **G3**: 保留 exit_v2 module 全部 alpha (任何修改不能损失 +218% LIVE / +449% PAPER 改善)
- **G4**: 双源 alpha 加和 (BWE alpha + Broader alpha 互不干扰)
- **G5**: 全 backwards compat — config flag 关闭整个 system 即可回到 L1 原始

### Non-goals

- **NG1**: 不做 per-thesis exit config in L4 (broader market 测试显示 wider-follow 反而损 -29pp)
- **NG2**: 不做 dir-check between rule and BWE direction (Hermes L4 测试显示 -71% cap)
- **NG3**: 不做 continuous position sizing (broader 测试显示 raw 损 -176pp)
- **NG4**: 不做 LLM 实时入场决策 (latency)
- **NG5**: 不增加新 BWE strategy (那是 BWE 信号生成层的事)

## 3. Layer A — BWE Entry + L2-per-lifecycle Exit

### 3.1 入场逻辑

BWE Telegram 信号触发 → **直接入场,不加 entry filter**(因为 BWE 已经过滤)。
方向由 BWE strategy 决定 (long/short)。
仓位:5% 固定 (current default)。

**不做的事**:
- ❌ Rule SKIP 过滤 (PAPER 上损 -32% cap)
- ❌ 仓位 sizing (LIVE 上 mean_cap 损)
- ❌ 方向 override (Hermes L4 测试 -71% cap)

### 3.2 Exit 逻辑 — Per-Lifecycle ExitConfig

根据 symbol 的 lifecycle 标签,选择不同的 ExitConfig:

```python
def get_exit_config(symbol):
    lifecycle = symbol_features[symbol]["lifecycle"]
    
    if lifecycle in ("sustained", "late_burst"):
        # 这些 coins 趋势持续,wider trail 让 winners 跑
        return ExitConfig(
            trail_tiers=((5, 5), (10, 10), (25, 18), (50, 28), (100, 40)),
            tradoor_saver_max_hw_age_min=20.0,
        )
    
    if lifecycle == "spike_decay":
        # decay 快,tight trail 锁利
        return ExitConfig(
            trail_tiers=((5, 3), (10, 5), (25, 8), (50, 12), (100, 18)),
        )
    
    # quiet / single_burst / unknown → baseline
    return ExitConfig()  # default trail 4/7/12/18/25
```

### 3.3 Evidence

| Sample | total_raw | total_cap | win % |
|---|---|---|---|
| Hermes LIVE (82 trades) | +101.4% | +5.07% | 67.1% |
| Hermes PAPER (210 trades) ⭐️ | **+144.1% (+12pp vs base)** | **+7.21%** | 65.2% |

PAPER 上 +12pp raw 提升来自 wider trail capturing PAPER's pc_crash_bounce_long 类 (mostly sustained/late_burst) 的更长 winner runs。

LIVE 上略损 (-48pp vs L2-base) 因 LIVE 的 oi_overcrowded_crash type 多是 spike_decay,wider trail 不适用。**最终选择 L2-per-lifecycle 因 paper 验证更重要**。

## 4. Layer B — Direct Market Scan + L4-tier Entry/Exit

### 4.1 入场逻辑 — 实时检测 + Rule Engine

```python
def market_scan_entry():
    # 每 1m 扫描所有 530 symbols
    for symbol in active_symbols:
        last_5min_close = get_close(symbol, ts=now)
        prev_5min_close = get_close(symbol, ts=now-5min)
        ret = (last_5min_close - prev_5min_close) / prev_5min_close * 100
        
        if abs(ret) < 8.0:
            continue  # not 妖币 event
        
        # Got an event — apply rule engine
        features = compute_features(symbol)  # score + lifecycle + reaction + etc
        wave_features = compute_wave_features(symbol, now)  # duration + pre_vol
        
        action, pos_pct, direction = apply_rules(features, wave_features, side="pump" if ret > 0 else "dump")
        
        if action == "SKIP":
            continue
        
        place_trade(symbol, direction, pos_pct=pos_pct, exit_config=ExitConfig())
```

### 4.2 Rule Engine (顺序匹配,first match wins)

```python
def apply_rules(meta, wave_feat, side):
    n_waves = meta["n_waves_14d"]
    lifecycle = meta["lifecycle"]
    reaction = meta["reaction"]
    score = meta["score"]
    duration = wave_feat["duration"]
    pre_vol = wave_feat["pre_vol"]
    
    # Rule A — insufficient history
    if n_waves < 3:
        return ("SKIP", 0, None)
    
    # Rule B — trend_continue → follow direction (5%)
    if reaction == "trend_continue" and 3 <= duration <= 20:
        direction = "long" if side == "pump" else "short"  # follow same direction
        return ("ENTER", 5, direction)
    
    # Rule C — prime fade signal (8% or 12% for very high score)
    if reaction == "mean_revert" and lifecycle in ("sustained", "single_burst"):
        pos = 12 if score >= 85 else 8
        direction = "short" if side == "pump" else "long"  # fade
        return ("ENTER", pos, direction)
    
    # Rule D — high score + low pre-vol (8% or 12%)
    if score >= 80 and pre_vol < 2.5:
        pos = 12 if score >= 85 else 8
        direction = "short" if side == "pump" else "long"  # fade
        return ("ENTER", pos, direction)
    
    # Rule E — duration 3-6 dead zone
    if 3 <= duration <= 6:
        return ("SKIP", 0, None)
    
    # Rule F — high pre-vol → follow (5%)
    if pre_vol >= 7.0:
        direction = "long" if side == "pump" else "short"  # follow
        return ("ENTER", 5, direction)
    
    # Rule G — default fade (3% if low score, 5% otherwise)
    pos = 3 if score < 50 else 5
    direction = "short" if side == "pump" else "long"
    return ("ENTER", pos, direction)
```

### 4.3 4-Tier 仓位

| Tier | Position % | 触发 |
|---|---|---|
| Mini | 3% | Rule G + score < 50 (弱信号兜底) |
| Standard | 5% | Rule B / Rule F / Rule G default |
| High | 8% | Rule C / Rule D + score 80-84 |
| Max | 12% | Rule C / Rule D + score ≥ 85 (极高 confidence) |

### 4.4 Exit

固定用 `ExitConfig()` baseline (含 G2 TRADOOR-saver, dynamic trail, ATR-aware stop, volume confirm)。
**不做** per-thesis swap — broader market 测试显示 wider-follow 反而 -29pp。

### 4.5 Evidence (1425 events 30d)

| Variant | total_raw | total_cap | mean_cap |
|---|---|---|---|
| L4-base (5/8% pos) | +1147.6% | +74.80% | +0.074% |
| **L4-tier-3-5-8-12** ⭐️ | **+1147.6% (=)** | **+89.70% (+20%)** | **+0.088%** |

**关键: total_raw 不变 (无 alpha 损失) + 资金效率提升 20%**。

## 5. Storage & State

### 5.1 Symbol features 表 (新建,在 `binance_extended_history.sqlite3` 内)

```sql
CREATE TABLE symbol_features (
  symbol TEXT PRIMARY KEY,
  yaobi_score REAL NOT NULL,
  n_waves_14d INTEGER NOT NULL,
  lifecycle TEXT NOT NULL,         -- sustained/late_burst/spike_decay/single_burst/quiet
  reaction TEXT NOT NULL,          -- mean_revert/trend_continue/mixed/n_a
  computed_at_ms INTEGER NOT NULL,
  reaction_computed_at_ms INTEGER NOT NULL  -- weekly update
);

CREATE INDEX idx_symbol_features_lifecycle ON symbol_features(lifecycle);
```

每天 daily batch 跑 `compute_symbol_features.py`(基于现有 `yaobi_score_explorer_v2.py` + `yaobi_per_symbol_deep_dive_v2.py`)。

### 5.2 决策日志表 (audit trail)

```sql
CREATE TABLE entry_decisions (
  trade_id TEXT PRIMARY KEY,
  symbol TEXT, ts_ms INTEGER,
  source TEXT,                     -- "BWE" or "MARKET_SCAN"
  features_json TEXT,
  rule_triggered TEXT,             -- "A".."G" for source=MARKET_SCAN
  action TEXT,                     -- ENTER / SKIP
  position_pct REAL,
  direction TEXT,                  -- long/short
  exit_config_label TEXT,          -- "baseline" / "wider" / "tighter"
  reason TEXT
);
```

### 5.3 Daily JSON dump (人类 review)

每天 batch 完后输出 `/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/daily_features_YYYY-MM-DD.json`:
- All symbols 的 yaobi_score 排名
- Top changes (新进入 lifecycle 类 / 新进入 trend_continue reaction)
- 触发各规则的 trade 统计

## 6. Integration with Hermes Bot

### 6.1 Config flags (新增到 `bwe_live_autotrader_binance_expectancy_live.json`)

```json
{
  "exit_engine": {
    "use_v2": false,             // [Phase 2 enable]
    "per_lifecycle_config": false  // [Phase 2 enable]
  },
  "market_scan_engine": {
    "enabled": false,            // [Phase 4 enable]
    "event_threshold_pct": 8.0,
    "max_concurrent_trades": 3
  }
}
```

### 6.2 Entry hook (BWE source)

在 `bwe_live_autotrader.py:_open_position` 里:

```python
def _open_position(self, symbol, side, ...):
    if self.config["exit_engine"]["use_v2"]:
        # Look up symbol features for lifecycle-aware exit config
        features = self.feature_store.get(symbol)
        exit_config = build_lifecycle_aware_config(features.lifecycle) \
            if self.config["exit_engine"]["per_lifecycle_config"] \
            else ExitConfig()  # baseline
        position["exit_config"] = exit_config
    
    # ... existing entry logic
```

### 6.3 Market scan engine (新模块,独立进程)

新文件 `/Users/ye/.hermes/scripts/bwe_market_scan_entry.py`:
- 独立进程,跟 `bwe_live_autotrader.py` 平行
- 每 60s 扫描 530 symbols 是否有 ±8% 5min event
- 应用 `apply_rules()` → 产生 trade decision
- 通过 `_open_position` 同 hook 进 bot (with `source="MARKET_SCAN"` tag)
- 限制 max_concurrent_trades = 3 (避免资金 overload)

## 7. Rollout Plan (5 Phases)

| Phase | 内容 | 时间 | Pass criterion |
|---|---|---|---|
| **1** Data + tools | 基建已经齐全 (30d backfill + collectors + watchdog) | ✅ Done | — |
| **2** BWE L2-per-lifecycle paper | 把 exit_v2 + per-lifecycle config 接入 paper bot | 1 周 | PAPER 3 天均 PnL > 0,胜率 > 60% |
| **3** BWE L2-per-lifecycle live | 单一 strategy (e.g., DAM/ZKJ-class) live 试点 | 1 周 | 5-10 单后总 PnL 正,无连续 3 单 catastrophe |
| **4** Market scan paper | 启动 market_scan_entry.py paper 验证 | 1 周 | 30+ events 后总 cap > 0,胜率 > 60% |
| **5** 全 live + market scan | 双源 hybrid 全 live | iterative | 周报 review |

每 phase 通过才进下一 phase。

## 8. Verification

### 8.1 Phase 2 paper criterion (BWE L2-per-lifecycle)

| 指标 | 当前 paper L1 | per-lifecycle 期望 |
|---|---|---|
| Total raw PnL | -317.6% | > +50% |
| Win rate | 26.3% | > 60% |
| Catastrophes | 0 | < 5 (per 100 trades) |

### 8.2 Phase 4 paper criterion (Market scan)

| 指标 | L1 naive | L4-tier 期望 |
|---|---|---|
| Total raw PnL (per 30 events) | -1.4% | > +25% |
| Win rate | 27.6% | > 60% |
| 资金 efficiency (mean_cap) | -0.002% | > +0.05% |

### 8.3 Rollback

任何 phase 失败 → 把对应 config flag 设回 false,立即回到上一 phase。
完全回退路径:`use_v2=false + market_scan_engine.enabled=false` 恢复 L1 原始。

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| L2-per-lifecycle 在 LIVE 上比 base 略损 | LIVE total_raw -48pp | Phase 2 paper 跑 3-7 天检查;若 paper 不达标用 L2-base 替代 |
| Market scan 入场频率 ~50/天 资金 overload | 仓位耗尽 | `max_concurrent_trades=3` cap |
| Symbol lifecycle 标签 stale (周更新但 symbol 突变) | 用错 ExitConfig | Phase 2 监控,若 stale 触发 catastrophe > 5%,降到 daily update |
| Watchdog 失效 → collectors 死 | 数据 stale | watchdog 自带 stale check + 双重监控 (process + freshness) |
| Top-100 之外 symbols 触发 market scan | 用 default meta → Rule A SKIP | Phase 2 review 是否漏 alpha;若 yes,扩 dive 到 top 200 |
| 12% 仓位某次大输 | 单笔损失 > -2% capital | exit_v2 hard stop 限制最坏 -29.9% × 12% = -3.6% |
| BWE 信号源中断 | Layer A 静默 | Hermes 多 channel + watchdog;Layer B 独立运作 |

## 10. Open Questions (delayed to Phase 2+)

1. **Lifecycle 标签每天还是每周?** (decision #1: lifecycle daily, reaction weekly) — 看 Phase 2 catastrophe 频率决定
2. **Market scan 加 long-short ratio / OI / funding 维度?** — 当前 4 维 enough,V2 数据后可能加
3. **新 entry signal source (e.g., 量价分歧)?** — 等 phase 5 后
4. **跨交易所 (OKX) 信号?** — 后期
5. **LLM 辅助决策?** — out of scope for v2

## 11. Out of Scope

- LLM 实时决策
- Cross-exchange (OKX/Bybit)
- Order book / depth 实时数据
- Cluster-based 自动分类
- Per-thesis exit config (data 反对)
- Direction-check between rule + BWE (data 反对)

## 12. Evidence Files (archive)

完整 phase findings + raw data 在 `archive/` 子目录:
- `archive/00_decision_log.md` — 用户每个决策时间线
- `archive/01_phase1_initial_brainstorm.md` — 5d data + exit_v2
- `archive/02_phase2_30d_validation.md` — 30d backfill + 4 analyses
- `archive/03_phase3_layer_validation.md` — L1-L4 双 sample 验证
- `archive/04_phase4_optimization.md` — 5+5 变体最终选择
- `archive/per_symbol_design_v1.md` — 上一版 spec (废弃)

Raw JSONs 在 `05_audits/`,scripts 在 `scripts/`。

## 13. Final lock-in 数据 (baseline metrics for future regression)

### BWE L2-per-lifecycle:
- LIVE: +101.4% raw / +5.07% cap / 67.1% win / mean_cap +0.062%
- PAPER: **+144.1% raw / +7.21% cap** / 65.2% win / mean_cap +0.034%

### Broader Market L4-tier-3-5-8-12:
- 1425 events: **+1147.6% raw / +89.70% cap** / 66.9% win / mean_cap +0.088%
- 灾难: 41 / 大赢家: 109

任何后续修改如果回归这些 baseline 之下 → 触发 review。
