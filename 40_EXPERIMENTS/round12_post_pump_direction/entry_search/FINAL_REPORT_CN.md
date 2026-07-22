# Round 12 入场 Alpha 搜索报告（中文白话）

- 生成时间：2026-05-27T18:47:17Z
- 本轮结论：DEV 粗筛没有任何方向达到“足够大 + 单调 + 分层一致”的最低门槛，因此按纪律不做细筛、不读 holdout；当前应判为“无稳健 alpha”。
- holdout 封存线：2026-04-22 00:00:00；粗筛/细筛只读 DEV，holdout 只在最终 reveal 子命令读取。
- 成本模型：前向收益统一扣 0.15% 往返成本；`slippage_abort_proxy` 用最近 1m 位移/振幅 > 0.80% 作为实盘弃单风险代理。
- 共试组合：粗筛 912 个 feature×方向×周期；细筛 0 个规则；p 值统一做 BH-FDR。

## 1. 粗筛榜：哪些方向像信号，哪些像噪声

| 轴/方向族 | 测试数 | 粗筛过 | 最好五分位差 | 最好|rho| | 判定 |
|---|---:|---:|---:|---:|---|
| axis5_condition / market_position | 12 | 0 | 0.086% | 0.0644 | 噪声/不稳 |
| axis1_axis2_volatility / true_range_or_parkinson | 40 | 0 | 0.077% | 0.0545 | 噪声/不稳 |
| axis1_numerator / directional_return_or_abs_displacement | 40 | 0 | 0.096% | 0.0529 | 噪声/不稳 |
| other / other | 36 | 0 | 0.076% | 0.0455 | 噪声/不稳 |
| axis2_baseline / other | 20 | 0 | 0.033% | 0.0442 | 噪声/不稳 |
| axis7_cross_section / cross_section_event_universe | 24 | 0 | 0.033% | 0.0442 | 噪声/不稳 |
| axis1_axis2_volatility / realized_volatility | 16 | 0 | 0.042% | 0.0441 | 噪声/不稳 |
| axis5_condition / btc_regime | 12 | 0 | 0.070% | 0.0358 | 噪声/不稳 |
| axis2_baseline / directional_return_or_abs_displacement | 360 | 0 | 0.095% | 0.0344 | 噪声/不稳 |
| other / phase0_existing_other | 12 | 0 | 0.038% | 0.0331 | 噪声/不稳 |
| axis1_axis2_atr / atr_normalized | 20 | 0 | 0.076% | 0.0341 | 噪声/不稳 |
| axis2_baseline / true_range_or_parkinson | 168 | 0 | 0.100% | 0.0305 | 噪声/不稳 |
| axis6_shape / candle_shape | 16 | 0 | 0.100% | 0.0346 | 噪声/不稳 |
| axis1_volume / volume_surge | 24 | 0 | 0.031% | 0.0260 | 噪声/不稳 |
| axis1_oi / oi_jump | 16 | 0 | 0.066% | 0.0216 | 噪声/不稳 |
| axis5_condition / coin_volatility_or_lifecycle | 8 | 0 | 0.113% | 0.0219 | 噪声/不稳 |
| axis2_baseline / realized_volatility | 64 | 0 | 0.095% | 0.0186 | 噪声/不稳 |
| axis2_baseline / phase0_existing_other | 4 | 0 | 0.020% | 0.0160 | 噪声/不稳 |
| axis1_volume / phase0_existing_volume_surge | 4 | 0 | 0.027% | 0.0146 | 噪声/不稳 |
| axis1_morphology / consecutive_green | 4 | 0 | 0.012% | 0.0142 | 噪声/不稳 |
| axis1_taker / taker_imbalance | 8 | 0 | 0.020% | 0.0100 | 噪声/不稳 |

粗筛前 20 个幸存者：
- 无。

最接近但仍不过线的方向（用于解释，不作为候选）：
- `dist_to_day_low_pct` → long 120m：五分位差=+0.052%，Spearman=-0.0644，单调步数=4/4，分层同向=2/3。
- `dist_to_day_low_pct` → short 120m：五分位差=+0.052%，Spearman=+0.0644，单调步数=4/4，分层同向=2/3。
- `dist_to_day_low_pct` → long 60m：五分位差=+0.061%，Spearman=-0.0628，单调步数=4/4，分层同向=3/3。
- `dist_to_day_low_pct` → short 60m：五分位差=+0.061%，Spearman=+0.0628，单调步数=4/4，分层同向=3/3。
- `parkinson_3m_pct` → long 60m：五分位差=+0.049%，Spearman=-0.0545，单调步数=2/4，分层同向=2/3。
- `parkinson_3m_pct` → short 60m：五分位差=+0.049%，Spearman=+0.0545，单调步数=2/4，分层同向=2/3。
- `ret_10m_pct` → long 60m：五分位差=+0.039%，Spearman=-0.0529，单调步数=3/4，分层同向=2/3。
- `ret_10m_pct` → short 60m：五分位差=+0.039%，Spearman=+0.0529，单调步数=3/4，分层同向=2/3。
- `parkinson_1m_pct` → long 60m：五分位差=+0.063%，Spearman=-0.0536，单调步数=2/4，分层同向=3/3。
- `parkinson_1m_pct` → short 60m：五分位差=+0.063%，Spearman=+0.0536，单调步数=2/4，分层同向=3/3。
- `range_1m_pct` → long 60m：五分位差=+0.062%，Spearman=-0.0536，单调步数=2/4，分层同向=3/3。
- `range_1m_pct` → short 60m：五分位差=+0.062%，Spearman=+0.0536，单调步数=2/4，分层同向=3/3。

## 2. 幸存者细筛

粗筛 0 幸存者，所以细筛被纪律性跳过；没有为了找赢家而放宽门槛。

## 3. Holdout 一次确认

holdout 没有读取。原因不是漏跑，而是 DEV 粗筛 0 幸存者；没有候选就不能 reveal 封存集。

## 4. 反过拟合与前视/成交性顾虑

- 现有 `pump_events.csv` 的时间戳是 5m `open_time_ms`，但事件特征用了该 5m bar 的 close；本脚本把可交易时间后移到该 5m bar 收盘后，并重算 `fwd_ret_*` 标签，避免把 bar 内信息当作入场前信息。
- 若任何规则出现胜率 >65% 或单笔均值 >2%，默认先当作泄漏/过拟合，需要回查逐笔路径。当前脚本也把这类高胜率候选排除在 fine/holdout pass 之外。
- 截面特征当前是“同一时刻触发事件集合内”的截面排名，不是全市场 640 币完整截面；报告中不能把它吹成完整市场强弱榜。
- OI/资金费/多空比表的历史覆盖未必覆盖整个 DEV，缺失会自然降样本；若 OI 方向表现好，需要单独看覆盖率，不能只看均值。
- 实盘急拉成交风险用 `slippage_abort_proxy` 近似；这不是盘口级滑点，任何依赖最快 1m 冲刺的规则都要打折。

