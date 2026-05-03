---
name: BWE 项目真实目的（用户亲口确认）
description: 用户在 2026-04-26 亲口确认的 BWE 真实目的：复刻 Karpathy autoresearch 架构在 5090 上做策略搜索
type: project
originSessionId: 9aa9a58b-6062-4d43-83be-5004328027b2
---
**用户原话（2026-04-26）：**
> "结合 BWE 的消息，加上消息对应时间的交易对 K 线图和 binance 其它的交易数据，然后使用 GitHub 项目 auto research 的架构，榨干 5090 的算力，然后去寻找最优的开仓和平仓的策略组合。"

**Why:** 这是用户亲口给的目的陈述，比文档里的描述更直接。任何工作必须对齐这四条而不是只对齐 docs/ 里的措辞。

**How to apply:** 评估任何 BWE 工作时按这四条打分：
1. **数据完整性**：有没有把"消息 + 对应时间 K 线 + 其它 Binance 数据"真接齐？
2. **架构忠实度**：是不是 Karpathy autoresearch 的 loop 模式（ONE file / ONE metric / 5min 预算 / NEVER STOP）？
3. **5090 算力利用**：GPU 是不是在持续跑实验，还是 90%+ 时间在闲置？
4. **优化深度**：是不是真的在搜索"最优开仓+平仓组合"（而不只是单边 entry 或单边 exit）？

## Karpathy autoresearch 项目核心信息
- 原项目：https://github.com/karpathy/autoresearch（2026 年 3 月发布）
- 用户本地路径：`/Users/ye/Desktop/Github/Autoresearch`（Mac mini）
- 本地快照：`H:/BWE/20_CODE/Autoresearch/`
- 三个核心文件：`prepare.py`（数据/eval，不可改）+ `train.py`（agent 唯一改的文件）+ `program.md`（agent 指令）
- 单 GPU 单文件单指标（val_bpb），固定 5 分钟/实验，~12 实验/小时
- 每实验一次 git commit，`results.tsv` 单表记录 keep/discard/crash
- **NEVER STOP 模式**：agent 通宵自动跑，"睡一觉醒来 100 个新实验"

## 当前 BWE 实现 vs Karpathy 原版的根本错位
当前 BWE 实现**完全没有遵循 Karpathy 的 loop 架构**：
- 多文件而不是单文件
- 多指标而不是单指标
- 一次性 batch 而不是 5min/experiment 的循环
- 跑完就停而不是 NEVER STOP
- 没有 results.tsv 等价的 commit-per-experiment 表

→ 后果：5090 算力利用率 ~5%，无法满足"榨干算力"的目的。任何后续工作必须先把这个架构对齐起来，再补统计/数据。
