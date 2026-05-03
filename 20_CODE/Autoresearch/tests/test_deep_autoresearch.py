import json

import pandas as pd


def test_entry_catalog_has_required_scale_and_unique_ids():
    from bwe_autoresearch.deep_autoresearch import build_entry_archetypes, generate_entry_catalog

    archetypes = build_entry_archetypes()
    catalog = generate_entry_catalog(archetypes)

    assert len(archetypes) >= 100
    assert len(catalog) >= 100_000
    assert catalog["branch_id"].is_unique
    assert catalog.groupby("archetype_id")["branch_id"].count().min() >= 1_000


def test_exit_catalog_has_required_scale_and_unique_ids():
    from bwe_autoresearch.deep_autoresearch import build_exit_archetypes, generate_exit_catalog

    archetypes = build_exit_archetypes()
    catalog = generate_exit_catalog(archetypes)

    assert len(archetypes) >= 100
    assert len(catalog) >= 100_000
    assert catalog["branch_id"].is_unique
    assert catalog.groupby("archetype_id")["branch_id"].count().min() >= 1_000


def test_all_exit_families_have_dynamic_evaluators():
    from bwe_autoresearch.deep_autoresearch import (
        FAST_EXIT_EVALUATORS,
        build_exit_archetypes,
    )

    archetypes = build_exit_archetypes()
    families = {x.family for x in archetypes}

    assert all(x.scorable for x in archetypes)
    assert families <= set(FAST_EXIT_EVALUATORS)


def test_each_exit_family_evaluator_scores_a_tiny_bundle():
    from bwe_autoresearch.deep_autoresearch import (
        FAST_EXIT_EVALUATORS,
        build_exit_archetypes,
        build_strategy_bundle,
        generate_exit_catalog,
    )

    rows_df = pd.DataFrame(
        [
            {"event_key": "BWE_pricechange_monitor#fam1", "month": "2026-04", "entry_ts_ms": 1_760_000_000_000, "entry_px": 100.0, "side": "long"},
            {"event_key": "BWE_pricechange_monitor#fam2", "month": "2026-04", "entry_ts_ms": 1_760_000_600_000, "entry_px": 100.0, "side": "long"},
        ]
    )
    path_rows = []
    for event_key, offset, closes in [
        ("BWE_pricechange_monitor#fam1", 0, [100, 101, 103, 106, 104, 102, 101]),
        ("BWE_pricechange_monitor#fam2", 600_000, [100, 99, 100, 102, 101, 98, 97]),
    ]:
        base_ts = 1_760_000_000_000 + offset
        for idx, close in enumerate(closes):
            path_rows.append(
                {
                    "event_key": event_key,
                    "channel": "BWE_pricechange_monitor",
                    "post_id": event_key.split("#")[1],
                    "symbol": "S",
                    "exchange": "X",
                    "alias": "A",
                    "event_ts_ms": base_ts,
                    "bar_ts_ms": base_ts + idx * 300_000,
                    "open": close,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                    "volume": 1.0 + idx,
                    "quote_volume": 10.0 + idx,
                }
            )
    bundle = build_strategy_bundle(
        rows_df,
        pd.DataFrame(path_rows),
        {"hard_stop_pct": 4.0, "activation_delay_min": 0, "catastrophe_stop_pct": 6.0},
    )
    archetypes = build_exit_archetypes()
    for archetype in archetypes:
        first_branch = generate_exit_catalog([archetype]).iloc[0]
        params = json.loads(first_branch.params_json)
        evaluator = FAST_EXIT_EVALUATORS[archetype.family]
        values, reasons, labels = evaluator(bundle, params)
        assert values.shape[0] == 2
        assert reasons.shape[0] == 2
        assert labels


def test_output_path_guardrail_rejects_live_paths():
    from bwe_autoresearch.deep_autoresearch import _is_output_path_safe, refuse_if_live_path

    assert _is_output_path_safe("/tmp/research_run")
    assert not _is_output_path_safe("/tmp/bwe_live_autotrader/output")

    try:
        refuse_if_live_path("/tmp/LaunchAgents/research")
    except ValueError:
        pass
    else:
        raise AssertionError("expected live path guardrail to raise")


def test_tiny_entry_scoring_scores_some_branches(tmp_path):
    from bwe_autoresearch.deep_autoresearch import (
        build_entry_archetypes,
        generate_entry_catalog,
        score_entry_catalog,
    )

    rows = []
    for i in range(40):
        rows.append(
            {
                "channel": "BWE_OI_Price_monitor",
                "side": "short",
                "event_type": "pump",
                "oi_ratio_pct": 12.0,
                "day_change_pct": 14.0,
                "entry_delay_s": [0, 10, 30, 60, 180][i % 5],
                "liquidity_bucket": ["low", "mid", "high"][i % 3],
                "marketcap_bucket_norm": ["<50m", "50m-200m", "200m-1b", ">=1b", "unknown"][i % 5],
                "btc_regime": ["btc_down", "btc_flat", "btc_up"][i % 3],
                "trend_alignment": ["aligned", "counter"][i % 2],
                "ts_ms": 1_760_000_000_000 + i * 60_000,
                "month": "2026-04",
                "symbol": f"S{i % 6}",
                "regime_state": "neutral",
                "market_type": "perp",
                "net_3m": 0.004 if i < 28 else -0.003,
                "net_5m": 0.006 if i < 30 else -0.003,
                "net_10m": 0.008 if i < 30 else -0.004,
                "net_15m": 0.010 if i < 32 else -0.004,
                "net_30m": 0.012 if i < 32 else -0.005,
                "net_60m": 0.014 if i < 34 else -0.006,
                "confirm_after_5m_reserved6": False,
                "confirm_before_5m_pricechange": False,
                "burst_seq_5m": 1,
                "mfe_pct": 4.0,
                "mae_pct": -2.0,
                "vol_regime": "warm",
            }
        )
    forward = pd.DataFrame(rows)
    archetype = next(x for x in build_entry_archetypes() if x.archetype_id == "g01_base")
    catalog = generate_entry_catalog([archetype])
    progress = {
        "requested_out_dir": str(tmp_path),
        "actual_out_dir": str(tmp_path),
        "used_fallback_out_dir": False,
        "status": "running",
        "stage": "test",
        "last_updated_at": "",
    }

    scores = score_entry_catalog(forward, catalog, [archetype], tmp_path, progress)

    assert scores.shape[0] == catalog.shape[0]
    assert int((scores["sample_size"] > 0).sum()) > 0
    assert set(scores["decision"].unique()) <= {"promote_to_deep_exit", "watchlist", "reject", "need_more_data"}


def test_tiny_exit_scoring_scores_some_branches():
    from bwe_autoresearch.deep_autoresearch import (
        build_strategy_bundle,
        build_exit_archetypes,
        evaluate_fixed_tp_full_bundle,
        generate_exit_catalog,
        summarize_exit_vector,
    )

    rows_df = pd.DataFrame(
        [
            {
                "event_key": "BWE_pricechange_monitor#1",
                "month": "2026-04",
                "entry_ts_ms": 1_760_000_000_000,
                "entry_px": 100.0,
                "side": "long",
            },
            {
                "event_key": "BWE_pricechange_monitor#2",
                "month": "2026-04",
                "entry_ts_ms": 1_760_000_600_000,
                "entry_px": 100.0,
                "side": "long",
            },
        ]
    )
    path_rows = []
    for event_key, offset, closes in [
        ("BWE_pricechange_monitor#1", 0, [100, 102, 106, 108, 107, 105]),
        ("BWE_pricechange_monitor#2", 600_000, [100, 99, 98, 97, 96, 95]),
    ]:
        base_ts = 1_760_000_000_000 + offset
        for idx, close in enumerate(closes):
            path_rows.append(
                {
                    "event_key": event_key,
                    "channel": "BWE_pricechange_monitor",
                    "post_id": event_key.split("#")[1],
                    "symbol": "S",
                    "exchange": "X",
                    "alias": "A",
                    "event_ts_ms": base_ts,
                    "bar_ts_ms": base_ts + idx * 300_000,
                    "open": close,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                    "volume": 1.0,
                    "quote_volume": 10.0,
                }
            )
    path_df = pd.DataFrame(path_rows)
    base = {"hard_stop_pct": 4.0, "activation_delay_min": 0, "catastrophe_stop_pct": 6.0}
    bundle = build_strategy_bundle(rows_df, path_df, base)

    archetype = next(x for x in build_exit_archetypes() if x.archetype_id == "fixed_tp_full__balanced")
    catalog = generate_exit_catalog([archetype]).head(3)
    summaries = []
    for row in catalog.itertuples(index=False):
        params = json.loads(row.params_json)
        values, reasons, labels = evaluate_fixed_tp_full_bundle(bundle, params)
        summaries.append(summarize_exit_vector(values, bundle["months"], reasons, labels))

    assert len(summaries) == 3
    assert all(x["sample_size"] == 2 for x in summaries)
    assert any(x["mean_net_pct"] != 0 for x in summaries)
