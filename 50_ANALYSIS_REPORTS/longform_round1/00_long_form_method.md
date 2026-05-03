# Long-Form Deep Round 1 Method

This package is the long-form review layer. It does not rerun search and does not call production systems. It converts the completed GPU fused strong run into an auditable research committee review.

## Source
- Stage: `max_alpha_gpu_fused_strong`
- Candidate space sample: `500000000000`
- Coarse eval: `100000000`
- Medium eval: `5000000`
- Deep eval: `200000`
- Stress eval: `20000`
- Path resolution: `1m_trade_kline`
- Paper only: `True`
- Live allowed: `False`

## Long-Form Review Phases
1. Evidence audit and de-duplication.
2. Entry/exit combination ranking.
3. Role-independent memo generation.
4. Cross-examination.
5. Red-team review.
6. Final Chinese verdict and focused ablation config.

## Sample Tier Summary
| sample_tier                 |   strategies |   clusters |   median_sample |   best_median |   median_p10 |   positive_p10_rate |   median_stress |   positive_stress_rate |
|:----------------------------|-------------:|-----------:|----------------:|--------------:|-------------:|--------------------:|----------------:|-----------------------:|
| early_alpha                 |        19569 |        154 |              24 |       23.3006 |     -1.82416 |             7.89003 |         1.43994 |                78.8901 |
| exploratory_watchlist       |        28228 |        183 |              42 |       23.8217 |     -1.82416 |             3.60989 |         1.19032 |                70.5328 |
| higher_confidence_watchlist |       130180 |        684 |             434 |       21.8662 |     -3.22416 |             5.22046 |         7.00752 |                80.9034 |
| validated_watchlist         |        22023 |        164 |              68 |       21.8119 |     -2.22416 |             2.00245 |         2.02785 |                64.8277 |

## Cluster Representative Leaders
| strategy_id           | strategy_family               | side   | entry_timing   | exit_family         |   sample_size | sample_tier                 |   median_net_pct |   p10_net_pct |   stress_fee_slippage_median_net_pct |   cost_stress_gap_pct |   robust_score | strategy_similarity_cluster_id   |   baseline_lift_pct |
|:----------------------|:------------------------------|:-------|:---------------|:--------------------|--------------:|:----------------------------|-----------------:|--------------:|-------------------------------------:|----------------------:|---------------:|:---------------------------------|--------------------:|
| v6_f468dea25e7faf1bcd | freshness_strict_confirmation | long   | 30s            | state_machine       |            27 | early_alpha                 |          23.2943 |      14.8108  |                              23.026  |              0.268318 |       0.129127 | cluster_31a30bceac               |             23.7461 |
| v6_c092b5ae27705bd211 | freshness_strict_confirmation | long   | 30s            | state_machine       |            27 | early_alpha                 |          23.1044 |      14.8988  |                              22.8361 |              0.268318 |       0.12881  | cluster_2f7c657c16               |             23.5561 |
| v6_8e501c5e8f1597677c | freshness_strict_confirmation | long   | 30s            | state_machine       |            46 | exploratory_watchlist       |          22.2037 |      10.8274  |                              21.9354 |              0.268318 |       0.121874 | cluster_f8691e9238               |             22.6555 |
| v6_9fd2c43f2c545e0b33 | freshness_strict_confirmation | long   | 30s            | breakeven_ratchet   |            73 | validated_watchlist         |          21.8119 |      11.2209  |                              21.5436 |              0.268318 |       0.119914 | cluster_728d84e317               |             22.2636 |
| v6_4aea03e3fa32fdedbb | freshness_strict_confirmation | long   | 30s            | breakeven_ratchet   |           102 | higher_confidence_watchlist |          21.8662 |      10.5059  |                              21.5979 |              0.268318 |       0.118654 | cluster_39710745e9               |             22.3179 |
| v6_858b4789d8f01def64 | freshness_strict_confirmation | long   | 30s            | state_machine       |            47 | exploratory_watchlist       |          21.2344 |      10.4294  |                              20.9661 |              0.268318 |       0.117279 | cluster_c6da0c2545               |             21.6861 |
| v6_8f21b07ab27a9ca722 | freshness_strict_confirmation | long   | 30s            | failed_continuation |            68 | validated_watchlist         |          20.8055 |       8.30602 |                              20.5372 |              0.268318 |       0.11274  | cluster_9e58844dbf               |             21.2572 |
| v6_1cd0cfff3a0cf26439 | freshness_strict_confirmation | long   | 30s            | failed_continuation |            68 | validated_watchlist         |          20.8055 |       8.30602 |                              20.5372 |              0.268318 |       0.11274  | cluster_aa0f61c0c1               |             21.2572 |
| v6_f70c9ed57173dd6a00 | oi_funding_continuation       | long   | 1m             | breakeven_ratchet   |           201 | higher_confidence_watchlist |          20.0794 |      10.8468  |                              19.8111 |              0.268318 |       0.111435 | cluster_8095517046               |             20.5312 |
| v6_691c612b10d572162f | freshness_strict_confirmation | long   | 30s            | breakeven_ratchet   |            79 | validated_watchlist         |          21.4885 |       6.11309 |                              21.2202 |              0.268318 |       0.109696 | cluster_4b64385841               |             21.9402 |
| v6_74fef72a29d155af49 | oi_funding_continuation       | long   | 1m             | breakeven_ratchet   |           292 | higher_confidence_watchlist |          19.5037 |       7.59988 |                              19.2354 |              0.268318 |       0.103382 | cluster_7ec0c6d094               |             19.9554 |
| v6_28d858af6439dc2b01 | premium_basis_overheat        | long   | 30s            | breakeven_ratchet   |           321 | higher_confidence_watchlist |          20.1791 |       4.21373 |                              19.9108 |              0.268318 |       0.103282 | cluster_5e5279eebc               |             20.6309 |
