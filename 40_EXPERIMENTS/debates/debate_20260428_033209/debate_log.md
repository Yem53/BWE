# Debate transcript: debate_20260428_033209

- Trigger: `manual`
- Models: {'pattern_miner': 'claude-opus-4-7', 'generator': 'claude-opus-4-7', 'steelman': 'claude-opus-4-7', 'devil': 'claude-opus-4-7', 'quant': 'claude-opus-4-7', 'risk': 'claude-opus-4-7', 'metric_critic': 'claude-opus-4-7', 'synthesizer': 'claude-opus-4-7', 'self_reflection': 'claude-opus-4-7', 'behavior_annotator': 'claude-opus-4-7', 'cross_pair_recommender': 'claude-opus-4-7'}
- Existing archetypes: 618 total
- Results so far: {'total': 25640, 'by_status': {'discard': 25640}, 'best_score': None, 'n_keeps': 0}

## 1. Generator (model=claude-opus-4-7, 135.35s)

```json
{
  "summary": "Round 4 lessons combine two gaps: exit-side pipeline is starved (only fixed family has positive trades; trail/multi_tp/breakeven/time_only all -ve median) and existing entries lean toward asymmetric TP/SL traps; this batch proposes 8 exit archetypes leveraging supported real-time signals as decay/flip watchdogs, plus naturally-symmetric mean-reversion entries and conflict/confirm cross-channel logic.",
  "proposals": [
    {
      "archetype": "x_exit_on_top_trader_position_dec",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "top_trader_position_ratio_dec"
      ],
      "notes": "Exit when smart-money top-trader position ratio drops post-entry — they are unwinding before retail catches the reversal.",
      "rationale": "None of the 133 existing exits use top_trader_position_ratio_dec as the trigger condition; this is a smart-money-exit family distinct from fixed/trail/multi_tp/breakeven/time_only kernels.",
      "expected_distinct": true
    },
    {
      "archetype": "x_exit_funding_normalize_meanrev",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "funding_abs_high"
      ],
      "notes": "Exit when funding rate has crossed back into normal band from extreme — extreme-funding alpha is gone.",
      "rationale": "Existing exits are PnL-shape-based (TP/SL/trail). This exits on a fundamentals state change (funding mean-reversion) regardless of PnL position.",
      "expected_distinct": true
    },
    {
      "archetype": "x_exit_global_long_ratio_collapse",
      "type": "exit",
      "channel": "*",
      "side": "long",
      "novel_dim": [
        "global_long_ratio_high"
      ],
      "notes": "For long entries — exit when global_long_ratio decays out of the high band, signaling crowd flip.",
      "rationale": "Sentiment-flip exit using global_long_ratio_high as the regime gate; not present in current 133 exits which are all price/time based.",
      "expected_distinct": true
    },
    {
      "archetype": "x_exit_premium_decay_watchdog",
      "type": "exit",
      "channel": "*",
      "side": "long",
      "novel_dim": [
        "premium_extreme"
      ],
      "notes": "Long exit watchdog — close when premium falls out of the extreme band, removing the premium-squeeze rationale.",
      "rationale": "Premium-state-change exit kernel; orthogonal to TP/SL/trail families. Targets the case where price holds but the perp-spot dislocation closes.",
      "expected_distinct": true
    },
    {
      "archetype": "x_exit_session_boundary_close",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "session=US"
      ],
      "notes": "Force-close any open position at session boundary (e.g. exit before US session opens to avoid macro shock).",
      "rationale": "Session-aware exit; existing time_only family uses absolute durations, not calendar session boundaries. Distinct kernel.",
      "expected_distinct": true
    },
    {
      "archetype": "x_hybrid_time_then_premium_watchdog",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "premium_extreme"
      ],
      "notes": "Hold for fixed time window unless premium crosses into the opposite extreme — then early exit; combines time + state-change.",
      "rationale": "Hybrid composition: time_only baseline overlaid with premium watchdog. None of the 5 existing exit kernels mix time-stop with a premium-state failsafe.",
      "expected_distinct": true
    },
    {
      "archetype": "x_hybrid_breakeven_then_funding_flip",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "funding_pct_top_decile"
      ],
      "notes": "Breakeven once unrealized hits TP/2, then add a funding-flip rip-cord — exits if the funding regime inverts.",
      "rationale": "Composition of breakeven + funding-flip exit; current breakeven kernel only ladders on price, not on funding regime change.",
      "expected_distinct": true
    },
    {
      "archetype": "x_exit_volume_exhaustion",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "volume_pct_below_p25"
      ],
      "notes": "Exit once realized volume in the post-entry window drops into the bottom quartile — momentum has died.",
      "rationale": "Volume-state-driven exit; current exit families don't gate on a post-entry volume bucket flip into below_p25.",
      "expected_distinct": true
    },
    {
      "archetype": "e_oi_collapse_volume_meanrev_short",
      "type": "entry",
      "channel": "OI_Price",
      "side": "short",
      "novel_dim": [
        "oi_change_pct<=-15",
        "volume_pct_top_decile",
        "liquidity_bucket=high"
      ],
      "notes": "Short when OI collapses sharply with high volume on a liquid pair — leveraged longs being flushed, expect mean reversion.",
      "rationale": "Negative oi_change_pct threshold (collapse) is rarely used in existing 257 entries which mostly use positive thresholds; combined with high-decile volume creates a distinct setup with naturally symmetric TP/SL profile.",
      "expected_distinct": true
    },
    {
      "archetype": "e_pc_neg_premium_neg_basis_arb_long",
      "type": "entry",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "premium_bps<=-20",
        "basis<=-0.3",
        "liquidity_bucket=high"
      ],
      "notes": "Long when both premium and basis are deeply negative — perp under-priced relative to spot, structural arbitrage support.",
      "rationale": "Combines two negative-side numeric thresholds (premium_bps + basis) with liquidity gate; this two-leg negative-dislocation entry is not in the current set which mostly hunts positive premium/funding extremes.",
      "expected_distinct": true
    },
    {
      "archetype": "e_r6_us_session_largecap_only_short",
      "type": "entry",
      "channel": "Reserved6",
      "side": "short",
      "novel_dim": [
        "session=US",
        "marketcap_bucket=large",
        "hour_utc>=14",
        "hour_utc<=20"
      ],
      "notes": "R6 extreme-move short, restricted to US session and large-cap only — best execution venue, lowest slippage tail.",
      "rationale": "R6 channel currently has 50 entry archetypes but the registry preview shows them duplicating identical scores; adding session+marketcap dual-gate yields a structurally distinct subset that the parser can actually differentiate.",
      "expected_distinct": true
    },
    {
      "archetype": "e_oi_taker_buy_with_short_squeeze_long",
      "type": "entry",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.65",
        "global_short_ratio_extreme",
        "funding<=0"
      ],
      "notes": "Long on OI_Price when aggressive buying meets crowded shorts AND funding is non-positive — squeeze fuel without paying funding tax.",
      "rationale": "Triple-orthogonal-confirmation entry combining flow (taker_buy), crowd (global_short_ratio_extreme), and cost (funding<=0); this specific 3-way combination is absent from the current OI_Price/long roster.",
      "expected_distinct": true
    },
    {
      "archetype": "e_pc_pump_smart_money_neutral_short",
      "type": "entry",
      "channel": "pricechange",
      "side": "short",
      "novel_dim": [
        "event_type=pump",
        "top_trader_position_ratio_dec",
        "premium_bps>=20"
      ],
      "notes": "Pump event short — fade when top traders are decreasing position AND premium is hot; retail-driven exhaustion setup.",
      "rationale": "Smart-money-fade entry using top_trader_position_ratio_dec as a confirmation signal; existing fade entries don't condition on top-trader direction this way.",
      "expected_distinct": true
    },
    {
      "archetype": "f_weekday_only_skip_weekend",
      "type": "filter",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "weekday=Mon"
      ],
      "notes": "Skip weekend windows (low liquidity, unreliable funding, wider spreads); active weekdays only.",
      "rationale": "Calendar-based liquidity filter; no current filter archetype gates on weekday categorical alone for global skip.",
      "expected_distinct": true
    },
    {
      "archetype": "r_low_liquidity_size_dampener",
      "type": "risk",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "liquidity_bucket=low"
      ],
      "notes": "Risk archetype that down-sizes by 50% on low-liquidity bucket trades to keep slippage tail bounded under compound replay.",
      "rationale": "Risk family currently has 41 archetypes; an explicit liquidity-bucket dampener tied to slippage realism is the kind of metric-conscious sizing rule the new mean/Kelly metrics will reward.",
      "expected_distinct": true
    },
    {
      "archetype": "f_stretched_market_funding_and_premium",
      "type": "filter",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "funding_abs_high",
        "premium_extreme"
      ],
      "notes": "Skip entries when BOTH funding-abs and premium are in their extreme bands — over-stretched market, mean-reversion risk to existing positions.",
      "rationale": "Two-flag composite filter; current filter set tends to use single flags, so the AND-composite over funding_abs_high + premium_extreme is structurally distinct.",
      "expected_distinct": true
    },
    {
      "archetype": "cc_conflict_oi_pc_opposite_side_skip",
      "type": "cross_channel",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "session=US"
      ],
      "notes": "Cross-channel veto — when OI_Price and pricechange fire on the same symbol with opposite sides within 90s, skip both (signal is ambiguous).",
      "rationale": "Conflict-resolution cross-channel rule; existing cross-channel archetypes mostly compose confirmations, not conflicts.",
      "expected_distinct": true
    },
    {
      "archetype": "cc_confirm_pc_r6_same_dir_size_boost",
      "type": "cross_channel",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "session=US",
        "liquidity_bucket=high"
      ],
      "notes": "When pricechange and Reserved6 fire same direction within 120s on a high-liquidity name, size-boost x1.5; double-channel confirmation = high-quality.",
      "rationale": "Confirmation-boost cross-channel that gates on liquidity for execution quality; existing 64 cross-channel rows don't combine pc+R6 timing window with liquidity gating.",
      "expected_distinct": true
    },
    {
      "archetype": "f_listing_age_minimum_180d",
      "type": "filter",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "listing_age_days>=180"
      ],
      "notes": "Filter out symbols listed under 180 days — avoid new-listing volatility regime where historical kline patterns are unreliable.",
      "rationale": "Age-based filter; current filter set uses marketcap/liquidity buckets but no explicit listing_age_days gate.",
      "expected_distinct": true
    },
    {
      "archetype": "x_exit_basis_invert",
      "type": "exit",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "basis<=0"
      ],
      "notes": "Exit when basis crosses through zero (positive→negative or vice versa); structural regime flip indicates the carry rationale is gone.",
      "rationale": "Basis-inversion exit; current exit kernels don't use basis sign change as the trigger.",
      "expected_distinct": true
    }
  ]
}
```

## 2. Devil (model=claude-opus-4-7, 116.13s)

```json
{
  "summary": "Generator batch is mostly sound with strong exit-side coverage and naturally-symmetric mean-reversion entries; main concerns are a few novel_dim/notes mismatches, sample-size starvation on triple-AND entries, and one filter with contradictory weekday spec.",
  "critiques": [
    {
      "archetype_ref": "x_exit_on_top_trader_position_dec",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "During paper-shadow, log how often top_trader_position_ratio_dec flips post-entry — if <5% trigger rate, the exit is effectively dormant."
    },
    {
      "archetype_ref": "x_exit_funding_normalize_meanrev",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "Funding updates are 8h-cadenced on Binance — verify the exit polling resolution is fine enough that normalize crossings aren't missed mid-bucket."
    },
    {
      "archetype_ref": "x_exit_global_long_ratio_collapse",
      "verdict": "seems_ok",
      "concerns": []
    },
    {
      "archetype_ref": "x_exit_premium_decay_watchdog",
      "verdict": "seems_ok",
      "concerns": []
    },
    {
      "archetype_ref": "x_exit_session_boundary_close",
      "verdict": "possibly_fail",
      "concerns": [
        "novel_dim is `session=US` but notes describe exiting BEFORE US session opens — the dim gates on being IN the US session, which contradicts a pre-US-session exit. Either the dim should be `session!=US` plus a boundary-time predicate, or notes should be 'exit at end of US session'."
      ],
      "monitoring_advice": "Check first-day paper-shadow firings: if the exit only fires on positions opened during US session, the registered behavior matches the dim, not the notes."
    },
    {
      "archetype_ref": "x_hybrid_time_then_premium_watchdog",
      "verdict": "seems_ok",
      "concerns": []
    },
    {
      "archetype_ref": "x_hybrid_breakeven_then_funding_flip",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "funding_pct_top_decile is a state flag, not a flip event — confirm the kernel interprets a transition out of that decile as the rip-cord, not just being in it."
    },
    {
      "archetype_ref": "x_exit_volume_exhaustion",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "On Reserved6 extreme-event entries, post-entry volume often collapses within 60s by design — risk of premature exits cutting genuine moves; verify trigger window is >=90s post-entry."
    },
    {
      "archetype_ref": "e_oi_collapse_volume_meanrev_short",
      "verdict": "possibly_fail",
      "concerns": [
        "OI_Price channel preview shows entries dominated by positive OI surges; oi_change_pct<=-15 may be very rare on this channel (sample-size starvation risk).",
        "Combining oi_change_pct<=-15 with volume_pct_top_decile AND liquidity_bucket=high is a triple AND on rare conditions — could yield <50 triggers in 30 days."
      ],
      "monitoring_advice": "After first GPU pass, check trigger count; if <100, relax to two of the three dims or drop liquidity gate."
    },
    {
      "archetype_ref": "e_pc_neg_premium_neg_basis_arb_long",
      "verdict": "possibly_fail",
      "concerns": [
        "premium_bps<=-20 AND basis<=-0.3 simultaneously is a rare double-negative dislocation; expect very low trigger count.",
        "Negative premium + negative basis is often a symptom of stale or thin perp book on a mid-liquidity pair, even with liquidity_bucket=high — slippage tail may eat the structural arbitrage edge."
      ],
      "monitoring_advice": "Track realized round-trip cost per trigger; if mean cost > 25bps the structural-arb thesis is dead."
    },
    {
      "archetype_ref": "e_r6_us_session_largecap_only_short",
      "verdict": "seems_ok",
      "concerns": [],
      "monitoring_advice": "R6 channel preview shows 50 entries already collapsing to identical scores — verify session+marketcap dual-gate actually differentiates triggers from baseline R6/short."
    },
    {
      "archetype_ref": "e_oi_taker_buy_with_short_squeeze_long",
      "verdict": "possibly_fail",
      "concerns": [
        "Triple-AND on taker_buy_ratio_5m>=0.65, global_short_ratio_extreme, funding<=0 is structurally restrictive; in pump regimes funding rapidly turns positive so the funding<=0 gate likely vetoes most squeeze candidates."
      ],
      "monitoring_advice": "If trigger count <200 over 30d, consider relaxing funding<=0 to funding<=fund_p50."
    },
    {
      "archetype_ref": "e_pc_pump_smart_money_neutral_short",
      "verdict": "seems_ok",
      "concerns": []
    },
    {
      "archetype_ref": "f_weekday_only_skip_weekend",
      "verdict": "likely_fail",
      "concerns": [
        "novel_dim is `weekday=Mon` but notes describe skipping weekends (i.e. allow Mon-Fri). The dim as specified will only allow Mondays, vetoing Tue-Sun including all the working weekdays the notes intend to keep. Clear logical defect between dim and stated intent — fix dim to enumerate Mon-Fri or use a `weekday!=Sat,Sun` form."
      ],
      "monitoring_advice": "After parser run, count distinct weekdays in fired triggers — if only Monday appears, dim is wrong, not parser."
    },
    {
      "archetype_ref": "r_low_liquidity_size_dampener",
      "verdict": "seems_ok",
      "concerns": []
    },
    {
      "archetype_ref": "f_stretched_market_funding_and_premium",
      "verdict": "seems_ok",
      "concerns": []
    },
    {
      "archetype_ref": "cc_conflict_oi_pc_opposite_side_skip",
      "verdict": "possibly_fail",
      "concerns": [
        "novel_dim only specifies `session=US`; the cross-channel conflict logic (opposite-side OI vs pricechange within 90s) is not represented in any supported field. Risk that the kernel cannot encode the temporal+side conflict and falls back to baseline."
      ],
      "monitoring_advice": "Verify the kernel parser actually reads cross-channel timing windows; if not, this archetype will degenerate to a session=US filter."
    },
    {
      "archetype_ref": "cc_confirm_pc_r6_same_dir_size_boost",
      "verdict": "possibly_fail",
      "concerns": [
        "Same parser concern as conflict variant — temporal co-firing window (120s) and same-direction logic aren't in novel_dim, only session=US + liquidity_bucket=high.",
        "Restricting to US session AND high liquidity will additionally compress already-rare pc+r6 co-firings; expect very few size-boost events."
      ],
      "monitoring_advice": "Log pc+r6 same-direction co-fire count over 30d before and after session+liquidity gates to confirm enough sample remains for size-boost to matter."
    },
    {
      "archetype_ref": "f_listing_age_minimum_180d",
      "verdict": "seems_ok",
      "concerns": []
    },
    {
      "archetype_ref": "x_exit_basis_invert",
      "verdict": "possibly_fail",
      "concerns": [
        "novel_dim is `basis<=0` which is a state predicate, not an inversion event. If entry already had basis<=0 (common in deep pumps with negative carry), this exits at T0+epsilon for zero edge.",
        "Need a transition predicate (basis_sign_change_since_entry) to capture inversion semantics; current flag is ambiguous."
      ],
      "monitoring_advice": "Track time-to-exit distribution; if mode <5s, exit is firing on entry-time state, not crossings."
    }
  ]
}
```

## 3. Quant (model=claude-opus-4-7, 222.46s)

```json
{
  "summary": "Batch is mathematically healthy with strong exit-side coverage as requested; primary concerns are sample-size starvation on triple-AND entries (#9, #10, #12), a literal weekday=Mon defect that contradicts stated intent (#14), and cross-channel archetypes (#17, #18) whose temporal/co-firing logic falls outside SUPPORTED_FIELDS so they degenerate to plain filters at parse time; #20 basis-invert and #5 session-boundary need transition vs state-predicate clarification but remain useful narrowings.",
  "analyses": [
    {
      "archetype_ref": "x_exit_on_top_trader_position_dec",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X083"
      ],
      "distinctness_notes": "Flag-token exit (top_trader_position_ratio ≤ p25) is a smart-money rip-cord; orthogonal to PnL-shape kernels (fixed/trail/multi_tp/breakeven/time_only). Adjacent to existing X083 (exit_on_top_trader_change) but uses a state-flag rather than a delta-event.",
      "expected_triggers_30d": 1500,
      "triggers_estimate_method": "Applies to all open positions; ~25% of trade lives will cross top_trader_position_ratio into the bottom quartile post-entry (≈ 6000 trades/30d × 0.25 = 1500)",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Best as watchdog overlay on fixed kernel; weak signal added to breakeven; redundant with multi_tp ladder."
    },
    {
      "archetype_ref": "x_exit_funding_normalize_meanrev",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X080"
      ],
      "distinctness_notes": "Differs from X080 (exit_on_funding_flip): exits when funding_abs leaves the high band (mean reversion) rather than on a sign flip. New regime-state exit family.",
      "expected_triggers_30d": 600,
      "triggers_estimate_method": "Funding cadence is 8h on Binance → ≤3 evaluation points/day per trade; ~10% of high-funding entries see normalization within trade window. 6000 trades × 0.10 = 600",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Only meaningful when entry was conditioned on a funding-extreme regime; pairs with funding_abs_high entries; weakly informative for non-funding-conditioned entries."
    },
    {
      "archetype_ref": "x_exit_global_long_ratio_collapse",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Sentiment-flip exit gated on global_long_ratio_high transition out; current 133 exits are price/time-based and don't use crowd-sentiment regimes.",
      "expected_triggers_30d": 800,
      "triggers_estimate_method": "Long-only subset (~50% of trades = 3000) × ~25% see global_long_ratio leave the p75+ band during trade window (8h funding cycles) ≈ 750-800",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Long-only family; pairs naturally with squeeze-long entries that conditioned on high crowd-long sentiment to begin with."
    },
    {
      "archetype_ref": "x_exit_premium_decay_watchdog",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X081"
      ],
      "distinctness_notes": "Differs from X081 (exit_on_premium_spike): exits on decay OUT of premium-extreme rather than on entry into one. State-leaving rather than state-entering — distinct kernel direction.",
      "expected_triggers_30d": 400,
      "triggers_estimate_method": "Long-only subset 3000 × ~13% see premium leave the p90+ band within trade lifetime ≈ 400",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "narrow",
      "exit_compatibility_notes": "Best on long entries with premium_extreme in entry conditions; on other entries this is a near-no-op."
    },
    {
      "archetype_ref": "x_exit_session_boundary_close",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Calendar-session exit; existing time_only family uses absolute durations only. Math caveat: novel_dim `session=US` reads as 'while in US session'; if intended as 'before US open' the predicate is logically inverted (Devil flagged this) — synthesizer should clarify direction or accept the literal reading 'force-close at US-session END'.",
      "expected_triggers_30d": 2000,
      "triggers_estimate_method": "~33% of trades open during US session; all of them get a session-end forced exit ≈ 6000 × 0.33 = 2000",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Compatible with all entries; effectively a calendar-time stop. Note: literal-dim semantics is 'in-session', not 'pre-session'; synthesizer should pick one and document."
    },
    {
      "archetype_ref": "x_hybrid_time_then_premium_watchdog",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Hybrid composition: time-baseline + premium_extreme failsafe. None of the 5 base kernels combine time-stop with a state-flag rip-cord — structurally novel.",
      "expected_triggers_30d": 800,
      "triggers_estimate_method": "Across all trades (6000), ~13% see premium hit the opposite extreme within their time window ≈ 800",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Generic time-based hybrid; works on any entry channel/side."
    },
    {
      "archetype_ref": "x_hybrid_breakeven_then_funding_flip",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Composition of breakeven kernel + funding_pct_top_decile rip-cord. Existing breakeven kernel only ladders on price; funding-decile transition as second-stage exit is novel.",
      "expected_triggers_30d": 300,
      "triggers_estimate_method": "Conditional on price reaching TP/2 (~40% of trades = 2400) × ~13% see funding decile flip during remaining trade life ≈ 300",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Note: funding_pct_top_decile is a state flag (≥p90); kernel must interpret a transition OUT as the trigger — confirm during paper-shadow."
    },
    {
      "archetype_ref": "x_exit_volume_exhaustion",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X079"
      ],
      "distinctness_notes": "Inverse of X079 (exit_on_volume_spike) — exits on volume collapse rather than spike. Distinct trigger semantics.",
      "expected_triggers_30d": 1500,
      "triggers_estimate_method": "All trades 6000 × ~25% see post-entry volume drop into bottom quartile ≈ 1500",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Risk on Reserved6 entries: post-event volume collapse is structural; needs ≥90s post-entry trigger window to avoid clipping genuine moves."
    },
    {
      "archetype_ref": "e_oi_collapse_volume_meanrev_short",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Negative-side oi_change_pct entries are rare in the existing 257; combined with high-decile volume + high-liquidity gate yields a structurally new mean-reversion setup with naturally symmetric TP/SL profile.",
      "expected_triggers_30d": 7,
      "triggers_estimate_method": "OI_Price events 1400 × ~10% (oi_change_pct ≤ -15 is rare on this OI-surge channel) × ~10% (volume top decile) × ~50% (high liquidity) ≈ 7",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Mean-reversion thesis pairs with multi_tp or fixed-symmetric (TP≈SL); avoid trail/runner kernels which assume continuation."
    },
    {
      "archetype_ref": "e_pc_neg_premium_neg_basis_arb_long",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Two-leg negative-dislocation entry; current pricechange/long set hunts positive premium/funding extremes. Direction-distinct.",
      "expected_triggers_30d": 12,
      "triggers_estimate_method": "pricechange 5000 × ~5% (premium_bps ≤ -20) × ~10% (basis ≤ -0.3 conditional on negative premium, partially co-incident) × ~50% (high liquidity) ≈ 12",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Structural-arb thesis: short-horizon mean-reversion fits multi_tp / fixed-tight-TP; trail kernels misaligned with thesis."
    },
    {
      "archetype_ref": "e_r6_us_session_largecap_only_short",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E316",
        "E317",
        "E318",
        "E319",
        "E320",
        "E321",
        "E322",
        "E323",
        "E327",
        "E333"
      ],
      "distinctness_notes": "R6/long preview shows 50 archetypes collapsing to identical scores → existing R6 dims aren't differentiating triggers. Adding session+marketcap+hour dual-gate is the first R6 archetype with a real trigger-set narrowing.",
      "expected_triggers_30d": 35,
      "triggers_estimate_method": "Reserved6 800 × ~33% (US session) × ~20% (large cap) × ~80% (hour 14-20 ⊂ US session) ≈ 42; conservatively 35",
      "sample_size_verdict": "tight",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 4,
      "n_total_conditions": 4,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "R6 short bias and US-large-cap focus → liquid execution; pair with fixed kernel TP≈3-5%, SL≈3% for symmetric profile."
    },
    {
      "archetype_ref": "e_oi_taker_buy_with_short_squeeze_long",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Triple-orthogonal-confirmation entry: flow (taker_buy) × crowd (global_short_extreme) × cost (funding≤0). This specific 3-way combination absent from existing OI_Price/long set.",
      "expected_triggers_30d": 28,
      "triggers_estimate_method": "OI_Price 1400 × ~25% (taker_buy ≥ 0.65) × ~10% (global_short_extreme p90) × ~80% (funding ≤ 0 conditional on crowded short) ≈ 28",
      "sample_size_verdict": "too_few",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Squeeze thesis fits trail or multi_tp_with_runner — current results show trail family all-negative, so multi_tp may dominate. Note Devil's funding-vetoes-pumps concern: funding≤0 cuts most squeeze candidates."
    },
    {
      "archetype_ref": "e_pc_pump_smart_money_neutral_short",
      "distinct": true,
      "distinct_from_existing_ids": [
        "E149"
      ],
      "distinctness_notes": "Differs from E149 (pc_pump_aggressive_buy_immediate_long) by inverting side and adding smart-money-divergence (top_trader_position_ratio_dec). Smart-money-fade entry not present in existing fade set.",
      "expected_triggers_30d": 125,
      "triggers_estimate_method": "pricechange 5000 × ~50% (event_type=pump) × ~25% (top_trader p25 dec) × ~20% (premium_bps ≥ 20 ≈ p80) ≈ 125",
      "sample_size_verdict": "adequate",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 3,
      "n_total_conditions": 3,
      "exit_compatibility": "specific",
      "exit_compatibility_notes": "Fade-pump thesis fits fixed-symmetric (TP≈SL ~3%) or multi_tp_with_be; avoid runner kernels — fade is short-horizon by design."
    },
    {
      "archetype_ref": "f_weekday_only_skip_weekend",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "MATH DEFECT: novel_dim `weekday=Mon` is literal-Monday-only, contradicting stated 'skip weekend' intent (which would need Mon-Fri inclusion). As written, filter passes ~14% of trades; as intended, ~71%. Synthesizer must pick: either rewrite dim to multiple `weekday=...` rows or treat literal as 'Mon-only filter' and rename. Distinct EITHER way.",
      "expected_triggers_30d": 850,
      "triggers_estimate_method": "If literal weekday=Mon: 6000 × ~14% = 850 trades pass. If intended Mon-Fri: 6000 × ~71% = 4260.",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Calendar gate; agnostic to exit family. Recommend the synthesizer fix the dim/name pairing before commit."
    },
    {
      "archetype_ref": "r_low_liquidity_size_dampener",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "Liquidity-bucket-tied sizing rule; risk family of 41 doesn't currently have a slippage-realism dampener keyed to low-bucket bookings. Distinct.",
      "expected_triggers_30d": 1800,
      "triggers_estimate_method": "All trades 6000 × ~30% in low-liquidity bucket ≈ 1800 (each gets 50% size)",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Risk-side rule, exit-agnostic; will reduce left-tail magnitude under new mean/Kelly metrics — directly addresses R2 E126 paper bleed lesson."
    },
    {
      "archetype_ref": "f_stretched_market_funding_and_premium",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "AND-composite over funding_abs_high + premium_extreme; existing filter set tends to use single flags, so the conjunction is structurally distinct.",
      "expected_triggers_30d": 200,
      "triggers_estimate_method": "Trades that match both flags: ~25% (funding_abs_high p75) × ~10% (premium_extreme p90) × correlation factor ~1.3 = ~3% of 6000 ≈ 200 SKIPPED",
      "sample_size_verdict": "tight",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Pre-trade veto; works with any exit family. Tight sample is fine since this is a SKIP filter."
    },
    {
      "archetype_ref": "cc_conflict_oi_pc_opposite_side_skip",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "PARTIAL-DEGEN: The cross-channel conflict semantics described in notes (opposite-side OI+pc within 90s) are NOT in supported fields — there is no temporal/cross-channel predicate. As parsed, archetype reduces to a `session=US` filter. Distinct ONLY if the loop has a separate cross_channel kernel that consumes the type metadata; otherwise this is a duplicate of any session=US filter.",
      "expected_triggers_30d": 2000,
      "triggers_estimate_method": "If parsed as session=US filter only: 6000 × 0.33 = 2000. If true CC-conflict logic exists: ~30 OI/pc opposite-side co-fires × 0.33 US ≈ 10",
      "sample_size_verdict": "ample",
      "computable_at_T0": false,
      "uncomputable_fields": [
        "cross_channel_opposite_side_within_90s"
      ],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Synthesizer note: confirm whether a CC-kernel reads the `type=cross_channel` metadata to apply the temporal conflict logic; if not, this archetype's behavior is the session filter alone."
    },
    {
      "archetype_ref": "cc_confirm_pc_r6_same_dir_size_boost",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "PARTIAL-DEGEN: Same parser concern as cc_conflict — pc+R6 same-direction co-firing within 120s logic is unrepresented in novel_dim. As filter-parsed, reduces to session=US AND liquidity_bucket=high. Distinct only if a CC-kernel layer activates on type=cross_channel.",
      "expected_triggers_30d": 1000,
      "triggers_estimate_method": "If parsed as filter only: 6000 × 0.33 (US) × 0.5 (high liq) ≈ 1000. If true CC co-fire logic: ~20-40 pc+R6 co-fires × gates ≈ 5",
      "sample_size_verdict": "ample",
      "computable_at_T0": false,
      "uncomputable_fields": [
        "cross_channel_same_direction_within_120s",
        "size_multiplier=1.5"
      ],
      "fall_through_conditions": [],
      "n_supported_conditions": 2,
      "n_total_conditions": 2,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Same caveat as cc_conflict — synthesizer must verify CC-kernel exists; otherwise this is a vanilla session+liquidity filter."
    },
    {
      "archetype_ref": "f_listing_age_minimum_180d",
      "distinct": true,
      "distinct_from_existing_ids": [],
      "distinctness_notes": "First age-based filter; existing filters use marketcap/liquidity buckets only. Distinct.",
      "expected_triggers_30d": 4500,
      "triggers_estimate_method": "Most listed Binance pairs are >180d → ~75% of trades pass = 6000 × 0.75 = 4500",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Pre-trade veto on new listings; agnostic to exit family. Filters away unreliable kline regime — directly supports historical pattern validity."
    },
    {
      "archetype_ref": "x_exit_basis_invert",
      "distinct": true,
      "distinct_from_existing_ids": [
        "X084"
      ],
      "distinctness_notes": "Differs from X084 (exit_on_basis_invert) registered already by similar name? — verify slug uniqueness. SEMANTIC CAVEAT: novel_dim `basis<=0` is a state predicate, not a transition. If entry already had basis≤0, this exits at T0+ε for zero edge (Devil flagged). Need transition-since-entry semantics for the inversion thesis to hold.",
      "expected_triggers_30d": 1800,
      "triggers_estimate_method": "All trades 6000 × ~30% see basis cross zero during trade lifetime ≈ 1800 (much higher under literal-state reading)",
      "sample_size_verdict": "ample",
      "computable_at_T0": true,
      "uncomputable_fields": [],
      "fall_through_conditions": [],
      "n_supported_conditions": 1,
      "n_total_conditions": 1,
      "exit_compatibility": "broad",
      "exit_compatibility_notes": "Carry-regime exit; pairs best with structural-arb entries (e.g. proposal #10). Under literal state-reading: mode of time-to-exit will be near-zero for entries already in basis≤0 — synthesizer should treat this as informative regardless and let the GPU loop reveal the distribution."
    }
  ]
}
```

## 4. Risk (model=claude-opus-4-7, 130.36s)

```json
{
  "summary": "Batch is research-integrity clean — no concrete data leakage, no credential exposure, no mass-manipulation enablers; main monitoring concerns are live-overlap on OI_Price entries with the user's existing pump-long live strategy and concentration risk from the 1.5x size-boost cross-channel rule.",
  "risk_assessments": [
    {
      "archetype_ref": "x_exit_on_top_trader_position_dec",
      "leakage_risk": "none",
      "leakage_notes": "Exit archetype using top_trader_position_ratio_dec is post-entry by design — exits are supposed to consume post-T0 state and this is not future-snooping into entry conditions.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Pure exit overlay — no new positions opened, no conflict with live OI_Price pump-long.",
      "concentration_risk": "none",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "None required."
    },
    {
      "archetype_ref": "x_exit_funding_normalize_meanrev",
      "leakage_risk": "none",
      "leakage_notes": "funding_abs_high consumed post-entry as a regime-state exit; no T0 contamination.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit-only kernel.",
      "concentration_risk": "none",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "None required."
    },
    {
      "archetype_ref": "x_exit_global_long_ratio_collapse",
      "leakage_risk": "none",
      "leakage_notes": "global_long_ratio_high regime change is a legitimate post-entry exit signal.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit-only kernel.",
      "concentration_risk": "none",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "None required."
    },
    {
      "archetype_ref": "x_exit_premium_decay_watchdog",
      "leakage_risk": "none",
      "leakage_notes": "premium_extreme transition consumed post-T0 as exit trigger; allowed.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit-only kernel.",
      "concentration_risk": "none",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "None required."
    },
    {
      "archetype_ref": "x_exit_session_boundary_close",
      "leakage_risk": "none",
      "leakage_notes": "session=US is calendar metadata, fully known at T0 and after.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit-only kernel.",
      "concentration_risk": "none",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "None required from a risk-integrity perspective; Devil's dim/notes-direction defect is a synthesizer correctness item, not an integrity issue."
    },
    {
      "archetype_ref": "x_hybrid_time_then_premium_watchdog",
      "leakage_risk": "none",
      "leakage_notes": "Hybrid exit with premium_extreme failsafe — post-entry consumption is appropriate for an exit family.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit-only kernel.",
      "concentration_risk": "none",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "None required."
    },
    {
      "archetype_ref": "x_hybrid_breakeven_then_funding_flip",
      "leakage_risk": "none",
      "leakage_notes": "funding_pct_top_decile transition observed post-entry — clean for an exit overlay.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit-only kernel.",
      "concentration_risk": "none",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "None required."
    },
    {
      "archetype_ref": "x_exit_volume_exhaustion",
      "leakage_risk": "none",
      "leakage_notes": "volume_pct_below_p25 measured post-entry as an exit trigger; not entry-time leakage.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit-only kernel.",
      "concentration_risk": "none",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "None required."
    },
    {
      "archetype_ref": "e_oi_collapse_volume_meanrev_short",
      "leakage_risk": "none",
      "leakage_notes": "oi_change_pct, volume_pct_top_decile, and liquidity_bucket are all standard pre-T0 derivable fields; no forward_/confirm_after/post_event suffix.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "medium",
      "live_conflict_notes": "OI_Price/short on a symbol the user's live BWE_OI_Price_monitor pump-long strategy could simultaneously be long — opposite-side conflict possible during simultaneous OI surge+collapse regimes on adjacent symbols.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "During paper-shadow, log any same-symbol same-window collisions with the live OI_Price pump-long; if any occur, add a conflict-skip guard before promotion."
    },
    {
      "archetype_ref": "e_pc_neg_premium_neg_basis_arb_long",
      "leakage_risk": "none",
      "leakage_notes": "premium_bps and basis are spot/perp dislocation fields known at T0; liquidity_bucket is symbol metadata.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Pricechange/long does not directly overlap with live OI_Price pump-long unless cross-channel co-firing occurs; mitigated by separate channel.",
      "concentration_risk": "low",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "None required from integrity perspective."
    },
    {
      "archetype_ref": "e_r6_us_session_largecap_only_short",
      "leakage_risk": "none",
      "leakage_notes": "session, marketcap_bucket, hour_utc are all calendar/symbol metadata available at T0.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "low",
      "live_conflict_notes": "R6 short on large-caps does not collide with live OI_Price pump-long.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Large-cap-only restriction concentrates triggers on a small symbol set (BTC/ETH/SOL/etc.) during US hours — monitor symbol-level distribution; if >50% of triggers land on 1-2 symbols, add a per-symbol throttle."
    },
    {
      "archetype_ref": "e_oi_taker_buy_with_short_squeeze_long",
      "leakage_risk": "low",
      "leakage_notes": "taker_buy_ratio_5m is conventionally the trailing 5-minute window up to T0 — clean. Flagged as low (not none) because if the kernel implementation interprets it as forward 5m it would be leakage; verify SUPPORTED_FIELDS resolves it to trailing.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "high",
      "live_conflict_notes": "OI_Price/long with squeeze fuel directly overlaps with the user's existing BWE_OI_Price_monitor pump-long live strategy — same channel, same side, same general regime. Two systems opening longs on the same symbol within seconds will double the user's effective sizing.",
      "concentration_risk": "medium",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "Before any promotion, gate this archetype with a 'no live-system overlap' check: skip if the live OI_Price pump-long has fired on the same symbol within ±5 minutes. Document the overlap explicitly in the paper-shadow report."
    },
    {
      "archetype_ref": "e_pc_pump_smart_money_neutral_short",
      "leakage_risk": "low",
      "leakage_notes": "top_trader_position_ratio_dec on entry is acceptable IF interpreted as the trailing-window decline up to T0; if the field encodes a forward-window decrease it would be post-T0 leakage. Quant marked computable_at_T0=true — trust pending kernel verification.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "low",
      "live_conflict_notes": "Pricechange/short on pump events does not directly conflict with live OI_Price pump-long.",
      "concentration_risk": "low",
      "adversarial_risk": "medium",
      "overall_severity": "caution",
      "remediation": "Confirm SUPPORTED_FIELDS definition of top_trader_position_ratio_dec is trailing-window. If forward-window, downgrade to exit-only or rewrite. Adversarial: a sophisticated taker watching BWE pricechange + perp top-trader feed could front-run; acceptable at $1000 capital."
    },
    {
      "archetype_ref": "f_weekday_only_skip_weekend",
      "leakage_risk": "none",
      "leakage_notes": "Calendar-only filter; no leakage vector.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Pre-trade filter does not generate positions.",
      "concentration_risk": "low",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "None from integrity perspective; the Devil-flagged dim/notes mismatch is a correctness item for the synthesizer to fix, not a risk block."
    },
    {
      "archetype_ref": "r_low_liquidity_size_dampener",
      "leakage_risk": "none",
      "leakage_notes": "Sizing rule keyed on symbol metadata bucket; no future leakage.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Sizing-only rule.",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "None required — actively reduces concentration risk and addresses the R2 E126 paper-bleed lesson."
    },
    {
      "archetype_ref": "f_stretched_market_funding_and_premium",
      "leakage_risk": "none",
      "leakage_notes": "Both flags are pre-T0 regime states.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Pre-trade veto only.",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "None required."
    },
    {
      "archetype_ref": "cc_conflict_oi_pc_opposite_side_skip",
      "leakage_risk": "none",
      "leakage_notes": "Cross-channel skip rule; even if Quant flags partial-degeneration into a session=US filter, this is a correctness/encoding issue, not a leakage one.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Conflict-skip rule actively REDUCES live-system collision risk if the kernel honors it.",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "None from integrity perspective; synthesizer must verify kernel reads cross-channel metadata before claiming the conflict logic actually fires."
    },
    {
      "archetype_ref": "cc_confirm_pc_r6_same_dir_size_boost",
      "leakage_risk": "none",
      "leakage_notes": "Cross-channel size-boost rule; no future-function fields.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "low",
      "live_conflict_notes": "pc+R6 confirmation does not directly collide with live OI_Price pump-long, though same-symbol stacking is possible during multi-channel regimes.",
      "concentration_risk": "high",
      "adversarial_risk": "low",
      "overall_severity": "caution",
      "remediation": "1.5x boost on an already 5-10% per-trade sizing pushes effective exposure to 7.5-15% on a $1000 account — at the upper edge of the user's stated risk envelope. Cap the boost so post-boost notional does not exceed 12% of capital, and forbid the boost when the user has another open BWE-driven position on the same symbol."
    },
    {
      "archetype_ref": "f_listing_age_minimum_180d",
      "leakage_risk": "none",
      "leakage_notes": "listing_age_days is symbol metadata known at T0 and earlier.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Pre-trade filter only.",
      "concentration_risk": "none",
      "adversarial_risk": "none",
      "overall_severity": "acceptable",
      "remediation": "None required."
    },
    {
      "archetype_ref": "x_exit_basis_invert",
      "leakage_risk": "none",
      "leakage_notes": "basis<=0 evaluated post-entry as an exit trigger is by-design post-T0 consumption and not entry leakage.",
      "multitest_inflation_risk": "low",
      "live_conflict_risk": "none",
      "live_conflict_notes": "Exit-only kernel.",
      "concentration_risk": "none",
      "adversarial_risk": "low",
      "overall_severity": "acceptable",
      "remediation": "None from integrity perspective; the Quant/Devil-flagged state-vs-transition semantics is a correctness item, not a leakage block."
    }
  ]
}
```

## 5. Synthesizer (model=claude-opus-4-7, 169.19s)

```json
{
  "summary": "Round 4 Generator delivered the requested exit-side surge (9 of 20 proposals are exits, addressing the X101+ pipeline starvation lesson) plus naturally symmetric mean-reversion entries and conflict/confirm cross-channel logic. Default-accept posture honored: 19 accepted (12 clean, 7 accept-with-watch), 1 revised for clear dim/notes contradiction, 0 rejected. No concrete post-T0 leakage and no kernel-blocking duplicate slugs were found.",
  "accepted_archetypes": [
    {
      "id": "X134",
      "type": "exit",
      "archetype": "x_exit_on_top_trader_position_dec",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "top_trader_position_ratio_dec"
      ],
      "expected_distinct": true,
      "notes": "Exit when smart-money top-trader position ratio drops post-entry — they are unwinding before retail catches the reversal.",
      "synthesizer_note": "Clean smart-money rip-cord; orthogonal to X083 (delta-event) by using state-flag semantics."
    },
    {
      "id": "X135",
      "type": "exit",
      "archetype": "x_exit_funding_normalize_meanrev",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "funding_abs_high"
      ],
      "expected_distinct": true,
      "notes": "Exit when funding rate has crossed back into normal band from extreme — extreme-funding alpha is gone.",
      "synthesizer_note": "Differs from X080 flip; mean-reversion regime exit. Devil's 8h-cadence note is monitoring guidance, not a blocker."
    },
    {
      "id": "X136",
      "type": "exit",
      "archetype": "x_exit_global_long_ratio_collapse",
      "channel": "*",
      "side": "long",
      "novel_dim": [
        "global_long_ratio_high"
      ],
      "expected_distinct": true,
      "notes": "For long entries — exit when global_long_ratio decays out of the high band, signaling crowd flip.",
      "synthesizer_note": "First sentiment-flip exit family; pairs with crowd-condition long entries."
    },
    {
      "id": "X137",
      "type": "exit",
      "archetype": "x_exit_premium_decay_watchdog",
      "channel": "*",
      "side": "long",
      "novel_dim": [
        "premium_extreme"
      ],
      "expected_distinct": true,
      "notes": "Long exit watchdog — close when premium falls out of the extreme band, removing the premium-squeeze rationale.",
      "synthesizer_note": "Direction-distinct from X081 (entry-into vs leave-of premium-extreme)."
    },
    {
      "id": "X138",
      "type": "exit",
      "archetype": "x_exit_session_boundary_close",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "session=US"
      ],
      "expected_distinct": true,
      "notes": "Force-close any open position at US-session END (literal reading of session=US dim — i.e. trades held during US session get closed at session boundary).",
      "synthesizer_note": "Devil flagged dim/notes-direction mismatch; resolved by adopting literal-dim reading (close at end of US session, not before US open) and rewording notes accordingly."
    },
    {
      "id": "X139",
      "type": "exit",
      "archetype": "x_hybrid_time_then_premium_watchdog",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "premium_extreme"
      ],
      "expected_distinct": true,
      "notes": "Hold for fixed time window unless premium crosses into the opposite extreme — then early exit; combines time + state-change.",
      "synthesizer_note": "Hybrid time+state composition not present in the 5 base kernels."
    },
    {
      "id": "X140",
      "type": "exit",
      "archetype": "x_hybrid_breakeven_then_funding_flip",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "funding_pct_top_decile"
      ],
      "expected_distinct": true,
      "notes": "Breakeven once unrealized hits TP/2, then add a funding-flip rip-cord — exits if the funding regime inverts.",
      "synthesizer_note": "Devil's flag-vs-event note: kernel must read the transition OUT of top decile as trigger; verify in paper-shadow."
    },
    {
      "id": "X141",
      "type": "exit",
      "archetype": "x_exit_volume_exhaustion",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "volume_pct_below_p25"
      ],
      "expected_distinct": true,
      "notes": "Exit once realized volume in the post-entry window drops into the bottom quartile — momentum has died. Trigger window must be ≥90s post-entry to avoid clipping R6 structural post-event volume collapse.",
      "synthesizer_note": "Inverse of X079; Devil's R6-clipping concern absorbed into notes as ≥90s guard."
    },
    {
      "id": "E334",
      "type": "entry",
      "archetype": "e_oi_collapse_volume_meanrev_short",
      "channel": "OI_Price",
      "side": "short",
      "novel_dim": [
        "oi_change_pct<=-15",
        "volume_pct_top_decile",
        "liquidity_bucket=high"
      ],
      "expected_distinct": true,
      "notes": "Short when OI collapses sharply with high volume on a liquid pair — leveraged longs being flushed, expect mean reversion.",
      "synthesizer_note": "Quant ~7 triggers/30d (too_few) — accept-with-watch; if first GPU pass shows <30 triggers, relax liquidity_bucket gate. Risk caution on live-overlap with OI_Price pump-long: log same-symbol collisions before any promotion."
    },
    {
      "id": "E335",
      "type": "entry",
      "archetype": "e_pc_neg_premium_neg_basis_arb_long",
      "channel": "pricechange",
      "side": "long",
      "novel_dim": [
        "premium_bps<=-20",
        "basis<=-0.3",
        "liquidity_bucket=high"
      ],
      "expected_distinct": true,
      "notes": "Long when both premium and basis are deeply negative — perp under-priced relative to spot, structural arbitrage support.",
      "synthesizer_note": "Quant ~12 triggers/30d (too_few) — accept-with-watch; track realized round-trip cost, abandon if mean cost >25bps per Devil."
    },
    {
      "id": "E336",
      "type": "entry",
      "archetype": "e_r6_us_session_largecap_only_short",
      "channel": "Reserved6",
      "side": "short",
      "novel_dim": [
        "session=US",
        "marketcap_bucket=large",
        "hour_utc>=14",
        "hour_utc<=20"
      ],
      "expected_distinct": true,
      "notes": "R6 extreme-move short, restricted to US session and large-cap only — best execution venue, lowest slippage tail.",
      "synthesizer_note": "First R6 archetype with real trigger-set narrowing vs the duplicate-score E316–E333 set; per Risk caution, monitor symbol-level distribution and add per-symbol throttle if >50% land on 1-2 names."
    },
    {
      "id": "E337",
      "type": "entry",
      "archetype": "e_oi_taker_buy_with_short_squeeze_long",
      "channel": "OI_Price",
      "side": "long",
      "novel_dim": [
        "taker_buy_ratio_5m>=0.65",
        "global_short_ratio_extreme",
        "funding<=0"
      ],
      "expected_distinct": true,
      "notes": "Long on OI_Price when aggressive buying meets crowded shorts AND funding is non-positive — squeeze fuel without paying funding tax.",
      "synthesizer_note": "Quant ~28 triggers/30d (too_few) and Risk HIGH live-conflict with existing OI_Price pump-long live strategy. Accept-with-watch ONLY for backtest/paper; before any live promotion, gate with ±5min same-symbol live-overlap skip per Risk remediation."
    },
    {
      "id": "E338",
      "type": "entry",
      "archetype": "e_pc_pump_smart_money_neutral_short",
      "channel": "pricechange",
      "side": "short",
      "novel_dim": [
        "event_type=pump",
        "top_trader_position_ratio_dec",
        "premium_bps>=20"
      ],
      "expected_distinct": true,
      "notes": "Pump event short — fade when top traders are decreasing position AND premium is hot; retail-driven exhaustion setup.",
      "synthesizer_note": "Smart-money-fade entry adequate sample (~125). Risk caution on top_trader_position_ratio_dec window semantics — verify SUPPORTED_FIELDS interprets it as trailing, not forward; downgrade to exit-only if forward."
    },
    {
      "id": "R042",
      "type": "risk",
      "archetype": "r_low_liquidity_size_dampener",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "liquidity_bucket=low"
      ],
      "expected_distinct": true,
      "notes": "Risk archetype that down-sizes by 50% on low-liquidity bucket trades to keep slippage tail bounded under compound replay.",
      "synthesizer_note": "Directly addresses R2 E126 paper-bleed lesson; new mean/Kelly metrics will reward left-tail compression."
    },
    {
      "id": "F124",
      "type": "filter",
      "archetype": "f_stretched_market_funding_and_premium",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "funding_abs_high",
        "premium_extreme"
      ],
      "expected_distinct": true,
      "notes": "Skip entries when BOTH funding-abs and premium are in their extreme bands — over-stretched market, mean-reversion risk to existing positions.",
      "synthesizer_note": "AND-composite distinct from existing single-flag filters; ~200 skips/30d is fine for a SKIP filter."
    },
    {
      "id": "C065",
      "type": "cross_channel",
      "archetype": "cc_conflict_oi_pc_opposite_side_skip",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "session=US"
      ],
      "expected_distinct": true,
      "notes": "Cross-channel veto — when OI_Price and pricechange fire on the same symbol with opposite sides within 90s, skip both. session=US gate restricts to high-liquidity hours.",
      "synthesizer_note": "Quant flagged temporal/cross-channel logic is NOT in SUPPORTED_FIELDS — kernel must consume type=cross_channel metadata for conflict-skip to actually fire; verify in paper-shadow before promotion."
    },
    {
      "id": "C066",
      "type": "cross_channel",
      "archetype": "cc_confirm_pc_r6_same_dir_size_boost",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "session=US",
        "liquidity_bucket=high"
      ],
      "expected_distinct": true,
      "notes": "When pricechange and Reserved6 fire same direction within 120s on a high-liquidity name, size-boost x1.5; double-channel confirmation = high-quality. Boost capped so post-boost notional ≤12% of capital, and forbidden when another open BWE position exists on same symbol.",
      "synthesizer_note": "Risk HIGH concentration on 1.5x boost over 5-10% base — incorporated 12% notional cap and same-symbol veto into notes per Risk remediation. Same CC-kernel verification caveat as C065."
    },
    {
      "id": "F125",
      "type": "filter",
      "archetype": "f_listing_age_minimum_180d",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "listing_age_days>=180"
      ],
      "expected_distinct": true,
      "notes": "Filter out symbols listed under 180 days — avoid new-listing volatility regime where historical kline patterns are unreliable.",
      "synthesizer_note": "First age-based filter; supports historical pattern validity for the entire entry roster."
    },
    {
      "id": "X142",
      "type": "exit",
      "archetype": "x_exit_basis_invert",
      "channel": "*",
      "side": "both",
      "novel_dim": [
        "basis<=0"
      ],
      "expected_distinct": true,
      "notes": "Exit when basis is in the non-positive regime post-entry; structural carry rationale removed. State-predicate reading — for entries already in basis≤0, exit will fire near T0+ε which the GPU loop will surface in time-to-exit distribution.",
      "synthesizer_note": "Quant flagged near-name overlap with X084 (exit_on_basis_invert) — accept anyway because the supported-field encoding (basis<=0 state) differs from X084's transition semantics; let GPU/paper-shadow distinguish via TP/SL surface and time-to-exit mode."
    }
  ],
  "revised_archetypes": [
    {
      "original_archetype_ref": "f_weekday_only_skip_weekend",
      "revised_archetype": "f_monday_only_setup",
      "revision_reason": "Devil + Quant flagged clear logical defect: novel_dim weekday=Mon contradicts stated 'skip weekend' (Mon-Fri) intent. SUPPORTED_FIELDS uses single-value categorical equality, so an AND of weekday=Mon..Fri is impossible (weekday is a single value per row), and there is no negation predicate to encode 'skip Sat/Sun'. Revised by aligning slug+notes to the literal dim (Monday-only setup) — the user can later request a true Mon-Fri filter if the parser is extended to support categorical IN-lists.",
      "revised_novel_dim": [
        "weekday=Mon"
      ],
      "revised_notes": "Monday-only setup gate — focuses on Asian + early-US weekly-open liquidity regime. NOTE: this is NOT the originally-intended weekend-skip filter; SUPPORTED_FIELDS lacks the IN-list / negation needed for that semantic. If a Mon-Fri inclusion gate is desired, request a parser extension to weekday=Mon|Tue|Wed|Thu|Fri or weekday!=Sat,Sun."
    }
  ],
  "rejected_archetypes": [],
  "next_round_focus": "Round 5 should (a) verify whether the loop's cross-channel kernel actually consumes type=cross_channel metadata for temporal conflict/confirm logic — if not, propose a parser extension before more CC archetypes; (b) extend the parser to support categorical IN-lists / negation so weekday-skip and similar filters can be specified honestly; and (c) propose more naturally-symmetric mean-reversion entries on OI_Price (negative-side oi_change_pct is under-explored) plus exits keyed on basis-transition and funding-decile transition events rather than state predicates."
}
```
