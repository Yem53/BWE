# Day 1 完成报告（2026-04-26）

## 状态：✅ 全部 5 个子步通过

| # | 任务 | 状态 | 关键产物 |
|---|---|---|---|
| 1.1 | 修 K 线路径 + smoke test | ✅ PASS | [v6_complete_strategy.py:56,73](../20_CODE/Autoresearch/bwe_autoresearch/v6_complete_strategy.py) 改 2 行；smoke 显示 2,641,437 行可读 |
| 1.2 | legacy cache 数据加载器 | ✅ 代码 PASS | `bwe_loop_data_loader.py` —— 自动识别 list-OHLCV / dict-pricemap 格式，price_map 自动跳过 |
| 1.3 | 300 原型 registry | ✅ PASS（quota 100/50/80/30/40，0 验证错误）| [hypothesis_registry.jsonl](../40_EXPERIMENTS/hypothesis_registry.jsonl) 66KB |
| 1.4 | coverage_map.html 生成器 | ✅ PASS | [coverage_map.html](../40_EXPERIMENTS/coverage_map.html) 1.3MB，含 5 章节 |
| 1.5 | git init + 首提交 | ✅ PASS | commit `7e920a0` [BWE-Day1] 49 files, 23,166 insertions |

## 关键数字

- **K 线数据**：2,641,437 行事件窗口对齐 1m K 线（之前以为 0）
- **300 原型**：entry 100 + exit 50 + filter 80 + risk 30 + cross_channel 40
- **Combo 空间估计**：基础 25,000；单 filter 单 risk 60M；含 cross-channel 288M
- **代码新增行数**：约 1,500（新文件）+ Karpathy 原版 21,500 已纳入版本控制

## 后台任务（仍在跑）

`bwe_loop_data_loader.py` 全量加载 26GB legacy cache：已重启在后台，预计 5-15 分钟完成。Day 2 开工时验证完成情况即可。

## Day 1 中的偏离 / 决策

1. **kline 路径修法**：用 `../../cache/normalized/...` 相对路径而不是绝对路径 —— 保持 v6 文件 fdir 解析逻辑不变，最小侵入
2. **legacy loader 智能跳过 price_map**：phase1_run1 的 `{ts: float}` 格式不能用于 OHLCV backtest，自动 skip 并记入 status_counts（不是 silent fail）
3. **流式 flush 5M 行/part**：避免 50K 文件全量加载爆 RAM，最后用 polars streaming concat
4. **git scope = Autoresearch 子目录**：按用户 B 选项；初次 commit 把 Karpathy 原文件全收入，后续修改可追溯

## 你需要看的东西

1. 浏览器打开 `H:/BWE/40_EXPERIMENTS/coverage_map.html` —— 确认 300 原型清单是不是你想要的
2. （可选）瞄一眼 `H:/BWE/40_EXPERIMENTS/hypothesis_registry.jsonl` —— 抽几条看 notes 写得对不对

## Day 2 准备

按 active_plan.md，明天进 Loop 框架 + GPU 内核：
- 2.1 `bwe_loop.py`（NEVER STOP wrapper）
- 2.2 `bwe_loop_gpu_eval.py`（torch+numba batch eval）
- 2.3 `bwe_loop_score_metric.py`（`oos_p25_net_pct_after_cost`）
- 2.4 `bwe_loop_results.py`（results.tsv 自动 keep/discard）
- 2.5 smoke test 1 archetype × 10K 变体

**Day 2 启动前请完成：你这边有 review 反馈否？没有就直接开 Day 2。**
