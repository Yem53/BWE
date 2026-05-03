# BWE Autoresearch Round 4 — Master Overview

> 状态：Mac 端 hygiene 阶段（2026-04-27 启动）
> 上一轮：Round 3 完成 20K experiments 2026-04-27 19:37（参考 `40_EXPERIMENTS/morning_brief_latest.md` + `analysis/20260427_194910/summary.md`）
> 下一轮 GPU loop：等本机 hygiene 全部完成 + 用户回 5090 → 一行命令起跑

---

## 1. Round 4 Mission

找到 **妖币 regime（庄家控盘 small-cap pump）** 下的最优 entry × exit 组合。

研究本质：**识别庄家拉升过程的特征信号 → 配合大 TP 长 hold 骑全程**。不是大盘币的 fat-left-tail 风险管理，是 fat-right-tail 的庄家行为捕捉。

参见 `~/.claude/projects/-Volumes-T9-BWE/memory/feedback_yaobi_strategy_wide_tp_dynamic_exit.md` 完整 thesis。

## 2. Round 3 → Round 4 Pivot 摘要

| 维度 | Round 3 实际 | Round 4 必改 | 根因 |
|---|---|---|---|
| TP grid | linspace(0.2, 6.0, 150) | log-spaced 0.5-500%（参 D1 实证） | 妖币拉升常见 30-200%，0.2-6% 完全错位 |
| SL grid | linspace(0.2, 6.0, 150) | {3, 5, 7, 10}% | 妖币 2-5% 噪声会洗掉 0.2% SL |
| Hold horizon | [5, 15, 30, 60] min | [30m, 1h, 2h, 3h, 4h, 5h] (受 event_windows 物理 5h 上限) | 庄家主升段窗口；R4 后续若有效再扩 7d |
| Default score metric | `legacy p25` (BUGGY — 自标注) | `mean_net + right_tail_aware gate` | p25 在 fat-right-tail 分布下砍掉 alpha 源 |
| SL/TP > 4 reject rule | 隐含规则 | 废除 | 大盘币 regime 遗留假设 |
| Archetype 总数 | 523 (大量 channel × side × novel_dim) | ~65 (40 entry + 20 exit + 5 risk/filter) | 1/8 密度但每条对齐妖币 regime |
| paper_shadow exit 配对 | 默认 fixed_tp1_sl1_symmetric | 按 entry 全局 best_exit（跨 family） | R3 keep 的 trail 0.2/0.2 在 paper 跑成 fixed 0.2/4.4 = 假亏损 |

## 3. Round 3 重大问题映射到 Round 4 解决方案

### P0（不解决就是浪费 GPU）

| # | Round 3 问题 | Round 4 解决 | 落地文件 |
|---|---|---|---|
| Q1 | 5 套 metric 排序矛盾 | 单一 keep gate `mean_net AND right_tail_lift AND no_blowup`；废 legacy p25 | `bwe_loop_score_metric.py`、`configs/metric_contract.json` |
| Q2 | paper_shadow 用错 exit 配对 | 跨 family lookup best_exit；可选 family override | `scripts/paper_shadow_sim.py` |
| Q3 | 4 family 0/everything positive | **解读反转**：family 没问题，是 step 全设错。grid 重设后 trail/multi_tp 应当 dominate | `bwe_loop.py` DEFAULT_*_GRID |

### P1

| # | Round 3 问题 | Round 4 解决 |
|---|---|---|
| Q4 | n=5000 触发饱和 | novel_dim 必须包含庄家特征子集；≤2 AND 条件硬上限 |
| Q5 | X100 (`composite_exit_be_partial_runner`) -0.08 floor | **诊断澄清**：`eval_breakeven` line 153 `gross_be = zeros` 逻辑正确 — 是 BE 在 TP 0.20 触发后归零 + cost 0.08 = 残值 -0.08。Round 4 大 TP grid 下应自然好转。仍需 audit 确认 |
| Q6 | SL/TP > 4 reject 规则 | 废除 |
| Q7 | Generator pricechange/long bias | Channel 配额硬性强制（OI 40% / R6 30% / PC 25% / CC 5%） |
| Q8 | 9% crash from extreme filter | 18 个 funding extreme archetype 翻方向重写或下线 |

### P2 / 新增

| # | 问题 | Round 4 处理 |
|---|---|---|
| R9 | Archetype space 缺"庄家识别"组合 | 新增 ~40 entry archetype，少量正交 OR + ≤2 AND（D2） |
| R10 | 19:49 提的 X101-X108 大部分太小 | X101 (0.5/0.5) X102 (1.0/1.5) 废；X103 (1.5/3.0) X104 (2.0/2.0) 留 baseline；新增 X110+ 大 TP 系列 |

## 4. Archetype Space 重设（D3 配额）

总计约 **65 条**（vs Round 3 的 523 条 = 1/8 密度，但每条对齐妖币）：

| 频道 | 30d events | 配额 | archetype 数 | 设计原则 |
|---|---:|---:|---:|---|
| **OI_Price** | 11,536 | **40%** | **16** | 主战场。OI rising + price rising + smallcap + low_liq 是庄家加仓 telegraph；OI unwind 系列；funding-aware 但翻方向（positive funding extreme = 庄家拉爆空头 = long continuation） |
| **Reserved6** | 332 | **30%** | **12** | 信号最纯 (180s 8-15% 极端) 但样本极稀。**每个必须极宽 filter / 单维度** 才能用上 332 events |
| **pricechange** | 66,110 | **25%** | **10** | 海量但需严选 manipulator filter；vol_burst + taker_buy + smallcap 子集 |
| **Cross-channel** | (重叠) | **5%** | **2** | OI + PC 60s 内双触发 等少量探索 |

加上：
- **~20 个 wide-TP exit archetype** (X110+ 系列：TP {5,10,15,25,40,70,120,200} × SL {3,5,7,10} × trail_step {2,4,6} × hold {2h,6h,24h,48h,72h,7d})
- **~5 个 risk/filter archetype**（multi_tp ladder 等组合 exit）

## 5. Variant Grid 重设（具体改动）

**当前** `bwe_loop.py:78-80`:
```python
DEFAULT_TP_GRID = np.linspace(0.2, 6.0, 150, dtype=np.float32)
DEFAULT_SL_GRID = np.linspace(0.2, 6.0, 150, dtype=np.float32)
DEFAULT_HOLD_MINUTES = [5, 15, 30, 60]
```

**Round 4 baseline**（log-spaced 大范围）:
```python
# Round 4 妖币 regime: log-spaced TP (0.5% to 500%), wider SL, multi-day hold
DEFAULT_TP_GRID = np.geomspace(0.5, 500.0, 60, dtype=np.float32)  # 60 个 log-spaced
DEFAULT_SL_GRID = np.array([3.0, 5.0, 7.0, 10.0], dtype=np.float32)
DEFAULT_HOLD_MINUTES = [30, 60, 120, 180, 240, 300]  # 30m, 1h, 2h, 3h, 4h, 5h (event_windows physical max)
```

Variants per archetype: **60 × 4 × 7 = 1680**（vs Round 3 的 90,000，是 1/53）。
Round 3 dense grid 是为了 sweet spot 微调；Round 4 grid 切粗但范围扩 100x，更合理 trade-off。

**注意 trail family 的 SL = trail_step**（同一参数，kernel 复用）—— `eval_trailing_pct` 用 SL_pct 做 trail。所以 Round 4 trail step 自然落在 {3, 5, 7, 10}%，跟 D1 提的 {1.5, 2.5, 4, 6} 相比偏宽。后续看实测决定要不要单独加 trail-only grid。

**待 D1 实证** (Codex 任务包 #0): 历史最大正向 forward return → 决定 TP 上限是 500% 还是要往上加。

## 6. Score Metric 重设

**当前**: `BWE_SCORE_METRIC` env 默认 `kelly_capped` (cap 10)，但 Round 3 实际 keep 决策走的是 `legacy p25`（rescore 才用 v2 metric 重排）。

**Round 4 改动**:
- `bwe_loop_score_v2.py`: 新增 `right_tail_lift_pct` metric（p90 - median，奖励 fat-right-tail 命中庄家拉升的 archetype）
- 新增 `no_blowup_gate`: max_drawdown_pct ≤ 30% 才允许 keep（妖币 regime 下没 0.5% SL 之后这条 gate 是必要的）
- Default metric 切到 `mean_net AND right_tail_lift gate AND no_blowup`
- `configs/metric_contract.json` 更新：废 SL/TP<4 rule，加 right_tail_lift threshold

## 7. paper_shadow 修配对

`scripts/paper_shadow_sim.py` line 213-238 当前 lookup best TP/SL 时 **限制在指定 family 内**（默认 fixed）。R3 keep 的 trail 0.2/0.2 在 paper 跑出来的是 fixed 0.2/4.4 假数据。

**Round 4 改动**：
- 默认 lookup **跨 family** 拿全局 best_score 的 (family, tp, sl)
- 保留 `--exit-family X` 参数允许显式指定
- 输出 markdown 加一行明确写跑的是哪个 family（之前只写了 archetype 名）

## 8. X100 Audit 结论（预诊断，待 Codex 验证）

`bwe_loop_exit_kernels.py:103-165` `eval_breakeven`:
- Line 153 `gross_be = torch.zeros(...)` —— BE 触发后 outcome = 0
- Line 164 `out = (gross - cost_pct).float()` —— 减去 cost
- 当 TP=0.20 / SL=0.20 / cost=0.08 → 大量 BE 触发归零 → net = -0.08

**结论**：X100 不是逻辑 bug，是**参数 regime 错**。Round 4 grid TP {5..500}% 下 BE 触发率会显著下降，X100 应自然好转。

**Codex 任务包 #3** 仍要做：(a) 确认没有 hardcoded floor；(b) 在 Round 4 grid 下 mock 跑一次看 distribution；(c) 给 BE 触发率随 TP 变化的曲线。

## 9. Mac → 5090 → Mac Timeline

```
[Mac 准备 — 现在开始, 1-2 天]                        [5090 — 等回 Windows]                    [Mac — 收尾]

  hygiene #1-13 (见 todo 列表)                          10. nohup python bwe_loop.py            13. analysis + rescore
  ├── #1-3  Memory + overview + parquet 实证             11. 挂 1-3 天 (~20K experiments)         14. paper_shadow 真跑 best
  ├── #4    TEAM_PHILOSOPHY 升级                         12. cron stall-check                    15. LLM team Round 4 debate
  ├── #5-8  Codex 4 任务包并行 (entry / exit / X100)                                              16. morning_brief 生成
  ├── #9-11 metric / paper_shadow / grid 改               (期间用户在 Mac 看 cron 推送)             17. cross-pair recommender
  ├── #12   smoke test 1 archetype × ~1680 variants                                              18. paper_shadow → live 决策
  └── #13   final commit + 启动卡
```

## 10. 风险 & Open Questions

| # | 风险 | 缓解 |
|---|---|---|
| R-D1 | TP 500% 上限可能仍偏低（妖币历史见过 +1000%） | Codex #0 跑历史 max forward return 实证；偏低就上调到 1500% |
| R-grid | 60×4×7=1680 variants 在 5090 上每 archetype 比 R3 的 90K 快 50x，但 archetype 总数没成比例减 → 总 runtime 可能比 R3 短得多（好事） | 监控 GPU 利用率，若 <60% 加密 grid |
| R-trail-step | trail family 的 SL = trail_step 同参数，{3,5,7,10}% 可能偏宽（D1 提议 1.5-6%）| Smoke test 后看是否要 split trail-only grid |
| R-X100 | X100 audit 若发现真 bug 而非 regime 问题，需要修 kernel | Codex #3 任务包优先级最高 |
| R-no_blowup gate | mdd ≤ 30% 阈值在妖币高波动下可能过严 | 待 smoke test 后调阈值 |
| R-hold-7d | 7 天 hold horizon 在 1m kline 是 10080 个 bar，GPU memory 增加 | 已计算到 grid size 1/53 抵消；若 OOM fallback 到 3d |
| R-rejection | 全部 archetype 都跑不出 keep（妖币假设错） | smoke test 1 archetype 后 abort，先做 manual ground truth check |

## 11. Mac Hygiene 任务清单（参 TodoWrite）

详细 13 项见 todo 列表。完成后产物清单：

```
T9:/40_EXPERIMENTS/round4/
├── 00_planning/
│   ├── 00_overview.md           ← 本文档
│   ├── 01_round4_launch_card.md ← 5090 启动卡（最终交付）
│   └── 02_max_forward_return.md ← Codex #0 输出
├── 01_archetypes/
│   ├── round4_entries.jsonl     ← Codex #1 输出 (~40 条)
│   ├── round4_exits.jsonl       ← Codex #2 输出 (~20 条)
│   └── round4_risk_filter.jsonl ← 我手写 (~5 条)
├── 02_grids/
│   └── round4_variant_grid.py   ← 我改 bwe_loop.py 的 patch
├── 03_metrics/
│   ├── score_metric_v3.py       ← right_tail_lift + no_blowup
│   └── metric_contract_v3.json
├── 04_codex_tasks/
│   ├── task_0_max_return.md
│   ├── task_1_entries.md
│   ├── task_2_exits.md
│   └── task_3_x100_audit.md
├── 05_audits/
│   └── x100_audit_report.md     ← Codex #3 输出
├── 06_smoke/
│   └── smoke_test_round4.log    ← 1 archetype × ~1680 variants
└── 99_logs/
    └── codex_dispatch_log.csv   ← Codex 调用记账
```

## 12. 5090 启动卡（draft，待 hygiene 完成后填具体）

```
[等本机 hygiene 全部完成后写入 01_round4_launch_card.md]

cd H:\BWE\20_CODE\Autoresearch
git pull  # 拿到 Round 4 的 grid/metric/registry 改动
python -m bwe_autoresearch.bwe_loop_gpu_eval  # smoke test (15s)
python scripts/smoke_test_round4.py            # 1 archetype × variants (~30s)

# 起 Round 4 主 loop
nohup python -m bwe_autoresearch.bwe_loop > round4.log 2>&1 &

# Mac 端通过 cron 推送状态（已配置）
```

---

**最后更新**: 2026-04-27 by Mac 端 hygiene phase
