# Experiment Mutator Long Memo

## Mutation Principle
Mutation should increase causal information, not just leaderboard height. The next experiment should ask: does the entry still work when the exit is no longer optimized?

## Ablation Matrix
| strategy_family               | side   | entry_timing   | exit_family            |   rows |   unique_clusters |   median_sample |   max_sample |   best_median |   median_of_medians |   median_p10 |   best_p10 |   median_stress |   best_stress |   positive_p10_rate |   positive_stress_rate |   best_robust |   median_robust |   median_top_symbol_share |   longform_score |
|:------------------------------|:-------|:---------------|:-----------------------|-------:|------------------:|----------------:|-------------:|--------------:|--------------------:|-------------:|-----------:|----------------:|--------------:|--------------------:|-----------------------:|--------------:|----------------:|--------------------------:|-----------------:|
| state_machine_runner          | long   | T0             | indicator_invalidation |    573 |                11 |             954 |          954 |       18.1758 |            14.9925  |     -5.22416 |    3.84345 |        14.7242  |       17.9075 |             6.9808  |                    100 |     0.0941302 |       0.0611915 |                   6.07966 |         0.846054 |
| freshness_strict_confirmation | long   | 30s            | failed_continuation    |    607 |                10 |             334 |         1091 |       20.8055 |            17.8045  |     -5.22416 |    8.30602 |        17.5362  |       20.5372 |            13.6738  |                    100 |     0.11274   |       0.0742963 |                   7.97434 |         0.84296  |
| freshness_strict_confirmation | long   | 30s            | time_decay             |    668 |                 6 |             227 |          273 |       18.4457 |            17.7881  |     -1.82416 |    6.08709 |        17.5197  |       18.1774 |            17.0659  |                    100 |     0.0953066 |       0.0790649 |                   3.52423 |         0.825516 |
| oi_funding_continuation       | long   | 1m             | runner_trail           |   4576 |                12 |             163 |          255 |       17.982  |            12.4288  |     -2.22416 |   10.8658  |        12.1605  |       17.7136 |            19.8645  |                    100 |     0.0955797 |       0.0380684 |                   5.65957 |         0.815874 |
| premium_basis_overheat        | long   | 30s            | breakeven_ratchet      |    553 |                 5 |             420 |         1401 |       20.1791 |            16.3591  |     -5.22416 |    4.21373 |        16.0908  |       19.9108 |            19.8915  |                    100 |     0.103282  |       0.0635075 |                   6.07966 |         0.810493 |
| freshness_strict_confirmation | long   | 30s            | breakeven_ratchet      |   3781 |                 4 |             102 |          111 |       21.8662 |            15.7592  |     -2.22416 |   11.2209  |        15.4909  |       21.5979 |            24.676   |                    100 |     0.119914  |       0.0497955 |                   3.92157 |         0.809283 |
| oi_funding_continuation       | long   | 1m             | breakeven_ratchet      |   3610 |                 4 |             292 |          400 |       20.0794 |            13.4258  |     -2.22416 |   10.8468  |        13.1575  |       19.8111 |            22.133   |                    100 |     0.111435  |       0.0417179 |                   3.55731 |         0.809103 |
| oi_funding_continuation       | long   | 30s            | breakeven_ratchet      |    422 |                 4 |             102 |          111 |       21.8662 |            15.7592  |     -2.22416 |   10.5059  |        15.4909  |       21.5979 |            19.4313  |                    100 |     0.118654  |       0.0497955 |                   3.92157 |         0.806413 |
| freshness_strict_confirmation | long   | 30s            | state_machine          |   2061 |                16 |             139 |          904 |       23.2943 |             8.33396 |     -1.6578  |   14.8988  |         8.06564 |       23.026  |            13.9253  |                    100 |     0.129127  |       0.0233014 |                   9.03955 |         0.799058 |
| contrarian_crash_fade         | long   | 30s            | breakeven_ratchet      |   2997 |                 8 |             341 |         1401 |       20.1791 |            10.5656  |     -2.22416 |    4.21373 |        10.2973  |       19.9108 |             6.63997 |                    100 |     0.103282  |       0.0309196 |                   6.07966 |         0.798072 |

## First Experiment
Fixed entry:

- `strategy_family: premium_basis_overheat`
- `side: long`
- `entry_timing: 30s`

Swap exits:

- `indicator_invalidation`
- `breakeven_ratchet`
- `state_machine`
- `runner_trail`
- `fixed_tp_sl`

Success requires positive stressed median, acceptable p10, baseline lift, and no future safety failure.

## Stop Rule
If fixed TP/SL and at least one non-state-machine exit both fail, demote the entry family. If only state-machine succeeds, mark exit-path overfit risk.
