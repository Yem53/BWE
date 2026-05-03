# Debate transcript: debate_20260428_070823

- Trigger: `manual`
- Models: {'pattern_miner': 'claude-opus-4-7', 'generator': 'claude-opus-4-7', 'steelman': 'claude-opus-4-7', 'devil': 'claude-opus-4-7', 'quant': 'claude-opus-4-7', 'risk': 'claude-opus-4-7', 'metric_critic': 'claude-opus-4-7', 'synthesizer': 'claude-opus-4-7', 'self_reflection': 'claude-opus-4-7', 'behavior_annotator': 'claude-opus-4-7', 'cross_pair_recommender': 'claude-opus-4-7'}
- Existing archetypes: 652 total
- Results so far: {'total': 27797, 'by_status': {'discard': 27797}, 'best_score': None, 'n_keeps': 0}

## 1. Generator (model=claude-opus-4-7, 201.84s)

```json
{
  "summary": "27,797 results all discarded with 0 keepers and the X101+ exit pipeline is starved (R2 self-identified gap) — proposals weight EXIT archetypes (6) and propose entries with naturally symmetric or contrarian setups using ONLY supported fields, avoiding the asymmetric TP/SL trap from R1+R2.",
  "proposals": [
    {
      "archetype": "e_asia_global_short_extreme_squeeze_long",
      "type": "entry",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "session=Asian",
        "global_short_ratio_extreme",
        "liquidity_bucket=low"
      ],
      "notes": "Asian-session retail panic shorts in low-liquidity perps trigger squeezes within minutes — long fades the panic.",
      "rationale": "No existing entry combines session=Asian × global_short_ratio_extreme × liquidity_bucket=low; this 3-way intersection is uncovered.",
      "expected_distinct": true
    },
    {
      "archetype": "e_monday_oi_collapse_neg_premium_short",
      "type": "entry",
      "channel": "OI_Price",
      "side": "short",
      "novel_dim": [
        "weekday=Mon",
        "oi_change_pct<=-15",
        "premium_bps<=-20"
      ],
      "notes": "Monday OI collapse with deep negative premium signals continuation of weekend liquidation — shorts ride the unwind.",
      "rationale": "Weekday-gated OI-collapse continuation not in 85 OI_Price entries; adds calendar dimension to existing OI archetypes.",
      "expected_distinct": true
    },
    {
      "archetype": "e_top_trader_capitulation_neg_funding_long",
      "type": "entry",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "top_trader_position_ratio_low",
        "funding<=-0.0005",
        "premium_bps<=-15"
      ],
      "notes": "Smart money capitulated (low ratio) + funding deeply negative + cash discount — contrarian long at maximum bearish positioning.",
      "rationale": "Combines three orthogonal contrarian signals; existing top_trader archetypes don't gate on funding AND premium simultaneously.",
      "expected_distinct": true
    },
    {
      "archetype": "e_us_open_extreme_taker_buy_extended_short",
      "type": "entry",
      "channel": "pricechange",
      "side": "short",
      "novel_dim": [
        "hour_utc=14",
        "taker_buy_ratio_5m>=0.65",
        "day_change_pct>=15"
      ],
      "notes": "US-open frenzy with already-extended daily move and aggressive taker buying — fade the late longs piling in at the high.",
      "rationale": "hour_utc dimension absent from existing 267 entries; combines intraday-timing gate with exhaustion signal.",
      "expected_distinct": true
    },
    {
      "archetype": "e_new_listing_oi_extreme_short",
      "type": "entry",
      "channel": "OI_Price",
      "side": "short",
      "novel_dim": [
        "listing_age_days<=30",
        "oi_pct_top_decile",
        "premium_bps>=15"
      ],
      "notes": "New listing under 30 days with extreme OI pump and positive perp premium — crowded longs in immature liquidity get faded.",
      "rationale": "listing_age_days as gate is absent from existing entry archetypes; introduces asset-maturity dimension.",
      "expected_distinct": true
    },
    {
      "archetype": "e_midcap_premium_basis_divergence_long",
      "type": "entry",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "marketcap_bucket=mid",
        "premium_bps>=15",
        "basis_rate<=-0.001"
      ],
      "notes": "Mid-cap with positive perp premium but negative basis — perp/spot divergence playable arb-style long with natural exit when basis normalizes.",
      "rationale": "Cross-instrument premium↔basis divergence pair not represented; existing arb archetypes use only one of the two signals.",
      "expected_distinct": true
    },
    {
      "archetype": "e_global_long_overcrowded_funding_top_premium_short",
      "type": "entry",
      "channel": "pricechange",
      "side": "short",
      "novel_dim": [
        "global_long_ratio_extreme",
        "funding_pct_top_decile",
        "premium_extreme"
      ],
      "notes": "Triple-extreme stack of crowd sentiment + funding + premium — high-conviction short fade against maximally crowded longs.",
      "rationale": "Stacking 3 supported flag tokens for overcrowding is novel; existing archetypes use 1-2 of these flags at a time.",
      "expected_distinct": true
    },
    {
      "archetype": "e_european_session_oi_ratio_burst_lowliq_long",
      "type": "entry",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "session=European",
        "oi_ratio_pct>=20",
        "liquidity_bucket=low"
      ],
      "notes": "European-session OI ratio burst in low-liquidity pairs — early followers pile in ahead of US confirmation, riding the front-running flow.",
      "rationale": "session=European × oi_ratio_pct combination not present in 85 OI_Price entries; calendar+liquidity gate is novel.",
      "expected_distinct": true
    },
    {
      "archetype": "e_pre_us_open_taker_buy_oi_top_long",
      "type": "entry",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "hour_utc=13",
        "oi_pct_top_decile",
        "taker_buy_ratio_5m>=0.6"
      ],
      "notes": "Just-before-US-open hour with top-decile OI and aggressive taker buy — front-running the US session activity boost.",
      "rationale": "hour_utc=13 (pre-US-open) gate combined with OI+taker is uncovered; existing entries don't slice by 1-hour buckets.",
      "expected_distinct": true
    },
    {
      "archetype": "x_funding_flip_accelerated_trail",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "funding_rate>=0",
        "funding<=-0.0001"
      ],
      "notes": "Trail-style exit that tightens immediately when funding rate flips against the held position direction — funding-aware exit family.",
      "rationale": "No existing exit kernel uses funding-rate flip as a gate; bridges trail + funding signal into a new hybrid exit family — fills X101+ gap.",
      "expected_distinct": true
    },
    {
      "archetype": "x_premium_revert_to_neutral_exit",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "premium_bps<=0",
        "premium_bps>=0"
      ],
      "notes": "Exit when premium_bps reverts to neutral (crosses 0) — locks in the arb-driven move and avoids holding into stale premium.",
      "rationale": "Premium-mean-revert exit logic absent from 150 exit archetypes; uses supported premium_bps field as gate.",
      "expected_distinct": true
    },
    {
      "archetype": "x_top_trader_sentiment_flip_exit",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "top_trader_position_ratio_low",
        "top_trader_position_ratio_high"
      ],
      "notes": "Exit when top-trader position ratio flips against the held position — smart money has capitulated or loaded, signal exhausted.",
      "rationale": "Smart-money sentiment flip as exit gate is novel; existing 5 exit kernels (fixed/time_only/breakeven/trail/multi_tp) use price/time only.",
      "expected_distinct": true
    },
    {
      "archetype": "x_basis_normalize_take_profit",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "basis_rate>=-0.0005",
        "basis_rate<=0.0005"
      ],
      "notes": "Exit when basis_rate normalizes within ±5 bps of zero — basis-driven trade has played its hand.",
      "rationale": "Basis-rate normalization as exit trigger is uncovered in 150 exits; uses supported basis_rate field.",
      "expected_distinct": true
    },
    {
      "archetype": "x_oi_unwind_protective_long_exit",
      "type": "exit",
      "channel": "*",
      "side": "long",
      "novel_dim": [
        "oi_change_pct<=-5",
        "oi_change_pct<=-10"
      ],
      "notes": "For long positions: exit when post-entry OI drops 5% or more — leveraged longs are deleveraging, removing fuel for further upside.",
      "rationale": "OI-collapse-as-exit-gate is distinct from price/time-based exits; pairs with any kernel as a hybrid family.",
      "expected_distinct": true
    },
    {
      "archetype": "x_volume_decay_exhaustion_exit",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "volume_pct_below_p25"
      ],
      "notes": "Exit when post-entry volume drops below p25 of recent distribution — signal exhausted, no follow-through, scratch the trade.",
      "rationale": "Volume-decay-as-exit-gate uncovered; the 5 existing exit kernels are price+time only and don't read volume.",
      "expected_distinct": true
    },
    {
      "archetype": "f_overheated_state_block_entries",
      "type": "filter",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "funding_pct_top_decile",
        "premium_extreme",
        "funding_abs_extreme"
      ],
      "notes": "Block all entries when funding magnitude AND premium are both in extreme states — avoid entering at peak crowd-positioning.",
      "rationale": "Multi-flag overheated-state filter not present in 126 filter archetypes; uses supported flag tokens.",
      "expected_distinct": true
    },
    {
      "archetype": "f_marketcap_liquidity_minimum_quality",
      "type": "filter",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "marketcap_bucket=mid",
        "liquidity_bucket=high",
        "quote_volume_24h>=10000000"
      ],
      "notes": "Require mid+ marketcap or high liquidity or 10M+ daily quote volume — exclude manipulation-prone microcaps.",
      "rationale": "Quality-gate combining 3 supported categorical/numeric fields not present in current filter set.",
      "expected_distinct": true
    },
    {
      "archetype": "r_funding_abs_extreme_half_size",
      "type": "risk",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "funding_abs_extreme",
        "funding_abs_high"
      ],
      "notes": "Reduce position size to 50% when funding magnitude is extreme — tail risk of funding-driven liquidation cascade is materially higher.",
      "rationale": "Adaptive size scaling on funding magnitude is uncovered in 42 risk archetypes; introduces volatility-aware sizing.",
      "expected_distinct": true
    },
    {
      "archetype": "cc_oi_pricechange_consensus_120s_amplify",
      "type": "cross_channel",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.6",
        "oi_change_pct>=10"
      ],
      "notes": "When OI_Price and pricechange channels fire same-direction within 120s and taker-buy and OI both confirm — high-confidence amplified entry.",
      "rationale": "Cross-channel consensus amplification gated by supported micro-signals (taker+OI) not present in 67 cross_channel archetypes.",
      "expected_distinct": true
    },
    {
      "archetype": "cc_reserved6_then_pricechange_180s_fade_short",
      "type": "cross_channel",
      "channel": "Reserved6",
      "side": "short",
      "novel_dim": [
        "move_pct>=8",
        "premium_bps>=20"
      ],
      "notes": "Reserved6 (extreme move) followed by pricechange within 180s with premium spike — late longs piling in after the climax, fade short.",
      "rationale": "Sequential ordered-channel pattern (Reserved6→pricechange) gated by move+premium; existing cross_channel archetypes are within-window co-occurrence, not sequenced.",
      "expected_distinct": true
    }
  ]
}
```

## 2. Devil (model=claude-opus-4-7, 207.29s)

```json
{
  "summary": "Mostly clean batch with healthy push toward exit-side coverage, but three exit archetypes (x_premium_revert, x_top_trader_flip, x_funding_flip) have AND-coded novel_dim that can never co-fire as point-in-time conjunctions — same R1 silent-passthrough bug pattern; flag a few sample-size and momentum-fade concerns elsewhere.",
  "critiques": [
    {
      "archetype_ref": "e_asia_global_short_extreme_squeeze_long",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "Three-way intersection (session=Asian × global_short_ratio_extreme × liquidity_bucket=low) — report n_triggers per 30d; if <100, relax liquidity gate first."
    },
    {
      "archetype_ref": "e_monday_oi_collapse_neg_premium_short",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "Track distribution of fires within Monday — early-Monday continuation thesis weakens past the first ~4h after weekend reopen."
    },
    {
      "archetype_ref": "e_top_trader_capitulation_neg_funding_long",
      "verdict": "possibly_fail",
      "concerns": [
        "Triple-extreme stack (low top_trader_ratio AND funding<=-0.0005 AND premium_bps<=-15) likely collapses to <50 triggers per 30d — below useful sample size for the v2 mean/kelly metrics."
      ],
      "monitoring_advice": "Report n_triggers explicitly; if <100, relax to 2-of-3 extremes via OR."
    },
    {
      "archetype_ref": "e_us_open_extreme_taker_buy_extended_short",
      "verdict": "possibly_fail",
      "concerns": [
        "Shorting at hour_utc=14 with day_change_pct>=15 AND taker_buy_ratio_5m>=0.65 fades the historically strongest US-open continuation hour — left-tail risk of another 5–10% extension is the dominant failure mode here.",
        "Entry slippage will be material when taker_buy_ratio is that elevated (offer-side thinning) — 8–16bps round-trip assumption may understate cost on this archetype specifically."
      ],
      "monitoring_advice": "In paper-shadow track max-adverse-excursion within first 30 min and rerun under 16bps cost; if mean drops by >50%, edge is cost-driven."
    },
    {
      "archetype_ref": "e_new_listing_oi_extreme_short",
      "verdict": "possibly_fail",
      "concerns": [
        "New listings (<=30d) historically exhibit asymmetric upside continuation under top-decile OI prior to first major flush — shorting into new-listing pump has poor R:R; this is the same asymmetric TP/SL trap shape that bit E126.",
        "listing_age_days population in 30d BWE window is small — likely <40 triggers across all symbols."
      ],
      "monitoring_advice": "Bucket results by listing_age_days (0–7 / 8–14 / 15–30); if young bucket is the loser, gate higher; verify p25_capped_tail not just mean."
    },
    {
      "archetype_ref": "e_midcap_premium_basis_divergence_long",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "Confirm basis_rate unit (annualized vs periodic) matches the <=-0.001 threshold semantics — mis-scaled threshold would silently filter to ~empty set."
    },
    {
      "archetype_ref": "e_global_long_overcrowded_funding_top_premium_short",
      "verdict": "possibly_fail",
      "concerns": [
        "Three top-decile/extreme flags ANDed (global_long_ratio_extreme × funding_pct_top_decile × premium_extreme) will fire on a tiny joint tail — sample starvation (<30 triggers/30d) is likely."
      ],
      "monitoring_advice": "Report n_triggers; if too few, drop to any-2-of-3 OR-of-extremes form."
    },
    {
      "archetype_ref": "e_european_session_oi_ratio_burst_lowliq_long",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "Compare lift vs the *-session OI burst baseline — if European-session adds <0.05 lift, the calendar gate is dead weight."
    },
    {
      "archetype_ref": "e_pre_us_open_taker_buy_oi_top_long",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "Single-hour gate (hour_utc=13) cuts sample by ~24x; verify trigger count meets minimum before scoring as keep."
    },
    {
      "archetype_ref": "x_funding_flip_accelerated_trail",
      "verdict": "possibly_fail",
      "concerns": [
        "novel_dim mixes two distinct field tokens (funding_rate>=0 and funding<=-0.0001) — if these resolve to the same underlying funding field they are mutually contradictory as a point-in-time AND; if different fields the schema is not clear from notes and the loop may silently fall through (R1-class bug).",
        "Binance perp funding only updates every 8h — a 'funding-flip accelerated trail' lacks intra-hold granularity to act before standard TP/SL kernels fire."
      ],
      "monitoring_advice": "Synthesizer: clarify whether this is a state-transition (cross-zero event with prev/next snapshot) vs an AND-conjunction; reject if it would silently fall through SUPPORTED_FIELDS."
    },
    {
      "archetype_ref": "x_premium_revert_to_neutral_exit",
      "verdict": "likely_fail",
      "concerns": [
        "novel_dim [premium_bps<=0, premium_bps>=0] is only co-satisfiable at premium_bps==0 exactly — read as AND-conjunction (the standard novel_dim semantics) it will essentially never fire and silently degrade to the channel/side baseline, exactly the R1 silent-passthrough bug.",
        "Intended semantics ('cross-zero') requires a state-transition encoding the exit kernel framework must explicitly support; existing 5 kernels (fixed/time_only/breakeven/trail/multi_tp) do not."
      ],
      "monitoring_advice": "Synthesizer: rewrite as a band trigger (premium_bps in [-2,+2]) OR a verified cross event; otherwise exclude before scoring to avoid polluting results.tsv with a duplicate baseline."
    },
    {
      "archetype_ref": "x_top_trader_sentiment_flip_exit",
      "verdict": "likely_fail",
      "concerns": [
        "novel_dim stacks top_trader_position_ratio_low AND top_trader_position_ratio_high — these are mutually exclusive flag tokens at any single timestamp; AND-conjunction is unsatisfiable and will silently fall through to baseline (R1 bug pattern).",
        "'Flip' semantics requires comparing two consecutive snapshots; the present exit kernel framework does not appear to expose prev-state, so this archetype likely has no valid implementation path."
      ],
      "monitoring_advice": "Synthesizer: either rewrite as a state-transition primitive (prev_low AND curr_high) once the loop supports it, or exclude this archetype outright."
    },
    {
      "archetype_ref": "x_basis_normalize_take_profit",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "Band [-5bps,+5bps] is consistent — confirm basis_rate poll cadence matches the exit-kernel evaluation tick to avoid missed crossings."
    },
    {
      "archetype_ref": "x_oi_unwind_protective_long_exit",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "novel_dim [oi_change_pct<=-5, oi_change_pct<=-10] is redundant — effective threshold is -10; synthesizer should collapse to a single bound and clarify the OI delta window (post-entry vs trailing)."
    },
    {
      "archetype_ref": "x_volume_decay_exhaustion_exit",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "Define p25 reference window length explicitly (e.g., last 60 min vs trailing 24h) — without it the trigger is not reproducible."
    },
    {
      "archetype_ref": "f_overheated_state_block_entries",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "funding_pct_top_decile and funding_abs_extreme are highly correlated — ANDing both adds minimal marginal selectivity over either alone; report filter-on vs filter-off keep-rate to confirm the filter actually subtracts losers."
    },
    {
      "archetype_ref": "f_marketcap_liquidity_minimum_quality",
      "verdict": "possibly_fail",
      "concerns": [
        "Notes say 'mid+ marketcap OR high liquidity OR 10M+ quote_volume_24h' (OR), but novel_dim is a flat list typically interpreted as AND — encoding mismatch will produce a much stricter filter than described and silently discard usable signals."
      ],
      "monitoring_advice": "Synthesizer: explicitly state OR vs AND in the produced rule and default to OR to match the quality-floor intent; verify the loop's filter combinator semantics first."
    },
    {
      "archetype_ref": "r_funding_abs_extreme_half_size",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "funding_abs_extreme already implies funding_abs_high — listing both as AND is redundant; synthesizer should collapse to single flag, or build a tiered scaler (high=70%, extreme=50%) to actually use both bins."
    },
    {
      "archetype_ref": "cc_oi_pricechange_consensus_120s_amplify",
      "verdict": "possibly_fail",
      "concerns": [
        "Cross-channel consensus within 120s AND taker_buy_ratio_5m>=0.6 AND oi_change_pct>=10 is a compound AND likely to yield <50 triggers per 30d.",
        "Cross-channel join with directional consensus must be implemented as a real pairing; if the loop currently treats novel_dim as a per-event filter only, this archetype will silently fall through to baseline."
      ],
      "monitoring_advice": "Track raw n_pairs found before micro-signal filtering; if <50, drop one micro-signal gate, and verify cross-channel pairing is actually wired before scoring."
    },
    {
      "archetype_ref": "cc_reserved6_then_pricechange_180s_fade_short",
      "verdict": "possibly_fail",
      "concerns": [
        "Ordered-pair (Reserved6 → pricechange within 180s) requires sequence-aware cross-channel logic; if the framework only supports unordered co-occurrence, this archetype collapses to a duplicate of an existing within-window pair and silently falls through (R1 bug pattern)."
      ],
      "monitoring_advice": "Synthesizer: confirm whether ordering is honored; if not, either declare equivalence to an unordered cross-channel and exclude, or defer until ordered-join is added to the loop."
    }
  ]
}
```

## 3. Quant (model=claude-opus-4-7, 236.71s)

```json
{
  "summary": "All 20 proposals use only SUPPORTED_FIELDS so no parser-level fall-through — improvement over R1 — but 11/20 stack 3-way extremes that drive expected triggers below 30/30d, and three exits (x_premium_revert, x_top_trader_flip, x_funding_flip) encode 'flip/cross-zero' semantics as AND-conjunctions of mutually-incompatible gates which will silently reduce to channel/side baselines, exactly the R1 passthrough bug pattern.",
  "analyses": [
    {
      "archetype_ref": "e_asia_global_short_extreme_squeeze_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E333"
      ],
      "distinctness_notes": "First entry to gate session=Asian × global_short_ratio_extreme × liquidity_bucket=low simultaneously; E333 e_global_short_squeeze_volume_ uses volume not session/liquidity, so structurally distinct.",
      "expected_triggers_30d": 55,
      "triggers_estimate_method": "5000 pricechange events × ~1/3 (Asian session) × ~0.10 (global_short_ratio_extreme is p90 flag) × ~1/3 (liquidity_bucket=low) ≈ 55",
      "sample_size_verdict": "tight",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Squeeze fade thesis resolves fast; pairs best with fixed kernels X001-X005 (symmetric/aggressive) or X027 breakeven_at_1r; trail kernels (X017-X026) and time_only (X030+) are demonstrated R3 losers per by_exit_family stats."
    },
    {
      "archetype_ref": "e_monday_oi_collapse_neg_premium_short",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E334",
        "E332"
      ],
      "distinctness_notes": "Adds weekday calendar dimension to OI-collapse + neg-premium continuation; existing E334 (oi_collapse_volume_meanrev) and E332 (basis_extreme_premium) lack calendar gating.",
      "expected_triggers_30d": 3,
      "triggers_estimate_method": "1400 OI_Price events × 1/7 (Monday) × ~0.15 (oi_change_pct<=-15) × ~0.10 (premium_bps<=-20 deep cash discount) ≈ 3",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Continuation thesis pairs with fixed (X001-X005) or multi_tp_first_be_runner (X010); avoid pure trail given Monday-specific gap continuation profile."
    },
    {
      "archetype_ref": "e_top_trader_capitulation_neg_funding_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E330",
        "E331"
      ],
      "distinctness_notes": "Stacks three independent contrarian signals; E330 e_neg_funding_oi_squeeze_long uses funding+OI not top_trader+premium; E331 e_top_trader_contrarian_pump_s is short-side at pump, this is long-side at capitulation.",
      "expected_triggers_30d": 4,
      "triggers_estimate_method": "1400 OI_Price events × ~0.25 (top_trader_position_ratio_low p25 flag) × ~0.10 (funding<=-0.0005 deeply neg) × ~0.10 (premium_bps<=-15) ≈ 3.5",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Capitulation reversal needs runner-style exit; X010 multi_tp_first_be_runner or X027 be_at_1r_then_hold are best fits; avoid time_only X030+ (R3 demonstrated negative across the family)."
    },
    {
      "archetype_ref": "e_us_open_extreme_taker_buy_extended_short",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "hour_utc as numeric gate is absent from the 267 existing entries shown; novel intraday-timing dimension layered with exhaustion signal.",
      "expected_triggers_30d": 3,
      "triggers_estimate_method": "5000 pricechange events × 1/24 (hour_utc=14 ≈ 208) × ~0.15 (taker_buy_ratio_5m>=0.65 high tail) × ~0.05 (day_change_pct>=15 extended move) ≈ 1.5",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Short-fade at extension is high-variance; require fixed_tp1_sl1_symmetric (X001) or conservative tp1_sl2 (X004) — multi_tp ladders demonstrated negative in R3 by_exit_family."
    },
    {
      "archetype_ref": "e_new_listing_oi_extreme_short",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "listing_age_days as gate is novel — no existing entries in the 267 use asset-maturity dimension; structurally distinct.",
      "expected_triggers_30d": 2,
      "triggers_estimate_method": "1400 OI_Price events × ~0.10 (listing_age_days<=30 small population) × 0.10 (oi_pct_top_decile) × ~0.15 (premium_bps>=15) ≈ 2",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "New-listing pump shorting carries E126-class asymmetric tail risk; only fixed_tp1_sl1_symmetric (X001) or fixed_tp1_sl2_conservative (X004) are defensible; avoid multi_tp ladders."
    },
    {
      "archetype_ref": "e_midcap_premium_basis_divergence_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E332",
        "E335"
      ],
      "distinctness_notes": "Combines premium_bps>=15 with basis_rate<=-0.001 simultaneously — E332 e_basis_extreme_premium_short and E335 e_pc_neg_premium_neg_basis_arb each use only one of the two signals.",
      "expected_triggers_30d": 7,
      "triggers_estimate_method": "1400 OI_Price events × ~1/3 (marketcap_bucket=mid) × ~0.15 (premium_bps>=15) × ~0.10 (basis_rate<=-0.001 negative basis) ≈ 7",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Arb-style convergence; natural pair is x_basis_normalize_take_profit or x_premium_revert (if rewritten as band) — fixed kernels less optimal because exit signal is structural not price-based."
    },
    {
      "archetype_ref": "e_global_long_overcrowded_funding_top_premium_short",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E331"
      ],
      "distinctness_notes": "Triple-flag overcrowding stack (global_long_ratio_extreme × funding_pct_top_decile × premium_extreme); E331 top_trader_contrarian_pump uses different flag set.",
      "expected_triggers_30d": 15,
      "triggers_estimate_method": "5000 pricechange × ~0.10 × ~0.10 × ~0.10 = 5; adjusted +3x for inter-flag correlation (overheated regimes co-occur) ≈ 15",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Crowded-fade short; fixed kernels (X001-X005) only — multi_tp/trail/time_only all negative in R3 by_exit_family."
    },
    {
      "archetype_ref": "e_european_session_oi_ratio_burst_lowliq_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E337"
      ],
      "distinctness_notes": "session=European × oi_ratio_pct combination uncovered; E337 e_oi_taker_buy uses different micro-signal stack with no session gate.",
      "expected_triggers_30d": 23,
      "triggers_estimate_method": "1400 OI_Price events × ~1/3 (European session) × ~0.15 (oi_ratio_pct>=20) × ~1/3 (liquidity_bucket=low) ≈ 23",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Front-running flow pairs with fixed (X001-X005) or multi_tp_first_be_runner (X010); breakeven X027 protects against EU-session reversion."
    },
    {
      "archetype_ref": "e_pre_us_open_taker_buy_oi_top_long",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E337"
      ],
      "distinctness_notes": "hour_utc=13 single-hour gate is novel; E337 oi_taker_buy lacks intraday timing.",
      "expected_triggers_30d": 1,
      "triggers_estimate_method": "1400 OI_Price events × 1/24 (hour_utc=13 ≈ 58) × 0.10 (oi_pct_top_decile) × ~0.25 (taker_buy_ratio_5m>=0.6) ≈ 1.5",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Single-hour cut starves to ≈1; recommend Synthesizer widen to hour_utc IN [12,13] before scoring; otherwise no exit family will produce signal."
    },
    {
      "archetype_ref": "x_funding_flip_accelerated_trail",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "AND-conjunction (funding_rate>=0 AND funding<=-0.0001) is unsatisfiable since funding_rate and funding both map to the same Binance funding field per SUPPORTED_FIELDS — gate cannot fire and archetype silently degrades to channel/side baseline. R1-class semantic bug; needs state-transition primitive (prev/next snapshot) which the 5 existing exit kernels do not expose.",
      "expected_triggers_30d": 0,
      "triggers_estimate_method": "AND of mutually-incompatible numeric bounds on the same field ≈ 0 valid intersection",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Even if rewritten as a true funding-cross event, Binance funding only updates every 8h — granularity is below typical hold; recommend Synthesizer drop or restate as funding_abs_high entry-time gate paired with trail kernel."
    },
    {
      "archetype_ref": "x_premium_revert_to_neutral_exit",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "AND of premium_bps<=0 AND premium_bps>=0 only co-satisfies at premium_bps==0 exactly — gate effectively never fires and archetype reduces to baseline (R1 passthrough). Synthesizer must rewrite as a band trigger (e.g., premium_bps in [-2,+2]) or a cross-zero state event.",
      "expected_triggers_30d": 0,
      "triggers_estimate_method": "AND of contradictory bounds satisfies only at zero point measure ≈ 0 holds where exit fires",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "If rewritten as band [-2bps,+2bps] it pairs naturally with arb-style entries (e_midcap_premium_basis_divergence_long); otherwise exclude from scoring."
    },
    {
      "archetype_ref": "x_top_trader_sentiment_flip_exit",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "top_trader_position_ratio_low (≤p25) AND _high (≥p75) are mutually exclusive flag tokens at any single timestamp — AND-conjunction unsatisfiable, exact R1 silent-passthrough pattern. 'Flip' semantics requires prev-state comparison the framework does not expose.",
      "expected_triggers_30d": 0,
      "triggers_estimate_method": "AND of disjoint percentile-flag tokens ≈ 0 holds where gate fires",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Recommend Synthesizer exclude or defer until a state-transition primitive (prev_low AND curr_high) is added to the loop kernel."
    },
    {
      "archetype_ref": "x_basis_normalize_take_profit",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Band [-5bps,+5bps] is co-satisfiable and basis_rate is supported numeric; structurally novel — none of the 5 existing exit kernels (fixed/time_only/breakeven/trail/multi_tp) read basis.",
      "expected_triggers_30d": 350,
      "triggers_estimate_method": "basis_rate clusters near zero on majority of held positions; ≈70% of typical 60-min holds will see at least one tick within ±5bps band → ~70% of any held archetype's positions will hit; for paired entries (~500 holds/30d) ≈ 350 fires",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Best paired with arb-style entries (e_midcap_premium_basis_divergence_long, E335 pc_neg_premium_neg_basis_arb); confirm basis_rate poll cadence matches exit-tick interval before scoring."
    },
    {
      "archetype_ref": "x_oi_unwind_protective_long_exit",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "OI-collapse as exit gate is structurally distinct from the 5 price/time-only kernels; redundant double-bound (<=-5 AND <=-10) collapses to effective threshold -10 — Synthesizer should remove the weaker bound.",
      "expected_triggers_30d": 80,
      "triggers_estimate_method": "For long holds (~500/30d typical), oi_change_pct<=-10 within hold window fires on ~15% of holds (high-leverage deleveraging events) ≈ 75",
      "sample_size_verdict": "tight",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Long-side only; clarify with Synthesizer whether OI delta is post-entry or trailing window — current spec ambiguous, affects trigger interpretation materially."
    },
    {
      "archetype_ref": "x_volume_decay_exhaustion_exit",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Single-flag volume_pct_below_p25 — structurally distinct from price/time-only existing kernels; uses supported flag token.",
      "expected_triggers_30d": 600,
      "triggers_estimate_method": "volume_pct_below_p25 fires on ~25% of bars by definition; for ~500 typical holds × ~5 bars examined ≈ 600 fires",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Reference window length for p25 must be specified (60min vs 24h trailing) — without explicit window, results are not reproducible; flag for Synthesizer to pin down."
    },
    {
      "archetype_ref": "f_overheated_state_block_entries",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Multi-flag AND of funding_pct_top_decile × premium_extreme × funding_abs_extreme is novel filter shape; supported flag tokens.",
      "expected_triggers_30d": 50,
      "triggers_estimate_method": "7200 total events (5000+1400+800) × ~0.10 × ~0.10 × ~0.10 = 7; adjusted +7x for inter-flag correlation (overheated regimes cluster) ≈ 50",
      "sample_size_verdict": "tight",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "funding_pct_top_decile and funding_abs_extreme are highly correlated (≥80%); ANDing both adds minimal selectivity over either alone — Synthesizer should drop one and replace with an orthogonal signal."
    },
    {
      "archetype_ref": "f_marketcap_liquidity_minimum_quality",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Quality-floor filter combining marketcap_bucket × liquidity_bucket × quote_volume_24h is structurally novel; all fields supported.",
      "expected_triggers_30d": 2400,
      "triggers_estimate_method": "AND interpretation: 7200 × ~1/3 (mid mcap) × ~1/3 (high liq) × ~0.5 (qv24h>=10M) ≈ 400 PASS, blocks 6800; OR interpretation per notes: ≈ 4800 PASS, blocks 2400",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "CRITICAL: notes describe OR semantics ('mid+ marketcap OR high liquidity OR 10M+ volume') but novel_dim list is parsed as AND in current loop — encoding mismatch will produce a much stricter filter than intended; Synthesizer must either explicitly OR-encode or accept that intended quality-floor becomes a strict triple-quality gate."
    },
    {
      "archetype_ref": "r_funding_abs_extreme_half_size",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Adaptive sizing on funding magnitude is novel; both flag tokens supported. funding_abs_extreme (≥p90) implies funding_abs_high (≥p75) so AND is redundantly equal to extreme.",
      "expected_triggers_30d": 720,
      "triggers_estimate_method": "7200 total events × ~0.10 (funding_abs_extreme p90 flag, redundant with _high) ≈ 720",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Synthesizer should either collapse to single flag funding_abs_extreme, or refactor as a tiered scaler (high→70%, extreme→50%) to actually use both bins."
    },
    {
      "archetype_ref": "cc_oi_pricechange_consensus_120s_amplify",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Cross-channel consensus gated on supported micro-signals (taker_buy_ratio_5m + oi_change_pct) is structurally novel; both fields supported.",
      "expected_triggers_30d": 18,
      "triggers_estimate_method": "~1400 OI events × p(any pricechange within ±120s) ≈ 1400 × 0.10 ≈ 140 raw pairs; × ~0.25 (taker>=0.6) × ~0.50 (oi>=10) ≈ 18",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Cross-channel pairing within 120s is NOT a per-event filter — must verify the loop has an active cross_channel pairing implementation; if novel_dim is treated as a per-event filter only, this archetype will silently fall through to baseline (R1 pattern). Synthesizer: confirm cc plumbing before scoring."
    },
    {
      "archetype_ref": "cc_reserved6_then_pricechange_180s_fade_short",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Ordered (Reserved6 → pricechange) sequence pairing is structurally distinct from any unordered cross-channel co-occurrence in the 67 existing cc archetypes; supported numeric fields (move_pct, premium_bps).",
      "expected_triggers_30d": 24,
      "triggers_estimate_method": "800 Reserved6 × p(pricechange within next 180s | Reserved6 fired) ≈ 800 × 0.30 ≈ 240 sequenced pairs; × ~0.40 (move_pct>=8) × ~0.25 (premium_bps>=20) ≈ 24",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Ordered-pair semantics requires sequence-aware cross_channel logic; if the framework only supports unordered co-occurrence this archetype collapses to a duplicate of an existing within-window pair (R1 silent-passthrough pattern). Pair short-fade with fixed (X001-X005) only — trail/time_only demonstrated negative in R3."
    }
  ]
}
```

## 4. Risk (model=claude-opus-4-7, 147.89s)

```json
{
  "summary": "No true integrity blockers — all 21 proposals reference T0-computable supported fields with no forward/post-T0 snooping, no credential access, and no mass-symbol manipulation; main caution items are live-overlap (5 OI_Price/long entries share channel+side with the user's live BWE_OI_Price_monitor pump long), symbol concentration on the new-listing short, and size-amplification on the cross-channel consensus rule.",
  "risk_assessments": [
    {
      "archetype_ref": "e_asia_global_short_extreme_squeeze_long",
      "leakage_risk": "none",
      "leakage_notes": "session, global_short_ratio_extreme percentile flag, and liquidity_bucket are all observable at T0; ensure global_short_ratio percentile uses trailing-window distribution not full-sample.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Different channel (pricechange) from the live OI_Price/long bot; no same-symbol same-direction conflict expected.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "n/a"
    },
    {
      "archetype_ref": "e_monday_oi_collapse_neg_premium_short",
      "leakage_risk": "none",
      "leakage_notes": "weekday, oi_change_pct, premium_bps all available at T0.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Same channel (OI_Price) as live bot but opposite side (short vs long); could create simultaneous opposite positions on the same symbol if Monday OI collapse and a pump-long signal both fire — net flat exposure, but doubles round-trip cost.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "n/a"
    },
    {
      "archetype_ref": "e_top_trader_capitulation_neg_funding_long",
      "leakage_risk": "none",
      "leakage_notes": "All three fields observable at T0; verify top_trader_position_ratio_low percentile uses trailing-window not whole-sample.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "Same channel AND same side as live BWE_OI_Price_monitor pump long bot — concurrent fires would double position size on the same symbol/direction, exceeding the 5–10% per-trade sizing target.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Add a runtime de-dup gate against the live OI_Price/long bot's open positions before sizing this archetype's signal in paper-shadow."
    },
    {
      "archetype_ref": "e_us_open_extreme_taker_buy_extended_short",
      "leakage_risk": "none",
      "leakage_notes": "hour_utc, taker_buy_ratio_5m, day_change_pct all T0-observable.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Different channel and opposite side from live bot.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "n/a"
    },
    {
      "archetype_ref": "e_new_listing_oi_extreme_short",
      "leakage_risk": "low",
      "leakage_notes": "listing_age_days uses listing timestamp (T0-safe). Confirm oi_pct_top_decile percentile is computed on the new-listing's own short history, not a forward-looking distribution.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Same channel (OI_Price), opposite side from live; minor.",
      "concentration_risk": "high",
      "adversarial_risk": "medium",
      "overall_severity": "caution",
      "remediation": "Cap to ≤2 concurrent new-listing positions and ≤25% of capital across the listing_age_days≤30 universe; report symbol distribution — if 1–2 tickers drive >50% of triggers, gate stricter."
    },
    {
      "archetype_ref": "e_midcap_premium_basis_divergence_long",
      "leakage_risk": "none",
      "leakage_notes": "marketcap_bucket, premium_bps, basis_rate observable at T0; verify basis_rate poll matches T0 timestamp (not next-poll value).",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "Same channel AND same side as live OI_Price/long bot — same de-dup concern as the capitulation_long archetype.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Same de-dup gate against the live bot's open positions in paper-shadow."
    },
    {
      "archetype_ref": "e_global_long_overcrowded_funding_top_premium_short",
      "leakage_risk": "low",
      "leakage_notes": "All three percentile flags T0-computable; verify _top_decile / _extreme are derived from trailing distributions to prevent in-sample percentile leakage.",
      "multitest_inflation_risk": "medium",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Different channel and opposite side from live bot.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "n/a"
    },
    {
      "archetype_ref": "e_european_session_oi_ratio_burst_lowliq_long",
      "leakage_risk": "none",
      "leakage_notes": "session, oi_ratio_pct, liquidity_bucket are all T0-observable.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "Same channel + same side as live OI_Price/long bot — concurrent-position risk.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Add live-bot de-dup gate; cap to ≤1 concurrent position per symbol when liquidity_bucket=low to avoid micro-structural single-point exposure."
    },
    {
      "archetype_ref": "e_pre_us_open_taker_buy_oi_top_long",
      "leakage_risk": "none",
      "leakage_notes": "hour_utc, oi_pct_top_decile, taker_buy_ratio_5m all T0-observable.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "Same channel + same side as live OI_Price/long bot — concurrent-position risk.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Add live-bot de-dup gate before sizing in paper-shadow."
    },
    {
      "archetype_ref": "x_funding_flip_accelerated_trail",
      "leakage_risk": "none",
      "leakage_notes": "Exit-side; reads funding state at decision tick. No forward/post-exit fields. Quant's unsatisfiable-AND concern is a structural/encoding issue, not a research-integrity (leakage) issue.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit kernel, paired with paper trades only.",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "n/a (encoding fix is Synthesizer's job, not a risk-integrity block)."
    },
    {
      "archetype_ref": "x_premium_revert_to_neutral_exit",
      "leakage_risk": "none",
      "leakage_notes": "Exit reads current premium_bps; no forward field.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit kernel only.",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "n/a"
    },
    {
      "archetype_ref": "x_top_trader_sentiment_flip_exit",
      "leakage_risk": "none",
      "leakage_notes": "Exit kernel; reads percentile flag at decision tick. No future-function field.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit kernel only.",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "n/a"
    },
    {
      "archetype_ref": "x_basis_normalize_take_profit",
      "leakage_risk": "none",
      "leakage_notes": "basis_rate observable at T0; band trigger is a current-state read.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit kernel only.",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "n/a"
    },
    {
      "archetype_ref": "x_oi_unwind_protective_long_exit",
      "leakage_risk": "low",
      "leakage_notes": "Notes say 'post-entry OI drops 5% or more' — this is T0-safe ONLY if oi_change_pct is measured from entry-time to current decision-tick (rolling). If the loop interprets oi_change_pct as a forward-window delta (e.g. 'next 30min OI drop'), that's post-exit-decision data and would leak. Synthesizer must pin window semantics.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit kernel only.",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "n/a from risk standpoint, but Synthesizer should explicitly anchor oi_change_pct to (entry_time → current_tick), not any forward window."
    },
    {
      "archetype_ref": "x_volume_decay_exhaustion_exit",
      "leakage_risk": "low",
      "leakage_notes": "volume_pct_below_p25 must reference a TRAILING distribution (e.g. last 60min before decision tick) and not a full-sample p25 — the latter would be an in-sample percentile leak. Same concern applies to all volume_pct_* flag derivations.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit kernel only.",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "n/a from risk standpoint; Synthesizer pin the p25 reference window to a trailing causal interval."
    },
    {
      "archetype_ref": "f_overheated_state_block_entries",
      "leakage_risk": "low",
      "leakage_notes": "Filter only blocks entries — even if the percentile flags were over-fitted, the failure mode is over-blocking (conservative), not generating false alpha. Still, _top_decile / _extreme flags must be trailing-distribution to be honest.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Filter only.",
      "concentration_risk": "none",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "n/a"
    },
    {
      "archetype_ref": "f_marketcap_liquidity_minimum_quality",
      "leakage_risk": "low",
      "leakage_notes": "marketcap_bucket / liquidity_bucket assignment must be point-in-time (snapshot at T0), not the latest known assignment — using current bucket retrospectively would inject mild survivorship bias.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Filter only.",
      "concentration_risk": "none",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "n/a"
    },
    {
      "archetype_ref": "r_funding_abs_extreme_half_size",
      "leakage_risk": "low",
      "leakage_notes": "funding_abs_extreme percentile flag must derive from a trailing distribution at T0.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Risk-side scaler; if applied to live bot orders later, halving size during extreme funding regimes is conservative — beneficial, not conflicting.",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "n/a"
    },
    {
      "archetype_ref": "cc_oi_pricechange_consensus_120s_amplify",
      "leakage_risk": "none",
      "leakage_notes": "120s consensus window uses two past events at decision tick — T0-safe. taker_buy_ratio_5m and oi_change_pct are both T0-observable.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "high",
      "live_conflict_notes": "'Amplified' size on cross-channel consensus, when one of the two events is the same OI_Price/long signal the live bot is also acting on, would double-load the position — and the 'amplify' verb in the name suggests >1.0x sizing. At 5–10% baseline × amplifier × concurrent live entry, effective per-symbol exposure could easily breach 20%.",
      "concentration_risk": "high",
      "adversarial_risk": "medium",
      "overall_severity": "caution",
      "remediation": "Cap the amplify multiplier to ≤1.0x in paper-shadow until effective per-symbol exposure is measured against live-bot positions; explicitly de-dup against live OI_Price/long fires before applying any amplification."
    },
    {
      "archetype_ref": "cc_reserved6_then_pricechange_180s_fade_short",
      "leakage_risk": "none",
      "leakage_notes": "Ordered Reserved6→pricechange within 180s uses two past events at decision tick — T0-safe. move_pct and premium_bps T0-observable.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Different channel anchor (Reserved6) and short side; opposite side of live OI_Price/long means rare same-symbol opposite-direction collisions but no double-loading.",
      "concentration_risk": "medium",
      "adversarial_risk": "medium",
      "overall_severity": "caution",
      "remediation": "Cap to ≤1 concurrent position per symbol; track Reserved6 source-symbol distribution — if a small set of tickers dominates triggers, the strategy is symbol-fragile."
    }
  ]
}
```

## 5. Synthesizer (model=?, 300.03869795799255s)

**ERROR**: `timeout`

```json
{}
```
