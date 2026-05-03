import json
from pathlib import Path

import pandas as pd


def test_is_new_strategy_rejects_pure_parameter_tweak():
    from bwe_autoresearch.discovery import CandidateSpec, is_new_strategy

    base = CandidateSpec(
        candidate_id="base",
        hypothesis="OI pump overcrowding fades after delayed entry",
        source_channel="BWE_OI_Price_monitor",
        family="oi_overcrowded_pump_reversal_short",
        discovery_layer="known_family_refinement",
        direction="short",
        entry_rule={"event_type": "pump", "oi_ratio_pct_gte": 10},
        filters={},
        exit_rule={"type": "fixed_horizon", "entry_delay_s": 60, "holding_horizon_min": 15},
        risk_rule={"max_position_frac": 1.0},
        novelty_reason="baseline known family",
    )
    tweak = CandidateSpec(
        candidate_id="tweak",
        hypothesis="same hypothesis with only a horizon tweak",
        source_channel="BWE_OI_Price_monitor",
        family="oi_overcrowded_pump_reversal_short",
        discovery_layer="known_family_refinement",
        direction="short",
        entry_rule={"event_type": "pump", "oi_ratio_pct_gte": 10},
        filters={},
        exit_rule={"type": "fixed_horizon", "entry_delay_s": 60, "holding_horizon_min": 30},
        risk_rule={"max_position_frac": 1.0},
        novelty_reason="only holding horizon changed",
    )

    assert not is_new_strategy(tweak, base)


def test_is_new_strategy_accepts_new_alpha_or_material_exit_logic():
    from bwe_autoresearch.discovery import CandidateSpec, is_new_strategy

    base = CandidateSpec(
        candidate_id="base",
        hypothesis="OI pump overcrowding fades after delayed entry",
        source_channel="BWE_OI_Price_monitor",
        family="oi_overcrowded_pump_reversal_short",
        discovery_layer="known_family_refinement",
        direction="short",
        entry_rule={"event_type": "pump", "oi_ratio_pct_gte": 10},
        filters={},
        exit_rule={"type": "fixed_horizon", "entry_delay_s": 60, "holding_horizon_min": 15},
        risk_rule={"max_position_frac": 1.0},
        novelty_reason="baseline known family",
    )
    cross_channel = CandidateSpec(
        candidate_id="cross",
        hypothesis="Reserved6 pump plus later OI confirmation marks crowded exhaustion and should fade short",
        source_channel="BWE_Reserved6",
        family="r6_oi_confirm_pump_fade_short",
        discovery_layer="controlled_new_strategy_discovery",
        direction="short",
        entry_rule={"event_type": "pump", "move_pct_gte": 10, "confirm_after_5m_oi": True},
        filters={"liquidity_bucket_in": ["mid", "high"]},
        exit_rule={"type": "channel_invalidated_exit", "entry_delay_s": 30, "fallback_horizon_min": 60},
        risk_rule={"max_position_frac": 0.5},
        novelty_reason="new cross-channel alpha and material exit logic",
    )

    assert is_new_strategy(cross_channel, base)


def test_score_candidate_computes_metrics_and_promotion_category():
    from bwe_autoresearch.discovery import CandidateSpec, score_candidate

    rows = []
    for i in range(30):
        rows.append(
            {
                "channel": "BWE_pricechange_monitor",
                "post_id": i,
                "ts_ms": 1760000000000 + i * 60_000,
                "symbol": f"S{i % 6}USDT",
                "event_type": "pump",
                "side": "long",
                "entry_delay_s": 0,
                "net_5m": 0.012 if i < 24 else -0.006,
                "burst_seq_5m": 2,
                "liquidity_bucket": "high",
                "confirm_count_5m": 1,
            }
        )
    df = pd.DataFrame(rows)
    candidate = CandidateSpec(
        candidate_id="pc_second_signal_cont_long_test",
        hypothesis="Second pricechange pump confirms propagation and supports a short continuation long",
        source_channel="BWE_pricechange_monitor",
        family="pc_second_signal_cont_long",
        discovery_layer="controlled_new_strategy_discovery",
        direction="long",
        entry_rule={"event_type": "pump", "burst_seq_5m_eq": 2},
        filters={"liquidity_bucket_in": ["high"]},
        exit_rule={"type": "fixed_horizon", "entry_delay_s": 0, "holding_horizon_min": 5},
        risk_rule={"max_position_frac": 0.5},
        novelty_reason="uses repeat-trigger state as entry alpha",
    )

    result = score_candidate(df, candidate, min_sample=20)

    assert result["sample_size"] == 30
    assert result["win_rate_pct"] == 80.0
    assert result["median_net_pct"] > 0
    assert result["decision"] == "promote_to_paper"


def test_generate_hypotheses_respects_budget_and_contains_open_discovery():
    from bwe_autoresearch.discovery import generate_hypotheses

    candidates = generate_hypotheses(max_hypotheses=80)
    assert 20 <= len(candidates) <= 80
    layers = {c.discovery_layer for c in candidates}
    families = {c.family for c in candidates}
    assert "known_family_refinement" in layers
    assert "controlled_new_strategy_discovery" in layers
    assert "contrarian_exploratory" in layers
    assert "pc_second_signal_cont_long" in families
    assert "r6_oi_confirm_pump_fade_short" in families


def test_write_outputs_creates_required_artifacts(tmp_path):
    from bwe_autoresearch.discovery import CandidateSpec, write_outputs

    candidate = CandidateSpec(
        candidate_id="x",
        hypothesis="test",
        source_channel="BWE_Reserved6",
        family="r6_bigmove_pump_fade_short",
        discovery_layer="known_family_refinement",
        direction="short",
        entry_rule={"event_type": "pump"},
        filters={},
        exit_rule={"type": "fixed_horizon", "entry_delay_s": 0, "holding_horizon_min": 60},
        risk_rule={"max_position_frac": 0.5},
        novelty_reason="test",
    )
    rows = [
        {
            "candidate_id": "x",
            "family": "r6_bigmove_pump_fade_short",
            "decision": "watchlist",
            "sample_size": 10,
            "win_rate_pct": 60.0,
            "median_net_pct": 1.0,
            "mean_net_pct": 1.2,
            "score": 3.0,
        }
    ]
    write_outputs(tmp_path, [candidate], pd.DataFrame(rows), pd.DataFrame(rows))

    required = [
        "new_hypotheses.jsonl",
        "new_entry_candidates.jsonl",
        "new_exit_candidates.jsonl",
        "discovery_scoreboard.csv",
        "neighborhood_stability.csv",
        "hypothesis_reject_log.csv",
        "round1_discovery_report_zh.md",
    ]
    for name in required:
        assert (tmp_path / name).exists(), name
    first = json.loads((tmp_path / "new_hypotheses.jsonl").read_text().splitlines()[0])
    assert first["candidate_id"] == "x"
