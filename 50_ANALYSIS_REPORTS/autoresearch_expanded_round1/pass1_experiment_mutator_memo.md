# Experiment Mutator Round 1 Memo

## Mutation Queue
Use the discovery scoreboard as the mutation queue. The first expansions should stay local: adjacent entry timing, nearby threshold quantiles, exit stop width, time-stop horizon, and breakeven trigger.

## Discipline
- One hypothesis per iteration.
- Keep baseline-first evaluation in every pass.
- Preserve fee, slippage, latency, and missed-fill stress in the objective.
- Convert every new idea into a verifiable strategy grammar before evaluation.

## Top Queue
| hypothesis_id   | discovery_type    | entry_family                  | exit_family            | direction   | sample_tier                 |   discovery_score | decision                 |
|:----------------|:------------------|:------------------------------|:-----------------------|:------------|:----------------------------|------------------:|:-------------------------|
| HYP_c984bb352d  | complete_strategy | premium_basis_overheat        | indicator_invalidation | long        | higher_confidence_watchlist |          0.840932 | watchlist_needs_ablation |
| HYP_b2ca5a77a3  | entry             | premium_basis_overheat        | ANY                    | long        | higher_confidence_watchlist |          0.816256 | watchlist_needs_ablation |
| HYP_a5add7218f  | entry             | oi_funding_continuation       | ANY                    | long        | higher_confidence_watchlist |          0.814962 | watchlist_needs_ablation |
| HYP_c3c0449ddf  | complete_strategy | freshness_strict_confirmation | breakeven_ratchet      | long        | higher_confidence_watchlist |          0.80928  | watchlist_needs_ablation |
| HYP_40cb1e9511  | complete_strategy | premium_basis_overheat        | state_machine          | long        | higher_confidence_watchlist |          0.806205 | watchlist_needs_ablation |
| HYP_96fb583667  | complete_strategy | oi_funding_continuation       | breakeven_ratchet      | long        | higher_confidence_watchlist |          0.805729 | watchlist_needs_ablation |
| HYP_0bc89253af  | complete_strategy | premium_basis_overheat        | breakeven_ratchet      | long        | higher_confidence_watchlist |          0.802026 | watchlist_needs_ablation |
| HYP_bb1fb15b32  | complete_strategy | premium_basis_overheat        | runner_trail           | long        | higher_confidence_watchlist |          0.800572 | watchlist_needs_ablation |
| HYP_bdef076c7d  | complete_strategy | oi_funding_continuation       | breakeven_ratchet      | long        | higher_confidence_watchlist |          0.798791 | watchlist_needs_ablation |
| HYP_f69f5554cf  | complete_strategy | oi_funding_continuation       | runner_trail           | long        | higher_confidence_watchlist |          0.795859 | watchlist_needs_ablation |
| HYP_5535c835bc  | exit              | ANY                           | indicator_invalidation | long        | higher_confidence_watchlist |          0.794651 | watchlist_needs_ablation |
| HYP_0b7b2a6bd0  | complete_strategy | freshness_strict_confirmation | time_decay             | long        | higher_confidence_watchlist |          0.791311 | watchlist_needs_ablation |

## Mutation Rules
- Mutate only one family dimension per pass: entry condition, timing, exit state, or risk parameter.
- Prefer local neighborhoods around proven families before creating new global families.
- Record rejected mutations by reason so later rounds do not rediscover them.
- Add a shuffled/random baseline every time a new family is introduced.
