# Experiment Mutator Memo

## Mutation Principle
The next round should not increase global search width. It should increase causal clarity. The right mutation unit is a single hypothesis from the discovery queue, with all other dimensions frozen.

## Discovery Queue
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
| DISC_adc6ee18a57c | HYP_bdef076c7d  | complete_strategy | oi_funding_continuation       | breakeven_ratchet      | long        | higher_confidence_watchlist |          0.798791 | watchlist_needs_ablation | Combined module oi_funding_continuation/30s/breakeven_ratchet/long is a complete-strategy candidate for controlled paper validation.           | Freeze this complete module, then mutate only one parameter neighborhood in the next pass. |
| DISC_f283c1859f32 | HYP_f69f5554cf  | complete_strategy | oi_funding_continuation       | runner_trail           | long        | higher_confidence_watchlist |          0.795859 | watchlist_needs_ablation | Combined module oi_funding_continuation/1m/runner_trail/long is a complete-strategy candidate for controlled paper validation.                 | Freeze this complete module, then mutate only one parameter neighborhood in the next pass. |

## Mutations To Run First
1. Complete-strategy neighborhood for `premium_basis_overheat / 30s / indicator_invalidation / long`.
2. Entry ablation for `premium_basis_overheat / 30s / long` while swapping only exit families.
3. Entry ablation for `oi_funding_continuation` comparing `30s` and `1m` with the same exit.
4. Exit ablation for `breakeven_ratchet` with fixed entry families.
5. Cluster representative re-score for `freshness_strict_confirmation / 30s / state_machine`.

## What Not To Mutate Yet
Do not mutate everything at once. Do not create a new entry grammar at the same time as a new exit grammar. Do not change cost assumptions while testing strategy logic. Do not use paper-shadow feedback until the focused ablation pass is complete.

## Reject Handling
Every failed mutation should produce one of these reasons:

- `entry_not_reusable`
- `exit_not_reusable`
- `cluster_neighbor_weak`
- `cost_stress_failure`
- `baseline_lift_failure`
- `p10_negative_after_ablation`
- `sample_tier_only_observation`

This matters because the next AutoResearch loop should learn where not to spend GPU time.

## Mutation Budget Recommendation
Keep the first true next round modest: enough to run the top 5 to 8 hypotheses with local neighborhoods, not enough to become another broad max_alpha pass. The objective is to isolate mechanism, not maximize leaderboard.
