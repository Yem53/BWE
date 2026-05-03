# Meta Research Director Memo

## Position
This run is now good enough to support a serious second research phase, but not good enough to skip the ablation layer. The GPU fused strong run searched a 500B-scale parameter space and produced a dense 200k-row final leaderboard. The deep review should treat that as discovery evidence, not as a paper-ready strategy selection event.

The strongest governance fact is that no candidate in the retained leaderboard has `sample_size <= 15`; the population begins at early-alpha and moves through exploratory, validated, and higher-confidence tiers. That means the user-requested policy is compatible with the data: sample size should not be used as a hard reject above 15. It should be used as confidence labeling and sizing discipline.

## Evidence
| sample_tier                 |   strategies |
|:----------------------------|-------------:|
| higher_confidence_watchlist |       130180 |
| exploratory_watchlist       |        28228 |
| validated_watchlist         |        22023 |
| early_alpha                 |        19569 |

Top raw result: `v6_f468dea25e7faf1bcd` is `freshness_strict_confirmation` / `long` / `30s` / `state_machine` with sample `27`, median `23.2943`, p10 `14.8108`, and stress median `23.0260`.

Top 100+ sample result: `v6_4aea03e3fa32fdedbb` is `freshness_strict_confirmation` / `long` / `30s` / `breakeven_ratchet` with sample `102`, median `21.8662`, p10 `10.5059`, and stress median `21.5979`.

## Governance Call
The raw top cluster is compelling but too duplicated to crown directly. Multiple top rows share the same strategy family, side, timing, exit, and cluster. That is not a failure; it is exactly why the AutoResearch layer exists. The correct move is to convert repeated evidence into a cluster representative and then test whether nearby parameter changes retain the edge.

The second governance call is that the best high-confidence candidates are only modestly weaker than the small-sample raw leaders. This matters. If the high-confidence tier had collapsed, the round would be mostly a small-sample artifact. Instead, the 100+ tier still shows strong median and stressed median results.

## Required Next Move
Run a focused ablation sequence, one hypothesis at a time:

1. Freeze a complete candidate and mutate only nearby parameter thresholds.
2. Freeze entry and swap exits.
3. Freeze exit and swap entries.
4. De-duplicate by cluster representative before any paper-shadow gate.
5. Keep baseline-first comparison and execution stress in every pass.

## Decision
Continue research, but do not enter paper-shadow yet. The phase label should be `focused_ablation_before_paper_shadow`.
