# Lead Synthesizer Memo

## Consensus
All roles converge on the same conclusion: the run has real research signal, but the next move is not deployment and not another global max_alpha pass. The next move is focused ablation.

## Strongest Preliminary Families
1. `premium_basis_overheat / 30s / long`, especially with `indicator_invalidation`, `breakeven_ratchet`, `state_machine`, and `runner_trail`.
2. `freshness_strict_confirmation / 30s / long`, especially state-machine raw alpha and breakeven high-confidence alpha.
3. `oi_funding_continuation / 1m or 30s / long`, especially with breakeven and runner exits.
4. `contrarian_crash_fade / 30s / long`, useful but requiring p10 and adverse-regime caution.

## Strongest Exit Families
`breakeven_ratchet` is the most reusable-looking exit module. `state_machine` has the strongest raw top but needs de-duplication. `runner_trail` is worth retaining. `fixed_tp_sl` should remain the control.

## Final Synthesis
The AutoResearch upgrade is now qualitatively different from a leaderboard. It contains a hypothesis ledger, component catalogs, discovery queue, role critique, cross-examination, and next-round ablation plan. The value of the next round will come from proving which component actually carries the edge.

## Final Recommendation
Proceed to a focused ablation round in paper-sandbox mode only. Do not enter paper-shadow until the ablation round produces a de-duplicated, execution-stressed, future-safe complete strategy with stable p10 and positive baseline lift.
