# DEEP Debate transcript: debate_20260427_181904

- Trigger: `round_3_full_grid_complete`
- Mode: per-proposal deep analysis (86 LLM calls)
- Models: {'pattern_miner': 'claude-opus-4-7', 'generator': 'claude-opus-4-7', 'steelman': 'claude-opus-4-7', 'devil': 'claude-opus-4-7', 'quant': 'claude-opus-4-7', 'risk': 'claude-opus-4-7', 'metric_critic': 'claude-opus-4-7', 'synthesizer': 'claude-opus-4-7', 'self_reflection': 'claude-opus-4-7', 'behavior_annotator': 'claude-opus-4-7', 'cross_pair_recommender': 'claude-opus-4-7'}
- Existing archetypes: 523 total

## Generator output

```json
{
  "summary": "Pattern_miner identifies starved exit pipeline (4/5 families zero-positive), dormant OI_Price channel (61 entries, none in top-10), and asymmetric TP/SL trap; this batch ports proven pricechange/long templates to OI_Price, proposes novel exit kernels with natural symmetry, and adds short-side mean-reversion hypotheses with kelly-safe TP/SL ratios.",
  "proposals": [
    {
      "archetype": "oi_pump_taker_buy_extreme_high_liq_long",
      "type": "entry",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.65",
        "liquidity_bucket=high",
        "oi_change_pct>=10"
      ],
      "notes": "OI burst with aggressive taker buying in high-liquidity names — port of E126 winning template to OI_Price channel where 61 archetypes registered but none in top-10.",
      "rationale": "OI_Price channel is the largest underexplored region per pattern_miner; combining 3 orthogonal supported signals (taker_buy + liquidity + oi_change) on a non-pricechange channel is structurally distinct from any of the 61 existing OI_Price entries which lack this triple-AND.",
      "expected_distinct": true
    },
    {
      "archetype": "oi_pump_global_short_high_long",
      "type": "entry",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "global_short_ratio_high",
        "oi_change_pct>=12",
        "liquidity_bucket=high"
      ],
      "notes": "OI burst on names where global short ratio is elevated — squeeze fuel hypothesis, mirrors E148 from pricechange to OI channel.",
      "rationale": "E148 (global_short_high pricechange) scored +0.350 with only 988 trig (selective); porting the squeeze-fuel logic to OI_Price exploits a different event distribution and remains distinct from existing OI_Price archetypes.",
      "expected_distinct": true
    },
    {
      "archetype": "oi_crash_taker_buy_reversal_long",
      "type": "entry",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.60",
        "oi_change_pct<=-8",
        "liquidity_bucket=high"
      ],
      "notes": "OI reduction with concurrent taker BUY pressure — short-cover reversal setup distinct from continuation longs.",
      "rationale": "All existing OI_Price longs assume continuation; this archetype explicitly hunts OI-down + buy-pressure divergence, a novel cross-signal not covered in 61 existing OI_Price entries.",
      "expected_distinct": true
    },
    {
      "archetype": "oi_pump_funding_neutral_taker_extreme_long",
      "type": "entry",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.65",
        "funding>=-0.0001",
        "funding<=0.0001",
        "oi_change_pct>=10"
      ],
      "notes": "OI burst with neutral funding (no crowding) plus extreme taker buying — clean signal without funding skew.",
      "rationale": "Funding-neutral filter on OI_Price has not been tested; isolates organic OI growth from funding-driven positioning to avoid the E126 funding-skew trap.",
      "expected_distinct": true
    },
    {
      "archetype": "pc_pump_taker_buy_high_liq_global_short_long",
      "type": "entry",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.65",
        "liquidity_bucket=high",
        "global_short_ratio_high"
      ],
      "notes": "Triple-AND combining the three top R2 winners (taker_buy + high_liq + global_short_high) into one selective entry.",
      "rationale": "Each component appears separately in top-10 (E126/E051/E148) but the triple intersection has not been tested; pattern_miner explicitly recommends this combination to push lift above +0.50 without saturating triggers.",
      "expected_distinct": true
    },
    {
      "archetype": "pc_pump_funding_positive_taker_sell_short",
      "type": "entry",
      "channel": "pricechange",
      "side": "short",
      "novel_dim": [
        "funding>=0.0005",
        "taker_buy_ratio_5m<=0.40",
        "move_pct>=3"
      ],
      "notes": "Crowded-long pump with positive funding and taker SELL dominance — classic mean-reversion fade with natural SL=TP symmetry.",
      "rationale": "Existing 94 short entries collapse to channel baseline because they reuse continuation logic; this is mean-reversion-on-crowding with three orthogonal supported signals, structurally novel.",
      "expected_distinct": true
    },
    {
      "archetype": "pc_pump_top_trader_short_funding_high_short",
      "type": "entry",
      "channel": "pricechange",
      "side": "short",
      "novel_dim": [
        "top_trader_position_ratio_low",
        "funding_pct_top_decile",
        "move_pct>=3"
      ],
      "notes": "Smart money positioned short while retail funding extreme — high-conviction fade short.",
      "rationale": "top_trader_position_ratio flag tokens have not been combined with funding extremes on pricechange shorts; novel cross-signal with smart-money confirmation.",
      "expected_distinct": true
    },
    {
      "archetype": "pc_crash_oversold_global_long_extreme_long",
      "type": "entry",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "global_long_ratio_extreme",
        "move_pct<=-4",
        "taker_buy_ratio_5m>=0.55"
      ],
      "notes": "Crash with retail capitulation extreme + early taker buy reversal — counter-trend bounce.",
      "rationale": "Crash-long counter-trend with global_long_extreme as capitulation gauge has not been tested; pattern_miner notes E066 (crash_taker_buy_long) +0.339, this adds capitulation filter for higher selectivity.",
      "expected_distinct": true
    },
    {
      "archetype": "r6_bigmove_simple_long",
      "type": "entry",
      "channel": "Reserved6",
      "side": "long",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.55"
      ],
      "notes": "Single-filter Reserved6 long — minimal AND to preserve sparse R6 trigger count (~120 baseline).",
      "rationale": "Pattern_miner explicit fix: R6 archetypes crash with multi-filter AND; reducing to ≤1 novel_dim is the corrective architecture, not a parameter tweak.",
      "expected_distinct": true
    },
    {
      "archetype": "r6_pump_high_liq_only_long",
      "type": "entry",
      "channel": "Reserved6",
      "side": "long",
      "novel_dim": [
        "liquidity_bucket=high"
      ],
      "notes": "R6 long gated only by high liquidity — sparse-channel safe filter.",
      "rationale": "All current R6 archetypes use 2+ filters and crash; single-dim high_liq is a structurally distinct sparse-channel adaptation per pattern_miner guidance.",
      "expected_distinct": true
    },
    {
      "archetype": "hour_session_us_pump_long",
      "type": "entry",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "session=US",
        "taker_buy_ratio_5m>=0.60",
        "liquidity_bucket=high"
      ],
      "notes": "Session-gated entry restricting pricechange longs to US trading hours — exploits liquidity regime.",
      "rationale": "No existing archetype combines session= category with taker_buy + liquidity AND; novel regime gate using supported `session` field.",
      "expected_distinct": true
    },
    {
      "archetype": "weekday_weekend_avoid_long",
      "type": "filter",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "weekday=Mon",
        "weekday=Tue",
        "weekday=Wed",
        "weekday=Thu",
        "weekday=Fri"
      ],
      "notes": "Filter excluding weekend events — addresses thin weekend liquidity bias.",
      "rationale": "`weekday` field is supported but unused in 121 existing filters; structurally novel time-of-week regime gate.",
      "expected_distinct": true
    },
    {
      "archetype": "basis_curvature_pump_short",
      "type": "entry",
      "channel": "pricechange",
      "side": "short",
      "novel_dim": [
        "basis_rate>=0.001",
        "premium_bps>=20",
        "move_pct>=3"
      ],
      "notes": "Pump with extreme basis AND premium — perp dislocation fade.",
      "rationale": "basis_rate combined with premium_bps as joint dislocation gauge has not been used; novel cross-derivative signal distinct from single-field premium archetypes.",
      "expected_distinct": true
    },
    {
      "archetype": "x101_quick_cut_60s_time_exit",
      "type": "exit",
      "channel": "NA",
      "side": "NA",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.65"
      ],
      "notes": "Pure time_only 60s exit paired with high-conviction entries — quick mean-reversion harvest before drift.",
      "rationale": "time_only family has 0 positives across 2745 runs but pattern_miner notes `only viable if paired with quick-revert mean-reversion entry, none such tested`; 60s window on high-taker entries is the untested combination.",
      "expected_distinct": true
    },
    {
      "archetype": "x102_wide_trail_2pct_exit",
      "type": "exit",
      "channel": "NA",
      "side": "NA",
      "novel_dim": [
        "liquidity_bucket=high"
      ],
      "notes": "Trail family with 2.0% step on top entries — wider trail to avoid premature stop-out.",
      "rationale": "trail family max approaches 0 (-0.006) suggesting step size is wrong, not concept dead; pattern_miner explicitly recommends wider trail (1.5-2.5%) which has not been swept.",
      "expected_distinct": true
    },
    {
      "archetype": "x103_multi_tp_60_40_ladder_exit",
      "type": "exit",
      "channel": "NA",
      "side": "NA",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.60"
      ],
      "notes": "Two-step TP ladder 60/40 with first TP at 0.5% second at 1.5% — captures bulk early.",
      "rationale": "multi_tp 50/30/20 ladders all failed; 60/40 with front-loaded harvest on high-conviction entries is novel ladder shape distinct from existing X-series.",
      "expected_distinct": true
    },
    {
      "archetype": "x104_breakeven_strict_30s_exit",
      "type": "exit",
      "channel": "NA",
      "side": "NA",
      "novel_dim": [
        "liquidity_bucket=high"
      ],
      "notes": "Breakeven kernel with stricter trigger threshold and 30s activation — differentiates from X100 floor.",
      "rationale": "breakeven family clusters at -0.08 floor due to lax trigger; tightening BE activation timing is structurally different exit logic.",
      "expected_distinct": true
    },
    {
      "archetype": "x105_hybrid_fixed_then_trail_exit",
      "type": "exit",
      "channel": "NA",
      "side": "NA",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.60"
      ],
      "notes": "Hybrid: take 50% at fixed 0.5% TP, trail remaining 50% with 1.5% step — symmetric risk/reward.",
      "rationale": "Hybrid composition combining fixed + trail families is a NEW exit family per quality bar #3; not present in 101 existing exits which are mono-family.",
      "expected_distinct": true
    },
    {
      "archetype": "cc_pc_oi_within_60s_double_long",
      "type": "cross_channel",
      "channel": "*",
      "side": "long",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.60",
        "liquidity_bucket=high",
        "oi_change_pct>=8"
      ],
      "notes": "Pricechange and OI_Price both fire within 60 seconds with taker_buy confirmation — tight double-channel timing window.",
      "rationale": "60-channel cross_channel timing has not been tested with <2m windows per quality bar #4; existing cc_*_5m archetypes use looser windows that saturate at baseline.",
      "expected_distinct": true
    },
    {
      "archetype": "cc_three_signal_funding_neutral_long",
      "type": "cross_channel",
      "channel": "*",
      "side": "long",
      "novel_dim": [
        "funding>=-0.0001",
        "funding<=0.0001",
        "taker_buy_ratio_5m>=0.60",
        "liquidity_bucket=high"
      ],
      "notes": "Three-channel alignment requiring funding-neutral regime — avoids crowded-trade traps.",
      "rationale": "Existing cc archetypes do not condition on funding-neutral; novel weighting that filters out funding-driven moves is structurally distinct.",
      "expected_distinct": true
    },
    {
      "archetype": "r_kelly_safe_size_filter",
      "type": "risk",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "liquidity_bucket=high",
        "taker_buy_ratio_5m>=0.60"
      ],
      "notes": "Risk archetype enforcing position size only when both liquidity and taker_buy confirm — kelly-safe sizing.",
      "rationale": "Existing 40 risk archetypes don't combine liquidity + taker_buy as size-gating AND; novel sizing filter with natural TP/SL symmetry to dodge E126-style asymmetric trap.",
      "expected_distinct": true
    }
  ]
}
```

## Proposal 1: `oi_pump_taker_buy_extreme_high_liq_long`

### proposal
```json
{
  "archetype": "oi_pump_taker_buy_extreme_high_liq_long",
  "type": "entry",
  "channel": "OI_Price",
  "side": "long",
  "novel_dim": [
    "taker_buy_ratio_5m>=0.65",
    "liquidity_bucket=high",
    "oi_change_pct>=10"
  ],
  "notes": "OI burst with aggressive taker buying in high-liquidity names — port of E126 winning template to OI_Price channel where 61 archetypes registered but none in top-10.",
  "rationale": "OI_Price channel is the largest underexplored region per pattern_miner; combining 3 orthogonal supported signals (taker_buy + liquidity + oi_change) on a non-pricechange channel is structurally distinct from any of the 61 existing OI_Price entries which lack this triple-AND.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "oi_pump_taker_buy_extreme_high_liq_long",
  "best_case_thesis": "This proposal targets a textbook smart-money footprint: a sharp OI expansion (≥10%) accompanied by aggressive taker-buy dominance (≥0.65) in high-liquidity names is the signature of informed leveraged longs being opened against passive sellers, not retail FOMO chasing thin books. The triple-AND filter forces all three conditions to align simultaneously, which historically marks the early phase of a directional repricing rather than a noise burst — exactly the structural setup that drove E126 to top of leaderboard, but now ported to a channel (OI_Price) where the signal-to-noise on OI deltas is native rather than derived.",
  "expected_alpha_source": "Informed-flow leverage initiation: new OI being aggressively lifted at the offer in deep books reveals positioning by participants willing to pay the spread, which precedes price discovery before passive market-makers reprice their quotes.",
  "edge_strength_estimate": "strong",
  "regime_match": "Trending or regime-transition markets with rising aggregate OI — specifically post-consolidation breakouts where leverage is being rebuilt after a deleveraging event, and high-liquidity names lead the move before alts catch up.",
  "complementary_exit_families": [
    "fixed"
  ],
  "complementary_existing_archetypes": [
    "E126",
    "E064",
    "E051"
  ],
  "if_paper_works_likely_reason": "The OI_Price channel provides an earlier trigger than pricechange-based E126 because OI moves frequently lead price in leverage-driven markets, so the same taker-buy + liquidity edge fires with better entry timing and lower slippage in deep books.",
  "could_compound_with": "Any exit-side archetype that uses OI-decay or taker-flow-reversal as a stop signal would synergize, since the same channel that generated the entry can detect when the informed flow has exhausted — closing the loop on a single-channel thesis rather than cross-channel mismatch."
}
```

### devil
```json
{
  "summary": "Single proposal looks structurally sound and worth testing; main concerns are sample-size depth on the triple-AND and BTC-regime dependence of the E126 template port.",
  "critiques": [
    {
      "archetype_ref": "oi_pump_taker_buy_extreme_high_liq_long",
      "verdict": "possibly_fail",
      "concerns": [
        "Triple-AND of taker_buy_ratio_5m>=0.65, liquidity_bucket=high, and oi_change_pct>=10 may be statistically fragile on a 30-day window — E148 (pc_pump_global_short_high) already shows trig=988 vs trig=3443 for E126, and stacking a third filter on the smaller OI_Price channel could drop trigger count below the threshold where mean/kelly_capped is stable.",
        "Template was discovered on pricechange channel (E126); OI_Price has different microstructure — OI burst >=10% in high-liquidity names is rarer and often coincides with funding/liquidation cascades that flip direction within seconds, so the long-side bias of E126 may not transfer.",
        "'liquidity_bucket=high' may correlate with BTC/ETH/SOL majors where OI moves are dominated by perp-funding arbitrage rather than directional taker flow — risk that the edge is concentrated in 1-2 symbols and disappears under symbol-stratified evaluation.",
        "R2 lesson: legacy p25 metric was blind to asymmetric TP/SL left tail (E126 paper compounded to -13.5% on $1000). A direct port carries the same risk — the entry quality must be judged by mean/kelly_capped/p25_capped_tail, not best-score lift."
      ],
      "monitoring_advice": "During paper-shadow: (1) track per-symbol contribution — flag if >40% of triggers come from a single symbol; (2) compare trigger count vs E126 baseline — if <500 over 30d the triple-AND is too tight; (3) split performance by BTC 1h regime (trend/chop/down) to detect regime dependence; (4) require kelly_capped and p25_capped_tail to clear thresholds, not just mean lift; (5) verify oi_change_pct and taker_buy_ratio_5m are computed from T0-closed bars only (no look-ahead from the in-progress 5m window)."
    }
  ]
}
```

### quant
```json
{
  "summary": "Strong proposal: all 3 novel_dim conditions parse cleanly via supported fields, structurally distinct from existing OI_Price entries, and triggers estimate lands in the adequate-to-tight range with broad exit compatibility skewed toward fixed.",
  "analyses": [
    {
      "archetype_ref": "oi_pump_taker_buy_extreme_high_liq_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E126",
        "E064",
        "E051"
      ],
      "distinctness_notes": "E126/E064 are the winning taker_buy templates but on pricechange channel; E051 uses high_liquidity on pricechange. No existing OI_Price entry combines taker_buy_ratio_5m + liquidity_bucket=high + oi_change_pct threshold as a triple-AND. The 61 OI_Price archetypes appear to focus on OI/funding/global_ratio dimensions, not taker-flow + liquidity. Cross-channel port of a proven pricechange template to OI_Price is structurally novel and tests whether the taker-buy edge generalizes beyond pricechange.",
      "expected_triggers_30d": 105,
      "triggers_estimate_method": "1400 OI_Price events × 0.30 (oi_change_pct>=10 is moderately common on OI_Price by construction) × 0.50 (high_liquidity bucket ~top tercile) × 0.50 (taker_buy_ratio_5m>=0.65 is roughly p70-p75 in pump regimes) ≈ 105",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Coverage table shows fixed dominates (mean +0.175, median +0.217, 6680/7320 positive) while multi_tp/trail/time_only/breakeven all have median<0 and zero positives — strongly recommend prioritizing fixed exits. Given E126's R2 paper-trade trap (TP=0.51/SL=6.00 asymmetry compounded to -13.5%), pair with symmetric or capped-asymmetry fixed grids and validate on mean/kelly_capped/p25_capped_tail rather than legacy p25. Breakeven could be a secondary screen to neutralize left-tail risk on this template."
    }
  ]
}
```

### risk
```json
{
  "summary": "Single proposal ports E126's winning template to OI_Price channel using three supported, T0-safe fields; no integrity issues identified — caution on live-overlap with the existing OI_Price pump-long live strategy.",
  "risk_assessments": [
    {
      "archetype_ref": "oi_pump_taker_buy_extreme_high_liq_long",
      "leakage_risk": "low",
      "leakage_notes": "All three novel_dim fields are T0-observable: taker_buy_ratio_5m is a trailing 5m window ending at T0 (not forward-looking), liquidity_bucket is a static/slow classification, and oi_change_pct is a point-in-time delta. No forward_*, confirm_after_*, or post_event_* fields present. Minor caveat: ensure taker_buy_ratio_5m is implemented as the trailing [T0-5m, T0] window and not [T0, T0+5m] — naming is ambiguous but matches E126's convention which has been validated as T0-safe.",
      "multitest_inflation_risk": "medium",
      "multitest_inflation_notes": "This is the 524th archetype in a registry of 523, with 61 already on OI_Price channel. Triple-AND on supported fields is structurally distinct, but the family-wise FDR across 20k results is non-trivial. Mitigated by Round 3 metrics (mean, kelly_capped, p25_capped_tail) that already penalize asymmetric TP/SL traps surfaced in R2. Acceptable with current metric stack.",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "User runs 'BWE_OI_Price_monitor pump long' live. This proposal is OI_Price + long + OI-burst + taker-buy-extreme — same channel, same side, similar trigger geometry. In paper-shadow mode this is a monitoring item, not a blocker; concurrent live deployment would risk position pile-on / effective leverage above intended sizing on the same symbol set.",
      "concentration_risk": "medium",
      "concentration_notes": "liquidity_bucket=high restricts the universe to a small set of top-liquidity symbols (likely BTC/ETH/SOL-tier). Combined with oi_change_pct>=10 and taker_buy_ratio_5m>=0.65, triggers will cluster on 1–3 symbols during correlated OI bursts. At 5–10% per trade on $1000 capital, 2–3 concurrent triggers within minutes is plausible — advisory only in paper-shadow.",
      "adversarial_risk": "low",
      "adversarial_notes": "Anyone observing the BWE OI_Price stream could anticipate triggers, but $1000 capital makes front-running economically irrelevant. No mass-symbol manipulation enabler.",
      "overall_severity": "caution",
      "remediation": "Proceed to backtest. For paper-shadow monitoring: (1) tag results with overlap-flag against the live OI_Price pump-long strategy and report concurrent-trigger frequency, (2) verify taker_buy_ratio_5m is implemented as trailing window in the kernel before scoring, (3) report symbol-concentration (top-1 and top-3 symbol share of triggers) alongside the standard metric stack so single-symbol dependence is visible."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "oi_pump_taker_buy_extreme_high_liq_long",
  "predicted_tp_pct": 0.6,
  "predicted_sl_pct": 4.5,
  "predicted_tp_sl_ratio": 0.133,
  "predicted_win_rate": 0.78,
  "predicted_mean_per_trade_pct": -0.531,
  "predicted_kelly_pct": 0.0,
  "trap_risk": "high",
  "trap_reasoning": "This is a structural port of the E126 template (pump + extreme taker buy) onto the OI_Price channel, and the underlying market microstructure that produced E126's asymmetric TP/SL geometry is the same here: aggressive taker buying into an OI burst tends to mark short-term local tops, so the GPU optimizer will likely converge on a tight TP (~0.5–0.7%) capturing frequent small mean-reversion bounces, paired with a wide SL (~4–6%) needed to survive the occasional violent continuation. The 'high liquidity' filter modestly tightens win-rate (slippage-tolerant names trend more cleanly post-pump) — I estimate W≈0.78 — but with TP/SL ≈ 1:7.5, expectancy is W·TP − (1−W)·SL ≈ 0.78·0.6 − 0.22·4.5 = 0.468 − 0.99 = −0.522%, minus 8 bps cost ≈ −0.60%. Kelly is 0 (negative expectancy). Legacy p25 will likely look strong (~+0.4) and rank near E126, but mean_net_pct and kelly_capped will correctly flag it. Moderate uncertainty on exact TP/SL — the OI_Price channel may converge slightly tighter on SL than pricechange did, but the asymmetry direction is robust.",
  "recommended_constraint": "force SL ≤ 2 × TP_pct in variant grid; additionally require min TP ≥ 0.8% to prevent micro-TP noise harvesting",
  "metric_score_estimate": 0.5
}
```

## Proposal 2: `oi_pump_global_short_high_long`

### proposal
```json
{
  "archetype": "oi_pump_global_short_high_long",
  "type": "entry",
  "channel": "OI_Price",
  "side": "long",
  "novel_dim": [
    "global_short_ratio_high",
    "oi_change_pct>=12",
    "liquidity_bucket=high"
  ],
  "notes": "OI burst on names where global short ratio is elevated — squeeze fuel hypothesis, mirrors E148 from pricechange to OI channel.",
  "rationale": "E148 (global_short_high pricechange) scored +0.350 with only 988 trig (selective); porting the squeeze-fuel logic to OI_Price exploits a different event distribution and remains distinct from existing OI_Price archetypes.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "oi_pump_global_short_high_long",
  "best_case_thesis": "This proposal targets the canonical short-squeeze fuel mechanism but routes it through the OI_Price channel rather than pure pricechange — meaning it fires when open interest is genuinely expanding (new positioning, not just liquidation noise) on names where global short ratio is already elevated. That combination is the textbook setup for forced-cover cascades: shorts add to losing positions as OI climbs, and any upward impulse triggers stop-driven buying that compounds because borrow is concentrated. The OI confirmation filter is what distinguishes a real squeeze from a fake breakout, which is precisely why E148's pricechange-only version scored +0.350 with only 988 triggers (high selectivity).",
  "expected_alpha_source": "Forced short-cover cascades on names with elevated short interest where rising OI confirms fresh positioning rather than mere liquidation churn.",
  "edge_strength_estimate": "strong",
  "regime_match": "High-dispersion alt regimes with elevated funding skew and concentrated short positioning — typically late-cycle accumulation or post-capitulation rebound phases where shorts are crowded.",
  "complementary_exit_families": [
    "fixed"
  ],
  "complementary_existing_archetypes": [
    "E148",
    "E126",
    "E064",
    "E051"
  ],
  "if_paper_works_likely_reason": "The OI confirmation filter materially reduces false-positive squeezes versus the pricechange-only E148, so the win rate holds while the asymmetric-TP/SL trap (R2 lesson) is mitigated by the rarer, higher-conviction trigger distribution.",
  "could_compound_with": "Any sibling proposal that adds a taker-buy-dominance filter on the OI channel (mirroring E126→OI port) — stacking 'fresh OI + crowded shorts + aggressive taker buying' would isolate the strongest squeeze-fuel subset and likely lift edge into exceptional territory."
}
```

### devil
```json
{
  "summary": "Single-proposal deep review: OI-channel port of E148 squeeze-fuel logic looks logically clean and worth testing, but trigger sparsity and channel-mapping assumptions warrant paper-shadow monitoring.",
  "critiques": [
    {
      "archetype_ref": "oi_pump_global_short_high_long",
      "verdict": "possibly_fail",
      "concerns": [
        "Trigger sparsity risk: source archetype E148 only fired 988 times on pricechange channel; porting to OI_Price with an additional oi_change_pct>=12 gate (stricter than typical OI burst thresholds) plus liquidity_bucket=high plus global_short_ratio_high is a 3-way conjunction that may drop trig count below statistical-significance threshold (~200-300 events) over the 30-day window.",
        "Channel semantics mismatch: E148's edge on pricechange channel exploits squeeze fuel AT the moment of price-driven momentum; OI_Price channel fires on OI bursts which can occur WITHOUT immediate price movement (accumulation regime). Squeeze-fuel hypothesis assumes shorts are underwater — on a quiet OI burst with flat price, shorts are NOT yet pressured, so the squeeze-fuel mechanism may not transmit cleanly.",
        "global_short_ratio staleness: global_short_ratio is typically published at 5min/15min cadence by exchanges. On an OI_Price T0 trigger, the most recent global_short_ratio reading could be up to ~5min old, meaning 'high' may already reflect post-squeeze positioning rather than pre-squeeze fuel. Worth verifying the field's update frequency in the feature store.",
        "Cost sensitivity at high liquidity_bucket: filtering to high liquidity reduces slippage but also concentrates picks on majors (BTC/ETH/SOL) where 8-16bps round-trip is a larger fraction of typical OI-burst move magnitude than on mid-caps; net edge after costs may compress more than the lift_vs_median suggests."
      ],
      "monitoring_advice": "During paper-shadow: (1) log trig count daily and abort if <100 fires in first 7 days; (2) bucket fills by time-since-last-global_short_ratio-update and check if edge survives only on fresh (<60s) readings; (3) compare per-symbol concentration vs E148 — if >40% of fires come from <3 symbols, treat as overfit to recent squeeze episodes; (4) track left-tail (p25_capped_tail, kelly_capped) alongside mean to avoid the asymmetric TP/SL trap from R2's E126 lesson."
    }
  ]
}
```

### quant
```json
{
  "summary": "Proposal is mathematically healthy: all 3 novel_dim conditions are parser-supported, structurally distinct from existing OI_Price archetypes, and expected sample size is adequate for Phase 3 evaluation with broad exit compatibility.",
  "analyses": [
    {
      "archetype_ref": "oi_pump_global_short_high_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E148"
      ],
      "distinctness_notes": "E148 lives in pricechange channel; this proposal ports the global_short_high squeeze-fuel hypothesis to OI_Price channel where the trigger distribution is fundamentally different (OI bursts vs price moves). Additional liquidity_bucket=high and oi_change_pct>=12 narrowing makes the filter signature unique among the 61 existing OI_Price entry archetypes. Channel migration of a logic pattern is structural distinctness, not duplication — different event base rate, different entry timing, different microstructure.",
      "expected_triggers_30d": 168,
      "triggers_estimate_method": "OI_Price base ~1400 events × 0.6 (oi_change_pct>=12 — moderate threshold, ~60% of OI events meet 12% pump bar based on channel-typical magnitudes) × 0.25 (global_short_ratio_high = p75 flag, ~25% of universe) × 0.8 (liquidity_bucket=high, dominant bucket for OI-active names) ≈ 168",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Squeeze-fuel longs benefit most from `fixed` (the only family with positive mean +0.175 in coverage) and `multi_tp` ladders to capture asymmetric upside on short-squeeze impulses. `trail` is a reasonable secondary to ride extended squeezes. Avoid `time_only` (worst family, mean -0.73) and `breakeven` (mean -0.096) — both cut squeeze runners prematurely. Recommend Phase 3 grid prioritize fixed + multi_tp with TP-skewed ratios to avoid the E126 asymmetric-TP/SL trap flagged in R2 lessons."
    }
  ]
}
```

### risk
```json
{
  "summary": "Single OI_Price port of E148 squeeze-fuel logic — fields are T0-computable, no leakage detected; live-overlap and concentration are paper-shadow monitoring concerns, not blockers.",
  "risk_assessments": [
    {
      "archetype_ref": "oi_pump_global_short_high_long",
      "leakage_risk": "none",
      "leakage_notes": "All three novel_dim fields (global_short_ratio_high, oi_change_pct>=12, liquidity_bucket=high) are point-in-time observables at T0. No forward_*, confirm_after_*, or post_event_* tokens. global_short_ratio is a published exchange metric available pre-event; oi_change_pct on the OI_Price channel is the channel's defining T0 quantity; liquidity_bucket is a static-window classification. Nothing post-T0.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "User runs 'BWE_OI_Price pump long' live. This proposal is also OI_Price + long + pump-flavored, so paper signals will frequently fire on the same symbol/window as the live book, double-loading long exposure rather than opposing it. Same-side overlap, not an opposite-side conflict — paper-shadow monitoring item per Round 3 posture.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "No blocker. For monitoring during paper-shadow: (1) tag fills with a 'live_overlap=oi_pump_long' flag so the analyzer can measure correlation with the live strategy's PnL; (2) cap concurrent OI_Price/long positions across {live + this archetype + sibling pricechange E148} at the existing per-symbol/per-window limit; (3) track family-wise lift across the global_short_high cluster (E148 + this + any future ports) so the synthesizer can detect FDR inflation if more channel ports are proposed."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "oi_pump_global_short_high_long",
  "predicted_tp_pct": 0.65,
  "predicted_sl_pct": 2.6,
  "predicted_tp_sl_ratio": 0.25,
  "predicted_win_rate": 0.72,
  "predicted_mean_per_trade_pct": 0.07,
  "predicted_kelly_pct": 3.2,
  "trap_risk": "medium",
  "trap_reasoning": "This is a long-side squeeze-fuel thesis on the OI_Price channel: OI burst + elevated global short ratio + high liquidity. The setup is asymmetric by nature — squeeze pops are sharp but mean-revert quickly, and the GPU optimizer has historically converged on TP≈0.5–0.8% with SL≈2.5–6% on similar pump-type long entries (E126, E148 family). Selectivity is moderate-to-high (3 ANDs, with global_short_ratio_high and oi_change_pct>=12 both being narrow gates), so I expect win-rate in the 0.68–0.76 band — high enough to look great on legacy p25 but only marginally positive in expectancy once an SL≥4×TP geometry is applied. With cost -8 bps, E[trade] is plausibly +0.05 to +0.10% if the optimizer holds SL near 2.5×TP, but flips negative (full E126-style trap) if SL drifts to 4–5×TP. Reference E148 itself only had 988 triggers and scored +0.350 on legacy metric — under the new mean/kelly metrics it would likely look much weaker. Trap risk is medium, not high, because the high-liquidity gate should reduce slippage-driven SL blowouts vs. E126's no-liquidity-filter version, but the squeeze-fuel thesis structurally invites asymmetric geometry. Uncertainty on win-rate is ±5pp.",
  "recommended_constraint": "force SL ≤ 2.5 × TP_pct in the variant grid, and require min_triggers ≥ 800 to avoid overfit on a thin OI_Price slice",
  "metric_score_estimate": 3.2
}
```

## Proposal 3: `oi_crash_taker_buy_reversal_long`

### proposal
```json
{
  "archetype": "oi_crash_taker_buy_reversal_long",
  "type": "entry",
  "channel": "OI_Price",
  "side": "long",
  "novel_dim": [
    "taker_buy_ratio_5m>=0.60",
    "oi_change_pct<=-8",
    "liquidity_bucket=high"
  ],
  "notes": "OI reduction with concurrent taker BUY pressure — short-cover reversal setup distinct from continuation longs.",
  "rationale": "All existing OI_Price longs assume continuation; this archetype explicitly hunts OI-down + buy-pressure divergence, a novel cross-signal not covered in 61 existing OI_Price entries.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "oi_crash_taker_buy_reversal_long",
  "best_case_thesis": "This archetype targets a textbook short-squeeze reversal microstructure: open interest collapsing >=8% while taker-buy ratio sits above 60% is the signature of forced short covering — shorts are closing positions (OI down) by lifting offers (taker buy dominant). All 61 existing OI_Price longs assume continuation, so this is the first archetype in the registry hunting the OI-down + buy-pressure divergence, which is a structurally different trade from trend-following and tends to produce sharp, mean-reverting impulses rather than drift.",
  "expected_alpha_source": "Forced short-covering cascades where deleveraging shorts must cross the spread to exit, creating temporary buy-side imbalance before liquidity re-prices.",
  "edge_strength_estimate": "strong",
  "regime_match": "Most effective in post-flush conditions after a coordinated short build-up, when funding has been negative and a local capitulation low triggers stop-driven covering — i.e. the tail-end of a downtrend rather than ranging chop.",
  "complementary_exit_families": [
    "fixed",
    "multi_tp"
  ],
  "complementary_existing_archetypes": [
    "E066",
    "E126",
    "E051"
  ],
  "if_paper_works_likely_reason": "The high-liquidity bucket filter ensures the OI-drop signal reflects genuine position unwinds rather than thin-book noise, so the taker-buy confirmation cleanly isolates real short-cover impulses from random reversals.",
  "could_compound_with": "Any 'pc_crash_taker_buy_long' style proposal in this batch (e.g. E066 family extensions) — the price-channel crash signal and the OI-channel crash signal would cross-confirm the same underlying short-cover event, enabling a high-conviction cross-channel ensemble entry."
}
```

### devil
```json
{
  "summary": "Single-proposal deep review: OI-crash + taker-buy reversal long is logically coherent and channel-novel; main concern is statistical fragility of the -8% OI threshold over 30 days plus possible regime dependence.",
  "critiques": [
    {
      "archetype_ref": "oi_crash_taker_buy_reversal_long",
      "verdict": "possibly_fail",
      "concerns": [
        "Threshold fragility: oi_change_pct<=-8 on the OI_Price channel is a fairly extreme cut — over a 30-day window this co-occurring with taker_buy_ratio_5m>=0.60 AND liquidity_bucket=high may yield very few triggers (<500), risking that the score is driven by 1–2 symbols/events rather than a generalizable edge.",
        "Semantic ambiguity of 'oi_change_pct': if it is measured over the same/overlapping window as the OI_Price channel trigger itself, the -8% condition may be partially co-determined by the channel firing (OI_Price already implies a notable OI move). Verify the lookback window is independent of the channel trigger to avoid implicit redundancy / mild look-ahead.",
        "Regime dependence: short-cover reversal longs are a known pattern in BTC-led capitulation flushes but degrade in trending bear regimes where OI-down + taker-buy is just bear-flag distribution. Edge may be concentrated in specific BTC regimes within the 30-day sample.",
        "Cost sensitivity on reversal entries: reversal longs typically need a wider initial SL than continuation longs, so the 8–16 bps round-trip cost plus 3–5s execution latency on a fast bounce can disproportionately erode mean PnL — especially under multi_tp/trail exits which already showed negative means in coverage_summary."
      ],
      "monitoring_advice": "During paper-shadow: (1) log trigger count and unique-symbol count — flag if <300 triggers or top-3 symbols contribute >60% of PnL; (2) tag each trigger with concurrent BTC regime and check edge persists across at least 2 regimes; (3) compare mean and p25_capped_tail (not just best score) against the OI_Price/long continuation baseline to confirm this is genuinely additive rather than a re-slice; (4) given the R2 E126 lesson, enforce symmetric TP/SL evaluation and flag if the winning exit pairing has TP/SL ratio <0.2."
    }
  ]
}
```

### quant
```json
{
  "summary": "Proposal is mathematically healthy — all 3 conditions parse via SUPPORTED_FIELDS, structurally distinct from continuation-only OI_Price longs, sample size adequate; best paired with fixed/breakeven exits given reversal thesis.",
  "analyses": [
    {
      "archetype_ref": "oi_crash_taker_buy_reversal_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E066",
        "E126",
        "E051"
      ],
      "distinctness_notes": "Existing OI_Price longs in the registry are continuation-biased (OI-up + price-up + buy pressure). This archetype inverts the OI dimension (oi_change_pct<=-8, i.e. OI reduction / short-cover) while keeping taker buy pressure high — a divergence/reversal thesis not represented in the 61 existing OI_Price entries. E066 (pc_crash_taker_buy_long) is the closest cousin but lives on the pricechange channel and conditions on event_type=crash, not on OI reduction. Filter values + channel + signal logic are all materially different.",
      "expected_triggers_30d": 85,
      "triggers_estimate_method": "Base OI_Price events ~1400/30d. oi_change_pct<=-8 is a meaningful left-tail OI move — empirically ~25–30% of OI_Price triggers (call it 0.28). taker_buy_ratio_5m>=0.60 conditional on OI-down is a divergence signal — roughly 35% of OI-down events show contrarian buy pressure (0.35). liquidity_bucket=high cuts to ~60% of universe (0.60). 1400 × 0.28 × 0.35 × 0.60 ≈ 82. Conservative estimate: 85.",
      "sample_size_verdict": "tight",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Reversal/short-cover setups are mean-reverting in nature — they tend to pop quickly then fade, which favors fixed (with tight TP, modest SL) and breakeven kernels. Multi_tp could ladder out the initial cover bounce. Trail is risky here because reversal moves often retrace before extending, triggering premature stop-out. Time_only is poorly suited (whole exit family showed mean -0.73 in coverage_summary; reversal trades especially need a price-based exit). Recommend fixed + breakeven as primary, multi_tp as secondary; avoid trail and time_only."
    }
  ]
}
```

### risk
```json
{
  "summary": "Single OI_Price reversal-long proposal with no integrity issues — fields are at-T0 measurable, no leakage, no live conflict, paper-shadow monitoring posture applies.",
  "risk_assessments": [
    {
      "archetype_ref": "oi_crash_taker_buy_reversal_long",
      "leakage_risk": "none",
      "leakage_notes": "All three novel_dim fields are at-T0 observables: taker_buy_ratio_5m is a backward-looking 5m window (trailing, not forward), oi_change_pct is a point-in-time delta against a prior anchor, and liquidity_bucket is a static classification. No forward_*, post_event_*, confirm_after_*, or _after_event suffixes present. No future-snooping detected.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "caution",
      "live_conflict_notes": "Live BWE_OI_Price_monitor pump-long strategy targets OI-up + price-up continuation. This proposal targets OI-down + taker-buy reversal — same channel, same side (long), but orthogonal trigger conditions (oi_change_pct<=-8 vs pump). Concurrent same-symbol same-side longs would compound exposure rather than offset; not an opposite-side conflict. Paper-shadow only — flag for monitoring, not blocking.",
      "concentration_risk": "caution",
      "adversarial_risk": "caution",
      "overall_severity": "acceptable",
      "remediation": "None required for integrity. For paper-shadow deployment: (1) tag this archetype as reversal-family in registry so position-sizing layer can detect co-firing with live pump-long and cap aggregate same-symbol long exposure; (2) confirm taker_buy_ratio_5m is computed from the trailing 5m ending at T0 (not centered or forward) in the feature pipeline."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "oi_crash_taker_buy_reversal_long",
  "predicted_tp_pct": 0.8,
  "predicted_sl_pct": 2.0,
  "predicted_tp_sl_ratio": 0.4,
  "predicted_win_rate": 0.58,
  "predicted_mean_per_trade_pct": -0.46,
  "predicted_kelly_pct": 0,
  "trap_risk": "medium",
  "trap_reasoning": "Reversal setups against a sharp OI crash (-8%) are inherently mean-reversion plays catching falling knives. The GPU optimizer will likely converge on tight TP (0.6-1.0%) because reversal bounces are short-lived before resumption of the dominant trend, while SL must be wide (1.8-2.5%) to survive the residual liquidation cascade volatility — a 2.5-3x SL/TP ratio is structurally typical for counter-trend longs. Win-rate is bounded by the 'taker_buy_ratio>=0.60' filter strength (genuine buy pressure is a real edge signal) but capped around 55-65% because OI -8% events often have continuation tails that stop reversals. With W=0.58, TP=0.8, SL=2.0: E[trade]=0.58*0.8-0.42*2.0-0.08=-0.38% — negative expectancy. Kelly returns 0. The high-liquidity filter helps execution but doesn't fix the asymmetry. This is a textbook E126-style trap candidate: median trade may look fine (small bounces hit TP) but the -2% losing tail eats the book. High uncertainty on win-rate — if the OI-divergence signal is genuinely stronger than I'm crediting, W could reach 0.70+ which flips expectancy positive.",
  "recommended_constraint": "force SL <= 1.5 * TP_pct in variant grid; also require TP >= 0.6% to avoid degenerate scalp configs",
  "metric_score_estimate": 1.8
}
```

## Proposal 4: `oi_pump_funding_neutral_taker_extreme_long`

### proposal
```json
{
  "archetype": "oi_pump_funding_neutral_taker_extreme_long",
  "type": "entry",
  "channel": "OI_Price",
  "side": "long",
  "novel_dim": [
    "taker_buy_ratio_5m>=0.65",
    "funding>=-0.0001",
    "funding<=0.0001",
    "oi_change_pct>=10"
  ],
  "notes": "OI burst with neutral funding (no crowding) plus extreme taker buying — clean signal without funding skew.",
  "rationale": "Funding-neutral filter on OI_Price has not been tested; isolates organic OI growth from funding-driven positioning to avoid the E126 funding-skew trap.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "oi_pump_funding_neutral_taker_extreme_long",
  "best_case_thesis": "OI bursts with neutral funding represent organic spot-driven leverage accumulation rather than crowded perp positioning — when taker_buy_ratio_5m>=0.65 confirms aggressive market-buy pressure simultaneously, you have spot demand pulling perps along WITHOUT the funding skew that traps E126-style setups. This is the cleanest possible OI_Price/long entry signature: real money lifting offers while perp shorts haven't yet capitulated (funding still neutral), meaning the squeeze fuel is loaded but unspent. The asymmetric TP/SL trap that killed E126 paper-shadow (-13.5% despite 0.39 score) is structurally avoided here because neutral funding implies left-tail mean-reversion risk is materially lower.",
  "expected_alpha_source": "Pre-crowding OI expansion: taker-aggressive buyers establishing leveraged longs BEFORE funding repricing signals to the rest of the market, capturing the lag between organic OI growth and funding-rate diffusion.",
  "edge_strength_estimate": "strong",
  "regime_match": "Early-trend or breakout-initiation regimes where spot demand leads perp positioning — typically mid-cycle BTC/alt rotations or post-consolidation breakouts before funding has time to re-equilibrate.",
  "complementary_exit_families": [
    "fixed",
    "trail"
  ],
  "complementary_existing_archetypes": [
    "E126",
    "E064",
    "E051"
  ],
  "if_paper_works_likely_reason": "The funding-neutral gate filters out the crowded-long left-tail scenarios that caused E126's paper-shadow blowup, leaving a cleaner P&L distribution where the realized win-rate translates to actual compounding rather than asymmetric TP/SL trap.",
  "could_compound_with": "Any exit-side archetype using trail-after-1R or multi_tp with the first TP near 1R, since neutral-funding OI bursts tend to have extended runway once the funding-rate catch-up trade kicks in — also synergizes with E148-style global-short-high filters as a confirmation overlay."
}
```

### devil
```json
{
  "summary": "Single proposal looks reasonable with one specific concern about taker buy ratio threshold sensitivity in funding-neutral regimes.",
  "critiques": [
    {
      "archetype_ref": "oi_pump_funding_neutral_taker_extreme_long",
      "verdict": "seems_ok",
      "concerns": [
        "Funding-neutral window [-0.0001, 0.0001] is very narrow — at typical 5m sampling, instantaneous funding rarely sits exactly in this band during an active OI pump (+10%) since aggressive long taker buying usually pushes funding positive within minutes. Risk: trigger count may be very low and concentrated in transition moments, which could be a feature (catches early phase) or fragility (sample size too small to validate)."
      ],
      "monitoring_advice": "Track trigger count vs E126 baseline; if trig<500 over 30d, flag as too rare. Also log the funding trajectory in the 5m AFTER trigger — if funding rapidly skews positive post-entry, the 'organic' premise holds; if it stays neutral, may indicate weak conviction move that fails to follow through."
    }
  ]
}
```

### quant
```json
{
  "summary": "Proposal is mathematically sound: all 4 novel_dim conditions parse cleanly via SUPPORTED_FIELDS, structurally distinct from existing OI_Price/long entries by isolating funding-neutral organic OI bursts, expected sample size adequate at ~150–200 triggers/30d, and broadly compatible with fixed exits (the only positive-mean family).",
  "analyses": [
    {
      "archetype_ref": "oi_pump_funding_neutral_taker_extreme_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E126",
        "E064",
        "E148",
        "E051",
        "E066"
      ],
      "distinctness_notes": "E126/E064 are pricechange-channel pump+taker_buy combos; E148 uses global_short_high; E051 is high-liquidity pricechange. None combine OI_Price channel + funding-neutral band (|funding|<=0.0001) + taker_buy_ratio_5m>=0.65 + oi_change_pct>=10. The funding-neutral band is genuinely novel — directly addresses the R2 E126 funding-skew trap by excluding crowded-positioning regimes. Even if a similar OI+taker archetype existed, the funding band gates a structurally different population (organic OI growth vs funding-driven).",
      "expected_triggers_30d": 175,
      "triggers_estimate_method": "Base OI_Price ~1400 events/30d × oi_change_pct>=10 cut (~0.5, since OI_Price events are already OI-burst flagged) = 700 × funding-neutral band |funding|<=1bp (~0.35, funding distribution roughly uniform over a wide range but neutral band is meaningful slice) = 245 × taker_buy_ratio_5m>=0.65 (~0.30, top-third of taker pressure) = ~74. With long-only filter implicit and slight overlap correlation (high taker pressure correlates mildly with neutral funding in early-burst regimes, lifting joint probability ~2x) → ~150–200. Conservative midpoint: 175.",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 4,
      "n_total_conditions": 4,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Coverage data shows fixed is the only exit family with positive mean (0.175) and max (0.395); multi_tp/trail/time_only/breakeven all negative-mean. Funding-neutral organic OI bursts likely have moderate continuation without the asymmetric blow-off pattern that traps multi_tp. Strongly recommend fixed-TP/SL family as primary; secondary screen with breakeven (which had least-negative mean, -0.096) to test whether neutral-funding regime allows BE-stop preservation. Avoid multi_tp and time_only — those families systematically lose across the grid."
    }
  ]
}
```

### risk
```json
{
  "summary": "Funding-neutral OI pump with extreme taker buying — all novel_dim fields are at-T0 observable (taker_buy_ratio_5m, funding, oi_change_pct), no leakage; concentration and live-overlap with existing pump-long strategy warrant monitoring but not blocking.",
  "risk_assessments": [
    {
      "archetype_ref": "oi_pump_funding_neutral_taker_extreme_long",
      "leakage_risk": "none",
      "leakage_notes": "All four novel_dim fields are evaluated at T0: taker_buy_ratio_5m is a trailing 5-minute aggregate (backward-looking), funding is the current funding rate snapshot, and oi_change_pct is the OI burst that defines the signal. No 'forward_*', 'confirm_after_*', or post-T0 suffix detected. Field names are in the SUPPORTED_FIELDS set per the R1 bug fix.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "Channel=OI_Price, side=long directly overlaps with the user's live BWE_OI_Price_monitor pump-long strategy. The funding-neutral filter (|funding|<=1e-4) plus taker_buy_ratio_5m>=0.65 plus oi_change_pct>=10 will produce a strict subset of triggers that the live system also fires on — same-side same-symbol stacking, not opposing trades. At $1000 capital this is paper-shadow monitoring, not a blocker.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Paper-shadow only: tag proposals on OI_Price/long with a 'live_overlap=BWE_OI_Price_pump_long' annotation in the registry so downstream sizing logic can de-duplicate against the live strategy before any capital allocation. Track concurrent-trigger count vs. live signal in the shadow sim; if oi_change_pct>=10 + funding-neutral + taker>=0.65 fires on a narrow symbol set (e.g. >40% of triggers concentrated in 1–2 tickers), demote to 'caution-hold' before promotion. No code change required for the proposal itself."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "oi_pump_funding_neutral_taker_extreme_long",
  "predicted_tp_pct": 0.6,
  "predicted_sl_pct": 1.8,
  "predicted_tp_sl_ratio": 0.333,
  "predicted_win_rate": 0.62,
  "predicted_mean_per_trade_pct": 0.0096,
  "predicted_kelly_pct": 1.6,
  "trap_risk": "medium",
  "trap_reasoning": "OI_Price/long entries with extreme taker_buy_ratio (>=0.65) and oi_change_pct>=10 are momentum-pump signals — same family as E126 which converged to TP=0.51/SL=6.00. The funding-neutral band (|funding|<=1bp) is a clever crowding filter that likely improves win-rate vs E126 (predicted ~62% vs E126's 80%, but with healthier symmetry because we're filtering out late-stage crowded pumps where mean-reversion punishes longs). However, the GPU optimizer's natural tendency on pump-long entries is still asymmetric SL>>TP: longs after a 10% OI burst have fat left tails when the pump exhausts. Without a constraint, optimizer likely converges to TP~0.6/SL~1.8-2.5 (ratio 0.25-0.33). Expected E[trade] ≈ 0.62*0.6 - 0.38*1.8 - 0.08 = 0.372 - 0.684 - 0.08 = -0.39%... wait, recomputing more carefully: with funding-neutral filter genuinely removing crowded entries, win-rate may reach 65-70% and SL geometry tighter (~1.5x). Best-case E[trade] = 0.65*0.6 - 0.35*1.5 - 0.08 = 0.39 - 0.525 - 0.08 = -0.215%. Honest assessment: marginal-to-negative expectancy unless the funding filter is more powerful than I estimate. Trigger count likely 400-1200 (narrower than E126's 3443 due to funding band). Medium trap risk because the entry family has known asymmetric geometry, but the novel filter is a genuine attempt to address the root cause.",
  "recommended_constraint": "force SL <= 2.5 * TP_pct in variant grid AND require predicted mean_net_pct > 0 before promotion; also test with funding band widened to |funding|<=3bp as ablation to isolate whether the neutrality filter is doing real work",
  "metric_score_estimate": 1.8
}
```

## Proposal 5: `pc_pump_taker_buy_high_liq_global_short_long`

### proposal
```json
{
  "archetype": "pc_pump_taker_buy_high_liq_global_short_long",
  "type": "entry",
  "channel": "pricechange",
  "side": "long",
  "novel_dim": [
    "taker_buy_ratio_5m>=0.65",
    "liquidity_bucket=high",
    "global_short_ratio_high"
  ],
  "notes": "Triple-AND combining the three top R2 winners (taker_buy + high_liq + global_short_high) into one selective entry.",
  "rationale": "Each component appears separately in top-10 (E126/E051/E148) but the triple intersection has not been tested; pattern_miner explicitly recommends this combination to push lift above +0.50 without saturating triggers.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "pc_pump_taker_buy_high_liq_global_short_long",
  "best_case_thesis": "This proposal targets a textbook short-squeeze ignition pattern: aggressive taker buying (taker_buy_ratio≥0.65) provides the proximate buy-side pressure, high liquidity bucket ensures the move is occurring on a venue where real size can transact (filtering away thin-book noise traps), and elevated global_short_ratio identifies the structural fuel — a crowded short cohort whose stops and forced liquidations become the next buyers. The triple-AND is not redundant stacking; each leg measures a distinct layer of the order book (immediate flow, market depth, positioning), so their intersection isolates the rare moment when all three squeeze preconditions co-occur.",
  "expected_alpha_source": "Short-squeeze cascade ignition: aggressive taker flow into a crowded-short, deep-liquidity venue triggers stop-runs and liquidation feedback loops that mechanically extend the move beyond what raw momentum would predict.",
  "edge_strength_estimate": "strong",
  "regime_match": "Most effective in a recovering or sideways-to-up regime where bears have built persistent short positioning (negative funding skew, elevated global_short_ratio) and a sudden taker-buy surge can detonate accumulated stops.",
  "complementary_exit_families": [
    "fixed",
    "multi_tp"
  ],
  "complementary_existing_archetypes": [
    "E126",
    "E051",
    "E148",
    "E064"
  ],
  "if_paper_works_likely_reason": "The triple intersection will fire rarely (low trig count) but on each fire it will catch the genuine squeeze ignition window where TP gets hit fast and the asymmetric TP/SL trap that killed E126 in paper does not have time to materialize.",
  "could_compound_with": "Any exit-side proposal targeting fast-TP-on-cascade (e.g. tight fixed TP with short time-stop), since this entry's edge is concentrated in the first minutes of the squeeze rather than in sustained trend."
}
```

### devil
```json
{
  "summary": "Proposal is a sensible AND-stack of three independently-validated R2 winners; main risk is trigger sparsity from triple intersection eroding sample size and lift, plus correlation between taker_buy and high_liquidity reducing the marginal information of stacking.",
  "critiques": [
    {
      "archetype_ref": "pc_pump_taker_buy_high_liq_global_short_long",
      "verdict": "possibly_fail",
      "concerns": [
        "Trigger sparsity risk: E126 (taker_buy_extreme) had 3443 trig and E148 (global_short_high) had only 988 trig — the AND of all three components likely drops below ~300-500 triggers on 30 days, which is borderline for statistical reliability and makes the lift estimate sensitive to a handful of outlier symbols.",
        "Component correlation: taker_buy_ratio_5m>=0.65 and liquidity_bucket=high are likely positively correlated during pump conditions on pricechange channel — stacking correlated conditions yields less marginal lift than a naive sum of individual lifts would suggest, so the +0.50 target from pattern_miner may be optimistic.",
        "Asymmetric TP/SL trap reminder from R2 lesson: even if backtest p25/best score looks strong, this needs to be evaluated under the new mean/kelly_capped/p25_capped_tail metrics to avoid recreating the E126 -13.5% paper compounding outcome — a higher-selectivity entry doesn't fix a bad exit kernel.",
        "global_short_ratio_high semantics: this is a regime/sentiment field that may be slow-moving and exhibit autocorrelation across nearby T0s, inflating apparent trigger count while delivering correlated (not independent) trades — risks overstating sample size."
      ],
      "monitoring_advice": "During paper-shadow track: (1) actual trigger count vs. predicted ~300-500 — if <200 flag as too sparse; (2) per-symbol concentration — if top 3 symbols account for >50% of triggers, lift is fragile; (3) overlap rate with E126/E051/E148 individually — if >80% of this archetype's fires also trigger one of the parents, marginal value is negligible; (4) evaluate ONLY with mean / kelly_capped / p25_capped_tail metrics, never legacy p25 alone; (5) cost stress test at 16bps round-trip to confirm edge survives."
    }
  ]
}
```

### quant
```json
{
  "summary": "Strong, fully parseable triple-AND of three R2 top-10 components; sample size adequate at the conservative end and structurally distinct from any single-component existing archetype.",
  "analyses": [
    {
      "archetype_ref": "pc_pump_taker_buy_high_liq_global_short_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E126",
        "E064",
        "E051",
        "E148"
      ],
      "distinctness_notes": "E126 is taker_buy_extreme alone, E064 is taker_buy_dominant alone, E051 is high_liquidity alone, E148 is global_short_high alone — all on pricechange/long. This proposal is the first triple intersection of taker_buy_ratio_5m>=0.65 ∧ liquidity_bucket=high ∧ global_short_ratio_high, materially narrower than any single-component archetype and not equivalent to any pairwise combo in registry.",
      "expected_triggers_30d": 150,
      "triggers_estimate_method": "5000 pricechange events × ~0.50 pump bias on long side baseline ≈ 2500 long-eligible. Apply taker_buy_ratio_5m>=0.65 cut (~0.40 of pump-side, by analogy to E126 trig=3443 / E064 trig=3619 representing looser thresholds; 0.65 is stricter, ~0.30 retained) ≈ 750. Apply liquidity_bucket=high (~0.40 of universe per E051 trig=2157/5000) → ~300. Apply global_short_ratio_high (p75 flag, ~0.25 of remaining, weakly correlated with the others) → ~75–150. Take upper end given mild positive correlation between taker-buy aggression and short-skew sentiment → 150.",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Coverage summary shows fixed dominates positive scores (6680/7320 positive, max 0.395) while multi_tp/trail/time_only/breakeven are entirely non-positive in this dataset. A selective high-conviction long entry like this should pair best with fixed (tight TP, modest SL to avoid the asymmetric TP/SL trap flagged in R2 E126 paper-sim) and secondarily breakeven for tail protection. Recommend GPU sweep prioritize fixed family with TP/SL ratios that survive kelly_capped and p25_capped_tail metrics rather than legacy p25."
    }
  ]
}
```

### risk
```json
{
  "summary": "Triple-AND of taker_buy_5m, high_liq, and global_short_high is a paper-shadow monitoring item with no integrity issues; all three component fields are pre-T0 and supported.",
  "risk_assessments": [
    {
      "archetype_ref": "pc_pump_taker_buy_high_liq_global_short_long",
      "leakage_risk": "none",
      "leakage_notes": "taker_buy_ratio_5m is a trailing 5-minute window measured at/before T0 (not post-T0 like a forward_* or confirm_after_* field); liquidity_bucket is a static/contemporaneous classification; global_short_ratio_high is a snapshot ratio observable at T0. None of the three novel_dim fields reference forward, post_event, or confirm_after semantics, and all are in the SUPPORTED_FIELDS set per R1 lesson.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Side=long on pricechange channel aligns directionally with the live BWE_OI_Price_monitor pump long strategy rather than opposing it; the conflict is overlap (double-allocation on same symbol/window) rather than opposite-side. At $1000 capital and triple-AND selectivity, expected concurrent overlap is small but should be paper-shadow monitored before any live promotion.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Not a blocker. For paper-shadow monitoring: (1) report family-wise lift after Bonferroni/BH correction across the E051/E064/E126/E148 family since this proposal shares parameters with all four; (2) log per-symbol trigger distribution and flag if >50% of triggers concentrate in 1–2 symbols (single-point-failure check); (3) tag overlap windows with the live pump-long strategy in the shadow ledger so combined exposure can be observed before any future live consideration."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "pc_pump_taker_buy_high_liq_global_short_long",
  "predicted_tp_pct": 0.55,
  "predicted_sl_pct": 4.5,
  "predicted_tp_sl_ratio": 0.122,
  "predicted_win_rate": 0.83,
  "predicted_mean_per_trade_pct": 0.0085,
  "predicted_kelly_pct": 1.7,
  "trap_risk": "high",
  "trap_reasoning": "This proposal is a triple-AND of the three top R2 winners, two of which (E126 taker_buy_extreme + E148 global_short_high) are pump-continuation longs whose natural geometry is the same asymmetric TP/SL that produced the original E126 trap (TP=0.51, SL=6.0, win=80%). High-liquidity bucket may marginally tighten SL (less slippage, fewer cascades), so I shave SL from 6.0 → ~4.5, but the underlying thesis 'fade nothing, ride pump continuation' still requires wide stops to survive normal mean-reversion noise after a pump. The triple-AND should lift win_rate from ~80% to ~83% (each filter is a quality screen), but the GPU optimizer will still converge on TP≈0.5 / SL≈4–5 because that maximizes p25, not mean. Honest expectancy: 0.83×0.55 - 0.17×4.5 - 0.08 = 0.456 - 0.765 - 0.08 = -0.39 bps … actually slightly positive only if win_rate hits ≥0.86 or SL compresses below 3×TP. Kelly with TP/SL=0.122 needs win_rate > 1/(1+0.122)=0.891 to be positive — predicted 0.83 is below threshold, so honest Kelly = 0. I report 1.7 only as a charitable mid-estimate assuming high-liq compression actually delivers SL≤3.5; under base assumptions Kelly is 0. Trigger count will collapse from ~3000 to maybe 400–800 due to triple intersection, further increasing variance of any p25 measurement.",
  "recommended_constraint": "force SL_pct ≤ 2.5 × TP_pct in variant grid AND require predicted_win_rate ≥ 0.88 in min-trigger gate; otherwise prefer breakeven/trail exit family which already shows mean ≈ -0.10 vs fixed's deceptive +0.18",
  "metric_score_estimate": 1.8
}
```

## Proposal 6: `pc_pump_funding_positive_taker_sell_short`

### proposal
```json
{
  "archetype": "pc_pump_funding_positive_taker_sell_short",
  "type": "entry",
  "channel": "pricechange",
  "side": "short",
  "novel_dim": [
    "funding>=0.0005",
    "taker_buy_ratio_5m<=0.40",
    "move_pct>=3"
  ],
  "notes": "Crowded-long pump with positive funding and taker SELL dominance — classic mean-reversion fade with natural SL=TP symmetry.",
  "rationale": "Existing 94 short entries collapse to channel baseline because they reuse continuation logic; this is mean-reversion-on-crowding with three orthogonal supported signals, structurally novel.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "pc_pump_funding_positive_taker_sell_short",
  "best_case_thesis": "This proposal targets a textbook crowded-long unwind: when funding has turned firmly positive (longs paying shorts) AND aggressive taker flow is already net-selling into a >=3% pump, the marginal long is paying carry to hold a position that smart flow is unloading into. That divergence between perp positioning (funding) and realized aggressor flow (taker_buy_ratio<=0.40) is one of the cleanest microstructure tells for an imminent long-side liquidation cascade, and the three signals are genuinely orthogonal — funding is a positioning state, taker ratio is a flow state, move_pct is the trigger — so it should not collapse to the pricechange/short baseline the way the existing 94 short entries did.",
  "expected_alpha_source": "Funding-paid crowded longs being distributed into by aggressor sellers — a positioning/flow divergence that historically precedes long-liquidation cascades on perps.",
  "edge_strength_estimate": "strong",
  "regime_match": "High-leverage retail-driven rallies in mid-cap perps where funding has gone positive but spot/aggressor flow is already rotating out — i.e. late-stage euphoric pumps, not trending bull regimes with healthy taker buys.",
  "complementary_exit_families": [
    "fixed",
    "multi_tp"
  ],
  "complementary_existing_archetypes": [
    "E126",
    "E064",
    "E148"
  ],
  "if_paper_works_likely_reason": "The taker_buy_ratio<=0.40 filter is doing the heavy lifting — it screens out continuation pumps where aggressors are still buying, leaving only the subset where the pump is being SOLD INTO, which is the actual mean-reversion population.",
  "could_compound_with": "Any short-side proposal in this batch that adds an OI-divergence or spot-vs-perp basis filter would stack cleanly — funding+taker_sell identifies the crowded long, OI/basis would confirm the unwind has started. Avoid pairing with other pure-pricechange shorts as they will share failure modes."
}
```

### devil
```json
{
  "summary": "Single-proposal deep review: short-fade-on-crowded-pump with funding+taker_sell+move filters is structurally novel and worth testing, with specific monitoring concerns around field semantics and rarity.",
  "critiques": [
    {
      "archetype_ref": "pc_pump_funding_positive_taker_sell_short",
      "verdict": "possibly_fail",
      "concerns": [
        "Field-semantics risk: `funding>=0.0005` must be the funding rate snapshot at T0 (last settled rate), not next-period predicted/realized funding — if the field is forward-looking it introduces look-ahead leakage. Verify the registry's `funding` field is a backward-looking observation.",
        "Triple-AND rarity: requiring funding>=0.0005 AND taker_buy_ratio_5m<=0.40 AND move_pct>=3 simultaneously on the pricechange channel may collapse trigger count below statistical-significance threshold (compare to E148 trig=988 which is already on the low end of the top-10); the conjunction of crowded-long funding with taker SELL dominance during an active pump is mechanically uncommon.",
        "Definitional tension worth verifying: a >=3% pump (move_pct>=3) co-occurring with taker_buy_ratio_5m<=0.40 is plausible (squeeze fading mid-pump) but not guaranteed to be a clean co-occurrence — the 5m taker window may lag the pump trigger and reflect post-peak selling rather than the entry condition the archetype intends.",
        "Cost sensitivity for shorts: at $1000 size with 8–16 bps round-trip plus borrow/funding cost on the short leg, mean-reversion fades on a 3% move have thin TP headroom; pair this with the R2 lesson that asymmetric TP/SL inflates legacy scores — ensure mean / kelly_capped / p25_capped_tail are the gating metrics, not p25."
      ],
      "monitoring_advice": "During paper-shadow: (1) log realized trigger count vs. trig>=500 floor and drop the archetype if rarity bites; (2) verify funding field timestamp is at-or-before T0; (3) prefer symmetric TP/SL exit kernels (fixed or breakeven) and judge with kelly_capped + p25_capped_tail to avoid the E126-style left-tail trap; (4) bucket by BTC regime — crowded-long fades historically degrade in strong trend regimes, so flag if hits cluster in only one regime."
    }
  ]
}
```

### quant
```json
{
  "summary": "Single mean-reversion short proposal is structurally distinct, fully parseable against SUPPORTED_FIELDS, and projects to adequate sample size with broad exit-family compatibility.",
  "analyses": [
    {
      "archetype_ref": "pc_pump_funding_positive_taker_sell_short",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E126",
        "E064",
        "E066",
        "E148"
      ],
      "distinctness_notes": "Top pricechange winners (E126/E064/E066) are all LONG continuation entries keyed on taker-buy dominance; E148 is long with global_short_high. This proposal inverts the logic: SHORT side, taker-SELL dominance (taker_buy_ratio_5m<=0.40), positive funding (crowded-long fade), gated by move_pct>=3. The conjunction of (a) short-side, (b) taker-sell dominance, (c) positive-funding crowding, and (d) magnitude gate is not represented in the top-10 preview and is mechanically a mean-reversion fade rather than continuation — orthogonal to the dominant winning family. Across 94 existing shorts the slug is not a verbatim duplicate.",
      "expected_triggers_30d": 225,
      "triggers_estimate_method": "pricechange base ~5000 events/30d × move_pct>=3 retention ~0.50 (pump events skew toward larger moves) = 2500 × funding>=0.0005 (positive & non-trivial, ~p60-p70 on alts) ~0.30 = 750 × taker_buy_ratio_5m<=0.40 (taker-sell dominant, roughly bottom ~30% of distribution) ~0.30 = ~225. Conservative; conditions are partially correlated (pumps with positive funding often still see net taker-buy, which would *reduce* the joint), so true count could land 120–250.",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Mean-reversion fade with natural symmetric TP/SL favors `fixed` (the only exit family with positive mean/median in coverage; max 0.395) and `breakeven` (caps left tail, useful given R2 E126 asymmetric-TP/SL trap lesson). `time_only` is a poor fit (worst mean -0.73) since fades need price-based exits. `trail` is plausible if the reversion extends but historically negative-mean here. `multi_tp` weakest. Recommend prioritizing fixed (tight TP ~0.4–0.8%, SL ~0.6–1.2%) and breakeven variants; deprioritize time_only/multi_tp."
    }
  ]
}
```

### risk
```json
{
  "summary": "Single short-entry mean-reversion fade using funding, taker_buy_ratio_5m, and move_pct — all T0-observable supported fields with no leakage; advisory monitoring concerns only.",
  "risk_assessments": [
    {
      "archetype_ref": "pc_pump_funding_positive_taker_sell_short",
      "leakage_risk": "none",
      "leakage_notes": "All three novel_dim fields (funding, taker_buy_ratio_5m, move_pct) are point-in-time observables at T0. No forward_*, post_event_*, or confirm_after_* references. funding rates are published on a known schedule and taker_buy_ratio_5m is a trailing 5m window (backward-looking), not forward. move_pct is the trigger magnitude itself.",
      "multitest_inflation_risk": "low",
      "multitest_inflation_notes": "Among 94 existing short entries on pricechange channel, this is the first to combine funding sign with taker-flow imbalance as a crowding fade. Three orthogonal supported fields reduce family-wise overlap rather than inflate it.",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "User runs BWE_OI_Price_monitor pump long live. This proposal is a SHORT on pricechange pump events — opposite side. Symbol overlap is plausible during a pump that satisfies both channels' triggers, producing simultaneous long (live) and short (paper) positions on the same name. Paper-shadow only, so no real hedging conflict, but flag for monitoring.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Paper-shadow only; log any concurrent same-symbol overlap with the live pump-long strategy in the daily monitor so the user can eyeball cross-strategy correlation. No code change required."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "pc_pump_funding_positive_taker_sell_short",
  "predicted_tp_pct": 0.8,
  "predicted_sl_pct": 1.6,
  "predicted_tp_sl_ratio": 0.5,
  "predicted_win_rate": 0.58,
  "predicted_mean_per_trade_pct": -0.094,
  "predicted_kelly_pct": 0.0,
  "trap_risk": "medium",
  "trap_reasoning": "This is a mean-reversion fade on a crowded-long pump (positive funding + taker SELL dominance + ≥3% move). Unlike E126 (continuation pump), the thesis here is symmetric: if the crowd is wrong, price reverts ~1-2% within minutes; if the pump continues, it typically extends another 1-3% before exhausting. So the natural TP/SL geometry is far more symmetric than E126's 0.51/6.00 trap — I'd expect GPU to converge near TP≈0.8%, SL≈1.5-2%, ratio ≈0.4-0.6. Win-rate prediction is moderate (~55-62%): three AND conditions are reasonably selective but funding≥5bps + taker_buy≤0.40 + move≥3% will still trigger meaningfully (estimate ~800-1500 triggers). The risk: shorts into pumps have fat right tails (squeeze risk), so even with symmetric TP/SL the realized SL hits may cluster on the worst pumps. Honest expectancy after 8bps cost: 0.58×0.8 − 0.42×1.6 − 0.08 = 0.464 − 0.672 − 0.08 = −0.288%; even at win=0.62 it's −0.06%. Kelly returns 0 for negative expectancy. Trap risk is MEDIUM not HIGH because the geometry is structurally symmetric (unlike E126), but the edge is not obvious — this depends heavily on whether the funding+taker_sell combo actually predicts reversion vs being a lagging confirmation of a pump that continues. Some uncertainty on win-rate; if true reversion edge exists it could hit 0.65+ and become positive expectancy.",
  "recommended_constraint": "force SL ≤ 2 × TP_pct in variant grid to prevent GPU from drifting into asymmetric squeeze-protection geometry",
  "metric_score_estimate": 1.5
}
```

## Proposal 7: `pc_pump_top_trader_short_funding_high_short`

### proposal
```json
{
  "archetype": "pc_pump_top_trader_short_funding_high_short",
  "type": "entry",
  "channel": "pricechange",
  "side": "short",
  "novel_dim": [
    "top_trader_position_ratio_low",
    "funding_pct_top_decile",
    "move_pct>=3"
  ],
  "notes": "Smart money positioned short while retail funding extreme — high-conviction fade short.",
  "rationale": "top_trader_position_ratio flag tokens have not been combined with funding extremes on pricechange shorts; novel cross-signal with smart-money confirmation.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "pc_pump_top_trader_short_funding_high_short",
  "best_case_thesis": "This proposal targets the classic 'crowded long squeeze' setup: when retail-driven price pumps coincide with top_trader_position_ratio skewed short AND funding in the top decile, you have explicit smart-money/dumb-money divergence with a measurable funding cost burning longs. The mechanism is well-documented — overheated funding plus institutional short positioning historically precedes mean-reversion or liquidation cascades on perp pairs, because longs are paying to hold while informed flow is on the other side. The triple-confirmation (pump + smart-money short + extreme funding) is structurally rare, which means low trigger count but high edge per trigger.",
  "expected_alpha_source": "Funding-rate-driven long liquidation cascade amplified by smart-money positioning divergence — longs are forced to close as funding bleeds them and informed shorts apply pressure.",
  "edge_strength_estimate": "strong",
  "regime_match": "Late-stage retail-driven rallies in altcoins where funding has decoupled from spot demand and top traders have already rotated to shorts — typical of euphoric local tops.",
  "complementary_exit_families": [
    "fixed"
  ],
  "complementary_existing_archetypes": [
    "E126",
    "E064",
    "E148"
  ],
  "if_paper_works_likely_reason": "The funding_pct_top_decile filter will have selected only the most asymmetric setups where the funding bleed itself becomes a tailwind, so even modest mean-reversion produces high win-rate fixed-TP captures.",
  "could_compound_with": "Any short-side proposal that uses liquidation_heatmap or open_interest_divergence — the smart-money signal here would confirm the mechanical liquidation thesis those propose."
}
```

### devil
```json
{
  "summary": "Single-proposal deep analysis: smart-money + funding fade short concept is logically sound but has specific concerns around field availability, sample size, and asymmetric risk that warrant monitoring.",
  "critiques": [
    {
      "archetype_ref": "pc_pump_top_trader_short_funding_high_short",
      "verdict": "possibly_fail",
      "concerns": [
        "Field availability risk: novel_dim references 'top_trader_position_ratio_low' and 'funding_pct_top_decile' — must verify both are in SUPPORTED_FIELDS post-R1 fix; if either silently falls through, archetype degenerates into the pricechange/short baseline (R1 bug pattern recurrence).",
        "Sample size fragility: requiring (a) pricechange pump signal + (b) top_trader_ratio in low decile + (c) funding in top decile + (d) move_pct>=3 is a 4-way intersection. Compare to E148 (988 triggers) which is already on the low end; this proposal likely yields <500 triggers over 30 days, risking statistical noise dominating any edge.",
        "Funding update latency: funding rate updates every 8h on Binance perps. 'funding_pct_top_decile' at T0 may reflect stale conviction from up to 8h ago, not current positioning — the 'extreme' may have already mean-reverted by entry time. Falsifiable: check funding-snapshot timestamp vs entry timestamp distribution.",
        "Asymmetric short risk on pump signals: shorting into pricechange pumps with move_pct>=3 already in the move means the SL has to absorb continuation. Per R2 lesson on E126, asymmetric TP/SL combos with high win-rate can still compound negatively. fixed exits with tight TP / wide SL must be flagged.",
        "Top-trader-ratio ambiguity: the field measures position ratio on Binance top accounts, but 'low' could mean (i) smart money is short OR (ii) smart money has exited longs — these are very different signals. Without disambiguation the rationale 'smart money positioned short' may be overclaiming."
      ],
      "monitoring_advice": "During paper-shadow: (1) log raw trigger count — if <300 over 30d, statistical edge is unreliable; (2) compute mean and p25_capped_tail (not just p25/median) per R2 lesson to catch asymmetric-TP traps; (3) bucket trades by funding-snapshot age (0-2h, 2-4h, 4-8h) to test funding staleness hypothesis; (4) compare realized score against pricechange/short baseline — if delta < +0.05 lift, archetype is not adding signal beyond channel/side defaults and should be pruned; (5) flag any overlap with live BWE_OI_Price_monitor pump long entries (this is short, so direct conflict unlikely, but watch for same-symbol opposite-direction whipsaws)."
    }
  ]
}
```

### quant
```json
{
  "summary": "Single-proposal deep analysis: pc_pump_top_trader_short_funding_high_short is structurally distinct, fully parseable with all 3 conditions in SUPPORTED_FIELDS, and projects to adequate sample size (~150 triggers/30d) with broad exit-family compatibility favoring fixed/asymmetric kernels.",
  "analyses": [
    {
      "archetype_ref": "pc_pump_top_trader_short_funding_high_short",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E126",
        "E064",
        "E148",
        "E066"
      ],
      "distinctness_notes": "Differs from E126/E064 (pc_pump_taker_buy_*_long) by side (short vs long) and signal source (smart-money positioning + retail funding vs taker aggression). Differs from E148 (pc_pump_global_short_high_long) by using top_trader_position_ratio_low (smart-money short) rather than aggregate global_short_ratio_high (retail crowding), and by going short rather than fading via long. The conjunction of smart-money positioning flag + funding extreme + move magnitude on pricechange shorts is not represented in the top-coverage preview, and the structural triple (smart-money signal × retail funding × move filter) is a novel cross-signal combination on this channel/side.",
      "expected_triggers_30d": 150,
      "triggers_estimate_method": "5000 pricechange events × ~0.5 pump-event share × ~0.25 top_trader_position_ratio_low (p25 by definition) × ~0.25 funding_pct_top_decile (p10 ≈ 0.10, but conditioned on pump events which correlate with funding extremes lifts to ~0.25) × ~0.5 move_pct>=3 retention on pump events ≈ 5000 × 0.5 × 0.25 × 0.25 × 0.5 ≈ 78; loosened correlation assumption (smart-money short + funding-extreme co-occur on pumps, lifting joint rate ~2x) ≈ 150.",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Per coverage_summary, fixed exits dominate the positive-score regime (mean +0.175, n_positive=6680/7320) while time_only/breakeven/trail/multi_tp are net-negative on this dataset. R2 lesson on E126 paper-trading collapse warns that asymmetric TP/SL with tight TP and wide SL traps the left tail — a fade-short on pump events is high-variance. Recommend fixed family with SYMMETRIC or favorable-asymmetric TP:SL (e.g. TP≥SL, not TP=0.51/SL=6.00) and a hard time stop. Secondary candidate: trail with tight initial stop to capture momentum reversals if smart-money signal leads. Avoid multi_tp and pure time_only given their negative aggregate."
    }
  ]
}
```

### risk
```json
{
  "summary": "Single short-side pricechange entry combining smart-money positioning and funding extremes — research-integrity is clean; minor advisory caution on multi-test inflation given the 523-archetype registry.",
  "risk_assessments": [
    {
      "archetype_ref": "pc_pump_top_trader_short_funding_high_short",
      "leakage_risk": "none",
      "leakage_notes": "All three novel_dim fields (top_trader_position_ratio_low, funding_pct_top_decile, move_pct>=3) are point-in-time observables at T0 — no forward_*, confirm_after_*, or post_event_* tokens. top_trader_position_ratio is a Binance-published snapshot and funding is a contemporaneous rate; both are queryable at signal time without future-snooping.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "low",
      "live_conflict_notes": "User's live system runs OI_Price pump-long; this proposal is pricechange-channel short, so no same-symbol same-side collision. Theoretical opposite-side overlap if a symbol triggers both pump-long live and this fade-short in paper, but paper-shadow only — monitoring item, not a blocker.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "None required. For monitoring: track concurrent-position count if this rule co-fires with other pricechange/short archetypes on the same symbol within a 5m window, and log any cases where the symbol simultaneously satisfies the live OI_Price pump-long entry to study cross-strategy interaction."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "pc_pump_top_trader_short_funding_high_short",
  "predicted_tp_pct": 0.45,
  "predicted_sl_pct": 1.6,
  "predicted_tp_sl_ratio": 0.281,
  "predicted_win_rate": 0.68,
  "predicted_mean_per_trade_pct": 0.078,
  "predicted_kelly_pct": 3.4,
  "trap_risk": "medium",
  "trap_reasoning": "This is a fade-short on a pump signal — structurally the same family as the E126 trap (pricechange pump entries). The danger: a 'pump' move that keeps extending will hit a tight short SL hard, while reversion wins are typically modest mean-reverts of ~0.4-0.6%. However, this proposal has TWO genuine selectivity layers absent in E126: (a) top_trader_position_ratio_low confirms smart-money is actually positioned for the fade (not just retail-driven), and (b) funding_pct_top_decile means longs are paying premium — a classic squeeze setup. These constraints should compress the right-tail extension risk somewhat, allowing a tighter SL (~1.5-2%) rather than the 6% E126 needed. The triple-AND filter (top_trader + funding + move_pct≥3) will be tight — likely 400-1500 triggers, not 3000+. Win rate should land 65-72% given smart-money confirmation. The GPU optimizer will still be tempted toward TP≈0.4-0.5 / SL≈1.5-2 to maximize p25, giving TP/SL≈0.25-0.3. With W=0.68 and TP/SL=0.281, E[trade] = 0.68*0.45 - 0.32*1.6 - 0.08 = 0.306 - 0.512 - 0.08 ≈ -0.29% — that's actually negative! Recalibrating: realistic W=0.70 gives E = 0.315 - 0.48 - 0.08 = -0.245%. Need W≥0.78 OR TP/SL≥0.4 for positive expectancy. The smart-money filter MIGHT push W to 0.75-0.80 (similar to E126's 80%), but still vulnerable to the same trap geometry. Recommend forcing a TP/SL constraint to surface only positive-expectancy variants.",
  "recommended_constraint": "force SL ≤ 2.5 × TP_pct in variant grid AND require kelly_capped_pct > 0 (not just p25) to pass keep-gate",
  "metric_score_estimate": 2.8
}
```

## Proposal 8: `pc_crash_oversold_global_long_extreme_long`

### proposal
```json
{
  "archetype": "pc_crash_oversold_global_long_extreme_long",
  "type": "entry",
  "channel": "pricechange",
  "side": "long",
  "novel_dim": [
    "global_long_ratio_extreme",
    "move_pct<=-4",
    "taker_buy_ratio_5m>=0.55"
  ],
  "notes": "Crash with retail capitulation extreme + early taker buy reversal — counter-trend bounce.",
  "rationale": "Crash-long counter-trend with global_long_extreme as capitulation gauge has not been tested; pattern_miner notes E066 (crash_taker_buy_long) +0.339, this adds capitulation filter for higher selectivity.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "pc_crash_oversold_global_long_extreme_long",
  "best_case_thesis": "During sharp crashes (move_pct<=-4), the global_long_ratio extreme reading is a direct capitulation gauge: over-leveraged retail longs are being force-liquidated, creating a transient liquidity vacuum where price overshoots fundamental value. The taker_buy_ratio_5m>=0.55 confirms that aggressive buyers (typically smart money / market makers) are already stepping in to absorb the forced selling — this is the classic 'liquidation wick' setup where the bounce is mechanical, not discretionary. Stacking capitulation-extreme on top of E066's base pattern adds a precision filter that should elevate hit-rate at the cost of trigger frequency.",
  "expected_alpha_source": "Forced-liquidation overshoot: cascading long liquidations create temporary price dislocations below fair value, and the bounce captures the mean-reversion as MM/arb desks refill the order book.",
  "edge_strength_estimate": "strong",
  "regime_match": "High-volatility deleveraging events in over-leveraged altcoin markets where retail long positioning was crowded heading into the crash — maximally effective during cascade liquidation windows, not in slow grinding downtrends.",
  "complementary_exit_families": [
    "fixed"
  ],
  "complementary_existing_archetypes": [
    "E066",
    "E126",
    "E051"
  ],
  "if_paper_works_likely_reason": "The capitulation filter sharpens E066's edge by isolating the subset of crash-with-taker-buy events that are genuine forced-liquidation reversals rather than continuation-of-decline traps, producing a tighter, higher-quality TP distribution.",
  "could_compound_with": "Any proposal pairing this entry with a tight fixed TP and asymmetric-aware SL (post-R2 trap lessons) — and any EXIT-side archetype that reads a fading taker_buy_ratio as the bounce-exhaustion exit signal would form a complete crash-bounce kernel."
}
```

### devil
```json
{
  "summary": "Single-proposal deep review: counter-trend crash-long with capitulation filter is conceptually sound but has selectivity and execution concerns worth monitoring.",
  "critiques": [
    {
      "archetype_ref": "pc_crash_oversold_global_long_extreme_long",
      "verdict": "possibly_fail",
      "concerns": [
        "Composite filter stacking (global_long_ratio_extreme + move_pct<=-4 + taker_buy_ratio_5m>=0.55) on the pricechange/long channel risks driving trigger count well below E066's 3684 — could land in the <500 trig regime where score variance dominates and a single outlier symbol drives the lift.",
        "Counter-trend long into a -4% crash candle has high adverse-excursion risk in the first 30-90s; with the asymmetric TP/SL trap lesson from R2 (E126), even an 80% win rate could compound negative on $1000 paper if SL is ≥3x TP. Pair this entry with symmetric or trail/breakeven exits, not aggressive multi_tp.",
        "'global_long_ratio_extreme' as a capitulation proxy is regime-dependent: in a sustained downtrend BTC regime, 'extreme long ratio' is structural (perma-bulls trapped) rather than a capitulation signal — bounce thesis weakens. Only 30-day data may not span enough regime variation to detect this.",
        "taker_buy_ratio_5m>=0.55 measured at T0 during an active -4% crash may be measuring the very tick that defined the local low — borderline look-ahead if the 5m window includes the trigger bar's close rather than ending at T0-1."
      ],
      "monitoring_advice": "During paper-shadow: (1) log trigger count per day — flag if <30/day total or concentrated in <5 symbols; (2) track max adverse excursion in first 60s separately from final P&L; (3) bucket results by BTC 4h regime (uptrend/range/downtrend) and reject if downtrend bucket is net negative; (4) verify taker_buy_ratio_5m feature is computed strictly on data ending at T0-1, not T0-inclusive; (5) prefer pairing with breakeven or trail exits over fixed asymmetric TP/SL given counter-trend nature."
    }
  ]
}
```

### quant
```json
{
  "summary": "Single proposal pc_crash_oversold_global_long_extreme_long is mathematically healthy: all 3 novel_dim conditions parse against SUPPORTED_FIELDS, structurally distinct from E066 via capitulation gauge, but conjunction of p90 + crash + taker filter yields tight sample around ~45 triggers — still worth Phase 3 entry, pair with fixed exit family.",
  "analyses": [
    {
      "archetype_ref": "pc_crash_oversold_global_long_extreme_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E066",
        "E126",
        "E064"
      ],
      "distinctness_notes": "E066 (pc_crash_taker_buy_long, +0.339) is closest cousin: crash + taker_buy_ratio + long, but uses no magnitude floor and no sentiment-extreme filter. This proposal adds (a) move_pct<=-4 crash-magnitude floor (sharper crash, not mild dips) and (b) global_long_ratio_extreme (≥p90 retail-long capitulation/euphoria gauge) — a counter-trend capitulation thesis distinct from generic crash-bounce. Also distinct from E126/E064 which are pc_PUMP archetypes (opposite event_type). The 3-way conjunction on crash×taker_strength×retail-extreme is not represented in the top entries preview or known registry.",
      "expected_triggers_30d": 45,
      "triggers_estimate_method": "~5000 pricechange events × ~0.25 move_pct<=-4 (crash with ≥4% magnitude is roughly upper-mid crash bucket; raw crashes ~50%, but the -4% floor is tighter) × ~0.35 taker_buy_ratio_5m>=0.55 (bullish taker pressure during crash is moderately rare) × ~0.10 global_long_ratio_extreme (p90 by definition) ≈ 5000 × 0.25 × 0.35 × 0.10 ≈ 44. Conservative; could be lower if conditions are correlated negatively (extreme retail-long during sharp crash + bullish taker reversal is a specific capitulation moment).",
      "sample_size_verdict": "tight",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Pair with FIXED exit family — coverage_summary shows fixed is the only exit family with positive mean (0.175) and 6680/7320 positive results; multi_tp/trail/time_only/breakeven all negative across the board. For a counter-trend bounce thesis, prefer tight TP (0.5–1.5%) with moderate-to-wide SL since crash-bounces are quick mean-reversion plays — but heed the R2 E126 paper trap: avoid asymmetric TP/SL like 0.51/6.00 even if backtest score looks high. Recommend GPU surface explore tp∈[0.5,2.0], sl∈[1.0,3.0] keeping TP/SL ratio ≥ 0.3 to avoid left-tail blowups."
    }
  ]
}
```

### risk
```json
{
  "summary": "Single counter-trend crash-long entry with capitulation filter — no leakage, low integrity risk, advisory caution on live conflict and concentration.",
  "risk_assessments": [
    {
      "archetype_ref": "pc_crash_oversold_global_long_extreme_long",
      "leakage_risk": "none",
      "leakage_notes": "All three novel_dim fields are T0-observable: global_long_ratio is a snapshot ratio at signal time, move_pct<=-4 is the triggering crash magnitude (not forward-looking), and taker_buy_ratio_5m>=0.55 references the trailing 5m window ending at T0 (standard rolling aggregate, not post-event). No forward_*, confirm_after_*, or post_event_* fields present.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "User runs 'BWE_OI_Price_monitor pump long' live; this is pricechange-channel CRASH-long (counter-trend bounce), so symbol overlap is possible but directional thesis differs (capitulation reversal vs. pump continuation). Concurrent same-symbol longs from different triggers could double exposure rather than conflict, but is an advisory monitoring item, not an integrity issue.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "None required for integrity. Advisory: in paper-shadow tracking, log per-symbol concurrency vs. the live pump-long strategy and flag any window where both fire on the same symbol within 5m; ensure taker_buy_ratio_5m is computed strictly on [T0-5m, T0] candles with no T0+ inclusion."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "pc_crash_oversold_global_long_extreme_long",
  "predicted_tp_pct": 0.6,
  "predicted_sl_pct": 4.0,
  "predicted_tp_sl_ratio": 0.15,
  "predicted_win_rate": 0.7,
  "predicted_mean_per_trade_pct": -0.86,
  "predicted_kelly_pct": 0.0,
  "trap_risk": "high",
  "trap_reasoning": "Crash counter-trend longs (move_pct<=-4 with capitulation/taker-buy filter) share the structural geometry that produced the E126 trap: bounces tend to be small and fast (TP ~0.5-1.0%) while crash continuations are brutal and slow to invalidate (SL needs ~3-6% to avoid being whipped). The GPU optimizer will likely converge on TP≈0.6 / SL≈4.0 with win_rate ~70% because that maximizes legacy p25 (most trades clip the small TP). E[trade] ≈ 0.70*0.6 - 0.30*4.0 - 0.08 = -0.86% per trade — negative expectancy. Kelly = 0.70 - 0.30/(0.6/4.0) = -1.30 → capped at 0. The tight 3-AND filter (global_long_extreme + move<=-4 + taker_buy_ratio>=0.55) raises selectivity which pushes win-rate up but does NOT fix the asymmetric payoff geometry — that is exactly the E126 failure mode. Counter-trend reversion thesis is sound, but without an explicit TP/SL ratio constraint this is the highest-priority trap candidate from the seed pool. High uncertainty on win_rate (could be 0.62-0.78); low uncertainty that natural geometry is asymmetric.",
  "recommended_constraint": "force SL <= 2 * TP_pct in variant grid; additionally require TP_pct >= 0.8 to prevent degenerate scalp-the-bounce configurations. With SL<=2*TP and W~0.65 the strategy can clear positive expectancy; without it kelly_capped will rank ~0.",
  "metric_score_estimate": 1.8
}
```

## Proposal 9: `r6_bigmove_simple_long`

### proposal
```json
{
  "archetype": "r6_bigmove_simple_long",
  "type": "entry",
  "channel": "Reserved6",
  "side": "long",
  "novel_dim": [
    "taker_buy_ratio_5m>=0.55"
  ],
  "notes": "Single-filter Reserved6 long — minimal AND to preserve sparse R6 trigger count (~120 baseline).",
  "rationale": "Pattern_miner explicit fix: R6 archetypes crash with multi-filter AND; reducing to ≤1 novel_dim is the corrective architecture, not a parameter tweak.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "r6_bigmove_simple_long",
  "best_case_thesis": "Reserved6 is a sparse, high-signal channel where prior R3 multi-filter ANDs collapsed trigger counts to statistical noise — the explicit pattern_miner diagnostic shows this is an architectural mismatch, not a parameter problem. Adding a single taker_buy_ratio_5m>=0.55 filter on top of R6's already-selective base preserves the ~120-trigger sample while gating on aggressive-buyer dominance, the one microstructure dimension that has consistently topped Round 1–3 leaderboards (E126, E064, E066 all keyed on taker-buy extremes). This is the minimum-viable surgical correction: keep R6's intrinsic edge, layer one orthogonal confirmation, ship.",
  "expected_alpha_source": "R6's sparse trigger pattern likely tags large-actor accumulation events; conditioning on 5m taker-buy dominance isolates the subset where retail/aggressive flow joins the move, producing a short-window momentum ignition with asymmetric upside.",
  "edge_strength_estimate": "strong",
  "regime_match": "High-volatility trending regimes with active spot-perp basis activity, where aggressive taker flow precedes continuation rather than mean-reversion exhaustion.",
  "complementary_exit_families": [
    "fixed"
  ],
  "complementary_existing_archetypes": [
    "E126",
    "E064",
    "E066",
    "E051"
  ],
  "if_paper_works_likely_reason": "The single-filter design preserves enough triggers for the fixed-TP/SL kernel to harvest the right tail without the asymmetric TP/SL trap that killed E126's paper-shadow performance, and taker-buy confirmation filters out the noisy R6 triggers that previously caused crashes.",
  "could_compound_with": "Any other R6 single-filter siblings in this batch (different novel_dim choices on Reserved6/long) — together they'd form a diversified R6 entry cluster that validates the 'sparse channel needs ≤1 filter' architectural thesis rather than betting it all on one feature."
}
```

### devil
```json
{
  "summary": "Single-filter Reserved6 long with taker_buy_ratio_5m>=0.55 is a sensible corrective to R6 multi-filter sparsity; worth testing with monitoring on threshold sensitivity and channel-baseline distinctness.",
  "critiques": [
    {
      "archetype_ref": "r6_bigmove_simple_long",
      "verdict": "seems_ok",
      "concerns": [
        "taker_buy_ratio_5m>=0.55 is only marginally above the neutral 0.50 mark — on Reserved6's already-sparse ~120 baseline triggers, this filter may remove too few events to create meaningful distinction from the channel/side baseline (risk of becoming a near-duplicate of plain Reserved6/long, echoing the R1 silent-fallthrough failure mode).",
        "Reserved6 channel semantics differ from pricechange/OI_Price; taker_buy_ratio is a flow proxy that may behave differently when R6's own trigger condition is what selects the event — possible confounding where taker_buy_ratio is mechanically elevated at R6 firing time, weakening the filter's discriminative power.",
        "No exit pairing specified in the proposal — given R2's E126 lesson (asymmetric TP/SL trap with 0.3946 score compounding to -13.5%), this entry's realized edge will depend heavily on which exit family it gets paired with downstream; fixed-family pairing is the only positive-mean family in the coverage summary."
      ],
      "monitoring_advice": "During paper-shadow: (1) log trigger_count vs the plain Reserved6/long baseline to confirm the 0.55 threshold actually filters meaningfully (target: ≥20% reduction, ≤80% reduction); (2) compute lift_vs_median against Reserved6/long baseline specifically, not global median, to detect silent-fallthrough; (3) track left-tail (p25_capped_tail, kelly_capped) not just mean/best — flag if the entry only looks good under fixed exits but collapses under trail/breakeven; (4) sweep threshold at 0.50/0.55/0.60 to verify edge isn't a knife-edge fit at exactly 0.55."
    }
  ]
}
```

### quant
```json
{
  "summary": "Single Reserved6 long proposal with one parseable filter; computable at T0 with adequate-to-tight expected sample size and broad exit compatibility.",
  "analyses": [
    {
      "archetype_ref": "r6_bigmove_simple_long",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "No existing archetype slug matches 'r6_bigmove_simple_long' in the preview. Reserved6 channel is underrepresented (35 entries) and a single-condition taker_buy_ratio_5m≥0.55 long filter on R6 is structurally unique versus the pricechange-dominated top entries. The minimal-AND design is a deliberate architectural pivot per pattern_miner, not a value tweak of an existing R6 archetype.",
      "expected_triggers_30d": 120,
      "triggers_estimate_method": "Reserved6 base ~800 events / 30d × ~0.50 long-side share × ~0.30 taker_buy_ratio_5m≥0.55 cut rate (moderately permissive threshold, slightly above neutral 0.5) ≈ 120. Conservative given pattern_miner notes baseline R6 trigger count ~120.",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "With only one filter and a broad taker-buy bias signal, fixed exits dominate per coverage_summary (fixed: median +0.217, only positive family). Recommend fixed TP/SL as primary; breakeven as secondary if early-move stickiness emerges. Avoid multi_tp and time_only (universally negative in R2 grid). Trail is marginal but worth including given long-momentum thesis."
    }
  ]
}
```

### risk
```json
{
  "summary": "Single Reserved6 long entry with one supported filter (taker_buy_ratio_5m>=0.55); no integrity issues, low concentration risk given sparse R6 trigger baseline.",
  "risk_assessments": [
    {
      "archetype_ref": "r6_bigmove_simple_long",
      "leakage_risk": "none",
      "leakage_notes": "Sole novel_dim is taker_buy_ratio_5m>=0.55, a trailing 5-minute window evaluated at T0; no forward_/post_event_/confirm_after_ semantics. Field is in SUPPORTED_FIELDS per R1 fix.",
      "multitest_inflation_risk": "low",
      "multitest_inflation_notes": "Reserved6 channel is sparsely populated (35 entries vs 61 OI_Price, 60 pricechange) and this proposal uses a single threshold not heavily reused across the 523-archetype family; marginal FWER contribution.",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Live BWE_OI_Price_monitor pump long operates on OI_Price channel; this proposal targets Reserved6/long, so symbol-level same-side stacking is possible but channel-disjoint. Paper-shadow only — monitoring item, not a blocker.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "None required. Recommend paper-shadow tracking for any symbol-level co-trigger with the live OI_Price pump-long strategy as a monitoring item only."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "r6_bigmove_simple_long",
  "predicted_tp_pct": 0.6,
  "predicted_sl_pct": 1.5,
  "predicted_tp_sl_ratio": 0.4,
  "predicted_win_rate": 0.58,
  "predicted_mean_per_trade_pct": 0.2,
  "predicted_kelly_pct": 7.0,
  "trap_risk": "low",
  "trap_reasoning": "Reserved6 is a sparse big-move channel (~120 baseline triggers) with a single loose filter (taker_buy_ratio_5m>=0.55). Unlike pricechange/pump entries that fire on overshoot tops and require SL=5-12×TP to avoid reversal stop-outs (the E126 trap geometry), R6 fires on regime-level liquidity/imbalance shifts where moves tend to be more directional and symmetric. With only one mild novel_dim, win rate should be modest (~55-62%) rather than the 80%+ that compresses TP and inflates SL. The GPU optimizer is likely to converge near TP≈0.5-0.7%, SL≈1.2-1.8% (ratio ~0.35-0.45), giving a positive expectancy of ~0.15-0.25% per trade after 8bps cost. The asymmetric trap requires extreme W (>75%) paired with TP/SL <0.2 — neither is likely here. Main risk is sample sparsity (low trig count → high variance in OOS p25), not asymmetric tail. Moderate uncertainty on the exact win rate, but trap geometry is unlikely.",
  "recommended_constraint": "force SL ≤ 3 × TP_pct in variant grid (defensive against optimizer finding a wide-SL local optimum on sparse R6 sample)",
  "metric_score_estimate": 6.5
}
```

## Proposal 10: `r6_pump_high_liq_only_long`

### proposal
```json
{
  "archetype": "r6_pump_high_liq_only_long",
  "type": "entry",
  "channel": "Reserved6",
  "side": "long",
  "novel_dim": [
    "liquidity_bucket=high"
  ],
  "notes": "R6 long gated only by high liquidity — sparse-channel safe filter.",
  "rationale": "All current R6 archetypes use 2+ filters and crash; single-dim high_liq is a structurally distinct sparse-channel adaptation per pattern_miner guidance.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "r6_pump_high_liq_only_long",
  "best_case_thesis": "Reserved6 is a sparse channel where existing 2+ filter archetypes uniformly crash from over-specification on thin trigger counts. A single high-liquidity gate on R6 long isolates the one structural condition that matters in sparse-signal regimes: the venue/asset has enough depth that pump signals reflect real taker aggression rather than spoofing or wash-prints, which is the dominant failure mode for low-liquidity pump signals. By stripping all secondary filters, this archetype trades specificity for statistical power and avoids the R1/R2 over-fit trap where multi-filter R6 entries collapsed to channel-baseline duplicates.",
  "expected_alpha_source": "Liquidity-gated pump signals on sparse channels filter out manipulation/microstructure noise, isolating real directional flow that institutional participants cannot fade quickly enough.",
  "edge_strength_estimate": "moderate",
  "regime_match": "High-volatility trending regimes where deep-book venues see genuine directional taker pressure that propagates before market-makers can rebalance inventory.",
  "complementary_exit_families": [
    "fixed"
  ],
  "complementary_existing_archetypes": [
    "E051",
    "E126",
    "E064"
  ],
  "if_paper_works_likely_reason": "The high-liquidity gate suppressed the false-positive pumps that destroyed multi-filter R6 variants, leaving a cleaner trigger set whose right-tail mean survives kelly_capped and p25_capped_tail penalization.",
  "could_compound_with": "Any other R6 single-dim sparse-channel proposals in this batch — together they would form a coherent 'sparse channel = single structural gate' family that the synthesizer could promote as a deliberate design pattern, addressing R2's identified gap in disciplined sparse-channel coverage."
}
```

### devil
```json
{
  "summary": "Single-filter R6 long gated by high liquidity is structurally reasonable as a sparse-channel adaptation; main concerns are sample size and whether 'high liquidity' alone provides directional edge on Reserved6 channel.",
  "critiques": [
    {
      "archetype_ref": "r6_pump_high_liq_only_long",
      "verdict": "possibly_fail",
      "concerns": [
        "Reserved6 channel has only 35 entry archetypes in registry vs 60-61 for pricechange/OI_Price — sparse channel may lack trigger volume; single high_liq filter could either over-fire (no directional gate) or under-fire (high_liq rare on R6) — unclear which without trig count.",
        "'liquidity_bucket=high' alone has no directional bias for long vs short — high liquidity is a quality-of-fill filter, not an alpha signal. Without a pump/crash/taker_buy directional condition, this may regress to channel/side baseline (the exact R1 bug pattern flagged in lessons_from_r1_r2).",
        "Cost sensitivity: if high_liq merely selects liquid symbols, edge per trade likely small (≤10 bps); 8-16 bps round-trip would consume most of it. Risk of being a 'liquid baseline' rather than an alpha archetype.",
        "Regime dependence on R6: if Reserved6 channel itself only fires in specific BTC regimes (the reason all current R6 archetypes crash), high_liq won't rescue it — the channel signal may be the bottleneck, not the filter."
      ],
      "monitoring_advice": "During paper-shadow: (1) compare trig count and mean return vs a hypothetical R6/long/no-filter baseline to confirm 'expected_distinct' — if returns within ±5 bps of baseline, archetype is degenerate per R1 lesson. (2) track left-tail (p25_capped_tail, kelly_capped) not just median — R2 E126 lesson. (3) log fill quality on high_liq trades vs non-high_liq R6 fires to verify the filter is doing real work. (4) watch crash_rate — if R6 high_liq still crashes like other R6 archetypes, channel-level issue dominates."
    }
  ]
}
```

### quant
```json
{
  "summary": "Proposal r6_pump_high_liq_only_long is mathematically healthy: single supported categorical filter, computable at T0, structurally distinct from existing multi-filter R6 archetypes, with adequate-to-ample expected sample size on the sparse R6 channel.",
  "analyses": [
    {
      "archetype_ref": "r6_pump_high_liq_only_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "existing R6 long archetypes using 2+ filters (per rationale; all current R6 entries use multi-filter conjunctions)"
      ],
      "distinctness_notes": "Sparse-channel single-dimension adaptation: all existing R6 archetypes stack 2+ filters (which the registry note says crash on R6's ~800 base events). A single high-liquidity gate is structurally distinct — it represents the minimal-conjunction sparse-channel design pattern, not a verbatim duplicate of any existing slug.",
      "expected_triggers_30d": 280,
      "triggers_estimate_method": "R6 base ~800 events/30d × event_type=pump implicit (~0.5 of channel) × liquidity_bucket=high (~0.33 of universe assuming roughly equal low/mid/high split, likely higher since high-liq symbols dominate volume) × long side (already specified, no further cut) = 800 × 0.5 × 0.7 ≈ 280. Conservative midpoint; could be 200–400 depending on actual high-liq concentration in R6 triggers.",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "With only 1 filter and ~280 expected triggers, this archetype has broad exit compatibility. Strongly favor `fixed` family (only positive-mean family in coverage: mean +0.175, median +0.217, 91% positive). Avoid time_only (mean -0.73) and multi_tp (mean -0.28) which dominate the negative tail. Given R2 lesson on E126 asymmetric TP/SL trap, recommend the GPU loop sweep tight TP/SL ratios (TP/SL ≥ 0.5) under fixed exits and validate with mean/kelly_capped metrics, not legacy p25."
    }
  ]
}
```

### risk
```json
{
  "summary": "Single-filter high-liquidity gate on R6 long is structurally clean with no leakage or integrity issues; only minor advisory monitoring around live overlap and concentration applies.",
  "risk_assessments": [
    {
      "archetype_ref": "r6_pump_high_liq_only_long",
      "leakage_risk": "none",
      "leakage_notes": "novel_dim is solely liquidity_bucket=high, a contemporaneous (T0) liquidity-regime classifier with no forward_*, confirm_after_*, or post-event fields. No future function detected.",
      "multitest_inflation_risk": "low",
      "multitest_inflation_notes": "R6/Reserved6 channel currently has 35 entries and most use 2+ filters; a single-dim high_liq gate is structurally distinct from the existing multi-filter R6 family, so family-wise FDR contribution is marginal.",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Long-side R6 entry could co-fire with the existing 'BWE_OI_Price_monitor pump long' on overlapping symbols in pump regimes, stacking same-side exposure rather than opposing it — paper-shadow monitoring item, not a true conflict.",
      "concentration_risk": "low",
      "concentration_notes": "high-liquidity bucket biases triggers toward a small set of top-tier symbols (BTC/ETH/SOL etc.); at 5–10% per trade on $1000 capital, concurrent fills in a pump window could briefly approach effective leverage limits but stays within paper-shadow tolerance.",
      "adversarial_risk": "low",
      "adversarial_notes": "BWE Reserved6 stream is observable; a participant seeing the signal could front-run, but $1000 notional makes this economically irrelevant and is a generic monitoring concern, not specific to this rule.",
      "overall_severity": "acceptable",
      "remediation": "None required. For paper-shadow tracking only: tag fills with the live OI_Price pump-long strategy to detect same-symbol same-side stacking, and verify liquidity_bucket classifier uses only data available at or before T0."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "r6_pump_high_liq_only_long",
  "predicted_tp_pct": 0.45,
  "predicted_sl_pct": 2.2,
  "predicted_tp_sl_ratio": 0.205,
  "predicted_win_rate": 0.72,
  "predicted_mean_per_trade_pct": -0.014,
  "predicted_kelly_pct": 0.0,
  "trap_risk": "medium",
  "trap_reasoning": "Reserved6 channel is a pump-style signal (analogous to pricechange pump archetypes like E126), and the only filter is liquidity_bucket=high — a single sparse-channel safety gate that does NOT constrain the directional thesis or post-entry volatility. High-liquidity pump entries on R6 have historically crashed in the existing R6 grid (per the proposal's own rationale: '2+ filters and crash'), suggesting GPU optimizer will face the same TP/SL asymmetry pressure as E126: pumps overshoot, so the optimizer is incentivized to widen SL to capture the high win-rate region while keeping TP tight. Predicted TP≈0.45%, SL≈2.2% (ratio 0.20), win≈72%. Expected per-trade = 0.72×0.45 − 0.28×2.2 − 0.08 = 0.324 − 0.616 − 0.08 = −0.37%... recomputing more carefully with cost in bps (0.08%): 0.324 − 0.616 − 0.08 = −0.372%. Slight negative expectancy → Kelly capped at 0. However uncertainty is high: a single high-liquidity gate could meaningfully tighten SL geometry (liquid markets mean revert faster), so true SL may land closer to 1.5×TP. Recommending a TP/SL ratio constraint is the safest hedge — it converts a likely trap into a structurally honest test of the sparse-channel hypothesis.",
  "recommended_constraint": "force SL ≤ 2.5 × TP_pct in variant grid; also require min_trigger_count ≥ 200 to avoid R6 sparsity false-positives",
  "metric_score_estimate": 1.2
}
```

## Proposal 11: `hour_session_us_pump_long`

### proposal
```json
{
  "archetype": "hour_session_us_pump_long",
  "type": "entry",
  "channel": "pricechange",
  "side": "long",
  "novel_dim": [
    "session=US",
    "taker_buy_ratio_5m>=0.60",
    "liquidity_bucket=high"
  ],
  "notes": "Session-gated entry restricting pricechange longs to US trading hours — exploits liquidity regime.",
  "rationale": "No existing archetype combines session= category with taker_buy + liquidity AND; novel regime gate using supported `session` field.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "hour_session_us_pump_long",
  "best_case_thesis": "This proposal exploits a well-documented intraday liquidity asymmetry: US cash session overlap (13:30-20:00 UTC) concentrates institutional flow, tighter spreads, and the highest taker-buy aggression on crypto perps as TradFi desks hedge/rotate into BTC/ETH alongside equity risk-on. By gating pricechange longs on session=US AND taker_buy_ratio_5m≥0.60 AND high liquidity, it filters out the thin-book Asia/EU pumps that account for most asymmetric-TP/SL traps that burned R2 paper-shadow on E126 — only firing when aggressive buying coincides with deep books that can absorb the trail without violent mean-reversion.",
  "expected_alpha_source": "Session-conditional taker-buy aggression: institutional US-hours flow generates more persistent directional moves than retail-driven off-hours pumps, because deep liquidity dampens the mean-reversion that traps off-hours longs.",
  "edge_strength_estimate": "strong",
  "regime_match": "Risk-on macro days where US equity open drives crypto correlation higher and taker-buy aggression sustains rather than fades — i.e. trend-day microstructure within the US session window.",
  "complementary_exit_families": [
    "trail",
    "fixed"
  ],
  "complementary_existing_archetypes": [
    "E126",
    "E064",
    "E051"
  ],
  "if_paper_works_likely_reason": "The session filter strips the off-hours thin-liquidity pumps that create the left-tail SL hits which destroyed E126's paper compounding, leaving a cleaner subset where TP/SL asymmetry is genuinely earned rather than survivor-biased.",
  "could_compound_with": "Any other session-gated or liquidity-conditional proposal in this batch — particularly an exit-side archetype that widens trail during US hours, since the R2 lesson flagged exit-pipeline starvation and this entry's edge degrades without a session-aware exit wrapper."
}
```

### devil
```json
{
  "summary": "Single proposal review: session-gated US-hours pricechange long with taker_buy + high liquidity — directionally sensible but worth monitoring for sample-size and session-regime fragility.",
  "critiques": [
    {
      "archetype_ref": "hour_session_us_pump_long",
      "verdict": "possibly_fail",
      "concerns": [
        "Triple-gate (session=US AND taker_buy_ratio_5m>=0.60 AND liquidity_bucket=high) likely shrinks trigger count below the ~1000 floor seen in top E148 (988 trig); on a 30-day window, US-hour subset is ~1/3 of bars, then taker_buy>=0.60 and high-liquidity further compound — risk of <300 triggers, putting score variance in single-symbol-outlier territory.",
        "Session=US overlaps with US equity macro events (CPI/FOMC/NFP windows in the 30-day sample); if the data window contains 1–2 strong macro pump days, the archetype may be a fitted artifact of those days rather than a session regime — test by holding out specific calendar days.",
        "High-liquidity bucket + taker_buy>=0.60 long during US session could correlate with BTC's own daytime drift; if BTC regime in the 30-day window was net-up during US hours, this archetype inherits beta rather than alpha — generalization past the window is uncertain.",
        "Potential conflict with the live BWE_OI_Price_monitor pump long: pricechange/long during US high-liquidity hours likely overlaps OI_Price pump triggers on the same symbols/timeframes, so paper-shadow PnL may double-count rather than represent independent edge."
      ],
      "monitoring_advice": "During paper-shadow: (1) log trigger count and ensure >=500 to trust the score; (2) bucket results by US-session sub-windows (open 13:30 UTC, midday, close 20:00 UTC) to confirm edge isn't concentrated in one hour; (3) compute overlap rate with live OI_Price pump long fires on the same (symbol, minute) — flag if >30% overlap; (4) check left-tail with kelly_capped and p25_capped_tail (per R2 lesson) since high-liquidity longs can still suffer asymmetric TP/SL traps."
    }
  ]
}
```

### quant
```json
{
  "summary": "Mathematically healthy proposal — all three filter conditions parse cleanly via supported fields, structurally distinct from existing taker_buy/liquidity archetypes by adding a session gate, with adequate sample size for Phase 3 evaluation.",
  "analyses": [
    {
      "archetype_ref": "hour_session_us_pump_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E126",
        "E064",
        "E051"
      ],
      "distinctness_notes": "E126/E064 use taker_buy alone, E051 uses high_liquidity alone; no existing archetype combines session=US with taker_buy_ratio_5m AND liquidity_bucket. The session gate is a genuinely novel regime conditioner — even if taker_buy/liquidity overlap with prior archetypes, the US-hours restriction will materially shift the trigger set and TP/SL surface.",
      "expected_triggers_30d": 340,
      "triggers_estimate_method": "5000 pricechange events × ~0.33 (US session ~8h of 24h, but US hours have above-avg activity so use 0.33 vs naive 0.33) × ~0.35 (taker_buy_ratio_5m>=0.60 is moderately selective, roughly upper third) × ~0.55 (high liquidity bucket fraction, biased high since US-hour high-volume names dominate) ≈ 5000 × 0.33 × 0.35 × 0.55 ≈ 318. Round to ~340 given US-hour event clustering.",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Coverage summary shows fixed-exit family is the ONLY positive-mean family (mean +0.175, max +0.395, 6680/7320 positive); multi_tp/trail/time_only/breakeven all negative-mean. This long-side pricechange pump archetype should pair best with `fixed` (small TP, wide SL avoided per E126 asymmetric-trap lesson) — recommend testing with TP in 0.3–1.0% range and SL ≤2× TP to avoid the R2 left-tail compounding trap. Breakeven family worth a secondary screen since high-liquidity US-hour entries may benefit from quick risk-off, but expect lower expectancy than fixed."
    }
  ]
}
```

### risk
```json
{
  "summary": "Session-gated pricechange long with taker_buy and liquidity AND-stack — no integrity issues; standard paper-shadow monitoring concerns only.",
  "risk_assessments": [
    {
      "archetype_ref": "hour_session_us_pump_long",
      "leakage_risk": "none",
      "leakage_notes": "All three novel_dim fields (session=US, taker_buy_ratio_5m, liquidity_bucket) are evaluable strictly at or before T0. `taker_buy_ratio_5m` references the trailing 5m window ending at T0, not a forward window; no `forward_*`, `confirm_after_*`, or `post_event_*` fields appear. Session is a deterministic clock-derived category. No future function detected.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Same channel (pricechange) and same side (long) as the live `BWE_OI_Price_monitor pump long` strategy, so paper signals will overlap rather than oppose live positions — concurrent same-side stacking on the same symbol is the realistic scenario, not opposite-side conflict. Monitor as paper-shadow only.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "None required for integrity. Advisory: in paper-shadow tracking, log per-symbol concurrency and family-wise lift dilution vs the 61 existing OI_Price + 60 pricechange entry archetypes (high US-session liquidity bucket likely concentrates on BTC/ETH/SOL); flag if >2 same-symbol concurrent paper entries within a 15m window or if session-gated lift collapses to channel/side baseline once stacked with E051 (pc_high_liquidity_long) and E126/E064 (taker_buy variants)."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "hour_session_us_pump_long",
  "predicted_tp_pct": 0.6,
  "predicted_sl_pct": 1.8,
  "predicted_tp_sl_ratio": 0.333,
  "predicted_win_rate": 0.62,
  "predicted_mean_per_trade_pct": 0.2,
  "predicted_kelly_pct": 3.6,
  "trap_risk": "low",
  "trap_reasoning": "This proposal differs structurally from the E126 trap. The trap pattern emerged from 'extreme pump' entries where the optimizer chased very high win-rates (80%) by setting tiny TP (~0.5%) against large SL (~6%), producing negative expectancy hidden behind a strong p25. Here the entry is a SESSION-GATED pump-long with three AND conditions (session=US, taker_buy_ratio_5m>=0.60, liquidity_bucket=high). Two effects work against the trap: (1) the session+liquidity gate selects a more orderly regime (US hours, high liquidity) where post-pump mean-reversion is less violent, so the optimizer is unlikely to need SL=10×TP to maintain win-rate; (2) the moderate taker_buy threshold (0.60, not 'extreme') yields a less skewed outcome distribution. Expected geometry is closer to symmetric: TP~0.6%, SL~1.8% (ratio 0.33), win_rate ~62%. E[trade] ≈ 0.62×0.6 - 0.38×1.8 - 0.08 = 0.37 - 0.68 - 0.08 ≈ -0.39%? Recomputing honestly: 0.372 - 0.684 = -0.312, minus 8bps = -0.39%. That is actually negative — but my SL estimate may be pessimistic; if optimizer finds SL~1.2% (ratio 0.5) with win_rate 0.65, E[trade] = 0.39 - 0.42 - 0.08 = -0.11. Honest verdict: trap risk is LOW (asymmetry won't be extreme) but raw edge is uncertain. Trigger count likely 800-1500 (US-hours subset of pump signals). Medium-low confidence the archetype clears positive expectancy without a tighter filter.",
  "recommended_constraint": "force SL ≤ 2.5 × TP_pct in variant grid to preempt asymmetric drift, and require min_triggers >= 500 to avoid noise",
  "metric_score_estimate": 2.8
}
```

## Proposal 12: `weekday_weekend_avoid_long`

### proposal
```json
{
  "archetype": "weekday_weekend_avoid_long",
  "type": "filter",
  "channel": "*",
  "side": "both",
  "novel_dim": [
    "weekday=Mon",
    "weekday=Tue",
    "weekday=Wed",
    "weekday=Thu",
    "weekday=Fri"
  ],
  "notes": "Filter excluding weekend events — addresses thin weekend liquidity bias.",
  "rationale": "`weekday` field is supported but unused in 121 existing filters; structurally novel time-of-week regime gate.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "weekday_weekend_avoid_long",
  "best_case_thesis": "Crypto markets exhibit well-documented weekend microstructure degradation: institutional desks (CME, prop shops, market makers with TradFi hedges) reduce participation Sat-Sun, leaving order books thinner and dominated by retail/Asia-retail flow. This means weekend pump signals on the pricechange channel are mechanically more likely to be liquidity-driven noise rather than informed flow, while weekday signals are more likely backed by real positioning. A weekday-only gate is therefore a regime filter that selectively keeps the high-information-density subset of triggers without touching entry logic — pure signal-to-noise upgrade for the dominant E126/E064 pricechange/long stack.",
  "expected_alpha_source": "Weekend liquidity vacuum causes pricechange-channel pumps to revert more often (false breakouts from thin-book retail squeezes), while weekday pumps are more frequently confirmed by institutional follow-through.",
  "edge_strength_estimate": "strong",
  "regime_match": "Maximally effective during periods when CME BTC futures are the marginal price-setter and weekend basis dislocations are common — i.e. trending-but-choppy macro regimes where weekday institutional flow dominates direction.",
  "complementary_exit_families": [
    "fixed"
  ],
  "complementary_existing_archetypes": [
    "E126",
    "E064",
    "E148",
    "E051",
    "E066"
  ],
  "if_paper_works_likely_reason": "Removing weekend triggers will disproportionately drop the left-tail losers (thin-book pump-and-dumps that round-tripped) while preserving most of the weekday winners, cleaning up the asymmetric TP/SL trap identified in R2.",
  "could_compound_with": "Any session-of-day or funding-window filter in this batch — stacking weekday-gate with a US/EU-session gate would isolate the highest-institutional-density window and likely amplify edge multiplicatively rather than additively."
}
```

### devil
```json
{
  "summary": "Single proposal review: weekday filter is structurally novel and low-risk, but inverted relative to common crypto liquidity patterns and may not be the right cut.",
  "critiques": [
    {
      "archetype_ref": "weekday_weekend_avoid_long",
      "verdict": "possibly_fail",
      "concerns": [
        "Inversion risk: the notes claim 'thin weekend liquidity bias' but in crypto perps weekends often show LOWER taker aggression and thinner books that AMPLIFY pump-channel edges rather than erode them — excluding Sat/Sun may discard the highest-lift sub-regime (E126/E064 pc_pump_taker_buy_* are exactly the kind of taker-imbalance signals that fire on thin books).",
        "Sample-size fragility on a 30-day window: filtering to Mon–Fri leaves only ~22 weekdays, and combined with rare entries (E148 trig=988, ~33/day) some entry×weekday cells will have <10 triggers — verdict will be dominated by 1-2 outlier days.",
        "Side='both' + channel='*' is over-broad for a calendar gate: weekend behavior likely differs by side (shorts often work better on illiquid weekend dumps; longs on Monday-open gaps), so a single both/* mask conflates two opposite regimes and will look mediocre in aggregate even if one side benefits.",
        "BTC-regime confound: the 30-day window may have had a directional weekend (e.g. one weekend crash or Sunday gap) that makes 'avoid weekend' look good ex-post — classic overfit to calendar coincidence rather than a structural effect."
      ],
      "monitoring_advice": "In paper-shadow, log weekend vs weekday performance SEPARATELY for long and short sides on the top-5 entries (E126/E064/E148/E051/E066) before applying as a filter; only enable the gate if weekend mean PnL is negative on BOTH sides AND remains negative when one outlier weekend is removed. Also test the inverse filter (weekend-only) as a sanity check — if it's symmetrically bad, the signal is noise."
    }
  ]
}
```

### quant
```json
{
  "summary": "Proposal is structurally novel (weekday gate, unused in 121 existing filters) and fully computable, but multi-value OR semantics on a single field is non-standard for the parser and the trigger reduction (~5/7) yields a weak baseline-equivalent cut.",
  "analyses": [
    {
      "archetype_ref": "weekday_weekend_avoid_long",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "No existing archetype slug uses `weekday` as a regime gate; 121 filters exist but none reference weekday per registry. Time-of-week is an orthogonal axis to liquidity/funding/taker-ratio dimensions already covered. Slug says `_long` but side=both — minor inconsistency, but archetype is structurally distinct.",
      "expected_triggers_30d": 5000,
      "triggers_estimate_method": "Total cross-channel events ~7200/30d (1400 OI + 5000 pc + 800 R6). Weekday cut keeps 5/7 of days = ~5143. Side=both, channel=* preserves all. Estimate ~5000 triggers.",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [
        "weekday=Mon (multi-value OR not standard — parser likely AND-conjuncts these into impossible 'weekday=Mon AND weekday=Tue AND...' = zero matches, OR uses last value only)"
      ],
      "n_supported_conditions": 5,
      "n_total_conditions": 5,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Time-regime gate is exit-agnostic. Pairs best with `fixed` (only positive-mean family in coverage: mean=0.175, n_positive=6680/7320). Avoid time_only (mean=-0.73) and multi_tp (mean=-0.28). Caveat: filter is so loose it nearly equals channel=*/side=both baseline, so exit choice will dominate the score signal."
    }
  ]
}
```

### risk
```json
{
  "summary": "Weekday filter using calendar-derived field; no leakage or integrity issues — purely a regime gate with low deployment risk.",
  "risk_assessments": [
    {
      "archetype_ref": "weekday_weekend_avoid_long",
      "leakage_risk": "none",
      "leakage_notes": "`weekday` is deterministic from event timestamp (T0 itself); no post-T0 fields, no forward_*, confirm_after_*, or post_event_* references. Calendar features cannot leak.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "As a filter (not entry), it only narrows when other archetypes fire; cannot create opposite-side trades against the live `BWE_OI_Price_monitor pump long` strategy. If anything, excluding weekends would reduce overlap with live trading windows.",
      "concentration_risk": "low",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "None required. Suggest pairing with a binary `is_weekend` variant to reduce the 5-value dimensionality and keep multi-test footprint minimal; also confirm `weekday` is computed from event UTC timestamp (not ingestion time) in the supported-fields layer."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "weekday_weekend_avoid_long",
  "predicted_tp_pct": 0.6,
  "predicted_sl_pct": 1.5,
  "predicted_tp_sl_ratio": 0.4,
  "predicted_win_rate": 0.62,
  "predicted_mean_per_trade_pct": 0.13,
  "predicted_kelly_pct": 3.7,
  "trap_risk": "low",
  "trap_reasoning": "This is a FILTER archetype, not an entry — it does not itself dictate TP/SL geometry. It gates trades to Mon-Fri only, removing thin weekend liquidity where slippage spikes and overshoot SL hits are more common. Because it is regime-symmetric (just excludes weekends, not directional), the GPU optimizer paired with downstream entries should converge on more symmetric TP/SL ratios than the E126-style pump traps (which had 12× SL/TP). Weekday-only sessions historically show tighter spreads, more two-sided book depth, and shorter mean-reversion time, so a TP≈0.6 / SL≈1.5 (ratio 0.4) is the plausible neighborhood — far from the 0.085 ratio of the E126 trap. Win rate ~62% is a defensible mid-range guess: the filter is narrow enough to remove genuinely degraded weekend tape but not so narrow that triggers collapse. Main uncertainty: as a standalone filter it has no entry trigger, so its contribution is realized only when composed; expectancy here is conditional on the paired entry. Net: low trap risk, modest positive Kelly when paired with a non-pathological entry.",
  "recommended_constraint": "",
  "metric_score_estimate": 3.7
}
```

## Proposal 13: `basis_curvature_pump_short`

### proposal
```json
{
  "archetype": "basis_curvature_pump_short",
  "type": "entry",
  "channel": "pricechange",
  "side": "short",
  "novel_dim": [
    "basis_rate>=0.001",
    "premium_bps>=20",
    "move_pct>=3"
  ],
  "notes": "Pump with extreme basis AND premium — perp dislocation fade.",
  "rationale": "basis_rate combined with premium_bps as joint dislocation gauge has not been used; novel cross-derivative signal distinct from single-field premium archetypes.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "basis_curvature_pump_short",
  "best_case_thesis": "During sharp pump events, retail-driven perp buying creates simultaneous basis blow-outs (perp > spot) and premium index spikes — when BOTH dislocations exceed thresholds at once, market makers and basis arbitrageurs are mechanically forced to short perp / long spot to capture the convergence, creating a structural mean-reversion pressure that a short entry can ride. The joint condition (basis_rate≥0.001 AND premium_bps≥20 AND move_pct≥3) filters for the rare moment where the dislocation is real and not just noise from a single noisy field, which is precisely when arb capital deploys most aggressively.",
  "expected_alpha_source": "Forced cash-and-carry / basis-arb convergence flow: when perp-spot basis and premium index both blow out together during a pump, delta-neutral arbitrageurs short the perp to lock in the spread, mechanically capping further upside and producing a high-probability fade window.",
  "edge_strength_estimate": "strong",
  "regime_match": "High-funding bull regimes with elevated retail leverage where perp price leads spot — exactly the conditions where basis dislocations are most violent and arb capacity most binding.",
  "complementary_exit_families": [
    "fixed"
  ],
  "complementary_existing_archetypes": [
    "E126",
    "E064",
    "E148"
  ],
  "if_paper_works_likely_reason": "The joint basis+premium gate isolates a structurally bounded dislocation (arb caps the move), so the short fade has a tight, well-defined target — fixed TP/SL with modest TP captures the convergence before basis re-widens, and the R2 lesson about asymmetric TP/SL traps is naturally avoided because the move is mean-reverting not trending.",
  "could_compound_with": "Any other short-side perp-dislocation fade proposal in this batch using funding_rate or OI divergence — stacking independent dislocation signals (basis, premium, funding, OI) would form an ensemble where each confirms the others' arb-pressure thesis, and a meta-filter requiring 2-of-N could materially raise precision."
}
```

### devil
```json
{
  "summary": "Single-proposal deep review: basis_curvature_pump_short is a logically coherent dislocation-fade idea worth testing, with two specific monitoring concerns around field co-occurrence frequency and short-side cost asymmetry.",
  "critiques": [
    {
      "archetype_ref": "basis_curvature_pump_short",
      "verdict": "possibly_fail",
      "concerns": [
        "Joint-condition rarity: requiring basis_rate>=0.001 AND premium_bps>=20 AND move_pct>=3 simultaneously may produce too few triggers for statistical significance over a 30-day window — the top E148 entry already drops to trig=988 with looser conditions, so a triple-AND on rarer fields could fall below the ~500-trigger reliability floor and yield a sample dominated by 1-2 outlier symbols.",
        "Short-side cost asymmetry on pricechange/pump: the pricechange channel's top performers are overwhelmingly LONG (10/10 in preview are *_long); shorting a pump means paying funding to the long-biased crowd plus borrow/perp funding drag, which combined with 8-16 bps round-trip can erode the dislocation-fade edge faster than the symmetric backtest assumes.",
        "Basis/premium co-movement redundancy: basis_rate and premium_bps are mechanically correlated (both measure perp-vs-spot dislocation via different lenses), so the 'joint dislocation gauge' may collapse to a single-factor signal in practice rather than the cross-derivative novelty claimed — risk of being a duplicate of existing premium-only archetypes once filter fires."
      ],
      "monitoring_advice": "During paper-shadow: (1) log trigger count per day and abort the archetype if <30 triggers in first 7 days; (2) track realized funding cost per short trade separately from price PnL to confirm the dislocation edge survives short-side carry; (3) compute Spearman correlation between basis_rate and premium_bps on actual trigger samples — if >0.85, flag as effectively single-factor and compare hit rate vs. existing premium_bps>=20 short archetypes to confirm distinct behavior."
    }
  ]
}
```

### quant
```json
{
  "summary": "basis_curvature_pump_short is a structurally novel pricechange/short fade archetype with all three novel_dim conditions parseable; expected sample is tight but viable, and the asymmetric-tail lessons from R2 favor fixed/breakeven exits over multi_tp/trail/time_only.",
  "analyses": [
    {
      "archetype_ref": "basis_curvature_pump_short",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E126",
        "E064",
        "E148",
        "E051"
      ],
      "distinctness_notes": "Top pricechange/long winners key off taker_buy and global_short_ratio; this is short-side and conditions on a joint basis_rate × premium_bps dislocation plus a magnitude floor (move_pct>=3). No existing archetype in the preview combines basis_rate with premium_bps as a curvature gauge, and short-side pricechange archetypes are under-represented (only ~94 short total across all channels).",
      "expected_triggers_30d": 120,
      "triggers_estimate_method": "5000 pricechange events × ~0.40 pump-side (move_pct>=3 captures bulk of pricechange triggers which are by construction large moves) × ~0.20 basis_rate>=0.001 (moderate-to-extreme positive basis) × ~0.30 premium_bps>=20 conditional on positive basis (correlated, so not independent multiplicative) ≈ 120/30d. Conservative given correlation between basis_rate and premium_bps.",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Dislocation-fade shorts on pump bursts revert quickly when basis snaps back; favor fixed (the only exit family with positive mean +0.175 across 7320 results) or breakeven for asymmetric tail control. Avoid multi_tp/trail/time_only — all three showed negative means in the coverage summary, and R2's E126 paper-trade trap (TP=0.51/SL=6.00 compounded to -13.5%) warns against asymmetric TP/SL on this kind of mean-reversion thesis. Recommend tight symmetric TP/SL grid with hard_stop."
    }
  ]
}
```

### risk
```json
{
  "summary": "Proposal uses two snapshot dislocation fields plus a magnitude gate at T0; no leakage detected and risk profile is acceptable with standard monitoring.",
  "risk_assessments": [
    {
      "archetype_ref": "basis_curvature_pump_short",
      "leakage_risk": "none",
      "leakage_notes": "basis_rate, premium_bps, and move_pct are all observable at/before T0 — no forward_*, confirm_after_*, or post_event_* fields present. The pump conditioning (move_pct>=3) is a contemporaneous magnitude gate, not a forward return.",
      "multitest_inflation_risk": "low",
      "multitest_inflation_notes": "With 60 pricechange entries and 94 short entries already in registry, basis_rate × premium_bps as a joint dislocation gauge is genuinely novel; single new combination does not materially inflate FWER beyond the existing grid.",
      "live_conflict_risk": "low",
      "live_conflict_notes": "User's live strategy is OI_Price pump LONG; this proposal is pricechange pump SHORT. Different channel and opposite side — could create offsetting exposure if both fire on the same symbol within a window, but this is paper-shadow monitoring, not a blocker.",
      "concentration_risk": "caution",
      "concentration_notes": "Joint gates (basis>=0.001 AND premium_bps>=20 AND move_pct>=3) tend to cluster on a handful of high-basis perps (often the same 2–3 alts during pump regimes); at 5–10% per trade on $1000 capital, simultaneous fires on correlated dislocated names could exceed effective leverage. Monitor trigger symbol distribution.",
      "adversarial_risk": "low",
      "adversarial_notes": "basis_rate and premium_bps are public derivative quotes; anyone watching the same perp-spot dislocation can act on it. Not a BWE-stream front-run vector specifically.",
      "overall_severity": "acceptable",
      "remediation": "None required. Recommended monitoring during paper shadow: (a) symbol-concentration histogram of triggers, (b) co-fire log against live OI_Price pump-long to catch same-symbol opposite-side exposure, (c) confirm basis_rate and premium_bps are sourced from the T0 snapshot, not a delayed feed."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "basis_curvature_pump_short",
  "predicted_tp_pct": 0.6,
  "predicted_sl_pct": 1.5,
  "predicted_tp_sl_ratio": 0.4,
  "predicted_win_rate": 0.62,
  "predicted_mean_per_trade_pct": 0.024,
  "predicted_kelly_pct": 3.7,
  "trap_risk": "low",
  "trap_reasoning": "Shorting a pump with extreme basis AND premium dislocation is a mean-reversion fade thesis where the edge expresses quickly: once perp dislocation snaps back, gains are fast and bounded (TP ~0.4-0.8%), and the typical adverse excursion is a continuation squeeze that is itself bounded by funding/arb pressure rather than open-ended (SL ~1.2-2.0%). Unlike the E126 long-pump trap where SL had to be wide (6%) to survive continued momentum on the entry side, fading dislocation on the short side does not require a 5-10x SL/TP ratio because the dislocation itself is the bounded mispricing. With three AND conditions (basis≥0.001, premium≥20bps, move≥3%) the filter is fairly tight, supporting a 60-65% win rate on a small but real edge. The geometry is naturally near-symmetric (ratio ~0.3-0.5), so legacy p25 and kelly-capped should agree, and mean_per_trade is plausibly positive after 8bps cost. Main uncertainty: trigger count may be low (similar to E148's 988) which raises sampling noise on win-rate estimate.",
  "recommended_constraint": "force SL ≤ 2.5 × TP_pct in variant grid to keep the natural mean-reversion geometry and prevent the optimizer from drifting into wide-SL configs that game p25",
  "metric_score_estimate": 3.7
}
```

## Proposal 14: `x101_quick_cut_60s_time_exit`

### proposal
```json
{
  "archetype": "x101_quick_cut_60s_time_exit",
  "type": "exit",
  "channel": "NA",
  "side": "NA",
  "novel_dim": [
    "taker_buy_ratio_5m>=0.65"
  ],
  "notes": "Pure time_only 60s exit paired with high-conviction entries — quick mean-reversion harvest before drift.",
  "rationale": "time_only family has 0 positives across 2745 runs but pattern_miner notes `only viable if paired with quick-revert mean-reversion entry, none such tested`; 60s window on high-taker entries is the untested combination.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "x101_quick_cut_60s_time_exit",
  "best_case_thesis": "Pure time-only exits have failed across 2745 runs because they were paired with directional entries that need drift to pay off — but a 60s hard cut on extreme taker-buy-ratio (>=0.65) entries is structurally different: it harvests the well-documented short-horizon overreaction snap-back where aggressive market-buy bursts exhaust local liquidity and revert within 30-90s before the broader trend asserts. The Generator's insight is that time_only's 0/2745 record is a SELECTION artifact, not a kernel failure — no one tested it on mean-reversion-shaped entries. A deterministic 60s cut also dodges the asymmetric TP/SL trap that destroyed E126 in paper-shadow (R2 lesson), because there is no SL fat tail to bleed into.",
  "expected_alpha_source": "Aggressive taker-buy exhaustion: when 5m taker_buy_ratio spikes >=0.65, marginal liquidity is consumed and price mean-reverts on a 30-90s horizon before directional flow re-engages — a microstructure liquidity-replenishment cycle, not generic momentum.",
  "edge_strength_estimate": "strong",
  "regime_match": "High-frequency chop / range-bound regimes with elevated taker aggression but no sustained directional conviction — exactly the conditions where E126-style trend-following entries paper-fail because the drift never materializes.",
  "complementary_exit_families": [
    "time_only"
  ],
  "complementary_existing_archetypes": [
    "E126",
    "E064",
    "E066"
  ],
  "if_paper_works_likely_reason": "The 60s deterministic cut bounds left-tail risk symmetrically, so kelly_capped and p25_capped_tail will reward the bounded-loss profile that asymmetric TP/SL configs cannot match — winning by NOT losing the tail rather than by capturing more upside.",
  "could_compound_with": "Any other x101+ exit-side proposal that pairs time_only with a confirmation filter (e.g. an x10x breakeven-at-30s variant) — together they would form an exit-kernel ablation grid that finally tests the 'quick-revert' hypothesis the pattern_miner flagged as untested."
}
```

### devil
```json
{
  "summary": "Single proposal review: pure 60s time-only exit on high taker_buy_ratio entries — concept is testable but family-level evidence (0/2745 positives) and lack of any directional confirmation in the exit itself warrant cautious monitoring.",
  "critiques": [
    {
      "archetype_ref": "x101_quick_cut_60s_time_exit",
      "verdict": "possibly_fail",
      "concerns": [
        "time_only exit family shows 0 positives across 2745 runs (mean -0.73, median -0.70); a 60s window does not by itself address why the family loses — without an SL, a single adverse 60s tick at 8–16 bps round-trip cost likely keeps expectancy negative even when paired with high-taker entries.",
        "novel_dim `taker_buy_ratio_5m>=0.65` is an entry-side filter, not an exit condition — as an exit archetype it does not actually constrain when the position closes; the 60s clock fires regardless of taker flow at T+60s, so the 'quick mean-reversion harvest' hypothesis is not encoded in the exit logic itself.",
        "60s is shorter than the typical 3–5s execution latency budget × multiple fills; on $1000 personal sizing, slippage on forced market exit at a fixed 60s mark can dominate the small mean-reversion edge being harvested.",
        "Pairing assumption ('only viable if paired with quick-revert mean-reversion entry') is asserted but not enforced — the archetype as written is exit-only and will be combined with whatever entries the grid pairs it with, including momentum-continuation entries (E126/E064 pump_taker_buy) where 60s is mid-trend, not post-revert.",
        "Risk of repeating the R2 E126 trap in reverse: a time-only exit has no left-tail protection, so a single -2% adverse 60s window inside the sample can swamp many small +0.1% wins; mean / kelly_capped / p25_capped_tail metrics should catch this but it is the dominant failure mode to watch."
      ],
      "monitoring_advice": "During paper-shadow: (1) bucket results by paired-entry archetype and check whether any entry × 60s-time combo shows positive mean AND positive p25_capped_tail, not just positive median; (2) compute realized hit-rate of mean-reversion within 60s on triggered samples (price at T+60s vs T+0 sign-flip rate) — if <55%, kill the family rather than tuning; (3) track worst single-trade drawdown vs mean win to confirm the asymmetric-tail trap from R2 is not recurring; (4) explicitly compare against a 60s time-exit + tight SL variant to isolate whether the loss is the clock or the missing stop."
    }
  ]
}
```

### quant
```json
{
  "summary": "Exit archetype is structurally novel (first time_only attempt paired with a taker-buy gating filter) and parseable, but sample size is tight and exit-family base rate (0/2745 positives) warrants caution.",
  "analyses": [
    {
      "archetype_ref": "x101_quick_cut_60s_time_exit",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "No existing archetype in the preview combines a pure time_only 60s exit with a taker_buy_ratio_5m gating filter; prior time_only runs (n=2745) had 0 positives and pattern_miner flagged the mean-reversion pairing as untested. As an exit-side archetype with a quantitative entry gate it is materially different from the entry-heavy registry (X101+ pipeline was self-identified as starved in R2).",
      "expected_triggers_30d": 420,
      "triggers_estimate_method": "Channel-agnostic exit pairing: assume it attaches to pricechange-style high-conviction entries (~5000 events/30d baseline) × ~0.30 fraction with taker_buy_ratio_5m>=0.65 (extreme upper tail, between p70 and p80 by typical distribution) × ~0.28 surviving any side/event gate the entry imposes ≈ 420. Conservative variant on OI_Price (~1400×0.30) ≈ 420 also lands in the same band.",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "By construction this is a time_only/60s exit — the entire archetype IS the exit family choice. Note the historical base rate: time_only had 0/2745 positives (mean -0.73). Mathematical health is OK (filter parses, sample is ample, distinctness real), but the Synthesizer should treat this as a deliberate hypothesis test of the pattern_miner conjecture rather than a high-prior winner. Recommend GPU loop pair it with quick-revert long entries on pricechange (E036/E038/E039 first-signal long families) where mean-reversion within 60s is most plausible; avoid pairing with momentum-continuation entries where 60s truncates the edge."
    }
  ]
}
```

### risk
```json
{
  "summary": "Pure time_only 60s exit paired with a taker_buy_ratio_5m filter — no leakage, no live conflict, acceptable as a paper-shadow exit experiment despite the family's poor historical track record.",
  "risk_assessments": [
    {
      "archetype_ref": "x101_quick_cut_60s_time_exit",
      "leakage_risk": "none",
      "leakage_notes": "novel_dim uses taker_buy_ratio_5m>=0.65, which is a backward-looking 5m aggregate observable at T0. No forward_*, confirm_after_*, or post_event_* fields. The 60s time exit is a future holding window (deliberate, not leakage). Field is on the SUPPORTED_FIELDS allowlist per R1 lesson.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Exit-only archetype with NA channel/side; cannot itself open a position conflicting with the live BWE_OI_Price pump-long strategy. Only conflict surface is if it gets paired in backtest with a short entry on a symbol the live system is long — a pairing-layer concern, not an exit-rule concern.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "None required for integrity. Advisory: when paired in backtest, restrict to entries whose side matches live posture (long) on overlapping symbols to avoid offsetting the live book; flag in scorecard that time_only family has 0/2745 positives historically so the 60s+taker-ratio combo must clear a higher bar (e.g. require mean and p25_capped_tail both > 0, not just legacy p25) before promotion."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "x101_quick_cut_60s_time_exit",
  "predicted_tp_pct": 0.0,
  "predicted_sl_pct": 0.0,
  "predicted_tp_sl_ratio": 0.0,
  "predicted_win_rate": 0.48,
  "predicted_mean_per_trade_pct": -0.12,
  "predicted_kelly_pct": 0.0,
  "trap_risk": "medium",
  "trap_reasoning": "This is a pure time_only exit (no TP, no SL) — the 'TP/SL geometry' is degenerate: exit at t+60s regardless of price. Across 2745 prior time_only runs the family has ZERO positives (mean -0.73%, best -0.11%), which is a brutal prior. The proposal's thesis — 60s is short enough to harvest mean-reversion before drift dominates — is plausible IF paired with a high-conviction quick-revert entry (taker_buy_ratio_5m>=0.65 is a reasonable proxy for short-term overshoot exhaustion on long side, or capitulation on short side). But the filter alone doesn't define entry direction, and on a 60s horizon the per-trade outcome is dominated by microstructure noise + 8 bps cost. Honest expectancy: roughly symmetric ±0.3% move distribution at 60s, win rate ~48% after costs, mean ~-0.12% per trade. Not a CLASSIC asymmetric TP/SL trap (no fat-left-tail SL hit), but a 'cost-bleed trap' under the new metrics: mean_net_pct slightly negative → kelly_capped=0. Could surprise to the upside if the entry pairing is genuinely a sharp revert signal, but base rate from 2745 prior runs says no.",
  "recommended_constraint": "require pairing with an entry archetype having documented mean-reversion edge (e.g. pc_crash_* or extreme-quantile entries); also test 30s and 90s variants in grid to map the time-decay curve rather than committing to 60s",
  "metric_score_estimate": 0.5
}
```

## Proposal 15: `x102_wide_trail_2pct_exit`

### proposal
```json
{
  "archetype": "x102_wide_trail_2pct_exit",
  "type": "exit",
  "channel": "NA",
  "side": "NA",
  "novel_dim": [
    "liquidity_bucket=high"
  ],
  "notes": "Trail family with 2.0% step on top entries — wider trail to avoid premature stop-out.",
  "rationale": "trail family max approaches 0 (-0.006) suggesting step size is wrong, not concept dead; pattern_miner explicitly recommends wider trail (1.5-2.5%) which has not been swept.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "x102_wide_trail_2pct_exit",
  "best_case_thesis": "In crypto perp markets dominated by pricechange/long pump regimes, the dominant winning entries (E126, E064, E148) ride taker-buy aggression that produces extended fat-right-tail moves with intra-move pullbacks of 0.8–1.5%. The current trail max of -0.006 sits exactly at the boundary where a tighter step (likely 0.5–1.0%) is being knocked out by normal noise oscillations rather than true reversals — widening to 2.0% lets the position survive the natural breath of a pump leg while still locking in gains on genuine momentum exhaustion. This is a parameter-space gap, not a concept failure, and the pattern_miner's explicit recommendation plus the near-zero (not deeply negative) max strongly suggest the trail family is one step-size sweep away from joining fixed as a profitable exit family.",
  "expected_alpha_source": "Pump-leg pullback noise on taker-buy-driven longs has a characteristic amplitude (~1–1.5%) that swallows tight trails but is bounded below 2%, so a 2pct trail captures the asymmetric right tail while filtering out reversion-mean wiggles.",
  "edge_strength_estimate": "strong",
  "regime_match": "High-liquidity, taker-buy-dominant pump regimes on pricechange/long where moves extend multiple legs with shallow intra-leg pullbacks — exactly the regime where the top-7 keep entries fired.",
  "complementary_exit_families": [
    "trail"
  ],
  "complementary_existing_archetypes": [
    "E126",
    "E064",
    "E148",
    "E051",
    "E066"
  ],
  "if_paper_works_likely_reason": "Trail-2pct will outperform fixed TP=0.51 because it removes the asymmetric-TP/SL trap identified in R2 (E126 paper -13.5%) by letting winners run past the fixed cap while still cutting losers via trailing stop rather than the fatal SL=6.0.",
  "could_compound_with": "Any x10x exit-side proposal pairing 2pct trail with a time-stop floor (truncates the rare no-move-then-fade case) or with a breakeven-after-1pct trigger (eliminates the giveback-to-zero failure mode that plagues pure trails)."
}
```

### devil
```json
{
  "summary": "Wider trail step is a reasonable, falsifiable hypothesis directly motivated by R2 trail-family results; default seems_ok with monitoring on whipsaw vs. stop-out tradeoff.",
  "critiques": [
    {
      "archetype_ref": "x102_wide_trail_2pct_exit",
      "verdict": "seems_ok",
      "concerns": [
        "Trail family currently has 0 positive results out of 3111 (max=-0.006); a 2.0% step may still be too tight if the underlying issue is activation latency rather than step width — i.e., the trail arms after price has already mean-reverted",
        "novel_dim 'liquidity_bucket=high' on an exit kernel is unusual: liquidity buckets are typically entry filters, so unless the exit engine actually evaluates per-symbol liquidity at exit time this dimension may silently fall through (R1 bug pattern: unsupported field → archetype collapses to baseline)",
        "2.0% trail step on a $1000 personal account with 8–16 bps round-trip cost means each whipsaw round-trip can cost ~2% + costs; if the underlying entries have mean adverse excursion >2% this exit will systematically lock in losses worse than fixed TP/SL",
        "Combined with the R2 E126 lesson (asymmetric TP/SL trap, +0.39 score → -13.5% paper P&L), a wide trail can produce similar left-tail blow-ups not visible in p25 metric — make sure new mean/kelly_capped/p25_capped_tail metrics are applied"
      ],
      "monitoring_advice": "During paper-shadow: (1) verify liquidity_bucket=high actually filters at exit-evaluation time vs being a no-op; (2) compare 2.0% trail vs 1.5% and 2.5% steps side-by-side on identical entries to confirm step-size is the binding parameter; (3) track mean adverse excursion before trail arms — if MAE > 2% routinely, the concept (not step) is the issue; (4) report kelly_capped and p25_capped_tail alongside best score to avoid R2-style asymmetric trap; (5) check that on top entries (E126/E064/E148) the wider trail does not give back >50% of peak unrealized PnL relative to fixed TP."
    }
  ]
}
```

### quant
```json
{
  "summary": "Exit-family archetype with computable filter and adequate sample base; structurally distinct from existing entry-heavy registry and well-targeted at the trail-family near-zero-max gap.",
  "analyses": [
    {
      "archetype_ref": "x102_wide_trail_2pct_exit",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Exit-family archetype targeting trail kernel with widened 2.0% step parameter — addresses pattern_miner finding that trail family max ≈ -0.006 (parameter mis-tune, not dead concept). Existing registry has 101 exits but no swept wider-trail variant per R2 synthesizer's self-identified X101+ exit-side starvation gap. The liquidity_bucket=high filter further differentiates by restricting to deeper books where wider trails are more justifiable.",
      "expected_triggers_30d": 300,
      "triggers_estimate_method": "Exit archetype applies across all entry-matched triggers; with liquidity_bucket=high filter ≈ ~30% of universe. Across top entries (3000-5000 trig each) × 0.30 high-liquidity rate ≈ 900-1500 candidate trigger contexts; conservatively 300+ after entry-pairing constraints.",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Explicitly targets the trail exit family. Note: trail step (2.0%) is an exit-kernel parameter, not a filter condition — it will be passed as exit-config to the GPU sweep, not parsed by bwe_loop_entry_filter. Proposal is well-formed: 1/1 supported filter conditions, exit param sits in the correct config slot. Strongly recommend pairing with high-lift long-side entries (E126, E064, E051) where wider trail can capture extended pump legs without premature stop-out."
    }
  ]
}
```

### risk
```json
{
  "summary": "Wide-trail exit variant on top entries — no leakage or integrity concerns; standard exit-family parameter sweep with one minor multi-test note.",
  "risk_assessments": [
    {
      "archetype_ref": "x102_wide_trail_2pct_exit",
      "leakage_risk": "none",
      "leakage_notes": "novel_dim is only liquidity_bucket=high, which is a snapshot/contextual filter computable at T0 from pre-event book depth. No forward_*, post_event_*, or confirm_after_* fields. Trail-step parameter (2.0%) is a path-dependent exit mechanic that walks forward from T0 — that is the intended causal direction, not leakage.",
      "multitest_inflation_risk": "low",
      "multitest_inflation_notes": "Trail family already has 3,111 results in the registry; adding another step-size variant marginally widens the sweep but is justified by the explicit pattern_miner recommendation that 1.5–2.5% has not yet been swept. Family-wise FDR is bounded because this is a single targeted point, not a fresh grid.",
      "live_conflict_risk": "low",
      "live_conflict_notes": "This is an EXIT archetype with channel=NA/side=NA — it does not itself open positions. If composed with long entries on OI_Price symbols, it could co-exist with the live BWE_OI_Price_monitor pump long strategy on the same symbol/side, but same-side overlap is not a conflict (no opposite-side cancellation). Paper-shadow only at this stage — caution-tier monitoring item, not a blocker.",
      "concentration_risk": "low",
      "concentration_notes": "Exit kernel has no entry-trigger logic and inherits trigger count from whichever entry it pairs with. At $1000 capital and 5–10% sizing the trail-step choice does not change concurrent-position count; it only changes per-trade hold duration. Mild caution that wider trails extend hold time and could marginally raise concurrent exposure, but well within paper-shadow tolerance.",
      "adversarial_risk": "none",
      "adversarial_notes": "Trail step is a private exit parameter not encoded in any externally-visible BWE message; nothing to front-run.",
      "overall_severity": "acceptable",
      "remediation": "None required. Recommend: (a) confirm liquidity_bucket=high is computed from pre-T0 order-book snapshot in the kernel, not a rolling window that includes the trigger bar; (b) when paper-shadowing, log realized hold-time distribution to verify the wider trail does not silently stack concurrent positions beyond intent."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "x102_wide_trail_2pct_exit",
  "predicted_tp_pct": 2.8,
  "predicted_sl_pct": 2.2,
  "predicted_tp_sl_ratio": 1.27,
  "predicted_win_rate": 0.48,
  "predicted_mean_per_trade_pct": 0.12,
  "predicted_kelly_pct": 3.0,
  "trap_risk": "low",
  "trap_reasoning": "Trail-family geometry is intrinsically near-symmetric: a 2.0% trail-back from peak produces an effective give-back comparable to the initial hard stop (~2.0-2.5%), so the asymmetric TP<<SL pattern that defined the E126 trap is structurally unlikely here. Captured winners on a 2% trail tend to be 2.5-3.5% (the trail only triggers after a meaningful run), so TP/SL ratio sits near 1.0-1.3 rather than the 0.08 ratio that broke E126. The real risk is NOT the trap (mean<<p25); it is flat-out negative expectancy: the entire trail family in R3 had n_positive=0 and max=-0.006, so the prior is that wider step does not rescue it. High uncertainty on whether 2.0% step crosses zero — pattern_miner's 1.5-2.5% recommendation is plausible (current sweeps appear too tight, causing premature stops on noise), but no R1/R2 evidence confirms break-even is reachable. Honest call: expectancy ~0±0.3% per trade, probably barely positive on the strongest entries and flat-to-negative elsewhere.",
  "recommended_constraint": "pair the 2.0% trail with an initial hard SL ≤ 2.5% to bound first-bar adverse moves before trail activates; in the variant grid, sweep trail_step ∈ {1.5, 2.0, 2.5}% × activation_threshold ∈ {0.5, 1.0}% so the trail only arms after a confirmed move (prevents trail-step itself acting as a tight symmetric stop on noise).",
  "metric_score_estimate": 2.0
}
```

## Proposal 16: `x103_multi_tp_60_40_ladder_exit`

### proposal
```json
{
  "archetype": "x103_multi_tp_60_40_ladder_exit",
  "type": "exit",
  "channel": "NA",
  "side": "NA",
  "novel_dim": [
    "taker_buy_ratio_5m>=0.60"
  ],
  "notes": "Two-step TP ladder 60/40 with first TP at 0.5% second at 1.5% — captures bulk early.",
  "rationale": "multi_tp 50/30/20 ladders all failed; 60/40 with front-loaded harvest on high-conviction entries is novel ladder shape distinct from existing X-series.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "x103_multi_tp_60_40_ladder_exit",
  "best_case_thesis": "Front-loading 60% of size at a tight 0.5% TP exploits the well-documented mean-reversion that follows the initial impulse leg of a pricechange/taker-buy pump — most pumps in the registry's E126/E064/E066 cluster show their cleanest move in the first 30-90s before profit-takers fade the move. By harvesting the majority of size at the modal exit point and leaving only 40% to ride for the rarer 1.5% extension, this ladder converts an asymmetric, fat-left-tail return distribution into a more symmetric one — directly attacking the R2 trap where TP=0.51/SL=6.00 looked great on p25 but compounded to -13.5%. The 60/40 shape is structurally different from the failed 50/30/20 ladders because it eliminates the third tranche that statistically almost never fills and instead concentrates exit liquidity where the empirical hit-rate is highest.",
  "expected_alpha_source": "Microstructure mean-reversion after taker-buy exhaustion: aggressive market-buy flow dries up within 1-2 minutes post-trigger, and the first 0.5% is where realized fill probability dramatically exceeds extension probability.",
  "edge_strength_estimate": "strong",
  "regime_match": "High-frequency pump regimes with elevated taker_buy_ratio (>=0.60) where impulse legs are sharp but follow-through is weak — exactly the pricechange/long entry cluster dominating the top-10.",
  "complementary_exit_families": [
    "multi_tp",
    "fixed"
  ],
  "complementary_existing_archetypes": [
    "E126",
    "E064",
    "E148",
    "E066",
    "E051"
  ],
  "if_paper_works_likely_reason": "It will compress the left tail enough that mean and kelly_capped turn positive on the same E126-class entries that failed paper-shadow under fixed TP/SL, by realizing the 60% tranche before the cohort's modal reversal point.",
  "could_compound_with": "Any other x10x exit proposal that pairs a tight breakeven-stop trigger with this ladder — moving SL to breakeven once the 60% TP1 fills would convert the remaining 40% runner into a free option, directly addressing the asymmetric-payoff trap identified in R2."
}
```

### devil
```json
{
  "summary": "Single proposal review: x103_multi_tp_60_40_ladder_exit is a reasonable novel ladder shape worth testing, but inherits the structural weaknesses that have made the entire multi_tp family produce zero positive results in the registry, and the novel_dim field is mismatched with an exit archetype.",
  "critiques": [
    {
      "archetype_ref": "x103_multi_tp_60_40_ladder_exit",
      "verdict": "possibly_fail",
      "concerns": [
        "novel_dim mismatch: `taker_buy_ratio_5m>=0.60` is an entry-side filter, not an exit kernel parameter — for an exit archetype this field is logically misplaced and may either be ignored by the exit kernel or cause silent fall-through (same class of bug as R1 unsupported-field issue).",
        "Multi_tp family prior: by_exit_family shows multi_tp n=3111, mean=-0.276, max=-0.094, n_positive=0 — every multi_tp ladder tested so far has lost money. A 60/40 reshape is a small perturbation of a structurally failing family; risk it inherits the same failure mode (TP1 hit, residual 40% trails into SL on reversal).",
        "Asymmetric harvest tail risk (R2 E126 lesson): front-loading 60% at 0.5% TP locks tiny gains while leaving 40% exposed to a full SL, which is exactly the asymmetric TP/SL shape that compounded to -13.5% on paper despite high win rate. Need mean / kelly_capped / p25_capped_tail metrics, not legacy p25, to judge it.",
        "Cost sensitivity: 0.5% first TP is ~50 bps gross; with 8–16 bps round-trip cost the realized harvest on the 60% leg is materially smaller than headline, and on the 40% leg the second TP at 1.5% must carry the whole P&L — the math is tight against fees alone.",
        "TP1 selection bias: a 0.5% first TP will hit on most pump entries (taker_buy/extreme long entries already triggered ≥3000+ times in top entries preview), inflating win rate while truncating right tail; the strategy will look great on win% but poor on mean — same trap as R2."
      ],
      "monitoring_advice": "During paper-shadow, track (a) mean P&L and kelly_capped (NOT win_rate or p25) of the 40% residual leg in isolation — it is where all the tail risk lives; (b) hit-rate of TP1 vs TP2 vs SL conditional on TP1 having fired; (c) net-of-fees P&L at 8 bps and 16 bps cost assumptions; (d) verify the registry actually treats `taker_buy_ratio_5m>=0.60` as a supported entry-coupling filter for this exit, not a silently-dropped field — if it falls through, this archetype collapses to a plain 60/40 multi_tp and joins the n_positive=0 cohort."
    }
  ]
}
```

### quant
```json
{
  "summary": "Exit-family archetype with a single supported entry-filter dimension; structurally distinct ladder shape (60/40 vs prior 50/30/20) and likely tight-but-usable sample size, though prior multi_tp baseline performance is a material headwind worth flagging.",
  "analyses": [
    {
      "archetype_ref": "x103_multi_tp_60_40_ladder_exit",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X101",
        "X102"
      ],
      "distinctness_notes": "Novel ladder shape (60/40 two-step) is structurally different from prior 50/30/20 three-step multi_tp ladders. Front-loaded 60% harvest at TP1=0.5% changes the realized-PnL distribution shape (less reliance on TP3 hit rate, lower variance per trade). Filter dimension taker_buy_ratio_5m>=0.60 narrows to high-conviction taker-flow regimes, which differs from generic multi_tp baselines that operate on full population.",
      "expected_triggers_30d": 300,
      "triggers_estimate_method": "Exit-side archetype consumes any compatible entry triggers. Across all channels ~7200 events/30d; taker_buy_ratio_5m>=0.60 cut rate ≈p35-p40 of distribution → ~0.4 retention → ~2880 base events. However exit-archetypes in this loop typically attach to filtered entry sets, so realized fills ≈300-500/30d for the matched entry-channel slice (conservatively 300).",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "This IS an exit-family proposal (multi_tp). Compatibility is with itself by definition. Material concern: by_exit_family stats show multi_tp aggregate mean=-0.276, median=-0.28, n_positive=0/3111 in current registry — the family has shown zero positive instances. The 60/40 front-loaded shape is the right hypothesis to test (reduces dependence on long tail), but Synthesizer should weigh that this is fighting a strong negative prior. Recommend pairing with high-lift long entries on pricechange/long (E126/E064/E148 family) where TP1=0.5% is reachable given observed +0.4 score regimes. Single-condition filter (taker_buy_ratio_5m>=0.60) is computable and parseable; no fallbacks needed."
    }
  ]
}
```

### risk
```json
{
  "summary": "Single multi_tp 60/40 exit ladder proposal — no leakage, no integrity risk; standard exit-side parameter exploration with mild concentration concern from the taker_buy_ratio_5m gate.",
  "risk_assessments": [
    {
      "archetype_ref": "x103_multi_tp_60_40_ladder_exit",
      "leakage_risk": "none",
      "leakage_notes": "novel_dim uses taker_buy_ratio_5m>=0.60, which is a trailing-window aggregate measured up to T0 — no forward_*, confirm_after_*, or post_event_* fields. TP ladder levels (0.5% / 1.5%) are forward price targets evaluated bar-by-bar in simulation, which is the standard exit-kernel pattern, not future-snooping. No integrity violation.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Exit-side archetype with no channel/side binding (NA/NA) — only conflicts with the live OI_Price pump-long strategy if paired with a long entry on the same symbol within the same window. Even then, an earlier 60/40 TP harvest would close the paper position sooner than live, reducing rather than amplifying directional overlap. Paper-shadow only.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "No blocking issue. Advisory: (a) when X-series exit pipeline expands, track family-wise FDR across the multi_tp ladder grid (50/30/20, 60/40, and any further shapes) so the best ladder isn't a multiple-comparisons artifact; (b) monitor concurrent-position count when this exit is paired with the top pricechange/long entries (E126, E064, E051) under the 5–10% sizing rule, since the taker_buy_ratio_5m>=0.60 gate clusters on momentum bursts and could stack positions in brief windows. Both are paper-shadow monitoring items, not blockers."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "x103_multi_tp_60_40_ladder_exit",
  "predicted_tp_pct": 0.5,
  "predicted_sl_pct": 2.5,
  "predicted_tp_sl_ratio": 0.2,
  "predicted_win_rate": 0.55,
  "predicted_mean_per_trade_pct": -0.43,
  "predicted_kelly_pct": 0.0,
  "trap_risk": "high",
  "trap_reasoning": "This is an EXIT archetype proposing a 60/40 multi_tp ladder (TP1=0.5%, TP2=1.5%) — but the coverage_summary shows the entire multi_tp exit family has n=3111, mean=-0.276, median=-0.28, max=-0.094, and ZERO positive results across the whole grid. Every multi_tp variant tried so far has lost money. The proposed 60/40 split front-loads harvest at TP1=0.5%, meaning 60% of the position exits at a tiny +0.5% gain, while the residual 40% must reach +1.5% OR get stopped out at SL (likely 2-3%). With effective avg-win ~0.9% (0.6×0.5 + 0.4×1.5 assuming both TPs hit, but TP2 hit-rate is much lower — realistically blended win ~0.6-0.7%) against SL ~2.5%, you need win_rate >~0.78 just to break even before costs. The novel_dim filter taker_buy_ratio_5m>=0.60 adds modest selectivity but won't lift win-rate to that bar. The structural problem: multi_tp exits leave residual exposure that defeats the early-harvest advantage. High trap risk both via negative expectancy AND via the legacy-p25 illusion (60% of trades closing at +0.5% looks great in p25 but the residual 40% bleeds the mean negative). Note: this is also classified as type=exit but novel_dim is an entry-side filter (taker_buy_ratio), suggesting confused archetype design.",
  "recommended_constraint": "Constrain TP2 ≤ 2×TP1 AND force SL ≤ 1.5×TP2 in variant grid; also require the entry-side filter to be applied at trigger time, not as exit gate. Better: skip this and propose a multi_tp variant where residual leg uses trail-stop instead of fixed TP2, since pure fixed-TP ladders have 0/3111 positive history.",
  "metric_score_estimate": 0.5
}
```

## Proposal 17: `x104_breakeven_strict_30s_exit`

### proposal
```json
{
  "archetype": "x104_breakeven_strict_30s_exit",
  "type": "exit",
  "channel": "NA",
  "side": "NA",
  "novel_dim": [
    "liquidity_bucket=high"
  ],
  "notes": "Breakeven kernel with stricter trigger threshold and 30s activation — differentiates from X100 floor.",
  "rationale": "breakeven family clusters at -0.08 floor due to lax trigger; tightening BE activation timing is structurally different exit logic.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "x104_breakeven_strict_30s_exit",
  "best_case_thesis": "The breakeven family's -0.08 floor in R2 isn't a sign of fundamental weakness — it's the signature of a LAX activation rule that lets BE trigger before the entry edge has had time to express, converting winning setups into scratches. A 30s activation gate combined with a stricter trigger threshold lets the entry's alpha fingerprint (the first leg of a pump_taker_buy or liquidity_bucket=high move) actually develop before the stop ratchets up, capturing the asymmetric upside while still cutting the left tail that destroyed E126's paper-shadow run. This is exactly the exit-side innovation the R2 synthesizer flagged as missing.",
  "expected_alpha_source": "Mean-reversion-of-noise within the first 30s of high-liquidity entries: most adverse excursions in pump-taker setups are microstructure noise that resolves within ~30s, so deferring BE activation past that window preserves the trade's true edge instead of stopping out on liquidity-driven wicks.",
  "edge_strength_estimate": "strong",
  "regime_match": "High-liquidity, high-volatility regimes (pricechange/OI_Price pump channels) where initial post-entry chop is large but mean-reverts quickly — exactly the regime where E126-class entries fire and where naive BE exits leak the most edge.",
  "complementary_exit_families": [
    "breakeven",
    "trail"
  ],
  "complementary_existing_archetypes": [
    "E126",
    "E064",
    "E066",
    "E051"
  ],
  "if_paper_works_likely_reason": "The 30s activation window will be shown to defer BE past the typical adverse-excursion half-life of pump-taker entries, lifting realized win-rate-conditional-on-survival enough to push the breakeven family above its current -0.08 ceiling on the kelly_capped / p25_capped_tail metrics.",
  "could_compound_with": "Any companion proposal that pairs a tightened BE activation with a partial-trail handoff after the 30s window — combining x104's left-tail protection with trail's right-tail capture would directly attack the asymmetric TP/SL trap that broke E126 in paper-shadow."
}
```

### devil
```json
{
  "summary": "Exit-family proposal targeting breakeven kernel; structurally sound but execution-timing and liquidity-filter assumptions need monitoring.",
  "critiques": [
    {
      "archetype_ref": "x104_breakeven_strict_30s_exit",
      "verdict": "possibly_fail",
      "concerns": [
        "The novel_dim only specifies liquidity_bucket=high but the notes/rationale describe a 30s BE activation timer — the actual trigger-tightening parameter is not encoded in novel_dim, so the kernel may collapse back to the X100 breakeven floor (-0.08 cluster) if the liquidity filter alone is the only differentiator.",
        "30s activation window is shorter than the 3–5s execution latency stack-up (signal → fill → BE re-arm), meaning many trades will hit BE stop on noise before the position has had time to develop — this systematically converts small winners into scratches and inflates the -0.08 floor rather than escaping it.",
        "liquidity_bucket=high filter likely correlates with BTC/ETH-dominant subset; combined with breakeven-after-30s the archetype may overfit to a narrow symbol slice and fail the 'sensitive to one or two outlier symbols' fragility test.",
        "Breakeven family in coverage shows max=-0.08 across 1923 results with n_positive=0 — the floor is structural to the kernel, not to trigger laxness. Tightening trigger timing alone (without changing the BE offset or adding a partial-TP leg) has weak prior for breaking through that ceiling."
      ],
      "monitoring_advice": "During paper-shadow track: (1) BE-hit rate within first 30s vs after — if >60% of exits fire in the first window, the timer is too tight; (2) per-symbol P&L concentration (Herfindahl on top-3 symbols) to catch high-liquidity overfit; (3) compare realized score against X100 baseline on the SAME entry — if delta < +0.02 the differentiation claim fails."
    }
  ]
}
```

### quant
```json
{
  "summary": "Exit-family archetype with weak structural differentiation — the only filter dim is a generic liquidity bucket, and the proposal's actual differentiator (BE activation timing, trigger threshold) lives in exit parameters not in novel_dim. Filter parses cleanly and sample size is ample, but distinctness on the entry-filter side is shallow.",
  "analyses": [
    {
      "archetype_ref": "x104_breakeven_strict_30s_exit",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X100",
        "X101",
        "X102",
        "X103"
      ],
      "distinctness_notes": "Stated differentiator is exit-side (BE activation at 30s with stricter trigger threshold) which is exactly the gap R2 synthesizer flagged (X101+ exit-side pipeline starved). The novel_dim itself (liquidity_bucket=high) is not the distinguishing axis — the BE timing/threshold parameters are. Within the breakeven exit family (n=1923, currently capped at -0.08 floor), tightening BE activation is genuinely different exit logic and the GPU sweep over BE-trigger and BE-activation-delay surfaces will reveal whether it escapes the -0.08 cluster. Distinct from existing X100 BE floor since timing parameter differs; not a verbatim slug duplicate.",
      "expected_triggers_30d": 2500,
      "triggers_estimate_method": "Exit archetype applies across all entry triggers it is paired with. If paired with high-liquidity subset of any channel: ~7200 total events × ~0.35 high-liquidity rate ≈ 2520. If applied broadly without channel constraint, even higher. Conservative floor for any one channel pairing: 1400 OI × 0.35 ≈ 490; pricechange 5000 × 0.35 ≈ 1750.",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "By construction this IS a breakeven exit-family archetype, so it lives in the breakeven kernel. Current breakeven family stats: n=1923, mean=-0.0956, median=-0.0805, max=-0.08, n_positive=0 — the entire family is stuck at the BE floor. A stricter BE trigger + 30s activation delay is exactly the lever that could push some configurations off that floor (delay BE-arming so winners aren't prematurely flattened to 0). High-liquidity filter is a sensible pairing because high-liquidity names have tighter spreads and cleaner BE behavior. Recommend Synthesizer pair this with proven long-side high-liquidity entries (E051 pc_high_liquidity_long, E126) where the BE timing change can demonstrably improve over the -0.08 floor. Caveat for Synthesizer: monitor that 'liquidity_bucket=high' alone is a thin novel_dim — if the BE-timing parameters are not exposed in the search grid, this archetype risks collapsing onto X100. Recommend ensuring be_trigger_pct and be_activation_seconds are both swept."
    }
  ]
}
```

### risk
```json
{
  "summary": "Exit-side breakeven variant with high-liquidity filter; no integrity issues identified, standard advisory monitoring only.",
  "risk_assessments": [
    {
      "archetype_ref": "x104_breakeven_strict_30s_exit",
      "leakage_risk": "none",
      "leakage_notes": "novel_dim is liquidity_bucket=high (a static/contemporaneous regime tag, not post-T0); 30s activation timer is forward-running from T0, which is causal not leaky. No forward_*, confirm_after_*, or post_event_* fields present.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit-side archetype with NA channel/side does not generate entry positions and cannot conflict with the live BWE_OI_Price_monitor pump long strategy.",
      "concentration_risk": "low",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "None required. Advisory: confirm the 30s breakeven activation clock is computed from T0 forward (not retroactively) at implementation time, and that liquidity_bucket=high is bucketed using only data available at or before T0."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "x104_breakeven_strict_30s_exit",
  "predicted_tp_pct": 1.2,
  "predicted_sl_pct": 0.0,
  "predicted_tp_sl_ratio": null,
  "predicted_win_rate": 0.42,
  "predicted_mean_per_trade_pct": -0.05,
  "predicted_kelly_pct": 0.0,
  "trap_risk": "medium",
  "trap_reasoning": "This is an EXIT archetype using the breakeven kernel, not an entry. The breakeven family currently clusters at a -0.08 floor (median -0.0805, max -0.080519, n_positive=0 across 1923 results) — a structural ceiling, not a TP/SL geometry trap. Tightening BE activation to 30s with strict trigger reduces the SL to ~0 (BE moves stop to entry once activated), so geometry is asymmetric in the OPPOSITE direction of E126: capped downside, open upside via TP or runner. Risk: BE activation at 30s is short — many trades won't have moved enough to lock in, and premature BE cuts winners that would have reverted-then-resumed, dragging mean toward small negatives near the -0.08 family floor. Win rate likely 40-45% (BE flat-outs count as ~0, true wins need TP hit). Kelly = 0 because expected per-trade likely still slightly negative net of -8 bps cost; this archetype probably IMPROVES on the breakeven floor but unlikely to break into positive expectancy without pairing with a selective entry filter. The trap-risk dimension here is 'looks novel but stays in negative-expectancy cluster' rather than the E126 asymmetric-TP/SL trap.",
  "recommended_constraint": "pair this exit archetype with entry filter requiring liquidity_bucket=high AND trigger_strength≥p75; also test BE activation at 60s/90s in variant grid to find whether 30s is too aggressive",
  "metric_score_estimate": 0.5
}
```

## Proposal 18: `x105_hybrid_fixed_then_trail_exit`

### proposal
```json
{
  "archetype": "x105_hybrid_fixed_then_trail_exit",
  "type": "exit",
  "channel": "NA",
  "side": "NA",
  "novel_dim": [
    "taker_buy_ratio_5m>=0.60"
  ],
  "notes": "Hybrid: take 50% at fixed 0.5% TP, trail remaining 50% with 1.5% step — symmetric risk/reward.",
  "rationale": "Hybrid composition combining fixed + trail families is a NEW exit family per quality bar #3; not present in 101 existing exits which are mono-family.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "x105_hybrid_fixed_then_trail_exit",
  "best_case_thesis": "In pump regimes the price-action signature is a fast initial impulse followed by either a sharp mean-revert or a multi-leg continuation — a bimodal payoff that single-family exits cannot harvest. Locking 50% at a tight fixed TP monetizes the high-probability initial impulse (which paper-shadow on E126 showed materializes ~80% of the time) while trailing the remaining 50% with a wide step keeps a free option on the continuation tail, turning the asymmetric TP/SL trap that killed E126 paper-shadow into a structurally symmetric outcome. This directly addresses the R2 lesson: the failure was not entry edge but exit shape.",
  "expected_alpha_source": "Bimodal post-impulse return distribution in taker-buy-driven pumps: a high-probability small-magnitude reversion mode plus a low-probability large-magnitude continuation mode that mono-family exits systematically misprice.",
  "edge_strength_estimate": "strong",
  "regime_match": "High-volume pump regimes with elevated taker_buy_ratio_5m where initial impulse follow-through is bimodal — exactly the regime in which top entries (E126, E064, E148) trigger.",
  "complementary_exit_families": [
    "fixed",
    "trail"
  ],
  "complementary_existing_archetypes": [
    "E126",
    "E064",
    "E148",
    "E051",
    "E066"
  ],
  "if_paper_works_likely_reason": "The 50% fixed leg locks realized PnL before the asymmetric SL can dominate, converting E126-class entries from negative-compounding p25 traps into positive-mean kelly-capped survivors.",
  "could_compound_with": "Any other x10x exit-side proposal that introduces partial-fill or scale-out logic, plus any risk wrapper that caps per-trade SL — together they would form the missing exit-pipeline scaffold the R2 synthesizer flagged."
}
```

### devil
```json
{
  "summary": "Hybrid fixed+trail exit is conceptually novel but the proposed parameterization combined with an entry-side filter on an exit archetype raises specific concerns worth monitoring.",
  "critiques": [
    {
      "archetype_ref": "x105_hybrid_fixed_then_trail_exit",
      "verdict": "possibly_fail",
      "concerns": [
        "novel_dim 'taker_buy_ratio_5m>=0.60' is an entry-side condition embedded in an exit archetype — semantically mismatched: an exit kernel evaluates after entry has fired, so this filter either (a) reapplies at exit time (likely no-op or look-ahead-ish if it inspects future ticks) or (b) gets silently coerced as an entry filter, collapsing this back into a duplicate of an entry baseline (same R1 bug class noted in lessons_from_r1_r2).",
        "Asymmetric TP/SL trap risk: 0.5% fixed TP on 50% + trailing 1.5% step on remainder is implicitly asymmetric vs whatever stop-loss is paired downstream — R2 already documented E126's TP=0.51/SL=6.00 compounding to -13.5% despite +0.3946 score. Without an explicit SL bound in the proposal, mean/kelly_capped metrics could still mask left-tail blowups.",
        "by_exit_family table shows trail family mean=-0.150, multi_tp mean=-0.276 — both currently unprofitable on their own across 6,222 results. Hybridizing two losing families does not automatically yield a winner; needs evidence that the 50/50 split materially changes the trade distribution rather than averaging two negative expectancies.",
        "Trail step of 1.5% on the remaining 50% is large relative to a 0.5% first-leg TP — for a $1000 account at modest leverage, a 1.5% adverse move post-first-TP can wipe the locked-in gain net of 8–16 bps round-trip costs, leaving the hybrid statistically indistinguishable from fixed-only at 0.5%."
      ],
      "monitoring_advice": "During paper-shadow: (1) verify the taker_buy_ratio_5m>=0.60 filter is actually being evaluated at the exit kernel and not silently dropped — log filter-hit rate; (2) track the second-leg (trailing 50%) PnL distribution separately from the first-leg fixed TP, and confirm the trail leg has positive expectancy on its own — if not, the hybrid degrades to fixed-only-with-overhead; (3) compute mean, kelly_capped, and p25_capped_tail (per R2 lesson) — do not rely on median/p25 alone; (4) compare against a pure fixed-0.5%-TP baseline on the same trigger set to confirm the trail leg adds rather than subtracts edge."
    }
  ]
}
```

### quant
```json
{
  "summary": "Exit-family hybrid proposal is structurally novel relative to mono-family exits, but its single novel_dim filter is supported and yields adequate sample; flag that hybrid composition isn't a filter concern — execution will need kernel-level support.",
  "analyses": [
    {
      "archetype_ref": "x105_hybrid_fixed_then_trail_exit",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Existing 101 exits are mono-family (fixed | time_only | breakeven | trail | multi_tp). This proposal composes fixed+trail with a 50/50 split — structurally a new exit family per R2 synthesizer's identified gap (X101+ exit-side starvation). The single novel_dim taker_buy_ratio_5m>=0.60 acts as an entry-side gate but the archetype's novelty is in the exit composition, not the filter.",
      "expected_triggers_30d": 2000,
      "triggers_estimate_method": "Exit archetypes are channel-agnostic (channel=NA), so denominator ≈ all events ~7200/30d. Filter taker_buy_ratio_5m>=0.60 is a moderate buy-side bias (roughly top ~30-40% of taker ratio distribution given crypto baseline ~0.50): 7200 × 0.30 ≈ 2160. Conservatively round to 2000.",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Hybrid fixed+trail requires a NEW kernel — none of the 5 live exit kernels (fixed / time_only / breakeven / trail / multi_tp) natively support partial-fill TP then trail-on-remainder. multi_tp is closest (laddered TPs) but doesn't trail residual. Quant flag for Synthesizer: filter math is clean and sample is ample, but execution feasibility depends on whether a hybrid kernel exists or can be added. If forced into existing kernels, this collapses to either pure fixed or pure trail. Given R2's by_exit_family stats (fixed: mean +0.175, n_positive 6680/7320; trail: mean -0.150, all negative), a hybrid that captures fixed's left-tail protection while retaining trail's upside is theoretically attractive — but only if the kernel actually executes the composition. Recommend Synthesizer accept conditional on kernel availability; otherwise downgrade to multi_tp approximation."
    }
  ]
}
```

### risk
```json
{
  "summary": "Hybrid fixed+trail exit composition is research-integrity sound; the only flag is the taker_buy_ratio_5m field requiring the 5m window to be pre-T0, which is a verification item not a leakage finding.",
  "risk_assessments": [
    {
      "archetype_ref": "x105_hybrid_fixed_then_trail_exit",
      "leakage_risk": "low",
      "leakage_notes": "novel_dim uses taker_buy_ratio_5m>=0.60. The naming suffix '_5m' is ambiguous: if it denotes the trailing 5m window ending at T0 (lookback) it is clean; if it denotes a 5m window starting at T0 (lookahead) it would be post-T0 and leak. Given the SUPPORTED_FIELDS enforcement post-R1 and that taker_buy_ratio_5m is part of the standard pre-T0 microstructure feature set, treating as low rather than block. Verification: confirm the field's window is [T0-5m, T0], not [T0, T0+5m].",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit-side archetype with no entry directionality (channel=NA, side=NA); cannot generate positions that conflict with the live BWE_OI_Price pump-long monitor — it only governs exit composition for whatever entry it is paired with.",
      "concentration_risk": "low",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "Confirm in code review that taker_buy_ratio_5m is computed over the trailing window ending at T0 (not the forward window). If the implementation accidentally uses the forward 5m window, escalate to block — but the field name alone is not sufficient evidence of leakage given the post-R1 SUPPORTED_FIELDS gate."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "x105_hybrid_fixed_then_trail_exit",
  "predicted_tp_pct": 0.5,
  "predicted_sl_pct": 1.0,
  "predicted_tp_sl_ratio": 0.5,
  "predicted_win_rate": 0.55,
  "predicted_mean_per_trade_pct": 0.1,
  "predicted_kelly_pct": 1.0,
  "trap_risk": "low",
  "trap_reasoning": "This is an EXIT archetype proposing a hybrid composition (50% fixed TP at 0.5%, 50% trailing with 1.5% step). Unlike entry archetypes that inherit GPU-optimized TP/SL geometry, this proposal explicitly DEFINES the exit geometry as approximately symmetric: half the position locks in a quick 0.5% gain, the other half rides with a 1.5% trailing stop. This caps left-tail blow-ups because the trailing stop on the remaining 50% prevents catastrophic single-trade losses (max loss ~1.5% on the trailing half, locked profit on the fixed half). The effective TP/SL ratio is roughly 0.5 (much healthier than E126's 0.085), so even at moderate win rates (~55%) the expectancy stays positive. Crucially, this is the OPPOSITE of the E126 trap: instead of asymmetric small-wins/big-losses, it builds in asymmetric small-locked-wins/bounded-losses. The taker_buy_ratio>=0.60 filter is mild and doesn't dramatically narrow triggers. Main uncertainty: 'hybrid' family does not yet exist in the 5 real exit kernels (fixed/time_only/breakeven/trail/multi_tp) — implementation must compose two kernels, which may not match any of the 3111 trail or 7320 fixed records cleanly. Worth flagging to the synthesizer that the 'expected_distinct=true' claim is correct (genuinely new family) but executability depends on whether the kernel grid supports 50/50 split sizing.",
  "recommended_constraint": "In variant grid, force fixed_tp_pct ≤ trail_step_pct and require split_ratio in [0.3, 0.7] so neither leg dominates; also clamp fixed_tp_pct ≥ 0.3% to avoid degenerate scalp-half that taxes fees.",
  "metric_score_estimate": 5.5
}
```

## Proposal 19: `cc_pc_oi_within_60s_double_long`

### proposal
```json
{
  "archetype": "cc_pc_oi_within_60s_double_long",
  "type": "cross_channel",
  "channel": "*",
  "side": "long",
  "novel_dim": [
    "taker_buy_ratio_5m>=0.60",
    "liquidity_bucket=high",
    "oi_change_pct>=8"
  ],
  "notes": "Pricechange and OI_Price both fire within 60 seconds with taker_buy confirmation — tight double-channel timing window.",
  "rationale": "60-channel cross_channel timing has not been tested with <2m windows per quality bar #4; existing cc_*_5m archetypes use looser windows that saturate at baseline.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "cc_pc_oi_within_60s_double_long",
  "best_case_thesis": "When pricechange and OI_Price both fire within a 60-second window with taker_buy_ratio_5m>=0.60, you are observing simultaneous spot-driven price impulse AND derivatives-side new-position accumulation — that is the signature of fresh leveraged longs piling onto a spot-led move, not stale carry. Existing cc_*_5m archetypes saturate at baseline precisely because a 5-minute window pools together causally-unrelated fires; tightening to 60s isolates the rare regime where both books agree in real time, which historically front-runs continuation legs before late longs and shorts-getting-squeezed amplify the move.",
  "expected_alpha_source": "Real-time agreement between spot-flow (taker buy dominance) and derivatives positioning (OI expansion) within a sub-minute window — a microstructure signature of conviction-driven entry that precedes momentum ignition, distinct from passive carry or mean-reversion noise that dominates wider windows.",
  "edge_strength_estimate": "strong",
  "regime_match": "High-liquidity trending or breakout regimes where derivatives lead/confirm spot impulses; maximally effective when funding is neutral-to-slightly-positive (room for short squeeze) and BTC is not in macro distribution.",
  "complementary_exit_families": [
    "fixed"
  ],
  "complementary_existing_archetypes": [
    "E126",
    "E051",
    "E064"
  ],
  "if_paper_works_likely_reason": "The 60s tight-window filter successfully isolates the subset of cross-channel fires where both books are causally linked rather than coincident, producing a higher-conviction entry trigger than any single-channel pump signal alone.",
  "could_compound_with": "Any proposal that adds a liquidation-cascade or short-squeeze confirmation layer on top would compound — the dual-channel timing identifies conviction; a squeeze-fuel filter would identify when that conviction meets forced-buying tailwind."
}
```

### devil
```json
{
  "summary": "Cross-channel 60s double-fire long with 3-way filter conjunction is worth testing but carries concrete sample-size, regime, and live-strategy-overlap risks.",
  "critiques": [
    {
      "archetype_ref": "cc_pc_oi_within_60s_double_long",
      "verdict": "possibly_fail",
      "concerns": [
        "Sample-size fragility: 4-way conjunction (cross-channel 60s coincidence AND taker_buy_ratio_5m>=0.60 AND liquidity_bucket=high AND oi_change_pct>=8) is highly restrictive — likely trigger count well below the ~1000 baseline seen in E148. Coverage preview shows top entries at trig=988–5000; tightening the cross-channel window from cc_*_5m to <60s on top of three filters could collapse triggers under any minimum-sample threshold and produce noisy score estimates.",
        "Overlap with live BWE_OI_Price_monitor pump long: this archetype fires precisely when OI_Price + pricechange both confirm with taker_buy + high liquidity — i.e. exactly the conditions under which the user's existing pump-long is most likely already active. Risk of unintentional position doubling / correlated drawdown rather than orthogonal alpha.",
        "Asymmetric TP/SL trap echo (R2 lesson on E126): this is structurally a confirmed-pump long (high taker_buy, high liquidity, rising OI) — the same setup family that compounded to -13.5% on $1000 paper despite 80% win rate. Strong setups that win small and lose big are exactly where legacy p25 lies. Must be scored under mean / kelly_capped / p25_capped_tail, not legacy p25.",
        "Regime dependence: taker_buy_ratio_5m>=0.60 + oi_change_pct>=8 is a strongly directional bullish-confirmation gate; 30-day backtest window may not contain a meaningful BTC chop/down regime, so the edge could be regime-fitted rather than robust.",
        "Possible filter redundancy: OI_Price channel firing already implies an OI move; layering oi_change_pct>=8 on top may either be no-op (channel trigger threshold already exceeds 8) or shrink triggers further with little new information — worth measuring marginal trigger reduction from this filter alone."
      ],
      "monitoring_advice": "During paper-shadow: (1) report raw trigger count and discard if <300 over 30d; (2) track overlap-rate with live BWE_OI_Price_monitor pump-long fires (timestamp intersection) and flag if >40% co-fire; (3) require kelly_capped and p25_capped_tail to both be positive — do not promote on mean alone given R2 E126 precedent; (4) split metrics by BTC regime bucket if available to test regime-fitting; (5) ablate oi_change_pct>=8 to confirm it adds marginal lift rather than just reducing N."
    }
  ]
}
```

### quant
```json
{
  "summary": "Cross-channel double-fire archetype with 2/3 conditions parseable; sample size adequate but the 60s timing window itself is unparseable and will be ignored by the filter, so the archetype reduces to taker_buy + high_liquidity + oi_change_pct≥8 — still distinct enough to test.",
  "analyses": [
    {
      "archetype_ref": "cc_pc_oi_within_60s_double_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E126",
        "E064",
        "E051"
      ],
      "distinctness_notes": "E126/E064 are pricechange-only with taker_buy_extreme/dominant; E051 is pricechange high-liquidity. None combine taker_buy_ratio_5m>=0.60 AND liquidity_bucket=high AND oi_change_pct>=8 as a conjunction. The cross_channel framing plus the OI magnitude threshold (≥8%) materially narrows vs existing cc_*_5m archetypes which the rationale notes saturate at baseline. GPU optimization will reveal a different TP/SL surface.",
      "expected_triggers_30d": 140,
      "triggers_estimate_method": "Base: cross_channel proposals nominally draw from union but filter parser treats this as a flat conjunction over whichever channel fires. Estimating from OI_Price base ~1400/30d (since oi_change_pct>=8 is the binding constraint and only fires on OI events): 1400 × ~0.35 (oi_change_pct>=8 is moderately tight, top ~third of OI events) × ~0.5 (liquidity_bucket=high cut) × ~0.6 (taker_buy_ratio_5m>=0.60 on long-leaning OI events) ≈ 147. Conservative round to ~140.",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "All 3 conditions are in SUPPORTED_FIELDS (taker_buy_ratio_5m, liquidity_bucket, oi_change_pct all listed in section A/C). HOWEVER: the archetype's defining feature — the '60s cross-channel timing window' — is NOT expressible in the filter DSL (no pc_then_oi_*, no confirm_within_*, no cross-channel chain operators per SUPPORTED_FIELDS section D-skip list). The notes/rationale describe a temporal join the parser cannot enforce, so the archetype effectively executes as a static 3-condition AND filter on whichever channel fires. Synthesizer should be aware: this is NOT actually testing the 60s double-fire hypothesis, just a high-bar OI+taker+liquidity conjunction. Best paired with fixed exit family (the only family showing positive mean/median in coverage: mean=+0.175, median=+0.217, n_positive=6680/7320); avoid time_only/breakeven/multi_tp/trail which all show negative central tendency. Given E126's R2 paper trap (backtest +0.39 → -13.5% live with TP=0.51/SL=6.00), recommend Synthesizer constrain to symmetric or capped-asymmetry TP/SL grids and use mean / kelly_capped / p25_capped_tail metrics rather than legacy p25."
    }
  ]
}
```

### risk
```json
{
  "summary": "Cross-channel 60s double-trigger long proposal uses only supported pre-T0 fields and presents no integrity blockers; standard live-overlap and FWER monitoring apply.",
  "risk_assessments": [
    {
      "archetype_ref": "cc_pc_oi_within_60s_double_long",
      "leakage_risk": "low",
      "leakage_notes": "novel_dim fields (taker_buy_ratio_5m, liquidity_bucket, oi_change_pct) are all in the SUPPORTED_FIELDS set used by E126 and prior keepers, and the 'within_60s' window is a backward co-occurrence constraint between two T0-or-earlier channel fires — no forward_*, post_event_*, or confirm_after_* references. Only residual concern: the '_5m' suffix on taker_buy_ratio must remain a trailing 5m lookback (as in R2 E126); if any future kernel rewires it as a forward window the leak would be invisible. No action needed at proposal stage.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "Long-side cross-channel rule on '*' channel will fire on the same symbols as the user's live BWE_OI_Price_monitor pump long — when both pricechange and OI_Price fire within 60s with oi_change_pct>=8, this is precisely the regime where the live strategy is also entering. Risk is duplicate same-side stacking (capital concentration on one symbol, not opposite-side conflict). Paper-shadow only per Round 3 posture; flag for monitoring, not blocking.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "In paper-shadow logs, tag any trigger that co-occurs (within ±60s, same symbol) with a live BWE_OI_Price pump-long entry, and track whether the cc_* archetype's marginal lift survives after deduplicating those overlap events. Also confirm in the kernel registry that taker_buy_ratio_5m is wired to the trailing-5m computation (not a forward window) before this archetype enters any keeper promotion."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "cc_pc_oi_within_60s_double_long",
  "predicted_tp_pct": 0.7,
  "predicted_sl_pct": 2.1,
  "predicted_tp_sl_ratio": 0.33,
  "predicted_win_rate": 0.68,
  "predicted_mean_per_trade_pct": -0.28,
  "predicted_kelly_pct": 0.0,
  "trap_risk": "medium",
  "trap_reasoning": "Cross-channel confluence (PC + OI within 60s + taker_buy>=0.60 + high_liq + oi_change>=8) is a genuinely selective filter and likely produces above-baseline win rate (~0.66-0.70). However, this is exactly the regime where the GPU optimizer historically converges on asymmetric geometry: a long entry on a confirmed pump tends to give back small wins quickly while the occasional adverse move runs to a wide SL (the same dynamic that produced the E126 trap at TP=0.51/SL=6.00, W=80%). My base TP/SL prediction of 0.7/2.1 (ratio 0.33) yields E[trade] = 0.68*0.7 - 0.32*2.1 - 0.08 = -0.276%, i.e. negative expectancy despite high win rate — classic p25-positive / mean-negative trap shape. The confluence quality is real, but only the optimizer's geometry choice determines whether that alpha is captured. Uncertainty on win-rate is moderate (±0.05) and on SL is high (±0.6); if optimizer lands at SL≤1.4×TP the proposal can flip positive. Without a ratio constraint, expected kelly_capped score is ~0; with constraint, expected ~3-4.",
  "recommended_constraint": "force SL_pct <= 1.5 * TP_pct in variant grid; also require TP_pct between 0.6 and 1.5 to keep geometry symmetric and prevent optimizer from chasing W>=0.78 via wide SL",
  "metric_score_estimate": 2.5
}
```

## Proposal 20: `cc_three_signal_funding_neutral_long`

### proposal
```json
{
  "archetype": "cc_three_signal_funding_neutral_long",
  "type": "cross_channel",
  "channel": "*",
  "side": "long",
  "novel_dim": [
    "funding>=-0.0001",
    "funding<=0.0001",
    "taker_buy_ratio_5m>=0.60",
    "liquidity_bucket=high"
  ],
  "notes": "Three-channel alignment requiring funding-neutral regime — avoids crowded-trade traps.",
  "rationale": "Existing cc archetypes do not condition on funding-neutral; novel weighting that filters out funding-driven moves is structurally distinct.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "cc_three_signal_funding_neutral_long",
  "best_case_thesis": "Three-channel alignment (OI_Price + pricechange + Reserved6 firing in concert) is already a high-conviction signal that real flow is moving the tape; gating it on funding-neutral (|funding| <= 1bp) surgically excludes the dominant failure mode of cross-channel longs — entering AFTER perp-driven crowded longs have inflated funding, where the move is mostly squeeze-exhaustion rather than spot-led demand. Combined with taker_buy_ratio_5m >= 0.60 and high-liquidity bucket, this isolates the rare regime where aggressive market-buy aggression coincides with NO crowded-perp-long premium — i.e. spot-led, organic momentum that has runway because shorts haven't been wiped yet and longs haven't paid up.",
  "expected_alpha_source": "Funding-neutral filter eliminates the post-squeeze 'late-long' trap where cross-channel triple alignment is a coincident lagging indicator of an already-extended perp-crowded move; what remains is spot-flow-led continuation before perp positioning rebuilds.",
  "edge_strength_estimate": "strong",
  "regime_match": "Early-to-mid trend-day regimes where spot CVD is leading perps and funding hasn't yet repriced — typically the first 1-3 hours of a directional impulse, or post-deleveraging reset windows when funding has just normalized through zero.",
  "complementary_exit_families": [
    "fixed",
    "trail"
  ],
  "complementary_existing_archetypes": [
    "E126",
    "E064",
    "E051",
    "E148"
  ],
  "if_paper_works_likely_reason": "The funding-neutral gate will dramatically lower trigger count but raise per-trade quality because each surviving signal represents a structurally rare convergence (three-channel + aggressive taker flow + uncrowded perp book) that historically precedes multi-leg continuation rather than mean-reversion.",
  "could_compound_with": "Any cross-channel SHORT proposal that conditions on funding>=+0.0003 (crowded-long exhaustion) — together they would partition the cc namespace by funding regime, giving the synthesizer a clean long/short funding-conditional pair instead of overlapping cc archetypes."
}
```

### devil
```json
{
  "summary": "Single-proposal deep review: funding-neutral cross-channel long is structurally sound but has specific monitoring concerns around funding field availability at T0 and trigger rarity.",
  "critiques": [
    {
      "archetype_ref": "cc_three_signal_funding_neutral_long",
      "verdict": "possibly_fail",
      "concerns": [
        "Funding rate is published on an 8-hour cycle on Binance perps — the 'funding' field at T0 is the last-settled rate, not a live instantaneous value. A funding-neutral band of [-0.0001, +0.0001] (±1bp per 8h) is extremely tight and most symbol-hours sit OUTSIDE this band during any directional regime, so trigger count may be very low (likely <300 across 30 days, risking the same small-sample fragility that hurt E148 at trig=988).",
        "Cross-channel alignment ('three_signal') already implies a rare co-occurrence; stacking funding-neutral on top compounds rarity multiplicatively. If the three-channel base rate is ~1-2% of bars and funding-neutral is ~20-30% of bars, expected trigger rate is ~0.2-0.6% — borderline for stable estimation given 30-day window.",
        "Funding-neutral + taker_buy_ratio_5m>=0.60 + liquidity_bucket=high is a LONG bias (taker buy dominance) with a regime filter that REMOVES the strongest long-funding tailwind cases. This may select for mean-reversion-style longs in calm regimes — the opposite micro-structure of E126/E064 winners which thrive on taker-buy extremes during directional moves. Worth confirming whether the proposal is hunting a different alpha source than the dominant pricechange/long cluster."
      ],
      "monitoring_advice": "During paper-shadow: (1) log actual trigger count per day — abort/flag if <5/day average. (2) Check whether funding field is being read as last-settled snapshot vs forward-looking estimate; if forward-looking, flag as potential look-ahead. (3) Compare hit-rate split by |funding| quartile within the neutral band — if all alpha concentrates at one edge of [-0.0001, +0.0001], the band is mis-specified. (4) Verify this archetype's winners do NOT overlap >70% with E126/E064 trigger times — if they do, it's not structurally distinct despite the novel_dim claim."
    }
  ]
}
```

### quant
```json
{
  "summary": "Proposal is structurally distinct and parseable but conditions are well-supported individually; cross-channel triple-alignment combined with narrow funding-neutral band makes triggers tight to too_few — recommend pairing with fixed exit family.",
  "analyses": [
    {
      "archetype_ref": "cc_three_signal_funding_neutral_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "existing cc_* archetypes (60 cross_channel)"
      ],
      "distinctness_notes": "No existing cross_channel archetype conditions on a funding-neutral band (|funding|<=0.0001) AND requires taker_buy_ratio_5m>=0.60 AND liquidity_bucket=high simultaneously. The funding-neutral band is a novel filter dimension for cross-channel — most cc archetypes either ignore funding or use funding extremes. Combined with taker-buy dominance and high-liquidity gating, this carves out a distinct slice: aligned three-channel signal in a non-crowded funding regime with active aggressive-buy flow on liquid names. The 'avoid crowded-trade trap' thesis is structurally novel vs the existing 60 cc archetypes.",
      "expected_triggers_30d": 60,
      "triggers_estimate_method": "Cross-channel '*' with three-signal alignment baseline ~ min(OI_Price, pricechange, Reserved6) overlap ≈ 800 candidate alignment events × funding-neutral band (|funding|<=0.0001 is a tight ~p25-p40 window ≈ 0.20 retention) × taker_buy_ratio_5m>=0.60 (≈ 0.30 retention, top ~30% of taker imbalance) × liquidity_bucket=high (≈ 0.40 retention) × long-only (no further cut, side filter) = 800 × 0.20 × 0.30 × 0.40 ≈ 19. However, if 'three-signal' is interpreted as any-channel-with-confirmation rather than strict triple-overlap, baseline rises to ~3000 confirm-events × 0.20 × 0.30 × 0.40 ≈ 72. Conservative midpoint: ~60.",
      "sample_size_verdict": "tight",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 4,
      "n_total_conditions": 4,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Given funding-neutral + aggressive taker buy + high liquidity long thesis, the move is expected to be momentum-continuation but without funding-driven squeeze fuel — implies modest, mean-reverting-prone targets. Coverage shows fixed is the ONLY exit family with positive mean (0.175) and 6680/7320 positive runs; multi_tp/trail/time_only/breakeven all negative across 20K results. Strongly recommend fixed exit with conservative TP (0.6-1.2%) and tight SL (0.8-1.5%) symmetric to avoid the E126 asymmetric-TP/SL trap. Avoid time_only and multi_tp entirely. Breakeven could be a secondary candidate for protecting the small expected edge but historical data shows it underperforms fixed."
    }
  ]
}
```

### risk
```json
{
  "summary": "Single cross-channel funding-neutral long proposal with no integrity issues; standard advisory monitoring applies.",
  "risk_assessments": [
    {
      "archetype_ref": "cc_three_signal_funding_neutral_long",
      "leakage_risk": "none",
      "leakage_notes": "All four novel_dim fields (funding band, taker_buy_ratio_5m, liquidity_bucket) are point-in-time at T0 with no forward_*, post_event_*, or confirm_after_* references. taker_buy_ratio_5m is a trailing 5m window ending at T0, not a forward window — clean.",
      "multitest_inflation_risk": "low",
      "multitest_inflation_notes": "60 cross_channel archetypes already exist, but funding-neutral conditioning is structurally novel within that family; marginal FWER contribution is small relative to the 523-archetype registry.",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Long-side cross-channel rule could co-fire with the user's live BWE_OI_Price_monitor pump-long strategy on the same symbol, stacking exposure rather than opposing it. At 5–10% sizing this is a position-sizing/concentration concern, not a hedge conflict — paper-shadow monitoring item.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Advisory only: during paper-shadow, log overlap windows with live pump-long strategy and cap aggregate same-symbol exposure; verify funding/taker_buy/liquidity snapshots are sourced from T0-or-earlier bars in the kernel, not the post-event window."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "cc_three_signal_funding_neutral_long",
  "predicted_tp_pct": 0.6,
  "predicted_sl_pct": 1.5,
  "predicted_tp_sl_ratio": 0.4,
  "predicted_win_rate": 0.62,
  "predicted_mean_per_trade_pct": 0.012,
  "predicted_kelly_pct": 1.7,
  "trap_risk": "low",
  "trap_reasoning": "This is a tightly-filtered cross-channel long requiring three simultaneous conditions: funding in a narrow neutral band [-0.0001, 0.0001], taker_buy_ratio_5m >= 0.60, and high liquidity. The funding-neutral constraint is the structurally important one — it explicitly filters out crowded/funding-driven moves where overshoots and violent mean-reversions create the asymmetric TP/SL trap (the E126 pattern lived in heavy-funding pump regimes). With high liquidity + funding-neutral + buy-pressure confirmation, the realized move distribution should be tighter and more symmetric, so the GPU optimizer is unlikely to converge on a degenerate TP=0.5 / SL=6 geometry. I expect TP~0.6%, SL~1.5% (ratio ~0.4) with win-rate ~62% — modestly above breakeven but not heroic. Tight 4-condition AND filter likely yields low trigger count (estimate 200-600), which raises sample-size uncertainty more than trap-geometry uncertainty. Mean per-trade ~+1.2 bps after -8 bps cost is positive but thin; Kelly ~1.7% reflects the modest edge. Trap risk is LOW because the entry thesis itself rules out the regime that produced the trap, and the natural geometry is roughly symmetric.",
  "recommended_constraint": "force SL <= 2.5 x TP_pct in variant grid to keep geometry symmetric and prevent optimizer drift toward asymmetric tail-eating configs",
  "metric_score_estimate": 1.7
}
```

## Proposal 21: `r_kelly_safe_size_filter`

### proposal
```json
{
  "archetype": "r_kelly_safe_size_filter",
  "type": "risk",
  "channel": "*",
  "side": "both",
  "novel_dim": [
    "liquidity_bucket=high",
    "taker_buy_ratio_5m>=0.60"
  ],
  "notes": "Risk archetype enforcing position size only when both liquidity and taker_buy confirm — kelly-safe sizing.",
  "rationale": "Existing 40 risk archetypes don't combine liquidity + taker_buy as size-gating AND; novel sizing filter with natural TP/SL symmetry to dodge E126-style asymmetric trap.",
  "expected_distinct": true
}
```

### steelman
```json
{
  "archetype_ref": "r_kelly_safe_size_filter",
  "best_case_thesis": "This archetype attacks the exact failure mode that destroyed E126 in paper-shadow: asymmetric TP/SL traps that pass legacy p25 metrics but compound negatively due to fat left tails. By gating position size on the AND of high liquidity (which suppresses slippage on both entry and stop-out) AND elevated taker_buy_ratio (which confirms genuine aggressive-buy flow rather than passive book-stacking), it only deploys full Kelly-capped size when BOTH the execution-quality precondition AND the directional-conviction precondition hold simultaneously — a structurally different bet than any of the 40 existing risk archetypes. The mechanistic insight is that left-tail blowups in BWE signals correlate with low-liquidity tape (wide spreads → SL gets gapped through) far more than with weak directional signal, so liquidity is the dominant size-gate, with taker_buy as the conviction multiplier.",
  "expected_alpha_source": "Slippage-asymmetry on stop-outs in low-liquidity regimes — full size in those conditions converts a -SL into a -2*SL realized loss, and gating size to high-liquidity windows directly recovers that leak.",
  "edge_strength_estimate": "strong",
  "regime_match": "Maximally effective in mid-volatility regimes with healthy book depth (post-news consolidation, mid-session US/EU overlap) where taker flow is informative; degrades in thin Asian session or during BTC-led liquidation cascades where liquidity evaporates faster than the filter can react.",
  "complementary_exit_families": [
    "fixed",
    "breakeven"
  ],
  "complementary_existing_archetypes": [
    "E051",
    "E126",
    "E064"
  ],
  "if_paper_works_likely_reason": "It will pass paper-shadow specifically because the kelly_capped and p25_capped_tail metrics will reward the truncated left tail that high-liquidity gating produces, whereas full-size unfiltered variants get penalized by the same metrics — the archetype is essentially co-designed with the new R2 scoring fix.",
  "could_compound_with": "Stacks naturally with any pricechange/long pump-confirmation entry (E126, E064, E148) by acting as a size-overlay rather than a competing entry signal — and pairs with fixed-TP exits to preserve the symmetric TP/SL profile that dodges the E126 asymmetric trap."
}
```

### devil
```json
{
  "summary": "Proposal is logically coherent and addresses the R2 asymmetric-trap lesson, but its 'risk' typing is ambiguous and the AND-gate on two correlated bullish signals likely biases it toward long-only regimes despite side=both.",
  "critiques": [
    {
      "archetype_ref": "r_kelly_safe_size_filter",
      "verdict": "possibly_fail",
      "concerns": [
        "Type=risk with novel_dim that are entry-condition fields (liquidity_bucket, taker_buy_ratio_5m) — risk kernel typically governs sizing/SL, not entry gating; if the loop interprets these as entry filters the archetype collapses into a duplicate of existing E051 (pc_high_liquidity_long) ∩ E064 (pc_pump_taker_buy_dominant) rather than a distinct risk dimension.",
        "side=both with taker_buy_ratio_5m>=0.60 is asymmetric: top entries E126/E064/E148 show taker-buy-dominant conditions cluster on long/pump regimes; the same 0.60 threshold applied to shorts will fire rarely or only in counter-trend traps, so 'both' coverage is nominal not real.",
        "liquidity_bucket=high AND taker_buy_ratio_5m>=0.60 are positively correlated in pump regimes — the AND-gate may not reduce trigger count enough to deliver the kelly-safe property; need to verify post-filter trigger count is materially below the ~3000-5000 range seen on E064/E126 before claiming it dodges asymmetric tails.",
        "'Natural TP/SL symmetry' is asserted in notes but not encoded in novel_dim — symmetry must come from the paired exit kernel choice (fixed with TP≈SL), not from the entry/risk filter itself. If downstream pairs this with the same asymmetric TP=0.51/SL=6.00 family that trapped E126, the filter doesn't help."
      ],
      "monitoring_advice": "During paper-shadow: (1) log per-side trigger counts to confirm short-side actually fires, (2) compare p25_capped_tail and kelly_capped against E051/E064 baselines to verify the AND-gate adds incremental left-tail protection rather than just intersecting two known-good entry filters, (3) only pair with symmetric fixed-exit kernels (TP/SL ratio within 1.5x) to preserve the stated kelly-safe intent."
    }
  ]
}
```

### quant
```json
{
  "summary": "Risk archetype r_kelly_safe_size_filter is mathematically sound — both novel_dim conditions parse cleanly (liquidity_bucket categorical + taker_buy_ratio_5m numeric), structurally distinct from existing 40 risk archetypes (no prior combines liquidity AND taker_buy as conjunctive size-gate), with adequate-to-ample expected sample size and broad exit compatibility favoring the proven fixed-exit family.",
  "analyses": [
    {
      "archetype_ref": "r_kelly_safe_size_filter",
      "distinct": true,
      "distinct_from_existing_ids": [
        "R001-R040 (no existing risk archetype documented as combining liquidity_bucket=high AND taker_buy_ratio_5m>=0.60 as conjunctive size-gating filter)"
      ],
      "distinctness_notes": "Distinct on two axes: (1) conjunctive AND of a categorical liquidity gate with a continuous taker-flow threshold for sizing rather than entry filtering; (2) framed as kelly-safe size enforcement, which targets the R2-identified E126 asymmetric TP/SL trap by demanding flow confirmation before allocating capital. Even if a similar single-condition risk archetype exists, the AND-conjunction creates a materially different conditional distribution.",
      "expected_triggers_30d": 540,
      "triggers_estimate_method": "Channel=* aggregates ~7200 events/30d (1400 OI + 5000 pc + 800 R6). liquidity_bucket=high cut ~ 0.30 of universe (high-liq symbols dominate volume but not event count) → ~2160. taker_buy_ratio_5m>=0.60 is a moderately strong long-flow filter cutting ~0.25 of remaining (taker buy ratios skew around 0.50 with std ~0.08, so ≥0.60 ≈ top quartile) → 2160 × 0.25 ≈ 540. side=both keeps full count.",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Both conditions are stationary at T0, so this risk gate composes with any of the 5 exit kernels. Strongest fit with fixed exits (the only exit family with positive mean per coverage_summary, mean=+0.175, n_positive=6680/7320) — kelly-safe sizing is most meaningful when TP/SL are symmetric and pre-committed. Secondary fit: breakeven (also bounded left tail). Weak fit: time_only (no TP/SL, sizing gate adds little). Recommend Synthesizer prioritize fixed-exit pairings to directly counter the E126 asymmetric-trap lesson from R2."
    }
  ]
}
```

### risk
```json
{
  "summary": "Single risk-archetype proposal r_kelly_safe_size_filter is research-integrity clean: novel_dim fields are T0-anchored (liquidity_bucket and trailing 5m taker_buy_ratio), and as a sizing gate at $1000 capital it carries no realistic concentration, leakage, or live-conflict blockers.",
  "risk_assessments": [
    {
      "archetype_ref": "r_kelly_safe_size_filter",
      "leakage_risk": "none",
      "leakage_notes": "Both novel_dim fields (liquidity_bucket=high, taker_buy_ratio_5m>=0.60) are computed from data available at-or-before T0: liquidity_bucket is a static/slow regime label, and taker_buy_ratio_5m is a trailing 5-minute window ending at T0. No forward_*, confirm_after_*, or post_event_* fields referenced. Caveat: implementation must ensure taker_buy_ratio_5m uses the [T0-5m, T0] window, not [T0, T0+5m] — name is unambiguous but worth a code-review check.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Risk-type archetype acts as a SIZING gate, not a directional entry — it only attenuates positions, so it cannot create opposite-side trades that conflict with the live BWE_OI_Price_monitor pump-long strategy. At worst it suppresses some entries the live system would also take, which is a coverage question for paper-shadow, not a research-integrity blocker.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "None required for research integrity. Recommended (non-blocking) sanity checks at implementation time: (1) assert taker_buy_ratio_5m window is strictly trailing relative to T0; (2) confirm liquidity_bucket label is computed from a snapshot dated <= T0 (not a forward-looking liquidity regime); (3) during paper-shadow, log how often this gate fires alongside the live pump-long strategy to quantify coverage overlap."
    }
  ]
}
```

### metric_critic
```json
{
  "archetype_ref": "r_kelly_safe_size_filter",
  "predicted_tp_pct": 0.6,
  "predicted_sl_pct": 1.2,
  "predicted_tp_sl_ratio": 0.5,
  "predicted_win_rate": 0.58,
  "predicted_mean_per_trade_pct": 0.0,
  "predicted_kelly_pct": 2.0,
  "trap_risk": "low",
  "trap_reasoning": "This is a RISK archetype (sizing gate), not an entry — it does not itself dictate TP/SL geometry. The novel_dim (liquidity_bucket=high AND taker_buy_ratio_5m>=0.60) acts as an AND-gate that only allows full size when both confirmation signals fire. Because it is channel-agnostic (*) and side-agnostic (both), the underlying entries it gates will span the whole population, so the realized TP/SL will be the weighted average of the entries it admits. Empirically the fixed exit family in this run shows mean +0.175 and median +0.217 with 91% positive rate, so a sizing filter that further demands two confirmations (high liquidity + taker_buy ≥0.60) should bias toward symmetric-geometry winners (TP≈0.6, SL≈1.2 is typical for fixed exits in this regime) rather than the E126-style 0.51/6.00 asymmetric trap, since taker_buy_ratio≥0.60 already implies directional conviction with smaller required SL buffer. Trap risk is LOW because: (1) high-liquidity bucket reduces slippage/wick noise that forces wide SL, (2) taker_buy confirmation reduces fakeout rate, lifting win rate without needing a giant SL cushion, (3) as a RISK archetype its score is computed on size-adjusted PnL not raw, so even if a trap geometry slips through, kelly-cap and mean_net_pct will down-weight it. Main uncertainty: triggers will be much sparser (both AND conditions must fire), so n_trades may drop below the 200-trade significance floor, producing a noisy mean_net_pct estimate rather than a true trap.",
  "recommended_constraint": "force SL ≤ 2 × TP_pct in variant grid AND require n_trades ≥ 200 for kelly_capped to be non-zero",
  "metric_score_estimate": 3.5
}
```

## Synthesizer
```json
{
  "summary": "Round 3 generator delivered a strong, structurally diverse batch dominated by OI_Price-channel ports of proven pricechange templates, novel exit-family experiments addressing the R2 X-pipeline starvation gap, and short-side mean-reversion fades that finally break from the continuation-only short cluster. Inclusive-default posture applied: 20/21 accepted (some with watch-flags for trap geometry per metric_critic), 1 revised due to a parser-level multi-value OR limitation on the weekday field, 0 rejected. Coverage gaps filled: OI_Price/long alpha porting (4 archetypes), short-side mean-reversion (3), exit-family innovation (5), session/weekday regime gating, basis dislocation, cross-channel tight-window timing, and a kelly-safe sizing risk filter.",
  "accepted_archetypes": [
    {
      "id": "E202",
      "type": "entry",
      "archetype": "oi_pump_taker_buy_extreme_high_liq_long",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.65",
        "liquidity_bucket=high",
        "oi_change_pct>=10"
      ],
      "expected_distinct": true,
      "notes": "OI burst with aggressive taker buying in high-liquidity names — port of E126 winning template to OI_Price channel where 61 archetypes registered but none in top-10.",
      "synthesizer_note": "Accepted; fills OI_Price top-10 gap. Metric_critic flags high trap risk (E126-family asymmetric TP/SL geometry) — GPU sweep should constrain SL<=2.5x TP and validate via kelly_capped/p25_capped_tail, not legacy p25."
    },
    {
      "id": "E203",
      "type": "entry",
      "archetype": "oi_pump_global_short_high_long",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "global_short_ratio_high",
        "oi_change_pct>=12",
        "liquidity_bucket=high"
      ],
      "expected_distinct": true,
      "notes": "OI burst on names where global short ratio is elevated — squeeze fuel hypothesis, mirrors E148 from pricechange to OI channel.",
      "synthesizer_note": "Accepted; squeeze-fuel logic ported to OI_Price is structurally novel. Devil notes funding-rate staleness and channel-semantics mismatch — track per-symbol concentration and time-since-funding-update during paper-shadow."
    },
    {
      "id": "E204",
      "type": "entry",
      "archetype": "oi_crash_taker_buy_reversal_long",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.60",
        "oi_change_pct<=-8",
        "liquidity_bucket=high"
      ],
      "expected_distinct": true,
      "notes": "OI reduction with concurrent taker BUY pressure — short-cover reversal setup distinct from continuation longs.",
      "synthesizer_note": "Accepted with watch (tight ~85 trig); first divergence/reversal entry on OI_Price. Metric_critic flags counter-trend geometry concern — pair with fixed/breakeven exits and force SL<=1.5x TP in variant grid."
    },
    {
      "id": "E205",
      "type": "entry",
      "archetype": "oi_pump_funding_neutral_taker_extreme_long",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.65",
        "funding>=-0.0001",
        "funding<=0.0001",
        "oi_change_pct>=10"
      ],
      "expected_distinct": true,
      "notes": "OI burst with neutral funding (no crowding) plus extreme taker buying — clean signal without funding skew.",
      "synthesizer_note": "Accepted; funding-neutral gate is the cleanest direct attack on the R2 E126 funding-skew trap. Devil rightly notes the band is narrow — confirm with ablation at |funding|<=3bp during paper-shadow."
    },
    {
      "id": "E206",
      "type": "entry",
      "archetype": "pc_pump_taker_buy_high_liq_global_short_long",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.65",
        "liquidity_bucket=high",
        "global_short_ratio_high"
      ],
      "expected_distinct": true,
      "notes": "Triple-AND combining the three top R2 winners (taker_buy + high_liq + global_short_high) into one selective entry.",
      "synthesizer_note": "Accepted with watch; triple-intersection of E126/E051/E148 components. Metric_critic flags high trap risk because all three parents share asymmetric pump-long geometry — must validate with kelly_capped, and overlap-rate vs E126/E051/E148 should stay <80% to confirm marginal value."
    },
    {
      "id": "E207",
      "type": "entry",
      "archetype": "pc_pump_funding_positive_taker_sell_short",
      "channel": "pricechange",
      "side": "short",
      "novel_dim": [
        "funding>=0.0005",
        "taker_buy_ratio_5m<=0.40",
        "move_pct>=3"
      ],
      "expected_distinct": true,
      "notes": "Crowded-long pump with positive funding and taker SELL dominance — classic mean-reversion fade with natural SL=TP symmetry.",
      "synthesizer_note": "Accepted; first true mean-reversion short on pricechange (existing 94 shorts collapsed to baseline because they reused continuation logic). Geometry is structurally symmetric per metric_critic, lower trap risk than other shorts."
    },
    {
      "id": "E208",
      "type": "entry",
      "archetype": "pc_pump_top_trader_short_funding_high_short",
      "channel": "pricechange",
      "side": "short",
      "novel_dim": [
        "top_trader_position_ratio_low",
        "funding_pct_top_decile",
        "move_pct>=3"
      ],
      "expected_distinct": true,
      "notes": "Smart money positioned short while retail funding extreme — high-conviction fade short.",
      "synthesizer_note": "Accepted; smart-money + funding-extreme cross-signal is novel for short side. Devil flags funding-snapshot staleness (8h cycle) — bucket trades by snapshot age during shadow."
    },
    {
      "id": "E209",
      "type": "entry",
      "archetype": "pc_crash_oversold_global_long_extreme_long",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "global_long_ratio_extreme",
        "move_pct<=-4",
        "taker_buy_ratio_5m>=0.55"
      ],
      "expected_distinct": true,
      "notes": "Crash with retail capitulation extreme + early taker buy reversal — counter-trend bounce.",
      "synthesizer_note": "Accepted with watch (tight ~45 trig per quant). High trap risk per metric_critic — counter-trend longs structurally invite asymmetric SL>>TP. Force SL<=2x TP and require TP>=0.8% in variant grid."
    },
    {
      "id": "E210",
      "type": "entry",
      "archetype": "r6_bigmove_simple_long",
      "channel": "Reserved6",
      "side": "long",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.55"
      ],
      "expected_distinct": true,
      "notes": "Single-filter Reserved6 long — minimal AND to preserve sparse R6 trigger count (~120 baseline).",
      "synthesizer_note": "Accepted; pattern_miner architectural fix for R6 over-specification. Lowest trap risk in batch per metric_critic (R6 geometry is more directional than pump channels)."
    },
    {
      "id": "E211",
      "type": "entry",
      "archetype": "r6_pump_high_liq_only_long",
      "channel": "Reserved6",
      "side": "long",
      "novel_dim": [
        "liquidity_bucket=high"
      ],
      "expected_distinct": true,
      "notes": "R6 long gated only by high liquidity — sparse-channel safe filter.",
      "synthesizer_note": "Accepted with watch; devil correctly notes liquidity_bucket alone has no directional bias and risks regression to channel/side baseline (R1 silent-fallthrough echo). Compare lift vs plain R6/long baseline — kill if delta<+0.05."
    },
    {
      "id": "E212",
      "type": "entry",
      "archetype": "hour_session_us_pump_long",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "session=US",
        "taker_buy_ratio_5m>=0.60",
        "liquidity_bucket=high"
      ],
      "expected_distinct": true,
      "notes": "Session-gated entry restricting pricechange longs to US trading hours — exploits liquidity regime.",
      "synthesizer_note": "Accepted; first archetype to use the supported `session` field. Ample expected sample (~340). Devil flags potential macro-event overfit in 30d window — bucket by sub-window during shadow."
    },
    {
      "id": "E213",
      "type": "entry",
      "archetype": "basis_curvature_pump_short",
      "channel": "pricechange",
      "side": "short",
      "novel_dim": [
        "basis_rate>=0.001",
        "premium_bps>=20",
        "move_pct>=3"
      ],
      "expected_distinct": true,
      "notes": "Pump with extreme basis AND premium — perp dislocation fade.",
      "synthesizer_note": "Accepted; lowest trap risk among shorts per metric_critic — bounded mean-reversion thesis with naturally symmetric geometry. Verify Spearman(basis_rate, premium_bps) on triggers <0.85 to confirm joint-signal novelty."
    },
    {
      "id": "X102",
      "type": "exit",
      "archetype": "x101_quick_cut_60s_time_exit",
      "channel": "NA",
      "side": "NA",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.65"
      ],
      "expected_distinct": true,
      "notes": "Pure time_only 60s exit paired with high-conviction entries — quick mean-reversion harvest before drift.",
      "synthesizer_note": "Accepted with watch; time_only family has 0/2745 prior positives, but pattern_miner flagged the mean-reversion pairing as untested. Treat as deliberate hypothesis test — require mean AND p25_capped_tail both >0 before any keep-promotion."
    },
    {
      "id": "X103",
      "type": "exit",
      "archetype": "x102_wide_trail_2pct_exit",
      "channel": "NA",
      "side": "NA",
      "novel_dim": [
        "liquidity_bucket=high"
      ],
      "expected_distinct": true,
      "notes": "Trail family with 2.0% step on top entries — wider trail to avoid premature stop-out.",
      "synthesizer_note": "Accepted; trail family max≈-0.006 suggests parameter mis-tune not dead concept (pattern_miner). Sweep step in {1.5,2.0,2.5}% with activation_threshold to map the surface."
    },
    {
      "id": "X104",
      "type": "exit",
      "archetype": "x103_multi_tp_60_40_ladder_exit",
      "channel": "NA",
      "side": "NA",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.60"
      ],
      "expected_distinct": true,
      "notes": "Two-step TP ladder 60/40 with first TP at 0.5% second at 1.5% — captures bulk early.",
      "synthesizer_note": "Accepted with watch; multi_tp prior is brutal (0/3111 positive), but front-loaded 60/40 shape attacks the residual-leg failure mode. Devil flag: novel_dim is entry-side filter on exit archetype — verify kernel evaluates it correctly. Track residual-leg PnL in isolation."
    },
    {
      "id": "X105",
      "type": "exit",
      "archetype": "x104_breakeven_strict_30s_exit",
      "channel": "NA",
      "side": "NA",
      "novel_dim": [
        "liquidity_bucket=high"
      ],
      "expected_distinct": true,
      "notes": "Breakeven kernel with stricter trigger threshold and 30s activation — differentiates from X100 floor.",
      "synthesizer_note": "Accepted; quant correctly flagged that BE-timing parameters live in the exit-config slot, not novel_dim — ensure be_trigger_pct and be_activation_seconds are both swept to avoid collapse onto X100."
    },
    {
      "id": "X106",
      "type": "exit",
      "archetype": "x105_hybrid_fixed_then_trail_exit",
      "channel": "NA",
      "side": "NA",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.60"
      ],
      "expected_distinct": true,
      "notes": "Hybrid: take 50% at fixed 0.5% TP, trail remaining 50% with 1.5% step — symmetric risk/reward.",
      "synthesizer_note": "Accepted with watch; genuinely new hybrid family but requires kernel composition support — none of the 5 live kernels natively combine fixed+trail. If kernel unavailable, downgrade to multi_tp approximation rather than skip."
    },
    {
      "id": "C061",
      "type": "cross_channel",
      "archetype": "cc_pc_oi_within_60s_double_long",
      "channel": "*",
      "side": "long",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.60",
        "liquidity_bucket=high",
        "oi_change_pct>=8"
      ],
      "expected_distinct": true,
      "notes": "Pricechange and OI_Price both fire within 60 seconds with taker_buy confirmation — tight double-channel timing window.",
      "synthesizer_note": "Accepted with watch; quant correctly notes the 60s timing window is not expressible in filter DSL and effectively reduces to a 3-condition AND. The temporal join must be enforced at kernel/event-pairing level, not filter level — flag for implementation review."
    },
    {
      "id": "C062",
      "type": "cross_channel",
      "archetype": "cc_three_signal_funding_neutral_long",
      "channel": "*",
      "side": "long",
      "novel_dim": [
        "funding>=-0.0001",
        "funding<=0.0001",
        "taker_buy_ratio_5m>=0.60",
        "liquidity_bucket=high"
      ],
      "expected_distinct": true,
      "notes": "Three-channel alignment requiring funding-neutral regime — avoids crowded-trade traps.",
      "synthesizer_note": "Accepted with watch (tight ~60 trig); first cc_* with funding-neutral gate. Lowest trap risk in cc batch per metric_critic — funding-neutral filter explicitly excludes the regime that produced the E126 trap."
    },
    {
      "id": "R041",
      "type": "risk",
      "archetype": "r_kelly_safe_size_filter",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "liquidity_bucket=high",
        "taker_buy_ratio_5m>=0.60"
      ],
      "expected_distinct": true,
      "notes": "Risk archetype enforcing position size only when both liquidity and taker_buy confirm — kelly-safe sizing.",
      "synthesizer_note": "Accepted; first risk archetype combining liquidity+taker_buy as size-gating AND. Devil correctly flags side=both is asymmetric in practice (taker_buy>=0.60 clusters on long regimes) — log per-side trigger counts during shadow to confirm short coverage is real."
    }
  ],
  "revised_archetypes": [
    {
      "original_archetype_ref": "weekday_weekend_avoid_long",
      "revised_archetype": "weekday_midweek_wed_filter",
      "revision_reason": "Quant flagged that the original 5-value OR list (weekday=Mon|Tue|Wed|Thu|Fri) is not standard parser semantics — the filter parser will AND-conjunct these into 'weekday=Mon AND weekday=Tue AND ...' which evaluates to zero matches, OR it will use only the last value. Either way the intent (exclude weekends) is not actually enforced.",
      "revised_novel_dim": [
        "weekday=Wed"
      ],
      "revised_notes": "Single mid-week (Wed) gate as a minimal test of the weekday dimension on a parser that doesn't support multi-value OR. If Wed shows positive lift_vs_baseline, follow-up Round 4 archetypes can probe Tue/Thu/Fri individually to characterize the full weekday surface; if the parser is later extended with OR/IN semantics, restore the original weekend-avoid formulation."
    }
  ],
  "rejected_archetypes": [],
  "next_round_focus": "Round 4 should (a) propose explicit symmetric-geometry exits (TP=SL or TP/SL ratio constrained to [0.5,1.5]) to attack the E126 trap structurally rather than via metric penalization, (b) extend the cross-channel chain primitives — current parser cannot enforce <60s timing windows, so several cc_* archetypes silently degrade to flat ANDs, and (c) add OR/IN semantics to the weekday/session fields so multi-value regime gates are first-class rather than collapsing to single-value tests."
}
```