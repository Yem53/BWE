# Execution Lead Report — Per-Symbol 妖币 Strategy Implementation

> **Role**: Fallback Execution Lead (no official team bootstrapped).
> **Source spec**: `/Volumes/T9/BWE/40_EXPERIMENTS/round4/per_symbol_design_v2.md` (sections 5–7 primary, section 6 integration).
> **Goal**: Decompose Phase 2–5 rollout into atomic, executor-routable tasks.
> **Date**: 2026-04-29

---

## 0. Scope assumptions (stated explicitly per CLAUDE.md rule 1)

- Phase 1 (data + tools) is complete; this plan starts at Phase 2 (paper) and runs through Phase 5 (live + market scan).
- Existing modules are reusable: `exit_v2.py` already exists at `40_EXPERIMENTS/round4/exit_v2/exit_v2.py`; rule-engine and yaobi feature scripts in `40_EXPERIMENTS/round4/scripts/`. We integrate, not re-author.
- DB writes for `symbol_features` go to `binance_extended_history.sqlite3` (read-mostly DB, safe to add a new table).
- Decision-log table `entry_decisions` lives in a new sidecar DB (`decisions.sqlite3`) to avoid touching the live `binance_futures_1m.sqlite3` schema.
- Market scan reads OHLCV from the *live* DB read-only (WAL mode) — no schema changes there.
- "Subagent" estimates assume Sonnet 4.6 worker with focused write scope (1–3 hr human-equivalent each).
- Code lives under `/Users/ye/.hermes/scripts/` for runtime; analysis lives under `/Volumes/T9/BWE/40_EXPERIMENTS/round4/`.

---

## 1. Atomic task list

### Phase 2 — BWE L2-per-lifecycle paper (target: 1 week)

| ID | Title | Hrs | Inputs | Outputs | DoD | Executor |
|---|---|---|---|---|---|---|
| **T1** | Define `symbol_features` schema migration | 1 | spec §5.1 | `migrations/2026_04_30_create_symbol_features.sql` | Idempotent `CREATE TABLE IF NOT EXISTS` runs cleanly on backfill DB; index present | `python-reviewer` |
| **T2** | Build `compute_symbol_features.py` daily batch | 3 | `yaobi_score_explorer_v2.py`, `yaobi_per_symbol_deep_dive_v2.py`, backfill DB | `scripts/compute_symbol_features.py` writing to `symbol_features` table | One full run produces ≥400 rows; CLI flag `--dry-run` prints diff vs prior day | `tdd-guide` |
| **T3** | Define `entry_decisions` schema + sidecar DB | 1 | spec §5.2 | `migrations/2026_04_30_create_entry_decisions.sql`, `decisions.sqlite3` | Schema file + empty DB created at `~/.hermes/research/decisions.sqlite3` | `python-reviewer` |
| **T4** | Build `FeatureStore` lookup helper | 2 | T1, T2 | `bwe_autoresearch/feature_store.py` with `get(symbol)`, TTL cache, fallback row | `pytest` covers cache hit, miss, stale (>36h) → returns sentinel `lifecycle="quiet"` | `tdd-guide` |
| **T5** | Implement `build_lifecycle_aware_config` factory | 2 | spec §3.2, exit_v2 module | `bwe_autoresearch/exit_config_factory.py` | Unit tests cover all 5 lifecycle branches; returns `ExitConfig` baseline for unknown | `tdd-guide` |
| **T6** | Add config flags to `bwe_live_autotrader_binance_expectancy_live.json` | 0.5 | spec §6.1 | Patched config with `exit_engine.{use_v2,per_lifecycle_config}=false`, `market_scan_engine` block disabled | `jq` validates JSON; flags default to safe-off | `general-purpose` |
| **T7** | Wire entry hook in `bwe_live_autotrader.py:_open_position` | 3 | T4, T5, T6 | Patch to `bwe_live_autotrader.py` | When flags off → byte-identical behavior to prior commit (regression diff = 0); when on → `position["exit_config"]` set | `code-reviewer` |
| **T8** | Add decision logging in `_open_position` | 2 | T3, T7 | Append-row helper writing to `decisions.sqlite3` | Every paper open writes one row with `source="BWE"`, `features_json`, `exit_config_label` | `tdd-guide` |
| **T9** | Daily features cron entry + smoke test | 1 | T2 | `crontab` line `0 4 * * *` → `compute_symbol_features.py`; `daily_features_YYYY-MM-DD.json` artifact | Two consecutive days produce JSON; lifecycle distribution stable ±10% | `general-purpose` |
| **T10** | Phase 2 paper bot relaunch + smoke check | 1 | T6, T7, T8, T9 | Restarted paper instance with `use_v2=true`, `per_lifecycle_config=true` | First 5 BWE-triggered trades show non-default `exit_config_label` in decision log | `general-purpose` |
| **T11** | Phase 2 verification harness | 2 | T10 | `scripts/phase2_pass_check.py` reading paper journal | Reports {total_raw, win_rate, catastrophes/100} vs §8.1 thresholds | `tdd-guide` |

**Phase 2 subtotal: 11 tasks, ~18.5 hr**

---

### Phase 3 — BWE L2-per-lifecycle live pilot (target: 1 week)

| ID | Title | Hrs | Inputs | Outputs | DoD | Executor |
|---|---|---|---|---|---|---|
| **T12** | Define live-pilot strategy whitelist | 1 | Phase 2 results | Patch to live config: `live_pilot.strategies=["DAM_class","ZKJ_class"]` only | Whitelist gate enforced before `_open_position`; non-whitelisted strategies SKIP with reason `not_in_pilot` | `code-reviewer` |
| **T13** | Add hard stop guardrail check | 1 | exit_v2 hard-stop param | Defensive check that `exit_config.hard_stop_pct ≤ 30` for any live-pilot trade | Unit test asserts oversized stop is clamped | `tdd-guide` |
| **T14** | Live pilot enablement script + rollback runbook | 1 | T12 | `runbooks/phase3_live_enable.md` + `phase3_rollback.sh` (single command flips flags off) | Dry-run rollback verifies all flags revert in <5s | `general-purpose` |
| **T15** | Live pilot relaunch | 0.5 | T12-T14 | Restart with whitelist + use_v2 on | Process up; first 1 hr no errors; positions opened only for whitelisted strategies | `general-purpose` |
| **T16** | Phase 3 daily monitor | 2 | T11 | `scripts/phase3_live_monitor.py` running every 30m | Alerts to journal if 3 consecutive losses or daily PnL < -2% capital | `tdd-guide` |
| **T17** | Phase 3 sign-off pack | 1 | After 5–10 live trades | `40_EXPERIMENTS/round4/05_audits/phase3_signoff.md` with PnL, win rate, catastrophes | Gating numbers tabulated; explicit go/no-go recommendation | `general-purpose` |

**Phase 3 subtotal: 6 tasks, ~6.5 hr** (plus 1 wk wallclock for live data)

---

### Phase 4 — Market scan paper (target: 1 week)

| ID | Title | Hrs | Inputs | Outputs | DoD | Executor |
|---|---|---|---|---|---|---|
| **T18** | Implement `apply_rules` rule engine | 2 | spec §4.2 | `bwe_autoresearch/rule_engine.py` | Unit tests with golden inputs cover Rules A–G (≥10 cases); first-match-wins ordering enforced | `tdd-guide` |
| **T19** | Implement `compute_wave_features` | 2 | live DB klines | `bwe_autoresearch/wave_features.py` exposing `duration`, `pre_vol`, `magnitude` | Tests use frozen klines fixture; pre_vol matches numpy reference within 1e-6 | `tdd-guide` |
| **T20** | Implement event detector (±8% / 5min loop) | 3 | live DB read-only handle | `bwe_autoresearch/event_detector.py` with `scan(now)` → list[event] | Replay last 24h of live DB → detected count within ±10% of independent SQL count | `tdd-guide` |
| **T21** | Build `bwe_market_scan_entry.py` orchestrator | 3 | T18–T20, T4, T5, T8 | New file `/Users/ye/.hermes/scripts/bwe_market_scan_entry.py` (independent process) | 60s loop runs without leaking SQLite handles for 1 hr; structured logs to `~/.hermes/logs/market_scan.log` | `python-reviewer` |
| **T22** | Add 4-tier position sizing helper | 1 | spec §4.3 | `bwe_autoresearch/position_sizer.py` (tier→pos_pct map) | Unit test covers Mini/Standard/High/Max | `tdd-guide` |
| **T23** | Wire market scan → `_open_position` IPC | 2 | T21, T7 | Either (a) shared decision queue file, or (b) HTTP POST to autotrader; pick (a) for simplicity | Round-trip test: market scan writes 1 row → autotrader picks up <2s, opens paper position with `source="MARKET_SCAN"` | `code-reviewer` |
| **T24** | Enforce `max_concurrent_trades=3` for MARKET_SCAN source | 1 | T23 | Source-tagged position counter in autotrader | Test: 4th queued event SKIPped with reason `max_concurrent_market_scan` | `tdd-guide` |
| **T25** | Market scan paper enablement | 0.5 | T23, T24 | Patch config `market_scan_engine.enabled=true` (paper only); systemd-style supervisor entry | Process auto-restarts after kill; log shows scan iterations every 60s | `general-purpose` |
| **T26** | Phase 4 daily report builder | 2 | T25 + decision log | `scripts/phase4_paper_report.py` outputting daily JSON + markdown to `05_audits/` | Report shows count/rule, win-rate/rule, total_raw, mean_cap | `tdd-guide` |
| **T27** | Phase 4 verification gate script | 1 | T26 | `scripts/phase4_pass_check.py` against §8.2 thresholds | After 30+ events, returns exit code 0 only if total_cap > 0 + win_rate > 60% | `tdd-guide` |

**Phase 4 subtotal: 10 tasks, ~17.5 hr**

---

### Phase 5 — Full live + dual-source hybrid (iterative)

| ID | Title | Hrs | Inputs | Outputs | DoD | Executor |
|---|---|---|---|---|---|---|
| **T28** | Hybrid live config promotion plan | 1 | Phase 4 sign-off | `runbooks/phase5_hybrid_promotion.md` (gradual: scan first, then BWE remove whitelist) | Stepwise checklist, each step has explicit rollback flag | `general-purpose` |
| **T29** | Cross-source position-budget arbiter | 2 | T24 | Helper that allocates open-slot budget across BWE + MARKET_SCAN sources | Test: when 5 BWE positions open + 2 scan, 3rd scan is blocked but BWE still allowed (separate budgets respected per spec) | `tdd-guide` |
| **T30** | Live promotion of market scan source | 0.5 | T28 | Config flip; live process restart | First scan-source live trade logs `source="MARKET_SCAN"` and `mode="live"` | `general-purpose` |
| **T31** | Remove BWE strategy whitelist (full L2-per-lifecycle live) | 0.5 | Phase 3 sign-off + 7d scan-live clean | Patch removing `live_pilot.strategies` filter | All BWE strategies routable; rollback restores filter | `code-reviewer` |
| **T32** | Weekly hybrid review automation | 2 | T26, T17 | `scripts/weekly_hybrid_review.py` cron'd Monday 06:00 | Produces `weekly_hybrid_YYYY-WW.md` to `50_ANALYSIS_REPORTS/` with per-source breakdown | `tdd-guide` |
| **T33** | Regression baseline lock | 1 | spec §13 | `tests/test_baseline_regression.py` failing CI if recent rolling 30d mean_cap drops > 30% vs §13 numbers | Test runs from journal data; passes today | `tdd-guide` |

**Phase 5 subtotal: 6 tasks, ~7 hr** (plus open-ended iterative wallclock)

---

### Cross-cutting / safety

| ID | Title | Hrs | Inputs | Outputs | DoD | Executor |
|---|---|---|---|---|---|---|
| **T34** | Watchdog protection regression test | 1 | `collectors_watchdog.sh` | Test stub that mocks each collector PID and asserts watchdog detects | Test runs `collectors_watchdog.sh --selftest`; non-zero exit on simulated stale | `code-reviewer` |
| **T35** | DB read-only handle pattern enforcement | 1 | Live DB | Lint check that any new code opening `binance_futures_1m.sqlite3` uses `mode=ro` URI | grep + AST check fails CI on writable open | `python-reviewer` |
| **T36** | Reaction weekly recompute job | 1 | T2 | Separate cron `0 5 * * 0` calling `compute_symbol_features.py --reaction-only` | Sunday-only run updates `reaction` + `reaction_computed_at_ms`; lifecycle untouched | `general-purpose` |
| **T37** | Lifecycle stale guard | 1 | T4 | Refuse to apply per-lifecycle config when `now - computed_at_ms > 36h`; fall back to baseline | Unit test forces stale row → factory returns baseline | `tdd-guide` |
| **T38** | End-to-end smoke replay | 2 | T2, T18, T20, T21 | `scripts/e2e_smoke_replay.py` replays last 24h of live DB through scan engine in dry-run | Logs identical event count when run twice (deterministic) | `tdd-guide` |

**Cross-cutting subtotal: 5 tasks, ~6 hr**

---

**Grand total: 38 atomic tasks, ~55.5 implementation hours.**

---

## 2. Dependency graph

```
T1 ─► T2 ─► T9
 │     ├──► T4 ─► T5 ─► T7
 │     │            └──► T37
 │     └──► T36
T3 ─► T8 ─► T10 ─► T11 ─► (Phase 2 gate)
T6 ─► T7
                          (Phase 2 gate) ─► T12 ─► T13 ─► T14 ─► T15 ─► T16 ─► T17 ─► (Phase 3 gate)

(Phase 2 gate or T8) ─► T18, T19, T20, T22  (parallel quartet)
T18 + T19 + T20 ─► T21
T21 + T22 ─► T23 ─► T24 ─► T25 ─► T26 ─► T27 ─► (Phase 4 gate)

(Phase 3 + Phase 4 gates) ─► T28 ─► T29 ─► T30 ─► T31 ─► T32 ─► T33

Cross-cutting: T34 anytime; T35 before any code merging; T38 between Phase 4 build and Phase 4 enable.
```

| Edge | Reason |
|---|---|
| T1→T2 | Schema must exist before batch writes |
| T2→T4 | Feature store reads what batch writes |
| T4+T5→T7 | Hook needs both lookup and config factory |
| T3→T8 | Decisions table must exist before logging |
| T7+T8→T10 | Bot needs hook + logging together for clean Phase 2 |
| T10→T11 | Verification needs running data |
| Phase2-gate→T12 | Don’t pilot live until paper passes |
| T18+T19+T20→T21 | Orchestrator composes the trio |
| T21→T23 | IPC depends on orchestrator existing |
| T23→T24 | Concurrency cap is a wrapper around IPC |
| Phase3+Phase4→T28 | Hybrid plan needs both single-source proofs |

---

## 3. Parallelizable groups (different write scopes)

| Group | Members | Why parallel-safe |
|---|---|---|
| **G-A: Schema setup** | T1, T3 | Different SQL files, different DB targets |
| **G-B: Phase 2 helpers** | T4, T5, T22 | Three independent modules under `bwe_autoresearch/` |
| **G-C: Phase 4 quartet** | T18, T19, T20 (+T22 if not done) | All new files, no shared edits |
| **G-D: Verification & runbooks** | T11, T14, T16, T26, T27 | Each writes its own report/script |
| **G-E: Cross-cutting safety** | T34, T35, T37 | Independent guard scripts/tests |

**Conflicts to avoid (must be serialized):**
- T7 + T8 + T13 + T31 all touch `bwe_live_autotrader.py` → strict sequence.
- T6 + T12 + T25 + T30 all touch the same JSON config → serial only.

---

## 4. Phase mapping (tasks ↔ spec §7)

| Phase | Tasks | Spec section |
|---|---|---|
| **1** Data + tools | (already done) — verified by T34, T35 | §7 row 1 |
| **2** BWE L2-per-lifecycle paper | T1–T11 + T36, T37 | §3, §6.2, §7 row 2, §8.1 |
| **3** BWE live pilot | T12–T17 | §7 row 3, §9 risk row 1 |
| **4** Market scan paper | T18–T27 + T38 | §4, §6.3, §7 row 4, §8.2 |
| **5** Full live hybrid | T28–T33 | §7 row 5, §13 baselines |
| **Cross-cutting** | T34, T35 (safety), T36 (weekly), T37 (stale), T38 (smoke) | §9 risks |

---

## 5. Critical path analysis

Critical path (longest chain to "live with both sources running"):

```
T1 → T2 → T4 → T5 → T7 → T8 → T10 → T11
     [Phase 2 paper soak: 3–7 days wallclock]
   → T12 → T13 → T14 → T15 → T16 → T17
     [Phase 3 live soak: 5–10 trades, ~1 week]
   → T18 → T21 → T23 → T24 → T25 → T26 → T27
     [Phase 4 paper soak: 30+ events, ~1 week]
   → T28 → T29 → T30 → T31
```

**Implementation hours on critical path: ~28 hr** (T1+T2+T4+T5+T7+T8+T10+T11+T12+T13+T14+T15+T16+T17+T18+T21+T23+T24+T25+T26+T27+T28+T29+T30+T31).

**Wallclock minimum** (assuming Mac mini single-thread, no parallelism, soaks honored):
- Phase 2 build: ~2.5 days
- Phase 2 soak: 3 days minimum (spec says 3 days PnL>0)
- Phase 3 build + 5–10 trades: ~7 days
- Phase 4 build: ~2.5 days
- Phase 4 soak: ~7 days (need 30+ events)
- Phase 5 promotion: ~1 day
**Total minimum: ~22 wallclock days** to reach "both sources live".

---

## 6. Verification gates per phase

### Gate after Phase 2 (must pass before T12)
- [ ] T11 reports `total_raw > +50%` AND `win_rate > 60%` AND `catastrophes/100 < 5` (per §8.1)
- [ ] No watchdog incident during Phase 2 window (T34 selftest still green)
- [ ] Decision log row count == paper trade count (no silent drops)
- [ ] Lifecycle distribution diff Day1→Day7 < 10% (T9 stability)

### Gate after Phase 3 (must pass before T28)
- [ ] T17 sign-off shows positive total PnL across pilot
- [ ] No 3-consecutive-loss event triggering T16 alert
- [ ] Hard-stop never breached (T13 invariant held)

### Gate after Phase 4 (must pass before T28)
- [ ] T27 returns exit code 0 (`total_cap > +25%`, `win_rate > 60%`, `mean_cap > +0.05%`)
- [ ] `max_concurrent_market_scan` cap never hit silently >5x/day
- [ ] T38 smoke replay deterministic across 2 consecutive runs

### Gate after Phase 5 promotion (continuous)
- [ ] T33 regression test green every weekly cron
- [ ] Per-source PnL split visible in T32 weekly report

### Universal kill-switch (T14, T31 rollback paths)
- [ ] At any time, `use_v2=false + market_scan_engine.enabled=false` returns to L1 within <60s.

---

## 7. Resource allocation recommendations

### Single-threaded (1 subagent active)
Critical-path order is enforced. Total ~22 wallclock days as above. Lowest risk.

### 2 subagents in parallel
- **Worker A (build path)**: T1 → T2 → T4 → T5 → T7 → T8 → T10 → T11
- **Worker B (helpers + Phase 4 prep)**: T3 → T6 → T9 → T36 → T37 → T34 → T35 → T18 → T19 → T20 → T22 → T38
- Convergence point: T21 needs Worker B's T18+T19+T20 done before Worker A finishes Phase 2 soak.
- Saves ~3 days build wallclock, soaks unchanged.

### 3 subagents in parallel
- **Worker A**: schema + Phase 2 build (T1, T2, T4, T5, T7, T8)
- **Worker B**: Phase 4 helpers (T18, T19, T20, T22) + cross-cutting (T34, T35, T37)
- **Worker C**: ops + verification (T3, T6, T9, T11, T14, T16, T26, T27, T36, T38)
- All three converge at end of Phase 2 build, then mostly idle during Phase 2 soak.
- Saves ~5 days build wallclock total.
- **Risk**: 3-way merge contention on `bwe_live_autotrader.py` (T7) and the Hermes JSON config (T6, T12, T25, T30) — these MUST be serialized regardless of how many workers are active.

**Recommended: 2 subagents in parallel** — best build-time savings without contention risk on the hot autotrader file.

---

## 8. Known sequencing pitfalls

1. **Feature store BEFORE market scan engine** — T4/T2 must complete before T21, else scan code has no `lifecycle/reaction` to read and Rule C/D collapse to default. (Spec §4.2 hard-requires `meta["n_waves_14d"]`, `meta["lifecycle"]`, `meta["reaction"]`, `meta["score"]`.)

2. **Schema migration BEFORE batch writes** — T1 must precede T2, and T3 must precede T8. Running T2/T8 first creates implicit schemas that drift from the spec.

3. **Live DB writes are forbidden** — any new code (T20, T21) must open `binance_futures_1m.sqlite3` with `?mode=ro&immutable=1`. Forgetting this can corrupt the hot collector's WAL. T35 enforces this as a CI guard — land it early.

4. **Watchdog touch-paranoia** — T34 (regression test) should land before any other change to confirm baseline. Subsequent tasks must not rename/move `collectors_watchdog.sh` or its cron entry.

5. **`bwe_live_autotrader.py` edits MUST be serialized** — T7, T8, T13, T24, T31 all modify the same file. If two subagents land patches concurrently, the live 24/7 process can get a corrupted import on next reload (`config_reloaded` path at line 408 watches mtime). Pick one worker to own this file across the project.

6. **Config flag flips are atomic ops** — never partial-edit the live config. T6, T12, T25, T30 each must produce a complete valid JSON in one write. Use `mv tmp final` pattern, not in-place edits.

7. **Phase 2 paper enablement (T10) must come AFTER decision log (T8)** — without T8, paper run has no audit trail and Phase 2 verification (T11) has nothing to read.

8. **Hard stop guard (T13) before live (T15)** — landing T15 without T13 means a misconfigured `ExitConfig` could exceed the §9 risk budget on first live trade.

9. **Reaction weekly job (T36) BEFORE Phase 4** — Rule B/C in §4.2 read `reaction`. If T36 hasn't run a Sunday cycle, all symbols return `reaction="n_a"` and Rule B/C are dead.

10. **T29 (cross-source budget) before T30** — promoting market scan to live without per-source position budgets risks one source starving the other. Spec §6.3 hints at this (`max_concurrent_trades=3` is per-scan, not global), but T29 makes the contract explicit.

11. **Stale-feature guard (T37) is silent-correctness** — without it, a 7-day-old lifecycle label could silently apply wrong ExitConfig after a market regime shift. Land before any live phase.

12. **End-to-end smoke (T38) gates Phase 4 enable (T25)** — a 24h dry replay catches schema drift between batch writer and scan reader before they go live in tandem.

---

## 9. Verification approach summary

- **Test-first** (TDD) on T2, T4, T5, T8, T11, T13, T16, T18, T19, T20, T22, T24, T26, T27, T29, T32, T33, T34, T37, T38 — 20 tasks have meaningful failing tests writable up front.
- **Structural / smoke validation** on T1, T3, T6, T9, T10, T12, T14, T15, T17, T25, T28, T30, T31, T35, T36 — config/runbook/cron, no obvious unit test, but each has a concrete check.
- **Integration test** on T7, T21, T23 — these wire pieces together; verification is round-trip via test fixture.

---

## 10. Open issues for caller

1. **Decision log DB location**: I assumed `~/.hermes/research/decisions.sqlite3` (sidecar) over reusing `binance_extended_history.sqlite3`. If the user prefers consolidated, change T3 target — it does not change downstream tasks.
2. **IPC mechanism between scan engine and autotrader**: T23 picks "shared file queue" (simpler, file-system durable). HTTP option exists but adds a service surface. Caller should confirm.
3. **Live pilot whitelist names** (T12): spec says "DAM/ZKJ-class" but exact strategy IDs depend on the BWE live config; leaving as a placeholder for the user to fill at T12 time.
4. **Cross-source budget split** (T29): spec is silent on whether budgets are equal or weighted. Suggested default: 3 slots BWE + 3 slots MARKET_SCAN, total cap `max_concurrent_positions` from existing `risk` block. Caller should confirm before T29 lands.

---

## Execution sign-off: PLAN READY

- 38 atomic tasks, ~55.5 implementation hours.
- 22-day minimum wallclock to dual-source live (build + mandatory soaks).
- All 5 phases have explicit pass criteria mapped to spec §8.
- 12 sequencing pitfalls identified with concrete mitigations.
- 4 open issues flagged for caller confirmation but not blocking — defaults stated.
- Backwards-compat preserved at every step (G5): the `use_v2=false + market_scan_engine.enabled=false` rollback returns to L1 in <60s.
