# Debate transcript: debate_20260427_091138

- Trigger: `round_2_with_2700_results_and_5_exit_kernels`
- Models: {'generator': 'claude-sonnet-4-6', 'devil': 'claude-opus-4-7', 'quant': 'claude-sonnet-4-6', 'risk': 'claude-opus-4-7', 'synthesizer': 'claude-opus-4-7'}
- Existing archetypes: 523 total
- Results so far: {'total': 2803, 'by_status': {'keep': 7, 'discard': 2544, 'crash': 252}, 'best_score': 0.394617, 'n_keeps': 7}

## 1. Generator (model=claude-sonnet-4-6, 111.27s)

```json
{
  "summary": "Seven proposals targeting unused signal dimensions — listing age (coin maturity), day_change_pct as oversold context, negative premium for spot-led demand, negative funding as short-crowding proxy, global_short_ratio_high + OI confirmation for squeeze setup, small-cap volume burst, and oi_pct_top_decile (historical level vs delta) — all verified against SUPPORTED_FIELDS and each combining two or more orthogonal conditions.",
  "proposals": [
    {
      "archetype": "pc_pump_oversold_bounce_taker_long",
      "type": "entry",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "event_type=pump",
        "day_change_pct<=-5",
        "taker_buy_ratio_5m>=0.6"
      ],
      "notes": "Buy pump signal on coins already down 5%+ on the day where fresh taker buying confirms oversold reversal rather than exhaustion continuation.",
      "rationale": "day_change_pct as an oversold-context filter has not been combined with event_type=pump + taker_buy_ratio_5m in any existing entry; distinct from pure momentum entries that fire regardless of prior-day context.",
      "expected_distinct": true
    },
    {
      "archetype": "oi_pump_new_listing_taker_long",
      "type": "entry",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "oi_change_pct>=15",
        "listing_age_days<=180",
        "taker_buy_ratio_5m>=0.55"
      ],
      "notes": "OI surge on coins listed within 6 months with taker buying confirmation; newer listings have fewer sophisticated arbitrageurs so OI pumps more likely to translate to price follow-through.",
      "rationale": "listing_age_days is a completely unused dimension across all 523 existing archetypes; pairing coin maturity with OI surge is structurally distinct from any existing filter combination.",
      "expected_distinct": true
    },
    {
      "archetype": "pc_pump_short_squeeze_oi_long",
      "type": "entry",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "event_type=pump",
        "global_short_ratio_high",
        "oi_change_pct>=10"
      ],
      "notes": "Pump event when global short ratio is at high-percentile threshold and OI is building — crowded short positioning plus new longs entering creates a forced-covering cascade.",
      "rationale": "global_short_ratio_high flag has not been gated by oi_change_pct growth confirmation; E147/E148 used isolated global_long/short fields without OI growth, making this structurally distinct with two orthogonal squeeze signals.",
      "expected_distinct": true
    },
    {
      "archetype": "pc_pump_funding_negative_squeeze_long",
      "type": "entry",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "event_type=pump",
        "funding<=-0.005",
        "taker_buy_ratio_5m>=0.6"
      ],
      "notes": "Pump signal when funding is meaningfully negative (shorts paying longs) with aggressive taker buying — short-crowded perpetual plus spot-side demand pressure signals high squeeze probability.",
      "rationale": "Negative funding as a directional filter (shorts crowded) is distinct from funding_abs_high (magnitude-only); E154/E155 targeted Reserved6 channel and crashed on no_events; this uses pricechange channel with a confirmed-supported operator condition.",
      "expected_distinct": true
    },
    {
      "archetype": "oi_pump_premium_discount_long",
      "type": "entry",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "oi_change_pct>=15",
        "premium_bps<=-10",
        "taker_buy_ratio_5m>=0.55"
      ],
      "notes": "OI surge with perp trading at discount to spot (negative premium) plus taker buying — real spot demand driving the move rather than derivative-led speculation, suggesting higher-quality pump.",
      "rationale": "premium_bps in negative direction for longs is unexplored; E181 used premium_diverge for shorts and E187/E188 used basis_align/diverge; negative premium on a long entry targets the spot-demand-led regime, which is structurally opposite.",
      "expected_distinct": true
    },
    {
      "archetype": "pc_pump_small_cap_volume_surge_long",
      "type": "entry",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "event_type=pump",
        "marketcap_bucket=small",
        "volume_pct_top_decile",
        "taker_buy_ratio_5m>=0.55"
      ],
      "notes": "Pump on a small-cap coin with historically extreme volume plus taker buying confirmation; thin liquidity combined with a volume surge amplifies pump follow-through probability.",
      "rationale": "marketcap_bucket=small combined with volume_pct_top_decile is a novel size-plus-liquidity-burst pairing; E051 used liquidity_bucket=high which implicitly selects larger caps — this targets the opposite market-cap regime.",
      "expected_distinct": true
    },
    {
      "archetype": "pc_pump_oi_historically_extreme_long",
      "type": "entry",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "event_type=pump",
        "oi_pct_top_decile",
        "taker_buy_ratio_5m>=0.55",
        "liquidity_bucket=high"
      ],
      "notes": "Pump event when OI is in its historical top decile for that asset (absolute level, not delta spike) with taker confirmation in high-liquidity coins — historically elevated OI means more participants exposed to a squeeze.",
      "rationale": "oi_pct_top_decile (cross-time percentile flag) is structurally different from oi_change_pct (short-term delta); no existing archetype uses the historical OI level flag as a primary condition paired with event_type=pump and taker confirmation.",
      "expected_distinct": true
    }
  ]
}
```

## 2. Devil (model=claude-opus-4-7, 73.65s)

```json
{
  "summary": "Moderate-low confidence: most proposals reuse the same dual/triple-condition pricechange-pump template that has already failed across 30+ recent variants at val_score≈-0.28, and several rely on dimensions (listing_age_days, marketcap_bucket, oi_pct_top_decile) whose data availability and look-back computability have not been demonstrated in the 523 existing archetypes — so novelty is high but feasibility risk is severe.",
  "critiques": [
    {
      "archetype_ref": "pc_pump_oversold_bounce_taker_long",
      "verdict": "likely_fail",
      "failure_modes": [
        "Catching-falling-knife exposure: day_change_pct<=-5 selects assets in active downtrends where pump signals are most often dead-cat bounces; with best_sl pinned at 0.20 across all recent ladder_volume_weighted runs, single -5%+ adverse continuations will dominate the P&L tail and reproduce the -0.28 floor.",
        "Conditioning collision with the live BWE_OI_Price_monitor pump long: this archetype will fire on the same pump events but in the subset where price is already deeply down — historically the lower-quality slice of pump signals — meaning it competes for capital with the live strategy on its worst-conditioned trades rather than adding orthogonal edge.",
        "Sample-size fragility on the 30-day window: requiring event_type=pump AND day_change_pct<=-5 AND taker_buy_ratio_5m>=0.6 is a triple-AND filter; given E141–E150 already showed pump+taker variants either at 5000 (saturated) or ~1000 triggers, adding the day_change gate likely drops to <300 triggers, insufficient for the optimizer to distinguish edge from noise."
      ],
      "min_evidence_needed": "Bucket 30d historical pump events by day_change_pct deciles and measure forward 1h/4h return mean and Sharpe per decile; the bottom decile (≤-5%) must show statistically significantly higher forward return than the median bucket after subtracting 12bps round-trip cost."
    },
    {
      "archetype_ref": "oi_pump_new_listing_taker_long",
      "verdict": "likely_fail",
      "failure_modes": [
        "listing_age_days is claimed unused across 523 archetypes — that is a strong signal it may not be in SUPPORTED_FIELDS or not populated for the historical universe; if it fails the field check the archetype will crash like E154/E155/E158/E159/E160 (no_events_for_channel) and waste a slot.",
        "Survivorship/selection bias: coins listed within 180 days that survived to be in the dataset systematically outperform delisted peers, so any backtest will overstate edge. Live forward performance on new listings will not match historical because the listing_age<=180 cohort changes weekly.",
        "Liquidity and cost mismatch: newer listings typically have wider spreads and shallower books than the 8–16 bps round-trip assumption; with best_tp clustering at 0.32 in recent X014 runs, a realistic 25–40bps effective cost on small new listings will eat the entire target.",
        "Look-ahead concern on listing_age_days at T0: confirm the field reflects the listing date as known at trigger time and not a backfilled value adjusted after subsequent re-listings or symbol renames."
      ],
      "min_evidence_needed": "Verify listing_age_days exists in SUPPORTED_FIELDS and is populated for ≥80% of historical bars; then run a delisting-aware backtest including coins that were listed and later removed within the 30d window, with realistic per-symbol spread costs."
    },
    {
      "archetype_ref": "pc_pump_short_squeeze_oi_long",
      "verdict": "possibly_fail",
      "failure_modes": [
        "E147 (pc_pump_global_long_high_short) and E148 (pc_pump_global_short_high_long) both ran at ~988 triggers and discarded at -0.28; adding oi_change_pct>=10 narrows but does not change the underlying signal — the squeeze thesis already failed in the closest-neighbor experiment.",
        "global_short_ratio_high is a percentile/threshold flag whose computation window is unspecified — if it is computed on a rolling 30-day window inside the 30-day backtest dataset there is implicit look-ahead from the threshold-fitting process.",
        "Crowded-short squeezes are regime-dependent: they fire during BTC downtrend reversal regimes; the recent 30-day window may not contain such a regime, so the archetype either won't trigger meaningfully or will overfit a single squeeze cluster of 2–3 days."
      ],
      "min_evidence_needed": "Run with global_short_ratio_high computed strictly from data prior to T0 and report trigger-day distribution; require ≥5 distinct calendar days with triggers and a forward edge that survives removing the top-2 trigger days."
    },
    {
      "archetype_ref": "pc_pump_funding_negative_squeeze_long",
      "verdict": "possibly_fail",
      "failure_modes": [
        "funding<=-0.005 is a rare condition in perp markets — likely <50 trigger candidates per coin per 30d; combined with event_type=pump and taker_buy_ratio>=0.6 the trigger count will likely fall in the 50–200 range where prior R6 archetypes (E151–E165) all returned -0.27 to -0.28 due to inability to distinguish edge.",
        "Funding rate is published in 8-hour intervals on most venues; the value at T0 may be stale by up to 8h, so funding<=-0.005 may reflect short crowding from hours ago rather than the current state — meaning the squeeze may already have happened.",
        "Funding negativity often persists during sustained downtrends rather than preceding squeezes; the directional reading (negative = bullish) is contrary to the fact that prolonged funding negativity historically precedes further declines as much as squeezes."
      ],
      "min_evidence_needed": "Histogram of forward 1h/4h returns conditional on funding<=-0.005 alone over the full data history; the conditional mean must be positive and at least 1.5× the unconditional pump-event forward return after costs."
    },
    {
      "archetype_ref": "oi_pump_premium_discount_long",
      "verdict": "seems_ok",
      "failure_modes": [
        "premium_bps<=-10 (perp at 10bps discount to spot) is uncommon and often stale-quote-driven on illiquid books; thin-coin noise can fake a discount that vanishes on execution attempt, eating expected edge.",
        "E187 (cc_pc_oi_basis_align_long) and E188 (cc_pc_oi_basis_diverge_short) both went to 5000 triggers and -0.28 with X014 — the basis-related family has shown no edge in this kernel, so a closely related premium variant has prior evidence against it.",
        "OI_Price channel pump events on already-discounted perps may indicate spot-led demand but also indicate perp shorts being closed out (which raises perp price toward spot and removes the discount); the trigger condition can be self-extinguishing within the entry latency window."
      ],
      "min_evidence_needed": "Measure premium_bps decay from T0 to T0+5s on triggered events; if median |premium_bps| change exceeds half the entry threshold within 5s, the edge is non-executable. Otherwise proceed."
    },
    {
      "archetype_ref": "pc_pump_small_cap_volume_surge_long",
      "verdict": "likely_fail",
      "failure_modes": [
        "Small-cap pumps are the canonical wash-trade and pump-and-dump territory; the volume_pct_top_decile flag will preferentially select manipulated events whose forward return is negative-skewed even when mean is positive — the 0.20 SL floor in X014 will get hit on the dump leg.",
        "Cost sensitivity is severe: small-caps typically have 30–80bps round-trip cost; the 8–16bps assumption breaks, and best_tp values like 0.32 (seen across X014 runs) are smaller than realistic transaction cost on this universe.",
        "marketcap_bucket=small and volume_pct_top_decile both depend on cross-asset percentile rankings — confirm these are computed point-in-time; if computed on the full 30d window they leak future volume rankings into past trigger decisions.",
        "Direct conflict with the live BWE_OI_Price_monitor pump long if the live strategy already trades small-caps — same trigger universe, redundant exposure."
      ],
      "min_evidence_needed": "Apply realistic per-symbol transaction cost (use bid-ask spread × 2 + 5bps slippage) and require the strategy to remain net-positive after that adjustment; also confirm volume_pct_top_decile is computed strictly on lookback data."
    },
    {
      "archetype_ref": "pc_pump_oi_historically_extreme_long",
      "verdict": "possibly_fail",
      "failure_modes": [
        "oi_pct_top_decile is a per-asset historical percentile — confirm the percentile baseline is computed on a rolling lookback ending strictly before T0; otherwise this is a textbook look-ahead leak (asset's current OI is being compared to a distribution that includes future bars).",
        "Top-decile OI typically marks late-stage trend exhaustion as much as squeeze setup; the directional bias for long is not obvious — high absolute OI plus a pump is often the local top, not the launch pad.",
        "Quadruple-AND filter (pump + oi_pct_top_decile + taker_buy_ratio>=0.55 + liquidity_bucket=high) will likely produce <500 triggers in 30d after the orthogonal conditions intersect; with best_tp around 0.32, statistical power to distinguish from the -0.28 floor is marginal.",
        "Conflicts with the live BWE_OI_Price_monitor pump long: high-liquidity pumps with elevated OI is the exact universe the live strategy already targets; this archetype would double-up risk on overlapping triggers rather than diversify."
      ],
      "min_evidence_needed": "Verify oi_pct_top_decile is computed on a strictly point-in-time rolling window (e.g., trailing 60d excluding current bar); then segment forward returns by whether the asset is in an uptrend vs downtrend at T0 — top-decile OI must show positive forward edge in BOTH regimes for the long bias to be defensible."
    }
  ]
}
```

## 3. Quant (model=claude-sonnet-4-6, 160.35s)

```json
{
  "summary": "3 of 7 proposals contain novel dimensions that will fall through the filter parser (listing_age_days, marketcap_bucket, volume_pct_top_decile, oi_pct_top_decile are not in SUPPORTED_FIELDS), collapsing those archetypes to near-existing baselines; 2 viable proposals clear the trigger bar; 2 are trigger-tight and unlikely to survive statistical screening.",
  "analyses": [
    {
      "archetype_ref": "pc_pump_oversold_bounce_taker_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E126",
        "E064",
        "E141",
        "E149"
      ],
      "distinctness_notes": "E126 and E064 both combine event_type=pump with taker_buy_ratio thresholds but carry no prior-day context; day_change_pct<=-5 as an oversold-context gate is not present in any of the 201 existing entry archetypes and is orthogonal to all pump+taker variants tested in E141–E150.",
      "expected_triggers_30d": 430,
      "triggers_estimate_method": "Anchor to E126 (pump + taker>=0.6 → 3443 triggers). day_change_pct<=-5 filters to events where the asset is already down 5%+ on the day; crypto altcoins meet that threshold on roughly 12–15% of all event-days across the mixed-period dataset → 3443 × 0.125 ≈ 430 triggers.",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Fixed TP/SL (X001) and breakeven (X003-class) both viable at this trigger volume; multi_tp feasible but marginal; trail only if forward-return distribution is right-skewed."
    },
    {
      "archetype_ref": "oi_pump_new_listing_taker_long",
      "distinct": false,
      "distinct_from_existing_ids": [
        "E126"
      ],
      "distinctness_notes": "listing_age_days has never appeared in any of the 523 existing archetypes, which is the primary signal it is absent from SUPPORTED_FIELDS. When it falls through the parser, the archetype reduces to oi_change_pct>=15 + taker_buy_ratio_5m>=0.55 — a parameter delta of E126 (pc_pump_taker_buy_extreme_long) with only the channel differing, which does not constitute structural distinctness.",
      "expected_triggers_30d": 280,
      "triggers_estimate_method": "Without listing_age_days filter (fall-through): 1400 OI_Price events × 0.40 (oi_change>=15 pump subset) × 0.50 (taker>=0.55) ≈ 280. With listing_age_days active it would be 280 × 0.15 (new listings fraction) ≈ 42 — but the field is inoperative.",
      "sample_size_verdict": "adequate",
      "computable_at_T0": false,
      "uncomputable_fields": [
        "listing_age_days"
      ],
      "fall_through_conditions": [
        "listing_age_days<=180"
      ],
      "n_supported_conditions": 2,
      "n_total_conditions": 3,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Would only be evaluable as a novel archetype if listing_age_days is confirmed in SUPPORTED_FIELDS first; in current state it is a redundant near-duplicate of OI taker longs and should be rejected pending field verification."
    },
    {
      "archetype_ref": "pc_pump_short_squeeze_oi_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E147",
        "E148"
      ],
      "distinctness_notes": "E147 used global_long_ratio_high (long crowding proxy) and E148 used global_short_ratio_high without an OI growth gate; adding oi_change_pct>=10 as a confirmation that new longs are actively entering creates a squeeze-confirmation logic absent from both. The combination is a ≥4-parameter delta from the closest neighbor.",
      "expected_triggers_30d": 470,
      "triggers_estimate_method": "E147/E148 each showed ~988 triggers (pump + global_short/long_ratio_high ≈ 20% of ~5000 pricechange events). Adding oi_change_pct>=10 cuts by ~50% (OI growing on roughly half of pump events) → 988 × 0.48 ≈ 475.",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "All five exit families viable at ~470 triggers; breakeven and trail exits are best-motivated by the squeeze narrative (initial squeeze momentum then fade); fixed TP/SL as baseline."
    },
    {
      "archetype_ref": "pc_pump_funding_negative_squeeze_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E154",
        "E155"
      ],
      "distinctness_notes": "E154/E155 targeted the Reserved6 channel and crashed with no_events_for_channel — the funding-negative concept was never executed on pricechange. Negative directional gate (funding<=-0.005) is structurally different from funding_abs_high (magnitude-only), which tests crowding intensity regardless of direction. No existing pricechange archetype uses a signed funding threshold.",
      "expected_triggers_30d": 115,
      "triggers_estimate_method": "Anchor to E126 (pump + taker>=0.6 → 3443 triggers). funding<=-0.005 as a signed threshold (shorts paying longs): in the mixed-period dataset funding is negative roughly 8–10% of pump events → 3443 × 0.033 (joint: funding<=-0.005 AND already filtered by taker>=0.6 vs base pump events) estimated as 5000 pump × 0.30 pump_rate × 0.10 funding_neg × 0.35 taker_confirm ≈ 53–115; using midpoint 85 with wider range acknowledged.",
      "sample_size_verdict": "tight",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Tight trigger count favors fixed TP/SL only (X001); multi_tp and trail exit families require >300 triggers for reliable optimization. Recommend pairing with X001 exclusively in first run."
    },
    {
      "archetype_ref": "oi_pump_premium_discount_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E181",
        "E187",
        "E188"
      ],
      "distinctness_notes": "E181 applied premium_diverge as a short-side filter on pricechange; E187/E188 used basis_align/diverge on cross-channel cc_ archetypes. premium_bps<=-10 as a long-entry gate on OI_Price (perp below spot implies real spot demand) is directionally opposite to all tested premium conditions and has not been paired with oi_change_pct>=15 + taker confirmation.",
      "expected_triggers_30d": 39,
      "triggers_estimate_method": "1400 OI_Price events × 0.40 (oi_change>=15 subset) = 560 × 0.11 (premium<=-10bps occurs on ~11% of OI pump events; negative premium is uncommon and often fleeting) = 62 × 0.50 (taker>=0.55) ≈ 31–47; midpoint 39.",
      "sample_size_verdict": "tight",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "At ~39 triggers only fixed TP/SL (X001) is optimizable with any statistical confidence; all other exit families require more events. Flag for quick-screen only; do not invest multi_tp optimization slots."
    },
    {
      "archetype_ref": "pc_pump_small_cap_volume_surge_long",
      "distinct": false,
      "distinct_from_existing_ids": [
        "E051",
        "E064",
        "E126"
      ],
      "distinctness_notes": "Both novel dimensions (marketcap_bucket=small and volume_pct_top_decile) are cross-asset percentile rank fields that do not appear in any of the 523 existing archetypes, indicating they are absent from SUPPORTED_FIELDS. With both falling through, the archetype reduces to event_type=pump + taker_buy_ratio_5m>=0.55, which is a parameter delta of E064 (pc_pump_taker_buy_dominant_long, 3619 triggers, score=0.357). Fall-through rate: 2 of 4 conditions = 50%, at the rejection threshold; the 2 falling conditions are the only novel signal, making this structurally equivalent to a baseline.",
      "expected_triggers_30d": 1800,
      "triggers_estimate_method": "Without both novel dims: 5000 pricechange × 0.40 pump_rate × 0.55 taker>=0.55 ≈ 1100–1800 (consistent with E064 at 3619 with slightly lower taker threshold). With marketcap_bucket + volume_pct_top_decile active it would be ~1800 × 0.20 × 0.10 ≈ 36 — but both fields are inoperative.",
      "sample_size_verdict": "ample",
      "computable_at_T0": false,
      "uncomputable_fields": [
        "marketcap_bucket",
        "volume_pct_top_decile"
      ],
      "fall_through_conditions": [
        "marketcap_bucket=small",
        "volume_pct_top_decile"
      ],
      "n_supported_conditions": 2,
      "n_total_conditions": 4,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Rejected on distinctness grounds; if marketcap_bucket and volume_pct_top_decile are ever confirmed in SUPPORTED_FIELDS, re-evaluate — the tight-trigger version (~36) would be narrow exit only."
    },
    {
      "archetype_ref": "pc_pump_oi_historically_extreme_long",
      "distinct": false,
      "distinct_from_existing_ids": [
        "E051",
        "E064",
        "E126"
      ],
      "distinctness_notes": "oi_pct_top_decile is a cross-time per-asset historical OI percentile flag that has never appeared in any of the 523 archetypes, indicating it is absent from SUPPORTED_FIELDS. With it falling through, the archetype reduces to event_type=pump + taker_buy_ratio_5m>=0.55 + liquidity_bucket=high — a ≤2-parameter delta of E051 (pc_high_liquidity_long, 2157 triggers, score=0.347). Although the fall-through rate is only 1 of 4 conditions (25%), the one falling condition IS the sole novel dimension, making the archetype a functional duplicate of E051.",
      "expected_triggers_30d": 1100,
      "triggers_estimate_method": "Without oi_pct_top_decile: 5000 pricechange × 0.40 pump × 0.55 taker>=0.55 × 0.50 liquidity_bucket=high ≈ 550–1100 (E051 had 2157 on a less restrictive filter, consistent with a 2× reduction for taker gate). With oi_pct_top_decile active it would be ~1100 × 0.10 (top-decile OI fraction) ≈ 110 — but field is inoperative.",
      "sample_size_verdict": "ample",
      "computable_at_T0": false,
      "uncomputable_fields": [
        "oi_pct_top_decile"
      ],
      "fall_through_conditions": [
        "oi_pct_top_decile"
      ],
      "n_supported_conditions": 3,
      "n_total_conditions": 4,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Rejected on distinctness grounds due to collapse to E051 equivalent; if oi_pct_top_decile is confirmed in SUPPORTED_FIELDS the tight version (~110) is adequate for fixed TP/SL and breakeven, but not multi_tp."
    }
  ]
}
```

## 4. Risk (model=claude-opus-4-7, 61.92s)

```json
{
  "summary": "Moderate-to-high research-integrity risk: three proposals reference percentile/historical-rank fields whose point-in-time computation is unverified (textbook look-ahead leak risk), and four proposals overlap directly with the live BWE_OI_Price_monitor pump long universe — same-side concurrent positions on the same triggers will inflate effective leverage at $1000 capital × 5–10% sizing.",
  "risk_assessments": [
    {
      "archetype_ref": "pc_pump_oversold_bounce_taker_long",
      "leakage_risk": "low",
      "leakage_notes": "day_change_pct, event_type, and taker_buy_ratio_5m are all observable at T0; no forward-looking suffixes. Confirm day_change_pct is computed as (price_T0/price_at_session_open - 1) and not (price_T0/price_session_close - 1) where 'session_close' could be future-leaking.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "Same-side long pump on pricechange channel as the live BWE_OI_Price_monitor pump long; the day_change<=-5 gate selects a disjoint slice (already-down assets) so triggers should rarely overlap, but when they do they double-stack same-direction risk on one symbol.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "Add a runtime guard that rejects entry if the live pump-long strategy already holds a position in the same symbol; verify day_change_pct definition is point-in-time."
    },
    {
      "archetype_ref": "oi_pump_new_listing_taker_long",
      "leakage_risk": "high",
      "leakage_notes": "listing_age_days is suspect on two grounds: (a) Quant flagged it as absent from SUPPORTED_FIELDS so the condition silently falls through, meaning the archetype label misrepresents the actual filter — that is a research-integrity failure even if not technically leakage; (b) if the field IS later added, its values may be backfilled after symbol renames/re-listings and effectively encode post-T0 corporate actions. Survivorship bias compounds this: the historical 'new listing' cohort is conditioned on having survived to dataset assembly date.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "With listing_age_days inoperative the archetype collapses to oi_change>=15 + taker>=0.55 long, which is the live BWE_OI_Price_monitor pump long's exact universe — every trigger will be a redundant same-side stack on the live strategy, not orthogonal exposure.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "block",
      "remediation": "(1) Verify listing_age_days is in SUPPORTED_FIELDS and populated point-in-time before considering registration; (2) confirm the field is not backfilled across symbol renames; (3) require a delisting-aware backtest universe to neutralize survivorship; (4) add explicit non-overlap guard with the live pump long. Until all four are satisfied, do not register."
    },
    {
      "archetype_ref": "pc_pump_short_squeeze_oi_long",
      "leakage_risk": "medium",
      "leakage_notes": "global_short_ratio_high is a percentile/threshold flag — the percentile baseline must be computed on a strictly trailing window ending before T0. Devil's Advocate raised this concern and it is unresolved; if the percentile is fit on the full 30-day backtest window, the threshold itself encodes future information. Same concern applies if oi_change_pct>=10 is normalized cross-sectionally using future bars.",
      "multitest_inflation_risk": "high",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "Long pump with OI growth on pricechange channel overlaps materially with live BWE_OI_Price_monitor pump long; squeeze setups will fire on the same symbols the live strategy targets, doubling exposure during the highest-volatility periods (squeeze cascades) when slippage is worst.",
      "concentration_risk": "high",
      "adversarial_risk": "medium",
      "overall_severity": "caution",
      "remediation": "Tag for deep-eval gate with explicit checks: (a) global_short_ratio_high baseline computed on trailing window only; (b) regime-segmented forward returns (verify edge survives outside any single squeeze cluster of 2–3 days); (c) live-strategy non-overlap guard."
    },
    {
      "archetype_ref": "pc_pump_funding_negative_squeeze_long",
      "leakage_risk": "medium",
      "leakage_notes": "Funding rate is published in 8-hour intervals on most venues; if the dataset stores funding as the next-fixed value rather than the last-known-at-T0 value, funding<=-0.005 at trigger time secretly references a setting determined after T0 — classic temporal misalignment. Verify the field is the trailing realized funding, not the upcoming/scheduled funding.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "Long pump on pricechange channel overlaps with live BWE_OI_Price_monitor pump long universe; funding<=-0.005 narrows the slice but does not remove same-symbol same-side concurrency risk.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Confirm funding field semantics: must be last-realized-at-T0, not next-scheduled. Tag for deep-eval gate with explicit funding-staleness check (max age of funding observation at T0 reported in metadata)."
    },
    {
      "archetype_ref": "oi_pump_premium_discount_long",
      "leakage_risk": "low",
      "leakage_notes": "premium_bps and oi_change_pct are spot/perp basis observables at T0 if computed from synchronized snapshots; verify the spot leg used to compute premium_bps comes from a venue and timestamp aligned with the perp T0, not a delayed reference price.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "high",
      "live_conflict_notes": "OI_Price channel + oi_change_pct>=15 + long is structurally identical universe to live BWE_OI_Price_monitor pump long, with premium_bps<=-10 as the only narrowing gate. Whenever it fires, it fires on the live strategy's exact symbol-direction — same-side stacked exposure. At ~39 triggers/30d this is rare but each firing maximally concentrates with live capital.",
      "concentration_risk": "medium",
      "adversarial_risk": "medium",
      "overall_severity": "caution",
      "remediation": "Hard gate: the runtime must skip entry if the live BWE_OI_Price_monitor pump long is already positioned in the same symbol at T0. Verify spot/perp timestamp alignment for premium_bps."
    },
    {
      "archetype_ref": "pc_pump_small_cap_volume_surge_long",
      "leakage_risk": "high",
      "leakage_notes": "marketcap_bucket and volume_pct_top_decile are both cross-asset percentile-rank fields. Two distinct integrity hazards: (1) Quant flagged both as absent from SUPPORTED_FIELDS — the archetype label promises size/liquidity-burst conditioning but actually delivers plain pump+taker, so the registry record is misleading and any 'edge' attributed to the archetype mis-credits the wrong signal; (2) if added later, percentile rank fields are notorious leakage vectors — must be computed on trailing data only, never on the full backtest window.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "With novel dims inoperative collapses to event_type=pump + taker>=0.55 long on pricechange — the live BWE_OI_Price_monitor pump long universe; at ~1800 triggers/30d this would constantly stack same-side with live.",
      "concentration_risk": "high",
      "adversarial_risk": "high",
      "overall_severity": "block",
      "remediation": "Do not register: (a) verify marketcap_bucket and volume_pct_top_decile are in SUPPORTED_FIELDS AND computed strictly point-in-time on trailing data; (b) require realistic per-symbol spread cost (small-caps typically 30–80bps round-trip vs 8–16bps assumed); (c) live-strategy non-overlap guard. Adversarial: small-cap pump events are the canonical wash-trade venue — strategy can be intentionally triggered by manipulators if rule logic becomes inferable from order placements."
    },
    {
      "archetype_ref": "pc_pump_oi_historically_extreme_long",
      "leakage_risk": "high",
      "leakage_notes": "oi_pct_top_decile is a per-asset historical OI percentile and is the single most leakage-prone field type in the proposal set. If the percentile is computed using the full 30-day dataset (rather than a strictly trailing window ending before T0), every trigger silently knows the asset's future-relative OI ranking. Quant also flagged the field as absent from SUPPORTED_FIELDS, meaning the archetype currently collapses to E051-equivalent — registering it would attribute future edge to a signal that is not actually being measured.",
      "multitest_inflation_risk": "high",
      "live_conflict_risk": "high",
      "live_conflict_notes": "event_type=pump + taker + liquidity_bucket=high is exactly the live BWE_OI_Price_monitor pump long's high-quality slice; with oi_pct_top_decile inoperative this is functionally a near-duplicate that would fire on the live strategy's primary trigger universe ~1100 times in 30d, stacking same-side exposure constantly.",
      "concentration_risk": "high",
      "adversarial_risk": "medium",
      "overall_severity": "block",
      "remediation": "Do not register until: (a) oi_pct_top_decile is confirmed in SUPPORTED_FIELDS AND computed on a strictly trailing rolling window (e.g., trailing 60d excluding current bar); (b) regime-segmented forward returns show positive edge in BOTH uptrend and downtrend regimes (top-decile OI in downtrend is exhaustion, not squeeze setup); (c) explicit non-overlap guard with live pump long; (d) field name carries an explicit point-in-time suffix to make the trailing-window contract auditable."
    }
  ]
}
```

## 5. Synthesizer (model=claude-opus-4-7, 64.27s)

**ERROR**: `no JSON in assistant text`

```json
{}
```
