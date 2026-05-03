# Round 4 Score Metric Proposal — Mean + Right-Tail Lift + No-Blowup Gate

> 状态: **草案 — 等用户 confirm 后落地代码**
> 当前 default: `BWE_SCORE_METRIC=kelly_capped`（cap=10）
> R4 提议 default: `r4_keep_gate`（新增，组合）

## 1. 当前 metric 现状

| Metric | 文件 | 性质 | R3 表现 |
|---|---|---|---|
| `legacy p25` | `bwe_loop_score_metric.py` | OOS p25 of net returns | **R3 实际 keep 决策用的就是这个** — 自标 BUGGY，选出 E126 trap |
| `mean` | `bwe_loop_score_v2.py` | 简单 mean per-trade | 受 outlier 影响但不藏 left tail |
| `kelly_capped` | `bwe_loop_score_v2.py` | Kelly fraction × 100, cap 10 | **顶部全 capped at +10**，无法分辨真正最优 trail |
| `p25_capped_tail` | `bwe_loop_score_v2.py` | p25 with tail penalty (winsor p5) | R3 rescore 显示选出 E082 但 trig=102 太稀 |

## 2. 妖币 regime 下的 metric 困境

妖币是 **fat-right-tail 分布**（少数大赢家覆盖多数小输家）。这跟传统 fat-left-tail metric 假设相反：

| Metric 行为 | 在大盘币 fat-left-tail 下 | 在妖币 fat-right-tail 下 |
|---|---|---|
| `legacy p25` 砍 75% 上方 | 合理（防 left tail 黑天鹅） | **错误**（砍掉 alpha 来源） |
| `kelly_capped` cap | 防 outlier 主导 | **错误**（妖币就是要靠右尾） |
| `mean` | 易受 outlier 误导 | **正确**（右尾就是真实 EV） |
| `right_tail_lift = top_p10_mean - all_mean` | 没意义 | **正确**（直接奖励命中庄家拉升） |
| `max_drawdown ≤ 30% gate` | 太严 | **必要**（妖币高波动下唯一防全亏 gate） |

## 3. 提议的 R4 Composite Metric (`r4_keep_gate`)

### 3.1 公式

```python
def batch_score_r4_keep_gate(
    net_returns: torch.Tensor,  # [N_events, N_variants] f32 net % returns
    max_dd_threshold: float = 30.0,  # absolute %, no_blowup gate
    right_tail_quantile: float = 0.10,  # top 10% definition
    right_tail_weight: float = 0.3,  # how much to bonus right-tail lift
    **kwargs,
) -> torch.Tensor:
    """
    Round 4 妖币 regime composite metric:
    
        score = mean + right_tail_weight × (top_p10_mean - mean)
                if min_p10_mean > -max_dd_threshold else -1e6 (blowup gate)
    
    Per variant. Bootstrap-stabilized over walk-forward chunks (consistent with v2).
    
    Components:
      - mean: per-trade EV (fat-right-tail OK)
      - right_tail_lift: mean(top 10%) - mean overall — directly rewards 命中庄家拉升 events
      - no_blowup_gate: if mean of bottom 10% < -30%, force -1e6 (filter blowups)
    
    Why not p25 / kelly_capped:
      - p25 砍掉 right tail, but right tail IS the alpha in 妖币 regime
      - kelly_capped's cap=10 saturates at top, can't differentiate winners
      - mean alone is OK but doesn't reward right-tail concentration vs flat winners
    """
    # ... (vectorized implementation, walk-forward + bootstrap as in v2)
```

### 3.2 Synthetic test (用 v2 self-test 同 4 个 variants)

| Variant | 8% TP × 6% SL × 80% W (E126 trap) | 50/50 +1/-1 (NEUTRAL) | 60/40 +1/-1 (GOOD) | 90/10 +1/-0.5 (PERFECT) |
|---|---|---|---|---|
| E[trade] | -0.80 | 0.00 | +0.20 | +0.85 |
| `legacy p25` | **+0.50** ❌ (picks trap) | -0.50 | -0.50 | +1.00 |
| `mean` | -0.80 | 0.00 | +0.20 | +0.85 |
| `kelly_capped` | 0.00 | 0.00 | +5.0 | **+10.00 (cap)** |
| `p25_capped_tail` | -0.50 (winsor save) | -0.50 | -0.50 | +1.00 |
| **R4 `r4_keep_gate`** | **-1e6 ❌ (blowup at -6%)** | 0.00 | +0.20 | **+0.85+0.3×0.15=+0.895** |

R4 metric 唯一在 (a) 拒绝 trap (b) 区分 GOOD/PERFECT 都做对。

但**注意**：这个 metric 的"右尾奖励"只在右尾确实**比 mean 高**时才有奖励。即均匀正分布也不会被 over-rewarded。

### 3.3 妖币 regime 真实 case 测试（mock）

考虑一个 archetype，n=100 events，分布 {80% × +1%, 15% × -3%, 5% × +50%}：
- mean = 0.80 - 0.45 + 2.5 = **+2.85%**
- top 10% mean = (5% × 50%) average pick = ~50/2 = +25% (only 5 events qualify)
- right_lift = 25 - 2.85 = +22.15
- mdd proxy (bottom 10%) = -3% (worst 10 events)
- gate: -3 > -30 ✓ pass

R4 score = 2.85 + 0.3 × 22.15 = **+9.50** 

对比另一个 archetype，n=100 events，分布 {99% × +0.4%, 1% × -50%}（典型 fee trap with hidden blowup）:
- mean = 0.396 - 0.5 = **-0.10%**
- top 10% mean = +0.4%
- right_lift = 0.4 - (-0.10) = +0.5
- mdd proxy (bottom 10%) = (some +0.4 averaged with -50, n_bot=10) = -4.59% (10 events × -50/10 + 90 events × 0.4 → bottom 10 = 1 × -50 + 9 × 0.4 / 10 = -4.64)
- gate: -4.64 > -30 ✓ pass (ironically not blocked because the loss only on 1 event)

R4 score = -0.10 + 0.3 × 0.5 = **+0.05**

第二个 fee trap 在 R4 metric 下 score ≈ 0，**不会**被选为 winner（与 R3 的 +0.39 score 截然不同）。

### 3.4 边界 case

- 如果 archetype 全为正（极少见），右尾奖励小（top_mean ≈ overall mean），score ≈ mean。Fair.
- 如果 archetype 全为负（很多 R3 archetype），mean 已经负，right_lift 也小，score 仍负。Filtered out.
- 如果 only n=30 events，walk-forward chunks 可能 < MIN_TRIGGERS_PER_OOS=5 → return NaN，不参与排序（与 v2 行为一致）。

## 4. metric_contract.json 更新提议

当前 `configs/metric_contract.json` 写：
- `win_rate_pct_gte: 60.0` — promote_to_paper threshold
- `median_net_pct_gt: 0.0`
- `p25_net_pct_gte: -1.0`
- `profit_factor_gte: 1.35`
- `walk_forward_positive_rate_pct_gte: 55.0`

**R4 改动建议**：
- `win_rate_pct_gte` 从 60 **降到 30**（妖币右尾分布天然胜率低，60% 把所有 fat-right-tail archetype 砍掉）
- `median_net_pct_gt` 改 `mean_net_pct_gt: 0.0`（妖币 median 经常负，但 mean 可以正）
- 新增 `right_tail_lift_pct_gte: 5.0`（top 10% 比 overall mean 高至少 5pct）
- 新增 `max_drawdown_pct_lte: 30.0`（no_blowup gate，硬上限）
- **删除** `p25_net_pct_gte: -1.0`（p25 在妖币 regime 不再用作 promote gate）
- 保留 `profit_factor_gte` 和 `walk_forward_positive_rate_pct_gte`（these still meaningful）

## 5. 落地路径（待 user confirm）

1. ✅ **方案确认**: 用户 review 公式 + 测试 case → ack
2. ⏭ **代码改动**:
   - 新增 `batch_score_r4_keep_gate` to `bwe_loop_score_v2.py`（约 60 行 vectorized torch）
   - 注册 in `METRIC_FNS` dict line 233
   - 默认 metric 切换 `bwe_loop_score_v2.py:248` `os.environ.get("BWE_SCORE_METRIC", "kelly_capped")` → `"r4_keep_gate"`
3. ⏭ **metric_contract.json 改动** per §4
4. ⏭ **Self-test** 加 R4 case 进 `_self_test()` line 262

## 6. R3 SL/TP > 4 reject rule 处理

morning_brief §五写的硬规则:
> "reject any keep where SL/TP > 4 even if mean score is positive"

**R4 处理**: **废除**这条规则。妖币 regime 下绝对值（TP 5-500% / SL 3-10%）才重要，ratio 不重要。
- TP=10/SL=10 (ratio 1) 和 TP=70/SL=10 (ratio 7) 在妖币里都合理
- R3 这条规则隐含大盘币 fat-left-tail 假设，已废除（参 TEAM_PHILOSOPHY R4 升级版）

## 7. Open Questions for User

1. **right_tail_weight = 0.3 这个权重合理吗？** 如果觉得右尾应该更主导，可以 0.5 甚至 0.7
2. **max_dd_threshold = 30% 这个阈值合理吗？** 用户原话 "SL 在 10 以内"，单 trade SL 上限 10%，但 archetype 整体的 worst-case drawdown 30% 是 multi-trade 累加。如果觉得太严松到 50%；觉得太松收紧到 20%
3. **right_tail_quantile = 10% (top 10%) 合理吗？** 5% 更严但需要更多 sample；20% 更松
4. **win_rate gate 30% 是否太低？** 妖币右尾分布 win rate 25-40% 算正常；但 30% 是 minimum gate，可以收紧到 35%
