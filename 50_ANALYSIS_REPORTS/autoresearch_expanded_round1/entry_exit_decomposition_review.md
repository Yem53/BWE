# Entry Exit Decomposition Review

## Top Entry Modules

| strategy_family               | side   | entry_timing   | best_strategy_id      | best_sample_tier            |   best_median_net_pct |   entry_catalog_score |
|:------------------------------|:-------|:---------------|:----------------------|:----------------------------|----------------------:|----------------------:|
| premium_basis_overheat        | long   | 30s            | v6_28d858af6439dc2b01 | higher_confidence_watchlist |               20.1791 |              0.885534 |
| oi_funding_continuation       | long   | 1m             | v6_871de8c3a69cf23372 | higher_confidence_watchlist |               18.8787 |              0.853883 |
| contrarian_crash_fade         | long   | 30s            | v6_b1c1ca8225d6820489 | higher_confidence_watchlist |               20.1791 |              0.852524 |
| freshness_strict_confirmation | long   | 30s            | v6_691c612b10d572162f | validated_watchlist         |               23.2943 |              0.837379 |
| oi_funding_continuation       | long   | 30s            | v6_62a7735fcc14133733 | higher_confidence_watchlist |               21.8662 |              0.825631 |
| oi_funding_continuation       | long   | 1m             | v6_f70c9ed57173dd6a00 | higher_confidence_watchlist |               20.0794 |              0.816893 |
| liquidity_filtered_momentum   | long   | T0             | v6_1119ad97a5655ef5ec | higher_confidence_watchlist |               17.4629 |              0.812913 |
| oi_funding_continuation       | long   | 3m             | v6_7e52621494b6ff6de9 | exploratory_watchlist       |               16.3512 |              0.812039 |
| freshness_strict_confirmation | long   | 30s            | v6_4aea03e3fa32fdedbb | higher_confidence_watchlist |               23.1044 |              0.794272 |
| state_machine_runner          | long   | T0             | v6_d559b598378bae1f75 | higher_confidence_watchlist |               19.7758 |              0.767184 |
| message_context_breakout      | long   | 30s            | v6_8fd162e0643145aba7 | higher_confidence_watchlist |               19.2239 |              0.76699  |
| state_machine_runner          | long   | 3m             | v6_043741d443ad66e4bd | higher_confidence_watchlist |               18.0512 |              0.760971 |
| premium_basis_overheat        | long   | 1m             | v6_970501f9a03644c302 | higher_confidence_watchlist |               16.824  |              0.752913 |
| message_context_breakout      | long   | 5m             | v6_1829dccd8a1642840c | higher_confidence_watchlist |               19.3536 |              0.742524 |
| contrarian_crash_fade         | long   | 1m             | v6_dd230398eee54900a4 | higher_confidence_watchlist |               15.3182 |              0.735146 |
| state_machine_runner          | long   | T0             | v6_5fd8d71833e2bdc03e | higher_confidence_watchlist |               17.7848 |              0.734369 |
| premium_basis_overheat        | long   | 5m             | v6_c333aad2e6801e6b48 | higher_confidence_watchlist |               17.094  |              0.732621 |
| contrarian_crash_fade         | long   | 30s            | v6_0e881c4a17252008a9 | higher_confidence_watchlist |               16.4444 |              0.728835 |
| cross_channel_continuation    | long   | 1m             | v6_a71546ec4dcdcf990d | higher_confidence_watchlist |               18.356  |              0.71301  |
| message_context_breakout      | long   | 30s            | v6_d9ba92d563a253692b | higher_confidence_watchlist |               16.1722 |              0.710777 |

## Top Exit Modules

| exit_family            | side   |   horizon_min | best_strategy_id      | best_sample_tier            |   best_median_net_pct |   exit_catalog_score |
|:-----------------------|:-------|--------------:|:----------------------|:----------------------------|----------------------:|---------------------:|
| breakeven_ratchet      | long   |           240 | v6_28d858af6439dc2b01 | higher_confidence_watchlist |             21.8662   |             0.891176 |
| runner_trail           | long   |           240 | v6_a007baac46dfabbc59 | higher_confidence_watchlist |             19.6109   |             0.875588 |
| state_machine          | long   |           240 | v6_bb5a10b92455024a2a | higher_confidence_watchlist |             23.2943   |             0.873235 |
| time_decay             | long   |           240 | v6_2e078d5e7379ffb44f | higher_confidence_watchlist |             19.2482   |             0.86     |
| indicator_invalidation | long   |           240 | v6_ef65d121e8a0c33a26 | higher_confidence_watchlist |             19.7098   |             0.847647 |
| failed_continuation    | long   |           240 | v6_8f21b07ab27a9ca722 | validated_watchlist         |             20.8055   |             0.845882 |
| fixed_tp_sl            | long   |           240 | v6_ca60f9ead3c1807ba3 | higher_confidence_watchlist |              7.77584  |             0.827353 |
| partial_ladder         | long   |           240 | v6_58bc6eedb077fcdf78 | higher_confidence_watchlist |             13.0094   |             0.823529 |
| multi_tp_sl            | long   |           240 | v6_f659bda7526d587034 | higher_confidence_watchlist |             11.7758   |             0.810882 |
| prove_or_exit          | long   |           240 | v6_997445e7aff00de3b8 | validated_watchlist         |             17.4547   |             0.721618 |
| state_machine          | long   |            60 | v6_54789516a3b59f96d5 | higher_confidence_watchlist |              0.989471 |             0.718235 |
| time_decay             | short  |           240 | v6_fc8c485029e44f9413 | exploratory_watchlist       |             23.8217   |             0.718088 |
| state_machine          | long   |           120 | v6_e85033808beead644d | validated_watchlist         |              3.73746  |             0.706471 |
| breakeven_ratchet      | long   |           120 | v6_5ce75e75efb7d471c9 | higher_confidence_watchlist |              1.69947  |             0.695147 |
| runner_trail           | long   |           120 | v6_f5467e06cc08d1bb98 | exploratory_watchlist       |              8.97265  |             0.694118 |
| breakeven_ratchet      | short  |           240 | v6_c0eed5ab8431a36210 | early_alpha                 |             14.9566   |             0.658235 |
| time_decay             | long   |            60 | v6_7c40b7f9a1ce8c58c6 | validated_watchlist         |              0.545209 |             0.65     |
| partial_ladder         | long   |           120 | v6_66b4485ff6e60ff2de | exploratory_watchlist       |              4.40255  |             0.637206 |
| fixed_tp_sl            | long   |           120 | v6_c1f4436eb266aa6d21 | validated_watchlist         |              2.94603  |             0.636029 |
| failed_continuation    | long   |            60 | v6_afd57bb7682fd2e1a9 | exploratory_watchlist       |              0.922849 |             0.621324 |

## Top Complete Modules

| strategy_family               | side   | entry_timing   | exit_family            | best_strategy_id      | best_sample_tier            |   best_median_net_pct |   combined_funnel_score |
|:------------------------------|:-------|:---------------|:-----------------------|:----------------------|:----------------------------|----------------------:|------------------------:|
| oi_funding_continuation       | long   | 1m             | breakeven_ratchet      | v6_f70c9ed57173dd6a00 | higher_confidence_watchlist |               20.0794 |                0.853812 |
| freshness_strict_confirmation | long   | 30s            | breakeven_ratchet      | v6_4aea03e3fa32fdedbb | higher_confidence_watchlist |               21.8662 |                0.850359 |
| oi_funding_continuation       | long   | 1m             | runner_trail           | v6_a007baac46dfabbc59 | higher_confidence_watchlist |               17.982  |                0.842063 |
| contrarian_crash_fade         | long   | 30s            | breakeven_ratchet      | v6_b1c1ca8225d6820489 | higher_confidence_watchlist |               20.1791 |                0.840359 |
| state_machine_runner          | long   | T0             | state_machine          | v6_193850a81510091fa9 | higher_confidence_watchlist |               15.3114 |                0.822646 |
| contrarian_crash_fade         | long   | 30s            | state_machine          | v6_bb5a10b92455024a2a | higher_confidence_watchlist |               16.6358 |                0.820045 |
| freshness_strict_confirmation | long   | 30s            | time_decay             | v6_2e078d5e7379ffb44f | higher_confidence_watchlist |               18.4457 |                0.81296  |
| premium_basis_overheat        | long   | 30s            | breakeven_ratchet      | v6_28d858af6439dc2b01 | higher_confidence_watchlist |               20.1791 |                0.809821 |
| contrarian_crash_fade         | long   | 30s            | runner_trail           | v6_4fcb9eb4b2b00b7dfd | higher_confidence_watchlist |               15.7235 |                0.807937 |
| state_machine_runner          | long   | T0             | indicator_invalidation | v6_e7a7efed551c0270c9 | higher_confidence_watchlist |               18.1758 |                0.80426  |
| freshness_strict_confirmation | long   | 30s            | failed_continuation    | v6_8f21b07ab27a9ca722 | validated_watchlist         |               20.8055 |                0.802287 |
| freshness_strict_confirmation | long   | 30s            | state_machine          | v6_7e3f77086aad66284a | higher_confidence_watchlist |               23.2943 |                0.79435  |
| oi_funding_continuation       | long   | 30s            | breakeven_ratchet      | v6_62a7735fcc14133733 | higher_confidence_watchlist |               21.8662 |                0.790538 |
| contrarian_crash_fade         | long   | 30s            | indicator_invalidation | v6_ef65d121e8a0c33a26 | higher_confidence_watchlist |               18.5469 |                0.784305 |
| premium_basis_overheat        | long   | 30s            | runner_trail           | v6_bac7412912c100cee2 | higher_confidence_watchlist |               15.1001 |                0.780179 |
| premium_basis_overheat        | long   | 30s            | state_machine          | v6_3b209ada5128e04308 | higher_confidence_watchlist |               15.9604 |                0.779462 |
| oi_funding_continuation       | long   | 3m             | runner_trail           | v6_7e52621494b6ff6de9 | exploratory_watchlist       |               16.3512 |                0.777803 |
| premium_basis_overheat        | long   | 30s            | indicator_invalidation | v6_247669ac1f1496c94a | higher_confidence_watchlist |               18.5469 |                0.776861 |
| contrarian_crash_fade         | long   | 30s            | partial_ladder         | v6_08c905f8b420a36d0f | higher_confidence_watchlist |               12.7188 |                0.77278  |
| state_machine_runner          | long   | T0             | breakeven_ratchet      | v6_d559b598378bae1f75 | higher_confidence_watchlist |               19.7758 |                0.769955 |