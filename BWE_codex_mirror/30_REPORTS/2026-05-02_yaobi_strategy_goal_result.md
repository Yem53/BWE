# Yaobi Strategy Goal Result

Generated: 2026-05-02 21:30 America/New_York

> Superseded notice, 2026-05-02 22:37 EDT:
> the long `breakeven_ratchet` candidate family in this report is invalidated
> by the later strict 1m high/low state-machine replay. Do not use the
> `breakeven_ratchet` rows below as qualifying strategies. The replacement
> evidence is `30_REPORTS/2026-05-02_exact_high_low_retest.md` and
> `codex_discovery/runs/20260503T021854Z_exact_v6_state_machine_replay_all_objective_unique/`.

## Verdict

Current data supports a qualifying generic long strategy, but does not support any qualifying generic short strategy under the current objective gates.

This is a data-backed hard blocker, not a missing run:

- Long side: found and replayed 60 objective-pass generic long strategies.
- Short side: no objective-pass strategy after single-rule exact search, oracle-exit refinement, focused short search, and fixed-priority combo search.
- The short failure mode is stable: high-frequency short paths keep win rate but collapse mean return; high-mean short paths cannot reach the required monthly trigger count.

Objective gates used by the active scripts:

- `win_rate >= 75%`
- `monthly_triggers >= 500`
- `sum_return >= 2000%`
- `mean_return >= 8%`

Robust gates additionally require sufficient validation sample, positive validation mean, validation win rate, symbol diversification, and p10 loss control.

## Long Strategy Candidate

Superseded: this section used the older v6 MFE/MAE-style replay. The later
strict high/low replay found `breakeven_ratchet` has zero objective-pass rows
after same-candle washout handling.

Source run:

- `codex_discovery/runs/20260502T231744Z_v6_archive_replay/`

Best qualifying long replay rows:

| strategy_id | side | event_type | delay | exit | sample | monthly | win | mean | sum | top_symbol |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `v6_88eb1863db9eb3aa91` | long | pump | 180s | breakeven_ratchet | 645 | 841.30 | 79.07% | 25.00% | 16127.56% | 9.30% |
| `v6_fc31825e171ca67228` | long | pump | 300s | breakeven_ratchet | 645 | 841.30 | 77.83% | 24.86% | 16032.16% | 9.30% |
| `v6_3fe4bcde79ce0375e5` | long | pump | 30s | breakeven_ratchet | 700 | 807.69 | 78.71% | 25.76% | 18032.18% | 6.00% |

Usable generic long shape:

- Side: long
- Event type: pump
- Entry: delayed continuation entry after BWE/pump event, tested with 30s to 300s delays
- Exit: breakeven ratchet / failed-continuation family
- Status: objective-pass in replay, paper-only; not live-approved

## Short Search Evidence

### Focused Short Exact Search

Source run:

- `codex_discovery/runs/20260503T005819Z_short_focused_exact/`

Coverage:

- 180 symbols
- 6,640,095 one-minute rows
- 5,760 short entry rules
- 368 exit definitions
- 1,600 retained exact rows
- Numeric pass: 0
- Robust pass: 0

Best high-frequency short row:

| template | exit | sample | monthly | win | mean | sum | val_win | val_mean | top_symbol |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| focused_pullback_after_pump | trail_arm8_trail3_lock8_sl0_max240m | 848 | 844.13 | 76.18% | 2.86% | 2424.91% | 80.63% | 4.07% | 9.08% |

Best short row with `monthly >= 500` and `win >= 75`:

| template | exit | sample | monthly | win | mean | sum | val_win | val_mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| focused_failed_pump_wick | trail_arm8_trail3_lock8_sl0_max240m | 569 | 566.40 | 81.02% | 4.00% | 2274.67% | 78.01% | 3.38% |

Focused short rows with `monthly >= 500` and `mean >= 8`: 0.

### Short Combo Search

Source runs:

- `codex_discovery/runs/20260503T011807Z_short_combo_exact/`
- `codex_discovery/runs/20260503T012604Z_short_combo_exact/`

Best high-quality short combo:

| run | components | sample | monthly | win | mean | sum | val_win | val_mean | top_symbol |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `20260503T011807Z_short_combo_exact` | 6 | 420 | 417.90 | 75.00% | 9.04% | 3795.72% | 81.51% | 11.69% | 9.29% |

This fails only the monthly trigger gate.

Best frequency-side combo with `monthly >= 500` and `win >= 75`:

| run | components | sample | monthly | win | mean | sum | val_win | val_mean | top_symbol |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `20260503T012604Z_short_combo_exact` | 4 | 832 | 827.67 | 78.61% | 5.78% | 4809.90% | 84.88% | 7.95% | 8.53% |

This fails the mean-return gate.

Frequency-prioritized combos proved the trade-off:

- `monthly >= 500`: 640 retained combo rows
- `monthly >= 500` and `win >= 75`: 214 retained combo rows
- `monthly >= 500` and `mean >= 8`: 0 retained combo rows
- `monthly >= 500`, `win >= 75`, and `mean >= 8`: 0 retained combo rows

## Decision

Do not promote any short strategy from this run.

Recommended current strategy set:

- Long: superseded by strict high/low replay; use the later failed-continuation long candidate set, not the `breakeven_ratchet` rows listed above.
- Short: keep the best short combo only as a research near-miss, not as a qualifying strategy.

Short-side blocker:

- The current one-minute exact replay data does not contain a generic yaobi short strategy that simultaneously reaches 500 monthly triggers, 75% win rate, 2000% total return, and 8% mean return.

Required unblock options:

- Relax one short-side gate, most likely mean return from 8% to about 5.5%-6.0%, or monthly triggers from 500 to about 350-420.
- Add higher-resolution historical data beyond the available current 1s partial window, then retest exit timing.
- Change the short-side strategy definition from generic all-yaobi to a narrower event regime; this would no longer satisfy the current "generic for all yaobi" requirement.

## Archive

New or updated Codex-only artifacts:

- `codex_discovery/scripts/search_short_focused_exact.py`
- `codex_discovery/scripts/search_short_combo_exact.py`
- `codex_discovery/runs/20260503T005819Z_short_focused_exact/`
- `codex_discovery/runs/20260503T011807Z_short_combo_exact/`
- `codex_discovery/runs/20260503T012604Z_short_combo_exact/`
- `10_GRAPH/Strategy_Search_MOC.md`
- `10_GRAPH/Strategy_Search_Relationships.md`
- `10_GRAPH/Strategy_Search.canvas`
- `99_ADMIN/VAULT_SYNC_LOG.md`

No files under `/Volumes/T9/BWE` were modified.
