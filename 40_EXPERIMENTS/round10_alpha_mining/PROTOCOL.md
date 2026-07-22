# Round 10 — Autonomous Alpha Mining Protocol

> Karpathy autoresearch protocol. Designed 2026-05-23. **Read-only on all existing
> systems** (live bot/config/code/data untouched); all new output under
> `40_EXPERIMENTS/round10_alpha_mining/`. Approved budget: 7h wall-clock, autonomous.

## 0. Motivating finding (baselines)

The current live shorts (B/D) are **negative on every window that excludes the most-recent
30 days**, and only positive on the sealed last-30d. Their edge is **recent-regime-conditional**.

**TARGET (user-chosen 2026-05-23): hunt within the RECENT 3 MONTHS** (妖币 active regime). We
accept this is recent-regime alpha, not necessarily cross-regime-robust. Anti-overfit is still
enforced *within* the recent window via (a) a sealed most-recent hold-out and (b) walk-forward
consistency across sub-windows (a config must work across the recent period, not just one burst).
Older data (Nov–Feb) is used only as an informational contrast flag, NOT a selection gate.

| baseline | dev_recent90 (Jan16–Apr16) | dev_full (Nov1–Apr16) | sealed test (Apr16–May16) |
|---|---|---|---|
| B_US_PM (single tp5/sl2.5) | sum −66.5, wr 38, 2/6 | sum −82.4, wr 37, 1/6 | **SEALED** (reveal in report) |
| D_ASIA (single tp6/sl2.5) | sum −62.2, wr 31, 1/6 | sum −143.6, wr 32, 0/6 | **SEALED** |
| Champion_E (OI) | — (OI not in features npz; R29 holdout +130%/n40 = its baseline) | — | — |

## 1. Objective & baseline

- **Objective**: maximize `port_sum` (total portfolio return %, post cost+slippage+funding) on the
  selection set, **subject to gates** (frequency + consistency + anti-concentration). Secondary:
  calmar, maxdd, pos_windows (walk-forward consistency). Reason: project rule — sum balances
  frequency × quality; stability via gates.
- **Baseline to beat**: best of {B, D current} on the selection set = **negative** (see §0). A
  candidate is "alpha" only if it clears the gates AND beats baseline on dev-recent AND dev-full.
- **Complexity field**: log #filters / #params per config. Tie-breaker (Karpathy): within ε=1%
  port_sum, prefer fewer filters (more robust out-of-sample).

## 2. Data splits (anti-overfit core)

Data: 196d, 2025-11-01 → 2026-05-16, 200 syms × 282357 min (round7 npz + features).
**Focus = recent ~90d** (2026-02-16 → 05-16, the active regime).

- **SELECT / dev (primary)** = recent 90d minus the sealed tail = **2026-02-16 → 04-25 (~68d)**.
  All go/no-go + grid refinement here.
- **SEALED TEST** = **last ~21d (2026-04-25 → 05-16)**, the most-recent active regime. **Never
  used for selection.** Revealed only by `autoresearch-report` (the truest "works right now" check).
- **Walk-forward (primary anti-overfit within recent)**: `eval_window` splits the dev into 6
  sub-windows → require `pos_windows ≥ 4/6` (positive across the recent period, not one burst).
- **OLDER-DATA CONTRAST (flag only)** = Nov-01 → Feb-16: report each winner's sum here as a
  regime-robustness *flag*, but it is NOT a selection gate (user accepts recent-regime alpha).
- **Regime binning**: `eval_window` returns BTC bull/bear/chop breakdown → note for each winner.

## 3. Directions to coarse-screen (feasibility-checked against available data)

Available features (200×282357): `atr_pct, rsi, ret_60m, ret_5m, upper_wick, body_ret, vol_zs,
taker_ratio, pullback`. OI/funding/CVD-longshort are NOT precomputed.

| # | Direction | Feasible? | How |
|---|---|---|---|
| D1 | **Hour × side full sweep (incl. LONG)** | ✅ easy | vary hours_utc + side over base filters |
| D2 | **Long-side alpha** | ✅ easy | side="long", mirror filters (is there ANY long edge?) |
| D3 | **Entry-feature grid** (beyond B/D/Champ) | ✅ easy | grid over the 9 features + exits |
| D4 | **Multi-day hold mean-reversion** | ✅ easy | time_stop_min → 1–3 days; wider TP |
| D5 | **Exit-mechanism sweep on best new entry** | ✅ easy | advanced_exit_engine (single/trail/be/multi/decay) |
| D6 | **OI-driven** (spike / divergence / OI-MC band) | ⚠ needs join | join alert-archive `oi_chg` / data.binance.vision metrics `sum_open_interest` |
| D7 | **Micro-window reversion** (3s/60s/180s) | ⚠ needs join | alert archive event → 1m-kline exit sim (entry from archive) |
| D8 | **Multi-window / multi-channel confluence** | ⚠ needs join | alert archive: ≥2 windows fire on same sym in T |
| D9 | **妖币 lifecycle** (prior_pumps, repeated pump-dump) | ⚠ derive | count prior pumps from klines/alerts |
| ~~D10~~ | ~~Funding rate~~ | ❌ no data | **DROPPED** — no funding data available |

Order: screen the ✅-easy directions first (D1–D5), then the ⚠-join directions (D6–D9) if budget
remains or easy ones underwhelm. Drop any direction whose coarse screen fails go/no-go.

## 4. Coarse-screen go/no-go (per direction)

A direction is **GO** (→ refine grid) iff its best coarse config passes gates on the **SELECT/dev
window (Feb16–Apr25)**: `port_n ≥ 20`, `port_sum > 0`, `pos_windows ≥ 4/6`, `traded_syms ≥ 8`,
`top_share ≤ 35%`, `unique_days ≥ 8`. The older-data sum is recorded as a robustness *flag* (not a
gate). Else **NO-GO** → log, switch direction. (Coarse = ~10–20 configs per direction.)

## 5. Grid refinement (triggered on GO)

Focused grid (~30–80 configs) over the direction's key params, re-evaluated on DEV-recent +
DEV-full + 6-subwindow walk-forward. Keep configs passing gates on both; rank by dev-recent
port_sum with the simplicity tie-breaker.

## 6. Budget & hard-stops (autonomous)

- **Budget cap**: 200 experiments (each = one (entry,exit,split) eval). + **7h wall-clock hard stop.**
- **Hard stops** (any → stop & checkpoint):
  1. budget (200 exp) or 7h elapsed
  2. **looks-too-good** anomaly: any config with port_wr > 90% AND port_n > 20, OR
     dev_recent_sum/dev_full_sum implausibly huge (>5× any baseline) → flag data-leak, pause-log
  3. crash storm: 5 consecutive experiment exceptions
  4. no-improvement: 25 consecutive experiments with no new gated best across the active direction
     → switch direction; if all directions exhausted → apply "don't give up" (aggressive combos,
     near-miss mutations, revive prior near-misses) before stopping
- **Checkpoints**: write `checkpoints/round-N.md` every 5 rounds (autonomous — no soft stop).

## 7. Anti-overfit guardrails (forced)

1. **Confirmation** for any "alpha found" claim: gated-positive on the SELECT/dev window AND
   `pos_windows ≥ 4/6` (walk-forward consistency) — sealed-TEST confirmation reserved for the final
   report; older-data sum recorded as a regime-robustness flag.
2. **Test sealing**: never read the last-30d test for selection. (Even baselines' test metric sealed.)
3. **Full logging**: every experiment (incl. failures) appended to `experiments.jsonl`.
4. **Multiple-comparison**: at n_experiments ≥ 30, log BH-FDR warning; the triple-window +
   sealed-test requirement is the primary MC control (a config passing all 3 windows by chance is
   unlikely). Cap promoted "winners" to ≤5.
5. **Walk-forward**: pos_windows ≥ 4/6 required (no single-burst configs).
6. **Reproducible**: log seed + lib versions + data snapshot id per experiment.

## 8. Engineering contract

- Results: `round10_alpha_mining/experiments.jsonl`, one JSON/line:
  `{timestamp, iteration, direction, config, complexity, dev_recent, dev_full, is_new_best,
    runtime_sec, notes, anomaly_flags}` (dev_* = {port_n, port_sum, port_wr, pos_windows, calmar,
    maxdd, top_share, traded_syms, unique_days, regime}).
- Engine: reuse `round8/calibrate.py` (data load) + `eval_window` + `loop_search_framework`
  (build_entry_mask) + `advanced_exit_engine` (simulate_combo_advanced). New direction code
  (OI/micro/confluence joins) written as new modules under round10/, never touching existing files.
- Cost model: inherited from framework (SLIPPAGE_PCT + funding + cost_rt).

## 9. Termination

On any hard-stop: report trigger, top-≤5 gated configs (dev-recent + dev-full metrics, sealed-test
withheld), trend, budget used. Final reveal (sealed test) via `autoresearch-report`.
