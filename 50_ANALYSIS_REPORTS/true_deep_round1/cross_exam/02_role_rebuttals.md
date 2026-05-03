# Role Rebuttals

## Strategy Architect
The raw `freshness_strict_confirmation / state_machine` result is not enough by itself. I revise the architecture view: use it as a source of exit-state hypotheses, but give higher operational priority to `freshness_strict_confirmation / breakeven_ratchet` in the 100+ sample tier and to `premium_basis_overheat` complete modules that survive multiple exit families.

## Results Analyst
The leaderboard should be reported in three simultaneous views: raw profit, high-confidence profit, and stability/cluster support. The raw top remains important because its p10 is high, but the 100+ sample table is more decision-relevant for next-round queue priority.

## Statistical Skeptic
I accept the user's sample policy: greater than 15 is inclusion-worthy. My condition is that no claim should use the word reliable unless it survives a higher confidence tier or a local neighborhood test.

## Risk Critic
The main demotion risk is not that costs wipe out the signal; the stress table does not show that. The larger risk is path-shape and cluster overfit. I want cluster-representative evaluation before paper-shadow.

## Experiment Mutator
The first mutation should be falsification-oriented: hold `premium_basis_overheat / 30s / long` fixed and swap exits, including fixed TP/SL control. If the entry is real, at least one non-optimized exit should retain positive baseline lift.

## Execution/Paper Architect
No signal payload should be emitted yet. The next config is an ablation config, not a paper signal config. Paper-shadow requires a later positive gate decision.

## Lead Synthesizer
The revised synthesis is: continue with focused ablation; do not do global broad search; do not do paper-shadow yet.

## Evidence Snapshot
Top high-confidence candidates:

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
