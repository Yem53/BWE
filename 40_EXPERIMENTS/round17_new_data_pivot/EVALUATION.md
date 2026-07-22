---
type: plan
tags: [round17, pivot, new-data, feasibility, evaluation]
created: 2026-05-31
status: design
priority: high
---

# Round17 — 新数据管道 可行性+成本 评估(A 方向)

> 背景:round15(10 agent)+ round16(我 4 探针)= ~16 个严格测试证伪"公开 K线/衍生数据方向性 alpha"。
> 真杀手=执行/滑点不是信号。结论:要赢必须 (a) 拿更大 edge 的新数据,或 (b) 改执行。本评估给 A。

## 候选数据源 可行性矩阵(均已实测探针)

| 候选 | 能解锁的 edge | 数据源/可达性 | 成本 | 可执行($1000)? | 评分 |
|---|---|---|---|---|---|
| **低延迟上币事件 + 执行** | **我们已证实的 listing-fade**(+2~6%/单, 只输在晚进场/滑点) | Binance CMS 公告(Mac直连✅) + EC2 exchangeInfo 差分(不被墙✅) | 免费 | ✅ 新币是事件, 分批进 | ⭐⭐⭐⭐⭐ |
| **链上聪明钱(Hyperliquid)** | 跟/反巨鲸(信息不对称, 聊天群 Fartcoin/XPL) | api.hyperliquid.xyz(Mac直连✅, meta/allMids/任意地址持仓✅) | 免费(但好地址表要挖/或买 Nansen~$150/mo) | ✅ 信号→Binance perp | ⭐⭐⭐⭐ |
| 跨所(Upbit/Bitget) | 韩国溢价/价差 | Upbit API✅ | 免费 | ❌ 韩国 KYC + 已被我探针证伪(level/spike 全噪声) | ☠️ 死 |
| 新闻/推特抢跑 | 事件抢跑 | Twitter/X API | ~$100+/mo | 🟡 延迟敏感 | ⭐⭐ |
| 盘口/L2 微结构 | 高频做市/抢单 | 需自存 L2(没有) | 免费但海量存储 | ❌ 零售拼不过 | ⭐ |
| 美股/代币股 | 换域 | 券商/xStock | 不等 | 🟡 换市场 | ⭐⭐ |

## 推荐:两阶段

### Phase 1(先做)— 低延迟上币事件 + 执行管道
**为什么**:这是唯一"信号已被我们自己证实是真的"(round16 listing-fade: holdout +6% 中位/65% 胜)、
只输在"晚进场吃满滑点"的方向。Phase 1 同时攻 A(新数据=上币检测)+ B(改执行=分批限价/择时进场),
正中本 session 的核心病根(执行不是信号)。**便宜、快、可执行、有先验。**
- 上币检测:EC2 每 N 秒 diff fapi exchangeInfo 新 symbol(秒级)+ Binance CMS 公告兜底
- 执行研究:不在 hour-4 市价砸进去,而是用 1m 数据回测"分批限价/等首轮拉升衰竭再进"把 k 从 0.25 压到 ~0.1
- 验证:扩上币历史(data.binance.vision, 2020→今, n≈400)做真 dev/holdout + forward paper-shadow
- 风险:逼空左尾(硬止损会被噪声打掉, 见 round16)→ 用"分批+小仓+时间止损"而非硬价格止损

### Phase 2(higher ceiling)— Hyperliquid 链上聪明钱
**为什么**:免费全开, 信息不对称=edge 天花板高(可能真比摩擦大)。但要 R&D:
- 挖聪明钱地址(从大额 fills WS 反推常赢地址 / 公开 leaderboard 种子)
- 跟踪其持仓变动 → 信号 → Binance perp 执行
- 噪声大、需要更多实验, 故排 Phase 2

## Nansen 实测结论(2026-05-31, key 有效)
- key(nsn_前缀)✅ 有效;头 `apiKey` + 浏览器 UA(否则 Cloudflare 1010)。
- **致命限制:此 tier 只给"近期"数据,无深历史 → 不能即时回测:**
  - netflow = 当下快照(1h/24h/7d/30d 窗口, 无历史序列)
  - perp-trades(Hyperliquid 智能钱永续)= 仅 ~7 天;币种 BTC/ETH/HYPE/LIT/PURR/WLD(部分与 Binance perp 重叠)
  - dex-trades(带 block_timestamp)= 仅 ~24 小时(page200 空)
- 覆盖偏 链上 token + Hyperliquid,与 Binance perp 仅部分重叠。
- **结论:Nansen 是"实时信号源",不是"回测源"。要用只能 forward-log(每天抓快照)+ 前向 paper,数周后才知是否有效。**
  好处:forward 验证无法过拟合(最诚实);坏处:慢。
- 若要即时回测智能钱,需更高 tier 的历史端点(用户可查套餐),或换 Hyperliquid 原生 API 自存历史。

## ⭐ Hyperliquid 实测(2026-05-31)— 比 Nansen 完整得多, 且免费+可回测
透明 DEX → 全链上账本公开。实测确认:
- ✅ perp universe **213 币**(BTC/ETH/SOL/kPEPE/FARTCOIN...), 与 Binance 大量重叠
- ✅ **OHLCV**: candleSnapshot 每次 5000 bar, 用 endTime 向前翻页可回到上线(~2023), **免费**
- ✅ **funding/OI/premium**: API(近期)+ S3 asset_ctxs(全历史, 便宜)
- ✅✅ **任意地址当前持仓**: clearinghouseState — 实测拉到一个 $160K 账户正 short BTC(entry $72145, uPnL +$1819)
- ✅✅ **任意地址完整成交史**: userFillsByTime, 2000笔/次翻页 — **这正是 Nansen 限到7天的"聪明钱"数据, HL 上免费且完整**
- ⚠️ L2 盘口全历史: S3 requester-pays, TB级, 要花钱(egress)
- ⚠️ leaderboard 端点要换格式(422)→ 找鲸鱼可改用"大额fill反推"或已知地址

### 对比结论
| | Nansen(此tier) | **Hyperliquid** |
|---|---|---|
| 历史深度 | 24h~7d 快照 | **回到上线, 可翻页** |
| 可回测 | ❌ 只能前向 | ✅ **完整历史可回测** |
| 聪明钱持仓/成交 | 有但限频 | ✅ **任意地址完整, 免费** |
| 成本 | 月费 | **免费**(L2全历史除外) |

### 诚实 caveat(必须正视)
- HL 是**另一个交易所**(我们实盘在 Binance)→ "HL 聪明钱 → Binance 走势" 是**跨所 lead-lag 假设, 必须验证, 不能假设**。
- 但也可以**直接在 HL 上交易**(它本身就是真永续 DEX)→ 那就同所、无跨所 gap。
- 执行滞后仍在(看到 fill 时已过秒~分钟), 但比 Nansen 快, 且持仓可持续(能跟多日仓)。

### 新 Phase 2(取代 Nansen 路线)= HL 聪明钱回测
1. 找头部交易者(leaderboard / 大额fill反推)
2. 拉其完整 fill+持仓史(免费翻页)
3. 回测: 聪明钱聚合持仓是否预示前向收益(HL 自身 or Binance)
4. **这是真·可回测的**(不像 Nansen 只能前向攒)→ 当前最优的全新数据方向

## 不做
跨所中心化所(Upbit 已死)、L2 微结构(零售拼不过)、暂不碰美股(换域是另一个项目)。

## 待确认
Phase 1 是否就这么定?定了我先做 **上币历史回填(n≈400)+ 执行回测(把滑点压到 0.1 看 edge)** 这一步——
它能在不碰实盘、不花钱的前提下,给出"listing-fade 配上更好执行到底能不能赚"的确定答案。
