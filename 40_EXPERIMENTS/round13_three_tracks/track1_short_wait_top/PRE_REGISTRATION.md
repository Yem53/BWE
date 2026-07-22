---
type: experiment
tags: [round13, track1, short, wait-for-top, pre-registration]
created: 2026-05-29
status: wip
priority: high
---

# Track 1 — 做空"等顶/等动量转头"过滤器 · 预注册假设

> 先定死, 再看结果。本文件在跑任何过滤组合**之前**写定。
> 目的: 给做空入场加一道"等顶"条件, 看能不能把 B_US_PM 那种
> "拉升还在加速时追空、被过冲秒止损"的单子滤掉, 让改良版做空期望转正。

## 病因 (实盘已定位)
B_US_PM_PULLBACK 实盘 4胜9负 −$39.35 (胜率31%), 亏损主力。
它在妖币拉升还在**加速**时追空, 被过冲瞬间顶穿 SL
(实盘 NOM 3.9min / ME 17min / BSB 1.4min / HIGH 2.1min 就被秒止损)。

## Baseline B (实盘配置, 用框架字段表达)
- side = short
- entry = {hours_utc:[15,16,17,18,19], ret60_atr_min:4.0, pullback_pct_max:-0.02, vol_zs_min:1.5, rsi_min:60}
- exit  = {single, tp_atr:5.0, sl_atr:2.5, time_stop_min:240, tp_confirm_bars:1}

## 引擎 + 数据
- 引擎: `40_EXPERIMENTS/round8_calibration/calibrate.py` 的 `eval_window` (含组合仓位 + 成本 + 滑点 + funding)
- 数据: 196d, 200 币, 1-min grid, 2025-11-01 → 2026-05-16
- 特征 as-of 约定: 第 t 列特征只用 ≤ t-1 的收盘 bar; 引擎在 t_sig+1 开盘入场 → 无前视

## 4 个预注册假设 (每个在 B 的 entry 上 AND 一道过滤)

### H1 — 动量已转头 (ret5_atr 由正转负)
只在 5min ATR 归一动量 (ret_5m / atr_pct) 已经 ≤ 阈值 才做空。
- 框架字段: `ret5_atr_neg_max ∈ {0.0, -0.2, -0.4}`
- 含义: 信号 bar 上 5 分钟动量已经不再向上 (甚至向下) = 顶部动能在减弱

### H2 — 拒绝K线 (带长上影 + 收阴/弱实体)
只在出现"冲高回落"K线后才做空。
- 框架字段: `upper_wick_min ∈ {0.003, 0.005}` × `body_neg_max ∈ {0.0, -0.002}`
- 含义: 上影长 = 上冲被打回; 实体偏阴 = 多头力竭

### H3 — 距拉升峰值 N 根之后 (给过冲让路) ★核心新过滤
只在距 60min 内最高点已过 N 根 K 线之后才做空。
- 新特征 `bars_since_60m_high`: 第 t 列 = (t-1) − argmax(high[t-61:t-1])
  (复用 B 已经在用的 pullback 峰值定义: 60m 最高点)
- 参数: `bars_since_high_min ∈ {1, 2, 3, 4}` (即 task 的 N 扫 1/2/3/4)
- 含义: 峰值刚出现就追空最危险 (过冲未完); 等几根让过冲走完再进

### H4 — 成交量从爆发峰值衰减 (动能耗尽)
只在成交量从最近爆发峰值明显回落后才做空。
- 新特征:
  - `vol_zs_peak_10`: 第 t 列 = max(vol_zs[t-11:t-1]) (最近 10 根曾经的量峰)
  - 当前 vol_zs[t]
- 参数: 要求 `vol_zs_peak_10 >= burst_min` (确实爆过) 且
  `vol_zs[t] <= vol_zs_peak_10 − decay_min`
  - burst_min ∈ {2.0, 3.0}, decay_min ∈ {1.0, 1.5}
- 含义: 量先爆 (有人拉) 后缩 (拉力没了) = 动能耗尽, 这时做空更安全

## 时间切分 (强制)
- **Holdout = 最近 35 天 (约 04-11 → 05-16) 全程封存**, 筛选阶段绝不碰, 最后只验一次。
- **Dev = holdout 之前的部分**, 做 walk-forward 3 折 (等分时间)。
- 注意: 这与 calibrate.py 自带的 make_splits 不同 (那个 holdout 只 18d); 本 track 用自定义 35d 封存切法。

## 判定规则 (某过滤算"有效"必须全部满足)
1. **dev 全部 3 折** 的 short port_sum > 0 且 **每折** Calmar ≥ baseline B 同折 Calmar (跨折一致, 不是单折显著)
2. **holdout (35d)** 的 short port_sum 和 Calmar **都** ≥ baseline B 的 holdout
3. 不能把 D 类好单滤没: 在 D 的 entry 上加同一过滤, 方向必须一致 (port_sum 不应被严重砍掉变负) — 作为否决项
4. **反过拟合护栏**:
   - 只在单折好的当噪声丢弃
   - 胜率 > 65% 或单笔均值 > 2% → 先停, 查前视/泄漏
   - 测多个 H × 多参数 → 记总组合数, 报多重比较顾虑; 跨折一致优先于单点
   - 入场特征只用 ≤ 入场 bar 数据 (已由 as-of 约定保证)

## 交付
- 脚本 + 中间 jsonl + 最终中文报告写到本目录
- 报告含: 每个 H 的 dev/holdout port_sum/胜率/Calmar/maxdd vs baseline B; 是否有 holdout 通过的规则 (给精确指标) 或诚实"无"; 总组合数 + 多重比较; 前视/成交性顾虑
