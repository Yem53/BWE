# True Deep Round 1 Lead Synthesis

## Bottom Line
The research has enough signal to continue, but the correct next state is `focused_ablation_before_paper_shadow`, not paper-shadow and not another global max_alpha sweep.

## What Looks Real
The strongest preliminary edge is on long strategies around BWE pump/freshness/market-structure confirmation. The best raw candidate is early-alpha sample 27 but has very high median, p10, and stressed median. The best 100+ sample candidates remain highly positive, which materially reduces the concern that the entire run is a small-sample mirage.

## Best Candidate Families
- `premium_basis_overheat / 30s / long`: strongest discovery queue item, broad component evidence, multiple exits worth testing.
- `freshness_strict_confirmation / 30s / long`: strongest raw family, with a safer 100+ sample expression through `breakeven_ratchet`.
- `oi_funding_continuation / 1m or 30s / long`: broad sample support and good pairing with breakeven/runner exits.
- `contrarian_crash_fade / 30s / long`: potentially valuable but needs adverse-regime and p10 caution.

## Best Exit Modules
- `breakeven_ratchet`: best reusable-looking exit.
- `state_machine`: strongest raw leader but highest de-duplication burden.
- `runner_trail`: retain for ablation.
- `fixed_tp_sl`: keep as control, not winner.

## Why Not Paper Yet
The strategy families need component isolation. The top raw rows are clustered. Some group-level median p10 values are negative even when best rows are strong. The execution stress is encouraging but not a replacement for paper replay. Therefore the honest gate is hold-for-ablation.

## Immediate Next Round
Run the generated config in `final/next_round_config_true_deep.yaml`. The first ablation should test one hypothesis only: `premium_basis_overheat / 30s / long`, with exits swapped while all cost and data assumptions remain fixed.
    