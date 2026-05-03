# Statistical Skeptic Long Memo

## Statistical Stance
The user's sample policy is reasonable for discovery: sample_size > 15 enters analysis. But a 500B-scale search means selection bias remains the central statistical hazard.

## Evidence To Keep Visible
| sample_tier                 |   strategies |   clusters |   median_sample |   best_median |   median_p10 |   positive_p10_rate |   median_stress |   positive_stress_rate |
|:----------------------------|-------------:|-----------:|----------------:|--------------:|-------------:|--------------------:|----------------:|-----------------------:|
| early_alpha                 |        19569 |        154 |              24 |       23.3006 |     -1.82416 |             7.89003 |         1.43994 |                78.8901 |
| exploratory_watchlist       |        28228 |        183 |              42 |       23.8217 |     -1.82416 |             3.60989 |         1.19032 |                70.5328 |
| higher_confidence_watchlist |       130180 |        684 |             434 |       21.8662 |     -3.22416 |             5.22046 |         7.00752 |                80.9034 |
| validated_watchlist         |        22023 |        164 |              68 |       21.8119 |     -2.22416 |             2.00245 |         2.02785 |                64.8277 |

## Skeptical Requirements
1. De-duplicate by cluster.
2. Preserve bootstrap and permutation reports.
3. Require neighboring parameter support.
4. Do not equate early-alpha with reliability.
5. Penalize strategies that lose p10 after cluster representative selection.

## Decision
The current conclusion can say "signal exists"; it cannot say "final strategy found".
