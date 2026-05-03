# BWE v6 Karpathy-Faithful Loop —— Day 1-3 执行计划（Active）

> **状态**：2026-04-26 已对齐，等待开干
> **执行 agent 须知**：先读 `C:\Users\Admin\.claude\projects\H--\MEMORY.md` 获取项目背景记忆，再按本文件执行。

---

## 项目目的（用户口述，2026-04-26）

> 结合 BWE 消息 + 消息对应时间的交易对 K 线 + Binance 其它交易数据，使用 GitHub karpathy/autoresearch 架构（**只取精华版本，不全照搬**），榨干 5090 算力，寻找最优开仓+平仓策略组合。

**真实场景约束**：
- 个人交易，资金 **$1000 USDT**，每单 **5-10% 仓位**
- "正收益就上 live"（已有几个 live 策略在跑得不错）
- **时间压力大**，越快越好
- 所有任务时间盒 **1-2 天**，先 MVP 后扩大

---

## 关键架构决定（已锁定）

| 项 | 决定 |
|---|---|
| 整体架构 | Karpathy autoresearch 精华版 + BWE 适配（详见下方"Karpathy 取舍表"）|
| 首批原型数 | **300 条**（entry 100 + exit 50 + filter 80 + risk 30 + cross-channel 40），1 月内扩到 500+ |
| 首轮搜索量 | **1B 总评估**（100K combos × 100 触发 × 100 bootstrap），5090 上 ~1-2 天 |
| 单一指标 | `oos_p25_net_pct_after_cost`（OOS 25 分位 net return after cost）|
| GPU 技术栈 | **torch + numba**（最快上手）|
| LLM 团队 | 5 角色 debate（Generator / Devil / Quant / Risk / Synthesizer），每 20-30 archetype 一次 |
| LLM 调用方式 | `claude -p` subprocess（**用 $200 Max 订阅，不走 API**）|
| Cost 模型 | base 8bps round-trip + stress 16bps，per-symbol slippage 从 `legacy_market_cache_coverage_by_symbol.csv` 推 |
| 主目录 | `H:/BWE/20_CODE/Autoresearch/`（不另开新目录）|
| 新文件命名 | `bwe_loop_*` 前缀（与 v6 老文件区分）|
| Git 策略 | 每 keep 一个 winner = 一次 commit，message: `[archetype_id] score=X.XX vs best=Y.YY` |
| 主要数据 | H:/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows.parquet (71MB) + 26GB legacy_market_cache |

---

## Karpathy autoresearch 取舍表

### ✅ 保留
- 单一优化指标（适配为 `oos_p25_net_pct_after_cost`）
- 固定时间预算/实验（适配为 **10 分钟/experiment**）
- NEVER STOP loop
- results.tsv 单表 + keep/discard/crash
- Auto keep/discard via git advance/reset
- Agent 自己跑不问人

### ⚙️ 改造
- ONE 文件 `train.py` → ONE 配置 `experiment.yaml`（agent 改 yaml，不改 Python）
- 5 分钟严格 → 10 分钟柔性
- 单 GPU 单线程 → **单 experiment 内 GPU batch 评 10K-100K 变体**

### ❌ 扔掉
- 严格 no-new-deps（BWE 用 polars/numba/torch 都该装）
- 单文件可改约束

---

## 关键 Bug 修复（必须先做）

**[v6_complete_strategy.py:56](H:/BWE/20_CODE/Autoresearch/bwe_autoresearch/v6_complete_strategy.py)** 的 `LOCAL_KLINE_1M_EVENT_WINDOW` 路径指向了空快照（0 行）。真实数据在：
```
H:/BWE/30_DATA/cache/normalized/trade_kline_1m_event_windows.parquet  (71 MB)
```
这是 5 分钟的修复，但**不修后面全是空中楼阁**。

---

## Day 1 任务（8 小时内做完）

### 1.1 修 K 线路径（30 min）
- 改 `v6_complete_strategy.py:56` 一行
- 写 5 行 smoke 脚本验证 71MB 数据读得通、行数 > 0
- 输出：smoke test 通过

### 1.2 写 legacy cache 数据加载器（1.5 h）
- 文件：`H:/BWE/20_CODE/Autoresearch/bwe_autoresearch/bwe_loop_data_loader.py`
- 能读 `H:/BWE/30_DATA/reference/legacy_market_cache/` 下 26GB 历史 K 线（10 个 `bwe_*_run*` 子目录的 JSON）
- 输出统一的 polars/parquet 格式
- 输出：模块可 import 且能加载至少 1 个 run 的样本

### 1.3 写 hypothesis_registry.jsonl 首批 300 条（4 h）
- 文件：`H:/BWE/40_EXPERIMENTS/hypothesis_registry.jsonl`
- 字段 schema：
  ```json
  {"id": "E001", "type": "entry|exit|filter|risk|cross_channel",
   "archetype": "premium_basis_overheat",
   "channel": "OI_Price|pricechange|Reserved6|*",
   "side": "long|short|both",
   "novel_dim": ["premium_z>2", "after_pretrend_3m_neg"],
   "expected_distinct": true,
   "notes": "为什么这是个独立原型而不是别的变体"}
  ```
- 数量配额：
  - entry: 100（覆盖 3 频道 × pump/crash/oi_spike/funding_anomaly/premium_jump/burst/cross_confirm × long/short × 5 timing）
  - exit: 50（fixed_tp_sl / multi_tp_sl / partial_ladder / trailing / runner_trail / breakeven_ratchet / indicator_invalidation / state_machine / time_stop / short_event_hold / hybrid 各家）
  - filter: 80（liquidity / microstructure / regime / pretrend / burst / cooldown / symbol_meta）
  - risk: 30（仓位 / 并发 / 相关性 / 日损 / 多样性）
  - cross-channel: 40（confirm / conflict / decay / weight）
- 包含一些"我们怀疑不 work"的原型——明确测试和淘汰也是覆盖的一部分

### 1.4 写 coverage_map.html 生成器（1.5 h）
- 文件：`H:/BWE/20_CODE/Autoresearch/bwe_autoresearch/coverage_map_gen.py`
- 读 registry，输出 `H:/BWE/40_EXPERIMENTS/coverage_map.html`
- 5 维 heatmap：entry × timing × filter × exit × risk
- 初始全 untested 状态
- 可视化"哪些区域空白"

### 1.5 提交 Day 1 (30 min)
- `git add` 全部产物
- commit message: `[BWE-Day1] <子步号> <简述>`
- Day 1 总结写入 `H:/BWE/99_ADMIN/day1_completion_report.md`

---

## Day 2 任务（loop + GPU 内核）

### 2.1 bwe_loop.py（2 h）
- NEVER STOP wrapper，~150 行
- 流程：取 untested combo → 调 GPU eval → 解析 score → 决策 keep/discard → log → repeat

### 2.2 gpu_batch_eval.py（3 h）
- torch + numba 的 vectorized 策略评估 kernel
- 输入：(strategy_combos[N], events[M], klines) 张量
- 输出：score[N] 张量
- 目标吞吐：≥ 10K evals/秒 on 5090

### 2.3 score_metric.py（1 h）
- 单一指标 `oos_p25_net_pct_after_cost` 的实现
- cost 模型：base 8bps + stress 16bps + per-symbol slippage

### 2.4 results_logger.py（1 h）
- results.tsv 写入 + git commit/reset 决策
- 字段：commit | val_score | triggers | status | description

### 2.5 Smoke test（1 h）
- 跑 1 个 archetype × 10K 变体看吞吐
- 验证 ≥ 10K evals/秒 + git auto-commit 工作

---

## Day 3 任务（LLM team + 启动首轮 1B）

### 3.1 llm_debate_team.py（3 h）
- 5 角色 subprocess 版调 `claude -p`
- 5 文件 chain：proposer → devil → quant → risk → synthesizer
- 每个角色独立 context（不共享状态）

### 3.2 5 个角色的 prompt 模板（2 h）
- 基于已有 `H:/BWE/00_PROJECT_REQUIREMENTS/prompts/` 改造
- 输出：5 个 .md prompt 文件

### 3.3 联调一次完整 debate cycle（1 h）
- 测试 proposer → devil → quant → risk → synthesizer 整链
- 输出：`debate_log_001.json`

### 3.4 启动首轮 1B 评估 loop（30 min）
- `nohup python bwe_loop.py > loop.log 2>&1 &`
- 挂着跑 1-2 天

### 3.5 monitor.py（1.5 h）
- 终端实时看 results.tsv 增长 + GPU 利用率（nvidia-smi）
- 每 10 分钟输出一次状态

---

## 跨任务的通用约定

| 项 | 约定 |
|---|---|
| 卡住超过 30 分钟 | 跳过、log 到 `H:/BWE/99_ADMIN/day1_blockers.md`，继续下一个 |
| 失败兜底 | crash 自动 revert + log，连续 3 个相同 archetype crash 则跳过该 archetype |
| LLM 调用记账 | 每次 debate 把 token 用量 append 到 `H:/BWE/99_ADMIN/llm_usage_log.csv` |
| 不改 live | `H:/` 下任何与 live autotrader 相关路径都不碰 |
| 不读 secret | 任何 .env / credentials 文件都不读 |

---

## 不在本计划范围（推到第 2 周后）

- Portfolio replay（$1000 单策略不需要组合层）
- Strict bootstrap 1000 resample（100 够用）
- 跨频道联合策略（先把单频道扎实）
- 完整 baseline 框架（对比 live 实盘日志即可）
- 自动 paper → live 决定（保留人工最后一关）

---

## Day 1 成功标准

完成本文档"Day 1 任务"全部 5 个子步，最终交付：
1. `v6_complete_strategy.py:56` 路径已修，smoke test 通过
2. `bwe_loop_data_loader.py` 可 import 且能加载 legacy cache
3. `hypothesis_registry.jsonl` 含 300 条原型
4. `coverage_map.html` 可在浏览器打开看到 5 维 heatmap
5. 全部产物已 git commit
6. `H:/BWE/99_ADMIN/day1_completion_report.md` ≤ 500 字总结

---

**新会话进入后第一句应该问：** "我已读 MEMORY.md 和 day1_active_plan.md，确认开始 Day 1 任务 1.1 吗？"
