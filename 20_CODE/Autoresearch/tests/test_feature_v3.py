import pandas as pd
import pytest


def test_feature_v3_refuses_live_paths():
    from bwe_autoresearch.feature_v3 import refuse_live_path

    with pytest.raises(ValueError):
        refuse_live_path("/tmp/bwe_live_autotrader_runtime")
    with pytest.raises(ValueError):
        refuse_live_path("/tmp/LaunchAgents/ai.hermes.bwe-live-autotrader")


def test_feature_v3_detects_future_fields():
    from bwe_autoresearch.feature_v3 import contains_future_field, is_future_safe_rule

    rule = {"entry_gate_rule": {"net_30m_gte": 0.01, "mfe": 2.0, "confirm_after_5m_oi": True}}
    found = contains_future_field(rule)
    assert "net_30m_gte" in found
    assert "mfe" in found
    assert "confirm_after_5m_oi" in found
    assert not is_future_safe_rule(rule)
    assert not is_future_safe_rule({"entry_gate_rule": {"ret_5m": 0.02}})
    assert is_future_safe_rule({"entry_gate_rule": {"funding_rate_gte": 0.0}})


def test_feature_v3_freshness_buckets():
    from bwe_autoresearch.feature_v3 import freshness_bucket

    assert freshness_bucket(60_000) == "fresh_le_5m"
    assert freshness_bucket(500_000) == "stale_5m_10m_deweighted"
    assert freshness_bucket(700_000) == "too_old_gt_10m"
    assert freshness_bucket(None) == "missing"


def test_feature_v3_mark_outcomes_tiny():
    from bwe_autoresearch.feature_v3 import compute_mark_outcomes

    events = pd.DataFrame(
        [
            {
                "event_key": "k1",
                "api_symbol": "AAAUSDT",
                "symbol": "AAA",
                "channel": "BWE_pricechange_monitor",
                "event_type": "pump",
                "ts_ms": 1_000_000,
                "month": "1970-01",
                "core_complete": True,
            }
        ]
    )
    mark = pd.DataFrame(
        {
            "api_symbol": ["AAAUSDT"] * 10,
            "mark_1m_open_time_ms": [1_000_000 + i * 60_000 for i in range(10)],
            "mark_1m_close": [100, 101, 102, 103, 104, 105, 104, 103, 102, 101],
        }
    )
    out = compute_mark_outcomes(events, mark, delays_s=(0,), horizons_min=(5,))
    assert set(out["side"]) == {"long", "short"}
    long = out[out["side"] == "long"].iloc[0]
    short = out[out["side"] == "short"].iloc[0]
    assert long["path_resolution"] == "1m_mark"
    assert long["mark_mfe_pct"] > 0
    assert short["mark_mae_pct"] < 0


def test_feature_v3_schema_contract_written(tmp_path):
    from bwe_autoresearch.feature_v3 import write_contract_artifacts

    events = pd.DataFrame({"core_complete": [True, False]})
    write_contract_artifacts(tmp_path, events)
    assert (tmp_path / "data_contract.md").exists()
    schema = (tmp_path / "v3_candidate_schema.json").read_text()
    assert "entry_gate_rule" in schema
    assert "live_allowed" in schema
    metric = (tmp_path / "v3_metric_contract.json").read_text()
    assert "feature_freshness" in metric
    contract = (tmp_path / "data_contract.md").read_text()
    assert "local_kline_rows=0" in contract
    assert "binance_status_active_now" in contract


def test_feature_v3_manifest_is_paper_only():
    from bwe_autoresearch.feature_v3 import make_manifest

    exit_leaderboard = pd.DataFrame(
        [
            {
                "decision": "promote_to_paper",
                "entry_candidate_id": "entry1",
                "exit_policy_id": "exit1",
                "channel": "BWE_pricechange_monitor",
                "event_type": "pump",
                "side": "long",
                "entry_delay_s": 60,
                "exit_family": "状态机型",
                "policy_json": '{"type":"state_machine"}',
                "path_resolution": "1m_mark",
                "sample_size": 100,
                "median_net_pct": 1.2,
                "p25_net_pct": -0.2,
                "win_rate_pct": 60.0,
                "mfe_capture_ratio": 0.5,
                "giveback_ratio_pct": 0.8,
            }
        ]
    )
    portfolio = pd.DataFrame([{"entry_candidate_id": "entry1", "exit_policy_id": "exit1"}])
    features = pd.DataFrame([{"use_decision": "use", "feature_packet": "taker_flow"}])
    manifest = make_manifest(exit_leaderboard, portfolio, features)
    assert manifest["paper_only"] is True
    assert manifest["live_allowed"] is False
    assert manifest["experiments"][0]["paper_only"] is True
    assert manifest["experiments"][0]["live_allowed"] is False
    assert manifest["experiments"][0]["required_clean_complete"] == 20
