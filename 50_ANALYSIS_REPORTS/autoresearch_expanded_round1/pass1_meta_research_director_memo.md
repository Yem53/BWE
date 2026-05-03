# Meta Research Director Round 1 Memo

- Source stage: max_alpha_gpu_fused_strong.
- Candidate space sample: 500000000000.
- Rows analyzed: 200000.
- Path resolution: 1m_trade_kline.
- Scope: paper-sandbox research only.
- Sample tiers: {'higher_confidence_watchlist': 130180, 'exploratory_watchlist': 28228, 'validated_watchlist': 22023, 'early_alpha': 19569}.
- Hypothesis decisions: {'watchlist_needs_ablation': 79, 'watchlist_paper_probe': 1}.
- Hypothesis kinds: {'entry': 20, 'exit': 20, 'complete_strategy': 25, 'risk_exit_neighborhood': 15}.

## Assessment
The run should be treated as a strong discovery pass, not as promotion evidence by itself. The correct AutoResearch move is to preserve the full strategy objects while forcing the next pass to test one hypothesis at a time.

## Directives
- Keep the GPU fused strong run as the main source of truth for this round.
- Use the base and CPU branches only as reference inputs if their artifacts are present.
- Drive the next pass from the hypothesis ledger and reject log, not from a fresh unconstrained brainstorm.
- Rank both profit and stability; do not collapse them into one view.

## Evidence Anchors
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

## Governance Upgrade
The most important upgrade is not another wider search. It is the conversion of results into a repeatable research program. Every hypothesis now has a source, a sample tier, an evidence packet, a decision, and a next action. That makes future rounds auditable and prevents repeated testing of the same weak idea under a new label.

## Stop/Continue Rule
Continue only through focused ablations. Stop broad expansion until at least one complete strategy family survives component isolation, neighborhood stability, and execution-cost stress.
