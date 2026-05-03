# V5 真正 40 轮搜索 Prompt (Tomorrow)

## 给 Claude 的指令

> 我之前做了 v4 exit + entry 搜索 (各 40 轮)，但部分 phase 是参数变体不是新机制。
> 现在重做，**严格 40 轮，每轮一个真正不同的机制，最后 phase 深度搜索**。
> 
> 现有最佳:
> - **EXIT**: `60min ATR×10 time-decay extreme lock 35→18 @ +12%` sum +1783, cap 34%, win 70%
> - **ENTRY**: `mag 3-13% + top_LS>0.9 + funding>0` n=525, sum +4177, win 74%
> 
> 详细见: 
> - `/Volumes/T9/BWE/40_EXPERIMENTS/round5/specs/2026-04-30-v4-exit-search-archive.md`
> - `/Volumes/T9/BWE/40_EXPERIMENTS/round5/specs/2026-04-30-v4-entry-search-archive.md`

## V5 Exit 搜索 — 30 个真正不同机制 (Phase 1-3) + Phase 4 深搜

### Phase 1 (R1-10): 已测过的基础机制重做 (确认不变)
1. Pure time hold + SL grid
2. ATR trail
3. MFE staged progressive lock  
4. TP ladder
5. Two-phase partial close
6. Trailing SL toward BE
7. Vol decay tighten
8. Counter-pump trigger
9. BTC-aware protect
10. CVD reversal exit

### Phase 2 (R11-20): 新机制（v4 没测的）
11. **Funding flip 真触发**：监控 funding rate 的实际方向翻转 (不是 threshold 触发)
12. **OI unwind cascade**：检测 OI 在多个 5min bar 内连续下降 X% 的级联模式
13. **Mark-spot premium 退出**：mark price 跟 spot price 偏差超过阈值 (BTC liquidation 信号)
14. **Bayesian red-K accumulator**：每根 1m K 红线 +1 vote, 累积到 N 票退出
15. **Sub-bar SL semantics**：用 close 而不是 high 作为 SL 触发 (避免 wick)
16. **Adaptive trail by entry MFE velocity**：MFE 增长快 → trail 紧；增长慢 → trail 松
17. **Liquidation cluster proximity**：估算潜在 liquidation cascade 价位，到达就退
18. **Sector momentum exit**：同 sector (DeFi/Layer1/Meme) 其他币方向反转就退
19. **Multi-bar momentum exhaustion**：连续 N 根 1m bar 收 high (短期 trend 反转) 退
20. **Volume normalization detection**：1m vol 回到入场前 1h 均值时退

### Phase 3 (R21-30): 进一步新机制
21. **Funding 24h history trend**：funding 在过去 24h 是否一直高 (持续拥挤多)
22. **Top trader L/S delta**：5min 内大户 L/S 比例变化 → 大户在加多/减多
23. **Per-symbol historical exit**：该币历史平均最佳 hold time（用前 24h 类似 event）
24. **Adaptive ATR multiplier**：ATR mult 根据当前 1m bar volatility 动态调整
25. **Pre-bar-close vs intra-bar SL**：要求 SL 触发用 close 不是 high (anti-wick 强化版)
26. **Volume profile exit**：1m vol 落到入场 vol 的 X% 持续 N 根
27. **Time-bucketed exit**：按 UTC 小时段调整 hold time (Asia / EU / US 不同)
28. **Spread/slippage 友好 exit**：选择在低 ATR 1m bar 内退出 (减少滑点)
29. **Cross-correlation exit**：跟 BTC 同步度突变 → 退 (山寨脱钩信号)
30. **Pareto multi-objective**：同时优化 sum + win + max_dd 的多目标 exit

### Phase 4 (R31-40): 深度搜索 top winners
- 取前 30 轮最高 sum 的前 5 个机制
- 对每个做 4-轮深度参数 grid (~30-50 spec each)
- 找各机制的最优参数
- R40: 组合最优 5 个 exit 投票退出 (每个 +1 vote, 多数派触发退)

---

## V5 Entry 搜索 — 30 个真正不同机制 + Phase 4 深搜

### Phase 1 (R1-10): 已测过的基础维度重做
1. Magnitude bucket
2. Yao depth (prior_pumps_24h)
3. has_dump_24h
4. Volume_24h range
5. Lifecycle classification
6. Funding rate snapshot
7. OI 5min change
8. Top trader L/S ratio
9. Taker buy ratio
10. BTC concurrent direction

### Phase 2 (R11-20): 没测过的维度
11. **Listing age**: 新币 (<14d / <30d) vs 老币
12. **Symbol category**: top10 majors / mid-cap / micro-cap
13. **Pump rapidity**: 这个 pump 多少秒/分钟内涨 X% (爆速)
14. **Recent ATR percentile**: 该币最近 24h ATR 在历史百分位
15. **Pre-pump volume baseline**: 入场前 1h vol 跟 24h 均量比
16. **Hour of day (UTC)**: 时段分布
17. **Day of week**: 周末 vs 工作日
18. **Cross-channel resonance**: pricechange + OI 同币 5min 内 co-fire
19. **Pump-dump-pump pattern**: 该币 24h 内是否经历 pump→dump→pump
20. **Wick structure**: 入场 1m bar 的 high-close 距离 (long wick → 失败概率高)

### Phase 3 (R21-30): 衍生 / 趋势特征
21. **Top trader L/S DELTA**: 大户比例 5min/1h 变化方向
22. **Funding rate TREND**: 24h 内 funding 是上升还是下降
23. **Funding 24h average**: 平均 funding (持续拥挤指标)
24. **OI 24h % change**: 持仓 24h 累积变化
25. **OI velocity**: OI 短期 vs 长期变化率比
26. **CVD divergence**: 价格新高但买盘 CVD 没新高
27. **BTC-symbol correlation**: 该币跟 BTC 短期相关度 (突变 = 信号)
28. **Sector momentum**: 同 sector 其他币短期方向
29. **Mark-spot premium at entry**: 期货 mark price vs 现货 spot 偏差
30. **Multi-bar volume profile**: 入场前 N 根 1m bar 的 volume shape

### Phase 4 (R31-40): 深度搜索 top winners
- 取前 30 轮最高 sum 的前 5 个 filter dimension
- 对每个做参数 grid + 跟现有 winner 组合 (top_LS, funding, mag)
- 找最佳 4-filter / 5-filter 组合
- R40: Bayesian 加权 score (每个 filter +N 分, score>=K 的 events 入场)

---

## 强制要求

1. **每轮必须用真实 30 天数据跑** (不能空想 / 跳过)
2. **每个机制必须有清晰 thesis** (1 句话: 为什么这个机制能 alpha)
3. **每轮必须输出**: n, sum, mean, win, capture %
4. **breakthrough 标准**: sum > 当前 best by >5%
5. **10 轮无 breakthrough → 写一段反思**, 然后 pivot
6. **Phase 1-3 中任何轮如果是参数变体而非新机制 → 跳过, 换真新机制**
7. **Phase 4 必须深度搜索, 不能再加全新机制** (那就不是深搜了)

## 期望输出

最终交付:
- 4 个 best exit (按风险等级, 像 v4 的 EP_AGGRESSIVE/BALANCED/SAFE/SAFEST)
- 4 个 best entry (按频率/质量等级)
- 一个 evidence-driven 选择矩阵 (entry × exit 4×4 = 16 specs)
- 跟 v4 winner 的对比 (如果 v5 没找到更好 → 接受 v4 为最终)

## 给我的最后建议

**不要改变 dataset** (还用 30 天 yao base + 60min hold + 真 binance K 线)。
**不要重新走 v4 的弯路** (TP cap / counter-pump 等已知失败的不要再测)。
**严格执行 phase 1-3 的「新机制 only」原则**, 看是否能再涨 +500 sum 以上。
如果 Phase 1-3 没找到比 v4 winner 强 5% 的, 直接转 paper-shadow 验证现有 winner。
