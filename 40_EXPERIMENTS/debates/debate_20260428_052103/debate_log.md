# Debate transcript: debate_20260428_052103

- Trigger: `manual`
- Models: {'pattern_miner': 'claude-opus-4-7', 'generator': 'claude-opus-4-7', 'steelman': 'claude-opus-4-7', 'devil': 'claude-opus-4-7', 'quant': 'claude-opus-4-7', 'risk': 'claude-opus-4-7', 'metric_critic': 'claude-opus-4-7', 'synthesizer': 'claude-opus-4-7', 'self_reflection': 'claude-opus-4-7', 'behavior_annotator': 'claude-opus-4-7', 'cross_pair_recommender': 'claude-opus-4-7'}
- Existing archetypes: 637 total
- Results so far: {'total': 26778, 'by_status': {'discard': 26778}, 'best_score': None, 'n_keeps': 0}

## 1. Generator (model=claude-opus-4-7, 94.91s)

```json
{
  "summary": "Round 4 generator pass: registry now has 637 archetypes but exit family is structurally broken (only 'fixed' has any positives, all trail/multi_tp/breakeven/time_only families show 0/n_positive — strongly indicates exit-side starvation as flagged by R2 synthesizer); pricechange/short channel and Reserved6/short are under-represented vs. existing entry distribution; proposing 18 archetypes leaning heavily on (a) novel exit kernels using supported flag tokens (premium_extreme, funding_pct_top_decile, top_trader_position_ratio_dec) for state transitions, (b) under-mined Reserved6/short cross-channel combos, and (c) symmetric-risk mean-reversion entries that avoid the E126 asymmetric TP/SL trap.",
  "proposals": [
    {
      "archetype": "x_exit_on_premium_extreme_flip",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "premium_extreme",
        "premium_bps<=5"
      ],
      "notes": "Close position when premium_extreme flag deactivates and premium_bps reverts below 5, capturing premium-mean-reversion exhaustion.",
      "rationale": "None of 142 exits use premium_extreme deactivation as exit trigger; current X033 only watches funding normalize. Premium reversion is orthogonal to funding/volume signals.",
      "expected_distinct": true
    },
    {
      "archetype": "x_exit_on_top_trader_dec_flip",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "top_trader_position_ratio_dec",
        "top_trader_position_ratio<=0"
      ],
      "notes": "Exit when smart-money position ratio flips from positive decile back to neutral, indicating informed flow has unwound.",
      "rationale": "Smart-money flip exit not in registry; existing exits use volume/funding/premium normalize but never top-trader positioning crossover.",
      "expected_distinct": true
    },
    {
      "archetype": "x_exit_on_funding_pct_top_decile_decay",
      "type": "exit",
      "channel": "OI_Price",
      "side": "short",
      "novel_dim": [
        "funding_pct_top_decile",
        "funding_abs_high"
      ],
      "notes": "For shorts entered during funding-extreme regime, exit when funding decays out of top decile, locking gains before squeeze risk rises.",
      "rationale": "Funding-decile-decay exit is novel; X034 exit_on_premium_normalize uses premium not funding decile, and no exit uses funding_pct_top_decile as decay trigger.",
      "expected_distinct": true
    },
    {
      "archetype": "x_exit_hybrid_be_then_top_trader_trail",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "top_trader_position_ratio_high",
        "top_trader_position_ratio_low"
      ],
      "notes": "Move stop to breakeven on first +0.3% favorable, then exit only when top_trader_position_ratio crosses against the trade direction.",
      "rationale": "Hybrid composition: BE + smart-money invalidation as exit. Existing breakeven family uses price-only, never combined with positional flow data.",
      "expected_distinct": true
    },
    {
      "archetype": "x_exit_on_global_long_short_extreme_flip",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "global_long_ratio_extreme",
        "global_short_ratio_extreme"
      ],
      "notes": "Exit position when retail long/short ratio crosses out of extreme bucket (contrarian regime ends), regardless of P&L state.",
      "rationale": "Retail-sentiment-extreme decay as exit is new; existing exits never reference global_long_ratio or global_short_ratio.",
      "expected_distinct": true
    },
    {
      "archetype": "x_exit_session_rollover_partial",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "session=US",
        "session=Asian"
      ],
      "notes": "Take 50% off at session boundary (US→Asian or Asian→European), trail rest with native exit, hedging session-specific reversal risk.",
      "rationale": "No exit references session as a transition trigger; this captures known session-rollover liquidity shifts.",
      "expected_distinct": true
    },
    {
      "archetype": "x_exit_on_taker_buy_ratio_flip_short",
      "type": "exit",
      "channel": "OI_Price",
      "side": "short",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.6",
        "taker_buy_ratio_5m<=0.4"
      ],
      "notes": "Short exit triggered when 5m taker-buy ratio flips from <=0.4 (sellers dominant) to >=0.6 (buyers regaining), signaling short-cover risk.",
      "rationale": "Aggressor-flip exit using taker_buy_ratio_5m crossover not in registry; existing X exits trigger on price/volume/funding only.",
      "expected_distinct": true
    },
    {
      "archetype": "x_exit_oi_collapse_runner",
      "type": "exit",
      "channel": "OI_Price",
      "side": "short",
      "novel_dim": [
        "oi_change_pct<=-10",
        "oi_pct_top_decile"
      ],
      "notes": "Hold short as runner while OI continues collapsing (oi_change_pct<=-10), exit only when OI stops decreasing — rides full liquidation cascade.",
      "rationale": "OI-decay-as-runner-condition exit is novel; existing trail/runner exits use price-only ATR or fixed multi-TP.",
      "expected_distinct": true
    },
    {
      "archetype": "e_pc_lowliq_smallcap_mean_revert_long",
      "type": "entry",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "liquidity_bucket=low",
        "marketcap_bucket=small",
        "move_pct<=-8",
        "global_short_ratio_high"
      ],
      "notes": "Long mean-reversion on small-cap low-liquidity dumps where retail is extreme short — symmetric SL=TP target around natural ATR.",
      "rationale": "Combines low-liq + small-cap + retail-short-extreme on long side; existing pricechange/long entries don't gate on retail short ratio + liquidity together.",
      "expected_distinct": true
    },
    {
      "archetype": "e_r6_extreme_pump_top_trader_short_short",
      "type": "entry",
      "channel": "Reserved6",
      "side": "short",
      "novel_dim": [
        "top_trader_position_ratio_low",
        "oi_pct_top_decile",
        "premium_bps>=15"
      ],
      "notes": "Short Reserved6 8-15% pumps when smart money sits in low decile + OI top decile + premium >=15bps — fade retail-driven extreme moves.",
      "rationale": "Reserved6/short with smart-money low + OI top + premium gate is a triple-orthogonal combo not present in 51 existing Reserved6 entries.",
      "expected_distinct": true
    },
    {
      "archetype": "e_r6_pump_funding_neg_short_squeeze_long",
      "type": "entry",
      "channel": "Reserved6",
      "side": "long",
      "novel_dim": [
        "funding<=-0.0005",
        "funding_abs_high",
        "global_short_ratio_extreme"
      ],
      "notes": "Long Reserved6 events when funding deeply negative + retail extremely short — primed for short-squeeze continuation.",
      "rationale": "Reserved6/long with deep-negative funding + retail-extreme-short triple gate is structurally distinct from any of the 51 Reserved6 entries.",
      "expected_distinct": true
    },
    {
      "archetype": "e_pc_session_asian_smallcap_short",
      "type": "entry",
      "channel": "pricechange",
      "side": "short",
      "novel_dim": [
        "session=Asian",
        "marketcap_bucket=small",
        "liquidity_bucket=low",
        "move_pct>=5"
      ],
      "notes": "Short Asian-session small-cap low-liq pumps with move_pct>=5 — exploits known Asian-session retail FOMO + thin book.",
      "rationale": "Asian-session + smallcap + lowliq + price-move triple gate on short side is novel; existing pricechange/short entries don't compose session+marketcap+liquidity.",
      "expected_distinct": true
    },
    {
      "archetype": "e_oi_basis_curvature_arb_short",
      "type": "entry",
      "channel": "OI_Price",
      "side": "short",
      "novel_dim": [
        "basis>=0.005",
        "premium_bps>=25",
        "oi_change_pct>=20",
        "funding_pct_top_decile"
      ],
      "notes": "Short when basis + premium + OI all extreme positive AND funding in top decile — fade compounded long-side overcrowding.",
      "rationale": "Quadruple-extreme positive composite on short side; existing OI_Price/short entries top out at 2-3 conditions.",
      "expected_distinct": true
    },
    {
      "archetype": "e_pc_volume_decile_above_p75_neg_funding_long",
      "type": "entry",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "volume_pct_above_p75",
        "funding<=-0.0003",
        "global_short_ratio_high"
      ],
      "notes": "Long pricechange when volume above p75 + funding negative + retail short_high — captures pre-squeeze setup with confirmed flow.",
      "rationale": "Volume-p75 (not top decile) + neg funding + retail-short-high triplet for long is distinct from existing pricechange/long entries.",
      "expected_distinct": true
    },
    {
      "archetype": "e_oi_hour_utc_us_close_pump_short",
      "type": "entry",
      "channel": "OI_Price",
      "side": "short",
      "novel_dim": [
        "hour_utc>=20",
        "hour_utc<=22",
        "oi_change_pct>=12",
        "top_trader_position_ratio_dec"
      ],
      "notes": "Short OI-pumps occurring during US-close window (20-22 UTC) where smart money is top-decile long — fade end-of-day positioning.",
      "rationale": "hour_utc time-bucket + smart-money-top-decile + OI-pump on short side; hour_utc gating absent from current OI_Price/short entries.",
      "expected_distinct": true
    },
    {
      "archetype": "e_pc_weekday_friday_short_squeeze_long",
      "type": "entry",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "weekday=Fri",
        "funding<=-0.0004",
        "global_short_ratio_extreme",
        "liquidity_bucket=mid"
      ],
      "notes": "Long Friday short-squeeze setup: deep-negative funding + retail extremely short + mid-liquidity (not too thin to manipulate).",
      "rationale": "Friday weekday gate + funding + retail-short-extreme + mid-liq quadruple condition is structurally novel.",
      "expected_distinct": true
    },
    {
      "archetype": "f_filter_session_us_premium_extreme",
      "type": "filter",
      "channel": "*",
      "side": "NA",
      "novel_dim": [
        "session=US",
        "premium_extreme",
        "funding_abs_high"
      ],
      "notes": "Restrict any entry to US session AND premium_extreme AND funding_abs_high — high-conviction regime gate to reduce false positives.",
      "rationale": "Triple regime filter combining session + premium_extreme + funding_abs_high not in 125 existing filters.",
      "expected_distinct": true
    },
    {
      "archetype": "cc_pricechange_then_oi_within_60s_long",
      "type": "cross_channel",
      "channel": "*",
      "side": "long",
      "novel_dim": [
        "volume_pct_top_decile",
        "oi_change_pct>=10",
        "funding<=-0.0002"
      ],
      "notes": "Long when pricechange channel fires first then OI_Price confirms within ~60s with OI-pump + volume-decile + neg funding — sequential confirmation pattern.",
      "rationale": "Sequential-confirmation cross-channel timing window <60s with three-factor confirm is novel; existing 66 cross-channel entries use simultaneous or single-channel logic.",
      "expected_distinct": true
    }
  ]
}
```

## 2. Devil (model=claude-opus-4-7, 89.16s)

```json
{
  "summary": "Generator batch is mostly sound with novel composition, but the heavy reliance on the same handful of supported flag tokens (top_trader_position_ratio_dec, global_short_ratio_extreme, premium_extreme, funding_pct_top_decile) means several proposals risk co-firing on the same rare regime windows; statistical fragility and sample-size concerns dominate, with two proposals showing concrete logical/scope gaps worth flagging.",
  "critiques": [
    {
      "archetype_ref": "x_exit_on_premium_extreme_flip",
      "verdict": "possibly_fail",
      "concerns": [
        "premium_bps<=5 deactivation may fire instantly at entry T0 if the entry condition didn't itself require premium_extreme — exit could trigger before any meaningful holding period, collapsing into a near-zero-return wash"
      ],
      "monitoring_advice": "track median holding time per trade; if <30s for >10% of trades, gate this exit on a minimum-hold floor"
    },
    {
      "archetype_ref": "x_exit_on_top_trader_dec_flip",
      "verdict": "possibly_fail",
      "concerns": [
        "top_trader_position_ratio updates at coarser cadence (typically 5min on Binance) than 1m kline — the 'flip' signal can lag price by 2-4 minutes, which is long enough for a fast move to fully reverse before exit triggers"
      ],
      "monitoring_advice": "compare exit fill price vs. price at top_trader flip detection — if slippage_to_signal median > 0.5%, this exit is structurally late"
    },
    {
      "archetype_ref": "x_exit_on_funding_pct_top_decile_decay",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "funding settles every 8h; verify decay-out-of-top-decile actually produces enough exit events vs. forced-time exits dominating"
    },
    {
      "archetype_ref": "x_exit_hybrid_be_then_top_trader_trail",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "watch the BE-hit-rate vs. trail-exit-rate split — if >80% exit on BE before trail engages, the smart-money invalidation half is dead weight"
    },
    {
      "archetype_ref": "x_exit_on_global_long_short_extreme_flip",
      "verdict": "possibly_fail",
      "concerns": [
        "global_long_ratio_extreme and global_short_ratio_extreme are derived from retail futures positioning that updates at 5min cadence — same lag concern as top-trader flip; additionally 'extreme' bucket is rare so most trades may never see a flip and fall through to default exit"
      ],
      "monitoring_advice": "log fraction of trades where this exit actually fires vs. default-time-out fallback; if <15%, exit family is essentially time_only in disguise"
    },
    {
      "archetype_ref": "x_exit_session_rollover_partial",
      "verdict": "seems_ok",
      "concerns": [
        "partial-50%-off semantics need to map cleanly onto the 5 existing exit kernels (fixed/time/breakeven/trail/multi_tp); if the loop doesn't natively support session-boundary partials, this archetype may silently fall through to baseline like the R1 unsupported-field bug"
      ],
      "monitoring_advice": "verify session boundary partials produce a different val_score than channel/side baseline — duplicate baseline scores indicate silent fallthrough"
    },
    {
      "archetype_ref": "x_exit_on_taker_buy_ratio_flip_short",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "taker_buy_ratio_5m is noisy — track flip-then-reflip rate; if >30%, consider requiring ratio to hold ≥2 consecutive 5m windows"
    },
    {
      "archetype_ref": "x_exit_oi_collapse_runner",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "this is the most promising exit in the batch — track max-favorable-excursion vs. realized exit price to verify runner logic actually captures cascade tail"
    },
    {
      "archetype_ref": "e_pc_lowliq_smallcap_mean_revert_long",
      "verdict": "possibly_fail",
      "concerns": [
        "small-cap + low-liquidity + 8% dump is exactly the regime where 8-16bps round-trip cost gets compounded by wide spreads; realized slippage on entry+exit could easily eat 30-50bps even before TP hits",
        "global_short_ratio_high data may not exist for small-cap altcoins (Binance only publishes long/short ratio for top ~50 pairs)"
      ],
      "monitoring_advice": "verify global_short_ratio is actually populated for trades in this archetype's symbol set; if NaN for >30% of triggers, archetype effectively reduces to lowliq+smallcap+dump on long side"
    },
    {
      "archetype_ref": "e_r6_extreme_pump_top_trader_short_short",
      "verdict": "seems_ok",
      "concerns": [
        "triple-orthogonal gating may be too restrictive given Reserved6 only has 51 existing entries to begin with — sample size on 30-day window could fall below statistical relevance"
      ],
      "monitoring_advice": "if triggers <50 over the test window, flag as too-rare-to-evaluate rather than failing"
    },
    {
      "archetype_ref": "e_r6_pump_funding_neg_short_squeeze_long",
      "verdict": "seems_ok",
      "concerns": [
        "Reserved6 channel is described as 'mostly short' (180s extreme moves) — long entries on this channel are inherently fighting the channel's signal direction, which is fine for contrarian setups but expect lower base rate"
      ],
      "monitoring_advice": "compare win rate to existing Reserved6/long baseline; if no meaningful lift, contrarian thesis isn't holding"
    },
    {
      "archetype_ref": "e_pc_session_asian_smallcap_short",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "session=Asian + smallcap + lowliq is a thin-book regime — verify entry slippage doesn't dominate the edge"
    },
    {
      "archetype_ref": "e_oi_basis_curvature_arb_short",
      "verdict": "possibly_fail",
      "concerns": [
        "four simultaneous extreme conditions (basis>=0.005 AND premium_bps>=25 AND oi_change_pct>=20 AND funding_pct_top_decile) is likely to produce <20 triggers in 30 days — falls into the same overfitting/fragility trap as a fitted explanation of one or two recent winners",
        "basis and premium_bps are highly correlated — gating on both extreme is near-redundant, effectively reducing to a 3-condition gate with extra noise"
      ],
      "monitoring_advice": "if trigger count <30, mark as insufficient-sample; consider relaxing one of basis/premium to top-quartile rather than extreme"
    },
    {
      "archetype_ref": "e_pc_volume_decile_above_p75_neg_funding_long",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "clean composition; track lift vs. existing pc_pump_neg_funding_long baseline to confirm volume_p75 gate adds value over volume_top_decile"
    },
    {
      "archetype_ref": "e_oi_hour_utc_us_close_pump_short",
      "verdict": "seems_ok",
      "concerns": [
        "hour_utc 20-22 is a 3-hour window — combined with OI-pump>=12 and top-trader-decile gate may produce sample sizes too small for stable estimation"
      ],
      "monitoring_advice": "if triggers <40 over test window, consider widening hour band to 19-23 UTC"
    },
    {
      "archetype_ref": "e_pc_weekday_friday_short_squeeze_long",
      "verdict": "possibly_fail",
      "concerns": [
        "weekday=Fri restricts to ~14% of the calendar; combined with three additional gates (funding + retail-extreme + mid-liq) this likely fires <15 times in 30 days, well below statistical reliability for a strategy meant to size 5-10% of $1000",
        "weekday gating risks pure overfitting to recent-week patterns — Friday-specific edges have a poor track record in academic crypto literature without strong mechanism"
      ],
      "monitoring_advice": "if trigger count <20, treat any positive score as noise; consider removing weekday gate as an A/B test"
    },
    {
      "archetype_ref": "f_filter_session_us_premium_extreme",
      "verdict": "seems_ok",
      "concerns": [
        "triple-AND filter is restrictive enough that it may starve downstream entries — verify it doesn't reduce trigger count below useful threshold for any entry it gates"
      ],
      "monitoring_advice": "track per-entry trigger count when this filter is applied; if any entry drops to <30 triggers, filter is too tight"
    },
    {
      "archetype_ref": "cc_pricechange_then_oi_within_60s_long",
      "verdict": "possibly_fail",
      "concerns": [
        "sequential-confirmation timing window assumes both channel events are reliably timestamped to <1s precision and join logic exists in the loop — if cross-channel timing isn't natively supported, this could silently fall through to baseline like the R1 unsupported-field bug",
        "60s window is short relative to the 5min update cadence of OI data — many real OI confirmations may arrive 60-300s after the price signal and be excluded"
      ],
      "monitoring_advice": "first verify the loop has a cross-channel temporal join primitive; if not, flag as unsupported. Second, log distribution of pricechange→OI lag and consider widening to 180s if 60s captures <30% of true sequential events"
    }
  ]
}
```

## 3. Quant (model=claude-opus-4-7, 188.49s)

```json
{
  "summary": "Filter-parseability is clean across all 18 proposals (every novel_dim token resolves to SUPPORTED_FIELDS, so no R1-style silent fall-through), but ~7 proposals stack 3-4 narrow gates against thin base channels and land in too_few territory; the exit batch is structurally novel but several exits encode state-transition semantics not natively expressible by the 5 live kernels (fixed/time_only/breakeven/trail/multi_tp) — those need monitoring for silent baseline collapse separate from filter parseability.",
  "analyses": [
    {
      "archetype_ref": "x_exit_on_premium_extreme_flip",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X033",
        "X034",
        "X035"
      ],
      "distinctness_notes": "No exit in the 142-exit registry uses premium_extreme deactivation; X034 watches premium normalize via different threshold/semantics.",
      "expected_triggers_30d": 1200,
      "triggers_estimate_method": "Exit applies on top of any entry; effective coverage = entries × P(premium ever in extreme). For broad pairing assume ~50% of paired-entry trades enter during premium_extreme regime; if base entry batch fires ~2400 trades/30d, ~1200 see this exit logic.",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "State-transition exit — does not map to fixed/time/be/trail/multi_tp natively; risk of silent fall-through to baseline if loop has no premium-flip kernel hook."
    },
    {
      "archetype_ref": "x_exit_on_top_trader_dec_flip",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X033",
        "X034",
        "X036"
      ],
      "distinctness_notes": "No existing exit references top_trader_position_ratio crossover.",
      "expected_triggers_30d": 600,
      "triggers_estimate_method": "Top-trader data updates ~5min cadence; flip events are rare (~25% of trades that enter at _dec see _dec→neutral within typical hold). For ~2400 paired entries × 0.25 ≈ 600 flips.",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Custom flip kernel needed; cadence lag (5m) means realized exits are structurally late vs. price."
    },
    {
      "archetype_ref": "x_exit_on_funding_pct_top_decile_decay",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X033",
        "X034"
      ],
      "distinctness_notes": "No exit decays out of funding top decile; X033 watches funding sign normalize, not decile threshold.",
      "expected_triggers_30d": 300,
      "triggers_estimate_method": "Funding settles every 8h. For OI_Price/short entries ~600/30d, P(entry in funding top decile that decays during hold) ≈ 0.5 → 300.",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Funding-decile decay maps poorly to native kernels; requires explicit decile-tracking exit logic."
    },
    {
      "archetype_ref": "x_exit_hybrid_be_then_top_trader_trail",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X053",
        "X056"
      ],
      "distinctness_notes": "Existing breakeven family (X053, X056) uses price-only BE; this composes BE with smart-money invalidation as the trail trigger.",
      "expected_triggers_30d": 2400,
      "triggers_estimate_method": "Applies broadly to any paired entry that takes BE-eligible profit (~+0.3%); ~50% of trades reach BE → ~2400 if paired across full entry batch (~4800 trades).",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "BE half maps to breakeven kernel; trail-on-flip half is custom — partial fall-through risk where BE fires but smart-money trail silently degrades to time-out."
    },
    {
      "archetype_ref": "x_exit_on_global_long_short_extreme_flip",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X033",
        "X034",
        "X035"
      ],
      "distinctness_notes": "No exit uses global_long_ratio or global_short_ratio.",
      "expected_triggers_30d": 300,
      "triggers_estimate_method": "Retail-extreme bucket is rare (~10% of trades enter during extreme); P(flip during hold) ≈ 0.3. For ~10000 trades → ~300 flips. Many trades will fall through to default exit.",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Mostly relevant to entries already gated on retail-extreme; if not paired carefully, exit fires <15% of the time and degrades to time_only baseline."
    },
    {
      "archetype_ref": "x_exit_session_rollover_partial",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X053",
        "X056",
        "X057"
      ],
      "distinctness_notes": "Session as exit-trigger is novel; existing partials are price-ladder based.",
      "expected_triggers_30d": 2000,
      "triggers_estimate_method": "~3 session boundaries/day × 30 = 90 boundaries; trades active across boundaries depend on hold time. For median 30m hold, ~25% of trades cross a session boundary → ~2000 of ~8000 trades.",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "50%-partial-then-trail composition not in 5 native kernels; high silent-fall-through risk — if val_score equals channel/side baseline it's the R1 bug pattern."
    },
    {
      "archetype_ref": "x_exit_on_taker_buy_ratio_flip_short",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X033",
        "X034",
        "X035"
      ],
      "distinctness_notes": "No exit uses taker_buy_ratio_5m crossover; existing exits are price/volume/funding only.",
      "expected_triggers_30d": 500,
      "triggers_estimate_method": "For OI_Price/short entries ~600/30d, P(taker_buy_ratio_5m crosses 0.4→0.6 during hold) ≈ 0.85 (noisy 5m series flips often) → ~500.",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Aggressor-flip exit; not in native kernels. Watch for noise — flip-then-reflip can fire prematurely without a hold-N-windows guard."
    },
    {
      "archetype_ref": "x_exit_oi_collapse_runner",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X061",
        "X062",
        "X057"
      ],
      "distinctness_notes": "OI-as-runner-condition novel; existing trail/runner kernels (X061, X062) are price/ATR based.",
      "expected_triggers_30d": 250,
      "triggers_estimate_method": "OI_Price/short ~600/30d × P(OI cascade ≥10% during hold) ~0.4 → ~250.",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Closest fit to trail family but with OI gate instead of price; cleanest of the exit batch — mathematically well-posed for cascade tail-capture."
    },
    {
      "archetype_ref": "e_pc_lowliq_smallcap_mean_revert_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E328",
        "E329",
        "E036"
      ],
      "distinctness_notes": "E328/E329 are smallcap/lowliq pumps; this is mean-revert on dumps with retail-short-extreme gate — opposite move direction + retail-flow filter.",
      "expected_triggers_30d": 15,
      "triggers_estimate_method": "5000 pc events × P(lowliq)~0.30 × P(smallcap)~0.40 × P(move<=-8)~0.10 × P(short_ratio_high)~0.25 ≈ 15.",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 4,
      "n_total_conditions": 4,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Mean-reversion → fixed family with symmetric TP/SL; multi_tp also fits. Avoid trail (no trend)."
    },
    {
      "archetype_ref": "e_r6_extreme_pump_top_trader_short_short",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E332",
        "E334"
      ],
      "distinctness_notes": "Reserved6 channel + top_trader_low + oi_pct_top_decile + premium_bps gate is structurally novel; E332/E334 are OI_Price-channel premium/OI plays.",
      "expected_triggers_30d": 3,
      "triggers_estimate_method": "800 R6 events × P(top_trader_low)~0.25 × P(oi_pct_top_decile)~0.10 × P(premium_bps>=15)~0.13 ≈ 2.6.",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Fade-extreme-pump → multi_tp or fixed with tight TP. Sample too thin to meaningfully test exit surface."
    },
    {
      "archetype_ref": "e_r6_pump_funding_neg_short_squeeze_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E330",
        "E333"
      ],
      "distinctness_notes": "Reserved6 contrarian-long with deep-negative funding + retail-extreme-short triple-gate not in registry.",
      "expected_triggers_30d": 4,
      "triggers_estimate_method": "800 R6 events × P(funding<=-0.0005)~0.05 × P(funding_abs_high)~1 (redundant) × P(short_ratio_extreme)~0.10 ≈ 4. funding_abs_high redundant with deeply-negative funding — effectively 2 independent gates.",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Squeeze continuation → trail or multi_tp with wide TP. Fragile sample — flag for caution."
    },
    {
      "archetype_ref": "e_pc_session_asian_smallcap_short",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E331",
        "E329"
      ],
      "distinctness_notes": "Session+marketcap+liquidity+move composite on short side not present in existing pricechange/short.",
      "expected_triggers_30d": 45,
      "triggers_estimate_method": "5000 pc × P(session=Asian)~0.30 × P(smallcap)~0.40 × P(lowliq)~0.30 × P(move>=5)~0.25 ≈ 45.",
      "sample_size_verdict": "tight",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 4,
      "n_total_conditions": 4,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Asian thin-book pump fade → fixed (tight TP/SL) or multi_tp scales well. Slippage risk in lowliq."
    },
    {
      "archetype_ref": "e_oi_basis_curvature_arb_short",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E332",
        "E335",
        "E330"
      ],
      "distinctness_notes": "4-extreme composite distinct from existing 2-3 condition OI_Price/short entries.",
      "expected_triggers_30d": 2,
      "triggers_estimate_method": "1400 OI events × P(basis>=0.005)~0.10 × P(premium>=25bps)~0.10 (highly correlated with basis, treat as ~1.0 conditional) × P(oi_change>=20)~0.15 × P(funding_top_decile)~0.10 ≈ 2.1. Basis/premium correlation makes this effectively a 3-gate composite.",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 4,
      "n_total_conditions": 4,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Overcrowding fade → fixed with TP at basis-mean-reversion target. Recommend Synthesizer relax basis OR premium to top-quartile to lift sample."
    },
    {
      "archetype_ref": "e_pc_volume_decile_above_p75_neg_funding_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E330",
        "E337"
      ],
      "distinctness_notes": "volume_pct_above_p75 (not top_decile) + neg funding + retail-short-high triplet differs from typical top-decile-volume gates in existing pc/long entries.",
      "expected_triggers_30d": 31,
      "triggers_estimate_method": "5000 pc × P(volume_above_p75)~0.25 × P(funding<=-0.0003)~0.10 × P(short_ratio_high)~0.25 ≈ 31.",
      "sample_size_verdict": "tight",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Pre-squeeze flow setup → fits trail (squeeze runner) and multi_tp; fixed acceptable."
    },
    {
      "archetype_ref": "e_oi_hour_utc_us_close_pump_short",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E332",
        "E337"
      ],
      "distinctness_notes": "hour_utc time-bucket gating absent from existing OI_Price/short entries.",
      "expected_triggers_30d": 12,
      "triggers_estimate_method": "1400 OI × P(hour 20-22)~0.125 × P(oi_change>=12)~0.27 × P(top_trader_dec)~0.25 ≈ 11.8.",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 4,
      "n_total_conditions": 4,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "End-of-day positioning fade → fixed with quick TP. Recommend Synthesizer widen hour band 19-23 if accepted."
    },
    {
      "archetype_ref": "e_pc_weekday_friday_short_squeeze_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E333",
        "E330"
      ],
      "distinctness_notes": "weekday=Fri restriction novel for pricechange/long.",
      "expected_triggers_30d": 2,
      "triggers_estimate_method": "5000 pc × P(weekday=Fri)~0.14 × P(funding<=-0.0004)~0.06 × P(short_ratio_extreme)~0.10 × P(midliq)~0.40 ≈ 1.7.",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 4,
      "n_total_conditions": 4,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Sample is so thin any positive score is overfitting noise — recommend dropping weekday gate as A/B baseline."
    },
    {
      "archetype_ref": "f_filter_session_us_premium_extreme",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Triple-AND filter session+premium_extreme+funding_abs_high not in 125 existing filters.",
      "expected_triggers_30d": 50,
      "triggers_estimate_method": "Filter cut rate = P(session=US)~0.40 × P(premium_extreme)~0.10 × P(funding_abs_high)~0.25 ≈ 1%. Applied to 5000 pc events → 50; applied to 1400 OI → 14.",
      "sample_size_verdict": "tight",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Filter is restrictive — track per-entry trigger when applied; if any gated entry drops below 30 triggers, filter is too tight."
    },
    {
      "archetype_ref": "cc_pricechange_then_oi_within_60s_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E330",
        "E337"
      ],
      "distinctness_notes": "Sequential-confirmation cross-channel timing window not in 66 existing cross_channel entries.",
      "expected_triggers_30d": 40,
      "triggers_estimate_method": "Filter parser only sees 3 supported conditions (volume_top_decile + oi_change>=10 + funding<=-0.0002); the 'within_60s' temporal join is descriptive, not in novel_dim. Without join: 5000 pc × 0.10 × 0.15 × 0.12 ≈ 9. With actual cross-channel join (if loop supports): widening to ~180s window OI confirmations within 5min of pc → ~40.",
      "sample_size_verdict": "tight",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Cross-channel temporal join primitive must exist in loop; if absent the 'within_60s' clause is silently dropped and archetype reduces to 3-gate pc/long entry. Synthesizer should verify loop primitive before treating as cross_channel."
    }
  ]
}
```

## 4. Risk (model=claude-opus-4-7, 99.15s)

```json
{
  "summary": "Round 4 batch shows no concrete data leakage (all novel_dim fields are pre-T0 or T0-derived) and no credential/sandbox boundary violations; main risks are concentration on rare regime windows (top_trader_dec, premium_extreme, retail-extreme co-firing) and live-system overlap on OI_Price/short pumps with the user's existing pump-long live strategy — all softened to caution per Round 3+ posture.",
  "risk_assessments": [
    {
      "archetype_ref": "x_exit_on_premium_extreme_flip",
      "leakage_risk": "none",
      "leakage_notes": "premium_extreme and premium_bps are both T0-observable real-time fields, not forward-looking.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit kernel applied to existing entries; no new position direction.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": ""
    },
    {
      "archetype_ref": "x_exit_on_top_trader_dec_flip",
      "leakage_risk": "none",
      "leakage_notes": "top_trader_position_ratio_dec is a real-time decile bucket published by Binance at 5min cadence, not post-T0.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit-only kernel.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Multitest inflation flagged because 4 proposals (this, x_exit_hybrid_be_then_top_trader_trail, e_r6_extreme_pump_top_trader_short_short, e_oi_hour_utc_us_close_pump_short) all share top_trader_position_ratio decile gates — recommend Synthesizer cap top_trader-gated archetypes per round at 2 to reduce family-wise FDR."
    },
    {
      "archetype_ref": "x_exit_on_funding_pct_top_decile_decay",
      "leakage_risk": "none",
      "leakage_notes": "funding_pct_top_decile is computed from rolling history at T0, not future funding.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit-only kernel paired with OI_Price/short.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": ""
    },
    {
      "archetype_ref": "x_exit_hybrid_be_then_top_trader_trail",
      "leakage_risk": "none",
      "leakage_notes": "BE half is price-only; top_trader half uses real-time decile observation.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit composition; no entry side effect.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Same top_trader-decile family overcrowding as x_exit_on_top_trader_dec_flip; monitor only."
    },
    {
      "archetype_ref": "x_exit_on_global_long_short_extreme_flip",
      "leakage_risk": "none",
      "leakage_notes": "global_long_ratio_extreme and global_short_ratio_extreme are observable bucket flags at decision time, not forward.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit-only.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": ""
    },
    {
      "archetype_ref": "x_exit_session_rollover_partial",
      "leakage_risk": "none",
      "leakage_notes": "session is a deterministic clock-derived field, fully T0-knowable.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Partial-close composition; does not flip side or open new positions.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": ""
    },
    {
      "archetype_ref": "x_exit_on_taker_buy_ratio_flip_short",
      "leakage_risk": "none",
      "leakage_notes": "taker_buy_ratio_5m is computed from completed 5m bars at evaluation time, not forward.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit-only kernel.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": ""
    },
    {
      "archetype_ref": "x_exit_oi_collapse_runner",
      "leakage_risk": "none",
      "leakage_notes": "oi_change_pct and oi_pct_top_decile evaluated at exit-decision time using completed-bar OI data, not future.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit-only; runner logic on existing short.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": ""
    },
    {
      "archetype_ref": "e_pc_lowliq_smallcap_mean_revert_long",
      "leakage_risk": "none",
      "leakage_notes": "All four fields (liquidity_bucket, marketcap_bucket, move_pct, global_short_ratio_high) are T0-observable.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Long mean-revert on dumps; no overlap with live OI_Price pump-long strategy (different channel + opposite-direction trigger).",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "At 5-10% sizing on $1000, lowliq+smallcap means realized slippage may dominate edge. Concentration_risk=medium because thin-book entries can stack against limited capital. Add to paper-shadow gating with explicit slippage haircut before any promote."
    },
    {
      "archetype_ref": "e_r6_extreme_pump_top_trader_short_short",
      "leakage_risk": "none",
      "leakage_notes": "All three fields are T0-observable bucket flags.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Reserved6 short on extreme pumps aligns with channel default direction; live strategy is OI_Price pump-long, different channel.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "top_trader-decile family overcrowding (4 archetypes share this gate). Monitor for sample <50 (Quant estimated 3 triggers/30d) — too thin to evaluate without longer window."
    },
    {
      "archetype_ref": "e_r6_pump_funding_neg_short_squeeze_long",
      "leakage_risk": "none",
      "leakage_notes": "funding fields and global_short_ratio_extreme are real-time observable.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "caution",
      "live_conflict_notes": "Reserved6/long contrarian could co-fire with OI_Price/long-pump live strategy on the same symbol if BWE OI&Price + Reserved6 both trigger the long side concurrently. At 5-10% sizing, two long entries on the same symbol = 10-20% effective exposure — within acceptable bounds but worth monitoring.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Paper-shadow should track concurrent-position events between this archetype and the live OI&Price pump-long; flag if same-symbol exposure exceeds 15% of capital in any 5min window."
    },
    {
      "archetype_ref": "e_pc_session_asian_smallcap_short",
      "leakage_risk": "none",
      "leakage_notes": "session, marketcap, liquidity, move_pct all T0-observable.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Asian-session smallcap short — orthogonal to live OI&Price pump-long.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Asian thin-book + smallcap + lowliq is exactly where adversarial fade risk and slippage compound. Concentration_risk=medium because Asian session smallcaps are a small symbol set — repeat triggers may load on 2-3 names. Track per-symbol trigger histogram; if top-2 symbols >40% of triggers, flag for symbol single-point failure."
    },
    {
      "archetype_ref": "e_oi_basis_curvature_arb_short",
      "leakage_risk": "none",
      "leakage_notes": "basis, premium_bps, oi_change_pct, funding_pct_top_decile are all T0-observable.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Short on OI_Price overcrowding fade — opposite to live pump-long; same-symbol same-time concurrent opposite-side trades possible but Reserved-6 short would already be flagged similarly.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "4-extreme-AND composite + basis/premium correlation = effectively a 3-gate fit on rare regime; Quant estimated 2 triggers/30d. Concentration_risk=medium because such rare events tend to cluster on 1-2 high-OI majors. Recommend Synthesizer relax basis OR premium to top-quartile per Quant suggestion."
    },
    {
      "archetype_ref": "e_pc_volume_decile_above_p75_neg_funding_long",
      "leakage_risk": "none",
      "leakage_notes": "volume_pct_above_p75, funding, global_short_ratio_high all T0-observable.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "caution",
      "live_conflict_notes": "pricechange/long pre-squeeze setup may co-fire with live OI&Price pump-long on same symbol. Monitor concurrent-exposure as with e_r6_pump_funding_neg_short_squeeze_long.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Paper-shadow concurrent-position monitoring; flag if same-symbol long exposure stacks above 15% of capital."
    },
    {
      "archetype_ref": "e_oi_hour_utc_us_close_pump_short",
      "leakage_risk": "none",
      "leakage_notes": "hour_utc deterministic; oi_change_pct and top_trader_position_ratio_dec T0-observable.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "none",
      "live_conflict_notes": "OI_Price short fade on pumps — opposite to live OI&Price pump-long, but on the SAME channel + SAME symbol scenario: live strategy may be entering long while this fades short. At $1000 / 5-10% sizing this is small but worth flagging.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Live-conflict softened to caution: Synthesizer should add a guard so this archetype does not enter when the live OI&Price pump-long is already in a position on the same symbol within the prior N minutes. Monitor in paper-shadow first."
    },
    {
      "archetype_ref": "e_pc_weekday_friday_short_squeeze_long",
      "leakage_risk": "none",
      "leakage_notes": "weekday, funding, global_short_ratio_extreme, liquidity all T0-observable.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Long-only; could stack with live pump-long but probability is low given quadruple gate.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Multitest_inflation_risk=medium because weekday gating without strong mechanism is a classic overfitting trap (Devil and Quant both flagged). Quant estimates 2 triggers/30d — any positive score is noise. Recommend Synthesizer drop weekday gate as an A/B baseline before Round 5."
    },
    {
      "archetype_ref": "f_filter_session_us_premium_extreme",
      "leakage_risk": "none",
      "leakage_notes": "session, premium_extreme, funding_abs_high all T0-observable.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Filter only — does not open positions.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": ""
    },
    {
      "archetype_ref": "cc_pricechange_then_oi_within_60s_long",
      "leakage_risk": "none",
      "leakage_notes": "Sequential-confirmation pattern uses two channel events both observable at T0_confirm; the OI confirmation at T0+60s is the new entry trigger time, not a forward-snoop on the original price event. As long as the entry timestamp is the OI-confirm timestamp (not the earlier price-event timestamp), there is no leakage.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "caution",
      "live_conflict_notes": "Long entry composing pricechange + OI_Price signals — directly overlaps with live OI&Price pump-long strategy on the same OI confirmation. High likelihood of same-symbol concurrent long exposure with live bot. At 5-10% sizing this could compound to 10-20% effective exposure on a single symbol.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Two requirements before any promote: (1) verify entry timestamp is anchored at OI-confirm time, not the earlier price event (otherwise the 'within_60s' clause is post-event window-fitting on the price side); (2) add a live-bot-position guard so this archetype does not open if the live OI&Price pump-long has an open position on the same symbol. Paper-shadow concurrent-exposure tracking required."
    }
  ]
}
```

## 5. Synthesizer (model=claude-opus-4-7, 212.02s)

```json
{
  "summary": "Round 4 batch is exit-heavy (8/18) which directly addresses R2's exit-pipeline starvation finding; filter parseability is clean across all 18 (no R1-style silent fall-through risk on the supported-fields side). Main concerns are sample-size thinness on 4-condition entries (3 revised inclusively to widen samples) and state-transition exits that need post-run kernel-fit verification. Accepted 15, revised 3, rejected 0 per Round 3+ inclusive posture.",
  "accepted_archetypes": [
    {
      "id": "X150",
      "type": "exit",
      "archetype": "x_exit_on_premium_extreme_flip",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "premium_extreme",
        "premium_bps<=5"
      ],
      "expected_distinct": true,
      "notes": "Close position when premium_extreme flag deactivates and premium_bps reverts below 5, capturing premium-mean-reversion exhaustion.",
      "synthesizer_note": "Novel premium-flip exit not in 142-exit registry; Devil flagged instant-trigger risk if paired entry lacks premium_extreme gate — recommend pairing only with premium-gated entries to avoid wash trades."
    },
    {
      "id": "X151",
      "type": "exit",
      "archetype": "x_exit_on_top_trader_dec_flip",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "top_trader_position_ratio_dec",
        "top_trader_position_ratio<=0"
      ],
      "expected_distinct": true,
      "notes": "Exit when smart-money position ratio flips from positive decile back to neutral, indicating informed flow has unwound.",
      "synthesizer_note": "Smart-money-flip exit unique in registry; 5m cadence lag (Devil) tolerable for non-scalping holds — track slippage-to-signal in monitor; one of 4 top_trader-gated archetypes (Risk multitest watch)."
    },
    {
      "id": "X152",
      "type": "exit",
      "archetype": "x_exit_on_funding_pct_top_decile_decay",
      "channel": "OI_Price",
      "side": "short",
      "novel_dim": [
        "funding_pct_top_decile",
        "funding_abs_high"
      ],
      "expected_distinct": true,
      "notes": "For shorts entered during funding-extreme regime, exit when funding decays out of top decile, locking gains before squeeze risk rises.",
      "synthesizer_note": "Clean funding-decile decay exit; all critics seems_ok with ample sample estimate (~300 trig/30d)."
    },
    {
      "id": "X153",
      "type": "exit",
      "archetype": "x_exit_hybrid_be_then_top_trader_trail",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "top_trader_position_ratio_high",
        "top_trader_position_ratio_low"
      ],
      "expected_distinct": true,
      "notes": "Move stop to breakeven on first +0.3% favorable, then exit only when top_trader_position_ratio crosses against the trade direction.",
      "synthesizer_note": "Composite BE + smart-money trail; watch BE-hit-rate vs. trail-fire-rate — if BE dominates >80%, trail half is dead weight. Top_trader-decile family member (multitest cap monitor)."
    },
    {
      "id": "X154",
      "type": "exit",
      "archetype": "x_exit_on_global_long_short_extreme_flip",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "global_long_ratio_extreme",
        "global_short_ratio_extreme"
      ],
      "expected_distinct": true,
      "notes": "Exit position when retail long/short ratio crosses out of extreme bucket (contrarian regime ends), regardless of P&L state.",
      "synthesizer_note": "Retail-extreme decay exit never used in registry; sample adequate but exit-fire-rate may fall below 15% if not paired with retail-gated entries — accept-with-watch on degradation to time_only baseline."
    },
    {
      "id": "X155",
      "type": "exit",
      "archetype": "x_exit_session_rollover_partial",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "session=US",
        "session=Asian"
      ],
      "expected_distinct": true,
      "notes": "Take 50% off at session boundary (US→Asian or Asian→European), trail rest with native exit, hedging session-specific reversal risk.",
      "synthesizer_note": "Session-boundary partial-close composition not in 5 native kernels; CRITICAL post-run check: if val_score equals channel/side baseline, this is the R1 silent-fall-through pattern — verify partial-then-trail kernel hook before merge."
    },
    {
      "id": "X156",
      "type": "exit",
      "archetype": "x_exit_on_taker_buy_ratio_flip_short",
      "channel": "OI_Price",
      "side": "short",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.6",
        "taker_buy_ratio_5m<=0.4"
      ],
      "expected_distinct": true,
      "notes": "Short exit triggered when 5m taker-buy ratio flips from <=0.4 (sellers dominant) to >=0.6 (buyers regaining), signaling short-cover risk.",
      "synthesizer_note": "Clean aggressor-flip exit; if flip-then-reflip rate >30% in monitor, add ≥2-consecutive-window guard in implementation."
    },
    {
      "id": "X157",
      "type": "exit",
      "archetype": "x_exit_oi_collapse_runner",
      "channel": "OI_Price",
      "side": "short",
      "novel_dim": [
        "oi_change_pct<=-10",
        "oi_pct_top_decile"
      ],
      "expected_distinct": true,
      "notes": "Hold short as runner while OI continues collapsing (oi_change_pct<=-10), exit only when OI stops decreasing — rides full liquidation cascade.",
      "synthesizer_note": "Most promising exit in batch — Devil and Quant both flagged as cleanest cascade-runner composition; track max-favorable-excursion vs. realized exit price to verify tail-capture."
    },
    {
      "id": "E338",
      "type": "entry",
      "archetype": "e_pc_lowliq_smallcap_mean_revert_long",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "liquidity_bucket=low",
        "marketcap_bucket=small",
        "move_pct<=-8",
        "global_short_ratio_high"
      ],
      "expected_distinct": true,
      "notes": "Long mean-reversion on small-cap low-liquidity dumps where retail is extreme short — symmetric SL=TP target around natural ATR.",
      "synthesizer_note": "Sample tight (~15 trig/30d) and global_short_ratio may be NaN for smallcaps (Devil concern); accept-with-watch — REQUIRED: paper-shadow with explicit slippage haircut and verify global_short_ratio populated for >70% of triggers before any promote."
    },
    {
      "id": "E339",
      "type": "entry",
      "archetype": "e_r6_extreme_pump_top_trader_short_short",
      "channel": "Reserved6",
      "side": "short",
      "novel_dim": [
        "top_trader_position_ratio_low",
        "oi_pct_top_decile",
        "premium_bps>=15"
      ],
      "expected_distinct": true,
      "notes": "Short Reserved6 8-15% pumps when smart money sits in low decile + OI top decile + premium >=15bps — fade retail-driven extreme moves.",
      "synthesizer_note": "Triple-orthogonal Reserved6/short rare in registry; Quant estimates only ~3 trig/30d — accept-with-watch, may need 60-90d evaluation window. Member of top_trader-decile family (multitest cap monitor)."
    },
    {
      "id": "E340",
      "type": "entry",
      "archetype": "e_r6_pump_funding_neg_short_squeeze_long",
      "channel": "Reserved6",
      "side": "long",
      "novel_dim": [
        "funding<=-0.0005",
        "funding_abs_high",
        "global_short_ratio_extreme"
      ],
      "expected_distinct": true,
      "notes": "Long Reserved6 events when funding deeply negative + retail extremely short — primed for short-squeeze continuation.",
      "synthesizer_note": "Reserved6 contrarian-long thin sample (~4 trig/30d); Risk flagged live-conflict with OI&Price pump-long bot — paper-shadow MUST track concurrent-position events on same symbol; flag if same-symbol exposure exceeds 15% of capital in any 5min window."
    },
    {
      "id": "E341",
      "type": "entry",
      "archetype": "e_pc_session_asian_smallcap_short",
      "channel": "pricechange",
      "side": "short",
      "novel_dim": [
        "session=Asian",
        "marketcap_bucket=small",
        "liquidity_bucket=low",
        "move_pct>=5"
      ],
      "expected_distinct": true,
      "notes": "Short Asian-session small-cap low-liq pumps with move_pct>=5 — exploits known Asian-session retail FOMO + thin book.",
      "synthesizer_note": "4 supported conditions; sample tight (~45) and Risk flagged single-symbol concentration risk — track per-symbol trigger histogram, flag if top-2 symbols >40% of triggers."
    },
    {
      "id": "E342",
      "type": "entry",
      "archetype": "e_pc_volume_decile_above_p75_neg_funding_long",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "volume_pct_above_p75",
        "funding<=-0.0003",
        "global_short_ratio_high"
      ],
      "expected_distinct": true,
      "notes": "Long pricechange when volume above p75 + funding negative + retail short_high — captures pre-squeeze setup with confirmed flow.",
      "synthesizer_note": "Cleanest entry in batch with ample sample (~31); track lift vs. existing pc_pump_neg_funding_long baseline to confirm volume_p75 gate adds value over volume_top_decile. Live-conflict watch with pump-long bot."
    },
    {
      "id": "F126",
      "type": "filter",
      "archetype": "f_filter_session_us_premium_extreme",
      "channel": "*",
      "side": "NA",
      "novel_dim": [
        "session=US",
        "premium_extreme",
        "funding_abs_high"
      ],
      "expected_distinct": true,
      "notes": "Restrict any entry to US session AND premium_extreme AND funding_abs_high — high-conviction regime gate to reduce false positives.",
      "synthesizer_note": "Triple regime filter not in 125 existing filters; restrictive (~1% pass rate) — track per-entry trigger when applied, drop filter if any gated entry falls below 30 triggers."
    },
    {
      "id": "C067",
      "type": "cross_channel",
      "archetype": "cc_pricechange_then_oi_within_60s_long",
      "channel": "*",
      "side": "long",
      "novel_dim": [
        "volume_pct_top_decile",
        "oi_change_pct>=10",
        "funding<=-0.0002"
      ],
      "expected_distinct": true,
      "notes": "Long when pricechange channel fires first then OI_Price confirms within ~60s with OI-pump + volume-decile + neg funding — sequential confirmation pattern.",
      "synthesizer_note": "Two pre-promote requirements (Risk): (1) verify loop has cross-channel temporal join primitive — without it, the 'within_60s' clause silently drops and reduces to 3-gate pc/long entry; (2) verify entry timestamp anchored at OI-confirm time, not earlier price event, to avoid leakage. Live-bot-position guard required against pump-long bot."
    }
  ],
  "revised_archetypes": [
    {
      "original_archetype_ref": "e_oi_basis_curvature_arb_short",
      "revised_archetype": "e_oi_basis_oi_funding_overcrowd_short",
      "revision_reason": "Quant flagged ~2 trig/30d (too_few) and Devil noted basis/premium correlation makes it effectively a 3-gate fit; revising inclusively by dropping the redundant premium_bps>=25 (correlated with basis) and softening basis>=0.005→0.003 and oi_change_pct>=20→15 to lift sample to a testable threshold.",
      "revised_novel_dim": [
        "basis>=0.003",
        "oi_change_pct>=15",
        "funding_pct_top_decile"
      ],
      "revised_notes": "Short OI_Price overcrowding fade when basis premium + OI-pump + funding-top-decile co-fire — preserves the overcrowding thesis but removes basis/premium redundancy and softens thresholds to gain ~3-4x more triggers."
    },
    {
      "original_archetype_ref": "e_oi_hour_utc_us_close_pump_short",
      "revised_archetype": "e_oi_hour_utc_us_close_pump_short",
      "revision_reason": "Quant estimated ~12 trig/30d (too_few) on the original 20-22 UTC band; widening to 19-23 UTC per Quant's explicit recommendation to lift sample while preserving the US-close-window thesis.",
      "revised_novel_dim": [
        "hour_utc>=19",
        "hour_utc<=23",
        "oi_change_pct>=12",
        "top_trader_position_ratio_dec"
      ],
      "revised_notes": "Short OI-pumps occurring during extended US-close window (19-23 UTC) where smart money is top-decile long — fade end-of-day positioning. Note: still in top_trader-decile multitest family; live-conflict guard with pump-long bot required."
    },
    {
      "original_archetype_ref": "e_pc_weekday_friday_short_squeeze_long",
      "revised_archetype": "e_pc_neg_funding_extreme_short_midliq_long",
      "revision_reason": "Devil flagged weekday=Fri as classic overfitting trap and Quant estimated ~2 trig/30d (too_few); dropping the weekday gate per all critics' recommendation, keeping the funding+retail-short-extreme+midliq core thesis as A/B baseline before any future weekday A/B.",
      "revised_novel_dim": [
        "funding<=-0.0004",
        "global_short_ratio_extreme",
        "liquidity_bucket=mid"
      ],
      "revised_notes": "Long pricechange short-squeeze setup: deep-negative funding + retail extremely short + mid-liquidity (not too thin to manipulate). If next round wants to test Fri specifically, run as paired A/B against this baseline."
    }
  ],
  "rejected_archetypes": [],
  "next_round_focus": "Round 5 should (a) validate the 8 novel exit kernels (X150-X157) by comparing val_scores against fixed/trail/multi_tp baselines on the same entries — any exit producing identical baseline score is the R1 silent-fall-through pattern and must be flagged for kernel-hook implementation; (b) expand Reserved6/short and pricechange/short entry lines beyond the over-represented top_trader-decile family (4 archetypes already share that gate) to reduce family-wise FDR; (c) propose more entries that are paired with the asymmetric-TP/SL-resistant scoring (mean, kelly_capped, p25_capped_tail) to surface true left-tail-aware edges per the E126 paper-shadow lesson."
}
```
