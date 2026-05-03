# Exact High/Low Retest

Generated: 2026-05-02 22:37 EDT

## Verdict

The strict intrabar rule is now a hard gate.

Every future strategy must pass candle-by-candle 1m `high/low` replay before it can be called valid. A strategy that claims later favorable movement after the same candle would already have hit stop, breakeven, or trailing stop is not valid.

Full retest result:

- Source: `codex_discovery/runs/20260502T231209Z_v6_archive_audit/v6_archive_objective_pass.csv`
- Source rows before dedupe: 33,380
- Unique strategy IDs retested: 19,235
- Strict objective pass: 5,221
- Long strict pass: 5,221
- Short strict pass: 0
- Path resolution: `1m_trade_kline_forced_codex_exact_state_machine`
- Output run: `codex_discovery/runs/20260503T021854Z_exact_v6_state_machine_replay_all_objective_unique/`

## Exact Replay Contract

The replay rule used here is conservative and explicit:

- Entry price uses the archived strategy delay mapped to the normalized 1m trade-kline event path.
- For each post-entry candle, adverse stop is checked before favorable target or trailing activation when both happen inside the same candle.
- Long stops use candle `low`; short stops use candle `high`.
- Long profit activation uses candle `high`; short profit activation uses candle `low`.
- Breakeven and trailing exits can be washed out on the same candle where they activate.
- `failed_continuation` checks initial stop before the early continuation close check.
- `time_decay` uses intrabar stop first, otherwise time-exit return is decayed.
- `multi_tp_sl` and `partial_ladder` are marked non-pass for now because the archived payload does not contain enough unambiguous partial-fill state-machine rules.

## Retest Counts

| Exit family | Retested | Strict pass | Decision |
|---|---:|---:|---|
| failed_continuation | 3,496 | 3,285 | keep for candidate pool |
| time_decay | 2,061 | 1,921 | keep for candidate pool |
| indicator_invalidation | 815 | 13 | keep only after further manual review |
| runner_trail | 3,904 | 2 | keep only after further manual review |
| breakeven_ratchet | 3,865 | 0 | invalidated |
| state_machine | 4,299 | 0 | invalidated under this replay |
| partial_ladder | 720 | 0 | unsupported exact semantics, non-pass |
| multi_tp_sl | 75 | 0 | unsupported exact semantics, non-pass |

## Washout Evidence

The high/low logic materially changes the result.

| Exit family | Rows | Strict pass | Trades replayed | Same-candle washout exits | Same-candle washout share |
|---|---:|---:|---:|---:|---:|
| breakeven_ratchet | 3,865 | 0 | 2,921,053 | 1,789,809 | 61.27% |
| runner_trail | 3,904 | 2 | 2,940,652 | 1,943,975 | 66.11% |
| state_machine | 4,299 | 0 | 3,136,197 | 2,084,635 | 66.47% |

This is exactly the washout issue the user flagged. The old MFE/MAE-style replay let many strategies claim later favorable excursion even though a realistic stop would already have fired inside the candle.

## Old Long Candidates

The old final report named these `breakeven_ratchet` rows. They are no longer valid:

| Strategy | Old exit | Strict sample | Strict monthly | Strict win | Strict mean | Strict sum | Strict pass | Main exit evidence |
|---|---|---:|---:|---:|---:|---:|---|---|
| `v6_88eb1863db9eb3aa91` | breakeven_ratchet | 645 | 841.30 | 93.49% | 0.94% | 608.34% | false | 587 same-candle washouts |
| `v6_fc31825e171ca67228` | breakeven_ratchet | 645 | 841.30 | 91.78% | 1.20% | 774.92% | false | 532 same-candle washouts |
| `v6_3fe4bcde79ce0375e5` | breakeven_ratchet | 700 | 807.69 | 24.71% | 0.66% | 460.39% | false | 385 same-candle washouts |

## Strict Long Representative

A strict-passing long representative is:

- Strategy ID: `v6_982b322524d6a28283`
- Family: `liquidity_filtered_momentum`
- Side: long
- Event type: pump
- Entry timing: 3m
- Exit family: `failed_continuation`
- Conditions:
  - `marketcap <= 71,000,000`
  - `top_trader_long_short_account_ratio__longShortRatio >= 2.2404000759124756`
  - `global_long_short_account_ratio__longShortRatio >= 1.6828899383544922`
- Strict sample: 539
- Monthly trigger estimate: 703.04
- Win rate: 86.09%
- Mean net return: 27.73%
- Estimated total return: 14,945.05%
- Top symbol share: 5.19%
- Exit counts: 15 failed-continuation exits, 60 initial stops, 464 time exits
- Status: paper-only, not live-approved

## Short Status

The old archive objective-pass set contains no strict-passing short strategy. The independent short-focused exact searches were already high/low-path based and remained at zero objective pass:

- `codex_discovery/runs/20260503T005819Z_short_focused_exact/`: numeric pass 0, robust pass 0
- `codex_discovery/runs/20260503T011807Z_short_combo_exact/`: numeric pass 0, robust pass 0
- `codex_discovery/runs/20260503T012604Z_short_combo_exact/`: numeric pass 0, robust pass 0

Current hard conclusion is unchanged on the short side: no qualifying generic short strategy exists under the current gates.

## Forward Rule

From this point onward, a BWE_codex strategy is not allowed to enter the candidate set unless all of the following are true:

- The strategy has a deterministic entry rule.
- The exit rule is a deterministic state machine.
- The backtest scans each post-entry candle in order.
- Intrabar stop and washout checks use `high/low`, not only final close, MFE, or MAE aggregates.
- Same-candle adverse movement is handled conservatively.
- Unsupported or ambiguous exit semantics are non-pass until the state machine is specified and retested.

No live or paper promotion is implied by this retest.

