# Auditor Report — Per-Symbol 妖币 Strategy v2

> **Role**: Fallback Auditor (heavyweight `/Agent-teams-plan` coordination layer)
> **Date**: 2026-04-29
> **Inputs**: `per_symbol_design_v2.md` + `archive/00_decision_log.md` + Phase 1-4 archive
> **Charter**: RISK + VERIFICATION + ACCEPTANCE GATING. Not a designer.

---

## 0. Executive Summary

The design is data-driven, evidence-anchored, backwards-compatible via flags, and documents its own limitations. The Phase 1-4 archive shows honest Caveats, including an explicit Hermes vs Broader L4 incomparability disclosure.

However, **several concrete blockers** stand between this spec and a clean execution gate:

1. The PAPER +12pp lift that justifies L2-per-lifecycle is a **single-sample / single-period** finding (one 30d window, 210 trades) and is **inconsistent with LIVE** (-48pp on 82 trades). Calling this "PAPER validation > LIVE evidence" is a tradeable thesis but it is **not robust generalization**, and the audit must treat this as a **structural overfit risk**, not as locked-in alpha.
2. Phase 4 picks `L2-per-lifecycle` for BWE despite LIVE losing -48pp. The decision rationale is "PAPER 验证更重要" (Phase 4 doc), but no out-of-sample test was run. **Mandatory: rolling-window or holdout validation before Phase 3 live.**
3. The `max_concurrent_trades=3` cap on Layer B has no risk-budget audit. With Layer B firing ~50/day and tier 12% positions, financial concentration risk under simultaneous catastrophes is **not bounded**. Numbers below.
4. The 5-phase gate criteria in §7 are too soft. "PAPER 3 天均 PnL > 0,胜率 > 60%" can be satisfied by random walk in trending tape. **Mandatory: minimum-trade-count + drawdown gates.**
5. No automated regression detector exists for the 2 lock-in baselines. Spec §13 is descriptive, not enforcing.

Status at end of audit: **REWORK REQUIRED** (5 blockers itemized in §7). All other items below are guardrails for the rework path.

---

## 1. Risk Register

### 1.1 Design Risks

| # | Risk | Severity | Likelihood | Mitigation | Detection |
|---|---|---|---|---|---|
| D1 | **Lifecycle label staleness** — weekly reaction + daily lifecycle batch may misclassify a symbol mid-regime change (e.g., a former `sustained` becomes `spike_decay`). Wrong ExitConfig is selected. | High | Med-High | Daily recompute lifecycle (already in spec §5.1); add 24h tripwire: if a position's symbol lifecycle changed in last 24h, log + flag. | Daily diff of `symbol_features.lifecycle`; monitor `lifecycle_change` rate. Threshold: > 10% of top-100 symbols flipping label per week → recompute window suspect. |
| D2 | **L2-per-lifecycle over-fits PAPER 30d window.** PAPER +12pp came from 210 trades concentrated in a regime where `pc_crash_bounce_long` happened to align with `sustained/late_burst`. LIVE lost -48pp on 82 trades. | **Critical** | High | Rolling 7d-window PAPER replay BEFORE Phase 3 enables live; if any window shows L2-per-lifecycle < L2-base by >20pp, fall back to L2-base. | Compute `total_raw[L2-per-lifecycle] / total_raw[L2-base]` per rolling 7d window over last 30d. Variance > 50pp = unstable. |
| D3 | **Rule engine first-match-wins ordering** is brittle. Rule C (mean_revert + sustained/single_burst) supersedes Rule D (score≥80 + low pre-vol) but the decision log shows the order was data-discovered, not theoretically grounded. A regime shift could invert which rule should fire first. | Med | Med | Quarterly re-discovery via `rule_discovery_v2.py`; lock current order behind a config flag `rule_order_version=v2_30d_2026_04`; alert on rule-trigger histogram drift. | Histogram of `rule_triggered` per week. If Rule C drops below 5% of all triggers (was ~22% in 1425 events), regime shift suspected. |
| D4 | **Top-100 dive coverage gap.** 18% (259/1425) of broader-market events fall outside top-100 dive set → default Rule A SKIP. Could be missing genuine alpha or correctly avoiding noise — unknown. | Med | High | Phase 4 review: aggregate skipped-event PnL had they been entered with default 5% fade; if > +50% raw aggregate → expand dive to top 200. | After Phase 4 paper, compute `would-be-trade PnL on Rule A SKIPs`; threshold +50% raw. |
| D5 | **Per-lifecycle config divergence between bot config and feature store.** If `feature_store.get(symbol)` returns `None` (new symbol, batch lag), default ExitConfig() is used — different from baseline `L2-base` which is always default. This is **hidden behavioral drift**. | Med | Med | Code path must explicitly log `lifecycle_lookup=missing` and emit metric. Alert if > 5% of trades enter via missing lifecycle path. | `lifecycle_lookup_missing_rate` metric in `entry_decisions`. |
| D6 | **Direction signal collision** between BWE and Market Scan when both fire on same symbol within a short window. Spec does not specify dedupe. | High | Med | Dedupe rule in `_open_position`: if symbol already has an open position from any source, second source request is rejected and logged. | New trade-rejection counter per source. |
| D7 | **Rule B/F follow vs BWE fade conflict** if both engines target same symbol. Layer A says short, Layer B says long — net zero or hedged unintentionally. | High | Low-Med (rare overlap) | Same dedupe (D6) plus per-symbol single-direction lock. | Same as D6. |
| D8 | **Wave detection in `market_scan_entry()`** uses 5-min closing returns; spec says `>= 8.0%`. No specification of micro-wave (multiple 8% events in 30 minutes for the same symbol re-firing). | Med | High | Cooldown per symbol after market-scan trigger: minimum 60 minutes before re-fire. | `market_scan_retrigger_lt_60min` counter. |

### 1.2 Execution Risks

| # | Risk | Severity | Likelihood | Mitigation | Detection |
|---|---|---|---|---|---|
| E1 | **Breaking live bot during `_open_position` hook integration.** `bwe_live_autotrader.py` is 92KB / 24/7 critical infra. | **Critical** | Med | Hook landed behind `exit_engine.use_v2=false` default. Touch only `_open_position`; add a `--config-validate` smoke that loads new fields against template. Pair-review the diff; ban any unrelated edits in the same commit. | CI: `python -m bwe_live_autotrader --validate-config`. Integration smoke must pass before merge. |
| E2 | **Market scan entry process drift.** Independent process means restart loop, crash recovery, port binding, log rotation all need to be re-implemented (not inherited from autotrader). | High | High | Reuse autotrader's `_open_position` via shared module import (not RPC). Watchdog must monitor PID and dump heartbeat to file; add cron entry parallel to existing watchdog. | Heartbeat freshness check (< 90s); PID liveness; log rotation size cap. |
| E3 | **Schema migration on live DB.** `binance_extended_history.sqlite3` is 3.3 GB; adding `symbol_features` and `entry_decisions` mid-flight could lock writers. | Med | Med | Schema additions only via `CREATE TABLE IF NOT EXISTS` + indexes built `CONCURRENTLY` (or `WITHOUT ROWID` separately); never during peak collector window. Run migration during a 5-min collector pause + watchdog mute. | Migration logs + post-migration sanity SELECT counts. |
| E4 | **Feature batch failure** on the daily compute job leaves stale `lifecycle/reaction` for new entries. | Med | High | Job failure → bot falls back to default ExitConfig (already covered by spec). Add hard cron alert if last `computed_at_ms` > 36 hours. | `freshness_age_hours` metric. |
| E5 | **Config flag flips mid-trade.** If user toggles `exit_engine.use_v2` from false→true while positions are open, those positions remain on baseline; new ones use v2 — operationally confusing. | Med | Med | Document explicitly: flag flips affect *new* trades only. Add `config_flip_audit_log`. | Config-version stamp on each open position. |

### 1.3 Operational Risks

| # | Risk | Severity | Likelihood | Mitigation | Detection |
|---|---|---|---|---|---|
| O1 | **VPN drop mid-batch leaves DB inconsistent.** Phase 2 archive shows 161 zombie symbols from this exact failure mode (`HTTP error 5 retry but mark done` bug). | High | High | Watchdog already in place (Decision #6). Recompute job must also be **VPN-state-aware**: if VPN down at `compute_symbol_features.py` start, the job exits without writing partial table updates (use staging table + atomic rename). | Watchdog log + zombie-count audit run weekly. |
| O2 | **Watchdog flapping.** Per-minute cron + multiple retry can mask underlying connectivity issue. | Med | Med | Watchdog should escalate (e.g., disable trading) after 30 consecutive minute-failures rather than retry forever. | Watchdog state file `consecutive_fail_count`. |
| O3 | **Cross-machine coordination.** Mac mini runs live bot; 5090 only when GPU loop. If H: drive moves while bot is live, bot dies. | High | Low (procedural) | Bot reads from `/Users/ye/.hermes/...` (local SSD, not H:); features DB at `/Users/ye/.hermes/research/binance_extended_history.sqlite3` is also local. No cross-machine dep. **Verify bot has zero H: drive read paths before Phase 3 live.** | `lsof | grep T9` while bot running → must return empty for bot PID. |
| O4 | **Log volume explosion.** `entry_decisions` table grows ~50 rows/day from market scan + ~10/day from BWE. 30 days = 1800 rows. Manageable, but `features_json TEXT` column unbounded. | Low | High | Cap `features_json` at 4KB; add WAL rotation policy. | Table size SELECT each Sunday. |
| O5 | **Crontab clobbering.** Watchdog is in user crontab; adding the daily feature-batch + market-scan watchdog increases cron complexity. Manual edits could collide. | Med | Med | All cron entries managed via single `bwe_crontab.txt` source-controlled file; `crontab bwe_crontab.txt` to apply. Diff before/after. | `crontab -l` snapshot in archive after each change. |

### 1.4 Financial Risks

| # | Risk | Severity | Likelihood | Mitigation | Detection |
|---|---|---|---|---|---|
| F1 | **12% tier × -29.9% worst case = -3.6% capital hit per trade.** Spec §9 already acknowledges. With 3 concurrent Layer B trades all at 12%, simultaneous catastrophe = -10.8% capital. | **Critical** | Low (per spec data: 41/1425 cat = 2.9%) but **stacks** under concurrent positions. | Hard rule: at most ONE 12% position open at a time, regardless of `max_concurrent_trades`. Other concurrent slots forced to ≤8%. | Position-table aggregator: sum of position_pct across open trades; alert > 25%. |
| F2 | **Layer A + Layer B concurrent stacking.** Spec specifies max_concurrent for Layer B = 3 but says nothing about Layer A interaction. Worst case: 1 Layer A 5% + 3 Layer B 12% = 41% capital exposed. Margin/leverage layered on top. | High | Med | Global `max_total_open_position_pct = 25%`. Reject new entries if global cap exceeded. | Same aggregator as F1. |
| F3 | **Mean_cap +0.088% on 1425 events** assumes ALL events are tradeable concurrently — spec disclosed this caveat. Real cap will be lower because of (a) capital occupancy, (b) max_concurrent. The PAPER expectation in §8.2 (`> +0.05% mean_cap`) is **post-friction unrealistic** — needs recalibration. | Med | High | Re-compute mean_cap simulating `max_concurrent_trades=3` queue (FIFO eviction or skip-on-full); use that number as Phase 4 acceptance threshold. | Re-run `market_layers_validation.py` with concurrency cap; new mean_cap is the gate. |
| F4 | **Leverage and margin dynamics not specified.** Live config shows `leverage: 2`, `max_total_margin_pct: 0.4`. New 12%-tier may conflict with existing equity sizing rules. | High | Med | Audit live JSON `equity_sizing` block; the new tier system must respect `max_total_notional_pct: 0.6` and `max_total_margin_pct: 0.4`. | Pre-trade check in `_open_position` re-verifying margin headroom. |
| F5 | **Live capital is $1000 (per CLAUDE.md).** A -10% week = -$100 stop-out trigger? Not specified. | High | Low | User-set drawdown circuit breaker: weekly capital ≤ -8% → auto-disable both engines via flag flip. | Daily capital snapshot; weekly delta. |
| F6 | **Slippage and fee assumption** in 1425-event backtest unknown. Real Binance futures perp fees + slippage on 8% events (volatile entries) typically 8-15bps each side. mean_cap +0.088% per trade (= 8.8 bps) is **roughly equal to round-trip frictional cost**. | **Critical** | High | Re-run validation with explicit fee+slippage model: 5bps fee/side + 5bps slippage on entry, 5bps on exit = 20bps drag. New mean_cap must remain > 0 after drag. | Updated `market_layers_validation.py` with fee model. |

### 1.5 Data Risks

| # | Risk | Severity | Likelihood | Mitigation | Detection |
|---|---|---|---|---|---|
| DR1 | **Zombie symbols** (Phase 2 had 161). Stale or partial data fed to lifecycle classifier. | High | Med (fixed in Phase 2 but recurrence possible) | `compute_symbol_features.py` must require minimum 14 days continuous klines before classifying; otherwise lifecycle = `unknown` → default ExitConfig. | Pre-classify count of `(symbol, days_continuous)`; reject < 14d. |
| DR2 | **Cross-table inconsistency** between `klines_1m` and `open_interest_1h`. yaobi_score uses both. If one collector lagged, score skewed. | Med | Med | Score computation must check `max_ts_ms` parity between source tables; reject if delta > 1 hour. | Pre-compute parity check, log mismatch. |
| DR3 | **Binance API silent throttle.** Symbols with high backfill load can return 200 OK but truncated. | Med | Low | Backfill scripts already retry with non-1 result; expand to also assert `len(rows) >= expected_min`. | Row-count sanity SELECT post-backfill. |
| DR4 | **Reaction label stale weekly.** A `mean_revert` symbol that flipped to `trend_continue` mid-week feeds Rule C → wrong fade decision. Decision #2 said "data-driven", but live reactions can lag observation. | High | Med-High | Reaction recompute frequency change to **3 days** (split-the-difference); if regime change detected (Rule C trigger rate drops > 30%), force daily. | Rule trigger histogram weekly. |
| DR5 | **Yaobi score age**: spec §5.1 says daily recompute. If batch fails 2 days, score is 2 days stale. Rule D (score≥80) decisions degrade. | Med | Med | Same DR1 fallback: stale score → ExitConfig() default + Rule A-only path. | Score age check in entry hook. |
| DR6 | **Wave duration / pre_vol** computed at trade-time using `compute_wave_features(symbol, now)` — must read from up-to-date 1m klines. Collector lag → wrong pre_vol. | Med | High | If `now - latest_kline_ts > 90s` for the symbol, abort entry (don't fall back to stale data). | Per-entry `kline_freshness_age_s` metric. |
| DR7 | **DB lock contention.** Live bot + collectors + feature batch + market scan all hit `binance_extended_history.sqlite3`. SQLite WAL mode helps but conflicts possible. | Med | Med | Verify WAL is on (`PRAGMA journal_mode=WAL`); add reader-writer separation: feature batch reads via secondary connection, never writes during collector active windows. | SQLite `busy_timeout` errors logged. |

---

## 2. Verification Strategy Per Phase

### Phase 1 — Data + tools (✅ Done per spec)

**Pre-phase**: N/A — already complete.

**Audit re-validation requirement** (added by this report):
- `SELECT COUNT(*) FROM klines_1m WHERE close_ms > strftime('%s','now')*1000 - 86400000` → must show > 22M of recent rows.
- `SELECT symbol, MAX(open_ms) FROM klines_1m GROUP BY symbol HAVING MAX(open_ms) < strftime('%s','now')*1000 - 600000` → must return 0 rows (no symbols stale > 10 min).
- Crontab: `crontab -l | grep collectors_watchdog` → must return entry.
- Watchdog process count: `ps -ef | grep -c binance_futures.*collector` → must return 3.

**Post-phase pass condition**: All 4 SQL/cron checks return expected values.

### Phase 2 — BWE L2-per-lifecycle paper

**Pre-phase checks (must all pass to enter)**:
1. `bwe_live_autotrader.py` config-validate smoke passes with new flags merged.
2. `feature_store.get(symbol)` returns lifecycle for ≥ 95% of currently-tracked symbols.
3. Rolling 7-window backtest: `L2-per-lifecycle` vs `L2-base` on 4 non-overlapping 7d windows from 30d archive — `total_raw` ratio variance ≤ 30pp across windows. **If FAIL → revert to L2-base, abort Phase 2 plan.**
4. Mean_cap recomputed with concurrency cap (F3 mitigation) → must be > 0.
5. Slippage/fee model added (F6 mitigation) → mean_cap post-drag > 0.

**Mid-phase monitoring (real-time)**:
- Per-trade log: `lifecycle_used`, `exit_config_label`, `realized_pnl_pct`. Stream to file.
- Daily metric: trade count, win rate, total raw, catastrophes (≤ -20%), big winners (≥ +20%).
- Lifecycle stability: compare today's `lifecycle` for traded symbols vs entry-time label; flag if changed.

**Post-phase pass condition (replaces soft spec criterion)**:
- ≥ 30 trades observed (not just 3 days — trade count gate).
- Total raw PnL > +50% (spec said).
- Win rate > 60% (spec said).
- Catastrophe rate ≤ 5% per 100 trades (spec said).
- **Added**: max-drawdown peak-to-trough < -25% raw cumulative.
- **Added**: Sharpe-style ratio `mean_pnl / stdev_pnl > 0.3` per trade.
- **Added**: Direct A/B against L2-base shadow run on same trades — L2-per-lifecycle must not lose > 30pp raw vs L2-base.

### Phase 3 — BWE L2-per-lifecycle live

**Pre-phase checks**:
1. Phase 2 fully passed (above).
2. Live bot config diff reviewed; only flag changes. No code changes since last live deploy beyond the `_open_position` hook.
3. User explicit "GO" confirmation logged with timestamp (from CLAUDE.md project rule #4).
4. Capital snapshot recorded: `current_balance_usd`.

**Mid-phase monitoring**:
- Per-trade outcome compared to PAPER prediction (was the lifecycle correctly chosen?).
- 5-trade rolling P&L; alert if cumulative ≤ -5% capital.
- Position aggregate cap: `sum(position_pct of open trades) ≤ 25%` (F2 mitigation).

**Post-phase pass condition**:
- 5-10 trades closed.
- Cumulative PnL > 0.
- No 3 consecutive catastrophes.
- **Added**: At least 1 lifecycle = `sustained` and 1 lifecycle = `spike_decay` traded — confirms both branches exercised.
- **Added**: Realized fees + slippage logged per trade; deviation from backtest model < 50%.

### Phase 4 — Market scan paper

**Pre-phase checks**:
1. `bwe_market_scan_entry.py` exists, has unit tests for `apply_rules()` (golden-value tests against decision-log examples).
2. Watchdog cron entry added for the new process.
3. F1+F2 mitigations live: position aggregator returns < 25% in synthetic concurrent-trade test.
4. F6 fee model in scan engine.
5. D6 dedupe (BWE vs Market Scan same symbol) tested with synthetic collision.

**Mid-phase monitoring**:
- `events_detected_per_day` count (expect ~50, alert if < 20 or > 100).
- Rule trigger histogram (compare to lock-in 1425-event distribution).
- `max_concurrent_trades` slot occupancy peak; alert if hits cap > 5 times/day.

**Post-phase pass condition**:
- ≥ 30 events triggered (not just 30 minutes — event-count gate).
- Total raw PnL > +25% (spec said).
- Win rate > 60% (spec said).
- mean_cap > +0.05% **post fee+slippage drag** (revised from spec).
- **Added**: Rule histogram match — no rule deviates > 50% from 1425-event archived distribution.
- **Added**: F1 satisfied — at most 1 12%-tier position observed open at any moment.

### Phase 5 — Full live + market scan hybrid

**Pre-phase checks**:
1. Phase 4 passed.
2. User explicit "GO" with capital-at-risk acknowledgement.
3. Daily review cadence agreed (per spec "周报 review" — Auditor recommends **daily for first 2 weeks then weekly**).

**Mid-phase monitoring**:
- All Phase 2-4 metrics, plus:
- Daily PnL by source (BWE vs Market Scan) — never let one source's drawdown drag the other.
- Weekly capital delta — circuit breaker at -8% (F5).

**Post-phase pass condition**:
- Iterative; "done" = 90 days continuous operation without breach of any auto-disable threshold.

---

## 3. Rollback Playbook

### Phase 2 (BWE paper) failure

| Step | Action |
|---|---|
| **Detection** | Any post-phase gate (above) fails after 30+ trades, OR Phase 2 mid-phase alert fires for 3 consecutive days. |
| **Stop** | Set `exit_engine.use_v2=false` AND `exit_engine.per_lifecycle_config=false` in JSON. Restart paper bot. |
| **Cleanup** | Mark `entry_decisions.exit_config_label='REVERTED'` for all open positions; let positions close naturally (do NOT force-close — that adds different bias). |
| **Diagnose** | Run `optimization_tests.py` on the just-collected 30+ trade slice; identify which lifecycle subset underperformed. |
| **Resume** | Only if diagnostic identifies a fixable cause. Otherwise fall back to L2-base permanently. |

### Phase 3 (BWE live) failure

| Step | Action |
|---|---|
| **Detection** | Cumulative PnL ≤ -5% capital, OR 3 consecutive catastrophes, OR any operational fault (hook crash). |
| **Stop** | Immediate kill switch: `exit_engine.use_v2=false`. Bot reverts to L1 baseline within next entry. **DO NOT close existing positions** unless their hard-stop fires; they're already exposed. |
| **Cleanup** | Audit `entry_decisions` last 24h; reconcile DB position state vs exchange reported positions. |
| **Resume** | Only after root-cause identified AND additional Phase 2 paper iteration passes. |

### Phase 4 (Market scan paper) failure

| Step | Action |
|---|---|
| **Detection** | Trades trigger > 100/day (spam) OR < 5/day (broken detection) OR mean_cap negative after 30 events. |
| **Stop** | Disable cron entry for `bwe_market_scan_entry.py`; kill process. |
| **Cleanup** | Cancel any pending paper orders; flush market-scan trade rows from `entry_decisions` (or tag `phase4_aborted`). |
| **Resume** | After investigation. Likely needs script-level fix, not config flip. |

### Phase 5 (Hybrid live) catastrophe

| Step | Action |
|---|---|
| **Detection** | Weekly capital delta ≤ -8%, OR any of Phase 3/4 detection signals. |
| **Stop** | `market_scan_engine.enabled=false` first (highest variance source). If still bleeding, then `exit_engine.use_v2=false`. Final: kill bot entirely if catastrophe in progress. |
| **Cleanup** | Position reconciliation; capital snapshot; incident post-mortem before any resume. |
| **Resume** | User explicit confirmation + at least 1 week of paper-only restart. |

### Universal abort (any phase)

| Trigger | Action |
|---|---|
| Bot crash with traceback in `_open_position` | Auto-disable v2 hook via try/except wrapping; fail-open to baseline. |
| DB locked > 60s | Kill blocking process (likely feature batch); disable batch cron until fixed. |
| Watchdog reports 30 consecutive collector failures | Auto-disable both engines (no fresh data → no fresh entries). |
| User issues stop command | Both flags false within 1 minute. |

---

## 4. Lock-in Baseline Regression Detection

### 4.1 Baselines (from spec §13)

| Metric | Lock-in value | Source | Auto-alert threshold |
|---|---|---|---|
| BWE L2-per-lifecycle PAPER total_raw | +144.1% | Phase 4 archive | < +100% (drop > 30%) |
| BWE L2-per-lifecycle PAPER total_cap | +7.21% | " | < +5% |
| BWE L2-per-lifecycle PAPER win % | 65.2% | " | < 60% |
| BWE L2-per-lifecycle LIVE total_raw | +101.4% | " | < +60% |
| Broader L4-tier total_raw | +1147.6% | " | < +800% |
| Broader L4-tier total_cap | +89.70% | " | < +60% |
| Broader L4-tier win % | 66.9% | " | < 60% |
| Broader L4-tier mean_cap | +0.088% | " | < +0.05% |
| Broader catastrophe count | 41/1425 (2.9%) | " | > 5% |

### 4.2 Required regression-detector additions

**Two new scripts must ship before Phase 2 GO**:

1. `/Volumes/T9/BWE/40_EXPERIMENTS/round4/scripts/regression_check_bwe.py`
   - Input: latest 30d Hermes trade table.
   - Output: pass/fail for the 4 BWE baseline metrics.
   - Cron: weekly Sunday 02:00; emit alert file to `99_ADMIN/alerts/`.

2. `/Volumes/T9/BWE/40_EXPERIMENTS/round4/scripts/regression_check_broader.py`
   - Input: rolling 30d broader-market events from `klines_1m`.
   - Output: pass/fail for the 5 broader baseline metrics.
   - Cron: weekly.

**Alert escalation**:
- 1 metric breach → log + email user.
- 2 metric breaches → also disable feature flag for the affected layer.
- 3+ metric breaches → full halt (both flags false) + user must explicitly resume.

### 4.3 Baseline freshness

The lock-in baselines are computed from a single 30d window (2026-03-29 → 2026-04-29). They are NOT robust to regime change. Auditor recommendation:

> Re-baseline quarterly via fresh 30d backfill + replay. If any new baseline metric is > 20% different from current lock-in, escalate to design review.

---

## 5. Protected Zones

### 5.1 Live bot — `/Users/ye/.hermes/scripts/bwe_live_autotrader.py` (92 KB, 24/7 critical)

**Allowed changes**:
- Config flag wiring in `_open_position` (lines TBD).
- New imports for `feature_store` and `build_lifecycle_aware_config`.

**FORBIDDEN**:
- Any refactor of existing trade lifecycle logic.
- Removing fields from any existing Position dict / class.
- Changing existing strategy_params handling.
- Touching the `bwe_live_trigger_strategies.py` strategy logic.

**Pre-merge gate**:
- `git diff` must show changes localized to `_open_position` + new imports. Anything else → reject.
- Config-validate smoke against template + each existing live JSON in scripts dir.

### 5.2 Collectors (3 alive)

- `binance_futures_1m_collector.py` (28 KB)
- `binance_futures_metric_collector.py` (45 KB)
- `binance_24h_ticker_collector.py` (4 KB)

**FORBIDDEN**:
- Stopping or restarting any collector during normal operation outside watchdog control.
- Modifying their config files.

**If schema migration needed**:
- Pause collectors via watchdog mute flag, do migration, unpause. Window ≤ 5 minutes.

### 5.3 Live DB — `binance_extended_history.sqlite3` (3.3 GB, APFS local)

**Allowed**:
- `CREATE TABLE IF NOT EXISTS symbol_features (...)`
- `CREATE TABLE IF NOT EXISTS entry_decisions (...)`
- `CREATE INDEX IF NOT EXISTS ...`

**FORBIDDEN**:
- `ALTER TABLE` on existing tables.
- `DROP TABLE` of any kind.
- Schema changes outside the watchdog-pause window.

### 5.4 Watchdog — cron-managed

**Allowed**:
- Adding NEW cron entries for new processes (feature batch, market scan).

**FORBIDDEN**:
- Modifying the existing `* * * * * collectors_watchdog.sh` line.
- Changing crontab via `crontab -e` (interactive); always via versioned `bwe_crontab.txt` apply.

### 5.5 Telegram raw exports (Mac only)

`/Users/ye/Desktop/Telegram/...` is read-only data source for BWE pipeline. **Never modify**. Any analytics that needs Telegram data must read-only-mount or copy to a working directory.

### 5.6 Capital config

`bwe_live_autotrader_binance_expectancy_live.json` `risk` block — **forbidden** to modify any value (`per_trade_usd`, `hard_stop_pct`, `max_total_*`, etc.) without user explicit confirmation. New strategy parameters go into NEW `strategy_params.<new_strategy>` keys, never overriding existing.

---

## 6. Acceptance Criteria for Whole Implementation

For the implementation to be considered "DONE":

1. **All 5 phases passed their post-phase gate** as defined in §2.
2. **All 9 lock-in baseline metrics** met or exceeded across the 90-day Phase 5 window (no breach beyond §4.2 thresholds).
3. **All Critical risks** (D2, E1, F1, F6) explicitly mitigated and documented as resolved in this report's risk register.
4. **All High risks** mitigated OR formally accepted by user with rationale (signed in `99_ADMIN/risk_acceptance_log.md`).
5. **Documentation complete**:
   - Spec v2 unchanged (this is the contract).
   - This audit report linked from spec §12.
   - Rollback playbook tested at least once in paper (synthetic failure).
   - Regression detectors live and producing weekly clean reports.
6. **Operational readiness**:
   - Watchdog handles VPN flap.
   - Crontab versioned.
   - Position aggregator enforces F1+F2 caps.
   - Feature batch produces fresh `symbol_features` daily.
   - Auditable `entry_decisions` table accumulating.
7. **Backwards compatibility verified**: setting both flags to false in production for 1 hour returns bot to baseline behavior with no anomalies. (Backwards-compat test in Phase 5.)
8. **User explicit sign-off** on transition from Phase 4 → Phase 5 (per CLAUDE.md hard rule #4).

---

## 7. Abort Conditions (halt + reset entirely)

The implementation MUST halt and revert to baseline if any of the following:

1. **Capital draw-down ≥ 15% from start of Phase 3 measurement.** (Crosses outside spec's expected envelope.)
2. **3+ lock-in baseline regressions** detected by §4 detector in any 4-week window.
3. **Critical risk realization** that wasn't mitigated:
   - Live bot crashes traced to v2 hook ≥ 2 incidents.
   - Live DB corruption incident.
   - Position aggregator bypass (12%+12%+12% concurrent observed).
4. **Regulatory / exchange event**: Binance changes futures rules in a way that invalidates 8% wave detection or fee model assumptions.
5. **User-issued halt**.
6. **Watchdog escalation** = 30 consecutive failures + collectors offline > 1 hour during live.
7. **Single-trade loss > 6% capital**: hard stop + catastrophe stop both fired but actual loss exceeded 6% (= leverage / liquidity event).

Reset = both flags false, all positions closed naturally, post-mortem in `99_ADMIN/incident_<date>.md`, no resume without user explicit confirmation AND new Phase 2 paper validation cycle.

---

## 8. Required Rework Before Audit Sign-off

The following are **blockers** that must be addressed before the implementation plan can move to Execution Lead:

### Blocker B1 — D2: L2-per-lifecycle robustness
Run rolling 7d-window cross-validation `L2-per-lifecycle` vs `L2-base` on the existing 30d archive. If variance > 30pp, the picked variant is unstable; revert spec to L2-base or document explicit accept-overfit rationale.

### Blocker B2 — F1+F2: position concentration
Add explicit specification text: "Global cap: sum of `position_pct` across ALL open positions (Layer A + Layer B) ≤ 25%. At most 1 position at 12% tier at a time." Then update spec §6.3 market scan engine accordingly.

### Blocker B3 — F6: fee/slippage realism
Re-run `market_layers_validation.py` with explicit 5bps fee/side + 5bps slippage model; update spec §13 lock-in baselines with post-drag numbers; update §8.2 acceptance threshold accordingly.

### Blocker B4 — Phase gate softness
Update spec §7 table to add minimum trade count, drawdown ceiling, and Sharpe-style ratio gates as defined in §2 of this report.

### Blocker B5 — Regression detector
The two scripts in §4.2 must be authored and a smoke-run against historical data must pass before Phase 2 GO.

### Non-blockers (recommended but not gating)
- D4: Top-100 dive coverage gap measurement.
- DR4: Reaction recompute frequency to 3 days.
- O5: Crontab versioning hygiene.

---

## Audit sign-off: REWORK REQUIRED — see blockers

Spec v2 is data-driven and honest about its caveats, but it is not yet ready for Execution Lead handoff. The five blockers (B1-B5) must be resolved. Two are quantitative re-runs (B1, B3); one is a spec text update (B2); one is a tightening of acceptance thresholds (B4); one is a new artifact (B5).

Once B1-B5 land, this report should be re-read to confirm the lock-in baselines have been refreshed under the new fee/slippage model and the new robustness check, and then the gate can re-open.

This Auditor is operating as a **fallback role agent** under the `/Agent-teams-plan` honesty rule (no real official team was bootstrapped for this task; this is one of the four fallback roles).

