---
type: architecture
tags: [stockusbinance, tradfi-perp, paper, design]
created: 2026-06-11
status: paper (零真钱敞口)
---

# stockusbinance 系统架构与逻辑

## 一句话定位
把 **stockusbot(美股基本面AI judgment)** 的信号,桥接到 **Binance TradFi永续(86只美股永续)** 上做**自动量化交易**。当前阶段 = **纯paper(纸面记账,零真钱)**,经四方审查(3 Claude agent + Codex)修复全部致命bug后,跑出第一个诚实回测数字。

## 为什么这条路成立(crypto转过来的根本原因)
BWE项目35个测试证明: $1000零售taker在Binance crypto永续上,**毛alpha < 滑点过路费(0.49% < 0.55%)→ 系统化必死**。TradFi永续改变了这个算术:
- **点差 0.001-0.04%**(实测: NVDA 0.5bp / QQQ 0.1bp / MU 1.2bp)= 比crypto妖币低 40-400倍
- 那道杀死所有crypto策略的"过路费"在这里基本消失 → 这是唯一可行前提

## 数据流(端到端)

```
[stockusbot]                    [Binance fapi (EC2东京,不被墙)]
 signal_ledger.jsonl             86只EQUITY永续行情
 (BUY/SELL/HOLD+信心+ref_price)   1m K线 / 盘口 / 资金费
        │                               │
        │                               ▼
        │                    collector_tradfi.py (EC2 systemd 24/7)
        │                     每60s轮询 → tradfi_capture.sqlite3
        │                     (klines_1m / book / funding 表)
        │                     + backfill_history.py 回填6周历史(bf_*表)
        │                               │
        │                          launchd rsync每小时
        │                               ▼
        ▼                    tradfi_capture_ec2.sqlite3 (本机副本)
 signal_bridge.py ◄─────────────────────┤
 (ledger → 可交易信号)                   │
  - F2子集白名单(只放行Sell侧)          │
  - F3透传正股outcomes对照              │
  - I1 universe动态从采集库读           │
        │                               │
        ▼                               ▼
 bridged_signals.jsonl ──────► paper_engine.py (纸面记账)
                                - F1因果进场(信号后第一根bar)
                                - 实测点差(book表)+真实资金费(bf_funding)
                                - 按side/白名单/标的归因 + 永续vs正股对照
                                        │
                                        ▼
                                 paper_trades.jsonl
                                        │
                                        ▼
                                 scoreboard.py (验收仪表盘)
                                  净均值/中位/胜率/回撤/验收门5项
```

## 核心组件逻辑

### 1. collector_tradfi.py (EC2 systemd, 24/7)
- 每60s轮询86只EQUITY永续: 1m K线(只存已收盘bar,防partial冻结) + bookTicker盘口(算实测点差) + premiumIndex资金费
- 每30轮(~30min)刷新universe,捕获每天新上的合约
- 单标的错误隔离;断点续采(INSERT OR REPLACE/IGNORE);磁盘撑463天
- **历史只有6周(2026-01起上市)→ 每分钟forward都是未来回测样本,越早跑越值钱**

### 2. signal_bridge.py (信号桥)
- stockusbot的`signal_ledger.jsonl` → 可交易信号
- **F2核心**: 不无差别桥接。实测stockusbot自身outcomes: **Sell@5d=+1.56%/64%胜(唯一正edge),Buy@5d=−1.71%(反向)**。白名单默认只放行Short侧,Long侧标tradeable=False(paper观察但真钱不交易)
- ticker→symbol显式映射(BRK.B→BRKBUSDT等);失败WARN落账不静默吞
- 当前: 42信号 → 29桥接(16空/13多,16条在白名单)

### 3. paper_engine.py (纸面引擎,核心)
- **F1因果**: 进场=信号recorded_at之后**第一根已收盘bar**(非往未来扫);出场同规则;exit早于目标时点则丢弃计数
- **成本**: taker吃盘口=进ask/出bid(用book表实测半点差) + taker费0.04%×2 + 真实8h资金费(bf_funding精确累加,缺数据回退年化基线不返回0)
- **归因**: 按 side / 白名单 / 标的 分组;并排"永续net vs 正股5d"(F3:量化基差+成本侵蚀)
- 时区: recorded_at带ET offset正确转UTC

### 4. scoreboard.py (验收仪表盘)
- 核心策略(Sell→空5天)的净均值/中位/胜率/累计/最大回撤
- 上真钱验收门5项checklist

## 当前实测结果(第一个诚实数字, 严格因果+实测成本)

| 配置 | 全体 | **Short侧(白名单)** | Long侧 |
|---|---|---|---|
| 持有5天 | −0.18% | **+1.43%/胜53%** | −2.08%/胜27% |
| 持有1天 | −1.00% | −0.60% | −1.50% |

- **审查发现被二次证实**: Buy做多是亏损源,Sell做空是唯一正期望
- **基差对照**: 永续net −0.57% vs 正股5d −1.68% → 永续执行面比正股少亏1.1%(成本低+无隔夜跳空),证明TradFi永续作执行面确实更优
- **但**: n=13/24全部探索性;最大回撤−27.8%(AVGO+20.6%撑半);验收门3/5未达标

## 双层架构设计(完整愿景)
- **低频层(S1, 已建)**: stockusbot基本面信号(4次/天够了,judgment不会5min变)→ 决定做多/空哪些票
- **高频层(S2, 待建)**: 隔夜基差回归(美股收盘期永续漂移→开盘回归,实测隔夜涨>0.5%→开盘均−0.61%但n=5)。**审查要求: S2实现前必须先做最小可证伪检验(OOS+符号可预测性+成本),≥30 OOS样本前不进账本**

## 风控规格(上真钱前,风控agent定,全部待实现)
- 🔴 **BLOCKER 账户隔离**: TradFi永续和你的BTC多单**同一USD-M保证金池**,全仓模式一个插针爆仓连坐爆BTC。**必须开Binance子账户隔离**(独立API key,无提现权限,IP白名单)
- 限额($60子账户): 1x杠杆/单标的$8/总名义$40/并发3/日亏熔断−$6/总回撤halt−$15/滑点>0.5%放弃
- TradFi特有: 限美股时段交易(闭市插针)/强制最长持仓5天(资金费)/**pre-IPO直接禁**(OpenAI/SpaceX无锚易插针)
- orphan保护: 从bwe-live `live_runner.py:2137`原样移植(BTC在白名单只告警不平)
- kill switch: 文件触发为主(独立文件名,可单停)
- **验收门**: forward≥40 + 扣全成本净正 + 回撤<12.5% + 子集一致 + 子账户隔离实测 + orphan/kill演练 + 用户显式确认,缺一不可

## 诚实结论(供你判断)
1. **架构成立、bug已堵、第一个数字可信** —— Sell侧+1.43%是真实因果回测,不是幻觉
2. **但样本远不够**(n=13),+1.43%完全可能是运气(AVGO一只撑半);**现在绝不能上真钱**
3. **正确路径**: 继续forward攒数据(采集器24/7在跑),几周后scoreboard验收门转绿,再讨论子账户+小额
4. **最大价值不是"又一个策略"**,而是: ①把stockusbot从"感觉"变"可度量"(Sell侧才是它的真本事);②TradFi永续这个低摩擦执行面是真的(基差对照证明);③一套审查到位的paper框架,不再凭感觉上钱
```
