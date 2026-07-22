---
type: experiment
tags: [round15, round16, synthesis, negative-result, methodology, carry, cross-exchange]
created: 2026-05-31
status: done
priority: high
---

# Round15 (10 agents) + Round16 probes — 汇总:公开数据 alpha 已枯竭

## 一句话
12 个独立、严格(8mo / holdout 只验一次 / 跨折同号 / BH-FDR / 滑点建模 / codex 跨模型查 bug)的测试,
**压倒性一致地证实:Binance 永续公开数据(K线/OI/funding/basis/多空比/taker/强平/截面/时段/跨所溢价)里的
方向性 edge 已被市场吃光。方法是对的(不断抓出自己的假阳性),坏结果是真的。**

## Round15 10 个 agent(全部完成)
| # | 方向 | 结论 |
|---|---|---|
| a01 强平级联 | 空头强平爆发→反转 | ❌ 无方向 edge,肥尾陷阱,数据全在 holdout 不可验 |
| a02 截面相对强弱 | 全市场动量排名 | ❌ 信号真但成本吃光,做空最强币 82% 成交不了(结构性) |
| a03 OI 方向背离 | 价涨+OI涨→做空 | ❌ 机制真(L17)但撑不起规则,干净滑点一压 dev/holdout 全负 |
| a04 资金费率/basis carry | carry + 基差回归 | ❌ carry/long 证伪;唯一弱信号(mid p99 short)薄到≈成本噪声 |
| a05 等顶过滤救B | 推广 D 的等顶 fade | ❌ 576 变体 0 过 FDR;救不了 B;**bootstrap 证 D 亚盘=72.5 百分位(≈随机)** |
| a06 更长持有周期 | 妖币暴涨后做空持 72h | ⚠️ **唯一活着的** holdout 复现 p=0.019,但高方差 CI 含 0、**在衰减**(10月+7.9%→近月+0.3%) |
| a07 taker 失衡 | 主动买卖盘择时 | ❌ 0/336 通过,假设证伪 |
| a08 时段×regime | 亚盘是否真因子 | ❌ **D"亚盘+0.49%"=n=75 侥幸**,8mo dev 期该窗口是亏的;驱动盈亏的是 regime 不是钟点 |
| a09 多空比极值 contrarian | 散户/大户极值逆向 | ❌ 17 候选 12 个 holdout 翻号,0 个过 Bonferroni;修了 3 个致命前视 bug |
| (vol-compression) | 波动压缩蓄势 | ❌ 基本无果 |

## Round16 我的独立探针(零 agent、零新管道)
- **carry/basis 探针**:funding/premium 作方向信号,per-币 Spearman −0.012 / +0.004 = 噪声;
  高 premium 妖币是**动量(继续涨)不是回归**→"做空高基差赌收敛"会亏。**与 a04 完全一致。**
- **Upbit 跨所韩国溢价探针**(25 高流动双边币 ×120d):币种特异溢价(双重去均值)→ Binance 前向收益,
  per-币 Spearman +0.000 / −0.008 = 噪声,价差 +0.03% < 成本,dev/holdout 翻号。
  ⚠️ **只测了溢价 LEVEL(且偏大币);溢价 SPIKE / Upbit 上币 EVENT(聊天群的真实机制、且多在小币)未测。**

## 关键结论(对项目)
1. **实盘 D 的核心 edge 被大样本证伪**:亚盘+等顶 +0.49% 是 n=75 幸存者偏差(a05+a08 各自独立证)。
   D 本质是 t≈0.5 不显著结果。→ 用户决定:**继续 paper 观察、先不动**(2026-05-31)。
2. **唯一真线索**:妖币 pump 后做空(fade)——机制真、但脆、在衰减。a06 的 72h 版是它最"活"的形态。
3. **为什么全负**:不是方法错,是**池子被抽干**——公开 K线/衍生数据被全球量化扫过无数遍。
   聊天群自己印证:真钱在 (a) 信息优势(链上/新闻/上币)、(b) 执行/速度优势(MM/套利基建)、
   (c) carry(真但薄、吃资金量)——**这些都不在"公开 K线"里**。

## Round16 探针 C(穷尽闭环, 2026-05-31)
- **Upbit 溢价 LEVEL(大币)**:噪声(per币ρ≈0)。
- **Upbit 溢价 SPIKE/velocity(小币)**:探针 `upbit_spike_probe.py`(结果见运行输出)。
- **carry/basis(我的探针 + a04)**:死。
- ⭐ **上币"利好出尽"(短新币)= 全 session 唯一通过控制的方向**(`listing_fade_probe.py` / `_slippage.py` / `_controls.py`):
  - 84 个归档期内新上币,首24h 中位 pump +22.7%;短 24h进场/72h持有 → dev +5.87%。
  - **熊市漂移对照通过**:老币随机做空同期=+0.13%(≈0)→ 新币确实特别,非"做空任何币"的 drift。
  - **无滑点 bootstrap CI [+1.29%,+10.26%] 排除0;新币特异 edge +5.74% 差值CI[+0.96,+10.28] 下界>0**。
  - **中滑点(k=0.25)点估 +2.82%/edge+3.66% 仍正,但差值CI [−1.11%,+8.40%] 含0**(滑点+抽样噪声后不再干净)。
  - **致命缺口**:holdout 仅 n=5 新上币 → 无真正 OOS;且短新币=最难成交(逼空左尾/借券/限额),amplitude 滑点代理可能低估真实危险。
  - **confirm-or-kill 已做完(便宜两关)**:
    - 时间序 OOS(dev58/holdout26,取代 n=5):DEV edge +7.4%,但 **HOLDOUT k=0.25 均值 −2.05%**(中位仍 +2.45%)→ 失败在均值=逼空左尾。
    - 加硬止损封尾(+8%):holdout 均值 −2.05% → **+0.06%(≈breakeven)**,中位 +2.16%,胜率 50%,**CI 仍含0**。
  - **最终定性:全 session 最接近活的方向,但严格 OOS + 真实滑点下 = breakeven,不可 bank。不值得扩历史。**
    唯一便宜的留口=forward paper-shadow(新币持续发生,真前向 OOS,免费),但预期要低。

## 贯穿 ~16 个测试的真正杀手:执行/滑点,不是缺信号
xsection 82% 成交不了 · OI 进场bar振幅 12% · 上币-fade 逼空尾+滑点 · taker/LS/强平肥尾。
**信号大多是真的,只是比"$1000 retail 在妖币上市价吃单"的摩擦小。瓶颈是执行,不是发现。**
→ 启示:要么换更大 edge 的新数据(链上/新闻/事件低延迟),要么改执行(maker/限价/更流动标的/速度),
要么承认 $1000-retail-taker 在妖币上做系统化 alpha 结构性不划算。

## 待用户拍板的战略分叉(见主对话)
- C(便宜、穷尽):补测跨所"溢价SPIKE/上币EVENT"(小币)+ 上币"利好出尽"(coin_age)——~15min,2 个探针,无 agent
- A(唯一通往全新 alpha):建**新数据管道**(链上聪明钱 / 新闻上币事件 / 跨所事件)——真投入
- B(收敛):接受妖币-fade 是公开数据里最好的 edge,配严格风控当它用,不再找
- D(换域):聊天群其它世界(美股/代币股),或承认 crypto 永续公开数据 alpha 已尽

## 反过拟合纪律(本轮遵守证据)
holdout 只验一次 · 跨折同号 · BH-FDR/Bonferroni · symbol-clustered bootstrap · 滞后衰减泄漏探针 ·
codex 跨模型查 bug(a09 揪出 3 个致命前视)· 全程只读、未碰实盘/EC2/fapi。
