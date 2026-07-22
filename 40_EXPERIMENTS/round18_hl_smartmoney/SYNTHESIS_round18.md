---
type: experiment
tags: [round18, hyperliquid, smart-money, synthesis, final]
created: 2026-05-31
status: done
priority: high
---

# Round18 — Hyperliquid 聪明钱 研究最终汇总(8/8 agent 完成)

数据集: 60 活跃盈利鲸鱼 / 812,846 成交 / 64 真perp币 / dev≈29万+holdout≈23万事件.
口径: 因果无前视, holdout=ts≥2026-04-20 只验一次, 扣成本(HL往返0.07%, 妖币市价滑点0.5-0.8%),
bootstrap CI下界, per-币Spearman跨币一致, BH-FDR/Bonferroni 多重比较.
全程峰值内存 <470MB/agent(panels.pkl 预计算 + 流式读 fills), 无再崩.

## 8 个 agent 结论一览
| agent | 方向 | 结论 | holdout |
|---|---|---|---|
| **a04 持续性把关** ⭐ | 聪明钱是真本事还是幸存者 | **top12鲸鱼聚合 per-trade 方向 +0.18%/笔, t=4.67, 过Bonferroni; top−bottom价差+0.17% CIlo+0.098** | ✅ **活** |
| a01 共识净持仓(存量) | net分档 follow/fade | dev 12h/24h过BH(rho+0.09), holdout失去显著, LS CIlo<0 | ❌ |
| a05 资金流Δ vs 存量 | Δnet 动量 | flow比level更差; flow_z系统性变负(拥挤反转味), 无正edge | ❌ |
| a07 大钱notional vs 人头 | conviction假设 | notional比count更差(纯噪声); conviction假设否定; count相对好但也死 | ❌ |
| a03 拥挤反向 fade | 极端一致时反着做 | 0 winner, 全网格负, q=1.0; 反向是错方向 | ❌ |
| a08 单鲸跟单 | 找可跟单个鲸鱼 | dev最佳+0.9%→holdout−0.3%, 0过Bonferroni | ❌ |
| a02 跟单新开仓+滞后 | 共识开仓信号落地 | K=2原始方向+1%(且lag-flat=无泄漏), 但55%是妖币、滑点吃光、0过多重比较 | ❌ |
| a06 妖币层聪明钱 | 帮Binance妖币做空/预警giveback | 信号≈噪声; giveback预警 dev/holdout 符号翻转; 0过BH; 妖币事件太稀+HL≠Binance妖币 | ❌ |

## 贯穿性结论(4+个agent独立印证)
> **能扛 holdout 的只有 a04 的"逐笔×逐鲸鱼方向"统计量(+0.18%/笔)。任何把聪明钱压缩成"币级聚合"的形态——持仓存量(a01)、资金流Δ(a05)、美元加权(a07)、反向(a03)、共识开仓(a02)——都把单个聪明钱的方向信息平均掉了, 于是 holdout 全死。关键区分: 成交流 ≠ 持仓存量。**

## a04 这个"唯一活的"到底能不能用? — 诚实判断: 暂时不能直接落地
1. **它是统计量, 不是可下单信号**: a04 活在"一篮子top鲸鱼的每笔成交方向的聚合统计", a02 已证明把它落成"离散共识开仓跟单"在现实滞后+成本下不可成交(方向对但+1%被妖币滑点清零)。
2. **挑不出单个鲸鱼**: a08 + a04 的 corr(dev,holdout) spearman≈0 → 无法事先知道"哪个鲸鱼"会持续好, 只能跟整组。
3. **edge 薄 (+0.18%/笔)**: 对 $1000、市价吃单的零售, 这个厚度经不起滑点。
4. **它在 Hyperliquid, 我们实盘在 Binance**: 跨所迁移假设未验证; 或者直接在 HL 上交易(同所)但 HL 妖币流动性/滑点更差。

## 对实盘的净建议
- **不把任何 round18 信号落成实盘开仓规则**(无一过 holdout+成本+多重比较, 与安全规则#4一致)。
- a04 唯一够格的用法 = **"聪明钱聚合方向"当一个监控/context 指标**(非独立触发), 且只在能成交的主流币、配合已有 edge。
- 妖币侧(a06): 聪明钱帮不了现有妖币做空择时/giveback预警, 不投入。
- 若真要继续 HL 方向: 唯一有意义的下一步是**forward paper**——跟"一篮子 top 鲸鱼聚合方向"在主流币上前向纸上跑数周, 因为 a04 是 OOS 真实但太薄, 只有前向实测能定生死(回测已到极限)。

## 与全项目主线的衔接
- Binance 公开数据 alpha 枯竭(round15+16, ~16测试) → HL 链上聪明钱(round18, 8测试): **聪明钱聚合方向是真的(a04), 但薄到无法零售落地**。
- 三个 session 的统一规律: **信号常常是真的, 杀手是执行/滑点/成本/样本外衰减**, 不是找不到信号。
- 真正能改命的不是"再找信号", 而是 **(a) 改执行(maker/限价/更流动标的/降频), 或 (b) 接受现有妖币fade配严格风控当唯一edge, 或 (c) 换资本量级/换市场**。

## 资源教训(已记 LEARNINGS 待写)
- 16GB Mac + ~16收集器, **绝不并发8个numpy agent** → OOM崩。
- 元凶: round19 `pkl_to_sqlite.py` 整体 `pickle.load()` 2.93GB + 一堆 robust_check/probe_leak 遗留进程没清理 → 撑爆swap。
- 正解: (1)预计算共享面板(panels.pkl 24MB)让agent加载而非各自重建; (2)分批并发(2个/批), 跑完释放再下批; (3)大pkl流式/分块读; (4)内存守卫Monitor(avail<320MB自动杀)。
