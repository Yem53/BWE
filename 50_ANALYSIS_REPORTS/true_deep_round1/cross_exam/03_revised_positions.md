# Revised Positions After Cross Examination

## Advanced Hypotheses
- Advance `premium_basis_overheat / 30s / long` as the first entry-family ablation.
- Advance `freshness_strict_confirmation / 30s / breakeven_ratchet / long` as the first high-confidence complete-strategy ablation.
- Advance `oi_funding_continuation / 1m / breakeven_ratchet / long` as the broad-sample continuation hypothesis.

## Held Hypotheses
- Hold `freshness_strict_confirmation / 30s / state_machine / long` as early-alpha raw leader until cluster representative and higher-sample checks are complete.
- Hold short-side discoveries for a separately balanced probe; do not conclude short is invalid from the current retained distribution.

## Demotion Criteria
- Demote any candidate whose positive median disappears under fixed TP/SL control.
- Demote any candidate whose p10 becomes materially worse after cluster de-duplication.
- Demote any candidate whose stressed median turns negative under cost/latency/missed-fill stress.
- Demote any early-alpha candidate that cannot reappear in adjacent parameter neighborhoods.
