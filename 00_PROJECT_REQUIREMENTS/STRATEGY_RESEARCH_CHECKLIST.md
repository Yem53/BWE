---
type: reference
tags: [checklist, research, paper, strategy, lookahead, backtest, live, anti-overfitting]
created: 2026-05-04
status: active
priority: high
---

# 📋 Strategy Research + Paper Checklist

> 实战 check list — 从 v6_multi_8 → strict 30d audit → paper 9 天 0 trades → v10
> 这一轮经验里捞出来的清单。每次启动新研究 / paper 前对照检查。
>
> **优先级标识**: 🔴 不做就出大问题 / 🟡 影响质量 / 🟢 优化项

相关文档:
- [[../40_EXPERIMENTS/round5/specs/BWE_PROJECT_DESIGN_RULES|BWE Project Design Rules]] — 10 原则 + 9 历史错误
- [[00_PROJECT_REQUIREMENTS_MOC|项目需求 MOC]]
- [[../CLAUDE|CLAUDE.md]] — 全局指令

---

# Part 1 — AI 找策略时 (research / backtest)

## 🔴 A. 防 Backtest 假阳性 (数字漂亮但 live 一定爆)

| 项 | 不做的后果 | 怎么做 |
|---|---|---|
| **As-of percentile** | 用全 30d 算 percentile = 把未来涨幅排进 universe = 严重 lookahead | 任何 ratio / z-score / rank 只用 entry 前可见历史算 |
| **As-of universe membership** | 30d 后视镜挑出"最活跃的 150 个币" = 同样未来函数 | universe 每天/每小时按过去 14d 重算 |
| **Entry timing** | 用 signal bar 的 close/high/low 成交 = 偷看未来 | signal at completed 1m close, entry at next 1m open + slippage |
| **TP wick 反 hunt** | high 触及 TP 算赢 = 把刺针当成交价 | TP 必须 close-confirm 1-3 bars + wick-aware slippage |
| **SL 风险侧优先 (不对称)** | SL 也 close-confirm = 抹掉真止损损失 | low/high touch SL **立即认**, 不准 confirm |
| **同 bar 同时触发 SL/TP** | 默认 TP 先发生 = 乐观 | **SL 先发生** (worst case) |
| **Funding fee 累计** | 跨 funding window 没扣 = 高估 PnL | 持仓跨 funding (8h) 时扣实际 funding rate |
| **Slippage 分级** | 固定 0.05% slippage = 妖币上严重低估 | 普通 0.05% / wick 0.2% / 极端 0 fill |

## 🔴 B. 防过拟合 / 单币伪通用

| 项 | 红线 |
|---|---|
| `traded_symbols` | < 25 自动 non-general; ≥ 50 才 candidate; ≥ 80 才 strong |
| `traded_symbols / eligible_symbols` | ≥ 25% (低于这个 = 99% 的币策略不感冒) |
| `top_symbol_share` | ≤ 20% (例: S1 在 1000000BOBUSDT 上占 60.97% = 单币运气, 不是策略) |
| `top_5_symbol_share` | ≤ 50% |
| `unique_days` | ≥ 20 / 30 (避免 alpha 全堆在某 1-2 天爆拉日) |
| **Train/Dev/Holdout 三段** | 18d / 6d / 6d, holdout 只能最后用一次, 不准反复调参 |
| **跨 split 持仓 embargo** | ≥ 240 min, 防止 train 持仓泄漏到 dev |

## 🔴 C. 防 Long/Short 互相借光

- 两个完全独立 leaderboard
- 每条 strategy 必须明确 side, 不准模糊 "双向"
- walk-forward 各侧分别做
- top-10 必须标 side, 一侧弱如实报 (不准用 long 的好结果代表 short)

## 🔴 D. 防 BWE 当成唯一触发源

- BWE = 17 syms × 30d 历史 + 频道运营人选币口味, 不是市场规律
- 每个 entry archetype **必须** 在没有 BWE 信号时也能从全市场扫出 trades
- 每条策略分别报 `no-BWE metrics` 和 `with-BWE-confirm metrics`
- 如果 no-BWE 失效到不可用而 with-BWE 才有效 → 标 **BWE-dependent**, 不进 PASS

## 🟡 E. 比值代替绝对阈值 (跨币跨时间通用)

```
❌ marketcap < $100M       ✅ marketcap_rank percentile
❌ vol ≥ $1M USDT          ✅ vol_zscore_30 ≥ 3
❌ ret_5m ≥ 3%             ✅ ret_5m / sym_5m_std_asof ≥ 2.5
❌ TP = 5%                 ✅ TP = 3 × ATR_at_entry
❌ BWE move_pct ≥ 3%       ✅ move_pct / sym_event_move_std_asof ≥ 2.5
```

允许的绝对常量只有: 时间窗口, fees, slippage, catastrophe SL=-10%, 主流币 blacklist, 物理上市时间。

## 🟡 F. 数据来源可验证

- `feature_registry.json` 强制: 每个 feature 有 `source_table/file/source_column`, lookback, as_of_rule
- 找不到 source → 该字段禁用, 不准凭 symbol 名称 / 叙事推断 (例 marketcap, sector, meme tag)
- 数据缺失 (例 ticker_24h hole) → 该 strategy 整条 skip, 不准 fillna(0) 假装有数据

## 🟢 G. 让 AI 持续探索 (不要规定明确退出条件)

- 给目标 (long 5 + short 5 candidate+) 不给步骤
- 不要列"phase 1→6 完成 = 退出", 否则 AI 跑完就停, 不迭代
- 只给 3 种 stop: 目标接近 / 连续 3 轮没推动 / 时间硬上限到
- 唯一硬上限: 时间 (12h) + 内存 (RAM ≤ 50GB, VRAM ≤ 28GB)

## 🟢 H. Portfolio replay 强制

只看 trade-level metrics 会被骗 — 100 笔 trade 都 +5% 看着漂亮, 但 portfolio replay 跑出来 max_dd -50% (因为同一时刻 5 只币同向暴露过大)。必须:
- `one_position_per_symbol`
- `same_symbol_cooldown` 30-60 min
- `max_concurrent` {5, 10} 都测
- `raw trades vs deduped portfolio metrics` 分开报, **排序优先看 deduped**

---

# Part 2 — Paper 阶段

## 🔴 I. Paper-LIVE Alignment Audit (最重要, 不做 = 白搭)

我们刚踩的坑 — backtest 9/9 strategy 在 strict audit 下都触发了, paper 实际 0 trades, 因为 paper 的实现和 backtest 不一致。

```
启动 paper 前必做:
1. 拿 paper config + backtest 同期数据
2. 取过去 7 天的 BWE event + 市场数据
3. paper runner 的 entry filter 跑一遍, 输出 should_enter 列表
4. backtest 同 config 跑一遍, 输出 did_enter 列表
5. 对比一致性:
   - 完全一致 ≥ 90%       → paper 实现没问题, 启动
   - 一致性 70-90%       → 找不一致原因 (filter 顺序? feature 计算?)
   - < 70%              → 修 paper runner, 别启动
```

## 🔴 J. Symbol Filter 不要过严

paper 在过去 9 天 0 trades 的根因:

```
paper 严格要求 symbol_meta.listing_ts_ms 不为 null 才认 active USDT perp
↓
新上市妖币 (CRCLUSDT 等) 在 daily_snapshot_collector 还没 ingest 时 listing_ts=null
↓
paper 全部 skip_not_active_usdt_perp
↓
即使 BWE 触发了对的事件, 也 0 trades
```

修复:
- `daily_snapshot_collector` 必须在 paper 启动前先跑完
- paper 的 `not_active` filter 应该 fallback 到 `is_in_exchangeInfo` (实时 API check)
- listing_ts 缺失时不要直接 skip, 用默认 listing_age = 365 (或者从 strategy filter 移除这条)

## 🔴 K. Order Placement 实操

我们之前踩过的坑:
- `notional_usdt = 10` < binance `minNotional = 50/100` → demo_orders_failed
- 修过 100 后还有失败, 因为 lot_size / tick_size 不对齐 (例 1000000BOBUSDT 价格 0.0000xxx, qty 必须整数)
- mark_price 60s 不刷新 → skip

防御:
1. exchange_filters 24h refresh, fallback 用 hardcoded minNotional=20
2. qty_for_notional 用 LOT_SIZE.stepSize round_down
3. mark_price stale 阈值 = 300s (不是 60s, paper 不需要那么严)
4. demo_orders_failed 计数监控, 5 min 内 > 5 次 → alert

## 🟡 L. 数据 Freshness 监控

每 5 min 检查:
- klines_1m 最新 ts ≥ now - 90s ? (collector 活着)
- mark_price 最新 ts ≥ now - 60s ?
- BWE jsonl 最新 ts ≥ now - 30 min ? (BWE 有事件才会写)
- ticker_24h 最新 update ≥ now - 1h ? (我们刚发现这表有 hole, 影响 L1/L4)

任一不达 → 该 strategy 暂停, 不要硬跑出错误信号。

## 🟡 M. WAL / OOM 防御

- sqlite WAL 必须 `wal_autocheckpoint = 2000` (我们之前踩过 68GB WAL → OOM)
- 每 60s 一次手动 `PRAGMA wal_checkpoint(PASSIVE)`
- multi_paper_runner RSS 监控, 超过 8GB 重启 (内存泄漏)

## 🟡 N. 风险硬规 (Live 优先)

- catastrophe SL = -10% 必须实施 (gap-down 那种就靠这个保命)
- time_stop ≤ 240 min (持仓越久越容易遇黑天鹅)
- `max_concurrent_total` ≤ 16 (不准 100 个币同时持仓)
- 单 strategy `max_concurrent_per_strategy` ≤ 5
- 同 sym `same_strategy_symbol_cooldown_min` ≥ 60 (别在同一币上反复抽)

## 🟢 O. 监控信噪比

之前踩过: 加了 OKX 实时数字播报 + paper hourly heartbeat, 用户烦死。

正确做法:
- Hourly heartbeat 写 log 但**不发通知**
- Telegram alert 只在: OPEN / CLOSE / crash / 异常单笔 (单笔损失 > -8%) / 数据 freshness 报警
- 每天 08:00 生成日报 (前 24h 概览), 一次性发

---

# Part 3 — 全程通用 (跨阶段)

## 🔴 P. 渐进上线流程 (永远别跳步)

```
backtest candidate (12h GPU)
       ↓
Paper-LIVE alignment audit (1 天)  ←  最容易跳的一步
       ↓
Paper 跑 7-14 天累计 metrics
       ↓
metrics 在预期折扣区间内?
   ✅ → 真小额 live ($100 cap, 单笔 5%)
   ❌ → 回到 backtest 重审
       ↓
Live 跑 30 天再放大 cap
```

预期折扣 (backtest → paper):
- mean 打 6-7 折 (slippage + fill rate)
- WR 打 87-93 折 (fill rate)
- monthly 打 7-8 折 (fill rate)
- max_dd 放大 1.7-2x (slippage + funding 累积)

## 🟡 Q. 失败回退

每个 strategy 都要有 "kill switch":
- 累计 max_dd > 30% → 自动停 (不等人工)
- 7d trades 触发数 < 期望的 30% → 暂停 (说明市场环境变了)
- 任一 catastrophe SL 触发后 → 暂停 24h, 排查原因再恢复

## 🟢 R. 复盘强制

每周一次:
- 跑 last 7d backtest (用同期真实市场数据 + 同 config)
- 对比 paper 实际 vs backtest 应该
- 偏差 > 30% → 排查 paper 实现 (不是 strategy 失效)
- 偏差 ≤ 30% → strategy 在正常衰减区间

---

# 优先级总结

如果只能 follow 5 条, follow 这 5 条:

1. **As-of 一切** (ratio + universe membership) — 防最大 lookahead 漏洞
2. **TP/SL 不对称** (TP confirm, SL touch 即认) — 防 wick 失真
3. **`traded_symbols ≥ 50` + `top_share ≤ 20%`** — 防单币伪通用
4. **Paper-LIVE alignment audit** — 防 "backtest 漂亮 paper 0 trades"
5. **渐进上线 (backtest → align → paper 14d → 小额 live)** — 防直接上 live 爆仓

---

# 更新历史

- 2026-05-04: 初版, 基于 v6_multi_8 翻车经验 + v10 codex prompt 设计 整理出 18 条 (A-R)
