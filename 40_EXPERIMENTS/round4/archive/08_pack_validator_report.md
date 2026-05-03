# 08 — Pack Validator Report (Acceptance Contract)

> **Role**: Pack Validator (fallback role agent — no official team bootstrap)
> **Date**: 2026-04-29
> **Spec under validation**: `/Volumes/T9/BWE/40_EXPERIMENTS/round4/per_symbol_design_v2.md` (530 lines, 13 sections, user-approved)
> **Companion reports** (referenced in this contract):
> - `archive/05_architect_report.md` — architecture decisions
> - `archive/06_execution_lead_report.md` — task decomposition
> - `archive/07_auditor_report.md` — risk + verification
>
> **Purpose**: This document is the GATE. No "complete" claim is honored unless every line of the conformance checklist passes against actual artifacts on disk + observed runtime evidence. Claims unsupported by evidence are rejected by default.

---

## 0. Honesty disclosure

This validator was launched as a fallback role agent because the official `/Agent-teams-plan` team bootstrap did not produce an attestable team identifier. Treat this report as an independent fallback acceptance gate, not as official-team output.

---

## 1. Requirement extraction

Each requirement is numbered REQ-NNN with a traceability tag `[§Section.Subsection]` pointing into `per_symbol_design_v2.md`. F = functional, NF = non-functional, C = constraint, T = test obligation, D = documentation obligation.

### 1.1 Spec §1 Context / Architecture overview

| ID | Type | Requirement | Trace |
|----|------|-------------|-------|
| REQ-001 | F | System MUST implement a dual-source hybrid architecture: (Source A) BWE Telegram + L2-per-lifecycle exit AND (Source B) direct market scan + L4-tier rule engine | §1.1, §1.2 |
| REQ-002 | F | Data layer MUST run 4 collectors continuously: `binance_futures_1m_collector`, `binance_futures_metric_collector`, `binance_24h_ticker_collector`, `binance_extended_history.sqlite3` | §1.2 |
| REQ-003 | NF | A `collectors_watchdog.sh` cron MUST run every minute and self-heal stale/dead collectors (separating VPN-down vs collector-stuck) | §1.2, decision #6 |
| REQ-004 | F | Feature extraction MUST produce: `yaobi_score` (daily), `lifecycle` ∈ {sustained, late_burst, spike_decay, single_burst, quiet} (daily), `reaction` ∈ {mean_revert, trend_continue, mixed, n_a} (weekly), per-event `pre_vol`/`wave_duration`/`magnitude` (on-demand) | §1.2 |

### 1.2 Spec §2 Goals & Non-goals (HARD constraints)

| ID | Type | Requirement | Trace |
|----|------|-------------|-------|
| REQ-005 | F | G1 — BWE-source trades MUST execute via L2-per-lifecycle path (PAPER 30d target +144% raw / +7.21% cap) | §2 G1, §13 |
| REQ-006 | F | G2 — Market-scan-source trades MUST execute via L4-tier path (1425-events target +1147.6% raw / +89.70% cap) | §2 G2, §13 |
| REQ-007 | F | G3 — `exit_v2` module alpha MUST be preserved (no modification may regress the +218% LIVE / +449% PAPER improvement vs original buggy logic) | §2 G3 |
| REQ-008 | F | G4 — BWE alpha and Broader alpha MUST be additive — neither source may interfere with the other's signal pipeline | §2 G4 |
| REQ-009 | C | G5 — Backwards-compat MUST hold: setting `exit_engine.use_v2=false` AND `market_scan_engine.enabled=false` returns the system to L1-baseline behavior bit-for-bit | §2 G5, §6.1 |
| REQ-010 | C | NG1 — System MUST NOT implement per-thesis exit config in L4 (data shows -29pp regression) | §2 NG1 |
| REQ-011 | C | NG2 — System MUST NOT implement direction-check between rule engine and BWE direction (Hermes L4 -71% cap) | §2 NG2 |
| REQ-012 | C | NG3 — System MUST NOT implement continuous position sizing (broader -176pp raw regression) | §2 NG3 |
| REQ-013 | C | NG4 — No LLM real-time entry decisions in this delivery | §2 NG4 |
| REQ-014 | C | NG5 — No new BWE strategy logic (out of scope — that lives in BWE signal layer) | §2 NG5 |

### 1.3 Spec §3 Layer A — BWE + L2-per-lifecycle

| ID | Type | Requirement | Trace |
|----|------|-------------|-------|
| REQ-015 | F | On BWE Telegram signal MUST enter directly with no rule SKIP filter | §3.1 |
| REQ-016 | F | BWE-source position size MUST be 5% fixed (no sizing override) | §3.1 |
| REQ-017 | C | BWE-source MUST NOT apply Rule SKIP filter (PAPER -32% cap) | §3.1 |
| REQ-018 | C | BWE-source MUST NOT override BWE-decided direction | §3.1 |
| REQ-019 | F | `get_exit_config(symbol)` MUST return: lifecycle ∈ {sustained, late_burst} → trail_tiers `((5,5),(10,10),(25,18),(50,28),(100,40))` + `tradoor_saver_max_hw_age_min=20.0`; lifecycle == spike_decay → `((5,3),(10,5),(25,8),(50,12),(100,18))`; otherwise → `ExitConfig()` baseline | §3.2 |
| REQ-020 | T | A test MUST verify all 5 lifecycle paths in `get_exit_config` return the exact tier values above | §3.2 |

### 1.4 Spec §4 Layer B — Market Scan + L4-tier

| ID | Type | Requirement | Trace |
|----|------|-------------|-------|
| REQ-021 | F | Market scan MUST run every 60s across all 530 symbols and detect ±8% events on 5-minute close-vs-close return | §4.1 |
| REQ-022 | F | `apply_rules(features, wave_features, side)` MUST evaluate Rules A-G in order and return on first match | §4.2 |
| REQ-023 | F | Rule A: `n_waves_14d < 3` → `("SKIP", 0, None)` | §4.2 |
| REQ-024 | F | Rule B: `reaction == "trend_continue"` AND `3 <= duration <= 20` → ENTER 5%, direction = same as side | §4.2 |
| REQ-025 | F | Rule C: `reaction == "mean_revert"` AND `lifecycle ∈ (sustained, single_burst)` → ENTER (12% if score≥85 else 8%), direction = fade | §4.2 |
| REQ-026 | F | Rule D: `score >= 80` AND `pre_vol < 2.5` → ENTER (12% if score≥85 else 8%), direction = fade | §4.2 |
| REQ-027 | F | Rule E: `3 <= duration <= 6` → SKIP | §4.2 |
| REQ-028 | F | Rule F: `pre_vol >= 7.0` → ENTER 5%, direction = follow | §4.2 |
| REQ-029 | F | Rule G default: ENTER (3% if score<50 else 5%), direction = fade | §4.2 |
| REQ-030 | F | 4-tier position table MUST be enforced: Mini=3%, Standard=5%, High=8%, Max=12% with the trigger conditions in §4.3 | §4.3 |
| REQ-031 | F | Market-scan exits MUST use `ExitConfig()` baseline (with G2 TRADOOR-saver, dynamic trail, ATR stop, volume confirm) — no per-thesis swap | §4.4 |
| REQ-032 | NF | Market scan MUST cap `max_concurrent_trades = 3` to avoid capital overload | §6.1, §9 risk row 2 |
| REQ-033 | T | Rule engine MUST have unit tests covering all 7 rules with both pump and dump sides | §4.2 (derived from spec rule precision) |

### 1.5 Spec §5 Storage & State

| ID | Type | Requirement | Trace |
|----|------|-------------|-------|
| REQ-034 | F | Table `symbol_features` MUST exist in `binance_extended_history.sqlite3` with columns and types exactly as specified (PRIMARY KEY symbol, REAL yaobi_score NOT NULL, INTEGER n_waves_14d NOT NULL, TEXT lifecycle/reaction NOT NULL, INTEGER computed_at_ms NOT NULL, INTEGER reaction_computed_at_ms NOT NULL) | §5.1 |
| REQ-035 | F | Index `idx_symbol_features_lifecycle` MUST exist on `symbol_features(lifecycle)` | §5.1 |
| REQ-036 | F | Daily batch `compute_symbol_features.py` MUST refresh `symbol_features` rows | §5.1 |
| REQ-037 | F | Table `entry_decisions` MUST exist with columns: `trade_id` (PK), `symbol`, `ts_ms`, `source`, `features_json`, `rule_triggered`, `action`, `position_pct`, `direction`, `exit_config_label`, `reason` | §5.2 |
| REQ-038 | F | Every entry decision (BWE or MARKET_SCAN) MUST insert one row into `entry_decisions` for audit | §5.2 |
| REQ-039 | F | Daily batch MUST write `daily_features_YYYY-MM-DD.json` to `/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits/` containing yaobi_score ranking, lifecycle/reaction transitions, and per-rule trade counts | §5.3 |

### 1.6 Spec §6 Hermes Bot Integration

| ID | Type | Requirement | Trace |
|----|------|-------------|-------|
| REQ-040 | F | `bwe_live_autotrader_binance_expectancy_live.json` MUST add: `exit_engine.use_v2` (default false), `exit_engine.per_lifecycle_config` (default false), `market_scan_engine.enabled` (default false), `market_scan_engine.event_threshold_pct` (8.0), `market_scan_engine.max_concurrent_trades` (3) | §6.1 |
| REQ-041 | C | Defaults of all 3 enable flags MUST be `false` so a fresh deploy continues to behave as L1 (REQ-009 backwards-compat) | §6.1, §2 G5 |
| REQ-042 | F | `bwe_live_autotrader.py:_open_position` MUST consult `exit_engine.use_v2` and `exit_engine.per_lifecycle_config` to decide between baseline `ExitConfig()` and `build_lifecycle_aware_config(features.lifecycle)` | §6.2 |
| REQ-043 | F | New independent process `/Users/ye/.hermes/scripts/bwe_market_scan_entry.py` MUST exist, run parallel to `bwe_live_autotrader.py`, scan every 60s, and pipe trades through the same `_open_position` hook tagged `source="MARKET_SCAN"` | §6.3 |
| REQ-044 | NF | Market scan process MUST respect `max_concurrent_trades=3` cap | §6.3 |

### 1.7 Spec §7 Rollout Plan (5 Phases — HARD gates)

| ID | Type | Requirement | Trace |
|----|------|-------------|-------|
| REQ-045 | F | Phase 1 (Data + tools): collectors + 30d backfill + watchdog already complete — verification artifacts MUST exist | §7 P1 |
| REQ-046 | F | Phase 2 pass criterion: PAPER 3-day rolling mean PnL > 0 AND win-rate > 60% on `exit_engine.use_v2=true + per_lifecycle_config=true` | §7 P2, §8.1 |
| REQ-047 | F | Phase 3 pass criterion: 5-10 single-strategy LIVE trades, total PnL positive, no streak of 3 consecutive catastrophes | §7 P3 |
| REQ-048 | F | Phase 4 pass criterion: 30+ market-scan PAPER events, total cap > 0, win-rate > 60% | §7 P4, §8.2 |
| REQ-049 | F | Phase 5 pass criterion: weekly review of dual-source LIVE PnL — iterative gate | §7 P5 |
| REQ-050 | C | A phase MAY NOT be entered until the previous phase's gate is green | §7 ("每 phase 通过才进下一 phase") |

### 1.8 Spec §8 Verification thresholds

| ID | Type | Requirement | Trace |
|----|------|-------------|-------|
| REQ-051 | T | Phase 2 PAPER targets: total_raw > +50%, win-rate > 60%, catastrophes < 5 per 100 trades (vs current L1 paper baseline of -317.6% raw / 26.3% win / 0 cat) | §8.1 |
| REQ-052 | T | Phase 4 PAPER targets (per 30 events): total_raw > +25%, win-rate > 60%, mean_cap > +0.05% | §8.2 |
| REQ-053 | F | Rollback procedure MUST be: set the offending flag(s) to false → return immediately to prior phase. Full revert path = `use_v2=false + market_scan_engine.enabled=false` | §8.3 |

### 1.9 Spec §9 Risk register

| ID | Type | Requirement | Trace |
|----|------|-------------|-------|
| REQ-054 | T | Mitigation for "L2-per-lifecycle LIVE -48pp" risk: Phase 2 paper run for 3-7 days; if paper fails, fall back to L2-base | §9 row 1 |
| REQ-055 | NF | Mitigation for "lifecycle stale" risk: monitor catastrophe rate; if > 5%, switch from weekly → daily reaction updates | §9 row 3 |
| REQ-056 | NF | Watchdog MUST implement dual monitoring (process liveness AND data freshness staleness check) | §9 row 4 |
| REQ-057 | NF | exit_v2 hard stop MUST cap worst-case 12%-position loss at ≈ -3.6% of capital (-29.9% × 12%) | §9 row 6 |
| REQ-058 | NF | Layer B MUST keep operating if BWE signal source goes silent — sources are independent | §9 row 7 |

### 1.10 Spec §10–§12 Open questions, Out-of-scope, Evidence

| ID | Type | Requirement | Trace |
|----|------|-------------|-------|
| REQ-059 | D | Open questions list (§10 items 1–5) MUST be carried into Phase 2+ review meetings, NOT silently resolved | §10 |
| REQ-060 | C | Out-of-scope items (§11) MUST NOT be implemented in this delivery: no LLM, no cross-exchange, no order-book data, no cluster auto-class, no per-thesis exit, no rule↔BWE dir-check | §11 |
| REQ-061 | D | Archive evidence files §12 MUST exist: `00_decision_log.md`, `01_phase1_initial_brainstorm.md`, `02_phase2_30d_validation.md`, `03_phase3_layer_validation.md`, `04_phase4_optimization.md`, `per_symbol_design_v1.md` | §12 |

### 1.11 Spec §13 Lock-in baselines (HARD acceptance metrics)

| ID | Type | Requirement | Trace |
|----|------|-------------|-------|
| REQ-062 | T | Replay BWE L2-per-lifecycle on Hermes LIVE 82-trade set MUST reproduce: +101.4% raw / +5.07% cap / 67.1% win / mean_cap +0.062% (within rounding tolerance ±0.1pp) | §13 |
| REQ-063 | T | Replay BWE L2-per-lifecycle on Hermes PAPER 210-trade set MUST reproduce: +144.1% raw / +7.21% cap / 65.2% win / mean_cap +0.034% (±0.1pp) | §13 |
| REQ-064 | T | Replay Broader L4-tier-3-5-8-12 on 1425-event set MUST reproduce: +1147.6% raw / +89.70% cap / 66.9% win / mean_cap +0.088% (±0.1pp) | §13 |
| REQ-065 | T | Catastrophe count (Broader) MUST be 41; big-winner count MUST be 109 | §13 |
| REQ-066 | C | Any subsequent code change that regresses ANY of REQ-062 / REQ-063 / REQ-064 below the locked baseline triggers mandatory review | §13 ("触发 review") |

---

## 2. Conformance checklist (binary)

Each item is ❌ (fails / unverified) until evidence is presented. Acceptance requires every item ✅.

### Code presence
- [ ] ❌ `compute_symbol_features.py` exists and writes `symbol_features` table
- [ ] ❌ `apply_rules()` function implements REQ-022 through REQ-029 exactly
- [ ] ❌ `get_exit_config(symbol)` implements REQ-019 exactly
- [ ] ❌ `bwe_live_autotrader.py:_open_position` consults config flags (REQ-042)
- [ ] ❌ `/Users/ye/.hermes/scripts/bwe_market_scan_entry.py` exists, scans 60s × 530 syms (REQ-043)
- [ ] ❌ Watchdog cron entry `* * * * * /Users/ye/.hermes/scripts/collectors_watchdog.sh` is installed (REQ-003)

### Schema
- [ ] ❌ Table `symbol_features` exists in `binance_extended_history.sqlite3` with exact columns (REQ-034)
- [ ] ❌ Index `idx_symbol_features_lifecycle` exists (REQ-035)
- [ ] ❌ Table `entry_decisions` exists with all 11 columns (REQ-037)

### Config
- [ ] ❌ `bwe_live_autotrader_binance_expectancy_live.json` has all 5 new keys (REQ-040)
- [ ] ❌ All 3 enable flags default to `false` (REQ-041)
- [ ] ❌ With flags false, code path is structurally identical to pre-v2 (REQ-009)

### Tests
- [ ] ❌ Unit test covers all 5 lifecycle branches of `get_exit_config` (REQ-020)
- [ ] ❌ Unit test covers all 7 rules × 2 sides = 14 minimum cases (REQ-033)
- [ ] ❌ Replay test reproduces Hermes LIVE baseline (REQ-062)
- [ ] ❌ Replay test reproduces Hermes PAPER baseline (REQ-063)
- [ ] ❌ Replay test reproduces Broader 1425-event baseline (REQ-064)
- [ ] ❌ Replay test asserts catastrophe=41, big_winner=109 (REQ-065)
- [ ] ❌ Test asserts default-flag run is bit-equivalent to L1 trace (REQ-009, REQ-041)

### Process / runtime
- [ ] ❌ All 4 collectors observed alive for 24+ continuous hours (REQ-002)
- [ ] ❌ Watchdog log shows at least one successful self-heal cycle OR demonstrates dual liveness+freshness monitoring (REQ-056)
- [ ] ❌ Daily batch produced `daily_features_YYYY-MM-DD.json` for at least one day (REQ-039)
- [ ] ❌ Phase 1 evidence collected and signed off by auditor (REQ-045)

### Documentation
- [ ] ❌ Architect report `archive/05_architect_report.md` exists with module decomposition + interface contracts
- [ ] ❌ Execution-lead report `archive/06_execution_lead_report.md` exists with phase-by-phase task graph
- [ ] ❌ Auditor report `archive/07_auditor_report.md` exists with risk register + verification plan + rollback drill
- [ ] ❌ This report `archive/08_pack_validator_report.md` exists (THIS file)
- [ ] ❌ All §12 evidence files exist (REQ-061) — verified present at time of writing
- [ ] ❌ Open-questions list carried forward into Phase 2 plan (REQ-059)

### Phase gates
- [ ] ❌ Phase 1 gate green (data infra)
- [ ] ❌ Phase 2 gate green: 3-day PAPER mean PnL > 0 AND win > 60% (REQ-046, REQ-051)
- [ ] ❌ Phase 3 gate green: 5-10 LIVE trades total positive, no 3-streak catastrophe (REQ-047)
- [ ] ❌ Phase 4 gate green: 30+ market-scan PAPER events, total cap > 0, win > 60%, mean_cap > +0.05% (REQ-048, REQ-052)
- [ ] ❌ Phase 5 weekly-review cadence established (REQ-049)

### Constraint checks
- [ ] ❌ No per-thesis L4 exit code present (REQ-010)
- [ ] ❌ No rule↔BWE direction-check code present (REQ-011)
- [ ] ❌ No continuous position sizing code present (REQ-012)
- [ ] ❌ No LLM real-time entry code present (REQ-013)
- [ ] ❌ No new BWE strategy logic added (REQ-014)
- [ ] ❌ No cross-exchange / order-book / cluster auto-class code added (REQ-060)

---

## 3. Acceptance contract

For "DONE" to be claimable, all of the following artifacts/states MUST be evidenced:

### 3.1 Code (must exist + reviewed + tested)
- `compute_symbol_features.py` (daily batch, computes yaobi_score / lifecycle / reaction)
- `apply_rules.py` (or equivalent module hosting the Rule A–G engine)
- `get_exit_config.py` (or equivalent — lifecycle → ExitConfig mapping)
- `build_lifecycle_aware_config()` helper (REQ-042)
- `/Users/ye/.hermes/scripts/bwe_market_scan_entry.py` (independent scanner process)
- Modified `bwe_live_autotrader.py:_open_position` honoring config flags
- Modified `bwe_live_autotrader_binance_expectancy_live.json` config keys

### 3.2 Tests (must exist + pass)
- `test_get_exit_config.py` — REQ-020
- `test_apply_rules.py` — REQ-033 (14+ cases)
- `test_replay_hermes_live.py` — REQ-062
- `test_replay_hermes_paper.py` — REQ-063
- `test_replay_broader_1425.py` — REQ-064 + REQ-065
- `test_backwards_compat_l1.py` — REQ-009 / REQ-041

### 3.3 Documentation (must be updated/present)
- `archive/05_architect_report.md`
- `archive/06_execution_lead_report.md`
- `archive/07_auditor_report.md`
- `archive/08_pack_validator_report.md` (this file)
- `per_symbol_design_v2.md` (already locked) — frozen, no edits without re-validation

### 3.4 Data (must be populated)
- `symbol_features` table populated for all 530 active symbols
- `entry_decisions` table populated with at least one row per Phase 2 paper trade
- `daily_features_YYYY-MM-DD.json` produced for ≥ 1 day

### 3.5 Process (must be running with health)
- 4 collectors live (`binance_futures_1m_collector`, `_metric_collector`, `_24h_ticker_collector`, backfill ETL completed)
- `collectors_watchdog.sh` cron entry installed and last-run timestamp < 90s old
- (Phase 4+) `bwe_market_scan_entry.py` daemon alive

### 3.6 Performance (lock-in baselines)
- BWE L2-per-lifecycle PAPER replay: ≥ +144.1% raw, ≥ +7.21% cap, ≥ 65.2% win (within ±0.1pp)
- BWE L2-per-lifecycle LIVE replay: ≥ +101.4% raw, ≥ +5.07% cap, ≥ 67.1% win
- Broader L4-tier-3-5-8-12 replay: ≥ +1147.6% raw, ≥ +89.70% cap, ≥ 66.9% win, mean_cap ≥ +0.088%
- Catastrophe count (Broader) = 41 ; big-winner count = 109

---

## 4. Coverage matrix — original prompt-pack 5 deliverables → artifacts

The original prompt pack listed five deliverables. Each is mapped to the report/artifact that proves delivery:

| # | User-listed deliverable | Required artifact | Status |
|---|--------------------------|-------------------|--------|
| 1 | Architecture decision record | `archive/05_architect_report.md` (module boundaries, ADRs, interfaces) | ❌ pending |
| 2 | Module-level decomposition | Section in `05_architect_report.md` enumerating: data layer, feature batch, BWE pipeline, scan pipeline, exit module, watchdog, schema migrations | ❌ pending |
| 3 | Implementation plan | `archive/06_execution_lead_report.md` (phase 1→5 task graph, owners, sequencing) + a writing-plans output if needed | ❌ pending |
| 4 | Acceptance criteria | THIS report (REQ-001..REQ-066 + §3 contract) + `archive/07_auditor_report.md` verification thresholds | ✅ this file ; ❌ auditor |
| 5 | Risk register + rollback | `archive/07_auditor_report.md` (risks §9 expanded, rollback drill from §8.3) | ❌ pending |

Until all four sibling reports exist on disk, the prompt-pack deliverable set is INCOMPLETE.

---

## 5. Mandatory rework triggers

Any one of the following → automatic REJECT, sent back for rework:

1. **Missing test for any `T` requirement** (REQ-020, REQ-033, REQ-051, REQ-052, REQ-054, REQ-062 through REQ-065). Empirically observed evidence is the only valid form.
2. **Documentation gap** — any missing report from §3.3, missing archive evidence file (REQ-061), or undocumented schema migration.
3. **Spec contradiction** — implementation deviates from spec, e.g., trail tier values differ from REQ-019, rule order changes, position % differs, etc. Even one incorrect tuple = reject.
4. **Lock-in regression** (REQ-066) — replay below baseline by > 0.1pp on raw OR > 0.1pp on cap OR > 0.5pp on win-rate.
5. **Backwards-compat broken** (REQ-009 / REQ-041) — flags-off run differs in any code path (compare `entry_decisions` row, exit config selected, position sized) from L1 baseline.
6. **Out-of-scope creep** — any line of code implementing REQ-010..REQ-014 / REQ-060 forbidden items.
7. **Phase gate skipped** (REQ-050) — Phase N+1 enabled before Phase N gate proven green.
8. **Watchdog not dual-mode** (REQ-056) — only liveness without freshness, or vice versa.
9. **Config defaults wrong** (REQ-041) — any of `use_v2`, `per_lifecycle_config`, `market_scan_engine.enabled` defaulting to `true`.
10. **`max_concurrent_trades` not enforced** (REQ-032 / REQ-044).
11. **Audit trail missing rows** — `entry_decisions` not populated for some entries (REQ-038).
12. **Honesty failures** — any "complete" claim without runnable verification command in evidence.

---

## 6. Final acceptance gate

Acceptance is granted only when ALL of these are TRUE in sequence:

1. **Sign-offs** — Architect, Execution Lead, Auditor each present a signed report (`archive/05`, `archive/06`, `archive/07`). Pack Validator (this report) accepts.
2. **Conformance checklist (Section 2)** — every box ✅ with attached evidence (file path or run output).
3. **Tests** — all 6 test files in §3.2 exist and pass under a fresh CI run; output captured.
4. **Lock-in replay** — REQ-062, REQ-063, REQ-064, REQ-065 reproduced live on the recorded data; deltas ≤ tolerance (±0.1pp / ±0.5pp).
5. **Backwards-compat replay** — flag-off run produces an `entry_decisions` trace bit-equivalent to L1 reference trace.
6. **Phase 2 PAPER green** before any LIVE switch — REQ-046 met (3-day PAPER mean PnL > 0, win > 60%).
7. **Phase 4 PAPER green** before market-scan goes LIVE — REQ-048 met.
8. **Watchdog drill** — at least one demonstrated VPN-down recovery cycle in watchdog log.
9. **Out-of-scope confirmation** — Pack Validator re-greps codebase for forbidden tokens (`per_thesis_exit`, `dir_check`, `continuous_pos`, etc.) → zero hits.
10. **Explicit user approval** — user reviews this acceptance contract + auditor report and explicitly says "go-live" before any LIVE trade is allowed (per CLAUDE.md hard rule #4).

If step 10 has not happened, the system MUST remain in PAPER even when all earlier gates green.

---

## 7. Failures observed at validation time (2026-04-29)

The current `archive/` directory contains:
- `00_decision_log.md` ✅
- `01_phase1_initial_brainstorm.md` ✅
- `02_phase2_30d_validation.md` ✅
- `03_phase3_layer_validation.md` ✅
- `04_phase4_optimization.md` ✅
- `per_symbol_design_v1.md` ✅
- `README.md` ✅
- THIS report (08) ✅ once written

Missing siblings required by §4 coverage matrix:
- `05_architect_report.md` — NOT FOUND
- `06_execution_lead_report.md` — NOT FOUND
- `07_auditor_report.md` — NOT FOUND

Until the three missing reports exist, prompt-pack deliverable set #1, #2, #3, #5 are NOT yet satisfied. Pack Validator cannot grant acceptance based solely on this self-written report.

Implementation work has not begun at the code level (no scan of `/Users/ye/.hermes/scripts/` or `binance_extended_history.sqlite3` was required for this validation pass — those checks belong to the post-implementation acceptance run, not the planning gate). When implementation begins, the §2 conformance boxes must be re-evaluated with actual file/DB checks.

---

## 8. Rework routing recommendation

Send back to:
- **Architect** — produce `archive/05_architect_report.md` covering module decomposition (data layer, feature batch, BWE entry hook, market-scan daemon, exit module, schema), interface contracts (`get_exit_config` signature, `apply_rules` signature, `_open_position` flag wiring), and ADRs for the dual-source decision.
- **Execution Lead** — produce `archive/06_execution_lead_report.md` with phase-1→5 task graph, owners, sequencing dependencies, and explicit phase gates aligned with §7 of spec.
- **Auditor** — produce `archive/07_auditor_report.md` with expanded risk register (carry §9 + add new risks from architect/execution-lead output), verification plan covering REQ-051..REQ-052 thresholds, rollback drill spec, and the runtime-evidence checklist for the post-implementation acceptance run.

Until those three exist, no implementation work should be advanced into Phase 2.

---

## Pack Validator sign-off: ACCEPTANCE CONTRACT LOCKED

This document constitutes the binding acceptance contract for the BWE per-symbol 妖币 strategy v2 delivery. Any future "complete" or "ready to go-live" claim is rejected by default unless every numbered REQ-001 through REQ-066 has explicit, attached, runtime-grounded evidence and every conformance checklist box in Section 2 is marked ✅ with that evidence.

The contract is now locked. Edits to this contract require either (a) a corresponding edit to `per_symbol_design_v2.md` triggered by an explicit user decision (logged in `00_decision_log.md`), or (b) a justified exception accepted by the user in writing.

— Pack Validator (fallback role agent), 2026-04-29
