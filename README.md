# BWE — 一次完整的个人量化研究历程 (2026.04 – 至今)

> A solo quantitative trading research project: crypto perpetuals → a self-built market-wide anomaly scanner → US-stock (TradFi) perpetuals alpha search on Binance.
> **No profit claims.** Most tested hypotheses were falsified — the falsification process itself, and the infrastructure that ran it, are the point of this repo.

一个人 + AI agent 协作完成的量化交易研究全过程存档。**这个仓库不展示"赚钱的策略"** —— 它展示的是:真实资金的小额实盘、被数据杀死的几百个假设、以及为了不再被假 alpha 骗到而逐步建起来的一整套研究纪律与自动化基建。

---

## 项目弧线(三个阶段, 按时间)

### 阶段 1 — 加密永续: 事件驱动策略 + 小额实盘 (2026.04–05)
- 基于 Telegram 异动信号(BWE 频道)+ Binance 全量 K线/OI/资金费数据, 做 entry × exit 联合搜索(单轮 2 万+ 组合, GPU 加速)
- **真实小额实盘**: 在 AWS EC2 部署 USDT-M 实盘 bot, 完整风控栈(名义限额 / 日亏熔断 / 文件 kill-switch / 孤儿单保护 / STOP_MARKET 兜底 / Telegram 中文播报), 同时运行 3 个事件驱动策略
- **结局(中肯版)**: 实盘量化出约 0.9% 的 backtest-live reality gap —— 回测边际覆盖不了真实滑点。风控按设计工作, 累计亏损被限制在数十美元量级, 随即停止实盘。这个发现成为后续一切纪律的起点
- 35+ 轮策略搜索的总结论: **$1000 级散户 taker 在公开加密 K线数据上, 毛 alpha < 交易成本** —— 这堵"成本墙"被反复验证

### 阶段 2 — 自建全市场异动扫描器 (2026.05–)
- 用 ~700 行 Python 复刻并替代第三方信号源: WS/REST 价格流 + OI 轮询 → 8 种时间窗异动检测(3s~1h)→ 冷却/推送过滤 → JSONL 归档 + Telegram 推送
- 以 EC2 systemd 服务 24/7 运行至今, 累计产出 **22 万+ 条带精确触发时间戳的异动警报语料**
- 对这份语料做过 **100+ 策略角度的系统性筛选**(round26): 约 1100 个统计 cell, 经 BH-FDR / LODO / 处女 holdout / 按天聚类 / 跨模型复审后, 两个幸存候选分别死于**容量幻觉**(簇内后期深单撑起的均值, 真实账户拿不到)与**资金费缺位**(表面 +1.3%/笔, 计入资金费后归零) —— 完整解剖记录在 `40_EXPERIMENTS/round26_alert_alpha/FINAL_VERDICT.md`

### 阶段 3 — 美股 TradFi 永续 alpha 搜索 (2026.07–, 进行中)
- 转向 Binance 新上线的美股永续(105 只, 点差比加密妖币低 40-400 倍 = 成本墙大幅降低)
- 数据: 105 只全历史 1m K线(738 万根)+ 真实 8h 资金费回填; Unusual Whales(财报/期权流)、FRED、Finnhub 多源整合
- **预注册协议**(`40_EXPERIMENTS/round27_usstock_alpha/ROUND27_PROTOCOL.md`): 假设族、数据切分(dev/val/处女 holdout 物理隔离)、成本模型、验收门全部在动手前冻结
- 三波 10 个假设族、**613 个统计 cell, 即时可交易幸存 = 0**(命中数低于纯噪声期望 —— 这是筛选器严格性的证明, 不是失败)
- 4 条冻结规则进入每日自动 forward paper 验证(PEAD 财报漂移 / 资金费结算 V 形 / 新上市效应 / 隔夜 drift), EC2 定时器每日记账, 等样本量说话

---

## 方法论(这个项目真正的产出)

历轮实验共归档 **6 种假 alpha 形态**, 每种都曾骗过第一眼:

| 假 alpha 形态 | 一句话 |
|---|---|
| β 伪装 | "策略收益"其实是大盘方向; β 剥离后归零(杀死了本项目最多的候选) |
| 聚类虚胖 | 同日/同事件交易强相关, iid t 值虚报 40-70% |
| 容量幻觉 | 均值靠簇内后期深单撑起, 容量受限的真实账户拿不到 |
| 资金费缺位 | 不计资金费的永续回测系统性高估空头收益 |
| 单日伪象 | 一个极端日贡献 >80% 净利(如 2025-10-10) |
| 幸存者偏差 | 死币/未上线标的从数据里静默消失 |

对应的防御纪律(全部工程化, 非口号): 预注册冻结 → dev/val/**处女 holdout** 三段隔离 → BH-FDR 多重比较校正 → LODO/留一名 → 事件日聚类 t → 公平 β̂ 剥离 → 手写 permutation → 1.5× 成本加压 → 执行滞后曲线 → **每个发现由独立 agent 以"默认它是假的"立场从零复算** → 跨模型(Claude × Codex)交叉审计。

## AI 协作方式

整个项目由一名开发者与 AI agent 团队协作完成: 多 agent 并行筛选假设族、每个发现即时对抗验证、跨模型复审抓实现 bug、EC2/本机双端自动化数据管线。人的角色是提出方向、设定纪律红线、做最终判断; agent 的角色是执行规模化的筛选与互相攻击。

## 仓库地图

```
infrastructure/
  collectors/bwe_scanner/     自建异动扫描器(EC2 systemd 服务, 运行至今)
  live_bot/live_runner.py     实盘 bot(风控栈: 熔断/kill-switch/孤儿单保护)
40_EXPERIMENTS/
  round7~24/                  加密阶段各轮实验文档(含大量被证伪的假设)
  round25_stockusbinance/     美股信号桥 + β 诊断(方向单 edge = β 伪装的完整解剖)
  round26_alert_alpha/        22万警报 × 100角度筛选 + 四重反假alpha终审
  round27_usstock_alpha/      现役: 美股永续 alpha 搜索(预注册协议 + 进度日志)
00_PROJECT_REQUIREMENTS/
  STRATEGY_RESEARCH_CHECKLIST.md   18 条实战研究检查清单
```

**未入库**(.gitignore): 数十 GB 行情数据库与警报语料、API 密钥/env、个人笔记与无关内容。脚本可复现全部数据拉取。

## 诚实声明

- 本项目**没有任何实盘盈利宣称**; 唯一的实盘阶段以受控小额亏损结束, 并产出了 reality-gap 的量化结论
- 所有"发现"均按预注册验收门评级; 截至最新提交, 没有任何策略通过全部验收门 —— forward 验证进行中
- 数字均可在对应 round 的脚本与 JSON 结果中复现

*This is a research archive, not investment advice. Nothing here constitutes a claim of profitability.*
