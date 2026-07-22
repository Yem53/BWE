---
type: plan
tags: [round19, news-events, multi-agent, roster]
created: 2026-05-31
status: design
---

# Round19 新闻/事件交易 — 10 agent 罗盘

数据基座:`events.jsonl`(2811公告,带ms时间戳+标的+子类型) + `event_klines.pkl`(602标的全历史5m,2024-2026) + 8mo aux(OI/funding/premium)。
共享 loader:`news_dataset.py`(因果对齐、dev/holdout、成本、bootstrap)。

## 铁律(每个agent都注入)
①因果:公告releaseDate=信号,入场在公告**后**(lag可调),前向收益从入场算 ②holdout=ts≥2026-04-20只验一次
③扣成本0.14%+妖币滑点 ④多配置/多事件→BH-FDR或Bonferroni+bootstrap下界 ⑤跨子样本/符号一致
⑥**样本量诚实**:每个cell标n,n<30标"探索性不可信" ⑦诚实报负=合格 ⑧只读不碰实盘 ⑨不写report文件→结论放最终消息

## 样本量现实(perp时代 2024-26)
perp_launch 183 · spot_list 203 · hodler 63 · delist 23。切dev/holdout+lag后每格更小→必须多重比较校正。

## 10 个方向
| # | 子目录 | 方向 | 核心假设 | 样本 |
|---|---|---|---|---|
| 1 | a01_perp_launch | 新合约上市反应 | 上市后fade还是follow,多lag/持有期 | 183 |
| 2 | a02_spot_list | 现货上币→永续反应 | "Will List"抢涨 vs 利好出尽 | 203 |
| 3 | a03_sell_the_news | 利好出尽(跨所有正事件) | 公告后初冲→反转做空 | ~400 |
| 4 | a04_delist | 下币冲击 | 下币→抛售/超跌反弹(双向) | 23(小,探索) |
| 5 | a05_pre_announce_drift | 公告前漂移(信息泄漏) | 公告前24-72h异动=内幕痕迹 | 全部 |
| 6 | a06_hodler_airdrop | HODLer/空投事件 | 空投公告→标的+BNB反应 | 63+44 |
| 7 | a07_tradfi_perp | 美股/TradFi代币永续 | OPENAIUSDT/TradFi上市后行为 | 子集 |
| 8 | a08_event_x_features | 事件×币种特征交互 | 哪类事件×什么市值/波动反应最强 | 全部 |
| 9 | a09_repeat_listing_cluster | 批量/连续上币簇 | 同日多币上市/"Multiple"公告的稀释效应 | 子集 |
| 10 | a10_oi_funding_confirm | 事件+OI/funding确认 | 公告后OI/funding变化能否过滤真假突破 | 8mo子集 |
