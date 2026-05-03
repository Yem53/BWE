# Strategy Architect Round 1 Memo

## Leading Complete Strategy Shape
- Top strategy: `v6_f468dea25e7faf1bcd` family `freshness_strict_confirmation` side `long` timing `30s` exit `state_machine` sample tier `early_alpha`.
- Top entry catalog family: `premium_basis_overheat` timing `30s` side `long`.
- Top exit catalog family: `breakeven_ratchet` side `long`.

## Architecture Call
The next design should separate entry edge from exit harvesting: hold the best exit modules fixed while mutating entry conditions, then hold the best entry modules fixed while swapping exits.

## Entry Anchors
| strategy_family               | side   | entry_timing   |   tested_strategies |   sample_gt15_count | best_strategy_id      | best_sample_tier            |   best_median_net_pct |   median_p10_net_pct |   positive_stress_rate_pct |
|:------------------------------|:-------|:---------------|--------------------:|--------------------:|:----------------------|:----------------------------|----------------------:|---------------------:|---------------------------:|
| premium_basis_overheat        | long   | 30s            |                2641 |                2641 | v6_28d858af6439dc2b01 | higher_confidence_watchlist |               20.1791 |             -2.22416 |                    95.797  |
| oi_funding_continuation       | long   | 1m             |                5476 |                5476 | v6_871de8c3a69cf23372 | higher_confidence_watchlist |               18.8787 |             -2.22416 |                    94.9963 |
| contrarian_crash_fade         | long   | 30s            |               18694 |               18694 | v6_b1c1ca8225d6820489 | higher_confidence_watchlist |               20.1791 |             -4.22416 |                    87.3114 |
| freshness_strict_confirmation | long   | 30s            |                5751 |                5751 | v6_691c612b10d572162f | validated_watchlist         |               23.2943 |             -2.22416 |                    94.9052 |
| oi_funding_continuation       | long   | 30s            |                 298 |                 298 | v6_62a7735fcc14133733 | higher_confidence_watchlist |               21.8662 |             -2.22416 |                   100      |
| oi_funding_continuation       | long   | 1m             |               10776 |               10776 | v6_f70c9ed57173dd6a00 | higher_confidence_watchlist |               20.0794 |             -1.82416 |                    88.9105 |
| liquidity_filtered_momentum   | long   | T0             |                8607 |                8607 | v6_1119ad97a5655ef5ec | higher_confidence_watchlist |               17.4629 |             -3.22416 |                    89.8571 |
| oi_funding_continuation       | long   | 3m             |                4184 |                4184 | v6_7e52621494b6ff6de9 | exploratory_watchlist       |               16.3512 |             -5.22416 |                    86.5918 |

## Exit Anchors
| exit_family            | side   |   horizon_min |   tested_strategies |   sample_gt15_count | best_strategy_id      | best_sample_tier            |   best_median_net_pct |   median_p10_net_pct |   positive_stress_rate_pct |
|:-----------------------|:-------|--------------:|--------------------:|--------------------:|:----------------------|:----------------------------|----------------------:|---------------------:|---------------------------:|
| breakeven_ratchet      | long   |           240 |               19942 |               19942 | v6_28d858af6439dc2b01 | higher_confidence_watchlist |              21.8662  |             -3.22416 |                        100 |
| runner_trail           | long   |           240 |               20674 |               20674 | v6_a007baac46dfabbc59 | higher_confidence_watchlist |              19.6109  |             -3.22416 |                        100 |
| state_machine          | long   |           240 |               20312 |               20312 | v6_bb5a10b92455024a2a | higher_confidence_watchlist |              23.2943  |             -3.22416 |                        100 |
| time_decay             | long   |           240 |               16329 |               16329 | v6_2e078d5e7379ffb44f | higher_confidence_watchlist |              19.2482  |             -4.22416 |                        100 |
| indicator_invalidation | long   |           240 |                4050 |                4050 | v6_ef65d121e8a0c33a26 | higher_confidence_watchlist |              19.7098  |             -5.22416 |                        100 |
| failed_continuation    | long   |           240 |               11422 |               11422 | v6_8f21b07ab27a9ca722 | validated_watchlist         |              20.8055  |             -5.22416 |                        100 |
| fixed_tp_sl            | long   |           240 |                8804 |                8804 | v6_ca60f9ead3c1807ba3 | higher_confidence_watchlist |               7.77584 |             -2.22416 |                        100 |
| partial_ladder         | long   |           240 |               14175 |               14175 | v6_58bc6eedb077fcdf78 | higher_confidence_watchlist |              13.0094  |             -3.22416 |                        100 |

## Architecture Tests
- Entry isolation: pair the same entry family with fixed TP/SL, breakeven, and state-machine exits.
- Exit isolation: pair the same exit family with the strongest and a neutral entry family.
- Timing isolation: keep conditions fixed while sweeping T0, 30s, 1m, 3m, and 5m.
- Side isolation: verify whether long dominance is structural or merely a data-window artifact.
