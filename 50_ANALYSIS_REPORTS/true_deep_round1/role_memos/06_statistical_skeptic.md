# Statistical Skeptic Memo

## Statistical Position
The new sample policy is acceptable for discovery: sample sizes greater than 15 should not be discarded automatically. But inclusion is not endorsement. The right statistical language is tiered confidence.

## Sample Structure
| sample_tier                 |   strategies |
|:----------------------------|-------------:|
| higher_confidence_watchlist |       130180 |
| exploratory_watchlist       |        28228 |
| validated_watchlist         |        22023 |
| early_alpha                 |        19569 |

There are no retained rows with sample size 15 or below. That is useful: the entire leaderboard is analyzable under the revised rule. Still, 16-29 and 30-49 should be treated as early/exploratory evidence, while 100+ can carry more conclusion weight.

## Small Sample Caution
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
| v6_44382982f34c250479 | freshness_strict_confirmation | long   | 30s            | state_machine |            27 | early_alpha   |          23.2943 |       14.8108 |                               23.026 |       0.129127 | cluster_31a30bceac               |
| v6_7df998b1f8ca6416da | freshness_strict_confirmation | long   | 30s            | state_machine |            27 | early_alpha   |          23.2943 |       14.8108 |                               23.026 |       0.129127 | cluster_31a30bceac               |

The raw top is impressive because p10 remains high for a 27-sample candidate. But it is also concentrated in the same family and cluster. The skeptical stance is: interesting, keep it, but force a neighbor and cluster-representative test.

## Multiple Testing
A 500B parameter search creates a massive selection problem. The existing bootstrap, permutation, effective sample size, multiple testing, and similarity-cluster artifacts are not optional reports; they are core controls. The next round should not optimize new parameters without updating those controls.

## Skeptic's Required Falsification
1. Cluster representative only, no duplicated rows.
2. Remove top 1 percent and top 5 percent contributors.
3. Compare to randomized timestamp/symbol baselines.
4. Test fixed entry with multiple exits and fixed exit with multiple entries.
5. Keep early-alpha candidates below paper-shadow threshold until they reappear in higher sample tiers.
