import json
from pathlib import Path

import pandas as pd


def test_feature_v5_loads_package_templates():
    from bwe_autoresearch.feature_v5 import DEFAULT_PACKAGE_DIR, load_templates

    templates = load_templates(DEFAULT_PACKAGE_DIR)

    assert len(templates) >= 80
    assert all("template_id" in item for item in templates)
    assert all(item["future_safety_rule"]["forbid_future_labels"] is True for item in templates)


def test_feature_v5_rejects_t0_confirm_after():
    from bwe_autoresearch.feature_v5 import static_legality_status

    candidate = {
        "entry_timing": "T0",
        "conditions_json": json.dumps([{"col": "confirm_after_5m_oi", "op": "eq", "value": True}]),
    }

    status, violation = static_legality_status(candidate)

    assert status == "reject"
    assert "t0_delayed_feature" in violation


def test_feature_v5_generates_large_manifest_from_templates(tmp_path):
    from bwe_autoresearch.feature_v5 import DEFAULT_PACKAGE_DIR, generate_candidate_manifest, load_templates

    templates = load_templates(DEFAULT_PACKAGE_DIR)[:3]
    df, summary = generate_candidate_manifest(templates, max_candidates_per_template=1200)

    assert len(df) >= 3000
    assert summary["raw_candidates"] == len(df)
    assert {"candidate_id", "template_id", "conditions_json", "coverage_valid"}.issubset(df.columns)


def test_feature_v5_manifest_is_paper_only():
    from bwe_autoresearch.feature_v5 import make_manifest_v5

    leaderboard = pd.DataFrame(
        [
            {
                "candidate_id": "v5_candidate_1",
                "template_id": "T001",
                "strategy_family": "F001",
                "sub_family": "oi_pump",
                "channel": "BWE_OI_Price_monitor",
                "event_type": "pump",
                "action": "long",
                "side": "long",
                "entry_timing": "1m",
                "entry_delay_s": 60,
                "horizon_min": 60,
                "conditions_json": "[]",
                "decision": "promote_to_paper",
                "sample_size": 120,
                "median_net_pct": 0.7,
                "p25_net_pct": -0.3,
                "p10_net_pct": -1.0,
                "win_rate_pct": 62.0,
                "profit_factor": 1.5,
                "robust_score": 10.0,
            }
        ]
    )

    manifest = make_manifest_v5(leaderboard, max_items=10)

    assert manifest["paper_only"] is True
    assert manifest["live_allowed"] is False
    assert manifest["experiments"][0]["paper_only"] is True
    assert manifest["experiments"][0]["live_allowed"] is False
    assert manifest["experiments"][0]["exit_interface_only"] is True


def test_feature_v5_score_candidate_exposes_stress_gate_field():
    from bwe_autoresearch.feature_v5 import score_candidate

    entry_outcomes = pd.DataFrame(
        [
            {
                "side": "long",
                "channel": "BWE_OI_Price_monitor",
                "event_type": "pump",
                "entry_delay_s": 0,
                "horizon_min": 30,
                "mark_net_pct": 1.0,
                "api_symbol": f"SYM{i}USDT",
                "ts_ms": 1_000_000 + i * 60_000,
                "soft_filter_penalty": 0.0,
            }
            for i in range(30)
        ]
    )
    row = pd.Series(
        {
            "candidate_id": "c1",
            "template_id": "T001",
            "strategy_family": "F001",
            "sub_family": "x",
            "channel": "BWE_OI_Price_monitor",
            "event_type": "pump",
            "action": "long",
            "side": "long",
            "entry_timing": "T0",
            "entry_delay_s": 0,
            "horizon_min": 30,
            "conditions_json": "[]",
            "complexity_score": 1,
        }
    )

    scored, _ = score_candidate(entry_outcomes, row)

    assert scored["stress_fee_slippage_mean_net_pct"] > 0
