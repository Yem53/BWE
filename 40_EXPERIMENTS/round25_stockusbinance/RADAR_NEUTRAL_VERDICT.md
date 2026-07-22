---
type: experiment
tags: [stockusbinance, radar, market-neutral, longshort, verdict, direction-1]
created: 2026-06-16
status: done
---

# 方向① stockusbot radar 市场中性多空 — 终审判决(2026-06-16)

## 缘起
β对冲诊断动摇了 stockusbinance 方向单(收益主要是大盘β不是选股)。方向① = 把 stockusbot
每日 radar 打分当**横截面相对排序器**做中性多空(多最高分+空最低分, dollar-neutral),
用以隔离"扣掉β之后, stockusbot 选股到底有没有真本事"。

## 数据
- radar: 18天(2026-05-22~06-15), 每天63只打分(combined_score/tech_score/sentiment/momentum_20d_pct)
- 30只映射到可交易TradFi永续, 回填1m K线93.7万根
- 面板297行/18天, 进场=radar日+1天00:00UTC首根永续bar(因果, 杜绝forward-ahead)
- 工作流: 3分析agent(核心LS/动量-情绪拆解/随机基线) + 对抗验证 + 终审, 7 agents/40万token

## 判决

### ① combined_score 中性多空 = 🔴 驳回(动量伪装+单名单日运气)
| 检验 | 结果 |
|---|---|
| f5净LS扣成本 | +0.79%/天(唯一像样horizon) |
| **MRVL一只占f5总LS的83%** | 留一名MRVL → f5塌到+0.31/天 |
| f1/f2/f3留一日/留一名 | 符号翻转(06-01一天贡献+14.3于+8.0的f1总和) |
| combined LS ≈ tech LS(差<0.005pp) | 多腿95-97.5%是tech_score触顶名 → 顶部=动量排序 |
| 朴素动量单因子LS | 每个horizon都负 → 赚的是hardware-long/software-short板块叠加 |
| moving-block bootstrap p(f5最佳) | 0.086, 95%CI[-0.48,+8.04]跨零 |
| 成本0.20%/腿 | f3翻负, 只f5名义幸存(恰是单名/不显著/板块倾斜那个) |
- 对抗方独立numpy重写**复现到<0.01pp**, 五路攻击全中。
- 一句话: 免费动量 + 18天hardware>software板块运气 + MRVL一只 + 5d重叠虚胖观测数。

### ② sentiment层(基本面AI存废) = ⚪ 未证实亦未证伪 → 不砍不投, 转forward
- **动量残差检验(正式)**: 每日横截面把fwd收益对momentum_20d_pct回归取残差, 看sentiment能否预测残差。
  结果: f1/f2/f3 perm-p = 0.27/0.34/0.90(全不显著); 唯一"显著"的 f5(resid_rho +0.167, p=0.038)
  **去掉MRVL从3.76塌到~1.3, winsor10→~1.4 = 同一只票的单名右尾, 非稳健**。
- 18天+单一普涨regime没有功率看见它。**不裁定无用(砍管线), 也不下注(扩资源), 冻结留观。**
- (Codex复审Item E闭合: 残差化在 orion/momentum_vs_sentiment.py + skeptic/adversarial.py 中正确实现,
  非ls_core那两个文件 → Codex最初没审到, 实际做了且方法正确。)

## ③ Forward paper(radar每天还在长, 14周后投票)— 预注册
每天落盘记录(不实盘下单), 攒**非重叠/OOS/跨regime**独立观测:
1. 三腿正交: combined / 纯sentiment / 纯momentum 各自tercile-LS的forward收益 → 看 **sentiment−momentum 残差** 是否净正(这才是基本面AI增量alpha唯一判据)
2. 板块中性版: hardware/software组内中性, 剥18天板块运气
3. 单名加帽≤20%: 回答"离开MRVL还活不活"
4. 非重叠f1+f5为主口径, 每周打bootstrap p + 留一名稳健性

**成立门槛(全过缺一不可)**: sentiment−momentum残差LS净正且bootstrap p<0.05 · 板块中性后仍正 · 加帽20%后仍正 · 跨越≥1个非普涨regime。回来投票: f5非重叠 n≥20(约14周)。

## ④ 不可做清单
- 不可实盘/paper下单这套LS(0个horizon同时满足 显著∧抗成本∧名字分散)
- 不可宣称sentiment已证明有效或已证伪(两向都没功率)
- 不可把f5 +0.79%当业绩(83%是MRVL一只)
- 不可用重叠"17天观测"当样本量(真实独立≈3-4)
- 不可把combined当"sentiment信号"(顶部95%是动量触顶名)
- 不可做空小样本单只科技股不设尾部保护(05-26/27 ORCL +21/26%已炸空腿)

## 与全项目铁律的第N次印证
散户方向性alpha=伪装的β/动量; 中性多空剥掉β后, 连stockusbot基本面分数也塌成"动量+板块运气"。
**唯一可能幸存的是 sentiment 在动量之外的残差** —— 但需forward攒够独立样本才能看见。
（与C2同理: 真正活的只有"相对/中性/残差"结构。）
