"""Day 1.3: Generate seed hypothesis_registry.jsonl with 300 archetypes.

Output:
    H:/BWE/40_EXPERIMENTS/hypothesis_registry.jsonl

Each line is a JSON object with this schema:
    {
        "id": str,            # e.g. "E001", "X042", "F012", "R007", "C031"
        "type": str,          # entry | exit | filter | risk | cross_channel
        "archetype": str,     # snake_case slug (the IDEA, not parameters)
        "channel": str,       # OI_Price | pricechange | Reserved6 | * | NA
        "side": str,          # long | short | both | NA
        "novel_dim": [str],   # distinguishing features (T0-known fields only for filter/entry)
        "expected_distinct": bool,  # likely structurally distinct from existing
        "notes": str          # one-sentence trading logic
    }

Quotas: entry 100 + exit 50 + filter 80 + risk 30 + cross_channel 40 = 300.

Usage:
    python -m bwe_autoresearch.hypothesis_registry_seed
    # or
    python -m bwe_autoresearch.hypothesis_registry_seed --validate-only
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bwe_autoresearch.bwe_paths import REGISTRY_JSONL as OUTPUT_PATH  # noqa: E402

# ---------------------------------------------------------------------------
# Type alias for compactness
# Each tuple: (archetype_slug, channel, side, novel_dim_list, notes)
# ---------------------------------------------------------------------------

Entry = tuple[str, str, str, list[str], str]


def _to_dict(prefix: str, idx: int, type_name: str, t: Entry) -> dict:
    archetype, channel, side, novel_dim, notes = t
    return {
        "id": f"{prefix}{idx:03d}",
        "type": type_name,
        "archetype": archetype,
        "channel": channel,
        "side": side,
        "novel_dim": novel_dim,
        "expected_distinct": True,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# ENTRIES (100): 35 OI_Price + 35 pricechange + 20 Reserved6 + 10 cross-channel
# ---------------------------------------------------------------------------

ENTRIES: list[Entry] = [
    # -- OI_Price channel (35) --
    ("oi_overcrowded_continuation_short", "OI_Price", "short",
     ["oi_change_pct>=15", "price_5m_neg"],
     "OI rises sharply while price falls — pile onto liquidation cascade."),
    ("oi_overcrowded_reversal_short", "OI_Price", "short",
     ["oi_change_pct>=15", "price_5m_pos"],
     "OI spike during pump = late longs trapped; fade the rally."),
    ("oi_dropping_squeeze_long", "OI_Price", "long",
     ["oi_change_pct<=-10", "price_5m_pos"],
     "OI drops while price rises = shorts capitulating, ride the squeeze."),
    ("oi_dropping_capitulation_short", "OI_Price", "short",
     ["oi_change_pct<=-10", "price_5m_neg"],
     "OI drops with price = liquidation continuation, short with the flow."),
    ("oi_funding_blowoff_short", "OI_Price", "short",
     ["oi_change_pct>=10", "funding_abs>=0.05pct"],
     "OI spike + extreme funding = blow-off top, fade short."),
    ("oi_funding_divergence_long", "OI_Price", "long",
     ["oi_change_pct>=8", "funding_neg"],
     "OI rising with negative funding = real buying interest under pressure."),
    ("oi_low_vol_fakeout_short", "OI_Price", "short",
     ["oi_change_pct>=10", "volume_pct_below_p25"],
     "OI rises without volume confirmation = fake breakout, fade."),
    ("oi_pump_immediate_short", "OI_Price", "short",
     ["delay_seconds=0"],
     "Immediate fade on OI pump signal."),
    ("oi_pump_delayed_30s_short", "OI_Price", "short",
     ["delay_seconds=30"],
     "Wait 30s for confirmation, then fade OI pump."),
    ("oi_pump_delayed_1m_short", "OI_Price", "short",
     ["delay_seconds=60"],
     "1-minute delay before fading OI pump."),
    ("oi_pump_pretrend_aligned_long", "OI_Price", "long",
     ["pretrend_5m_pos", "oi_change_pct>=8"],
     "OI pump aligned with 5m uptrend = momentum continuation."),
    ("oi_pump_counter_pretrend_short", "OI_Price", "short",
     ["pretrend_5m_neg", "oi_change_pct>=8"],
     "OI pump against 5m downtrend = trap, fade short."),
    ("oi_crash_immediate_short_cont", "OI_Price", "short",
     ["delay_seconds=0", "oi_change_pct<=-8"],
     "Immediate continuation short on OI crash."),
    ("oi_crash_delayed_30s_long", "OI_Price", "long",
     ["delay_seconds=30", "oi_change_pct<=-8"],
     "Wait 30s post-crash for contrarian bounce long."),
    ("oi_crash_pretrend_aligned_short", "OI_Price", "short",
     ["pretrend_5m_neg", "oi_change_pct<=-8"],
     "OI crash + downtrend = strong continuation."),
    ("oi_crash_oversold_long", "OI_Price", "long",
     ["pretrend_30m_pct<=-10", "oi_change_pct<=-12"],
     "Extreme oversold + OI capitulation = bounce setup."),
    ("oi_pump_high_premium_short", "OI_Price", "short",
     ["oi_change_pct>=10", "premium_bps>=20"],
     "OI pump with premium spike = overheated, fade."),
    ("oi_pump_low_premium_long", "OI_Price", "long",
     ["oi_change_pct>=8", "premium_bps_in_-5_5"],
     "OI pump with normal premium = healthy momentum."),
    ("oi_crash_high_funding_long", "OI_Price", "long",
     ["oi_change_pct<=-8", "funding>=0.02pct"],
     "OI crash but funding still positive = quick rebound likely."),
    ("oi_crash_negative_funding_short", "OI_Price", "short",
     ["oi_change_pct<=-8", "funding<=-0.05pct"],
     "OI crash + deeply negative funding = liquidation cascade."),
    ("oi_pump_btc_bull_long", "OI_Price", "long",
     ["oi_change_pct>=8", "btc_24h_pct>=0"],
     "OI pump in BTC bullish regime = ride momentum."),
    ("oi_pump_btc_bear_short", "OI_Price", "short",
     ["oi_change_pct>=8", "btc_24h_pct<=-1"],
     "OI pump in BTC bearish regime = fade weak rally."),
    ("oi_change_diverge_taker_long", "OI_Price", "long",
     ["oi_change_pct>=5", "taker_buy_ratio_5m>=0.55"],
     "OI rising with taker buy dominance = real demand."),
    ("oi_change_diverge_taker_short", "OI_Price", "short",
     ["oi_change_pct>=5", "taker_buy_ratio_5m<=0.45"],
     "OI rising but taker selling = distribution, fade."),
    ("oi_pump_low_liquidity_avoid", "OI_Price", "both",
     ["liquidity_bucket=low"],
     "Test arch: low-liquidity OI pumps as no-trade signal (filter validation)."),
    ("oi_pump_burst_3plus_short", "OI_Price", "short",
     ["burst_count_5m>=3", "oi_change_pct>=5"],
     "3rd+ OI signal in 5min = exhaustion, fade short."),
    ("oi_pump_first_signal_long", "OI_Price", "long",
     ["burst_count_5m=1", "oi_change_pct>=8"],
     "Only 1st OI signal in window = clean setup, ride momentum."),
    ("oi_pump_volume_confirmed_long", "OI_Price", "long",
     ["oi_change_pct>=8", "volume_pct_above_p75"],
     "OI pump + volume confirmation = real move."),
    ("oi_pump_volume_low_short", "OI_Price", "short",
     ["oi_change_pct>=8", "volume_pct_below_p25"],
     "OI pump without volume = thin market manipulation, fade."),
    ("oi_pump_persistent_oi_long", "OI_Price", "long",
     ["oi_change_pct>=8", "oi_continues_rising_60s"],
     "OI keeps building post-signal = sustained interest."),
    ("oi_crash_oi_recovers_long", "OI_Price", "long",
     ["oi_change_pct<=-8", "oi_recovers_within_60s"],
     "OI bounces back quickly = false alarm, long the recovery."),
    ("oi_pump_top_trader_short_long", "OI_Price", "long",
     ["oi_change_pct>=8", "top_trader_position_ratio_dec"],
     "Smart money shorting into OI pump = squeeze setup, contrarian long."),
    ("oi_pump_top_trader_long_short", "OI_Price", "short",
     ["oi_change_pct>=8", "top_trader_position_ratio_high"],
     "Smart money already long = retail FOMO, fade."),
    ("oi_pump_global_short_ratio_long", "OI_Price", "long",
     ["oi_change_pct>=8", "global_short_ratio_high"],
     "High global short ratio + OI pump = squeeze, long."),
    ("oi_pump_global_long_ratio_short", "OI_Price", "short",
     ["oi_change_pct>=8", "global_long_ratio_extreme"],
     "Extreme global long ratio + OI pump = top, fade."),

    # -- pricechange channel (35) --
    ("pc_first_signal_immediate_long", "pricechange", "long",
     ["delay_seconds=0", "burst_count_5m=1", "side_signal=pump"],
     "Single pump signal = immediate momentum entry."),
    ("pc_first_signal_immediate_short", "pricechange", "short",
     ["delay_seconds=0", "burst_count_5m=1", "side_signal=crash"],
     "Single crash signal = immediate continuation short."),
    ("pc_first_signal_30s_long", "pricechange", "long",
     ["delay_seconds=30", "burst_count_5m=1"],
     "Wait 30s post-pump for confirmation, then long."),
    ("pc_first_signal_1m_long", "pricechange", "long",
     ["delay_seconds=60", "burst_count_5m=1"],
     "1-minute delay before long entry."),
    ("pc_first_signal_3m_long", "pricechange", "long",
     ["delay_seconds=180"],
     "3-minute delayed entry = slow follower."),
    ("pc_second_signal_cont_long", "pricechange", "long",
     ["burst_count_5m=2", "side_signal=pump"],
     "2nd same-direction pump in 5min = confirmed momentum."),
    ("pc_second_signal_cont_short", "pricechange", "short",
     ["burst_count_5m=2", "side_signal=crash"],
     "2nd same-direction crash = confirmed downside."),
    ("pc_second_signal_reversal_short", "pricechange", "short",
     ["burst_count_5m=2", "side_change=true"],
     "2nd opposite-direction signal = mean reversion likely."),
    ("pc_third_plus_overheat_short", "pricechange", "short",
     ["burst_count_5m>=3", "side_signal=pump"],
     "3rd+ pump in 5min = exhaustion, fade short."),
    ("pc_third_plus_high_vol_short", "pricechange", "short",
     ["burst_count_5m>=3", "volume_pct_above_p90"],
     "3rd+ with extreme volume = blow-off climax."),
    ("pc_burst_seq_4plus_avoid", "pricechange", "both",
     ["burst_count_5m>=4"],
     "Test arch: 4+ burst as no-trade signal (overcrowded)."),
    ("pc_pretrend_aligned_long", "pricechange", "long",
     ["pretrend_5m_pos", "side_signal=pump"],
     "Pump signal aligned with 5m uptrend = momentum."),
    ("pc_pretrend_aligned_short", "pricechange", "short",
     ["pretrend_5m_neg", "side_signal=crash"],
     "Crash signal + 5m downtrend = continuation."),
    ("pc_pretrend_against_long", "pricechange", "long",
     ["pretrend_5m_pos", "side_signal=crash"],
     "Crash signal in uptrend = buy the dip."),
    ("pc_pretrend_against_short", "pricechange", "short",
     ["pretrend_5m_neg", "side_signal=pump"],
     "Pump signal in downtrend = sell the rally."),
    ("pc_high_liquidity_long", "pricechange", "long",
     ["liquidity_bucket=high", "side_signal=pump"],
     "Pump in high-liquidity symbols only = quality setup."),
    ("pc_low_liquidity_avoid", "pricechange", "both",
     ["liquidity_bucket=low"],
     "Test arch: low-liquidity pump = avoid (validation)."),
    ("pc_btc_correlated_long", "pricechange", "long",
     ["btc_correlation_30d>=0.6", "side_signal=pump"],
     "Pump in high BTC-correlated symbol = beta play."),
    ("pc_low_btc_correl_long", "pricechange", "long",
     ["btc_correlation_30d<=0.3", "side_signal=pump"],
     "Pump in idiosyncratic symbol = real fundamental move."),
    ("pc_short_event_hold_1m_long", "pricechange", "long",
     ["fixed_hold_minutes=1"],
     "Pump → 1-min fixed hold long (event-bounded)."),
    ("pc_short_event_hold_3m_long", "pricechange", "long",
     ["fixed_hold_minutes=3"],
     "3-min fixed hold."),
    ("pc_pump_low_premium_long", "pricechange", "long",
     ["side_signal=pump", "premium_bps_in_-5_5"],
     "Pump with normal premium = sustainable."),
    ("pc_pump_high_premium_short", "pricechange", "short",
     ["side_signal=pump", "premium_bps>=15"],
     "Pump + premium spike = overheated, fade."),
    ("pc_crash_low_premium_short", "pricechange", "short",
     ["side_signal=crash", "premium_bps_in_-5_5"],
     "Crash with normal premium = real selling, continue short."),
    ("pc_crash_high_funding_long", "pricechange", "long",
     ["side_signal=crash", "funding>=0.02pct"],
     "Crash but funding positive = quick bounce setup."),
    ("pc_crash_negative_funding_short", "pricechange", "short",
     ["side_signal=crash", "funding<=-0.05pct"],
     "Crash + deeply negative funding = cascade short."),
    ("pc_pump_oi_rising_long", "pricechange", "long",
     ["side_signal=pump", "oi_change_5m_pos"],
     "Pump + OI rising = real demand."),
    ("pc_pump_oi_falling_short", "pricechange", "short",
     ["side_signal=pump", "oi_change_5m_neg"],
     "Pump + OI falling = short squeeze done, fade."),
    ("pc_pump_taker_buy_dominant_long", "pricechange", "long",
     ["side_signal=pump", "taker_buy_ratio_5m>=0.6"],
     "Pump + aggressive buyers = momentum."),
    ("pc_pump_taker_sell_short", "pricechange", "short",
     ["side_signal=pump", "taker_buy_ratio_5m<=0.4"],
     "Pump but takers selling = distribution."),
    ("pc_crash_taker_buy_long", "pricechange", "long",
     ["side_signal=crash", "taker_buy_ratio_5m>=0.55"],
     "Crash + takers buying = bottom forming."),
    ("pc_pump_btc_bull_long", "pricechange", "long",
     ["side_signal=pump", "btc_24h_pct>=0"],
     "Pump in BTC bull day = ride beta."),
    ("pc_pump_btc_bear_short", "pricechange", "short",
     ["side_signal=pump", "btc_24h_pct<=-1"],
     "Pump in BTC bear day = fade weakness."),
    ("pc_pump_market_cap_small_long", "pricechange", "long",
     ["side_signal=pump", "market_cap_bucket=small"],
     "Pump in small-cap = high beta momentum."),
    ("pc_pump_market_cap_large_long", "pricechange", "long",
     ["side_signal=pump", "market_cap_bucket=large"],
     "Pump in large-cap = more reliable signal."),

    # -- Reserved6 channel (20) --
    ("r6_bigmove_pump_immediate_short", "Reserved6", "short",
     ["delay_seconds=0", "side_event=pump"],
     "R6 big-move pump = immediate fade (overcooked)."),
    ("r6_bigmove_pump_30s_short", "Reserved6", "short",
     ["delay_seconds=30", "side_event=pump"],
     "Wait 30s, then fade R6 pump."),
    ("r6_bigmove_pump_1m_short", "Reserved6", "short",
     ["delay_seconds=60", "side_event=pump"],
     "1-min delay for clearer fade entry."),
    ("r6_bigmove_crash_immediate_short_cont", "Reserved6", "short",
     ["delay_seconds=0", "side_event=crash"],
     "R6 big crash = immediate continuation short."),
    ("r6_bigmove_crash_30s_long", "Reserved6", "long",
     ["delay_seconds=30", "side_event=crash"],
     "30s post-crash bounce long."),
    ("r6_bigmove_crash_1m_long", "Reserved6", "long",
     ["delay_seconds=60", "side_event=crash"],
     "1-min bounce timing."),
    ("r6_pump_btc_bull_long", "Reserved6", "long",
     ["side_event=pump", "btc_24h_pct>=0"],
     "R6 pump in BTC bull = ride momentum (counter-default)."),
    ("r6_pump_btc_bear_short", "Reserved6", "short",
     ["side_event=pump", "btc_24h_pct<=-1"],
     "R6 pump in BTC bear = fade weak."),
    ("r6_crash_oversold_long", "Reserved6", "long",
     ["side_event=crash", "pretrend_30m_pct<=-15"],
     "Extreme crash + already oversold = mean reversion long."),
    ("r6_pump_oi_confirms_long", "Reserved6", "long",
     ["side_event=pump", "oi_change_5m_pos"],
     "R6 pump + OI rising = real demand."),
    ("r6_pump_oi_rejects_short", "Reserved6", "short",
     ["side_event=pump", "oi_change_5m_neg"],
     "R6 pump + OI falling = short squeeze done."),
    ("r6_pump_taker_buy_long", "Reserved6", "long",
     ["side_event=pump", "taker_buy_ratio_5m>=0.6"],
     "R6 + aggressive taker buying = real."),
    ("r6_pump_low_liq_avoid", "Reserved6", "both",
     ["liquidity_bucket=low"],
     "Test arch: R6 low-liq = avoid."),
    ("r6_pump_high_liq_long", "Reserved6", "long",
     ["liquidity_bucket=high", "side_event=pump"],
     "R6 in high liq = ride momentum."),
    ("r6_pump_premium_extreme_short", "Reserved6", "short",
     ["side_event=pump", "premium_bps>=50"],
     "R6 + extreme premium = overcooked, fade."),
    ("r6_pump_funding_extreme_short", "Reserved6", "short",
     ["side_event=pump", "funding_abs>=0.1pct"],
     "R6 + extreme funding = blowoff."),
    ("r6_first_in_2h_long", "Reserved6", "long",
     ["r6_signals_in_2h=1", "side_event=pump"],
     "Only first R6 in 2h = clean setup."),
    ("r6_after_pricechange_short", "Reserved6", "short",
     ["pc_signal_within_5m_before"],
     "R6 right after pricechange burst = exhaustion fade."),
    ("r6_after_oi_long", "Reserved6", "long",
     ["oi_signal_within_5m_before", "side_event=pump"],
     "R6 follows OI signal = chained confirmation."),
    ("r6_short_event_hold_5m", "Reserved6", "short",
     ["fixed_hold_minutes=5", "side_event=pump"],
     "R6 pump → 5-min fixed hold short."),

    # -- Cross-channel as primary entries (10) --
    ("cc_pc_then_oi_5m_long", "*", "long",
     ["pc_signal_then_oi_within_5m", "side_signal=pump"],
     "PC pump then OI confirms in 5m = strong long."),
    ("cc_oi_then_pc_5m_long", "*", "long",
     ["oi_signal_then_pc_within_5m", "side_signal=pump"],
     "OI signal then PC confirms = chained pump."),
    ("cc_r6_after_burst_short", "*", "short",
     ["r6_after_pc_burst_3plus"],
     "R6 right after PC burst exhaustion = fade short."),
    ("cc_oi_pc_simultaneous_long", "*", "long",
     ["oi_and_pc_within_60s", "side_signal=pump"],
     "OI + PC fire same minute = strong simultaneous signal."),
    ("cc_three_channel_within_5m_long", "*", "long",
     ["all_three_channels_within_5m", "side_signal=pump"],
     "All 3 channels fire in 5m window = max conviction."),
    ("cc_pc_oi_diverge_short", "*", "short",
     ["pc_pump_oi_falling_within_5m"],
     "PC pump but OI falls = fake breakout, short."),
    ("cc_oi_r6_align_short", "*", "short",
     ["oi_and_r6_within_5m", "side_event=crash"],
     "OI crash + R6 same direction = cascade short."),
    ("cc_pc_pump_no_oi_5m_short", "*", "short",
     ["pc_pump", "no_oi_signal_within_5m_after"],
     "PC pump without OI confirm in 5m = fake, fade."),
    ("cc_pc_crash_no_r6_long", "*", "long",
     ["pc_crash", "no_r6_within_5m"],
     "PC crash without R6 confirmation = noise, contrarian long."),
    ("cc_pc_then_oi_funding_align_long", "*", "long",
     ["pc_then_oi_within_5m", "funding_aligned"],
     "Chain confirmation with funding alignment = highest quality."),

    # === EXPANSION (Day 1, +100 to reach 200) ===
    # OI_Price extras (+25)
    ("oi_pump_taker_buy_extreme_long", "OI_Price", "long",
     ["oi_change_pct>=8", "taker_buy_ratio_5m>=0.7"],
     "OI pump + extreme taker buying = retail FOMO confirmed real."),
    ("oi_pump_taker_buy_extreme_short_pretrend_neg", "OI_Price", "short",
     ["oi_change_pct>=8", "taker_buy_ratio_5m>=0.7", "pretrend_5m_neg"],
     "OI + taker FOMO against downtrend = bull trap, fade."),
    ("oi_crash_basis_widening_short", "OI_Price", "short",
     ["oi_change_pct<=-8", "basis_widening"],
     "OI crash + basis widening = perp panic relative to spot."),
    ("oi_crash_basis_narrowing_long", "OI_Price", "long",
     ["oi_change_pct<=-8", "basis_narrowing"],
     "OI crash + basis narrowing = capitulation done, bounce."),
    ("oi_pump_2nd_signal_5m_short", "OI_Price", "short",
     ["burst_count_5m=2", "oi_change_pct>=8"],
     "2nd OI pump in 5min = late chasers, fade."),
    ("oi_pump_3rd_plus_avoid", "OI_Price", "both",
     ["burst_count_5m>=3"],
     "3rd+ OI signal = no-trade zone (overcrowded)."),
    ("oi_crash_btc_correlated_short", "OI_Price", "short",
     ["oi_change_pct<=-8", "btc_correlation_30d>=0.6"],
     "OI crash in high-BTC-correl symbol = ride beta down."),
    ("oi_crash_idiosyncratic_long", "OI_Price", "long",
     ["oi_change_pct<=-8", "btc_correlation_30d<=0.3"],
     "OI crash in idiosyncratic symbol = fundamental noise, contrarian."),
    ("oi_pump_high_premium_immediate_short", "OI_Price", "short",
     ["delay_seconds=0", "oi_change_pct>=8", "premium_bps>=20"],
     "Immediate fade on OI + premium spike."),
    ("oi_pump_high_premium_delayed_short", "OI_Price", "short",
     ["delay_seconds=60", "oi_change_pct>=8", "premium_bps>=20"],
     "1-min delay before fade on premium-confirmed OI pump."),
    ("oi_pump_funding_normalized_long", "OI_Price", "long",
     ["oi_change_pct>=8", "funding_in_-0.01_0.01"],
     "OI pump with normal funding = sustainable momentum."),
    ("oi_pump_funding_extreme_pos_short", "OI_Price", "short",
     ["oi_change_pct>=8", "funding>=0.1pct"],
     "OI + funding extreme positive = blowoff, fade."),
    ("oi_pump_funding_extreme_neg_long", "OI_Price", "long",
     ["oi_change_pct>=8", "funding<=-0.1pct"],
     "OI pump despite negative funding = real conviction long."),
    ("oi_change_mfi_oversold_long", "OI_Price", "long",
     ["oi_change_pct<=-8", "pretrend_30m_pct<=-15"],
     "OI capitulation + 30m oversold = mean reversion long."),
    ("oi_change_mfi_overbought_short", "OI_Price", "short",
     ["oi_change_pct>=8", "pretrend_30m_pct>=15"],
     "OI pump + 30m overbought = exhaustion fade."),
    ("oi_pump_session_us_long", "OI_Price", "long",
     ["oi_change_pct>=8", "session=US"],
     "OI pump in US session = institutional flow."),
    ("oi_pump_session_asia_short", "OI_Price", "short",
     ["oi_change_pct>=8", "session=Asian"],
     "OI pump in Asian session = retail-driven, fade."),
    ("oi_pump_weekend_short", "OI_Price", "short",
     ["oi_change_pct>=8", "weekday in [Sat,Sun]"],
     "OI pump on weekend = thin liquidity manipulation."),
    ("oi_pump_macro_event_avoid", "OI_Price", "both",
     ["near_macro_event"],
     "OI pump near Fed/CPI = avoid (unstable regime)."),
    ("oi_pump_2x_avg_volume_long", "OI_Price", "long",
     ["oi_change_pct>=8", "volume_2x_avg"],
     "OI + 2x avg volume = strong momentum."),
    ("oi_pump_5x_avg_volume_short", "OI_Price", "short",
     ["oi_change_pct>=8", "volume_5x_avg"],
     "OI + 5x volume = climax exhaustion."),
    ("oi_pump_volume_pct_ranked_long", "OI_Price", "long",
     ["oi_change_pct>=8", "volume_pct_top_decile"],
     "OI pump in top-decile volume hour."),
    ("oi_pump_oi_ranked_long", "OI_Price", "long",
     ["oi_change_pct>=8", "oi_pct_top_decile"],
     "OI pump in top-decile OI symbol = conviction."),
    ("oi_pump_funding_ranked_short", "OI_Price", "short",
     ["oi_change_pct>=8", "funding_pct_top_decile"],
     "OI + funding in top decile = overstretched."),
    ("oi_change_imbalanced_book_long", "OI_Price", "long",
     ["oi_change_pct>=5", "book_imbalance_bid_heavy"],
     "OI rising + bid-heavy book = real demand."),

    # PriceChange extras (+25)
    ("pc_pump_taker_buy_extreme_long", "pricechange", "long",
     ["side_signal=pump", "taker_buy_ratio_5m>=0.7"],
     "Pump + extreme taker buying = momentum confirmed."),
    ("pc_pump_taker_buy_extreme_against_pretrend_short", "pricechange", "short",
     ["side_signal=pump", "taker_buy_ratio_5m>=0.7", "pretrend_5m_neg"],
     "Taker FOMO against downtrend = bull trap."),
    ("pc_pump_basis_diverge_short", "pricechange", "short",
     ["side_signal=pump", "basis_widening"],
     "Pump + basis widening = perp leading spot, unsustainable."),
    ("pc_pump_basis_align_long", "pricechange", "long",
     ["side_signal=pump", "basis_narrowing"],
     "Pump + basis narrowing = healthy convergence."),
    ("pc_pump_2nd_within_30s_overheated_short", "pricechange", "short",
     ["burst_count_5m=2", "burst_density_30s=2"],
     "Two pumps within 30s = blow-off, fade."),
    ("pc_pump_4th_or_more_avoid", "pricechange", "both",
     ["burst_count_5m>=4"],
     "4th+ signal in burst = no-trade (saturation)."),
    ("pc_pump_btc_extreme_correlated_long", "pricechange", "long",
     ["side_signal=pump", "btc_correlation_30d>=0.8"],
     "Pump in extreme-BTC-correl symbol = pure beta play."),
    ("pc_pump_btc_no_correlation_long", "pricechange", "long",
     ["side_signal=pump", "btc_correlation_30d<=0.1"],
     "Pump in zero-correl symbol = idiosyncratic event."),
    ("pc_pump_premium_extreme_immediate_short", "pricechange", "short",
     ["delay_seconds=0", "side_signal=pump", "premium_bps>=30"],
     "Immediate fade on extreme premium pump."),
    ("pc_pump_premium_extreme_delayed_short", "pricechange", "short",
     ["delay_seconds=60", "side_signal=pump", "premium_bps>=30"],
     "1-min delayed fade on premium pump."),
    ("pc_pump_funding_resetting_long", "pricechange", "long",
     ["side_signal=pump", "funding_just_reset"],
     "Pump right after funding settlement = clean slate."),
    ("pc_pump_funding_extreme_pos_short", "pricechange", "short",
     ["side_signal=pump", "funding>=0.1pct"],
     "Pump + funding extreme positive = top setup."),
    ("pc_pump_funding_extreme_neg_long", "pricechange", "long",
     ["side_signal=pump", "funding<=-0.1pct"],
     "Pump despite negative funding = strong buyers."),
    ("pc_pump_volume_5x_baseline_long", "pricechange", "long",
     ["side_signal=pump", "volume_5x_baseline"],
     "Pump with 5x baseline volume = real."),
    ("pc_pump_volume_below_baseline_short", "pricechange", "short",
     ["side_signal=pump", "volume_below_baseline"],
     "Pump on low volume = paint, fade."),
    ("pc_pump_session_us_long", "pricechange", "long",
     ["side_signal=pump", "session=US"],
     "Pump in US session."),
    ("pc_pump_session_asia_short", "pricechange", "short",
     ["side_signal=pump", "session=Asian"],
     "Pump in Asian session = retail manipulation."),
    ("pc_pump_weekend_short", "pricechange", "short",
     ["side_signal=pump", "weekday in [Sat,Sun]"],
     "Weekend pump = thin liquidity, fade."),
    ("pc_pump_macro_event_avoid", "pricechange", "both",
     ["near_macro_event"],
     "Pump near macro event = avoid."),
    ("pc_pump_top_trader_long_short", "pricechange", "short",
     ["side_signal=pump", "top_trader_position_ratio_high"],
     "Smart money already long during pump = retail FOMO, fade."),
    ("pc_pump_top_trader_short_long", "pricechange", "long",
     ["side_signal=pump", "top_trader_position_ratio_dec"],
     "Smart money shorting into pump = squeeze setup."),
    ("pc_pump_global_long_high_short", "pricechange", "short",
     ["side_signal=pump", "global_long_ratio_high"],
     "Pump + global long ratio extreme = top."),
    ("pc_pump_global_short_high_long", "pricechange", "long",
     ["side_signal=pump", "global_short_ratio_high"],
     "Pump + high short ratio = squeeze setup."),
    ("pc_pump_aggressive_buy_immediate_long", "pricechange", "long",
     ["side_signal=pump", "aggressive_buy_5m"],
     "Pump + aggressive buy taker flow = momentum."),
    ("pc_pump_aggressive_sell_short", "pricechange", "short",
     ["side_signal=pump", "aggressive_sell_5m"],
     "Pump but aggressive sells = distribution, fade."),

    # Reserved6 extras (+15)
    ("r6_pump_2nd_in_2h_short", "Reserved6", "short",
     ["r6_signals_in_2h=2"],
     "2nd R6 in 2h = exhaustion, fade."),
    ("r6_pump_3rd_or_more_avoid", "Reserved6", "both",
     ["r6_signals_in_2h>=3"],
     "3rd+ R6 in 2h = unstable regime, avoid."),
    ("r6_pump_taker_extreme_short", "Reserved6", "short",
     ["side_event=pump", "taker_buy_ratio_5m>=0.75"],
     "R6 + extreme taker buy = euphoria, fade."),
    ("r6_pump_funding_extreme_pos_short", "Reserved6", "short",
     ["side_event=pump", "funding>=0.1pct"],
     "R6 + funding extreme pos = blowoff."),
    ("r6_pump_funding_extreme_neg_long", "Reserved6", "long",
     ["side_event=pump", "funding<=-0.1pct"],
     "R6 pump despite extreme negative funding = strong long."),
    ("r6_pump_basis_diverge_short", "Reserved6", "short",
     ["side_event=pump", "basis_widening"],
     "R6 + basis widening = perp euphoria."),
    ("r6_pump_basis_align_long", "Reserved6", "long",
     ["side_event=pump", "basis_narrowing"],
     "R6 + basis narrowing = healthy."),
    ("r6_pump_top_trader_long_short", "Reserved6", "short",
     ["side_event=pump", "top_trader_position_ratio_high"],
     "R6 + smart money already long = retail-driven."),
    ("r6_pump_global_long_extreme_short", "Reserved6", "short",
     ["side_event=pump", "global_long_ratio_extreme"],
     "R6 + extreme global long = top."),
    ("r6_pump_global_short_extreme_long", "Reserved6", "long",
     ["side_event=pump", "global_short_ratio_extreme"],
     "R6 + extreme global short = squeeze long."),
    ("r6_pump_session_us_long", "Reserved6", "long",
     ["side_event=pump", "session=US"],
     "R6 in US session = institutional."),
    ("r6_pump_session_asia_short", "Reserved6", "short",
     ["side_event=pump", "session=Asian"],
     "R6 in Asian session = retail, fade."),
    ("r6_pump_weekend_short", "Reserved6", "short",
     ["side_event=pump", "weekday in [Sat,Sun]"],
     "R6 on weekend = thin liq."),
    ("r6_pump_macro_event_avoid", "Reserved6", "both",
     ["near_macro_event"],
     "R6 near macro event = avoid unstable."),
    ("r6_pump_pretrend_extreme_short", "Reserved6", "short",
     ["side_event=pump", "pretrend_30m_pct>=20"],
     "R6 pump on already-overheated symbol = fade."),

    # Cross-channel as primary entries (+35)
    ("cc_pc_pump_oi_pump_5m_strong_long", "*", "long",
     ["pc_and_oi_pump_within_5m"],
     "PC pump + OI pump within 5m = double confirmation long."),
    ("cc_pc_crash_oi_crash_5m_strong_short", "*", "short",
     ["pc_and_oi_crash_within_5m"],
     "PC crash + OI crash = double confirmation short."),
    ("cc_pc_oi_misaligned_short", "*", "short",
     ["pc_pump_oi_crash_within_5m"],
     "PC pump but OI crashes = fake breakout."),
    ("cc_pc_pump_then_oi_crash_3m_short", "*", "short",
     ["pc_pump_then_oi_crash_3m"],
     "PC pump → OI crash 3m later = sellers using pump."),
    ("cc_oi_then_pc_30s_immediate_long", "*", "long",
     ["oi_then_pc_within_30s"],
     "OI signal → PC confirms in 30s = fast chain."),
    ("cc_oi_then_pc_2m_long", "*", "long",
     ["oi_then_pc_within_2m"],
     "OI → PC in 2min window."),
    ("cc_oi_then_pc_5m_funding_align_long", "*", "long",
     ["oi_then_pc_within_5m", "funding_aligned"],
     "OI → PC chain + funding aligned = highest quality."),
    ("cc_three_channel_2m_strong_long", "*", "long",
     ["all_three_channels_within_2m"],
     "All 3 channels in 2-min window = max conviction."),
    ("cc_three_channel_3m_strong_long", "*", "long",
     ["all_three_channels_within_3m"],
     "All 3 in 3-min."),
    ("cc_three_channel_pretrend_align_long", "*", "long",
     ["all_three_within_5m", "pretrend_aligned"],
     "Triple chain + pretrend aligned = highest weighted."),
    ("cc_pc_only_no_oi_5m_avoid", "*", "both",
     ["pc_no_oi_within_5m"],
     "PC alone without OI confirm = noise, no-trade."),
    ("cc_oi_only_no_pc_5m_long", "*", "long",
     ["oi_no_pc_within_5m"],
     "OI alone without PC = institutional positioning, follow."),
    ("cc_r6_after_oi_pump_long", "*", "long",
     ["r6_after_oi_pump_within_5m"],
     "R6 follows OI pump = chained momentum long."),
    ("cc_r6_after_pc_pump_short", "*", "short",
     ["r6_after_pc_pump_within_5m"],
     "R6 follows PC burst = exhaustion fade."),
    ("cc_pc_oi_taker_align_long", "*", "long",
     ["pc_oi_taker_aligned"],
     "PC + OI + taker flow all aligned = high conviction."),
    ("cc_pc_oi_premium_diverge_short", "*", "short",
     ["pc_oi_premium_diverge"],
     "PC pump + OI pump but premium against = unstable."),
    ("cc_pc_oi_funding_align_long", "*", "long",
     ["pc_oi_funding_align"],
     "PC + OI + funding all aligned = quality."),
    ("cc_pc_then_oi_burst_avoid", "*", "both",
     ["pc_then_oi_in_burst"],
     "PC + OI both in 5+ burst = chaos, no trade."),
    ("cc_oi_with_pc_burst_avoid", "*", "both",
     ["oi_in_pc_burst"],
     "OI fires within PC burst window = saturation, avoid."),
    ("cc_three_channel_30s_window_long", "*", "long",
     ["all_three_within_30s"],
     "Triple chain in 30s window = explosive setup."),
    ("cc_three_channel_60s_window_long", "*", "long",
     ["all_three_within_60s"],
     "Triple chain in 60s."),
    ("cc_pc_oi_basis_align_long", "*", "long",
     ["pc_oi_basis_align"],
     "PC + OI + basis convergence."),
    ("cc_pc_oi_basis_diverge_short", "*", "short",
     ["pc_oi_basis_diverge"],
     "PC + OI but basis widening = unsustainable."),
    ("cc_pc_to_r6_chain_short", "*", "short",
     ["pc_then_r6_within_5m"],
     "PC then R6 within 5m = exhaustion."),
    ("cc_oi_to_r6_chain_short", "*", "short",
     ["oi_then_r6_within_5m"],
     "OI then R6 within 5m = blowoff."),
    ("cc_pc_burst_3plus_then_oi_short", "*", "short",
     ["pc_burst_3plus_then_oi"],
     "PC burst exhaustion + OI confirms = fade."),
    ("cc_oi_3plus_then_pc_short", "*", "short",
     ["oi_3plus_then_pc"],
     "OI burst exhaustion + PC = fade."),
    ("cc_pc_oi_top_trader_align_long", "*", "long",
     ["pc_oi_top_trader_aligned"],
     "PC + OI + smart money aligned = top quality."),
    ("cc_pc_oi_global_short_extreme_long", "*", "long",
     ["pc_oi_global_short_extreme"],
     "PC + OI + extreme global short = squeeze."),
    ("cc_pc_oi_global_long_extreme_short", "*", "short",
     ["pc_oi_global_long_extreme"],
     "PC + OI + extreme global long = top."),
    ("cc_pc_btc_align_oi_align_long", "*", "long",
     ["pc_btc_align", "oi_btc_align"],
     "PC + OI + BTC alignment = beta + signal."),
    ("cc_pc_btc_diverge_oi_align_short", "*", "short",
     ["pc_btc_diverge", "oi_btc_align"],
     "PC against BTC + OI confirms = idiosyncratic short."),
    ("cc_pc_oi_session_us_long", "*", "long",
     ["pc_oi_session=US"],
     "PC + OI in US session = institutional flow."),
    ("cc_pc_oi_session_asia_short", "*", "short",
     ["pc_oi_session=Asian"],
     "PC + OI in Asian session = fade retail."),
    ("cc_pc_oi_weekend_short", "*", "short",
     ["pc_oi_weekday in [Sat,Sun]"],
     "PC + OI on weekend = thin manipulation."),
]

# ---------------------------------------------------------------------------
# EXITS (50)
# ---------------------------------------------------------------------------

EXITS: list[Entry] = [
    # fixed_tp_sl (5)
    ("fixed_tp1_sl1_symmetric", "NA", "NA", ["tp_pct=1", "sl_pct=1"], "1:1 risk:reward symmetric exit."),
    ("fixed_tp2_sl1_aggressive", "NA", "NA", ["tp_pct=2", "sl_pct=1"], "2:1 R:R aggressive."),
    ("fixed_tp3_sl1_runner", "NA", "NA", ["tp_pct=3", "sl_pct=1"], "3:1 R:R for swing trades."),
    ("fixed_tp1_sl2_conservative", "NA", "NA", ["tp_pct=1", "sl_pct=2"], "Tight TP, wide SL — high win rate."),
    ("fixed_tp1_5_sl1_default", "NA", "NA", ["tp_pct=1.5", "sl_pct=1"], "1.5:1 default exit."),

    # multi_tp_sl (5)
    ("multi_tp_50at1_50at2_sl1", "NA", "NA", ["tp1=1pct@50pct", "tp2=2pct@50pct", "sl=1pct"], "50% off at 1R, 50% at 2R."),
    ("multi_tp_33_33_33_at_1_2_3", "NA", "NA", ["3_equal_levels_1_2_3pct"], "Equal thirds at 1/2/3R."),
    ("multi_tp_25_25_50_back_loaded", "NA", "NA", ["25pct@1", "25pct@2", "50pct@3"], "Back-loaded scale-out for runners."),
    ("multi_tp_50at1_5_50at3_wide", "NA", "NA", ["tp1=1.5pct@50pct", "tp2=3pct@50pct"], "Wide spread between TP1/TP2."),
    ("multi_tp_first_be_runner", "NA", "NA", ["tp1@1", "rest_be_runner"], "TP1 then move SL to BE for rest."),

    # partial_ladder (6)
    ("ladder_5_steps_pct", "NA", "NA", ["5_equal_pct_steps"], "5 equal pct ladder."),
    ("ladder_3_steps_atr", "NA", "NA", ["3_atr_based_steps"], "3 ATR-based ladder steps."),
    ("ladder_fibonacci", "NA", "NA", ["fib_levels_618_1_1618_2618"], "Fibonacci-based exit ladder."),
    ("ladder_volume_weighted", "NA", "NA", ["vol_profile_levels"], "Exit at volume profile node."),
    ("ladder_decay", "NA", "NA", ["faster_exit_with_time"], "Exit accelerates with hold time."),
    ("ladder_tight_then_wide", "NA", "NA", ["tight_first_2_then_wide_3"], "Tight early, wide late."),

    # trailing_stop (5)
    ("trail_atr_2", "NA", "NA", ["trail=2*ATR"], "2x ATR trailing stop."),
    ("trail_atr_3", "NA", "NA", ["trail=3*ATR"], "3x ATR trailing."),
    ("trail_pct_1", "NA", "NA", ["trail_pct=1"], "1% trailing stop."),
    ("trail_pct_2", "NA", "NA", ["trail_pct=2"], "2% trailing stop."),
    ("trail_chandelier", "NA", "NA", ["chandelier_3atr_22"], "Chandelier exit (3 ATR over 22-bar high/low)."),

    # runner_trail (5)
    ("runner_50pct_trail2atr", "NA", "NA", ["tp1=1pct@50pct", "trail_rest=2atr"], "50% off at 1R, trail rest 2x ATR."),
    ("runner_67pct_trail3atr", "NA", "NA", ["tp1=1pct@67pct", "trail_rest=3atr"], "67% off at 1R, trail rest 3x ATR."),
    ("runner_fixed_then_trail_pct", "NA", "NA", ["tp1=fixed_pct", "rest_trail_pct"], "Fixed TP1, then % trail."),
    ("runner_decay", "NA", "NA", ["runner_with_decay"], "Runner with time-decay tightening."),
    ("runner_premium_based", "NA", "NA", ["exit_when_premium_normalizes"], "Runner exits when premium normalizes."),

    # breakeven_ratchet (4)
    ("be_at_1r_then_hold", "NA", "NA", ["be_trigger=1R"], "Move SL to BE at 1R, then hold."),
    ("be_at_0_5r_then_hold", "NA", "NA", ["be_trigger=0.5R"], "Earlier BE at 0.5R."),
    ("be_at_1r_trail_atr", "NA", "NA", ["be_at_1R", "then_trail=2atr"], "BE at 1R, then ATR trail."),
    ("be_at_2r_runner", "NA", "NA", ["be_at_2R", "runner"], "Late BE at 2R, runner mode."),

    # indicator_invalidation (5)
    ("exit_on_oi_reversal", "NA", "NA", ["oi_change_dir_flips"], "Exit when OI direction reverses."),
    ("exit_on_pc_signal_opposite", "NA", "NA", ["pc_opposite_signal"], "Exit on opposite-side PC signal."),
    ("exit_on_funding_normalize", "NA", "NA", ["funding_back_to_zero"], "Exit when funding normalizes."),
    ("exit_on_premium_normalize", "NA", "NA", ["premium_back_to_normal"], "Exit when premium back to normal."),
    ("exit_on_volume_drop", "NA", "NA", ["volume_falls_below_50pct_entry"], "Exit when volume falls < 50% of entry."),

    # state_machine (5)
    ("sm_3state_proven_runner", "NA", "NA", ["state1_prove", "state2_trail", "state3_runner"], "3-state: prove → trail → runner."),
    ("sm_2state_quick_or_persist", "NA", "NA", ["fast_tp_else_persist"], "Quick TP if fast move, else persist."),
    ("sm_event_holdthen_assess", "NA", "NA", ["hold_to_event_then_assess"], "Hold for event window, then evaluate."),
    ("sm_pretrend_aware", "NA", "NA", ["exit_logic_varies_with_pretrend"], "Exit varies based on entry pretrend."),
    ("sm_regime_aware", "NA", "NA", ["exit_logic_varies_with_btc_regime"], "Exit varies with BTC regime."),

    # time_stop (5)
    ("time_1m_hard", "NA", "NA", ["hard_stop=60s"], "Hard 1-min hold."),
    ("time_3m_hard", "NA", "NA", ["hard_stop=180s"], "3-min hard stop."),
    ("time_5m_hard", "NA", "NA", ["hard_stop=300s"], "5-min hard stop."),
    ("time_10m_hard", "NA", "NA", ["hard_stop=600s"], "10-min hard stop."),
    ("time_15m_hard", "NA", "NA", ["hard_stop=900s"], "15-min hard stop."),

    # short_event_hold (5)
    ("event_hold_then_close", "NA", "NA", ["hold_T0_to_T0plus_event"], "Hold from T0 to T0+event window."),
    ("event_hold_with_bail", "NA", "NA", ["hold_unless_2pct_against"], "Hold but bail if >2% against."),
    ("event_hold_runner", "NA", "NA", ["hold_then_trail"], "Hold event window, then trail."),
    ("event_hold_then_be", "NA", "NA", ["hold_then_be_only"], "Hold then BE-only."),
    ("event_hold_2h_max", "NA", "NA", ["max_hold=2h"], "Extended 2h max event hold."),

    # === EXPANSION (+50 to reach 100) ===
    # Hybrid + adaptive
    ("fixed_tp_sl_with_be_after_breakout", "NA", "NA", ["fixed", "be_after_break"], "Fixed TP/SL but move SL to BE after price breaks key level."),
    ("fixed_tp_sl_dynamic_by_atr", "NA", "NA", ["tp/sl_scaled_by_atr"], "TP and SL distances scale with current ATR."),
    ("multi_tp_with_be_lock", "NA", "NA", ["multi_tp", "be_lock_after_tp1"], "After TP1, lock in BE for the runner."),
    ("multi_tp_with_decay", "NA", "NA", ["multi_tp_decay"], "TP levels decay closer over time."),
    ("multi_tp_with_volatility_adjust", "NA", "NA", ["vol_adj_tp"], "TP spacing adjusts to realized volatility."),
    ("partial_ladder_with_be", "NA", "NA", ["ladder", "be_after_step1"], "Partial ladder + BE after first step."),
    ("partial_ladder_with_runner", "NA", "NA", ["ladder", "runner_after_4_steps"], "Ladder 4 steps + runner."),
    ("partial_ladder_with_volatility", "NA", "NA", ["ladder_vol_adjust"], "Ladder spacing scales with vol."),
    ("trailing_with_acceleration", "NA", "NA", ["trail_accelerating"], "Trail tightens as profit grows."),
    ("trailing_with_decay", "NA", "NA", ["trail_loosens_with_time"], "Trail loosens with hold time."),
    ("runner_with_indicator_invalidation", "NA", "NA", ["runner", "exit_on_indicator"], "Runner exits when indicator invalidates."),
    ("runner_with_state_transition", "NA", "NA", ["runner_sm_transition"], "Runner transitions through 3 states."),
    ("breakeven_then_aggressive_trail", "NA", "NA", ["be_then_tight_trail"], "BE at 1R then 1*ATR tight trail."),
    ("breakeven_then_indicator", "NA", "NA", ["be_then_exit_on_indicator"], "BE then exit on indicator signal."),
    ("indicator_invalidation_oi_or_premium", "NA", "NA", ["exit_on_oi_or_premium"], "Exit if OI reverses OR premium normalizes."),
    ("indicator_invalidation_with_time_stop", "NA", "NA", ["indicator_or_time"], "Indicator OR time stop, whichever first."),
    ("state_machine_4state", "NA", "NA", ["sm_4state"], "4-state machine: enter→prove→trail→runner."),
    ("state_machine_5state", "NA", "NA", ["sm_5state"], "5-state with explicit exhaustion state."),
    ("state_machine_volatility_adaptive", "NA", "NA", ["sm_vol_adaptive"], "State transitions depend on volatility regime."),
    ("time_stop_30s", "NA", "NA", ["hard_stop=30s"], "30-second hard stop for ultra-short events."),
    ("time_stop_2m", "NA", "NA", ["hard_stop=120s"], "2-min hard stop."),
    ("time_stop_45m", "NA", "NA", ["hard_stop=2700s"], "45-min hard stop for slow developing trades."),
    ("event_hold_then_quick_be", "NA", "NA", ["event_then_be_only"], "Hold for event, then BE-only mode."),
    ("event_hold_extended_runner", "NA", "NA", ["event_then_runner"], "Hold for event, then runner mode."),
    ("adaptive_exit_pretrend_aware", "NA", "NA", ["adaptive_pretrend"], "Exit logic depends on entry pretrend strength."),
    ("adaptive_exit_regime_aware", "NA", "NA", ["adaptive_regime"], "Exit logic depends on BTC regime."),
    ("adaptive_exit_burst_aware", "NA", "NA", ["adaptive_burst"], "Exit logic depends on burst count at entry."),
    ("adaptive_exit_funding_aware", "NA", "NA", ["adaptive_funding"], "Exit logic depends on funding state."),
    ("exit_on_volume_spike", "NA", "NA", ["exit_volume_spike_5x"], "Exit when volume spikes 5x baseline (climax)."),
    ("exit_on_funding_flip", "NA", "NA", ["exit_funding_sign_change"], "Exit when funding flips sign."),
    ("exit_on_premium_spike", "NA", "NA", ["exit_premium_spike"], "Exit when premium spikes beyond entry threshold."),
    ("exit_on_global_short_change", "NA", "NA", ["exit_global_short_dec"], "Exit when global short ratio normalizes (squeeze done)."),
    ("exit_on_top_trader_change", "NA", "NA", ["exit_top_trader_position_change"], "Exit when smart money position changes direction."),
    ("exit_on_basis_invert", "NA", "NA", ["exit_basis_invert"], "Exit when basis inverts."),
    ("exit_on_oi_decel", "NA", "NA", ["exit_oi_deceleration"], "Exit when OI rate of change decelerates."),
    ("exit_on_burst_3rd", "NA", "NA", ["exit_on_burst_count=3"], "Exit when 3rd burst signal triggers (saturation)."),
    ("exit_pre_funding_settlement", "NA", "NA", ["exit_30s_pre_funding"], "Exit 30s before funding settlement."),
    ("exit_pre_macro_event", "NA", "NA", ["exit_60s_pre_macro_event"], "Exit 60s before known macro event."),
    ("runner_decay_to_be", "NA", "NA", ["runner_decays_to_be"], "Runner gradually decays to BE."),
    ("runner_with_2tp_levels", "NA", "NA", ["runner_2_tps"], "Runner with 2 TP levels."),
    ("runner_with_3tp_levels", "NA", "NA", ["runner_3_tps"], "Runner with 3 TP levels."),
    ("partial_ladder_5tp_decay", "NA", "NA", ["ladder_5_tp_decay"], "5 TPs that decay tighter over time."),
    ("multi_tp_with_partial_runner", "NA", "NA", ["multi_tp_partial_runner"], "Multi TP + partial runner mode."),
    ("state_machine_oi_aware", "NA", "NA", ["sm_oi_aware"], "State machine watches OI changes for transitions."),
    ("state_machine_pretrend_aware_v2", "NA", "NA", ["sm_pretrend_v2"], "State machine v2 with pretrend awareness."),
    ("state_machine_funding_aware", "NA", "NA", ["sm_funding_aware"], "State machine watches funding for transitions."),
    ("state_machine_premium_aware", "NA", "NA", ["sm_premium_aware"], "State machine watches premium changes."),
    ("state_machine_btc_regime_aware", "NA", "NA", ["sm_btc_regime"], "State machine adapts to BTC regime."),
    ("composite_exit_be_trail_indicator", "NA", "NA", ["be_trail_indicator"], "BE → trail → indicator invalidation."),
    ("composite_exit_be_partial_runner", "NA", "NA", ["be_partial_runner"], "BE → partial → runner composite."),
]

# ---------------------------------------------------------------------------
# FILTERS (80)
# ---------------------------------------------------------------------------

FILTERS: list[Entry] = [
    # liquidity (12)
    ("filt_liq_high_only", "*", "NA", ["liquidity_bucket=high"], "Top-tier liquidity only."),
    ("filt_liq_high_mid", "*", "NA", ["liquidity_bucket in [high,mid]"], "Top 2 liquidity buckets."),
    ("filt_liq_volume_5m", "*", "NA", ["daily_volume_usd>=5e6"], "Daily volume > 5M USD."),
    ("filt_liq_volume_50m", "*", "NA", ["daily_volume_usd>=50e6"], "Daily volume > 50M USD."),
    ("filt_liq_oi_10m", "*", "NA", ["oi_usd>=10e6"], "Open interest > 10M USD."),
    ("filt_liq_oi_100m", "*", "NA", ["oi_usd>=100e6"], "Open interest > 100M USD."),
    ("filt_liq_spread_5bps", "*", "NA", ["spread_bps<=5"], "Bid-ask spread < 5 bps."),
    ("filt_liq_spread_10bps", "*", "NA", ["spread_bps<=10"], "Spread < 10 bps."),
    ("filt_liq_depth_top10", "*", "NA", ["depth_rank<=10"], "Symbol in top 10 by depth."),
    ("filt_liq_age_30d", "*", "NA", ["listing_age_days>=30"], "Listed > 30 days."),
    ("filt_liq_age_90d", "*", "NA", ["listing_age_days>=90"], "Listed > 90 days."),
    ("filt_liq_excludes_meme", "*", "NA", ["sector!=meme"], "Exclude meme sector."),

    # microstructure (10)
    ("filt_micro_book_imbalance_aligned", "*", "NA", ["book_imbalance_aligned"], "Order book matches signal direction."),
    ("filt_micro_taker_flow_aligned_5m", "*", "NA", ["taker_flow_5m_aligned"], "Taker flow same direction as signal."),
    ("filt_micro_taker_flow_against_5m", "*", "NA", ["taker_flow_5m_against"], "Contrarian: taker flow against signal."),
    ("filt_micro_recent_aggressive_buys", "*", "long", ["aggressive_buy_5m"], "Recent aggressive buys for long."),
    ("filt_micro_recent_aggressive_sells", "*", "short", ["aggressive_sell_5m"], "Recent aggressive sells for short."),
    ("filt_micro_quiet_book_avoid", "*", "NA", ["book_too_quiet"], "Skip when book too quiet (likely fake)."),
    ("filt_micro_volatile_book_avoid", "*", "NA", ["book_too_volatile"], "Skip when book too volatile."),
    ("filt_micro_no_iceberg_recent", "*", "NA", ["no_iceberg_5m"], "No recent iceberg orders detected."),
    ("filt_micro_aggregator_active", "*", "NA", ["cex_aggregator_active"], "CEX aggregators are active."),
    ("filt_micro_low_taker_for_high_ratio", "*", "long", ["low_taker_for_high_ratio"], "Low taker buy ratio for crash long (capitulation)."),

    # regime (12)
    ("filt_regime_btc_bull_only", "*", "NA", ["btc_24h_pct>=0"], "Only when BTC up day."),
    ("filt_regime_btc_bear_only", "*", "NA", ["btc_24h_pct<=-1"], "Only when BTC down day."),
    ("filt_regime_btc_neutral", "*", "NA", ["btc_24h_pct in [-1,1]"], "BTC neutral days."),
    ("filt_regime_btc_high_vol", "*", "NA", ["btc_atr_24h_high"], "High BTC volatility."),
    ("filt_regime_btc_low_vol", "*", "NA", ["btc_atr_24h_low"], "Low BTC volatility."),
    ("filt_regime_eth_dominance_high", "*", "NA", ["eth_dominance_high"], "ETH dominance high."),
    ("filt_regime_alt_season", "*", "NA", ["alt_season_index_high"], "Alt-season indicator high."),
    ("filt_regime_btc_dominance_falling", "*", "NA", ["btc_dom_falling_7d"], "BTC dominance dropping (alts strong)."),
    ("filt_regime_us_session", "*", "NA", ["session=US"], "US session only."),
    ("filt_regime_asian_session", "*", "NA", ["session=Asian"], "Asian session only."),
    ("filt_regime_european_session", "*", "NA", ["session=European"], "European session only."),
    ("filt_regime_weekend_only", "*", "NA", ["weekday in [Sat,Sun]"], "Weekends only."),

    # pretrend (12)
    ("filt_pretrend_3m_aligned_strong", "*", "NA", ["pretrend_3m_aligned_strong"], "Strong 3m trend in signal direction."),
    ("filt_pretrend_3m_aligned_weak", "*", "NA", ["pretrend_3m_aligned_weak"], "Mild 3m trend in direction."),
    ("filt_pretrend_5m_aligned", "*", "NA", ["pretrend_5m_aligned"], "5m trend aligned."),
    ("filt_pretrend_15m_aligned", "*", "NA", ["pretrend_15m_aligned"], "15m trend aligned."),
    ("filt_pretrend_30m_aligned", "*", "NA", ["pretrend_30m_aligned"], "30m trend aligned."),
    ("filt_pretrend_2h_aligned", "*", "NA", ["pretrend_2h_aligned"], "2h trend aligned."),
    ("filt_pretrend_3m_neutral", "*", "NA", ["pretrend_3m_flat"], "Flat 3m before signal."),
    ("filt_pretrend_3m_against", "*", "NA", ["pretrend_3m_against"], "Counter-trend signal."),
    ("filt_pretrend_volatility_low", "*", "NA", ["realized_vol_30m_low"], "Low recent volatility."),
    ("filt_pretrend_volatility_high", "*", "NA", ["realized_vol_30m_high"], "High recent volatility."),
    ("filt_pretrend_oi_aligned", "*", "NA", ["oi_trend_aligned"], "OI trend matches direction."),
    ("filt_pretrend_oi_against", "*", "NA", ["oi_trend_against"], "OI against direction (squeeze potential)."),

    # burst (8)
    ("filt_burst_first_only", "*", "NA", ["burst_count_5m=1"], "Only first signal in 5min."),
    ("filt_burst_first_two_only", "*", "NA", ["burst_count_5m<=2"], "Only first two signals."),
    ("filt_burst_third_plus_avoid", "*", "NA", ["burst_count_5m<3"], "Skip 3rd+ signals."),
    ("filt_burst_2plus_required", "*", "NA", ["burst_count_5m>=2"], "Require ≥2 signals (confirmation)."),
    ("filt_burst_window_3m", "*", "NA", ["burst_window=3m"], "Burst counted in 3min window."),
    ("filt_burst_window_10m", "*", "NA", ["burst_window=10m"], "Extended 10-min burst window."),
    ("filt_burst_no_burst_quiet", "*", "NA", ["burst_count_5m=0_outside_window"], "Exclude isolated signals (require chain context)."),
    ("filt_burst_chained_burst", "*", "NA", ["burst_chains_within_30s"], "Burst that chains to another within 30s."),

    # cooldown (8)
    ("filt_cd_symbol_5m", "*", "NA", ["cooldown_symbol_5m"], "5-min symbol cooldown."),
    ("filt_cd_symbol_15m", "*", "NA", ["cooldown_symbol_15m"], "15-min symbol cooldown."),
    ("filt_cd_symbol_1h", "*", "NA", ["cooldown_symbol_1h"], "1-hour symbol cooldown."),
    ("filt_cd_channel_5m", "*", "NA", ["cooldown_channel_5m"], "5-min channel cooldown."),
    ("filt_cd_channel_15m", "*", "NA", ["cooldown_channel_15m"], "15-min channel cooldown."),
    ("filt_cd_total_3m", "*", "NA", ["cooldown_global_3m"], "Global 3-min cooldown between any trades."),
    ("filt_cd_after_loss_30m", "*", "NA", ["cooldown_30m_after_loss_per_symbol"], "30-min cooldown after loss per symbol."),
    ("filt_cd_after_win_immediate", "*", "NA", ["no_cooldown_after_win"], "No cooldown after win (ride momentum)."),

    # symbol_meta (10)
    ("filt_meta_marketcap_above_100m", "*", "NA", ["market_cap_usd>=100e6"], "Market cap > 100M."),
    ("filt_meta_marketcap_above_1b", "*", "NA", ["market_cap_usd>=1e9"], "Market cap > 1B."),
    ("filt_meta_marketcap_under_50m", "*", "NA", ["market_cap_usd<=50e6"], "Market cap < 50M (high beta)."),
    ("filt_meta_listed_age_under_30d", "*", "NA", ["listing_age_days<=30"], "New listings only (high vol)."),
    ("filt_meta_btc_correlation_high", "*", "NA", ["btc_correlation_30d>=0.6"], "High BTC-correlation."),
    ("filt_meta_btc_correlation_low", "*", "NA", ["btc_correlation_30d<=0.3"], "Low BTC-correlation (idiosyncratic)."),
    ("filt_meta_sector_meme", "*", "NA", ["sector=meme"], "Meme sector only."),
    ("filt_meta_sector_defi", "*", "NA", ["sector=defi"], "DeFi sector only."),
    ("filt_meta_sector_l1", "*", "NA", ["sector=L1"], "L1 sector only."),
    ("filt_meta_blacklist_specific", "*", "NA", ["symbol_blacklist"], "Exclude specific problematic symbols."),

    # time_of_day (8)
    ("filt_tod_us_open", "*", "NA", ["hour_utc in [13,15]"], "US market open hours."),
    ("filt_tod_us_close", "*", "NA", ["hour_utc in [20,22]"], "US market close hours."),
    ("filt_tod_asian_open", "*", "NA", ["hour_utc in [0,2]"], "Asian market open."),
    ("filt_tod_funding_window", "*", "NA", ["near_funding_settlement"], "Pre/during funding settlement."),
    ("filt_tod_weekend", "*", "NA", ["weekday in [Sat,Sun]"], "Trade only on weekends (lower volume regime)."),
    ("filt_tod_high_vol_hours", "*", "NA", ["hour_in_top_3_vol"], "Historically high-vol hours."),
    ("filt_tod_low_vol_hours", "*", "NA", ["hour_in_bottom_3_vol"], "Quiet hours."),
    ("filt_tod_avoid_news_window", "*", "NA", ["not_near_macro_event"], "Avoid Fed/CPI windows."),

    # === EXPANSION (+40 to reach 120) ===
    # Liquidity extras (+5)
    ("filt_liq_top5", "*", "NA", ["liquidity_rank_top5"], "Symbol in top 5 by liquidity."),
    ("filt_liq_quote_volume_high", "*", "NA", ["quote_volume_above_p75"], "Quote volume above p75."),
    ("filt_liq_taker_volume_high", "*", "NA", ["taker_volume_above_p75"], "Taker volume above p75."),
    ("filt_liq_24h_change_volume_top", "*", "NA", ["24h_volume_change_top"], "24h volume change in top decile."),
    ("filt_liq_oi_24h_change_top", "*", "NA", ["oi_24h_change_top"], "OI 24h change in top decile."),
    # Microstructure extras (+6)
    ("filt_micro_book_imbalance_strong", "*", "NA", ["book_imbalance_strong_aligned"], "Order book imbalance strongly aligned with signal."),
    ("filt_micro_book_imbalance_against", "*", "NA", ["book_imbalance_against"], "Book imbalance against signal (contrarian)."),
    ("filt_micro_aggressive_buys_5m", "*", "NA", ["aggressive_buys_above_p75_5m"], "Aggressive buys above p75 in 5m."),
    ("filt_micro_aggressive_sells_5m", "*", "NA", ["aggressive_sells_above_p75_5m"], "Aggressive sells above p75 in 5m."),
    ("filt_micro_taker_ratio_extreme_high", "*", "NA", ["taker_ratio_above_0.7"], "Taker buy ratio above 0.7."),
    ("filt_micro_taker_ratio_extreme_low", "*", "NA", ["taker_ratio_below_0.3"], "Taker buy ratio below 0.3."),
    # Regime extras (+5)
    ("filt_regime_btc_realized_vol_top", "*", "NA", ["btc_realized_vol_top"], "BTC realized vol in top quartile."),
    ("filt_regime_btc_realized_vol_bottom", "*", "NA", ["btc_realized_vol_bottom"], "BTC realized vol in bottom quartile."),
    ("filt_regime_eth_btc_dominance_change", "*", "NA", ["eth_btc_dominance_changing"], "ETH/BTC dominance shifting."),
    ("filt_regime_alt_dominance_change", "*", "NA", ["alt_dominance_change"], "Alt dominance changing."),
    ("filt_regime_funding_average_extreme", "*", "NA", ["market_funding_avg_extreme"], "Market-wide funding average extreme."),
    # Pretrend extras (+5)
    ("filt_pretrend_3m_pos_strong", "*", "NA", ["pretrend_3m_pct>=2"], "3m pretrend strongly positive."),
    ("filt_pretrend_3m_neg_strong", "*", "NA", ["pretrend_3m_pct<=-2"], "3m pretrend strongly negative."),
    ("filt_pretrend_15m_pos_strong", "*", "NA", ["pretrend_15m_pct>=5"], "15m pretrend strongly positive."),
    ("filt_pretrend_15m_neg_strong", "*", "NA", ["pretrend_15m_pct<=-5"], "15m pretrend strongly negative."),
    ("filt_pretrend_oi_5m_change", "*", "NA", ["oi_change_5m_significant"], "OI 5m change significant."),
    # Burst extras (+3)
    ("filt_burst_first_in_30s", "*", "NA", ["burst_first_in_30s"], "First signal within 30s window."),
    ("filt_burst_first_in_60s", "*", "NA", ["burst_first_in_60s"], "First signal within 60s window."),
    ("filt_burst_density_high", "*", "NA", ["burst_density>=3_in_60s"], "High burst density (3+ in 60s)."),
    # Cooldown extras (+3)
    ("filt_cd_global_30s", "*", "NA", ["cooldown_global_30s"], "Global 30s cooldown between trades."),
    ("filt_cd_global_2m", "*", "NA", ["cooldown_global_2m"], "Global 2-min cooldown."),
    ("filt_cd_per_archetype_5m", "*", "NA", ["cooldown_per_archetype_5m"], "Per-archetype 5-min cooldown."),
    # Symbol meta extras (+5)
    ("filt_meta_volume_rank_top10", "*", "NA", ["volume_rank_top10"], "Symbol in top 10 by volume."),
    ("filt_meta_volume_rank_bottom10", "*", "NA", ["volume_rank_bottom10"], "Symbol in bottom 10 by volume (test)."),
    ("filt_meta_oi_rank_top10", "*", "NA", ["oi_rank_top10"], "Symbol in top 10 by OI."),
    ("filt_meta_funding_extreme_filter", "*", "NA", ["funding_extreme_history"], "Symbol has history of extreme funding."),
    ("filt_meta_recently_listed", "*", "NA", ["listing_age_days<=14"], "Recently listed (<=14 days)."),
    # TOD extras (+5)
    ("filt_tod_funding_settlement_pre", "*", "NA", ["pre_funding_settlement"], "Pre funding settlement window."),
    ("filt_tod_funding_settlement_post", "*", "NA", ["post_funding_settlement"], "Post funding settlement window."),
    ("filt_tod_us_open_first_30m", "*", "NA", ["us_open_first_30m"], "First 30 min of US open."),
    ("filt_tod_asian_close", "*", "NA", ["asian_close_window"], "Asian session close window."),
    ("filt_tod_macro_event_window", "*", "NA", ["macro_event_in_progress"], "Macro event in progress window."),
    # Macro event new category (+3)
    ("filt_macro_no_fed_24h", "*", "NA", ["no_fed_in_24h"], "No Fed event in 24h."),
    ("filt_macro_no_cpi_24h", "*", "NA", ["no_cpi_in_24h"], "No CPI release in 24h."),
    ("filt_macro_post_macro_event_long", "*", "NA", ["post_macro_event_15m"], "15min after macro event (volatility relief)."),
]

# ---------------------------------------------------------------------------
# RISKS (30)
# ---------------------------------------------------------------------------

RISKS: list[Entry] = [
    # position_sizing (8)
    ("risk_size_fixed_5pct", "NA", "NA", ["size=5pct_equity"], "Fixed 5% of equity per trade."),
    ("risk_size_fixed_10pct", "NA", "NA", ["size=10pct_equity"], "Fixed 10% (max from user spec)."),
    ("risk_size_fixed_7_5pct", "NA", "NA", ["size=7.5pct_equity"], "Fixed 7.5% middle ground."),
    ("risk_size_vol_adjusted", "NA", "NA", ["size=inverse_vol"], "Inverse-volatility sizing."),
    ("risk_size_kelly_quarter", "NA", "NA", ["size=0.25*kelly"], "1/4 Kelly fraction."),
    ("risk_size_kelly_half", "NA", "NA", ["size=0.5*kelly"], "1/2 Kelly fraction."),
    ("risk_size_atr_normalized", "NA", "NA", ["size_by_atr"], "Size proportional to ATR."),
    ("risk_size_pct_var_target", "NA", "NA", ["target_var_1pct"], "Target 1% VaR per trade."),

    # concurrency (6)
    ("risk_conc_max_1_position", "NA", "NA", ["max_open_positions=1"], "Only 1 open position at a time."),
    ("risk_conc_max_3_positions", "NA", "NA", ["max_open_positions=3"], "Max 3 open positions."),
    ("risk_conc_max_5_positions", "NA", "NA", ["max_open_positions=5"], "Max 5 open positions."),
    ("risk_conc_per_symbol_1", "NA", "NA", ["max_per_symbol=1"], "Max 1 per symbol."),
    ("risk_conc_per_side_max", "NA", "NA", ["max_per_side=3"], "Max 3 per side (limit lopsidedness)."),
    ("risk_conc_per_channel_max", "NA", "NA", ["max_per_channel=2"], "Max 2 per channel source."),

    # correlation (5)
    ("risk_corr_no_pair_corr_above_0_7", "NA", "NA", ["pair_corr<0.7"], "Exclude correlated pairs > 0.7."),
    ("risk_corr_max_3_per_sector", "NA", "NA", ["max_3_per_sector"], "Max 3 positions per sector."),
    ("risk_corr_btc_exposure_cap", "NA", "NA", ["btc_beta_exposure_cap"], "Cap BTC-correlated exposure."),
    ("risk_corr_no_two_high_beta", "NA", "NA", ["max_1_high_beta"], "Exclude double high-beta exposure."),
    ("risk_corr_dynamic_pair_check", "NA", "NA", ["realtime_corr_check"], "Real-time correlation check."),

    # daily_limit (5)
    ("risk_dl_loss_2pct_stop", "NA", "NA", ["daily_loss_stop=2pct"], "Stop trading at 2% daily loss."),
    ("risk_dl_loss_5pct_stop", "NA", "NA", ["daily_loss_stop=5pct"], "Stop trading at 5% daily loss."),
    ("risk_dl_max_10_trades", "NA", "NA", ["max_trades_per_day=10"], "Max 10 trades/day."),
    ("risk_dl_max_20_trades", "NA", "NA", ["max_trades_per_day=20"], "Max 20 trades/day."),
    ("risk_dl_pause_after_3_losses", "NA", "NA", ["pause_after_3_consec_loss"], "Pause after 3 consecutive losses."),

    # diversification (6)
    ("risk_div_force_symbol_rotation", "NA", "NA", ["force_rotation"], "Must rotate symbols (can't trade same twice)."),
    ("risk_div_avoid_recent_loser", "NA", "NA", ["skip_recent_loser_24h"], "Skip symbols with recent 24h losses."),
    ("risk_div_balance_long_short", "NA", "NA", ["balance_LS_ratio"], "Try to balance L/S exposure."),
    ("risk_div_sector_rotation", "NA", "NA", ["sector_rotation"], "Rotate sectors."),
    ("risk_div_exposure_max_30pct_per_symbol", "NA", "NA", ["max_pct_per_symbol=30"], "Cap exposure per symbol."),
    ("risk_div_geographic_diversification", "NA", "NA", ["geographic_diversification"], "Across token regions (illusory but try)."),

    # === EXPANSION (+10 to reach 40) ===
    ("risk_size_dynamic_volatility_floor", "NA", "NA", ["size_with_vol_floor"], "Dynamic sizing with minimum volatility floor."),
    ("risk_size_capped_max_5pct", "NA", "NA", ["size_capped_5pct_max"], "Hard cap at 5% per trade regardless of signal strength."),
    ("risk_conc_max_per_archetype_2", "NA", "NA", ["max_per_archetype=2"], "Max 2 open positions per archetype."),
    ("risk_conc_max_per_strategy_3", "NA", "NA", ["max_per_strategy=3"], "Max 3 open positions per complete strategy."),
    ("risk_dl_per_symbol_loss_2pct", "NA", "NA", ["per_symbol_loss_stop=2pct"], "Stop trading specific symbol after 2% daily loss in it."),
    ("risk_dl_per_strategy_loss_3pct", "NA", "NA", ["per_strategy_loss_stop=3pct"], "Stop strategy after 3% daily loss."),
    ("risk_div_pretrend_diversification", "NA", "NA", ["diversify_by_pretrend"], "Diversify across pretrend regimes."),
    ("risk_div_alternate_long_short", "NA", "NA", ["alternate_LS_within_hour"], "Alternate L/S within same hour for balance."),
    ("risk_div_no_recent_winner_repeat", "NA", "NA", ["no_repeat_winning_symbol_30m"], "No repeat trading recent winner symbol within 30m."),
    ("risk_div_session_diversification", "NA", "NA", ["diversify_across_sessions"], "Diversify trades across sessions."),
]

# ---------------------------------------------------------------------------
# CROSS_CHANNEL (40)
# ---------------------------------------------------------------------------

CROSS_CHANNEL: list[Entry] = [
    # confirm (12)
    ("cc_pc_within_2m_oi", "*", "NA", ["pc_then_oi_within_2m"], "PC + OI within 2-min window."),
    ("cc_pc_within_5m_oi", "*", "NA", ["pc_then_oi_within_5m"], "PC + OI within 5-min window."),
    ("cc_pc_within_10m_oi", "*", "NA", ["pc_then_oi_within_10m"], "PC + OI within 10-min window."),
    ("cc_oi_within_2m_pc", "*", "NA", ["oi_then_pc_within_2m"], "OI then PC within 2-min."),
    ("cc_oi_within_5m_pc", "*", "NA", ["oi_then_pc_within_5m"], "OI then PC within 5-min."),
    ("cc_r6_within_2m_pc", "*", "NA", ["r6_then_pc_within_2m"], "R6 + PC within 2-min."),
    ("cc_r6_within_5m_pc", "*", "NA", ["r6_then_pc_within_5m"], "R6 + PC within 5-min."),
    ("cc_pc_oi_r6_5m_window", "*", "NA", ["all_three_within_5m"], "All three channels in 5-min window."),
    ("cc_pc_oi_funding_align", "*", "NA", ["pc_oi_funding_aligned"], "PC + OI + funding sign aligned."),
    ("cc_oi_taker_align", "*", "NA", ["oi_signal_taker_aligned"], "OI signal + taker flow aligned."),
    ("cc_pc_oi_premium_align", "*", "NA", ["pc_oi_premium_aligned"], "PC + OI + premium aligned."),
    ("cc_full_chain_strong", "*", "NA", ["multi_signal_strong_confirm"], "Multi-signal strong confirmation chain."),

    # conflict (8)
    ("cc_no_recent_opposite", "*", "NA", ["no_opposite_signal_5m"], "No opposite signal within 5-min."),
    ("cc_no_opposite_pc_3m", "*", "NA", ["no_opposite_pc_3m"], "No opposite PC in 3-min."),
    ("cc_no_opposite_oi_5m", "*", "NA", ["no_opposite_oi_5m"], "No opposite OI in 5-min."),
    ("cc_skip_after_r6_opposite", "*", "NA", ["skip_if_r6_opposite_recent"], "Skip if R6 opposite recently."),
    ("cc_skip_recent_failed_loss", "*", "NA", ["skip_if_recent_loss_symbol"], "Skip if recent loss in this symbol."),
    ("cc_no_extreme_funding_against", "*", "NA", ["no_extreme_funding_against"], "Skip if funding against direction."),
    ("cc_no_pretrend_extreme", "*", "NA", ["no_pretrend_extreme"], "Skip extreme pretrend setups."),
    ("cc_btc_align_required", "*", "NA", ["btc_alignment_required"], "Require BTC alignment."),

    # weight (10)
    ("cc_weight_pc_2x_oi", "*", "NA", ["pc_weight=2x_oi"], "PC weighted 2x OI."),
    ("cc_weight_oi_2x_pc", "*", "NA", ["oi_weight=2x_pc"], "OI weighted 2x PC."),
    ("cc_weight_r6_3x", "*", "NA", ["r6_weight=3x"], "R6 highest weight."),
    ("cc_weight_equal", "*", "NA", ["equal_weights"], "Equal weights for all channels."),
    ("cc_weight_recency", "*", "NA", ["recent_signal_weighted_higher"], "Recent signals weighted more."),
    ("cc_weight_strength_proportional", "*", "NA", ["weight_by_signal_strength"], "Weight by signal magnitude."),
    ("cc_weight_volatility_inverse", "*", "NA", ["inverse_volatility_weighted"], "Inverse-volatility weighted."),
    ("cc_weight_liquidity_proportional", "*", "NA", ["weight_by_liquidity"], "Weight by liquidity."),
    ("cc_weight_btc_align_boost", "*", "NA", ["btc_align_boost_2x"], "Boost weight when BTC aligned."),
    ("cc_weight_funding_align_boost", "*", "NA", ["funding_align_boost"], "Boost when funding aligned."),

    # time_decay (10)
    ("cc_decay_2m_half", "*", "NA", ["half_life_2m"], "Signal value halves after 2-min."),
    ("cc_decay_5m_half", "*", "NA", ["half_life_5m"], "5-min half-life decay."),
    ("cc_decay_10m_half", "*", "NA", ["half_life_10m"], "10-min half-life decay."),
    ("cc_decay_linear_5m_zero", "*", "NA", ["linear_to_zero_5m"], "Linear decay to zero in 5-min."),
    ("cc_decay_linear_10m_zero", "*", "NA", ["linear_to_zero_10m"], "Linear decay to zero in 10-min."),
    ("cc_decay_step_2m", "*", "NA", ["step_decay_2m"], "Step-decay every 2-min."),
    ("cc_decay_exp_3m_tau", "*", "NA", ["exp_decay_tau_3m"], "Exponential decay tau=3min."),
    ("cc_decay_no_decay_15m", "*", "NA", ["no_decay_15m"], "No decay within 15-min."),
    ("cc_decay_immediate_post_event", "*", "NA", ["immediate_decay"], "Decay starts immediately."),
    ("cc_decay_post_first_minute", "*", "NA", ["decay_starts_after_60s"], "Decay starts after first minute."),

    # === EXPANSION (+20 to reach 60) ===
    ("cc_confirm_within_15s", "*", "NA", ["confirm_within_15s"], "Cross-channel confirmation within 15s."),
    ("cc_confirm_within_30s", "*", "NA", ["confirm_within_30s"], "Cross-channel confirmation within 30s."),
    ("cc_pc_oi_2nd_signal_within_5m", "*", "NA", ["pc_or_oi_2nd_signal_in_5m"], "PC or OI second signal within 5m."),
    ("cc_pc_pump_oi_pump_funding_align", "*", "NA", ["pc_oi_funding_aligned_pump"], "PC + OI pump + funding aligned (long bias)."),
    ("cc_pc_pump_oi_pump_funding_diverge_short", "*", "NA", ["pc_oi_funding_diverge_pump"], "PC + OI pump but funding against = short bias."),
    ("cc_oi_then_pc_alignment_short", "*", "NA", ["oi_pc_pretrend_misalign"], "OI + PC against pretrend = short."),
    ("cc_pc_oi_within_2m_strict", "*", "NA", ["pc_oi_within_2m_strict_align"], "PC + OI strict 2-min, side aligned."),
    ("cc_pc_oi_within_2m_pretrend_align", "*", "NA", ["pc_oi_within_2m_pretrend_aligned"], "PC + OI 2m + pretrend aligned."),
    ("cc_three_channel_strong_strict_30s", "*", "NA", ["three_channel_strict_30s"], "All 3 channels in strict 30s window."),
    ("cc_three_channel_pretrend_align_strict", "*", "NA", ["three_channel_pretrend_aligned"], "All 3 + pretrend strictly aligned."),
    ("cc_no_recent_failure_signal", "*", "NA", ["no_recent_failed_signal_5m"], "No recent failed signal in last 5m."),
    ("cc_no_recent_failure_archetype", "*", "NA", ["no_recent_failed_archetype_30m"], "No recent failed archetype within 30m."),
    ("cc_no_recent_high_volatility", "*", "NA", ["no_recent_high_vol_5m"], "No recent high volatility (pre-signal)."),
    ("cc_weight_recency_exponential", "*", "NA", ["recency_exp_weight"], "Exponential decay weighting by signal recency."),
    ("cc_weight_burst_count", "*", "NA", ["weight_inverse_burst"], "Weight inverse to burst count (favor first)."),
    ("cc_weight_archetype_history", "*", "NA", ["weight_by_archetype_winrate"], "Weight by archetype historical win rate."),
    ("cc_weight_failure_history_inverse", "*", "NA", ["weight_inverse_failure_rate"], "Weight inverse to failure rate."),
    ("cc_weight_combined_score", "*", "NA", ["combined_weighted_score"], "Combined weighted score from all heuristics."),
    ("cc_decay_15m", "*", "NA", ["half_life_15m"], "15-min half-life decay (slow)."),
    ("cc_decay_30m", "*", "NA", ["half_life_30m"], "30-min half-life decay (very slow)."),
]

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

VALID_CHANNELS = {"OI_Price", "pricechange", "Reserved6", "*", "NA"}
VALID_SIDES = {"long", "short", "both", "NA"}
VALID_TYPES = {"entry", "exit", "filter", "risk", "cross_channel"}


def validate_entry(entry: dict) -> list[str]:
    errors = []
    for k in ("id", "type", "archetype", "channel", "side", "novel_dim", "expected_distinct", "notes"):
        if k not in entry:
            errors.append(f"missing field: {k}")
    if entry["type"] not in VALID_TYPES:
        errors.append(f"invalid type: {entry['type']}")
    if entry["channel"] not in VALID_CHANNELS:
        errors.append(f"invalid channel: {entry['channel']}")
    if entry["side"] not in VALID_SIDES:
        errors.append(f"invalid side: {entry['side']}")
    if not isinstance(entry["novel_dim"], list) or not entry["novel_dim"]:
        errors.append("novel_dim must be non-empty list")
    if not entry["notes"] or len(entry["notes"]) < 10:
        errors.append(f"notes too short: {entry['notes']!r}")
    return errors


def build_registry() -> list[dict]:
    out: list[dict] = []
    for i, t in enumerate(ENTRIES, 1):
        out.append(_to_dict("E", i, "entry", t))
    for i, t in enumerate(EXITS, 1):
        out.append(_to_dict("X", i, "exit", t))
    for i, t in enumerate(FILTERS, 1):
        out.append(_to_dict("F", i, "filter", t))
    for i, t in enumerate(RISKS, 1):
        out.append(_to_dict("R", i, "risk", t))
    for i, t in enumerate(CROSS_CHANNEL, 1):
        out.append(_to_dict("C", i, "cross_channel", t))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--output", type=str, default=str(OUTPUT_PATH))
    args = ap.parse_args()

    registry = build_registry()
    expected_quotas = {
        "entry": 200, "exit": 100, "filter": 120, "risk": 40, "cross_channel": 60
    }
    actual_counts: dict[str, int] = {}
    all_errors: list[str] = []
    seen_ids: set[str] = set()
    seen_archetypes: set[str] = set()

    for entry in registry:
        actual_counts[entry["type"]] = actual_counts.get(entry["type"], 0) + 1
        errs = validate_entry(entry)
        for e in errs:
            all_errors.append(f"{entry.get('id', '?')}: {e}")
        if entry["id"] in seen_ids:
            all_errors.append(f"duplicate id: {entry['id']}")
        seen_ids.add(entry["id"])
        if entry["archetype"] in seen_archetypes:
            all_errors.append(f"duplicate archetype: {entry['archetype']}")
        seen_archetypes.add(entry["archetype"])

    print("Quota check:")
    for k, v in expected_quotas.items():
        actual = actual_counts.get(k, 0)
        status = "OK" if actual == v else "MISMATCH"
        print(f"  {k:15s} : {actual} / {v}  [{status}]")
    expected_total = sum(expected_quotas.values())
    print(f"Total: {len(registry)} (expected {expected_total})")
    print(f"Validation errors: {len(all_errors)}")
    for e in all_errors[:20]:
        print(f"  ! {e}")

    if all_errors or len(registry) != expected_total:
        print("\nFAIL")
        return 1

    if args.validate_only:
        print("\nVALIDATE-ONLY: skipping write.")
        return 0

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for entry in registry:
            f.write(json.dumps(entry, ensure_ascii=False))
            f.write("\n")
    print(f"\nPASS: wrote {len(registry)} archetypes to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
