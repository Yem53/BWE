---
type: experiment
tags: [bwe, direction, post-pump, autoresearch, protocol, anti-overfit]
created: 2026-05-27
status: design
priority: high
---

# Round 12 — Post-Pump Direction Protocol (pre-registered)

> **Status: AWAITING APPROVAL. Plan only — no experiment is run until the user approves.**
> Designed via `autoresearch-plan`. Anti-p-hacking guardrails are mandatory and may not be silently disabled.

## 0. Problem reframe (driven by latest evidence)

The entry trigger (detect pump + enter) is **solved**. P&L is decided entirely by the post-pump path.
"Held-to-now" forensics on the 9 live losers: **7/9 eventually reverted below entry** (ME +13.6%, NOM +5.9%,
SUPER-D +12.0%, MMT +13.9%, D +7.7%, SUPER-C +5.5%, ERA +11.3%); only 2/9 truly ran away (BAN reached
−33% adverse = liquidation at 3×; GUA too new). So:

- The **direction (eventual down) is mostly RIGHT**. Losses come from **(a)** entering during the post-pump
  *overshoot* and getting stopped (−2.5 ATR ≈ −2.6%) before the reversion arrives, and **(b)** the rare true
  runaways that never revert and would liquidate at 3×.
- **Real research question is NOT "up or down?"** It is: **(T)** can we push entry to *after the overshoot peaks*
  (等顶) to dodge the shake-out, and **(R)** can we identify & skip the rare runaways?

**Hard constraint:** 3× isolated ⇒ ~+33% adverse = liquidation. Round-8 already proved widening SL / breakeven /
trailing / no-stop are ALL far worse (they rescue reverters but get destroyed by runaways). So "just hold / widen
the stop" is OFF THE TABLE. Interventions must be at **entry selection / timing**, evaluated in $ via the real engine.

Prior-art (claude-mem, honest): strict-live search (May 4–8) tried many branches (exit archs, selectors,
path-score, 1s aggTrade, atr-trail) → **all PASS=0**, and **converged on "entry quality is the bottleneck" (#607)**.
We attack that bottleneck, but with **sober odds** and a **relative** bar (beat baseline), since the old absolute
"strict PASS" bar was shown mathematically unreachable on 30d 妖币.

## 1. Objective & Baseline

**Objective function (primary, $-based, via the real engine):** a candidate filter/timing rule is judged ONLY by
whether it improves the SHORT strategy's **portfolio expectancy** measured by `calibrate.eval_window` /
`simulate_portfolio`:
- Primary: Δ`port_sum` (sum of net returns) AND Δ`Calmar` BOTH ≥ 0 and meaningful.
- Guardrails: `maxdd` not worse; must not reduce trade count to a statistically useless level (n floor).
- **Classification metrics (AUC / precision on the "runaway" class) are diagnostics only, NOT the acceptance bar.**
  A model with great AUC that does not improve $ on holdout is rejected.

**Baseline (required — measured, current live config):**
| strat | window | port_sum | wr | n | note |
|---|---|---|---|---|---|
| D_ASIA | 90d | **+79.0%** | 32% | 223 | recent-regime winner |
| D_ASIA | 196d | −23.1% | 33% | 456 | not all-weather |
| B_US_PM | 90d | **+124.4%** | ~41% | 186 | |
| B_US_PM | 196d | +66.7% | ~41% | 427 | |
- Exits (fixed; NOT being changed): B single tp5/sl2.5/240m; D single tp6/sl2.5/240m; Champion tp4/sl2.8/200m.
- "Revert base-rate" (= short P&L>0 at exit) to be recomputed in Phase 1 on the labeled population (≈ wr above).
- A candidate must **beat these baselines** on the relevant window(s) to be considered.

**Complexity field (Karpathy tie-breaker):** every candidate records `n_added_conditions` (extra filter params/
rules) and `n_features` (for L4). On equal $ performance, the **simpler** candidate wins. Single-feature filters
are preferred over the multi-feature model unless the model **beats the best single-feature filter on holdout**.

## 2. Levers = pre-registered hypotheses (direction + acceptance fixed BEFORE looking at results)

| ID | Lever | Pre-registered hypothesis (direction) | Variants (search space) | Data |
|----|-------|----------------------------------------|--------------------------|------|
| **L2** | Pump morphology / timing (等顶) | Entering *after* momentum rolls over beats entering mid-pump | (a) require `ret5_atr` crossed >0→≤0 before entry; (b) parabolic blow-off: ≥N consecutive green bars + accel>θ + a rejection bar, short only after rejection; (c) pump duration/steepness buckets (fast-steep vs slow-grind) | klines (free) |
| **L3** | Live small-sample hints | High `vol_zs` → continues (skip); RSI only marginally over floor → continues (raise floor) | (a) `vol_zs` upper cap ∈ {2.5,3,4,5}; (b) `rsi_min` floor ∈ {72,75,78,80} | klines (free) |
| **L4** | Multi-feature model | A combination predicts revert-vs-runaway better than any single feature | logistic-reg + gradient-boosted trees; features = morphology + vol_zs + rsi + OI-direction + regime + (premium/taker/LS, known-weak, included for completeness); used as a signal filter (drop predicted-runaways) | klines+metrics (free) |
| **L5** | BTC regime conditioning | Disabling/down-sizing a strategy in adverse regime improves expectancy (D loses in bull) | per-strategy on/off or size×0.5 by `btc_regime_at` ∈ {bull,bear,chop} | klines (free) |
| **L1** | Real liquidation volume | Liquidation-fed pumps behave differently post-exhaustion | **DEFERRED** — no free history (Binance archive 404). Plan: start free WS `!forceOrder@arr` collection NOW (forward-only, throttled) and/or buy Coinglass historical only if Phase 4 justifies. **NOT tested this round.** | paid/forward |

For L2/L3/L5 a "filter" is applied by masking the entry signal in `build_entry_mask` / re-running `eval_window`.
The acceptance test (same for all): **Δport_sum ≥0 AND ΔCalmar ≥0 on the dev folds AND the sealed holdout,
AND consistent SIGN across B and D** (a lever that helps B but hurts D, or flips across walk-forward folds, is noise).

**SEQUENCING (user decision): test levers STRICTLY ONE AT A TIME, in order L2 → L3 → L5 — each lever fully run,
reported, and judged before the next begins. Do NOT mix features across levers. L4 (the multi-feature model, which
by nature mixes) runs LAST and ONLY if L2/L3/L5 leave a gap. On 90d-only data L4 is the most overfit-prone, so it
must beat the best single-feature filter on the 35d holdout by a clear margin or be rejected outright.**

## 3. Foundation dataset (Phase 0 — gate for everything)

`pumps_labeled.parquet`: every "pump event" across all ~200 perps over the full history.
- **Event definition** (generalizes B/D/Champion triggers into one clean population): a 5m bar with
  `ret60_atr ≥ 4.0` AND `rsi ≥ 60`, per symbol, with a 4h cooldown (no overlapping events same symbol).
- **Features at the trigger bar** — computed using ONLY data at/strictly before the trigger (no look-ahead):
  morphology (ret5_atr, ret60_atr, consecutive-green count, accel = Δret5_atr, run duration & % distance from
  pre-pump base, upper-wick, body), vol_zs, rsi, atr_pct, taker, OI 1h change + OI-direction, premium, top/global
  LS, `btc_regime_at`.
- **Forward label** (the outcome a real short would get): simulate a short at the trigger using the SAME exit
  logic the strategies use (tp/sl ATR + 240m time-stop) via the existing engine → `outcome ∈ {revert_win,
  continue_loss, timestop±}`, plus `MFE`, `MAE` (max adverse — for the liquidation flag), `bars_to_peak`,
  `overshoot_pct`.
- **Sanity gates before any lever runs:** (i) every feature value within sane bounds (reuse feature_study gates);
  (ii) no-look-ahead audit (recompute 3 random events by hand, confirm features use only ≤trigger data);
  (iii) label balance + base-rates reported; (iv) liquidation flag = share of events with MAE ≥ 28%.

## 4. Data splits — WALK-FORWARD on the RECENT 90d ONLY (mandatory; single split rejected)

Per user decision: backtest the **recent ~90 days only** (妖币-active regime; older data is a different regime and
would dilute). Total window ≈ last 90d.
- **Sealed HOLDOUT = most recent 35 days** — touched exactly once, in Phase 4 final reveal. Never used for selection.
- **Dev = the remaining ~55 days**, walk-forward: expanding folds (train ~30d → validate ~12d → roll ~12d, ~2–3
  folds). A lever must hold across folds, not just on average.
- **Robustness anchors (the 196d cross-window check is GONE):** with only 90d the main guards become (1) the sealed
  35d **holdout**, (2) **cross-strategy consistency** (must help B AND D, not flip), (3) the **complexity penalty**
  (prefer the simplest rule). These carry more weight now.
- ⚠️ **Honest trade-off (flagged):** 90d-only = a single regime + thin data ⇒ **higher overfit risk** and weaker
  out-of-regime evidence than 196d would give. Accepted per your call; compensated by leaning hard on the holdout +
  cross-strategy + simplicity. Treat any 90d-only "win" as provisional until it survives forward live.

## 5. Stopping conditions (any one)

- All pre-registered L2/L3/L5 hypotheses tested + L4 model search done (budget ≤10 optuna/GBM iterations).
- ≥5 consecutive variants with no dev improvement on a lever → stop that lever.
- Then the SINGLE holdout reveal (Phase 4). No re-tuning after the reveal.

## 6. Anti-overfit guardrails (default ON, cannot be silently disabled)

- Train/dev results are NOT reported as "results"; only holdout-confirmed survivors are.
- **Multiple comparisons:** we test 4 levers × several variants + a model → expect false positives. Require
  cross-window + cross-strategy CONSISTENCY (not single-window significance). If total experiments ≥30, apply
  **BH-FDR** to any p-values reported and say so.
- L4 model: **nested CV** (inner = hyperparam, outer = generalization) on dev, then ONE holdout check; must beat
  the best single-feature filter on holdout or be rejected (complexity not justified).
- **Anomaly self-check:** any candidate showing a suspiciously large jump (e.g. wr +15pts, or port_sum 2×) triggers
  a mandatory look-ahead / leakage audit before it's believed.
- **All experiments logged, including failures.** No dropping of inconvenient runs.
- Honest negative reporting: if a lever is noise, it is written down as noise (like the 884-trade study did).
- **Live-change gate:** nothing goes live without holdout pass + explicit user confirmation (real $500, 3× lev).

## 7. Engineering contract

- Dir: `40_EXPERIMENTS/round12_post_pump_direction/`.
- `pumps_labeled.parquet` (foundation) + `experiments.jsonl` (one line/experiment):
  `{timestamp, phase, lever_id, iteration, config, complexity, train_metric, dev_metric, holdout_metric|null,
   is_new_best, runtime_sec, anomaly_flags, notes}`.
- Reuse: `round8_calibration/calibrate.py` (eval_window, build_entry_mask, simulate_portfolio, btc_regime_at,
  make_splits) + `feature_study/` data.binance.vision loaders. Costs already modeled (SLIPPAGE_PCT + funding +
  fees); also model the live 0.8% slippage-abort.
- Reproducibility: fixed seeds; record lib versions (numpy/pandas/sklearn); data snapshot = immutable
  data.binance.vision archive paths.
- Risk metric set (reported for every survivor): port_sum, port_wr, maxdd, Calmar, Sortino, max-consecutive-losses,
  liquidation-exposure (kept trades with MAE ≥28%), regime-binned breakdown (bull/bear/chop).

## 8. Phases & expected artifacts

| Phase | Work | Artifact | Gate |
|---|---|---|---|
| 0 | Build + sanity-check labeled pump dataset | `pumps_labeled.parquet` + data-quality report | sanity must pass |
| 1 | Measure baseline + revert base-rate on dev (holdout sealed) | baseline table | — |
| 2 | Pre-registered single-lever tests L2/L3/L5 on walk-forward dev | per-lever verdicts | — |
| 3 | Multi-feature model L4 (nested CV on dev) | model + as-filter dev result | must beat best single-feature |
| 4 | Combine survivors → **single holdout reveal** → go/no-go report | final report | user confirm before live |
| 5 (future) | Liquidation integration plan (WS now / Coinglass later) | plan only | — |

## 9. Decisions (user-confirmed 2026-05-27)

1. **Holdout = 35 days.** ✓
2. **Backtest window = recent 90 days ONLY** (no 196d). ✓ — robustness trade-off flagged in §4.
3. **Strictly sequential, one lever at a time** (L2 → L3 → L5, then L4 last/optional). ✓ — no mixed-feature testing.

### Coinglass / Liquidation (L1) cost reality
Tiers: Hobbyist $29/mo · Startup $79/mo · **Standard $299/mo** · Professional $699/mo.
- Cheap tiers ($29/$79) give only **DAILY** liquidation history → **useless** for 5-minute pump analysis.
- The **5m/15m liquidation history we need is locked to Standard = $299/mo**.
- Practical path if pursued: buy **one month ($299)**, pull + cache the 90d of 5m liquidation history for the
  pump-event symbols (immutable → cache once), run L1, cancel.
- ⚠️ Quality caveat: source-throttled by Binance; our small-cap 妖币 trade mostly on Binance so cross-exchange
  aggregation helps little → likely the noisiest/sparsest liquidation data; some new perps may be uncovered.
- **Decision: DEFER.** Run free L2/L3/L5 first; buy the $299 one-month for L1 only if they leave a gap. Optionally
  start the free WS `!forceOrder@arr` forward-collector now ($0) to bank 5m liquidation history for a future round.
