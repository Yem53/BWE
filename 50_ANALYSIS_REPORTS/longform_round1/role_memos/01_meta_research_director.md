# Meta Research Director Long Memo

## Verdict
The project has crossed from raw search into research governance. The output is strong enough for focused ablation, but still not paper-shadow. The reason is subtle: the candidates are not weak; the attribution of alpha is not yet isolated.

## Evidence I Trust Most
| strategy_id           | strategy_family               | side   | entry_timing   | exit_family         |   sample_size | sample_tier                 |   median_net_pct |   p10_net_pct |   stress_fee_slippage_median_net_pct |   cost_stress_gap_pct |   robust_score | strategy_similarity_cluster_id   |   baseline_lift_pct |
|:----------------------|:------------------------------|:-------|:---------------|:--------------------|--------------:|:----------------------------|-----------------:|--------------:|-------------------------------------:|----------------------:|---------------:|:---------------------------------|--------------------:|
| v6_4aea03e3fa32fdedbb | freshness_strict_confirmation | long   | 30s            | breakeven_ratchet   |           102 | higher_confidence_watchlist |          21.8662 |      10.5059  |                              21.5979 |              0.268318 |      0.118654  | cluster_39710745e9               |             22.3179 |
| v6_f70c9ed57173dd6a00 | oi_funding_continuation       | long   | 1m             | breakeven_ratchet   |           201 | higher_confidence_watchlist |          20.0794 |      10.8468  |                              19.8111 |              0.268318 |      0.111435  | cluster_8095517046               |             20.5312 |
| v6_74fef72a29d155af49 | oi_funding_continuation       | long   | 1m             | breakeven_ratchet   |           292 | higher_confidence_watchlist |          19.5037 |       7.59988 |                              19.2354 |              0.268318 |      0.103382  | cluster_7ec0c6d094               |             19.9554 |
| v6_28d858af6439dc2b01 | premium_basis_overheat        | long   | 30s            | breakeven_ratchet   |           321 | higher_confidence_watchlist |          20.1791 |       4.21373 |                              19.9108 |              0.268318 |      0.103282  | cluster_5e5279eebc               |             20.6309 |
| v6_d559b598378bae1f75 | state_machine_runner          | long   | T0             | breakeven_ratchet   |           321 | higher_confidence_watchlist |          19.7758 |       4.19716 |                              19.5075 |              0.268318 |      0.102216  | cluster_6d2e9af121               |             20.2276 |
| v6_689ba2e8f3363d48e4 | state_machine_runner          | long   | T0             | breakeven_ratchet   |           321 | higher_confidence_watchlist |          19.7758 |       4.19716 |                              19.5075 |              0.268318 |      0.101916  | cluster_fe4abc49cd               |             20.2276 |
| v6_b0a2f3db55cb93618a | premium_basis_overheat        | long   | 30s            | failed_continuation |           321 | higher_confidence_watchlist |          20.0024 |      -2.01034 |                              19.7341 |              0.268318 |      0.0961618 | cluster_c769cf1ac2               |             20.4541 |
| v6_0c1db8a9f372c3bf4b | freshness_strict_confirmation | long   | 30s            | breakeven_ratchet   |           111 | higher_confidence_watchlist |          21.361  |      -5.22416 |                              21.0927 |              0.268318 |      0.0958586 | cluster_a0aec4ba6c               |             21.8127 |
| v6_a007baac46dfabbc59 | oi_funding_continuation       | long   | 1m             | runner_trail        |           196 | higher_confidence_watchlist |          16.8794 |      10.1966  |                              16.6111 |              0.268319 |      0.0955797 | cluster_5ee5422ec2               |             17.3312 |
| v6_2e078d5e7379ffb44f | freshness_strict_confirmation | long   | 30s            | time_decay          |           141 | higher_confidence_watchlist |          18.4457 |       6.08709 |                              18.1774 |              0.268318 |      0.0953066 | cluster_3a230e028b               |             18.8975 |

The high-confidence cluster representatives matter more than raw repeated rows. They show that strong results survive beyond the 27-sample early-alpha raw top.

## Operating Order
1. Use cluster representatives rather than duplicated leaderboard rows.
2. Test one hypothesis at a time.
3. Keep entry and exit isolation separate.
4. Preserve baseline, cost stress, and future safety in every pass.
5. Do not let paper-shadow consume a candidate until its complete strategy object survives ablation.

## Committee Decision
Proceed to `focused_ablation_before_paper_shadow`. The first hypothesis should be `premium_basis_overheat / 30s / long` with exit swap.
