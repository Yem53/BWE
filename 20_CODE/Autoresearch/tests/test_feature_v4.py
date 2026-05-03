import pandas as pd


def test_feature_v4_soft_filters_penalize_without_dropping_rows():
    from bwe_autoresearch.feature_v4 import add_soft_filter_penalties

    events = pd.DataFrame(
        [
            {
                "event_key": "bad",
                "is_tradable_at_event": False,
                "listing_age_days": 1,
                "quote_volume_24h": 1000,
                "marketcap": 1000,
                "mark_minus_index_proxy_pct": 0.5,
                "funding_age_ms": 700_000,
            },
            {
                "event_key": "good",
                "is_tradable_at_event": True,
                "listing_age_days": 40,
                "quote_volume_24h": 100_000_000,
                "marketcap": 1_000_000_000,
                "mark_minus_index_proxy_pct": 0.01,
                "funding_age_ms": 60_000,
            },
        ]
    )

    out = add_soft_filter_penalties(events)

    assert set(out["event_key"]) == {"bad", "good"}
    assert out.loc[out["event_key"].eq("bad"), "soft_filter_penalty"].iloc[0] > out.loc[out["event_key"].eq("good"), "soft_filter_penalty"].iloc[0]
    assert "not_tradable_at_event" in out.loc[out["event_key"].eq("bad"), "soft_filter_flags"].iloc[0]


def test_feature_v4_builds_multi_condition_rules_without_future_fields():
    from bwe_autoresearch.feature_v4 import build_deep_entry_rules, rule_future_fields

    events = pd.DataFrame(
        {
            "core_complete": [True] * 12,
            "channel": ["BWE_OI_Price_monitor"] * 12,
            "event_type": ["pump"] * 12,
            "oi_ratio_pct": list(range(10, 22)),
            "taker_buy_sell_volume__buySellRatio": [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.8, 2.0, 2.2, 2.5],
            "premium_1m_close": [0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1, 0.11],
            "quote_volume_24h": [1_000_000 + i * 100_000 for i in range(12)],
            "listing_age_days": [30] * 12,
        }
    )

    rules = build_deep_entry_rules(events, max_rules_per_context=80)

    assert rules
    assert any(len(rule.conditions) >= 2 for rule in rules)
    assert all(not rule_future_fields(rule) for rule in rules)


def test_feature_v4_decision_requires_stress_after_basic_quality():
    from bwe_autoresearch.feature_v4 import entry_v4_decision

    good = {
        "sample_size": 250,
        "symbol_count": 20,
        "median_net_pct": 0.8,
        "p25_net_pct": -0.4,
        "p10_net_pct": -1.4,
        "win_rate_pct": 61.0,
        "profit_factor": 1.6,
        "walk_forward_positive_rate_pct": 75.0,
        "remove_top_1pct_mean_net_pct": 0.2,
        "top_symbol_share_pct": 12.0,
        "stress_fee_slippage_mean_net_pct": 0.1,
    }
    bad_stress = dict(good, stress_fee_slippage_mean_net_pct=-0.1)

    assert entry_v4_decision(good, min_sample=100, complexity=4)[0] == "promote_to_paper"
    assert entry_v4_decision(bad_stress, min_sample=100, complexity=4) == ("watchlist", "stress_fee_slippage_weak")


def test_feature_v4_manifest_is_paper_only():
    from bwe_autoresearch.feature_v4 import make_entry_v4_manifest

    leaderboard = pd.DataFrame(
        [
            {
                "decision": "promote_to_paper",
                "candidate_id": "entry_v4_1",
                "channel": "BWE_OI_Price_monitor",
                "event_type": "pump",
                "action": "long",
                "entry_delay_s": 60,
                "horizon_min": 60,
                "conditions_json": "[]",
                "soft_filter_policy": "downgrade_not_exclude",
                "sample_size": 100,
                "median_net_pct": 1.0,
                "p25_net_pct": -0.3,
                "win_rate_pct": 62.0,
                "score": 10.0,
            }
        ]
    )

    manifest = make_entry_v4_manifest(leaderboard, max_items=5)

    assert manifest["paper_only"] is True
    assert manifest["live_allowed"] is False
    assert manifest["experiments"][0]["paper_only"] is True
    assert manifest["experiments"][0]["live_allowed"] is False
    assert manifest["experiments"][0]["entry_gate_rule"]["soft_filter_policy"] == "downgrade_not_exclude"


def test_feature_v4_no_trade_matrix_prefers_stable_candidate_over_reject_score():
    from bwe_autoresearch.feature_v4 import no_trade_matrix

    leaderboard = pd.DataFrame(
        [
            {
                "channel": "BWE_OI_Price_monitor",
                "event_type": "pump",
                "action": "long",
                "candidate_id": "stable",
                "entry_delay_s": 60,
                "horizon_min": 60,
                "sample_size": 120,
                "median_net_pct": 0.4,
                "p25_net_pct": -0.4,
                "score": 5.0,
                "decision": "promote_to_paper",
            },
            {
                "channel": "BWE_OI_Price_monitor",
                "event_type": "pump",
                "action": "long",
                "candidate_id": "same_direction_reject_high_score",
                "entry_delay_s": 60,
                "horizon_min": 60,
                "sample_size": 120,
                "median_net_pct": 1.1,
                "p25_net_pct": -1.3,
                "score": 60.0,
                "decision": "reject",
            },
            {
                "channel": "BWE_OI_Price_monitor",
                "event_type": "pump",
                "action": "short",
                "candidate_id": "reject_high_score",
                "entry_delay_s": 60,
                "horizon_min": 60,
                "sample_size": 120,
                "median_net_pct": 1.0,
                "p25_net_pct": -1.2,
                "score": 50.0,
                "decision": "reject",
            },
        ]
    )

    out = no_trade_matrix(leaderboard)

    row = out.iloc[0]
    assert row["recommended_action"] == "long"
    assert row["best_candidate_id"] == "stable"
