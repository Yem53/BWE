# Debate transcript: debate_20260428_014439

- Trigger: `manual`
- Models: {'pattern_miner': 'claude-opus-4-7', 'generator': 'claude-opus-4-7', 'steelman': 'claude-opus-4-7', 'devil': 'claude-opus-4-7', 'quant': 'claude-opus-4-7', 'risk': 'claude-opus-4-7', 'metric_critic': 'claude-opus-4-7', 'synthesizer': 'claude-opus-4-7', 'self_reflection': 'claude-opus-4-7', 'behavior_annotator': 'claude-opus-4-7', 'cross_pair_recommender': 'claude-opus-4-7'}
- Existing archetypes: 603 total
- Results so far: {'total': 26562, 'by_status': {'discard': 26562}, 'best_score': None, 'n_keeps': 0}

## 1. Generator (model=claude-opus-4-7, 140.33s)

```json
{
  "summary": "Round 4 generator targets the starved exit pipeline (8 of 18 proposals) with hybrid kernels triggered by funding/OI/premium/taker-flow signals, plus 5 multi-signal entries leveraging negative-funding squeeze, contrarian top-trader, and new-listing volatility — all using only validated SUPPORTED_FIELDS to avoid the R1 silent-skip bug.",
  "proposals": [
    {
      "archetype": "x_funding_flip_oi_decay",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "funding_rate<=0",
        "oi_change_pct<=-2"
      ],
      "notes": "Exit when funding flips against position AND OI starts decaying — orthogonal microstructure trigger before price reverses.",
      "rationale": "None of the 5 exit kernels (fixed/time_only/breakeven/trail/multi_tp) currently combines real-time funding sign change with OI decay; this adds a market-structure exit independent of price path.",
      "expected_distinct": true
    },
    {
      "archetype": "x_top_trader_reversal_exit",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "top_trader_position_ratio_dec"
      ],
      "notes": "Exit position when smart-money top-trader position ratio enters decline regime — leading indicator of impending reversal.",
      "rationale": "Existing exits are all price-based or time-based; using top_trader flag as exit trigger is structurally new and uses a real-time observable Binance metric.",
      "expected_distinct": true
    },
    {
      "archetype": "x_premium_collapse_be_lock",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "premium_bps<=5",
        "premium_bps>=-5"
      ],
      "notes": "Lock breakeven when premium_bps collapses to neutral band — premium decay signals exhaustion of the futures-spot spread driver.",
      "rationale": "X101+ exit family lacks premium-aware breakeven kernels; this fuses premium normalization with BE protection, distinct from time/price-based BE.",
      "expected_distinct": true
    },
    {
      "archetype": "x_basis_neutral_quick",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "basis_rate>=-0.01",
        "basis_rate<=0.01"
      ],
      "notes": "Quick exit when basis_rate normalizes to ±1% band — basis convergence often precedes mean reversion in perp markets.",
      "rationale": "No existing exit uses basis convergence as the primary trigger; orthogonal to price/funding/OI dimensions used by the 5 kernels.",
      "expected_distinct": true
    },
    {
      "archetype": "x_volume_decay_trail_tighten",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "volume_pct_below_p25"
      ],
      "notes": "Tighten trailing stop when volume drops below p25 — momentum exhaustion signal that classical trail kernels ignore.",
      "rationale": "Current trail (X-series) uses fixed ATR multiplier irrespective of volume regime; volume-conditioned trail tightening is structurally new.",
      "expected_distinct": true
    },
    {
      "archetype": "x_taker_inversion_exit_long",
      "type": "exit",
      "channel": "*",
      "side": "long",
      "novel_dim": [
        "taker_buy_ratio_5m<=0.45"
      ],
      "notes": "Close long when 5m taker buy ratio inverts below 0.45 — aggressive sellers taking control of order flow.",
      "rationale": "Order-flow-based exit; existing exit kernels do not consume taker_buy_ratio as a stop trigger — purely orthogonal to TP/SL/trail logic.",
      "expected_distinct": true
    },
    {
      "archetype": "x_session_aware_widen_us",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "session=US",
        "hour_utc>=14"
      ],
      "notes": "Widen TP and tighten SL during US session — different volatility regime than Asian; static exits underperform across sessions.",
      "rationale": "None of the 126 existing exits is session-conditioned; using session as an exit-parameter selector is structurally new.",
      "expected_distinct": true
    },
    {
      "archetype": "x_global_long_normalize_short",
      "type": "exit",
      "channel": "*",
      "side": "short",
      "novel_dim": [
        "global_long_ratio_high"
      ],
      "notes": "Close short when global long ratio fades from extreme to merely high — squeeze pressure relief, take profit on trend exhaustion.",
      "rationale": "Sentiment-normalization exit; existing exits do not use global_long_ratio transitions, structurally distinct from price/time stops.",
      "expected_distinct": true
    },
    {
      "archetype": "e_neg_funding_oi_squeeze_long",
      "type": "entry",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "oi_change_pct>=15",
        "funding<=-0.04",
        "premium_bps<=-15"
      ],
      "notes": "Long when OI surges with deeply negative funding AND discount premium — classic short-squeeze setup with three orthogonal confirmations.",
      "rationale": "Triple-condition entry combining OI momentum + funding extreme + premium discount; existing OI_Price/long archetypes typically use 1-2 of these, not all three jointly.",
      "expected_distinct": true
    },
    {
      "archetype": "e_top_trader_contrarian_pump_short",
      "type": "entry",
      "channel": "pricechange",
      "side": "short",
      "novel_dim": [
        "top_trader_position_ratio_high",
        "event_type=pump",
        "volume_pct_top_decile"
      ],
      "notes": "Short pump events when top-trader ratio is already crowded long — fade smart-money exhaustion with volume confirmation.",
      "rationale": "Contrarian top-trader entry on pricechange channel is not in registry; combines crowdedness flag with event-type and volume gate, structurally novel.",
      "expected_distinct": true
    },
    {
      "archetype": "e_basis_extreme_premium_short",
      "type": "entry",
      "channel": "OI_Price",
      "side": "short",
      "novel_dim": [
        "basis_rate>=0.05",
        "premium_extreme",
        "oi_change_pct>=10"
      ],
      "notes": "Short when basis blows out >5% AND premium extreme AND OI surging — classic perp overheating, mean reversion setup.",
      "rationale": "Basis-rate-driven short entry combined with premium_extreme flag is not in 81 OI_Price archetypes; uses an under-exploited curvature dimension.",
      "expected_distinct": true
    },
    {
      "archetype": "e_new_listing_funding_extreme_long",
      "type": "entry",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "listing_age_days<=30",
        "funding_abs_extreme",
        "liquidity_bucket=mid"
      ],
      "notes": "Long new listings (≤30d) when funding is at extreme and liquidity is mid — early-stage volatility with absorbable size.",
      "rationale": "Listing-age conditioning is rare in registry; combining with funding_abs_extreme + liquidity gate creates a fresh-token edge case not covered.",
      "expected_distinct": true
    },
    {
      "archetype": "e_global_short_squeeze_volume_long",
      "type": "entry",
      "channel": "Reserved6",
      "side": "long",
      "novel_dim": [
        "global_short_ratio_extreme",
        "volume_pct_top_decile",
        "event_type=crash"
      ],
      "notes": "Long Reserved6 crashes when global retail is extremely short AND volume is top-decile — squeeze fuel meets capitulation.",
      "rationale": "Existing R6 long archetypes mostly use small-cap/low-liq filters; using global_short_ratio_extreme as a sentiment gate on R6 is structurally distinct.",
      "expected_distinct": true
    },
    {
      "archetype": "f_midcap_us_session_gate",
      "type": "filter",
      "channel": "*",
      "side": "NA",
      "novel_dim": [
        "marketcap_bucket=mid",
        "session=US",
        "quote_volume_24h>=20000000"
      ],
      "notes": "Gate trades to mid-cap symbols during US session with healthy volume — best signal-to-noise band per session-cap analysis.",
      "rationale": "Session × marketcap_bucket × volume joint filter is not present in 121 filter archetypes; combines three orthogonal market-quality dims.",
      "expected_distinct": true
    },
    {
      "archetype": "f_low_liq_funding_abs_only",
      "type": "filter",
      "channel": "*",
      "side": "NA",
      "novel_dim": [
        "liquidity_bucket=low",
        "funding_abs_extreme",
        "listing_age_days>=90"
      ],
      "notes": "Only allow trades on low-liquidity symbols with funding extreme but excluding ultra-new listings — wild-but-not-untested universe.",
      "rationale": "Three-way liq × funding × listing-age filter is not in registry; isolates a specific risk-reward niche distinct from existing filters.",
      "expected_distinct": true
    },
    {
      "archetype": "r_inverse_volatility_size",
      "type": "risk",
      "channel": "*",
      "side": "NA",
      "novel_dim": [
        "move_pct<=3",
        "day_change_pct<=10",
        "day_change_pct>=-10"
      ],
      "notes": "Skip entries when symbol already moved >3% on the bar OR >10% on the day — chase-prevention to protect against late-stage continuation traps.",
      "rationale": "Existing risk archetypes use position sizing scalars; this one uses move_pct + day_change_pct as a hard gate, structurally distinct from sizing kernels.",
      "expected_distinct": true
    },
    {
      "archetype": "cc_oi_pc_synced_30s_long",
      "type": "cross_channel",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "oi_change_pct>=10",
        "event_type=pump",
        "taker_buy_ratio_5m>=0.55"
      ],
      "notes": "Trigger long only when OI_Price pump AND pricechange pump fire within 30s of each other AND taker flow confirms — synchronous multi-channel agreement.",
      "rationale": "Existing 62 cross_channel archetypes mostly use sequential timing; this requires synchronous (<30s) cross-confirmation with taker-flow gate, structurally new.",
      "expected_distinct": true
    },
    {
      "archetype": "cc_oi_then_r6_lowliq_short",
      "type": "cross_channel",
      "channel": "Reserved6",
      "side": "short",
      "novel_dim": [
        "oi_change_pct>=15",
        "liquidity_bucket=low",
        "global_long_ratio_high"
      ],
      "notes": "Short Reserved6 events when OI_Price already flagged within 60s AND symbol is low-liquidity AND retail is leaning long — liquidation cascade setup.",
      "rationale": "Combines cross-channel sequential timing with liquidity + sentiment gates; the joint conditioning isn't in current 49 R6/short archetypes.",
      "expected_distinct": true
    }
  ]
}
```

## 2. Devil (model=claude-opus-4-7, 189.85s)

```json
{
  "summary": "Round 4 generator delivers solid orthogonal coverage especially for the starved exit pipeline, but several proposals carry concrete concerns around metric cadence (funding 8h, top_trader 5m), scale notation ambiguity (basis_rate / funding decimals), state-vs-transition mismatches, and at least one direct conflict with Reserved6 channel semantics — none are hard logical defects, all worth paper-shadow monitoring.",
  "critiques": [
    {
      "archetype_ref": "x_funding_flip_oi_decay",
      "verdict": "possibly_fail",
      "concerns": [
        "Binance perp funding settles every 8h and intra-period funding_rate moves slowly; for typical BWE event hold times (minutes to a few hours), 'flip' will rarely trigger except near settlement, drastically reducing the exit's sampling rate.",
        "novel_dim is symmetric (channel='*', side='both') but funding-against-position semantics requires knowing position side — verify the engine resolves side correctly before applying."
      ],
      "monitoring_advice": "In paper-shadow, log the time from entry to first funding-flip+OI-decay co-occurrence; if median lag > position median hold time, the exit is effectively dead-letter."
    },
    {
      "archetype_ref": "x_top_trader_reversal_exit",
      "verdict": "possibly_fail",
      "concerns": [
        "top_trader_position_ratio is published on Binance as ~5min snapshots; for trades shorter than 5–10min the regime tag will lag the price action it is supposed to lead.",
        "'_dec' regime is undefined in novel_dim (slope window? threshold?) — risk of silent fall-through to baseline if SUPPORTED_FIELDS doesn't include the decline regime flag."
      ],
      "monitoring_advice": "Track exit-trigger latency vs position MFE; flag if >50% of triggers fire after price has already moved >0.5% adverse."
    },
    {
      "archetype_ref": "x_premium_collapse_be_lock",
      "verdict": "possibly_fail",
      "concerns": [
        "premium_bps in [-5, +5] is a tight band that many liquid perps occupy continuously — the BE lock could trigger at or near entry, collapsing into 'immediate BE' equivalent to a degenerate fixed exit."
      ],
      "monitoring_advice": "Measure fraction of positions where premium_collapse fires within the first 30s post-entry; if >30%, this kernel is degenerate."
    },
    {
      "archetype_ref": "x_basis_neutral_quick",
      "verdict": "possibly_fail",
      "concerns": [
        "basis_rate band [-0.01, +0.01] interpreted as ±1% is an order of magnitude wider than typical Binance perp basis (usually <0.1% absolute outside extremes); under that interpretation the quick exit is effectively always-on at entry.",
        "If the field is in raw decimal (0.01 = 1%) vs basis-points-as-decimal, the trigger semantics flip — confirm scale before counting this as a real exit."
      ],
      "monitoring_advice": "On first 100 paper-shadow fires, dump basis_rate distribution at entry; if >70% already sit inside ±1% the kernel is degenerate and should be retuned to ±0.1%."
    },
    {
      "archetype_ref": "x_volume_decay_trail_tighten",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "Standard trail-tightening monitoring: confirm tightened stops do not increase whipsaw rate disproportionately versus baseline trail."
    },
    {
      "archetype_ref": "x_taker_inversion_exit_long",
      "verdict": "possibly_fail",
      "concerns": [
        "taker_buy_ratio_5m frequently dips below 0.45 during normal uptrend pullbacks (intra-trend noise) — risks early-exit on profitable trades, especially on Reserved6 long crashes where post-flush taker flow is naturally seller-heavy briefly before squeeze."
      ],
      "monitoring_advice": "In paper-shadow, compare exit P&L vs counterfactual hold-to-fixed-TP; if the taker-inversion exit consistently caps gains short of TP, classify as too-tight."
    },
    {
      "archetype_ref": "x_session_aware_widen_us",
      "verdict": "possibly_fail",
      "concerns": [
        "Condition hour_utc>=14 is unbounded above and will keep matching through 23:59 UTC into the Asia overlap; US session is canonically ~14:00–21:00 UTC.",
        "'Widen TP and tighten SL' simultaneously is internally consistent but doesn't specify magnitudes — without parameter binding the kernel may not differ from the static baseline."
      ],
      "monitoring_advice": "Add an upper hour_utc bound (<22) and verify TP/SL multipliers actually deviate from the non-US baseline in the run logs."
    },
    {
      "archetype_ref": "x_global_long_normalize_short",
      "verdict": "possibly_fail",
      "concerns": [
        "The notes describe a transition ('fades from extreme to merely high') but novel_dim only encodes a static state ('global_long_ratio_high'); without a from→to comparator the trigger is just 'high', not 'normalizing'.",
        "Static high state on a short position is the wrong-side condition for taking profit — should likely be exiting on transition AWAY from extreme, not on the high state itself."
      ],
      "monitoring_advice": "Confirm the engine resolves a transition predicate from the current state field; if not, this kernel reduces to 'always exit shorts when crowd is long', which is semantically backwards."
    },
    {
      "archetype_ref": "e_neg_funding_oi_squeeze_long",
      "verdict": "possibly_fail",
      "concerns": [
        "funding<=-0.04 is ambiguous in scale: as decimal funding_rate (-4% per 8h) it is essentially never observed on Binance (cap is around ±0.75%/8h); as basis-points-as-decimal (-4 bps) it is mildly negative and very common — the conjunction's selectivity changes by orders of magnitude depending on interpretation.",
        "Triple-condition conjunction (oi>=15%, funding extreme, premium discount) is genuine signal but historically produces tiny sample (single-digit triggers/30d) — may starve the GPU loop."
      ],
      "monitoring_advice": "Before promoting, dump the trigger count over the 30-day window; if <50 events, paper-shadow won't have power."
    },
    {
      "archetype_ref": "e_top_trader_contrarian_pump_short",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "Same top_trader 5min snapshot caveat as x_top_trader_reversal_exit — note the staleness when interpreting 'crowded long' at event time."
    },
    {
      "archetype_ref": "e_basis_extreme_premium_short",
      "verdict": "possibly_fail",
      "concerns": [
        "basis_rate>=0.05 has the same scale ambiguity as x_basis_neutral_quick; if interpreted as 5% basis, the trigger is essentially never observed on Binance; if 0.05% (5bps), it is routine and not 'extreme'.",
        "premium_extreme + basis_rate are highly correlated dimensions — the conjunction may not add real orthogonality beyond the existing premium_extreme entries."
      ],
      "monitoring_advice": "Reconcile basis_rate scale with the data loader; rerun trigger counts after fix."
    },
    {
      "archetype_ref": "e_new_listing_funding_extreme_long",
      "verdict": "possibly_fail",
      "concerns": [
        "funding_abs_extreme is unsigned but the entry is directional long; for longs the favorable funding state is deeply negative, so an unsigned absolute condition would also fire on extremely positive funding (bearish for longs) — potential wrong-side firing.",
        "Listing_age<=30d on Binance often coincides with margin/leverage caps and thin liquidity; even valid signals may be unfeasible in real $1000 sizing."
      ],
      "monitoring_advice": "Constrain to funding<=-X (sign-aware) OR add a cross-check that fires only when funding sign is favorable for the position side."
    },
    {
      "archetype_ref": "e_global_short_squeeze_volume_long",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "R6 long is empirically alive (E316–E327 show best=+0.202, lift=+0.343 at trig=120) so the contrarian R6-long premise is supported; just monitor sample size when adding the global_short_ratio_extreme + top-decile-volume joint gate, which will narrow events significantly."
    },
    {
      "archetype_ref": "f_midcap_us_session_gate",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "Filter is conservative — track residual trigger count after gating; if it drops below ~30 events/30d, the resulting strategies will lack power."
    },
    {
      "archetype_ref": "f_low_liq_funding_abs_only",
      "verdict": "possibly_fail",
      "concerns": [
        "liquidity_bucket=low + funding_abs_extreme is exactly the regime where backtest fills diverge most sharply from real fills (slippage, partial fills, taker-only at adverse premium); kernel-level metrics may look attractive while live P&L erodes 30–80%.",
        "funding_abs_extreme is again unsigned and used here as a generic filter — fine for filter use, but downstream entries must apply sign-awareness."
      ],
      "monitoring_advice": "Mandatory paper-shadow comparison of in-bar fill price vs assumed mid-price for any combo gated by this filter; reject if shadow slippage >25% of expected edge."
    },
    {
      "archetype_ref": "r_inverse_volatility_size",
      "verdict": "possibly_fail",
      "concerns": [
        "The risk gate caps move_pct<=3 and |day_change_pct|<=10, but Reserved6 is defined as 180s 8–15% extreme moves — applied as a universal risk filter this archetype EXCLUDES the entire R6 channel by construction, which conflicts with R6 entries the same generator batch is producing.",
        "Day-change cap of ±10% will also eliminate most pricechange-channel pump events on small caps (where 10%+ daily moves are routine), starving the pricechange-long pipeline."
      ],
      "monitoring_advice": "Either restrict the risk archetype's channel scope to OI_Price/pricechange (excluding R6) or relax thresholds (move_pct<=8, day_change<=20) before letting the synthesizer compose with R6 entries."
    },
    {
      "archetype_ref": "cc_oi_pc_synced_30s_long",
      "verdict": "possibly_fail",
      "concerns": [
        "Timing window is 30s but the gate field taker_buy_ratio_5m is computed over a 5-minute lookback; ~9/10 of that window is pre-event data, so the gate measures pre-burst flow rather than the synchronous burst itself — likely diluted signal.",
        "Sub-30s OI/pricechange synchronization is rare on the 30-day dataset; expect <100 triggers and verify before scoring."
      ],
      "monitoring_advice": "Replace taker_buy_ratio_5m with taker_buy_ratio_1m (if SUPPORTED) or accept that this kernel is gated by stale flow data."
    },
    {
      "archetype_ref": "cc_oi_then_r6_lowliq_short",
      "verdict": "possibly_fail",
      "concerns": [
        "OI_Price alerts often auto-precede Reserved6 alerts on the same symbol because OI thresholds are easier to breach than the 8–15%/180s R6 trigger — the 'sequential confirmation' may be tautological detection of a single underlying event rather than two independent signals.",
        "Adding low-liquidity gate to short entries amplifies execution risk: fills on low-liq shorts during cascade liquidations are notoriously bad; kernel may look great in backtest but lose 30%+ to slippage in paper-shadow."
      ],
      "monitoring_advice": "Validate that the OI_Price→R6 gap is >5s on the historical alerts; if median gap <2s the 'cross-channel' label is misleading. Also enforce strict slippage modeling for low-liq shorts."
    }
  ]
}
```

## 3. Quant (model=claude-opus-4-7, 172.6s)

```json
{
  "summary": "All 18 proposals pass the filter-DSL parseability check (zero fall-through conditions — a clean improvement over the R1 50% silent-skip rate); main mathematical concerns are sample-starvation on the triple-conditioned entry archetypes (~5 of 18 likely <30 triggers/30d) and scale-ambiguity on funding/basis_rate fields that the Devil flagged.",
  "analyses": [
    {
      "archetype_ref": "x_funding_flip_oi_decay",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X053-X082 series"
      ],
      "distinctness_notes": "First exit kernel combining funding sign-flip with OI decay; orthogonal to all 5 live exit kernels (fixed/time_only/breakeven/trail/multi_tp) which are price/time-based.",
      "expected_triggers_30d": 2400,
      "triggers_estimate_method": "As exit kernel applied across positions (~5000 universe per combo) × ~50% funding<=0 × ~10% oi_change_pct<=-2 co-occurrence ≈ 250 firings per typical entry pipeline",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Pairs naturally with breakeven (lock at funding flip) and trail (tighten on OI decay); least useful with time_only."
    },
    {
      "archetype_ref": "x_top_trader_reversal_exit",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X053-X082"
      ],
      "distinctness_notes": "First exit using top_trader_position_ratio_dec flag; structurally orthogonal to the 5 price/time exit kernels.",
      "expected_triggers_30d": 1250,
      "triggers_estimate_method": "Flag token _dec ≈ p25 regime → ~25% of position lifetimes fire this exit",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Best with breakeven and trail; weak with multi_tp (would short-circuit ladder)."
    },
    {
      "archetype_ref": "x_premium_collapse_be_lock",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X053-X082"
      ],
      "distinctness_notes": "First premium-aware breakeven kernel; orthogonal to time/price-based BE.",
      "expected_triggers_30d": 3000,
      "triggers_estimate_method": "premium_bps in [-5,+5] is the modal range for liquid perps → very high firing rate; degeneracy risk",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Breakeven family only; likely degenerate (Devil flag valid) — recommend tightening band to [-2,+2] bps before deep eval."
    },
    {
      "archetype_ref": "x_basis_neutral_quick",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X053-X082"
      ],
      "distinctness_notes": "First basis-convergence exit; orthogonal to existing exit kernels.",
      "expected_triggers_30d": 2500,
      "triggers_estimate_method": "Scale-dependent: if decimal (±1%) → ~80% always-on (degenerate); if interpreted as bps → ~50% activation",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Quick/time_only exit family; scale ambiguity on basis_rate must be resolved at data-loader level before scoring is meaningful."
    },
    {
      "archetype_ref": "x_volume_decay_trail_tighten",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X053-X082"
      ],
      "distinctness_notes": "First volume-conditioned trail kernel; existing trails use static ATR multiplier.",
      "expected_triggers_30d": 1250,
      "triggers_estimate_method": "volume_pct_below_p25 by construction fires on ~25% of position lifetimes",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Trail family only; cleanest pairing with X-series acceleration/decay variants."
    },
    {
      "archetype_ref": "x_taker_inversion_exit_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X053-X082"
      ],
      "distinctness_notes": "First order-flow-based exit; structurally distinct from price/time stops.",
      "expected_triggers_30d": 1500,
      "triggers_estimate_method": "taker_buy_ratio_5m<=0.45 fires roughly 30% of long-position bars",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Long-only; pair with breakeven for protection, avoid trail (Devil flag: early-exits during pullbacks)."
    },
    {
      "archetype_ref": "x_session_aware_widen_us",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X053-X082"
      ],
      "distinctness_notes": "First session-conditioned exit parameter selector; novel dimension among 126 existing exits.",
      "expected_triggers_30d": 900,
      "triggers_estimate_method": "hour_utc>=14 → ~42% of clock; session=US conjunction ≈ 30% of total positions",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Acts as parameter modulator; recommend bounding hour_utc<22 (Devil flag valid) and binding explicit TP/SL multipliers before scoring."
    },
    {
      "archetype_ref": "x_global_long_normalize_short",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X053-X082"
      ],
      "distinctness_notes": "First sentiment-state-based short exit; orthogonal to price kernels.",
      "expected_triggers_30d": 1250,
      "triggers_estimate_method": "global_long_ratio_high (≥p75) → ~25% of short-position bars",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Short-only; Devil flag valid — semantics are static-state not transition. Without _extreme→_high transition support, kernel is wrong-sided. Flag for synthesizer to either reframe as 'while crowd long, hold' or augment with transition logic."
    },
    {
      "archetype_ref": "e_neg_funding_oi_squeeze_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E007-E327 OI long series"
      ],
      "distinctness_notes": "Triple orthogonal: OI surge + funding extreme + premium discount; existing OI/long archetypes use 1-2 of these conditions, not all 3 jointly.",
      "expected_triggers_30d": 18,
      "triggers_estimate_method": "1400 OI_Price events × 0.25 (oi>=15%) × 0.20 (funding<=-0.04 if interpreted as 4bp; ~1% if -4%) × 0.25 (premium<=-15bps) ≈ 18; Devil scale-ambiguity flag valid",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Squeeze setup → multi_tp ladder optimal; small sample but high-conviction — synthesizer may still keep for diversity even though stats power is weak."
    },
    {
      "archetype_ref": "e_top_trader_contrarian_pump_short",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E001-E253 pricechange short series"
      ],
      "distinctness_notes": "First contrarian top_trader short on pricechange channel; combines crowdedness flag + event-type + volume gate.",
      "expected_triggers_30d": 62,
      "triggers_estimate_method": "5000 pricechange × 0.5 (pump events) × 0.25 (top_trader_high) × 0.10 (volume_top_decile) = 62",
      "sample_size_verdict": "tight",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Fade exhaustion → fixed or breakeven preferred; trail likely whipsaws during chop."
    },
    {
      "archetype_ref": "e_basis_extreme_premium_short",
      "distinct": true,
      "distinct_from_existing_ids": [
        "OI_Price short series"
      ],
      "distinctness_notes": "First basis-rate-driven short on OI_Price; uses curvature dimension under-exploited in registry.",
      "expected_triggers_30d": 8,
      "triggers_estimate_method": "1400 OI_Price × 0.05 (basis>=0.05 — narrow under either scale) × 0.10 (premium_extreme) × 0.40 (oi>=10%) ≈ 3-15; Devil correlation flag valid (premium and basis correlate)",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Mean-reversion short → fixed/breakeven; basis_rate scale must be resolved before this is computable in practice."
    },
    {
      "archetype_ref": "e_new_listing_funding_extreme_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "pricechange long series"
      ],
      "distinctness_notes": "Listing-age conditioning is rare in registry; combines with funding_abs_extreme + liquidity gate for fresh-token niche.",
      "expected_triggers_30d": 17,
      "triggers_estimate_method": "5000 pricechange × 0.10 (listing_age<=30d) × 0.10 (funding_abs_extreme) × 0.33 (liq=mid) ≈ 17",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Devil flag valid — funding_abs_extreme is unsigned and direction-agnostic; recommend synthesizer add explicit funding<=-X for long-side semantic safety."
    },
    {
      "archetype_ref": "e_global_short_squeeze_volume_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E316-E327 r6_extreme_*_long"
      ],
      "distinctness_notes": "Existing R6 long archetypes use small-cap/low-liq filters; global_short_ratio_extreme as sentiment gate is novel for this channel.",
      "expected_triggers_30d": 6,
      "triggers_estimate_method": "800 R6 × 0.70 (crash events on R6) × 0.10 (global_short_extreme p90) × 0.10 (volume_top_decile) ≈ 6",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Squeeze fuel → multi_tp ladder; sample is thin but R6/long is empirically alive (E316-E327 lift +0.343), so even small-sample addition has option value."
    },
    {
      "archetype_ref": "f_midcap_us_session_gate",
      "distinct": true,
      "distinct_from_existing_ids": [
        "F001-F121 filter series"
      ],
      "distinctness_notes": "First joint session × marketcap × volume filter in 121 existing filters.",
      "expected_triggers_30d": 735,
      "triggers_estimate_method": "7000 total events × 0.35 (mid-cap) × 0.30 (US session) × 0.50 (quote_vol>=20M) ≈ 735",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Universal filter; pairs with all 5 exit families."
    },
    {
      "archetype_ref": "f_low_liq_funding_abs_only",
      "distinct": true,
      "distinct_from_existing_ids": [
        "F001-F121"
      ],
      "distinctness_notes": "Three-way liq × funding × listing-age filter not in registry.",
      "expected_triggers_30d": 160,
      "triggers_estimate_method": "7000 total × 0.33 (liq=low) × 0.10 (funding_abs_extreme) × 0.70 (listing>=90d) ≈ 160",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Low-liquidity universe — Devil's slippage flag is critical; recommend mandatory paper-shadow with realistic fills before any combo using this filter is promoted."
    },
    {
      "archetype_ref": "r_inverse_volatility_size",
      "distinct": true,
      "distinct_from_existing_ids": [
        "R001-R041 risk series"
      ],
      "distinctness_notes": "First risk archetype using move_pct + day_change_pct as hard gate (existing risk archetypes use sizing scalars).",
      "expected_triggers_30d": 4900,
      "triggers_estimate_method": "7000 total × 0.70 (passes move_pct<=3 OR |day_change|<=10 except R6) ≈ 4900",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "CRITICAL — Devil flag valid: move_pct<=3 EXCLUDES Reserved6 (8-15%/180s by definition) by construction. Synthesizer must either scope channel to OI_Price/pricechange OR relax to move_pct<=8/day_change<=20 before composing with R6 entries."
    },
    {
      "archetype_ref": "cc_oi_pc_synced_30s_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "CC001-CC062 cross_channel series"
      ],
      "distinctness_notes": "Existing cross_channels use sequential timing; synchronous (<30s) co-fire with taker-flow gate is structurally new at the parseable-fields level.",
      "expected_triggers_30d": 112,
      "triggers_estimate_method": "1400 OI_Price × 0.40 (oi>=10) × 0.50 (pump events) × 0.40 (taker>=0.55) ≈ 112; note synchronous-30s constraint not parseable, archetype matches single-channel conditions only",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Cross-channel timing in notes is descriptive; parser only enforces the 3 listed conditions. Synthesizer should be aware effective archetype is single-channel oi+pump+taker, not cross-confirmed."
    },
    {
      "archetype_ref": "cc_oi_then_r6_lowliq_short",
      "distinct": true,
      "distinct_from_existing_ids": [
        "CC001-CC062, R6 short series"
      ],
      "distinctness_notes": "Joint conditioning of OI threshold + low_liq + sentiment lean is novel for R6/short pipeline.",
      "expected_triggers_30d": 16,
      "triggers_estimate_method": "800 R6 × 0.25 (oi>=15) × 0.33 (liq=low) × 0.25 (global_long_high) ≈ 16",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Cross-channel sequencing not parser-enforced (same caveat as #17). Devil's tautology flag valid — verify OI→R6 gap >5s in historical alerts. Low-liq short slippage modeling mandatory before promotion."
    }
  ]
}
```

## 4. Risk (model=claude-opus-4-7, 193.6s)

```json
{
  "summary": "Round 4 batch clears the research-integrity bar — no concrete leakage (no forward_*/confirm_after_*/post_event_* fields), no secret access, no mass-symbol manipulation; primary risks are advisory: live-overlap on OI_Price/long entries vs the user's live BWE_OI_Price_monitor pump-long bot, percentile-flag staleness for top-decile / p25 / *_extreme regime tags if reference distributions are not strictly backward-rolling, and concentration on low-liq universe.",
  "risk_assessments": [
    {
      "archetype_ref": "x_funding_flip_oi_decay",
      "leakage_risk": "none",
      "leakage_notes": "funding_rate sign and oi_change_pct are real-time observables at T0; no forward fields.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Exit kernel applied to research combos only; the user's live BWE_OI_Price_monitor strategy carries its own exit, so no shared-state conflict at backtest layer.",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": ""
    },
    {
      "archetype_ref": "x_top_trader_reversal_exit",
      "leakage_risk": "low",
      "leakage_notes": "top_trader_position_ratio_dec is a regime tag; if '_dec' is a backward-rolling slope test it is fine. Verify SUPPORTED_FIELDS resolution does not use a centered or full-history reference window.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "",
      "concentration_risk": "none",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "Confirm in coverage_map_gen.py that top_trader_position_ratio_dec uses a backward-only slope window before scoring."
    },
    {
      "archetype_ref": "x_premium_collapse_be_lock",
      "leakage_risk": "none",
      "leakage_notes": "premium_bps is the real-time futures-spot spread; computable at T0.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": ""
    },
    {
      "archetype_ref": "x_basis_neutral_quick",
      "leakage_risk": "none",
      "leakage_notes": "basis_rate is observable at T0. Devil's scale-ambiguity concern is a parameterization/degeneracy issue, not a leakage issue.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": ""
    },
    {
      "archetype_ref": "x_volume_decay_trail_tighten",
      "leakage_risk": "low",
      "leakage_notes": "volume_pct_below_p25 is a percentile-rank flag. Backtest integrity depends on p25 being computed from a backward-rolling reference window (per-symbol or universe-level). If p25 is fit on the full sample including post-T0 bars, this is a hidden forward function.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "Verify volume_pct_below_p25 in coverage_map_gen.py uses a strictly backward rolling-window p25; if it uses a full-sample quantile this becomes a block."
    },
    {
      "archetype_ref": "x_taker_inversion_exit_long",
      "leakage_risk": "none",
      "leakage_notes": "taker_buy_ratio_5m is a backward-rolling 5min aggregate; observable at T0.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "",
      "concentration_risk": "none",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": ""
    },
    {
      "archetype_ref": "x_session_aware_widen_us",
      "leakage_risk": "none",
      "leakage_notes": "session and hour_utc are clock-derived; fully observable.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": ""
    },
    {
      "archetype_ref": "x_global_long_normalize_short",
      "leakage_risk": "none",
      "leakage_notes": "global_long_ratio is a Binance-published real-time metric. Devil's static-vs-transition concern is a semantic issue, not leakage.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": ""
    },
    {
      "archetype_ref": "e_neg_funding_oi_squeeze_long",
      "leakage_risk": "none",
      "leakage_notes": "OI, funding, premium all real-time. Sample-size and scale-interpretation concerns are statistical, not integrity-related.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "Same channel (OI_Price) and same side (long) as the user's live BWE_OI_Price_monitor pump-long strategy. With $1000 capital and 5–10% sizing, simultaneous fires on the same symbol could either double exposure or have one suppressed by the engine — both invalidate paper-vs-live equivalence.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Tag as live-overlap with BWE_OI_Price_monitor long; paper-shadow must model combined-exposure cap (one position per symbol across research + live) rather than treating the strategies as independent."
    },
    {
      "archetype_ref": "e_top_trader_contrarian_pump_short",
      "leakage_risk": "low",
      "leakage_notes": "volume_pct_top_decile and top_trader_position_ratio_high are percentile/regime flags. Same backward-window verification needed as x_volume_decay_trail_tighten.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Pricechange/short — different channel from live OI_Price/long; rare same-symbol overlap, manageable in paper-shadow.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "Confirm decile and high regime tags resolve via backward-rolling reference distributions only."
    },
    {
      "archetype_ref": "e_basis_extreme_premium_short",
      "leakage_risk": "none",
      "leakage_notes": "basis_rate, premium_extreme, oi_change_pct all observable at T0. premium_extreme regime tag should also be backward-rolling — verify alongside other *_extreme flags.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "low",
      "live_conflict_notes": "OI_Price/short opposes the live OI_Price/long bot on the same symbol; co-fires would offset rather than compound, but the offset itself is a real-portfolio behavior the backtest does not model.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Log co-trigger events vs live BWE_OI_Price_monitor long positions in paper-shadow to quantify offset frequency before promotion."
    },
    {
      "archetype_ref": "e_new_listing_funding_extreme_long",
      "leakage_risk": "none",
      "leakage_notes": "listing_age_days, funding, liquidity_bucket all observable at T0.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "New-listing universe (≤30d) is typically 5–15 symbols at any moment; cap concurrent positions from this archetype to 1 per symbol and ≤2 archetype-wide to prevent capital concentration on a single fresh token."
    },
    {
      "archetype_ref": "e_global_short_squeeze_volume_long",
      "leakage_risk": "low",
      "leakage_notes": "global_short_ratio_extreme and volume_pct_top_decile are regime/percentile flags. No direct forward fields, but flag construction must be backward-rolling.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "low",
      "live_conflict_notes": "R6/long does not directly oppose live OI_Price/long but competes for the same $1000 capital pool when both fire near each other.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Verify rolling-window construction of *_extreme / *_top_decile flags; enforce 1-position-per-symbol cap in synthesizer; paper-shadow must respect shared capital pool."
    },
    {
      "archetype_ref": "f_midcap_us_session_gate",
      "leakage_risk": "low",
      "leakage_notes": "marketcap_bucket, session, hour_utc are static or clock-based. quote_volume_24h must be the trailing 24h (not a centered or full-day-after window) — confirm in data loader.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "Confirm quote_volume_24h is computed from the trailing 24h ending at T0, not centered or forward-looking."
    },
    {
      "archetype_ref": "f_low_liq_funding_abs_only",
      "leakage_risk": "none",
      "leakage_notes": "liquidity_bucket and listing_age are static-ish; funding_abs_extreme is a regime tag (verify backward-rolling). No direct forward fields.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Filter biases the universe toward symbols where execution risk and adversarial front-running risk are highest; not a backtest-integrity issue but a real-fill-divergence concern.",
      "concentration_risk": "medium",
      "adversarial_risk": "medium",
      "overall_severity": "caution",
      "remediation": "Mandate paper-shadow with realistic slippage modeling (≥25% edge haircut) for any combo gated by this filter; reject promotion if shadow P&L < 50% of backtest P&L."
    },
    {
      "archetype_ref": "r_inverse_volatility_size",
      "leakage_risk": "none",
      "leakage_notes": "move_pct and day_change_pct are observable at T0.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "low",
      "live_conflict_notes": "By construction this gate eliminates Reserved6 (defined as 8–15% in 180s) and most pricechange-channel pump events; if the synthesizer composes this risk archetype with R6 entries the result is a structurally null combo. Not a sandbox-boundary issue, but it would silence legitimate live-trade-eligible events if shared with the live system.",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "caution",
      "remediation": "Scope to OI_Price/pricechange channels only, OR relax thresholds (move_pct<=8, day_change<=20) before composing with R6 entries — otherwise expect 0-trigger combos and silent backtest failure."
    },
    {
      "archetype_ref": "cc_oi_pc_synced_30s_long",
      "leakage_risk": "none",
      "leakage_notes": "oi_change_pct, event_type, taker_buy_ratio_5m all observable at T0. The descriptive 30s cross-channel sync is NOT parser-enforced — effective archetype is single-channel oi+pump+taker as flagged by Quant.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "high",
      "live_conflict_notes": "Direct same-channel same-side duplication of the user's live BWE_OI_Price_monitor pump-long strategy: same channel (OI_Price), same side (long), same trigger family (oi_change + pump). With $1000 capital and 5–10% sizing, simultaneous fires on the same symbol either double the intended exposure or cause one to be suppressed by the engine — both invalidate fill-equivalence between backtest and live, even though no backtest-integrity field is leaking.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Synthesizer must combine with an explicit 'no live overlap' filter (skip when live_strategy_active==1 on the symbol) before any combo from this archetype reaches paper-shadow; alternatively model combined-exposure scenarios explicitly in the shadow run."
    },
    {
      "archetype_ref": "cc_oi_then_r6_lowliq_short",
      "leakage_risk": "none",
      "leakage_notes": "oi_change_pct, liquidity_bucket, global_long_ratio_high all observable at T0. The 'OI_Price → R6 within 60s' sequencing is descriptive, not parser-enforced — no leakage.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "R6/short on a symbol where the live OI_Price/long bot may already be in position creates direct in-account hedging/offset within the same $1000 capital pool; not a backtest-integrity issue but a real-portfolio behavior the backtest does not model.",
      "concentration_risk": "medium",
      "adversarial_risk": "medium",
      "overall_severity": "caution",
      "remediation": "Same as cc_oi_pc_synced_30s_long — gate with 'no live opposite-side position on this symbol' filter; enforce strict cascade-slippage model (≥30% edge haircut) for low-liq shorts in paper-shadow before promotion."
    }
  ]
}
```

## 5. Synthesizer (model=claude-opus-4-7, 299.64s)

```json
{
  "summary": "Round 4 Synthesizer accepted 15 of 18 (83%) — heavy emphasis on the starved exit pipeline (X127-X133) plus 4 entries filling cross-channel and contrarian-sentiment gaps. Three revisions correct semantic defects: a static-state exit firing wrong-sided, an unsigned-funding new-listing entry, and a universal risk gate that would null-compose with R6 by construction. Zero rejections — Devil's possibly_fail flags are monitoring concerns, not logical defects, and let paper-shadow be the second filter per Round 3+ inclusive posture.",
  "accepted_archetypes": [
    {
      "id": "X127",
      "type": "exit",
      "archetype": "x_funding_flip_oi_decay",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "funding_rate<=0",
        "oi_change_pct<=-2"
      ],
      "expected_distinct": true,
      "notes": "Exit when funding flips against position AND OI starts decaying — orthogonal microstructure trigger before price reverses.",
      "synthesizer_note": "Devil flagged funding 8h cadence (slow flip rate) — accept anyway as paper-shadow signal; Quant ample (~2400), Risk acceptable. First exit kernel pairing funding sign-flip with OI decay."
    },
    {
      "id": "X128",
      "type": "exit",
      "archetype": "x_top_trader_reversal_exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "top_trader_position_ratio_dec"
      ],
      "expected_distinct": true,
      "notes": "Exit position when smart-money top-trader position ratio enters decline regime — leading indicator of impending reversal.",
      "synthesizer_note": "5min snapshot lag acceptable for >10min holds; Risk requires verification _dec resolves via backward-rolling slope only — flag in monitor not blocker."
    },
    {
      "id": "X129",
      "type": "exit",
      "archetype": "x_premium_collapse_be_lock",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "premium_bps<=5",
        "premium_bps>=-5"
      ],
      "expected_distinct": true,
      "notes": "Lock breakeven when premium_bps collapses to neutral band — premium decay signals exhaustion of the futures-spot spread driver.",
      "synthesizer_note": "Devil+Quant flag possible degeneracy (modal range for liquid perps); accept-with-watch — if >30% of fires are <30s post-entry, retune band to ±2 bps in R5."
    },
    {
      "id": "X130",
      "type": "exit",
      "archetype": "x_basis_neutral_quick",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "basis_rate>=-0.01",
        "basis_rate<=0.01"
      ],
      "expected_distinct": true,
      "notes": "Quick exit when basis_rate normalizes to ±1% band — basis convergence often precedes mean reversion in perp markets.",
      "synthesizer_note": "Scale ambiguity (decimal vs bps) must be resolved at data-loader before scoring; accept for paper-shadow with first-100-fires distribution dump as Devil suggested."
    },
    {
      "id": "X131",
      "type": "exit",
      "archetype": "x_volume_decay_trail_tighten",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "volume_pct_below_p25"
      ],
      "expected_distinct": true,
      "notes": "Tighten trailing stop when volume drops below p25 — momentum exhaustion signal that classical trail kernels ignore.",
      "synthesizer_note": "Cleanest of the exit batch — Devil seems_ok, Quant ample (~1250), Risk acceptable pending p25 backward-rolling verification."
    },
    {
      "id": "X132",
      "type": "exit",
      "archetype": "x_taker_inversion_exit_long",
      "channel": "*",
      "side": "long",
      "novel_dim": [
        "taker_buy_ratio_5m<=0.45"
      ],
      "expected_distinct": true,
      "notes": "Close long when 5m taker buy ratio inverts below 0.45 — aggressive sellers taking control of order flow.",
      "synthesizer_note": "Devil flags risk of early-exit on profitable pullbacks; pair with breakeven kernels (not trail) — paper-shadow must compare vs counterfactual fixed-TP hold."
    },
    {
      "id": "X133",
      "type": "exit",
      "archetype": "x_session_aware_widen_us",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "session=US",
        "hour_utc>=14"
      ],
      "expected_distinct": true,
      "notes": "Widen TP and tighten SL during US session — different volatility regime than Asian; static exits underperform across sessions.",
      "synthesizer_note": "session=US already binds the upper hour bound (canonically ≤21 UTC); engine-side TP/SL multipliers must actually deviate from baseline for this kernel to differentiate."
    },
    {
      "id": "E330",
      "type": "entry",
      "archetype": "e_neg_funding_oi_squeeze_long",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "oi_change_pct>=15",
        "funding<=-0.04",
        "premium_bps<=-15"
      ],
      "expected_distinct": true,
      "notes": "Long when OI surges with deeply negative funding AND discount premium — classic short-squeeze setup with three orthogonal confirmations.",
      "synthesizer_note": "Quant estimates ~18 triggers/30d (too_few) — accept-with-watch; Risk caution on live BWE_OI_Price_monitor pump-long overlap, paper-shadow must enforce one-position-per-symbol cap across research+live pools."
    },
    {
      "id": "E331",
      "type": "entry",
      "archetype": "e_top_trader_contrarian_pump_short",
      "channel": "pricechange",
      "side": "short",
      "novel_dim": [
        "top_trader_position_ratio_high",
        "event_type=pump",
        "volume_pct_top_decile"
      ],
      "expected_distinct": true,
      "notes": "Short pump events when top-trader ratio is already crowded long — fade smart-money exhaustion with volume confirmation.",
      "synthesizer_note": "Cleanest entry of the batch — Devil seems_ok, Quant tight (~62 triggers, adequate), Risk acceptable; 5min top_trader staleness is a known cross-batch caveat."
    },
    {
      "id": "E332",
      "type": "entry",
      "archetype": "e_basis_extreme_premium_short",
      "channel": "OI_Price",
      "side": "short",
      "novel_dim": [
        "basis_rate>=0.05",
        "premium_extreme",
        "oi_change_pct>=10"
      ],
      "expected_distinct": true,
      "notes": "Short when basis blows out >5% AND premium extreme AND OI surging — classic perp overheating, mean reversion setup.",
      "synthesizer_note": "Sample ~8 (too_few) and basis_rate scale ambiguity (5% vs 5bps) flagged; accept for option value — high-conviction overheating signature, retune threshold after first run if zero triggers."
    },
    {
      "id": "E333",
      "type": "entry",
      "archetype": "e_global_short_squeeze_volume_long",
      "channel": "Reserved6",
      "side": "long",
      "novel_dim": [
        "global_short_ratio_extreme",
        "volume_pct_top_decile",
        "event_type=crash"
      ],
      "expected_distinct": true,
      "notes": "Long Reserved6 crashes when global retail is extremely short AND volume is top-decile — squeeze fuel meets capitulation.",
      "synthesizer_note": "Sample ~6 (too_few) but R6/long is empirically alive (E316-E327 lift +0.343); accept for high-EV thin sample, enforce 1-position-per-symbol cap due to concentration risk."
    },
    {
      "id": "F122",
      "type": "filter",
      "archetype": "f_midcap_us_session_gate",
      "channel": "*",
      "side": "NA",
      "novel_dim": [
        "marketcap_bucket=mid",
        "session=US",
        "quote_volume_24h>=20000000"
      ],
      "expected_distinct": true,
      "notes": "Gate trades to mid-cap symbols during US session with healthy volume — best signal-to-noise band per session-cap analysis.",
      "synthesizer_note": "Clean accept — first joint session × marketcap × volume filter in 121 filters; Devil seems_ok, Quant ample (~735), Risk acceptable pending quote_volume_24h trailing-window verification."
    },
    {
      "id": "F123",
      "type": "filter",
      "archetype": "f_low_liq_funding_abs_only",
      "channel": "*",
      "side": "NA",
      "novel_dim": [
        "liquidity_bucket=low",
        "funding_abs_extreme",
        "listing_age_days>=90"
      ],
      "expected_distinct": true,
      "notes": "Only allow trades on low-liquidity symbols with funding extreme but excluding ultra-new listings — wild-but-not-untested universe.",
      "synthesizer_note": "Slippage divergence is the main concern (Devil+Risk both flag); MANDATE realistic-fill paper-shadow with ≥25% edge haircut before any combo using F123 is promoted to live."
    },
    {
      "id": "C063",
      "type": "cross_channel",
      "archetype": "cc_oi_pc_synced_30s_long",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "oi_change_pct>=10",
        "event_type=pump",
        "taker_buy_ratio_5m>=0.55"
      ],
      "expected_distinct": true,
      "notes": "Trigger long only when OI_Price pump AND pricechange pump fire within 30s of each other AND taker flow confirms — synchronous multi-channel agreement.",
      "synthesizer_note": "30s sync constraint is descriptive, not parser-enforced — effective archetype is single-channel oi+pump+taker; Risk flags HIGH live conflict with BWE_OI_Price_monitor pump-long bot, paper-shadow must model combined-exposure cap."
    },
    {
      "id": "C064",
      "type": "cross_channel",
      "archetype": "cc_oi_then_r6_lowliq_short",
      "channel": "Reserved6",
      "side": "short",
      "novel_dim": [
        "oi_change_pct>=15",
        "liquidity_bucket=low",
        "global_long_ratio_high"
      ],
      "expected_distinct": true,
      "notes": "Short Reserved6 events when OI_Price already flagged within 60s AND symbol is low-liquidity AND retail is leaning long — liquidation cascade setup.",
      "synthesizer_note": "Sample ~16 (too_few), tautology (OI→R6 may be same event) + low-liq slippage concerns; accept-with-watch — verify OI→R6 gap >5s in historical alerts, mandate ≥30% slippage haircut for shorts."
    }
  ],
  "revised_archetypes": [
    {
      "original_archetype_ref": "x_global_long_normalize_short",
      "revised_archetype": "x_global_short_flip_exit_short",
      "revision_reason": "Devil+Quant both flag wrong-sided semantics: original novel_dim 'global_long_ratio_high' encodes a static state, which means 'exit short while crowd is long' — that is the OPPOSITE of taking profit on squeeze relief (crowd-long is the squeeze fuel you want to hold the short for). Without a transition operator in the DSL, reframed to use global_short_ratio_high as the 'crowd has flipped' positive-exit signal.",
      "revised_novel_dim": [
        "global_short_ratio_high"
      ],
      "revised_notes": "Close short when global short ratio rises to high — crowd has flipped from long-extreme to short-leaning, indicating the squeeze played out and profit-taking is appropriate. Channel=*, side=short. Sentiment-flip exit, orthogonal to all 5 price/time exit kernels."
    },
    {
      "original_archetype_ref": "e_new_listing_funding_extreme_long",
      "revised_archetype": "e_new_listing_neg_funding_long",
      "revision_reason": "Devil flags that funding_abs_extreme is unsigned and could fire on highly POSITIVE funding (bearish for long) — original conditions are direction-blind for a directional long entry. Added explicit funding<=0 gate to enforce sign-awareness; conjunction now requires funding to be both extreme magnitude AND on the favorable side for longs.",
      "revised_novel_dim": [
        "listing_age_days<=30",
        "funding<=0",
        "funding_abs_extreme",
        "liquidity_bucket=mid"
      ],
      "revised_notes": "Long new listings (≤30d) when funding is negative AND at extreme magnitude AND liquidity is mid — early-stage volatility with absorbable size; sign-aware funding gate ensures the extreme is on the favorable side for longs. Channel=pricechange, side=long."
    },
    {
      "original_archetype_ref": "r_inverse_volatility_size",
      "revised_archetype": "r_chase_prevention_size",
      "revision_reason": "Devil+Quant+Risk all flag that move_pct<=3 EXCLUDES Reserved6 (defined as 8-15%/180s extreme moves) by construction; if synthesizer composes this risk archetype with any R6 entry the result is a structurally null combo (zero triggers). day_change_pct cap of ±10 also kills most pricechange-channel pump events on small caps. Thresholds relaxed so that R6 boundary moves and pricechange small-cap pumps can still compose with this gate while still capping out-of-bounds chases.",
      "revised_novel_dim": [
        "move_pct<=8",
        "day_change_pct<=20",
        "day_change_pct>=-20"
      ],
      "revised_notes": "Skip entries when symbol already moved >8% on the current bar OR >20% on the day — chase-prevention to protect against late-stage continuation traps; thresholds relaxed from R3 spec so R6 (8-15%/180s) and pricechange small-cap pumps can still compose. Channel=*, side=NA."
    }
  ],
  "rejected_archetypes": [],
  "next_round_focus": "Round 5 should pivot from individual archetype generation to entry × exit COMPOSITION — most R4 accepted units (X127-X133, E330-E333, F122-F123, C063-C064) are individually sound but unproven jointly. Propose 4-6 best-of-batch entry × exit candidate combos (e.g. E331 contrarian-pump-short × X132 taker-inversion-exit; E333 R6/long × X127 funding-flip-OI-decay) plus 2-3 transition-aware exit kernels now that x_global_long_normalize_short proved static-state exits can be silently wrong-sided."
}
```
