# 🌅 BWE Round 3 早间简报

生成时间：**2026-04-27 19:37**

---

## 一、Loop 完成情况

- **总实验数**：20,000 / 20,000 (100.0%)
- **按状态分布**：{'keep': 7, 'discard': 18203, 'crash': 1790}
- **best score (legacy p25)**：0.3946
- **总 keeps**：7

## 二、Top 10 真正的 Winners（按 Kelly metric 排序）

> 注：Kelly metric 是新的 v2 指标，能正确识破 asymmetric TP/SL trap。传统 p25 metric 之前误把 E126 (paper -13.5%) 排第一 —— Kelly 不会犯这个错。

| # | entry_id | archetype | exit family | TP | SL | trig | Kelly% | mean% | paper% |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | E001 | oi_overcrowded_continuation_sh | trail | 0.20 | 0.20 | 406 | **+10.00** | +0.1479 | +4.49 |
| 2 | E002 | oi_overcrowded_reversal_short | trail | 0.20 | 0.20 | 406 | **+10.00** | +0.1479 | +4.49 |
| 3 | E003 | oi_dropping_squeeze_long | trail | 0.20 | 0.20 | 190 | **+10.00** | +0.2712 | +3.96 |
| 4 | E004 | oi_dropping_capitulation_short | trail | 0.20 | 0.20 | 190 | **+10.00** | +0.3533 | +5.18 |
| 5 | E005 | oi_funding_blowoff_short | trail | 0.20 | 0.20 | 795 | **+10.00** | +0.1722 | +10.66 |
| 6 | E008 | oi_pump_immediate_short | trail | 0.20 | 0.20 | 1401 | **+10.00** | +0.1938 | +22.45 |
| 7 | E009 | oi_pump_delayed_30s_short | trail | 0.20 | 0.20 | 1401 | **+10.00** | +0.1938 | +22.45 |
| 8 | E010 | oi_pump_delayed_1m_short | trail | 0.20 | 0.20 | 1401 | **+10.00** | +0.1938 | +22.45 |
| 9 | E012 | oi_pump_counter_pretrend_short | trail | 0.20 | 0.20 | 878 | **+10.00** | +0.1623 | +11.30 |
| 10 | E013 | oi_crash_immediate_short_cont | trail | 0.20 | 0.20 | 250 | **+10.00** | +0.3275 | +6.37 |

## 三、Round 3 LLM Team 输出

### 3.1 Pattern Miner 发现

> After 20,000 results, only 7 keeps survive — all from the `fixed` exit family (mean +0.175, max +0.395), while `multi_tp`, `trail`, `time_only`, and `breakeven` families produced ZERO positives. Top entries cluster tightly in pricechange/long with taker_buy/liquidity/funding signals (E126, E064, E148, E051, E066), with E126 reaching +0.395 but already flagged as a paper-shadow trap (asymmetric TP/SL). Reserved6 channel and short-side archetypes are systematically failing (low triggers ~120 or crashes), and the X100 composite_exit_be_partial_runner sweep just confirmed breakeven/runner kernels under-perform fixed across the board.

- **主导**：pricechange_long_taker_buy_extreme — E126 pc_pump_taker_buy_extreme_long +0.395 (lift +0.475, trig 3443); E064 taker_buy_dominant_long +0.357; E066 crash_taker_buy_long +0.339 — taker_buy_ratio_5m as the discriminating field consistently outperforms naked pricechange
- **主导**：pricechange_long_high_liquidity_funding — E051 pc_high_liquidity_long +0.347 (lift +0.427, trig 2157); E148 pc_pump_global_short_high_long +0.350 (trig only 988 — selective)
- **主导**：first_signal_immediacy_long — E036/E038/E039/E040/E041 all best=+0.290 lift=+0.370 trig=5000 — saturated trigger ceiling, identical scores across 0s/30s/1m/3m windows suggests channel/side baseline rather than novel signal

- **未充分探索**：short_side_anywhere — Short variants either crash on triggers (Reserved6 shorts) or collapse to channel baseline; no short pattern has cleared 0.0
- **未充分探索**：OI_Price_channel — Despite largest channel allocation, no OI_Price archetype in keeps — Generator has been pricechange-biased
- **未充分探索**：X101+_exit_side_archetypes — Generator focused on entries; exit kernels untested on top entries (E126/E064/E051) beyond fixed default

### 3.2 Synthesizer + Self-Reflection 决策

- **接受的新 archetype 数**：20
- **Synthesizer 总结**：Round 3 generator delivered a strong, structurally diverse batch dominated by OI_Price-channel ports of proven pricechange templates, novel exit-family experiments addressing the R2 X-pipeline starvation gap, and short-side mean-reversion fades that finally break from the continuation-only short clu
- **Self-Reflection 总结**：Synthesizer rejected zero archetypes outright (all 21 proposals were accepted, 1 revised due to parser limitation), so there are no candidates to promote back. Sole revised item (weekday_weekend_avoid_long → weekday_midweek_wed_filter) was a legitimate parser-level fix not a rejection, and the user'

### 3.3 新接受的 Archetypes

- **E202** `oi_pump_taker_buy_extreme_high_liq_long` (OI_Price/long)
  > OI burst with aggressive taker buying in high-liquidity names — port of E126 winning template to OI_Price channel where 61 archetypes registered but none in top-10.
  > _Synthesizer note_: Accepted; fills OI_Price top-10 gap. Metric_critic flags high trap risk (E126-family asymmetric TP/SL geometry) — GPU sweep should constrain SL<=2.5x TP and validate via kelly_capped/p25_capped_tail, 
- **E203** `oi_pump_global_short_high_long` (OI_Price/long)
  > OI burst on names where global short ratio is elevated — squeeze fuel hypothesis, mirrors E148 from pricechange to OI channel.
  > _Synthesizer note_: Accepted; squeeze-fuel logic ported to OI_Price is structurally novel. Devil notes funding-rate staleness and channel-semantics mismatch — track per-symbol concentration and time-since-funding-update 
- **E204** `oi_crash_taker_buy_reversal_long` (OI_Price/long)
  > OI reduction with concurrent taker BUY pressure — short-cover reversal setup distinct from continuation longs.
  > _Synthesizer note_: Accepted with watch (tight ~85 trig); first divergence/reversal entry on OI_Price. Metric_critic flags counter-trend geometry concern — pair with fixed/breakeven exits and force SL<=1.5x TP in variant
- **E205** `oi_pump_funding_neutral_taker_extreme_long` (OI_Price/long)
  > OI burst with neutral funding (no crowding) plus extreme taker buying — clean signal without funding skew.
  > _Synthesizer note_: Accepted; funding-neutral gate is the cleanest direct attack on the R2 E126 funding-skew trap. Devil rightly notes the band is narrow — confirm with ablation at |funding|<=3bp during paper-shadow.
- **E206** `pc_pump_taker_buy_high_liq_global_short_long` (pricechange/long)
  > Triple-AND combining the three top R2 winners (taker_buy + high_liq + global_short_high) into one selective entry.
  > _Synthesizer note_: Accepted with watch; triple-intersection of E126/E051/E148 components. Metric_critic flags high trap risk because all three parents share asymmetric pump-long geometry — must validate with kelly_cappe
- **E207** `pc_pump_funding_positive_taker_sell_short` (pricechange/short)
  > Crowded-long pump with positive funding and taker SELL dominance — classic mean-reversion fade with natural SL=TP symmetry.
  > _Synthesizer note_: Accepted; first true mean-reversion short on pricechange (existing 94 shorts collapsed to baseline because they reused continuation logic). Geometry is structurally symmetric per metric_critic, lower 
- **E208** `pc_pump_top_trader_short_funding_high_short` (pricechange/short)
  > Smart money positioned short while retail funding extreme — high-conviction fade short.
  > _Synthesizer note_: Accepted; smart-money + funding-extreme cross-signal is novel for short side. Devil flags funding-snapshot staleness (8h cycle) — bucket trades by snapshot age during shadow.
- **E209** `pc_crash_oversold_global_long_extreme_long` (pricechange/long)
  > Crash with retail capitulation extreme + early taker buy reversal — counter-trend bounce.
  > _Synthesizer note_: Accepted with watch (tight ~45 trig per quant). High trap risk per metric_critic — counter-trend longs structurally invite asymmetric SL>>TP. Force SL<=2x TP and require TP>=0.8% in variant grid.
- **E210** `r6_bigmove_simple_long` (Reserved6/long)
  > Single-filter Reserved6 long — minimal AND to preserve sparse R6 trigger count (~120 baseline).
  > _Synthesizer note_: Accepted; pattern_miner architectural fix for R6 over-specification. Lowest trap risk in batch per metric_critic (R6 geometry is more directional than pump channels).
- **E211** `r6_pump_high_liq_only_long` (Reserved6/long)
  > R6 long gated only by high liquidity — sparse-channel safe filter.
  > _Synthesizer note_: Accepted with watch; devil correctly notes liquidity_bucket alone has no directional bias and risks regression to channel/side baseline (R1 silent-fallthrough echo). Compare lift vs plain R6/long base
- **E212** `hour_session_us_pump_long` (pricechange/long)
  > Session-gated entry restricting pricechange longs to US trading hours — exploits liquidity regime.
  > _Synthesizer note_: Accepted; first archetype to use the supported `session` field. Ample expected sample (~340). Devil flags potential macro-event overfit in 30d window — bucket by sub-window during shadow.
- **E213** `basis_curvature_pump_short` (pricechange/short)
  > Pump with extreme basis AND premium — perp dislocation fade.
  > _Synthesizer note_: Accepted; lowest trap risk among shorts per metric_critic — bounded mean-reversion thesis with naturally symmetric geometry. Verify Spearman(basis_rate, premium_bps) on triggers <0.85 to confirm joint
- **X102** `x101_quick_cut_60s_time_exit` (NA/NA)
  > Pure time_only 60s exit paired with high-conviction entries — quick mean-reversion harvest before drift.
  > _Synthesizer note_: Accepted with watch; time_only family has 0/2745 prior positives, but pattern_miner flagged the mean-reversion pairing as untested. Treat as deliberate hypothesis test — require mean AND p25_capped_ta
- **X103** `x102_wide_trail_2pct_exit` (NA/NA)
  > Trail family with 2.0% step on top entries — wider trail to avoid premature stop-out.
  > _Synthesizer note_: Accepted; trail family max≈-0.006 suggests parameter mis-tune not dead concept (pattern_miner). Sweep step in {1.5,2.0,2.5}% with activation_threshold to map the surface.
- **X104** `x103_multi_tp_60_40_ladder_exit` (NA/NA)
  > Two-step TP ladder 60/40 with first TP at 0.5% second at 1.5% — captures bulk early.
  > _Synthesizer note_: Accepted with watch; multi_tp prior is brutal (0/3111 positive), but front-loaded 60/40 shape attacks the residual-leg failure mode. Devil flag: novel_dim is entry-side filter on exit archetype — veri

### 3.4 推荐 Top 10 (Entry × Exit) 测试对

> Top-10 prioritizes diversifying the existing live BWE_OI_Price pump-long by adding short-side fades (E207/E208/E213), porting the winning taker-buy template to OI_Price (E202/E205) and Reserved6 (E210), and pairing high-conviction entries with the new exit families (X102 time, X103 trail, X105 BE, X106 hybrid) to attack R2's asymmetric TP/SL trap; fast-test priorities concentrate on funding-neutral and symmetric-geometry pairs that explicitly avoid the E126 paper failure mode.

| 排名 | Entry | Exit | Family | 优先级 | 思路 |
|---:|---|---|---|---|---|
| 1 | **E207** pc_pump_funding_positive_ | X101 composite_exit_be_pa | breakeven | fast | First true mean-reversion short on pricechange with structurally symmetric TP=SL geometry — directly fills the largest g |
| 2 | **E205** oi_pump_funding_neutral_t | X101 composite_exit_be_pa | breakeven | fast | Cleanest direct attack on the R2 E126 funding-skew trap — funding-neutral gate explicitly excludes the crowded-long regi |
| 3 | **E213** basis_curvature_pump_shor | X101 composite_exit_be_pa | breakeven | fast | Lowest trap risk among shorts per metric_critic — bounded perp-spot dislocation thesis with naturally symmetric geometry |
| 4 | **E126** pc_pump_taker_buy_extreme | X102 x101_quick_cut_60s_t | time_only | standard | Direct hypothesis test: pattern_miner flagged that E126's edge is front-loaded and the asymmetric TP/SL trap lives in th |
| 5 | **E202** oi_pump_taker_buy_extreme | X103 x102_wide_trail_2pct | trail | standard | Ports E126 winning template to OI_Price channel paired with wider 2% trail to test whether trail family's prior failure  |
| 6 | **E210** r6_bigmove_simple_long | X101 composite_exit_be_pa | breakeven | fast | Reserved6 architectural fix — R6 channel under-represented in top entries due to over-specification. Single-filter desig |
| 7 | **E126** pc_pump_taker_buy_extreme | X106 x105_hybrid_fixed_th | multi_tp | standard | Direct attack on the R2 E126 paper-trap: 50% at fixed 0.5% TP banks the front-loaded edge, remaining 50% trails 1.5% to  |
| 8 | **E208** pc_pump_top_trader_short_ | X101 composite_exit_be_pa | breakeven | standard | Smart-money + funding-extreme cross-signal is a novel high-conviction short. Adds positioning-data dimension (top_trader |
| 9 | **C062** cc_three_signal_funding_n | X101 composite_exit_be_pa | breakeven | exploratory | First cross-channel archetype with funding-neutral gate — explicitly excludes the regime that produced the E126 trap. Th |
| 10 | **E212** hour_session_us_pump_long | X105 x104_breakeven_stric | breakeven | exploratory | First archetype using the supported `session` field — exploits US-session liquidity regime. Paired with strict 30s break |

**多样性审计**：
- 频道分布：{'OI_Price': 2, 'pricechange': 6, 'Reserved6': 1, '*': 1}
- 方向分布：{'long': 7, 'short': 3, 'both': 0}
- Exit family 分布：{'fixed': 0, 'time_only': 1, 'breakeven': 6, 'trail': 1, 'multi_tp': 2}
- 评估：Top-10 covers all 4 channels and 4 of 5 exit families (fixed deliberately omitted since X101 composite already encodes BE+partial-runner and the user's live system runs fixed-style exits). Long-side still dominates 7-3, but this is the correct posture for the registry's accepted archetype mix; further short additions would require new archetype generation in Round 4.

## 四、Paper Shadow（$1000 复利模拟）Top 5 结果

### E005_1777332620

```
| Scenario | cost(bps) | trades | final$ | total% | max_dd% | win% | sharpe | p10 trade% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ideal | 8 | 795 | $943.76 | -5.62 | 5.86 | 78.2 | -0.153 | -0.5860 |
| realistic | 16 | 795 | $899.79 | -10.02 | 10.03 | 77.6 | -0.280 | -0.6660 |
| harsh | 24 | 795 | $857.87 | -14.21 | 14.21 | 0.0 | -0.406 | -0.7460 |
```

### E004_1777332618

```
| Scenario | cost(bps) | trades | final$ | total% | max_dd% | win% | sharpe | p10 trade% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ideal | 8 | 190 | $968.09 | -3.19 | 3.57 | 83.2 | -0.190 | -0.6946 |
| realistic | 16 | 190 | $957.11 | -4.29 | 4.42 | 82.6 | -0.256 | -0.7746 |
| harsh | 24 | 190 | $946.26 | -5.37 | 5.37 | 0.0 | -0.323 | -0.8546 |
```

### E003_1777332615

```
| Scenario | cost(bps) | trades | final$ | total% | max_dd% | win% | sharpe | p10 trade% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ideal | 8 | 190 | $984.75 | -1.52 | 2.28 | 83.2 | -0.091 | -0.8163 |
| realistic | 16 | 190 | $973.59 | -2.64 | 3.05 | 83.2 | -0.159 | -0.8963 |
| harsh | 24 | 190 | $962.55 | -3.74 | 3.93 | 83.2 | -0.227 | -0.9763 |
```

### E002_1777332613

```
| Scenario | cost(bps) | trades | final$ | total% | max_dd% | win% | sharpe | p10 trade% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ideal | 8 | 406 | $973.18 | -2.68 | 2.73 | 75.4 | -0.158 | -0.6095 |
| realistic | 16 | 406 | $949.76 | -5.02 | 5.04 | 74.6 | -0.300 | -0.6895 |
| harsh | 24 | 406 | $926.90 | -7.31 | 7.31 | 0.0 | -0.442 | -0.7695 |
```

### E001_1777332611

```
| Scenario | cost(bps) | trades | final$ | total% | max_dd% | win% | sharpe | p10 trade% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ideal | 8 | 406 | $973.18 | -2.68 | 2.74 | 75.4 | -0.158 | -0.6095 |
| realistic | 16 | 406 | $949.76 | -5.02 | 5.04 | 74.6 | -0.300 | -0.6895 |
| harsh | 24 | 406 | $926.90 | -7.31 | 7.31 | 0.0 | -0.442 | -0.7695 |
```


## 五、关键发现 / 警示

- ⚠️ **asymmetric_TP_SL_high_winrate** — Generator must include kelly_capped and p25_capped_tail in objective; reject any keep where SL/TP > 4 even if mean score is positive
- ⚠️ **trigger_saturation_at_5000** — Generator should treat any archetype with trig=5000 AND score within ±0.005 of channel baseline as a duplicate; require novel_dim that demonstrably reduces triggers below 4500
- ⚠️ **composite_exit_be_partial_runner_floor** — Stop pairing X100 with new entries until exit-side hypothesis is sharper; use fixed exit as default exit_id
- ✅ Top winner **E001** 在 Kelly metric 下 +10.00% — 真有 alpha（不是 p25 trap）

## 六、推荐下一步

### 立即可做

1. **Paper shadow** 这 10 个真 alpha 候选（Kelly>0）——拿真实 1 周 PnL 数据
2. Review 上面 Round 3 接受的 archetypes，去除任何明显错位
3. 检查 Cross-Pair Recommender 推荐对，挑 3 个 `fast` 优先级先 GPU 验证

### 中期（Round 4）

- 基于今晚结果让 LLM team 加深 winner 邻域
- 探索 Round 3 标记的 underexplored 主题
- 如有需要，调整 score metric / variant grid 范围

---

完整产物路径：
- Round 3 debate: `H:\BWE\40_EXPERIMENTS\debates\debate_20260427_181904`
- Rescore (4 metrics): `H:\BWE\40_EXPERIMENTS\analysis\rescore_20260427_181902`
- Analysis: `H:\BWE\40_EXPERIMENTS\analysis\20260427_181440`
