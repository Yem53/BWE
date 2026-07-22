---
type: experiment
tags: [bwe, feature-discovery, volatility-compression, breakout, squeeze, anti-overfit, no-lookahead]
created: 2026-05-31
status: design
priority: med
---

# a10 — 波动压缩 → 突破:可预测性与可交易性 Spec

> Round 15 并行发掘方向 a10。研究只读、不碰实盘/EC2/fapi。
> 强先验:compression 在 round14 只是个**弱 hint**,扣成本后大概率不成立。
> 任务是诚实判定它在某粒度/某条件下是否有可交易的东西,**报负=合格**。

## 0. 一句话目标

测「长期安静(波动收窄、区间紧)之后的**首次放量突破**」其后续方向
(继续走 trend-continuation vs 假突破反转 fade)是否**可预测、可交易**。
多粒度、做多做空两面都测。

## 1. 核心机制定义(全部 as-of,无前视)

### 压缩度(squeeze)在突破那根**之前**测
在候选突破 bar `t`(用其**收盘**作进场点),只用 `open_time_ms < t 收盘时刻` 的已收盘 bar:
- **band_width**:Bollinger 带宽 = `(SMA20 + 2σ - (SMA20 - 2σ)) / SMA20 = 4σ20/SMA20`,σ=20根收盘价 std。带宽越小=越压缩。
- **squeeze_ratio**:短窗/长窗实现波动比 = `std(ret, last 6) / std(ret, last 48)`(round14 的 compression 写法)。低=蓄势。
- **range_tightness**:近20根 `(max(high)-min(low)) / SMA20`。紧=压缩。
- **bbw_pctile**:band_width 在该币**过去 N 根**(纯历史,as-of)的分位 → "现在是不是比自己历史更安静"。

压缩状态判定:`bbw_pctile <= q`(默认 q∈{0.15,0.25})且持续 ≥ K 根(默认 K∈{6,12})。

### 突破触发(breakout trigger)
压缩期之后,bar `t` 满足(全部用 ≤t 的已收盘量价,**进场=t 收盘价**):
- **方向**:close 突破近 `W` 根(默认20)的 high(向上 UP)或 low(向下 DOWN)。
- **放量**:`vol[t] / mean(vol[t-W:t]) >= vmult`(默认 vmult∈{1.5,2.0,3.0})—— "首次放量"。
- **离开带**:close 在 Bollinger 上轨之上(UP)/下轨之下(DOWN)。

一个币同一压缩段只取**第一次**触发(避免同段重复计数)。触发后设冷却(默认 W 根)再允许下一个事件。

## 2. 关键警告(本项目栽过 event_end 事后泄漏)

- 进场点 = **突破那根的收盘**(`close[t]`),实时可得。**不**用任何 >t 信息定义事件。
- **检测滞后测试(决定性)**:把进场从 t 收盘推迟 lag∈{0,1,2,3 根}(对应粒度的分钟),
  看 edge 是否随 lag 快速塌向 0/抛硬币。仿 round14 `lag_test.py`。
  lag0 是"突破收盘瞬间能进"的乐观上界;实盘检测+下单有延迟,lag≥1 才是可信交易面。
  **若 edge 只在 lag0 存在 → 判定为定义性泄漏/不可交易。**
- 压缩分位 `bbw_pctile` 只用该币**截止 t 之前**的历史 band_width(扩张窗口或滚动窗口,绝不含未来)。

## 3. 数据 + 切分

- K线归档 8 个月(2025-09-28 → 2026-05-30),640 币:
  `30_DATA/binance_collectors_runtime/binance_futures_klines_archive.sqlite3`
  表 `klines_{5m,15m,30m,1h}`(本方向主测中粒度;1m/3m 太碎噪声大,2h/6h 事件太少)。`mode=ro`。
- **可交易池**:复用 round14 `tradable_universe.json`(≥$3M/日,278 币)。研究全币测,
  可交易性结论只在该池内下。
- **切分(按事件 = 突破 bar 的 open_time_ms 归属)**:
  - **HOLDOUT(封存)= 最近 35 天 ts ≥ 2026-04-20**(本项目硬规)。筛选/调参绝不读,每层最终验一次。
  - **DEV = 2025-09-28 → 2026-04-20(约 6.7 个月)**,walk-forward 3 折(连续三等分),
    要求信号**每折同号**才算稳。
  - 注:用满 8 个月窗口(任务硬规),不沿用 round14 的 4 个月。

## 4. 标签(向前测,从 1m 路径算,特征不偷看未来)

进场 = 突破 bar 收盘价 `entry`,持有 H ∈ {对应粒度的 4/8/12 根 ≈ 多个小时}:
- `fwd_ret_H` = `close[entry+H]/entry - 1`
- `mfe_H`(最大有利)/`mae_H`(最大不利),从 1m high/low 路径
- **trend-continuation 收益**:突破方向上的 fwd_ret(UP→long,DOWN→short)
- **fade 收益**:反方向(UP→short,DOWN→long)—— 假突破赚反转
- runaway flag:逆向达 3x 爆仓级(~11%)

两面都算,看「突破后到底是续势还是假突破」哪个可预测。

## 5. 方法(分阶段,反过拟合)

1. **Phase 0 可行性**:小样本(可交易池前 ~40 币,单粒度 15m)扫压缩→突破事件,
   出基础率:事件频次、UP/DOWN 比例、续势 vs fade 的**无条件**均值/胜率。
   **若续势和 fade 都 ≈ 抛硬币且扣成本后负 → 早停,诚实报负。**
2. **Phase 1 描述筛**:全 DEV、多粒度 {5m,15m,30m,1h} × 压缩强度分位 × vmult。
   看「压缩越深 / 放量越猛,突破后续势(或 fade)是否越强且单调」。
   Spearman + 条件分位价差,**跨 3 折同号 + 跨波动档(妖/中/大)一致**才标"有信号"。不调参,只判有无。
3. **Phase 2 组合**(仅当 Phase 1 有幸存点):压缩深度 AND 放量 AND 方向,
   嵌套 CV,必须打赢最好单条件,否则复杂度否决。
4. **Phase 3 holdout 确认**:最终候选在封存 35 天 + lag 测试下验一次。扛不住即否决。

## 6. 成本 + 可交易性

- taker 来回 ~0.14% + 妖币滑点;突破追单滑点更大,**>0.8% 滑点视为不可成交弃单**。
- 扣成本仍正才算赢家。样本 <50 标注 "样本不足"。
- 可交易性结论只在 278 币池内。

## 7. 反过拟合护栏(默认开,违则作废)

搜索面 = 4 粒度 × 多压缩分位 × 多 vmult × 多 H × 两面 = 大多重比较面。
- HOLDOUT 全程封存,每层只验一次;DEV walk-forward 3 折跨折同号 + 跨波动档一致。
- **BH-FDR(α=0.10)** 修正,报"共试多少 (粒度×分位×vmult×H×side) 组合"。
- 因果无前视(断言 feat_max_ot < anchor);**lag 测试**是核心闸。
- 结果好得离谱(胜率>65% 或单笔>2%)**先停查泄漏**。
- 幸存者偏差:用含已下架/归零币的全池复核(尤其高 ATR 过滤)。
- **诚实报负是合格主交付**;"多数是噪声"可接受且很可能。

## 8. 产物(本目录)

`a10_vol_compression/` 下:
- `r15_common.py` — 只读连库 + 切分 + 工具(自含,不依赖 round14)
- `scan_compression.py` — 压缩→突破事件扫描(无前视 + 断言)
- `label.py` — 三层前向标签
- `describe.py` — Phase 1 描述筛(分位价差 + Spearman + 跨折/跨档)
- `lag_test.py` — 检测滞后决定性检验
- `holdout_confirm.py` — 最终 holdout 揭晓
- `REPORT_中文.md` — 中文白话报告(有 holdout 通过的规则给精确定义+指标,或诚实"无";
  共试组合数 + FDR + 前视/成交性顾虑 + lag 测试结果)

## 9. 诚实前提

- compression 是 round14 的**弱 hint**,强先验是"突破后方向≈抛硬币+肥尾"(round12/13 已证)。
- 本方向要么找到**条件性** edge(某粒度+某压缩深度+某放量),要么诚实确认无。
- 8 个月单一/少数 regime,任何 holdout 通过的发现仍属"暂定",上实盘前需 forward paper-shadow。
