# True Deep Round 1 Method And Scope

This directory is the deep LLM-style research review layer. It does not rerun the 500B-scale search. It reads the completed GPU fused strong run and the AutoResearch expanded governance artifacts, then turns them into a slower, evidence-driven research seminar: independent role memos, cross-examination, rebuttal, revised positions, final synthesis, paper gate, and a next-round ablation config.

## Source Facts
- Stage: `max_alpha_gpu_fused_strong`
- Candidate space sample: `500000000000`
- Deep eval rows: `200000`
- Stress eval rows: `20000`
- Path resolution: `1m_trade_kline`
- Paper only: `True`
- Live allowed: `False`

## Sample Tiers
| sample_tier                 |   strategies |
|:----------------------------|-------------:|
| higher_confidence_watchlist |       130180 |
| exploratory_watchlist       |        28228 |
| validated_watchlist         |        22023 |
| early_alpha                 |        19569 |

## Key Evidence Tables
These tables are copied into `tables/` as CSV and referenced by each role.

### Top Raw
| strategy_id           | strategy_family               | side   | entry_timing   | exit_family   |   sample_size | sample_tier   |   median_net_pct |   p10_net_pct |   stress_fee_slippage_median_net_pct |   robust_score | strategy_similarity_cluster_id   |
|:----------------------|:------------------------------|:-------|:---------------|:--------------|--------------:|:--------------|-----------------:|--------------:|-------------------------------------:|---------------:|:---------------------------------|
| v6_f468dea25e7faf1bcd | freshness_strict_confirmation | long   | 30s            | state_machine |            27 | early_alpha   |          23.2943 |       14.8108 |                               23.026 |       0.129127 | cluster_31a30bceac               |
| v6_d54657ab4d233bc172 | freshness_strict_confirmation | long   | 30s            | state_machine |            27 | early_alpha   |          23.2943 |       14.8108 |                               23.026 |       0.129127 | cluster_31a30bceac               |
| v6_f99e0b972230177b64 | freshness_strict_confirmation | long   | 30s            | state_machine |            27 | early_alpha   |          23.2943 |       14.8108 |                               23.026 |       0.129127 | cluster_31a30bceac               |
| v6_cc98a1e33a315fc330 | freshness_strict_confirmation | long   | 30s            | state_machine |            27 | early_alpha   |          23.2943 |       14.8108 |                               23.026 |       0.129127 | cluster_31a30bceac               |
| v6_bcb3ea3c993ba6702d | freshness_strict_confirmation | long   | 30s            | state_machine |            27 | early_alpha   |          23.2943 |       14.8108 |                               23.026 |       0.129127 | cluster_31a30bceac               |
| v6_d59ac7b258010d14ae | freshness_strict_confirmation | long   | 30s            | state_machine |            27 | early_alpha   |          23.2943 |       14.8108 |                               23.026 |       0.129127 | cluster_31a30bceac               |
| v6_ff76d4c21acb09b07b | freshness_strict_confirmation | long   | 30s            | state_machine |            27 | early_alpha   |          23.2943 |       14.8108 |                               23.026 |       0.129127 | cluster_31a30bceac               |
| v6_12d3f680e30cefd7ec | freshness_strict_confirmation | long   | 30s            | state_machine |            27 | early_alpha   |          23.2943 |       14.8108 |                               23.026 |       0.129127 | cluster_31a30bceac               |

### Top High Confidence
| strategy_id           | strategy_family               | side   | entry_timing   | exit_family       |   sample_size | sample_tier                 |   median_net_pct |   p10_net_pct |   stress_fee_slippage_median_net_pct |   robust_score | strategy_similarity_cluster_id   |
|:----------------------|:------------------------------|:-------|:---------------|:------------------|--------------:|:----------------------------|-----------------:|--------------:|-------------------------------------:|---------------:|:---------------------------------|
| v6_4aea03e3fa32fdedbb | freshness_strict_confirmation | long   | 30s            | breakeven_ratchet |           102 | higher_confidence_watchlist |          21.8662 |       10.5059 |                              21.5979 |       0.118654 | cluster_39710745e9               |
| v6_7e7b60c24a3da75302 | freshness_strict_confirmation | long   | 30s            | breakeven_ratchet |           102 | higher_confidence_watchlist |          21.8662 |       10.5059 |                              21.5979 |       0.118654 | cluster_39710745e9               |
| v6_feb606b7d30768d175 | freshness_strict_confirmation | long   | 30s            | breakeven_ratchet |           102 | higher_confidence_watchlist |          21.8662 |       10.5059 |                              21.5979 |       0.118654 | cluster_39710745e9               |
| v6_85c7eafd0b2debc855 | freshness_strict_confirmation | long   | 30s            | breakeven_ratchet |           102 | higher_confidence_watchlist |          21.8662 |       10.5059 |                              21.5979 |       0.118654 | cluster_39710745e9               |
| v6_af26d07f7c5f2280ce | freshness_strict_confirmation | long   | 30s            | breakeven_ratchet |           102 | higher_confidence_watchlist |          21.8662 |       10.5059 |                              21.5979 |       0.118654 | cluster_39710745e9               |
| v6_8d51d50e819f9d04b5 | freshness_strict_confirmation | long   | 30s            | breakeven_ratchet |           102 | higher_confidence_watchlist |          21.8662 |       10.5059 |                              21.5979 |       0.118654 | cluster_39710745e9               |
| v6_78d35db409f71d4f45 | freshness_strict_confirmation | long   | 30s            | breakeven_ratchet |           102 | higher_confidence_watchlist |          21.8662 |       10.5059 |                              21.5979 |       0.118654 | cluster_39710745e9               |
| v6_43343e2ab976697a1f | freshness_strict_confirmation | long   | 30s            | breakeven_ratchet |           102 | higher_confidence_watchlist |          21.8662 |       10.5059 |                              21.5979 |       0.118654 | cluster_39710745e9               |

### Discovery Queue
| discovery_id      | hypothesis_id   | discovery_type    | entry_family                  | exit_family            | direction   | sample_tier                 |   discovery_score | decision                 | rationale                                                                                                                                      | next_action                                                                                |
|:------------------|:----------------|:------------------|:------------------------------|:-----------------------|:------------|:----------------------------|------------------:|:-------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------|
| DISC_5f198b588f7e | HYP_c984bb352d  | complete_strategy | premium_basis_overheat        | indicator_invalidation | long        | higher_confidence_watchlist |          0.840932 | watchlist_needs_ablation | Combined module premium_basis_overheat/30s/indicator_invalidation/long is a complete-strategy candidate for controlled paper validation.       | Freeze this complete module, then mutate only one parameter neighborhood in the next pass. |
| DISC_9c009a37dbad | HYP_b2ca5a77a3  | entry             | premium_basis_overheat        | ANY                    | long        | higher_confidence_watchlist |          0.816256 | watchlist_needs_ablation | Entry family premium_basis_overheat with timing 30s and side long has reusable alpha if it remains positive after holding exit choices fixed.  | Run one entry-family ablation with the top two stable exits and unchanged cost model.      |
| DISC_feee62fe1eab | HYP_a5add7218f  | entry             | oi_funding_continuation       | ANY                    | long        | higher_confidence_watchlist |          0.814962 | watchlist_needs_ablation | Entry family oi_funding_continuation with timing 30s and side long has reusable alpha if it remains positive after holding exit choices fixed. | Run one entry-family ablation with the top two stable exits and unchanged cost model.      |
| DISC_eb17ac95eaf9 | HYP_c3c0449ddf  | complete_strategy | freshness_strict_confirmation | breakeven_ratchet      | long        | higher_confidence_watchlist |          0.80928  | watchlist_needs_ablation | Combined module freshness_strict_confirmation/30s/breakeven_ratchet/long is a complete-strategy candidate for controlled paper validation.     | Freeze this complete module, then mutate only one parameter neighborhood in the next pass. |
| DISC_a2979f0ce27f | HYP_40cb1e9511  | complete_strategy | premium_basis_overheat        | state_machine          | long        | higher_confidence_watchlist |          0.806205 | watchlist_needs_ablation | Combined module premium_basis_overheat/30s/state_machine/long is a complete-strategy candidate for controlled paper validation.                | Freeze this complete module, then mutate only one parameter neighborhood in the next pass. |
| DISC_c280397669d1 | HYP_96fb583667  | complete_strategy | oi_funding_continuation       | breakeven_ratchet      | long        | higher_confidence_watchlist |          0.805729 | watchlist_needs_ablation | Combined module oi_funding_continuation/1m/breakeven_ratchet/long is a complete-strategy candidate for controlled paper validation.            | Freeze this complete module, then mutate only one parameter neighborhood in the next pass. |
| DISC_ea0d2be05a53 | HYP_0bc89253af  | complete_strategy | premium_basis_overheat        | breakeven_ratchet      | long        | higher_confidence_watchlist |          0.802026 | watchlist_needs_ablation | Combined module premium_basis_overheat/30s/breakeven_ratchet/long is a complete-strategy candidate for controlled paper validation.            | Freeze this complete module, then mutate only one parameter neighborhood in the next pass. |
| DISC_6e074fa4b9a2 | HYP_bb1fb15b32  | complete_strategy | premium_basis_overheat        | runner_trail           | long        | higher_confidence_watchlist |          0.800572 | watchlist_needs_ablation | Combined module premium_basis_overheat/30s/runner_trail/long is a complete-strategy candidate for controlled paper validation.                 | Freeze this complete module, then mutate only one parameter neighborhood in the next pass. |
