# Round 8 — 3-Strategy Filter Calibration Protocol

> 实验协议 (autoresearch-plan 产出). 规划相,**未执行**. 等用户批准后跑.
> Created 2026-05-21. Data snapshot md5: `9c11c9884f57a790` (klines_extended_196d.npz)

## 0. 背景与动机

- 当前 3 个 live 策略 (B_US_PM / D_ASIA / C_PULLBACK) 来自 round7 strict-audit,但参数是在**全 196d 上搜索 + 6-window 一致性选择**的 → 仍是 in-sample selection,**没有真正 holdout**.
- 实盘 5 天:B 触发 2 次(2 胜),**D_ASIA + C_PULLBACK 各 0 次**.
- 诊断 (2026-05-21,L16-appendix):D_ASIA 卡在单根 K 线形态 (upper_wick 3% / body_neg 5% 通过率);C_PULLBACK 卡在 pullback ≤ -4% (4.4% 通过率,near-miss 都在 -0.6% 远离 -4%).
- 同日修复 forming-bar bug → 实盘评估首次与收盘-bar 回测对齐 → **校准用收盘 bar features 天然对齐修复后实盘**.

## 1. 目标与基线

### 目标函数 (Objective)
**主目标**:在 DEV 集上,对每个策略,在满足"够频繁 + 鲁棒"硬门槛后,最大化**风险调整收益 (Calmar = port_sum / maxDD)**.

为什么 Calmar 不是纯 port_sum:纯收益易被"少数大赢"主导 → 过拟合.Calmar 惩罚回撤,偏好稳定 (符合项目 Rule:stability over return).

辅助报告:Sharpe / Sortino / port_wr / port_n / unique_days / max 连亏.

### 硬门槛 (DEV 上必须同时满足,否则候选淘汰)
| 门槛 | 值 | 理由 |
|---|---|---|
| port_n (DEV ~38d) | ≥ 8 | 够频繁 (≈ 0.2 单/天,否则统计无意义) |
| port_sum_pct | > 0 | 正期望 |
| port_wr_pct | ≥ 45% | 短策略可接受偏低 wr (靠盈亏比) |
| pos_windows | ≥ 4/6 | 时间一致性 (DEV 内 6 子窗) |
| traded_syms | ≥ 12 | 不靠单币 (scaled for 38d) |
| top_share_pct | ≤ 30% | 不靠单币集中 |
| unique_days | ≥ 10 | 不靠单日爆发 |

### 基线 (Baseline) — 先测,没基线不算完成
当前 live 3 策略参数,在 TRAIN/DEV/HOLDOUT **三段分别**评估:

| 策略 | 当前 entry 参数 | exit |
|---|---|---|
| B_US_PM_PULLBACK | hours[15-19], ret60_atr≥4.0, pullback≤-0.02, vol_zs≥1.5, rsi≥60 | tp5.0/sl2.5 |
| D_ASIA_LATE_CONFIRM | hours[0-4], ret60_atr≥6.0, rsi≥70, taker≤0.85, upper_wick≥0.003, body_neg≤-0.003 | tp6.0/sl2.5 |
| C_PULLBACK_STRICT | all hours, ret60_atr≥3.0, pullback≤-0.04, ret5_atr≤-0.3, vol_zs≥1.5, rsi≥60 | tp5.0/sl2.5 |

baseline 数字 (三段 port_n / port_sum / port_wr / Calmar) 是**校准后必须打败的对象**.若校准结果 holdout 不优于 baseline holdout → 不部署,保持现状.

### 简洁度 (Complexity) tie-breaker
记录每个候选的"激活 filter 数量".同等 DEV Calmar → **选 filter 更少 / 阈值更接近整数的** (Karpathy 简洁性 → 样本外更稳).

## 2. 搜索空间

引擎复用 `round7_strict_live_search/loop_search_framework.py` 的 `evaluate_strategy` (已含滑点 0.05%×2 + funding 0.01%/8h + 组合约束 + 6-window).只改 entry 阈值 grid.exit 第一轮固定 (tp/sl 保持当前),避免 entry×exit 联合爆炸 + exit 已被 round7 充分搜过.

### B_US_PM_PULLBACK (B 已盈利,目标=确认当前最优 or 微调)
- ret60_atr_min: {3.0, 3.5, 4.0, 4.5, 5.0}
- pullback_max: {-0.015, -0.02, -0.025, -0.03}
- vol_zs_min: {1.0, 1.25, 1.5, 2.0}
- rsi_min: {55, 60, 65}
- hours: {[15-19], [15-22]}
- → 5×4×4×3×2 = **480 combos**

### D_ASIA_LATE_CONFIRM (问题儿童,重点测"K 线形态 filter 是否过严")
- ret60_atr_min: {4.0, 5.0, 6.0}
- rsi_min: {65, 70}
- taker_max: {0.85, 0.95}
- upper_wick_min: {0.0, 0.0015, 0.003}  ← **含 0 = 测移除该 filter**
- body_neg_max: {0.0, -0.0015, -0.003}  ← **含 0 = 测移除该 filter**
- hours: {[0-4], [0-6]}
- → 3×2×2×3×3×2 = **216 combos**

### C_PULLBACK_STRICT (测 -4% pullback 墙是否该松)
- pullback_max: {-0.02, -0.025, -0.03, -0.035, -0.04}  ← 含 -2% 测松绑
- ret60_atr_min: {2.5, 3.0, 3.5}
- vol_zs_min: {1.0, 1.5}
- rsi_min: {55, 60}
- ret5_atr_max: {-0.3, 0.0}  ← 含 0 = 测移除
- → 5×3×2×2×2 = **120 combos**

**总搜索量**: 480 + 216 + 120 = **816 combos** × 3 段评估.

### 搜索策略
网格穷举 (grid).combos 数有限 (816),无需 optuna/贝叶斯.确定性,无随机种子需求.

## 3. 数据切分 (反过拟合关键)

196 天 (282,357 分钟) **按时间顺序**切 3 段,**holdout = 最近 (最接近 live regime)**:

| 段 | 日期范围 | 天数 | 占比 | 用途 |
|---|---|---|---|---|
| **TRAIN** | 2025-11-01 → 2026-02-26 | ~118d | 60% | 跑全 816 grid,筛过硬门槛的候选 |
| **DEV** | 2026-02-27 → 2026-04-05 | ~38d | 20% | 在 TRAIN 幸存者里,按 DEV Calmar 选最优 |
| **HOLDOUT** | 2026-04-06 → 2026-05-16 | ~40d | 20% | **只在最终报告看一次**,绝不参与选择 |

- 每段内部仍跑 6 子窗一致性 (pos_windows).
- **封存铁律**:HOLDOUT 的任何数字在"选定参数"之前绝不读取/绝不影响决策.脚本里 holdout 评估单独成函数,最后一次性调用.

## 4. 停止条件 (任一触发即停)
- 全 816 grid 跑完 (主要终止条件,grid 有限).
- 单策略找到 ≥1 个"三段全正 + DEV 打败 baseline"候选即可宣告成功 (但仍跑完 grid 记录全部).
- 运行超 30 min → 报告进度,人工决定是否继续 (向量化后预计 < 10 min).

## 5. 反过拟合护栏 (默认开,不可静默关)

1. **TRAIN 结果不直接作为成绩** — 仅用于初筛.
2. **三段全正硬约束**:候选必须 TRAIN > 0 AND DEV > 0 AND HOLDOUT > 0 才算"鲁棒".只在 1-2 段正 → 标记 `overfit_suspect`.
3. **多重比较修正**:816 combos ≫ 30 → 主动应用 **BH-FDR (α=0.10)** 于 DEV port_sum 的显著性,或至少要求 DEV Calmar 比 baseline 高 ≥ 30% margin (防"恰好胜出").报告里明确标注做了哪个.
4. **regime 分箱**:用 `btc_regime_196d.npz` 把 holdout trades 按 BTC 牛/熊/震荡分箱,确认候选不是"只在单一 regime 赚" (单 regime 特例 → 标记 `regime_fragile`).
5. **异常自检**:任何候选 holdout Calmar > 5 或 wr > 90% → 触发"数据泄漏 / 前视偏差"自检 (检查 feature 是否用了未来 bar).
6. **全部实验记录**:816 combos 全写 jsonl,失败/负收益的也留,不丢弃.

## 6. 量化策略额外项

- **walk-forward**:本协议用 train→dev→holdout 时间顺序切分 = walk-forward 的一种 (anchored).每段内 6 子窗 = 二级一致性检查.
- **风险指标全集**:Sharpe + Sortino + Calmar + maxDD + 最大连亏次数 — 全部记录每候选每段.
- **交易成本**:复用引擎现有 (entry/exit 滑点各 0.05% + funding 0.01%/8h).
- **regime 分箱**:见护栏 #4.

## 7. 工程契约

- **结果存储**: `round8_calibration/experiments.jsonl` (每行 1 combo)
- **每行字段**:
  ```json
  {"timestamp","strategy","config","complexity",
   "train":{"port_n","port_sum","port_wr","calmar","sharpe","sortino","maxdd","pos_windows","traded_syms","unique_days"},
   "dev":{...同上...},
   "holdout":{...同上...},
   "passed_dev_gates":bool,"three_split_positive":bool,
   "anomaly_flags":[],"regime_breakdown":{}}
  ```
- **可复现**:data md5 `9c11c9884f57a790`;grid 确定性无随机;numpy/pandas 版本记录.
- **最终产物**:`ROUND8_CALIBRATION_REPORT.md` — 每策略 baseline vs best-candidate 三段对比 + 部署建议 (调 / 不调 / 停用).

## 8. 预期 3 种结局 (诚实预设)

每个策略校准后只会是这 3 种之一:
1. **当前参数已近最优** → DEV 找不到显著更好的 → 保持现状 (B 很可能这样).
2. **阈值设歪了** → 找到"三段全正 + 打败 baseline + 简洁"的新参数 → 建议调整 (D_ASIA 的 candle filter 可能这样).
3. **当前 regime 无 edge** → 怎么调 holdout 都不正 → 建议**停用**该策略,而不是硬塞参数 (C_PULLBACK 可能这样).

**不会做的事**:为了"让它出单"而牺牲 holdout 表现去调参.holdout 不正 = 不部署.

---

## 待批准

协议完整 (目标/基线/搜索空间/三段切分/停止条件/6 道护栏/工程契约/regime 分箱全含).
请回复:
- **批准 / go** → 我开始执行 (先跑 baseline 三段,再跑 816 grid,最后 holdout 揭晓 + 报告)
- **修订** → 指出要改的部分 (如 grid 范围/切分比例/目标函数)
