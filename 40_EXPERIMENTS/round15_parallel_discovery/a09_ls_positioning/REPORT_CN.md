---
type: experiment
tags: [round15, ls_positioning, contrarian, long_short_ratio, a09, result]
created: 2026-05-31
status: done
priority: med
---

# a09 多空比极值 Contrarian (LS positioning) — 研究报告

> 一句话结论:**多空比极值/背离的逆向信号基本是噪声,没有稳健可交易的 alpha。**
> dev 上最亮的几个信号(yao 小币逆向做多,+2~3%)**出 holdout 后全线塌方**;
> 经典"散户极度看多→做空"逆向逻辑**连 dev 都是负的**;唯一 holdout 仍正的信号
> 扣多重比较后不显著、且胜率 <50%。诚实判定:**负结果 / 不通过**。

---

## 1. 做了什么

- **数据**:metrics_5m 的 global_ls(散户/全账户多空比)、toptrader_ls(大户/聪明钱多空比),8 个月 × 278 个可交易币(日均成交额 ≥ $3M)。前向收益来自 klines_5m。
- **3 个信号家族**(全部 per-symbol rolling 极值,不是静态阈,避免退化成选币):
  - F1 global_ls 极值:散户极度看多(rolling 分位 ≥0.90/0.95)→做空;散户极度看空(≤0.10/0.05)→做多。
  - F2 toptrader vs global 背离:div_z = 大户相对持仓 − 散户相对持仓 的 rolling z。大户多/散户空(div_z≥2)→做多;反向→做空。
  - F3 LS 快速变化(velocity):散户 1h 内快速加多(vel_z≥2)→做空;快速减多(≤−2)→做多。
- **机制**:信号在 T 触发 → T+5m 开盘进场 → 固定持有期(1h/4h/12h/24h)收盘出场,扣 0.14% 往返成本;cohort 前向收益分布 vs 同层同持有期的无条件 baseline。
- **分层**:majors(<1% ATR)/ mid(1–2.5%)/ yao(≥2.5%),外加 all。
- **纪律**:holdout 封存最近 40 天(ts≥2026-04-20),只在最后揭晓一次;dev = 2025-11-01→04-20,walk-forward 3 折;候选 = 3 折 net edge 同号为正 + dev net edge>0 + n≥50;赢家须过 holdout(净>0 且超 baseline)。
- 5.77M 个候选事件(4.59M dev / 1.18M holdout)。

---

## 2. 核心结果(诚实)

### DEV:192 个 cohort,17 个候选
dev 上的"赢家"高度集中在 yao 小币 + 做多 + 长持有期(散户极空/聪明钱背离做多/散户去杠杆做多),最高 net +2.6%、t 到 +3。看上去很诱人。

### HOLDOUT 揭晓:17 个候选里 12 个 edge 翻号

| 指标 | dev 中位 | holdout 中位 |
|---|---|---|
| 17 候选的 net edge(超 baseline) | +0.93% | −0.21% |

dev→holdout edge 符号一致只剩 5/17,翻号 12/17。最亮的 yao 逆向做多信号全线塌方:

| 信号(yao,逆向) | 持有 | DEV net / wr | HOLDOUT net / wr |
|---|---|---|---|
| F1 散户极空→做多 | 24h | +2.21% / 45% | −2.51% / 35% |
| F1 散户极空→做多 | 4h | +0.51% / 48% | −1.19% / 39% |
| F2 大户多/散户空→做多 | 24h | +1.88% / 48% | +0.59% / 40% |
| F3 散户去杠杆→做多 | 24h | +2.19% / 45% | +1.33% / 44% |
| F1 散户极多→做空(经典逆向) | 24h | −1.43% / 57% | −5.93% / 51% |
| F3 散户快速加多→做空 | 24h | +0.07% / 58% | −2.37% / 51% |

两个关键事实:
1. 经典逆向"散户极度看多→做空"连 dev 都是负的(net −0.26%~−1.43%),holdout 更差。胜率看着高(55–58%)是因为做空在略跌的窗口天然占便宜,但扣成本后均值为负——典型的"高胜率低赔率,被尾部吃光"。
2. 逆向做多在 dev 像有 alpha,但是 regime 拟合:dev 段(去年 11 月→今年 4 月)yao 小币整体偏强,"超跌买"顺了势;封存的最近 40 天 regime 一变,信号立刻失效或翻负。3 折一致只证明它在 dev 内稳定,不证明它跨 regime 稳健。

### 4 个"过 holdout"的信号 —— 扣多重比较后都不算数

朴素口径(holdout 净>0 且超 baseline)有 4 个通过。但用 symbol-clustered bootstrap(按币整块重抽,处理跨币/时间相关)看单边 p:

| 信号 | HOLDOUT n | net | edge | wr | bootP |
|---|---|---|---|---|---|
| F2 div z2.5 long mid 24h | 232 | +1.37% | +0.84% | 42% | 0.170 |
| F3 vel z2.5 short yao 1h | 572 | +0.18% | +0.13% | 53% | 0.348 |
| F1 global p05 long majors 24h | 952 | +0.25% | +0.09% | 46% | 0.359 |
| F3 vel z2.5 long all 24h | 3850 | +0.53% | +0.33% | 49% | 0.024 |

- 前 3 个 bootP 0.17–0.36,不显著,就是噪声。
- 第 4 个(散户去杠杆→全市场做多,24h)bootP=0.024,单看像信号。但:
  - 17 次 holdout 看,出现一个 p≈0.024 纯属期望之内(Bonferroni 0.024×17≈0.41;BH/FDR 下最小 p 的阈值≈0.003,0.024 过不了)。
  - 胜率 49%(<50%),均值靠少数大涨币撑(如 4USDT +2.2%);edge 只有 +0.33%,而它在 dev 的 edge 也只有 +0.11%(勉强够候选线)——不是强稳定信号,只是一个没被证伪的小正数。
  - 好的一面:它不是单币假象(278 个币、top1 占比 0.5%、39 个交易日都有),所以这是个"广而弱"的效应,不是过拟合到 1–2 个币。

---

## 3. 结论

不通过。LS 多空比极值与背离的逆向信号,在严格 dev/holdout + 成本 + 聚类 bootstrap 下,没有稳健可交易的 alpha。

- 经典逆向(散户极多→空)无效,扣成本为负,与"散户多空比偏噪声"的历史认知一致。
- 逆向做多在 dev 有 +2~3% 的假象,纯属 regime 拟合,出 holdout 即塌(12/17 翻号,中位 edge 从 +0.93% → −0.21%)。
- 唯一 holdout 仍正的 F3 散户去杠杆→24h 做多,扣多重比较不显著、胜率<50%,不足以作为赢家。最多算"未来若专门研究小币超跌反弹,可顺带留意散户去杠杆这个 context"的一条弱线索,不单独成策略,绝不上实盘。

> 这是一个合格的负结果。多空比应作为辅助 context(配合价格/OI/流动性),而非独立逆向择时信号。

---

## 4. 跨模型 review(codex)修了 3 个会致命的 bug

跑正式数据之前做了 codex 交叉审查,审出并修复(旧结果作废重跑):

| 严重度 | 问题 | 修复 |
|---|---|---|
| High | 前向收益差 1 根 bar(出场 cl[i+1+h],1h 实为 65min) | 改 cl[i+h],恰 h×5min |
| High | ATR 分层分母用 close[i](=未来 bar 收盘),泄漏进候选筛选 | 改 close[i-1](信号时已观测) |
| High | inner-join 丢缺口后用位移取前向收益,"1h" 可能跨数据缺口 | 加 ts[i+1]==ts[i]+5m 与 ts[i+h]==ts[i]+h*5m 连续性校验 |
| Med | rolling 分位桶边界用全序列 min/max(含未来) | 改只用最早 min_n 个值(warmup-only)定边界 |
| Med | 折级 edge 用全 dev baseline,削弱 walk-forward | 每折用自己的 dev{k} baseline |
| Med | 多重比较欠控、t-stat 在聚类下非 iid | 加 symbol-clustered bootstrap + 报告显式讨论 FDR |
| Low | t-stat 用 gross | 加 net-minus-baseline 口径 t-stat |

防泄漏要点(已核实):aux ts_ms 是周期收盘时刻(metric@T 概括 [T−5m,T]),进场用 T+5m 开盘 → 信号已知到进场有 5 分钟硬间隔,无前视;所有 rolling 统计 out[i] 在把 x[i] 入窗之前算,严格只用过去。

---

## 5. 文件

| 文件 | 内容 |
|---|---|
| DESIGN.md | 完整设计 + review 修复记录 |
| ls_common.py | 切分/读库/分层/统计工具 |
| build_signals.py | 逐币算 LS 特征 + 前向收益 → events.npz(流式写盘,5.77M 事件) |
| build_baseline.py | 无条件 baseline 采样 → baseline.npz |
| evaluate.py | cohort 统计 + dev 3 折 + holdout 揭晓 + clustered bootstrap |
| dev_results.json / holdout_results.json | 全部 192 cohort / 17 候选的明细 |
| events.npz(161M)/ baseline.npz(16M) | 中间产物 |

复现:python3 build_signals.py && python3 build_baseline.py && python3 evaluate.py(全只读,本机单线程,~5 分钟)。
