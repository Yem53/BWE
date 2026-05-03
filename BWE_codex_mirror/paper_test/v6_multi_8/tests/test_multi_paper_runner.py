#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import sys
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from multi_paper_runner import (  # noqa: E402
    Bar,
    BweEvent,
    FeatureSnapshot,
    OpenPosition,
    RunnerState,
    StrategySpec,
    build_heartbeat,
    evaluate_long_strategy,
    load_strategy_specs,
    maybe_apply_binance_fallback,
    parse_args,
    parse_bwe_post,
    portfolio_block_reason,
    short_pnl,
    simulate_exit,
    state_from_dict,
    state_to_dict,
)


def test_loads_nine_specs_with_long_and_short() -> None:
    specs = load_strategy_specs(ROOT / "config/strategies_9.json")
    assert len(specs) == 9
    assert sum(1 for s in specs if s.side == "long") == 5
    assert sum(1 for s in specs if s.side == "short") == 4
    assert any(s.strategy_id == "v6_982b322524d6a28283" for s in specs)


def test_long_strategy_without_marketcap_gate_can_pass() -> None:
    specs = load_strategy_specs(ROOT / "config/strategies_9.json")
    spec = next(s for s in specs if s.strategy_id == "v6_d9cf2c20ba340e99e0")
    event = parse_bwe_post(
        {
            "ts_ms": 1777741686616,
            "source": "BWE_pricechange_monitor",
            "post_id": "1",
            "text": "Price Monitor: ABCUSDT +5.0% in the past 60 seconds",
        }
    )
    assert event is not None
    features = FeatureSnapshot(
        top_ratio=2.5,
        top_ratio_age_ms=0,
        global_ratio=1.0,
        global_ratio_age_ms=0,
        top_position_ratio=2.0,
        taker_ratio=0.8,
        oi_chg_60m=6.0,
        quote_volume_24h=10_000_000.0,
        listing_age_days=500.0,
        mark_1m_age_ms=60_000,
    )
    ok, reason = evaluate_long_strategy(event, features, spec, {"ABCUSDT"})
    assert ok
    assert reason == "entry_pass"


def test_condition_strategy_rejects_missing_quote_volume() -> None:
    specs = load_strategy_specs(ROOT / "config/strategies_9.json")
    spec = next(s for s in specs if s.strategy_id == "v6_d9cf2c20ba340e99e0")
    event = parse_bwe_post(
        {
            "ts_ms": 1777741686616,
            "source": "BWE_pricechange_monitor",
            "post_id": "1",
            "text": "Price Monitor: ABCUSDT +5.0% in the past 60 seconds",
        }
    )
    assert event is not None
    features = FeatureSnapshot(
        top_ratio=2.5,
        top_ratio_age_ms=0,
        global_ratio=2.0,
        global_ratio_age_ms=0,
    )
    features.quote_volume_24h = None
    ok, reason = evaluate_long_strategy(event, features, spec, {"ABCUSDT"})
    assert not ok
    assert reason == "skip_quote_volume_24h_missing"


def test_hybrid_fallback_fills_missing_or_stale_long_features() -> None:
    spec = StrategySpec(
        strategy_id="L_TEST",
        label="L_TEST",
        side="long",
        trigger="bwe",
        entry_delay_s=180,
        conditions=[
            {"field": "quote_volume_24h", "op": "<=", "threshold": 50_000_000},
            {"field": "top_ratio", "op": ">=", "threshold": 2.0, "max_age_ms": 600_000},
            {"field": "mark_1m_age_ms", "op": "<=", "threshold": 300_000},
        ],
        exit={"kind": "failed_continuation"},
        event_type="pump",
    )
    event = parse_bwe_post(
        {
            "ts_ms": 1777741686616,
            "source": "BWE_pricechange_monitor",
            "post_id": "1",
            "text": "Price Monitor: ABCUSDT +5.0% in the past 60 seconds",
        }
    )
    assert event is not None
    db_features = FeatureSnapshot(top_ratio=2.5, top_ratio_age_ms=900_000, quote_volume_24h=None, mark_1m_age_ms=800_000)
    rest_features = FeatureSnapshot(top_ratio=2.7, top_ratio_age_ms=1_000, quote_volume_24h=10_000_000.0, mark_1m_age_ms=1_500)
    calls = []

    def fake_fetcher(symbol, base_url, current_ts_ms, needed_fields, timeout):
        calls.append((symbol, base_url, current_ts_ms, set(needed_fields), timeout))
        return rest_features

    args = SimpleNamespace(enable_binance_fallback=True, price_base_url="https://example.test", fallback_timeout_seconds=2.0, ticker_max_age_ms=600_000)
    merged, used = maybe_apply_binance_fallback(event, db_features, spec, args, 1777741866616, fetcher=fake_fetcher)

    assert calls == [("ABCUSDT", "https://example.test", 1777741866616, {"quote_volume_24h", "top_ratio", "mark_1m_age_ms"}, 2.0)]
    assert set(used) == {"quote_volume_24h", "top_ratio", "mark_1m_age_ms"}
    ok, reason = evaluate_long_strategy(event, merged, spec, {"ABCUSDT"})
    assert ok
    assert reason == "entry_pass"


def test_hybrid_fallback_does_not_call_rest_when_db_features_are_fresh() -> None:
    spec = StrategySpec(
        strategy_id="L_TEST",
        label="L_TEST",
        side="long",
        trigger="bwe",
        entry_delay_s=180,
        conditions=[
            {"field": "quote_volume_24h", "op": "<=", "threshold": 50_000_000},
            {"field": "top_ratio", "op": ">=", "threshold": 2.0, "max_age_ms": 600_000},
            {"field": "mark_1m_age_ms", "op": "<=", "threshold": 300_000},
        ],
        exit={"kind": "failed_continuation"},
        event_type="pump",
    )
    event = BweEvent(1, "BWE_pricechange_monitor", "1", "ABCUSDT +5%", "ABCUSDT", "pump", 5.0, None)
    features = FeatureSnapshot(top_ratio=2.5, top_ratio_age_ms=30_000, quote_volume_24h=10_000_000.0, mark_1m_age_ms=2_000)

    def fail_fetcher(*_args, **_kwargs):
        raise AssertionError("fresh DB features should not call Binance fallback")

    args = SimpleNamespace(enable_binance_fallback=True, price_base_url="https://example.test", fallback_timeout_seconds=2.0, ticker_max_age_ms=600_000)
    merged, used = maybe_apply_binance_fallback(event, features, spec, args, 1777741866616, fetcher=fail_fetcher)

    assert merged is features
    assert used == []


def test_short_adaptive_trail_uses_short_price_formula() -> None:
    spec = StrategySpec(
        strategy_id="S_TEST",
        label="S_TEST",
        side="short",
        trigger="scanner",
        entry_delay_s=0,
        conditions=[],
        exit={"kind": "adaptive_trail", "horizon": 120, "arm": 8, "trail": 3, "lock": 8, "sl": 0},
    )
    pos = OpenPosition(
        strategy_id="S_TEST",
        label="S_TEST",
        symbol="ABCUSDT",
        side="short",
        event_ts_ms=0,
        due_ts_ms=0,
        entry_ts_ms=0,
        entry_price=100.0,
        qty=1.0,
        mode="signal_only",
        exit=spec.exit,
    )
    bars = [
        Bar(open_time_ms=60_000, open=100.0, high=101.0, low=90.0, close=94.0),
        Bar(open_time_ms=120_000, open=94.0, high=94.5, low=88.0, close=90.0),
    ]
    closed = simulate_exit(pos, bars, spec)
    assert closed is not None
    assert closed.reason == "adaptive_trail"
    assert math.isclose(closed.pnl_pct, 8.0)


def test_short_pnl_is_price_based_linear_return() -> None:
    assert math.isclose(short_pnl(100.0, 50.0), 50.0)
    assert math.isclose(short_pnl(100.0, 200.0), -100.0)


def test_short_adaptive_trail_does_not_use_same_bar_low_to_exit_on_same_bar_high() -> None:
    spec = StrategySpec(
        strategy_id="S_TEST",
        label="S_TEST",
        side="short",
        trigger="scanner",
        entry_delay_s=0,
        conditions=[],
        exit={"kind": "adaptive_trail", "horizon": 120, "arm": 8, "trail": 3, "lock": 8, "sl": 0},
    )
    pos = OpenPosition(
        strategy_id="S_TEST",
        label="S_TEST",
        symbol="ABCUSDT",
        side="short",
        event_ts_ms=0,
        due_ts_ms=0,
        entry_ts_ms=0,
        entry_price=100.0,
        qty=1.0,
        mode="signal_only",
        exit=spec.exit,
    )
    closed = simulate_exit(pos, [Bar(open_time_ms=60_000, open=100.0, high=101.0, low=90.0, close=91.0)], spec)
    assert closed is None


def test_heartbeat_has_strategy_table_and_open_list() -> None:
    specs = load_strategy_specs(ROOT / "config/strategies_9.json")
    state = RunnerState(started_ts_ms=0)
    state.by_strategy["L1"] = {"pass": 3, "open": 1, "closed": 2, "wins": 1, "sum_pct": 4.2}
    state.open_positions.append(
        OpenPosition(
            strategy_id="L1",
            label="L1",
            symbol="ABCUSDT",
            side="long",
            event_ts_ms=0,
            due_ts_ms=0,
            entry_ts_ms=0,
            entry_price=1.23,
            qty=10.0,
            mode="signal_only",
            exit={"kind": "failed_continuation", "horizon": 240, "sl_pct": 0.05},
        )
    )
    msg = build_heartbeat(state, specs, now_ms=3_600_000)
    assert "BWE Paper-LIVE Heartbeat" in msg
    assert "strategy" in msg
    assert "Open (1):" in msg
    assert "ABCUSDT" in msg
    table_lines = [line for line in msg.splitlines() if line.startswith(("strategy", "PS0_", "L1_", "L2_", "L3_", "L4_", "S1_", "S2_", "S3_", "S4_"))]
    assert len({len(line) for line in table_lines}) == 1


def test_heartbeat_default_is_one_hour() -> None:
    args = parse_args([])
    assert args.heartbeat_seconds == 3600.0


def test_portfolio_blocks_duplicate_symbol_when_one_position_per_symbol() -> None:
    state = RunnerState(started_ts_ms=1)
    state.open_positions.append(
        OpenPosition(
            strategy_id="OTHER",
            label="OTHER",
            symbol="ABCUSDT",
            side="long",
            event_ts_ms=0,
            due_ts_ms=0,
            entry_ts_ms=1_000_000,
            entry_price=1.0,
            qty=1.0,
            mode="demo_order",
            exit={"kind": "failed_continuation"},
        )
    )
    spec = StrategySpec("S_TEST", "S_TEST", "short", "scanner", 0, [], {"kind": "adaptive_trail"})
    args = SimpleNamespace(max_concurrent_per_strategy=5, max_concurrent_total=16, one_position_per_symbol=True, same_strategy_symbol_cooldown_min=60, demo_orders=True)
    assert portfolio_block_reason(state, spec, "ABCUSDT", args, 2_000_000) == "skip_symbol_already_open"


def test_portfolio_blocks_demo_opposite_side_conflict_instead_of_signal_only() -> None:
    state = RunnerState(started_ts_ms=1)
    state.open_positions.append(
        OpenPosition(
            strategy_id="LONG",
            label="LONG",
            symbol="ABCUSDT",
            side="long",
            event_ts_ms=0,
            due_ts_ms=0,
            entry_ts_ms=1_000_000,
            entry_price=1.0,
            qty=1.0,
            mode="demo_order",
            exit={"kind": "failed_continuation"},
        )
    )
    spec = StrategySpec("S_TEST", "S_TEST", "short", "scanner", 0, [], {"kind": "adaptive_trail"})
    args = SimpleNamespace(max_concurrent_per_strategy=5, max_concurrent_total=16, one_position_per_symbol=False, same_strategy_symbol_cooldown_min=0, demo_orders=True)
    assert portfolio_block_reason(state, spec, "ABCUSDT", args, 2_000_000) == "skip_demo_opposite_side_conflict"


def test_portfolio_blocks_same_strategy_symbol_cooldown() -> None:
    state = RunnerState(started_ts_ms=1)
    state.closed_positions.append(
        OpenPosition(
            strategy_id="S_TEST",
            label="S_TEST",
            symbol="ABCUSDT",
            side="short",
            event_ts_ms=0,
            due_ts_ms=0,
            entry_ts_ms=1_000_000,
            entry_price=1.0,
            qty=1.0,
            mode="demo_order",
            exit={"kind": "adaptive_trail"},
        )
    )
    spec = StrategySpec("S_TEST", "S_TEST", "short", "scanner", 0, [], {"kind": "adaptive_trail"})
    args = SimpleNamespace(max_concurrent_per_strategy=5, max_concurrent_total=16, one_position_per_symbol=False, same_strategy_symbol_cooldown_min=60, demo_orders=True)
    assert portfolio_block_reason(state, spec, "ABCUSDT", args, 1_000_000 + 30 * 60_000) == "skip_same_strategy_symbol_cooldown"


def test_state_roundtrip_keeps_pending_and_open_positions() -> None:
    state = RunnerState(started_ts_ms=1)
    state.scanner_last_run_ms = 123456
    state.pending_entries.append(
        {
            "strategy_id": "L1",
            "event": {
                "ts_ms": 1,
                "source": "BWE_pricechange_monitor",
                "post_id": "1",
                "text": "Price Monitor: ABCUSDT +1%",
                "symbol": "ABCUSDT",
                "event_type": "pump",
                "move_pct": 1.0,
                "marketcap": None,
            },
            "due_ts_ms": 181000,
        }
    )
    raw = json.loads(json.dumps(state_to_dict(state)))
    restored = state_from_dict(raw)
    assert restored.pending_entries[0]["strategy_id"] == "L1"
    assert restored.scanner_last_run_ms == 123456


def main() -> None:
    test_loads_nine_specs_with_long_and_short()
    test_long_strategy_without_marketcap_gate_can_pass()
    test_condition_strategy_rejects_missing_quote_volume()
    test_hybrid_fallback_fills_missing_or_stale_long_features()
    test_hybrid_fallback_does_not_call_rest_when_db_features_are_fresh()
    test_short_adaptive_trail_uses_short_price_formula()
    test_short_pnl_is_price_based_linear_return()
    test_short_adaptive_trail_does_not_use_same_bar_low_to_exit_on_same_bar_high()
    test_heartbeat_has_strategy_table_and_open_list()
    test_heartbeat_default_is_one_hour()
    test_portfolio_blocks_duplicate_symbol_when_one_position_per_symbol()
    test_portfolio_blocks_demo_opposite_side_conflict_instead_of_signal_only()
    test_portfolio_blocks_same_strategy_symbol_cooldown()
    test_state_roundtrip_keeps_pending_and_open_positions()


if __name__ == "__main__":
    main()
