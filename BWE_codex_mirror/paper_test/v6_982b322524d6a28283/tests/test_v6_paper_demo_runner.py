#!/usr/bin/env python3
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from v6_paper_demo_runner import (  # noqa: E402
    Bar,
    FeatureSnapshot,
    OpenPosition,
    StrategyConfig,
    build_open_message,
    evaluate_entry,
    parse_bwe_post,
    round_step,
    simulate_failed_continuation_exit,
)


def test_parse_bwe_pump_with_marketcap() -> None:
    event = parse_bwe_post(
        {
            "ts_ms": 1777741686616,
            "source": "BWE_pricechange_monitor",
            "post_id": "78816",
            "text": "Price Monitor: LABUSDT (LAB) +1.8% in the past 3 seconds MarketCap: 70.9M",
        }
    )
    assert event is not None
    assert event.symbol == "LABUSDT"
    assert event.event_type == "pump"
    assert math.isclose(event.marketcap, 70_900_000.0)


def test_evaluate_entry_rejects_missing_marketcap() -> None:
    cfg = StrategyConfig()
    event = parse_bwe_post(
        {
            "ts_ms": 1,
            "source": "BWE_pricechange_monitor",
            "post_id": "p1",
            "text": "Price Monitor: ABCUSDT +2.0% in the past 10 seconds",
        }
    )
    assert event is not None
    ok, reason = evaluate_entry(
        event,
        FeatureSnapshot(top_ratio=3.0, top_ratio_age_ms=0, global_ratio=2.0, global_ratio_age_ms=0),
        cfg,
        active_symbols={"ABCUSDT"},
    )
    assert not ok
    assert reason == "skip_missing_marketcap"


def test_evaluate_entry_requires_marketcap_and_sentiment_thresholds() -> None:
    cfg = StrategyConfig()
    event = parse_bwe_post(
        {
            "ts_ms": 1,
            "source": "BWE_pricechange_monitor",
            "post_id": "p2",
            "text": "Price Monitor: ABCUSDT +2.0% in the past 10 seconds MarketCap: 70M",
        }
    )
    assert event is not None
    ok, reason = evaluate_entry(
        event,
        FeatureSnapshot(top_ratio=2.24, top_ratio_age_ms=0, global_ratio=1.69, global_ratio_age_ms=0),
        cfg,
        active_symbols={"ABCUSDT"},
    )
    assert not ok
    assert reason == "skip_top_ratio_below_threshold"
    ok, reason = evaluate_entry(
        event,
        FeatureSnapshot(top_ratio=2.25, top_ratio_age_ms=0, global_ratio=1.69, global_ratio_age_ms=0),
        cfg,
        active_symbols={"ABCUSDT"},
    )
    assert ok
    assert reason == "entry_pass"


def test_failed_continuation_stop_uses_intrabar_low_before_later_profit() -> None:
    cfg = StrategyConfig()
    pos = OpenPosition(
        strategy_id=cfg.strategy_id,
        symbol="ABCUSDT",
        side="long",
        event_ts_ms=0,
        due_ts_ms=0,
        entry_ts_ms=0,
        entry_price=100.0,
        qty=1.0,
        mode="dry_run",
    )
    bars = [
        Bar(open_time_ms=60_000, open=100.0, high=150.0, low=94.0, close=140.0),
        Bar(open_time_ms=120_000, open=140.0, high=160.0, low=130.0, close=150.0),
    ]
    closed = simulate_failed_continuation_exit(pos, bars, cfg)
    assert closed is not None
    assert closed.reason == "initial_stop"
    assert math.isclose(closed.exit_price, 95.0)
    assert math.isclose(closed.pnl_pct, -5.0)


def test_failed_continuation_exits_after_no_proof_at_10_minutes() -> None:
    cfg = StrategyConfig()
    pos = OpenPosition(
        strategy_id=cfg.strategy_id,
        symbol="ABCUSDT",
        side="long",
        event_ts_ms=0,
        due_ts_ms=0,
        entry_ts_ms=0,
        entry_price=100.0,
        qty=1.0,
        mode="dry_run",
    )
    bars = [
        Bar(open_time_ms=i * 60_000, open=100.0, high=101.0, low=98.0, close=100.0)
        for i in range(1, 11)
    ]
    bars[-1] = Bar(open_time_ms=600_000, open=100.0, high=101.0, low=98.0, close=98.0)
    closed = simulate_failed_continuation_exit(pos, bars, cfg)
    assert closed is not None
    assert closed.reason == "failed_continuation_exit"
    assert math.isclose(closed.pnl_pct, -2.0)


def test_round_step_floors_to_exchange_step() -> None:
    assert round_step(1.239, 0.01, 0.01, 2) == 1.23
    assert round_step(0.0009, 0.001, 0.001, 3) is None


def test_open_message_does_not_include_secret_material() -> None:
    cfg = StrategyConfig()
    msg = build_open_message(
        cfg,
        symbol="ABCUSDT",
        mode="demo_order",
        entry_price=100.0,
        qty=0.5,
        notional=50.0,
        top_ratio=2.5,
        global_ratio=1.8,
        marketcap=70_000_000,
        order_id="12345",
    )
    assert cfg.strategy_id in msg
    assert "ABCUSDT" in msg
    assert "BOT_TOKEN" not in msg
    assert "API_KEY" not in msg


def main() -> None:
    test_parse_bwe_pump_with_marketcap()
    test_evaluate_entry_rejects_missing_marketcap()
    test_evaluate_entry_requires_marketcap_and_sentiment_thresholds()
    test_failed_continuation_stop_uses_intrabar_low_before_later_profit()
    test_failed_continuation_exits_after_no_proof_at_10_minutes()
    test_round_step_floors_to_exchange_step()
    test_open_message_does_not_include_secret_material()


if __name__ == "__main__":
    main()
