# Overfit And Bias Audit

## Main Biases
| risk_id   | risk                            | severity   | evidence                                                                         | mitigation                                                                    |
|:----------|:--------------------------------|:-----------|:---------------------------------------------------------------------------------|:------------------------------------------------------------------------------|
| R1        | raw_top_cluster_duplication     | high       | Top raw freshness/state_machine rows repeat inside the same similarity clusters. | Rank cluster representatives before paper gate.                               |
| R2        | exit_path_shape_overfit         | high       | State-machine raw leaders may harvest one favorable 1m path shape.               | Swap exits with fixed entry and include fixed_tp_sl control.                  |
| R3        | multiple_testing_selection_bias | high       | 500B-scale parameter space creates selection pressure.                           | Use bootstrap, permutation, ESS, multiple testing penalty, and reject ledger. |
| R4        | long_short_imbalance            | medium     | Long dominates retained candidates while short has far fewer rows.               | Run separate balanced short-side probe before rejecting short.                |
| R5        | 1m_path_resolution_limit        | medium     | The path is 1m trade OHLCV, not tick replay.                                     | Declare path precision and require paper replay before shadow signals.        |

## Red-Team Conclusion
The result is promising but selection-biased by design. The next round must reduce degrees of freedom by freezing one side of the strategy and mutating only the other.

## Required Evidence Before Paper
- Cluster-representative positive performance.
- Positive stressed median.
- Positive or acceptable p10.
- Nonzero baseline lift after fixed controls.
- Future-safety pass.
