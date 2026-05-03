---
type: moc
tags: [moc, strategy-search, bwe-codex]
updated: 2026-05-03T18:30:27-04:00
status: active
---

# Strategy Search MOC

## Objective

- Long and short scanner-native common yaobi strategies, not one-symbol overfit.
- Numeric gates: sample-out win > 85%, monthly >= 500, sum > 5000%, mean >= 8%, after conservative execution costs.
- Robust gates include validation split, concentration cap, and execution realism.

## Evidence Spine

- [[codex_discovery/notes/2026-05-02_goal_strategy_search_progress|Goal strategy search progress]]
- [[codex_discovery/runs/20260503T051140Z_market_native_micro_stream/market_native_micro_stream|Focused scanner-native microstructure search]]
- [[codex_discovery/runs/20260503T055317Z_market_native_quality_exact/market_native_quality_exact|Quality-diverse scanner-native exact replay]]
- [[codex_discovery/runs/20260503T061922Z_market_native_portfolio_combo/market_native_portfolio_combo|Short scanner-native portfolio combo replay]]
- [[codex_discovery/runs/20260503T062415Z_market_native_portfolio_combo/market_native_portfolio_combo|Long scanner-native portfolio combo replay]]
- [[codex_discovery/runs/20260503T021854Z_exact_v6_state_machine_replay_all_objective_unique/exact_v6_state_machine_replay|Strict high/low all-objective replay]]
- [[codex_discovery/runs/20260503T001701Z_short_oracle_exit_refine/short_oracle_exit_refine|Short oracle exit refinement]]
- [[30_REPORTS/2026-05-02_exact_high_low_retest|Strict High/Low Retest Report]]
- [[paper_test/v6_982b322524d6a28283/README|v6_982 paper/demo runner]]
- [[paper_test/v6_982b322524d6a28283/reports/2026-05-03_marketcap_filter_impact|Market-cap filter impact]]
- [[paper_test/v6_982b322524d6a28283/reports/2026-05-03_paper_demo_setup_status|Paper/demo setup status]]
- [[paper_test/v6_multi_8/README|Multi-9 paper/demo runner]]
- [[paper_test/v6_multi_8/reports/2026-05-03_multi8_paper_setup_status|Multi-9 setup status]]

## Run Inventory

| Run | Primary Note | CSV Count | Pass Summary |
|---|---|---:|---|
| `20260502T220322Z_minute_grid` |  | 8380 | obj= robust= long= short= |
| `20260502T220503Z_minute_grid` |  | 15000 | obj= robust= long= short= |
| `20260502T221043Z_minute_grid` |  | 497180 | obj= robust= long= short= |
| `20260502T224111Z_micro_exact` |  | 31596 | obj= robust= long= short= |
| `20260502T224919Z_cooldown_stress` |  | 70756 | obj= robust= long= short= |
| `20260502T231209Z_v6_archive_audit` | [[codex_discovery/runs/20260502T231209Z_v6_archive_audit/v6_archive_audit|v6_archive_audit.md]] | 665725 | obj=33380 robust= long= short= |
| `20260502T231604Z_v6_archive_replay` |  | 0 | obj= robust= long= short= |
| `20260502T231648Z_v6_archive_replay` |  | 0 | obj= robust= long= short= |
| `20260502T231744Z_v6_archive_replay` | [[codex_discovery/runs/20260502T231744Z_v6_archive_replay/v6_archive_replay|v6_archive_replay.md]] | 60 | obj=60 robust= long=60 short=0 |
| `20260502T232042Z_bwe_event_short_grid` |  | 0 | obj= robust= long= short= |
| `20260502T232524Z_bwe_event_short_grid` |  | 0 | obj= robust= long= short= |
| `20260502T233019Z_bwe_event_short_grid` | [[codex_discovery/runs/20260502T233019Z_bwe_event_short_grid/short_grid|short_grid.md]] | 8346 | obj=0 robust= long= short= |
| `20260502T233635Z_second_level_gap_audit` | [[codex_discovery/runs/20260502T233635Z_second_level_gap_audit/second_level_gap_audit|second_level_gap_audit.md]] | 20 | obj= robust= long= short= |
| `20260502T234314Z_aggtrade_entry_smoke` | [[codex_discovery/runs/20260502T234314Z_aggtrade_entry_smoke/aggtrade_entry_smoke|aggtrade_entry_smoke.md]] | 25 | obj= robust= long= short= |
| `20260502T234505Z_aggtrade_entry_smoke` | [[codex_discovery/runs/20260502T234505Z_aggtrade_entry_smoke/aggtrade_entry_smoke|aggtrade_entry_smoke.md]] | 25 | obj= robust= long= short= |
| `20260502T235046Z_short_reversal_exact` |  | 0 | obj= robust= long= short= |
| `20260502T235456Z_short_reversal_exact` | [[codex_discovery/runs/20260502T235456Z_short_reversal_exact/short_reversal_exact|short_reversal_exact.md]] | 23283 | obj=0 robust=0 long= short= |
| `20260503T000552Z_aggtrade_top_v6_entry_smoke` | [[codex_discovery/runs/20260503T000552Z_aggtrade_top_v6_entry_smoke/aggtrade_top_v6_entry_smoke|aggtrade_top_v6_entry_smoke.md]] | 100 | obj= robust= long= short= |
| `20260503T000956Z_short_oracle_mfe` | [[codex_discovery/runs/20260503T000956Z_short_oracle_mfe/short_oracle_mfe|short_oracle_mfe.md]] | 1318 | obj= robust= long= short= |
| `20260503T001701Z_short_oracle_exit_refine` | [[codex_discovery/runs/20260503T001701Z_short_oracle_exit_refine/short_oracle_exit_refine|short_oracle_exit_refine.md]] | 2972 | obj=0 robust=0 long= short= |
| `20260503T005019Z_short_focused_exact` |  | 0 | obj= robust= long= short= |
| `20260503T005248Z_short_focused_exact` |  | 3427 | obj= robust= long= short= |
| `20260503T005435Z_short_focused_exact` | [[codex_discovery/runs/20260503T005435Z_short_focused_exact/short_focused_exact|short_focused_exact.md]] | 3477 | obj=0 robust=0 long= short= |
| `20260503T005615Z_short_focused_exact` | [[codex_discovery/runs/20260503T005615Z_short_focused_exact/short_focused_exact|short_focused_exact.md]] | 3514 | obj=0 robust=0 long= short= |
| `20260503T005819Z_short_focused_exact` | [[codex_discovery/runs/20260503T005819Z_short_focused_exact/short_focused_exact|short_focused_exact.md]] | 3945 | obj=0 robust=0 long= short= |
| `20260503T011206Z_short_combo_exact` | [[codex_discovery/runs/20260503T011206Z_short_combo_exact/short_combo_exact|short_combo_exact.md]] | 80 | obj=0 robust=0 long= short= |
| `20260503T011539Z_short_combo_exact` | [[codex_discovery/runs/20260503T011539Z_short_combo_exact/short_combo_exact|short_combo_exact.md]] | 101 | obj=0 robust=0 long= short= |
| `20260503T011807Z_short_combo_exact` | [[codex_discovery/runs/20260503T011807Z_short_combo_exact/short_combo_exact|short_combo_exact.md]] | 1064 | obj=0 robust=0 long= short= |
| `20260503T012141Z_short_combo_exact` | [[codex_discovery/runs/20260503T012141Z_short_combo_exact/short_combo_exact|short_combo_exact.md]] | 1315 | obj=0 robust=0 long= short= |
| `20260503T012604Z_short_combo_exact` | [[codex_discovery/runs/20260503T012604Z_short_combo_exact/short_combo_exact|short_combo_exact.md]] | 1715 | obj=0 robust=0 long= short= |
| `20260503T021050Z_exact_v6_state_machine_replay` | [[codex_discovery/runs/20260503T021050Z_exact_v6_state_machine_replay/exact_v6_state_machine_replay|exact_v6_state_machine_replay.md]] | 79 | obj=19 robust= long=19 short=0 |
| `20260503T021708Z_exact_v6_state_machine_replay_dry20` | [[codex_discovery/runs/20260503T021708Z_exact_v6_state_machine_replay_dry20/exact_v6_state_machine_replay|exact_v6_state_machine_replay.md]] | 44 | obj=2 robust= long=2 short=0 |
| `20260503T021807Z_exact_v6_state_machine_replay_dry20_masked` | [[codex_discovery/runs/20260503T021807Z_exact_v6_state_machine_replay_dry20_masked/exact_v6_state_machine_replay|exact_v6_state_machine_replay.md]] | 44 | obj=2 robust= long=2 short=0 |
| `20260503T021854Z_exact_v6_state_machine_replay_all_objective_unique` | [[codex_discovery/runs/20260503T021854Z_exact_v6_state_machine_replay_all_objective_unique/exact_v6_state_machine_replay|exact_v6_state_machine_replay.md]] | 48912 | obj=5221 robust= long=5221 short=0 |
| `20260503T043743Z_market_native_micro_stream` | [[codex_discovery/runs/20260503T043743Z_market_native_micro_stream/market_native_micro_stream|market_native_micro_stream.md]] | 900 | obj=0 robust= long= short= |
| `20260503T043832Z_market_native_micro_stream` | [[codex_discovery/runs/20260503T043832Z_market_native_micro_stream/market_native_micro_stream|market_native_micro_stream.md]] | 15373 | obj=0 robust= long= short= |
| `20260503T051055Z_market_native_micro_stream` | [[codex_discovery/runs/20260503T051055Z_market_native_micro_stream/market_native_micro_stream|market_native_micro_stream.md]] | 610 | obj=0 robust= long= short= |
| `20260503T051140Z_market_native_micro_stream` | [[codex_discovery/runs/20260503T051140Z_market_native_micro_stream/market_native_micro_stream|market_native_micro_stream.md]] | 49410 | obj=0 robust= long= short= |
| `20260503T055257Z_market_native_quality_exact` | [[codex_discovery/runs/20260503T055257Z_market_native_quality_exact/market_native_quality_exact|market_native_quality_exact.md]] | 140 | obj=0 robust= long= short= |
| `20260503T055317Z_market_native_quality_exact` | [[codex_discovery/runs/20260503T055317Z_market_native_quality_exact/market_native_quality_exact|market_native_quality_exact.md]] | 63130 | obj=0 robust= long= short= |
| `20260503T061904Z_market_native_portfolio_combo` | [[codex_discovery/runs/20260503T061904Z_market_native_portfolio_combo/market_native_portfolio_combo|market_native_portfolio_combo.md]] | 48 | obj=0 robust= long=0 short=0 |
| `20260503T061922Z_market_native_portfolio_combo` | [[codex_discovery/runs/20260503T061922Z_market_native_portfolio_combo/market_native_portfolio_combo|market_native_portfolio_combo.md]] | 2100 | obj=0 robust= long=0 short=0 |
| `20260503T062415Z_market_native_portfolio_combo` | [[codex_discovery/runs/20260503T062415Z_market_native_portfolio_combo/market_native_portfolio_combo|market_native_portfolio_combo.md]] | 1580 | obj=0 robust= long=0 short=0 |
| `20260503T063405Z_market_native_micro_stream` | [[codex_discovery/runs/20260503T063405Z_market_native_micro_stream/market_native_micro_stream|market_native_micro_stream.md]] | 10 | obj=0 robust= long= short= |
| `20260503T063445Z_market_native_micro_stream` |  | 0 | obj= robust= long= short= |
| `20260503T063654Z_market_native_micro_stream` | [[codex_discovery/runs/20260503T063654Z_market_native_micro_stream/market_native_micro_stream|market_native_micro_stream.md]] | 201 | obj=0 robust= long= short= |
| `20260503T063742Z_market_native_micro_stream` | [[codex_discovery/runs/20260503T063742Z_market_native_micro_stream/market_native_micro_stream|market_native_micro_stream.md]] | 42132 | obj=0 robust= long= short= |
| `20260503T070842Z_market_native_event_ranker` | [[codex_discovery/runs/20260503T070842Z_market_native_event_ranker/market_native_event_ranker|market_native_event_ranker.md]] | 140 | obj= robust= long= short= |
| `20260503T070931Z_market_native_event_ranker` | [[codex_discovery/runs/20260503T070931Z_market_native_event_ranker/market_native_event_ranker|market_native_event_ranker.md]] | 58522 | obj= robust= long= short= |
| `20260503T072723Z_market_native_cross_section_ranker` | [[codex_discovery/runs/20260503T072723Z_market_native_cross_section_ranker/market_native_cross_section_ranker|market_native_cross_section_ranker.md]] | 136 | obj= robust= long= short= |
| `20260503T072735Z_market_native_cross_section_ranker` | [[codex_discovery/runs/20260503T072735Z_market_native_cross_section_ranker/market_native_cross_section_ranker|market_native_cross_section_ranker.md]] | 35590 | obj= robust= long= short= |
| `20260503T074220Z_market_native_oracle_ceiling` | [[codex_discovery/runs/20260503T074220Z_market_native_oracle_ceiling/market_native_oracle_ceiling|market_native_oracle_ceiling.md]] | 152 | obj= robust= long= short= |
| `20260503T074233Z_market_native_oracle_ceiling` | [[codex_discovery/runs/20260503T074233Z_market_native_oracle_ceiling/market_native_oracle_ceiling|market_native_oracle_ceiling.md]] | 52638 | obj= robust= long= short= |
| `20260503T074742Z_market_native_extended_exits` |  | 54 | obj= robust= long= short= |
| `20260503T074800Z_market_native_extended_exits` | [[codex_discovery/runs/20260503T074800Z_market_native_extended_exits/market_native_extended_exits|market_native_extended_exits.md]] | 114 | obj= robust= long= short= |
| `20260503T074812Z_market_native_extended_exits` | [[codex_discovery/runs/20260503T074812Z_market_native_extended_exits/market_native_extended_exits|market_native_extended_exits.md]] | 29791 | obj= robust= long= short= |
| `20260503T075353Z_extended_exit_score_filter` | [[codex_discovery/runs/20260503T075353Z_extended_exit_score_filter/extended_exit_score_filter|extended_exit_score_filter.md]] | 0 | obj= robust= long= short= |
| `20260503T075400Z_extended_exit_score_filter` | [[codex_discovery/runs/20260503T075400Z_extended_exit_score_filter/extended_exit_score_filter|extended_exit_score_filter.md]] | 6037 | obj= robust= long= short= |
| `20260503T080755Z_market_native_leaf_selector` | [[codex_discovery/runs/20260503T080755Z_market_native_leaf_selector/market_native_leaf_selector|market_native_leaf_selector.md]] | 0 | obj= robust= long= short= |
| `20260503T080810Z_market_native_leaf_selector` | [[codex_discovery/runs/20260503T080810Z_market_native_leaf_selector/ABANDONED|ABANDONED.md]] | 0 | obj= robust= long= short= |
| `20260503T081359Z_market_native_leaf_selector` | [[codex_discovery/runs/20260503T081359Z_market_native_leaf_selector/market_native_leaf_selector|market_native_leaf_selector.md]] | 8360 | obj= robust= long= short= |
| `20260503T084136Z_market_native_delayed_entries` | [[codex_discovery/runs/20260503T084136Z_market_native_delayed_entries/market_native_delayed_entries|market_native_delayed_entries.md]] | 693 | obj= robust= long= short= |
| `20260503T084154Z_market_native_delayed_entries` | [[codex_discovery/runs/20260503T084154Z_market_native_delayed_entries/market_native_delayed_entries|market_native_delayed_entries.md]] | 637027 | obj= robust= long= short= |
| `20260503T091237Z_delayed_entry_score_filter` | [[codex_discovery/runs/20260503T091237Z_delayed_entry_score_filter/delayed_entry_score_filter|delayed_entry_score_filter.md]] | 8487 | obj= robust= long= short= |
| `20260503T092604Z_delayed_score_portfolio_combo` | [[codex_discovery/runs/20260503T092604Z_delayed_score_portfolio_combo/delayed_score_portfolio_combo|delayed_score_portfolio_combo.md]] | 2540 | obj= robust= long=0 short=0 |
| `20260503T092823Z_delayed_score_portfolio_combo` | [[codex_discovery/runs/20260503T092823Z_delayed_score_portfolio_combo/delayed_score_portfolio_combo|delayed_score_portfolio_combo.md]] | 2080 | obj= robust= long=0 short=0 |
| `20260503T094019Z_delayed_exit_refine` | [[codex_discovery/runs/20260503T094019Z_delayed_exit_refine/delayed_exit_refine|delayed_exit_refine.md]] | 391 | obj= robust= long= short= |
| `20260503T095023Z_dense_anomaly_oracle_ceiling` | [[codex_discovery/runs/20260503T095023Z_dense_anomaly_oracle_ceiling/dense_anomaly_oracle_ceiling|dense_anomaly_oracle_ceiling.md]] | 500031 | obj= robust= long= short= |
| `20260503T100610Z_dense_anomaly_oracle_selector` |  | 0 | obj= robust= long= short= |
| `20260503T101016Z_dense_anomaly_oracle_selector` | [[codex_discovery/runs/20260503T101016Z_dense_anomaly_oracle_selector/INVALID|INVALID.md]] | 1939 | obj= robust= long= short= |
| `20260503T101602Z_dense_anomaly_oracle_selector` | [[codex_discovery/runs/20260503T101602Z_dense_anomaly_oracle_selector/dense_anomaly_oracle_selector|dense_anomaly_oracle_selector.md]] | 2216 | obj= robust= long= short= |
| `20260503T102029Z_dense_anomaly_selector_real_exits` | [[codex_discovery/runs/20260503T102029Z_dense_anomaly_selector_real_exits/dense_anomaly_selector_real_exits|dense_anomaly_selector_real_exits.md]] | 276 | obj= robust= long= short= |
| `20260503T102332Z_dense_anomaly_selector_real_exits` | [[codex_discovery/runs/20260503T102332Z_dense_anomaly_selector_real_exits/dense_anomaly_selector_real_exits|dense_anomaly_selector_real_exits.md]] | 888 | obj= robust= long= short= |
| `20260503T102900Z_dense_selector_delayed_entries` | [[codex_discovery/runs/20260503T102900Z_dense_selector_delayed_entries/dense_selector_delayed_entries|dense_selector_delayed_entries.md]] | 952490 | obj= robust= long= short= |
| `20260503T104154Z_dense_delayed_score_filter` | [[codex_discovery/runs/20260503T104154Z_dense_delayed_score_filter/dense_delayed_score_filter|dense_delayed_score_filter.md]] | 10287 | obj= robust= long= short= |
| `20260503T110534Z_market_native_event_ranker` | [[codex_discovery/runs/20260503T110534Z_market_native_event_ranker/market_native_event_ranker|market_native_event_ranker.md]] | 60161 | obj= robust= long= short= |
| `20260503T114338Z_event_ranker_real_label_selector` | [[codex_discovery/runs/20260503T114338Z_event_ranker_real_label_selector/event_ranker_real_label_selector|event_ranker_real_label_selector.md]] | 10000 | obj= robust= long= short= |
| `20260503T125920Z_event_ranker_beam_selector` | [[codex_discovery/runs/20260503T125920Z_event_ranker_beam_selector/event_ranker_beam_selector|event_ranker_beam_selector.md]] | 10080 | obj= robust= long= short= |
| `20260503T131027Z_dense_anomaly_event_source` | [[codex_discovery/runs/20260503T131027Z_dense_anomaly_event_source/dense_anomaly_event_source|dense_anomaly_event_source.md]] | 749784 | obj= robust= long= short= |
| `20260503T132344Z_dense_anomaly_real_exit_selector` |  | 749784 | obj= robust= long= short= |
| `20260503T133935Z_dense_anomaly_real_exit_selector` | [[codex_discovery/runs/20260503T133935Z_dense_anomaly_real_exit_selector/dense_anomaly_real_exit_selector|dense_anomaly_real_exit_selector.md]] | 4139 | obj= robust= long= short= |
| `20260503T135622Z_market_native_cross_section_ranker` | [[codex_discovery/runs/20260503T135622Z_market_native_cross_section_ranker/market_native_cross_section_ranker|market_native_cross_section_ranker.md]] | 34893 | obj= robust= long= short= |
| `20260503T141634Z_market_native_delayed_entries` | [[codex_discovery/runs/20260503T141634Z_market_native_delayed_entries/market_native_delayed_entries|market_native_delayed_entries.md]] | 646564 | obj= robust= long= short= |
| `20260503T145947Z_delayed_entry_score_filter` | [[codex_discovery/runs/20260503T145947Z_delayed_entry_score_filter/delayed_entry_score_filter|delayed_entry_score_filter.md]] | 9716 | obj= robust= long= short= |
| `20260503T151957Z_delayed_score_portfolio_combo` | [[codex_discovery/runs/20260503T151957Z_delayed_score_portfolio_combo/delayed_score_portfolio_combo|delayed_score_portfolio_combo.md]] | 5120 | obj= robust= long=0 short=0 |
| `20260503T153431Z_market_native_extended_exits` | [[codex_discovery/runs/20260503T153431Z_market_native_extended_exits/market_native_extended_exits|market_native_extended_exits.md]] | 29997 | obj= robust= long= short= |
| `20260503T153630Z_market_native_leaf_selector` | [[codex_discovery/runs/20260503T153630Z_market_native_leaf_selector/market_native_leaf_selector|market_native_leaf_selector.md]] | 9200 | obj= robust= long= short= |
| `20260503T155114Z_extended_exit_score_filter` | [[codex_discovery/runs/20260503T155114Z_extended_exit_score_filter/extended_exit_score_filter|extended_exit_score_filter.md]] | 6043 | obj= robust= long= short= |
| `20260503T155235Z_market_native_veto_selector` | [[codex_discovery/runs/20260503T155235Z_market_native_veto_selector/market_native_veto_selector|market_native_veto_selector.md]] | 10000 | obj= robust= long= short= |
| `20260503T161417Z_event_ranker_leaf_union_portfolio` |  | 0 | obj= robust= long= short= |
| `20260503T161456Z_event_ranker_leaf_union_portfolio` | [[codex_discovery/runs/20260503T161456Z_event_ranker_leaf_union_portfolio/event_ranker_leaf_union_portfolio|event_ranker_leaf_union_portfolio.md]] | 16630 | obj= robust= long=0 short=0 |
| `20260503T161615Z_event_ranker_leaf_union_portfolio` | [[codex_discovery/runs/20260503T161615Z_event_ranker_leaf_union_portfolio/event_ranker_leaf_union_portfolio|event_ranker_leaf_union_portfolio.md]] | 15794 | obj= robust= long=0 short=0 |
| `20260503T162815Z_premium_crowding_reversal` | [[codex_discovery/runs/20260503T162815Z_premium_crowding_reversal/premium_crowding_reversal|premium_crowding_reversal.md]] | 326 | obj= robust= long= short= |
| `20260503T162840Z_premium_crowding_reversal` | [[codex_discovery/runs/20260503T162840Z_premium_crowding_reversal/premium_crowding_reversal|premium_crowding_reversal.md]] | 15340 | obj= robust= long= short= |
| `20260503T164305Z_premium_crowding_extended_exits` | [[codex_discovery/runs/20260503T164305Z_premium_crowding_extended_exits/premium_crowding_extended_exits|premium_crowding_extended_exits.md]] | 19514 | obj= robust= long= short= |
| `20260503T164636Z_dense_anomaly_real_exit_selector` |  | 749784 | obj= robust= long= short= |
| `20260503T171009Z_oracle_leaf_highlock_transfer` | [[codex_discovery/runs/20260503T171009Z_oracle_leaf_highlock_transfer/oracle_leaf_highlock_transfer|oracle_leaf_highlock_transfer.md]] | 55559 | obj= robust= long= short= |
| `20260503T171445Z_oracle_leaf_partial_transfer` | [[codex_discovery/runs/20260503T171445Z_oracle_leaf_partial_transfer/oracle_leaf_partial_transfer|oracle_leaf_partial_transfer.md]] | 56199 | obj= robust= long= short= |
| `20260503T172258Z_oracle_leaf_confirmed_entry_transfer` | [[codex_discovery/runs/20260503T172258Z_oracle_leaf_confirmed_entry_transfer/oracle_leaf_confirmed_entry_transfer|oracle_leaf_confirmed_entry_transfer.md]] | 60039 | obj= robust= long= short= |
| `20260503T172908Z_dense_real_beam_selector` | [[codex_discovery/runs/20260503T172908Z_dense_real_beam_selector/dense_real_beam_selector|dense_real_beam_selector.md]] | 3200 | obj= robust= long= short= |
| `20260503T174951Z_market_regime_augmentation` | [[codex_discovery/runs/20260503T174951Z_market_regime_augmentation/market_regime_augmentation|market_regime_augmentation.md]] | 793937 | obj= robust= long= short= |
| `20260503T175306Z_dense_real_beam_selector` | [[codex_discovery/runs/20260503T175306Z_dense_real_beam_selector/dense_real_beam_selector|dense_real_beam_selector.md]] | 1200 | obj= robust= long= short= |
| `20260503T180158Z_dense_real_beam_selector` |  | 0 | obj= robust= long= short= |
| `20260503T182612Z_dense_real_beam_selector` | [[codex_discovery/runs/20260503T182612Z_dense_real_beam_selector/dense_real_beam_selector|dense_real_beam_selector.md]] | 15000 | obj= robust= long= short= |
| `20260503T201331Z_dense_real_beam_selector` |  | 0 | obj= robust= long= short= |
| `20260503T202051Z_dense_real_beam_selector` |  | 0 | obj= robust= long= short= |
| `20260503T205404Z_market_native_veto_selector` | [[codex_discovery/runs/20260503T205404Z_market_native_veto_selector/market_native_veto_selector|market_native_veto_selector.md]] | 10000 | obj= robust= long= short= |
| `20260503T210144Z_event_ranker_beam_selector` |  | 0 | obj= robust= long= short= |
