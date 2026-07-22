---
type: plan
tags: [c2, forward-paper, filter, round26]
created: 2026-06-11
status: wip
priority: high
---

# C2 Forward Paper — 预注册方案(规则冻结于上线前)

## 验证对象
终审唯一幸存信号: **oi_price_1h 警报中 oi_chg>15% 的币, 未来24h跑输同日其它 oi_price_1h 警报币**。
历史依据: 240天同日配对超额 +0.97%/天, 63%正天, 9个月中6个月正(见 [[FINAL_VERDICT]])。
定位: **过滤器**(给现有short体系选标的/规避做多), 不是独立策略(资金费已判死独立裸空)。

## 基建(2026-06-11上线)
- EC2 `/home/ubuntu/bwe-scanner/c2_forward_eval.py`, systemd `c2-forward.timer` 每日03:40 UTC
- forward起点 **2026-06-09**(处女holdout止于06-08, 不回灌)
- 当日全部oi_price_1h警报 → 24h做空净收益(0.94%成本) + 资金费单独记账
- 输出 `data/c2_forward/`(summary.jsonl + 每日明细), scanner-rsync 自动带回Mac
- 看进度: `python3 c2_forward_scoreboard.py`

## 预注册验收门(写死, 不许事后改)
| 门 | 标准 |
|---|---|
| G1 样本量 | forward ≥ **30个交易日** |
| G2 超额均值 | excess_day 均值 > **+0.30%/天** |
| G3 稳定性 | 正天比例 ≥ **55%** |
| G4 资金费复核 | c2_mean_postfund 仍显著为负 → 维持"只当filter"; 若转正需重审定位 |

**全过 → 提案接入live short体系当选标的过滤器(需用户显式批准, 不自动)。
任一不过 → 信号衰减, 归档, 不纠缠。**

## 不许做
- 不许在forward期间调 oi_chg 阈值/持有期(那是重新过拟合)
- 不许把它当独立策略开仓(资金费-1.27%/笔的死刑判决仍有效)
