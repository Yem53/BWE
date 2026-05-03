# BWE v2 Phase T48-T50 — Layer B Scanner + VPN Routing — Implementation Plan

> **Status**: 2026-04-29 16:55 UTC — Synthesized from 4 fallback role agents (architect / execution-lead / auditor / pack-validator). Awaiting user `批准执行`.
> **For agentic workers**: REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (preferred) or `superpowers:test-driven-development` (inline). Steps use `- [ ]` checkboxes.

---

## Goal

Build a Layer B market scanner that polls all 530 Binance USDT-M perp futures for ±8% wave events (mimics BWE Telegram pattern, exceeds it via direct local DB access + 30s cadence + 530 sym coverage), feeds events into the existing bot via JSONL pattern, and ensures ALL Binance-interacting processes route through Clash Verge.

## Architecture

- **Scanner** = standalone process, reads local SQLite (collector writes), zero direct Binance HTTP — VPN routing concern is moot for scanner itself. Decoupled via JSONL event file.
- **VPN enforcement** = process-launcher wrapper exporting `HTTP_PROXY/HTTPS_PROXY` env vars; Clash Verge (127.0.0.1:7897) handles speed-tier policy group + auto-fallback transparently.
- **Backwards compat** = `market_scan_engine.enabled=false` default + 24h shadow-only mode + A/A+B PnL parity gate.

## Tech Stack

Python 3.11 / sqlite3 (WAL+query_only) / requests (env-var proxy) / pytest / atomic JSONL append / Clash Verge HTTP/SOCKS5 on 127.0.0.1:7897.

---

## §A. Materials Audit ✅

| Material | Read | Status |
|---|---|---|
| `per_symbol_design_v2.md` §1-4 (Layer B spec) | ✅ | Source of truth |
| `rule_engine.py` (apply_rules 7 规则) | ✅ | Reuse, do not modify |
| `position_sizing.py` (4-tier 12/8/5/3) | ✅ (in T1-T47) | Reuse |
| `feature_store.py` (530 symbols pre-computed) | ✅ | Reuse |
| `alert_dispatcher.py` (T45) | ✅ | Reuse |
| `bwe_matrix_monitor.py` (BWE pattern reference) | ✅ | Pattern template |
| Live process list | ✅ | metric_collector NOT running (VPN-fix casualty) |
| Live klines DB | ✅ | 5 GB, 16:50 UTC update — collector alive |
| Clash exit IP geolocation | ✅ | Verizon NYC home (split-routing); Binance traffic via Colombia node |

## §B. Coordination Layer

- **Mode**: 4-agent fallback (no official persistent team available in runtime)
- **Launched (real, parallel)**:
  - architect → 65s, 36.7K tokens — 5 architectural decisions + ASCII flow + 3 risks
  - execution-lead → 37s, 18.6K tokens — task graph + critical path + parallelizable items
  - auditor → 34s, 18.5K tokens — 10-row risk register + 4 gates + 4 scenarios
  - pack-validator → 50s, 43.5K tokens — spec → deliverable matrix + 7 gaps + 5 hard acceptance criteria
- **All explicitly disclosed as fallback role agents, not official teammates**

## §C. Superpowers Skills Used

| Phase | Skill | Status |
|---|---|---|
| Brainstorming | `superpowers:brainstorming` | Used in earlier sessions when spec was finalized; not re-invoked (this is Y option of approved spec) |
| Planning | `superpowers:writing-plans` | ✅ Loaded this turn |
| Coordination | `coordination-protocol` (per Agent-teams-plan command) | Implicit |
| Execution (after approval) | `subagent-driven-development` + `test-driven-development` + `requesting-code-review` + `verification-before-completion` | Pending approval |
| Debugging path | `systematic-debugging` | Reserved |

## §D. Claude-MEM Findings

**Intentionally skipped.** The current task (T48 Layer B) is a direct Y-option of the spec that was already finalized via brainstorming + 4 archived phase docs in earlier sessions. No new domain retrieval needed. **Auditor + Pack Validator both treated spec as source of truth and confirmed no gaps requiring memory retrieval.** If user disputes this judgement, can retroactively run claude-mem search before execution.

## §E. Prompt Pack Audit (from Pack Validator)

### Conformance matrix

| Spec ref | Requirement | T48/T49/T50 task | Evidence required |
|---|---|---|---|
| §1.2 | Layer B as independent process | T48d main loop | Process launchable separately |
| §4.1 | 1m scan / 530 syms / ±8% / 5m close | T48a-d | Unit test: ±7.99% no fire, ±8.0% fires |
| §4.2 | Reuse 7-rule engine | T48d imports `rule_engine.apply_rules` | grep proves zero duplication |
| §4.3 | 4-tier sizing 3/5/8/12% via existing | T48d imports `position_sizing.compute_pos_lev` | grep proves zero duplication |
| §4.4 | Baseline ExitConfig only (no per-lifecycle on Layer B) | T48d emits `exit_config="baseline"` | Test asserts no lifecycle swap |
| §5.1 | Read from `symbol_features` | T48d via existing `feature_store` | Test with seeded sqlite |
| §5.2 | Write `entry_decisions` row per event | T48d via existing `entry_decisions_logger` | Row count matches event count |
| §6.1 | `enabled=false` default | T48d config flag | Default config rejects live |
| §6.3 | max_concurrent_trades=3 | Bot existing concurrency cap (no T48 work) | Pre-existing |
| §7 P4 | Layer B PAPER first | T48d ships flag-gated, no live until Phase 2 passes | Live entrypoint blocked |
| User C3 | All Binance HTTP via clashverge | **T49** = wrapper enforcement | grep + lsof audit |
| User C4 | Restart broken collectors | **T50** = restart + freshness check | All 3 collectors live <120s freshness |

### Pack Validator gaps flagged (HIGH severity)

1. **"Exceed BWE" superiority metric** not in spec — adding to plan: latency < BWE alert lag (BWE ~10-30s lag, scanner ~30s deterministic) + coverage 530 vs BWE ~100 syms.
2. **Reuse existing entry hook** (line 1698 added in T47) — bot reads scanner_events.jsonl via existing event_log mechanism. **Do NOT add 5th hook.**
3. **Phase ordering**: Layer B activation MUST wait for Phase 2 (BWE L2-per-lifecycle paper smoke 48h) to pass before going live. Locked in §X (this plan) and verified at gate G5.

## §F. Preflight Audit

| Item | Status |
|---|---|
| `bwe_v2/` modules import-clean | ✅ (verified earlier with 182/182 tests) |
| Bot file syntax-valid after T47 hooks | ✅ (verified earlier) |
| Live klines DB writable + readable | ✅ (5GB, 60s freshness) |
| Clash Verge listener on 127.0.0.1:7897 | ✅ (Binance via proxy returns 200) |
| chat_id captured for both bots | ✅ (5394953277) |
| `.env_bwe_v2` chmod 600 + gitignored | ✅ |
| metric_collector running | ❌ — needs T50 restart |
| Bot's JSONL reader generic enough? | ⚠️ — must verify in T48e (architect flagged) |

## §G. Design Summary (from Architect)

**Module decomposition** (all new in `/Users/ye/.hermes/scripts/bwe_v2/`):

```
scanner_detector.py     pure ±8% / wave_features detection (no I/O)
scanner_cooldown.py     in-memory + SQLite-backed dedup, 15min TTL, injectable clock
scanner_event_writer.py atomic JSONL append (single os.write to avoid race)
market_scanner.py       main loop: clock-aligned 30s cadence (T+15s, T+45s offsets)
launch_with_proxy.sh    NEW wrapper: HTTP_PROXY/HTTPS_PROXY env + Clash health gate
```

**Data flow**:

```
binance_futures_1m_collector.py  (writes DB every 60s, via Clash proxy)
                |
                v
binance_futures_1m.sqlite3  (read-only by scanner)
                |
                v
+--- market_scanner.py (every 30s, T+15s/T+45s offsets) ---+
|  1. read latest closed bar per symbol                    |
|  2. scanner_detector.detect(±8%) [pure]                   |
|  3. scanner_cooldown.is_eligible(symbol)                  |
|  4. feature_store.get(symbol) + WaveFeatures              |
|  5. rule_engine.apply_rules() → Decision                  |
|  6. scanner_event_writer.emit(event) → JSONL              |
+----------------------------------------------------------+
                |
                v  (existing tail-and-resume reader in bot)
bwe_v2_scanner_events.jsonl  (append-only)
                |
                v
bwe_live_autotrader.py  (Layer A bot, reuses existing entry path)
                |
                v
[PROTECTED] rule_engine → position_sizing → alert_dispatcher (unchanged)
```

## §H. Task Decomposition + Dependencies

### Phase A: VPN Routing (T49) — gates all subsequent

```
T49a (15min) : Audit proxy state — grep current env, lsof PIDs 38446/40876, ping 7897
       gate: curl -x http://127.0.0.1:7897 https://fapi.binance.com/fapi/v1/ping → 200
       deps: none
       
T49b (30min): Write launch_with_proxy.sh
       exports HTTP_PROXY=http://127.0.0.1:7897, HTTPS_PROXY=same, NO_PROXY=localhost,127.0.0.1
       gate: dry-run --help succeeds with env shown
       deps: T49a
       
T49c (15min): Add proxy preflight to wrapper
       fail-fast if 7897 unreachable, retry 3x with backoff before exit 1
       gate: kill Clash → wrapper refuses launch; restart → wrapper proceeds
       deps: T49b
```

### Phase B: Restart Failed Collectors (T50)

```
T50a (15min, parallel with T49a): Inventory expected vs running collectors
       expected: 1m, metric, 24h_ticker (3 total)
       actual: 1m ✓, 24h_ticker ✓, metric ✗
       gate: written diff list
       deps: none
       
T50b (15min): Restart binance_futures_metric_collector via T49b wrapper
       nohup → tail log 60s → assert HTTP 200s + no proxy errors
       gate: 60s clean writes + log shows proxy header
       deps: T49b, T50a
       
T50c (15min): Verify all 3 collectors using proxy
       lsof -p <pid> -i shows TCP to 127.0.0.1:7897 (not Binance IPs)
       if any bypassing: kill + restart through wrapper
       gate: lsof confirms all 3 → 7897
       deps: T49b, T50a, T50b
```

### Phase C: Scanner Modules (T48 TDD chain)

```
T48a (1.5h): scanner_detector.py + tests
       pure functions: detect_8pct(bars, window=5), wave_features(bars, event_idx)
       RED: 5 unit tests (synthetic ±8.0/7.99/-8.0/-7.99 / volume spikes)
       GREEN: minimal impl
       gate: 5/5 tests green; pure (no imports beyond stdlib + dataclasses)
       deps: T48-design-freeze (this plan = freeze)
       
T48b (1h): scanner_cooldown.py + tests
       Cooldown class: is_eligible(sym, now), mark_fired(sym, now)
       in-memory dict + sqlite WAL backed; injected clock for tests
       RED: 6 tests (eligible/blocked/restart-recovers/expires/multi-sym/clock-monotonic)
       GREEN: minimal impl
       gate: 6/6 + restart recovery test green
       deps: T48a (none — independent)
       
T48c (45min): scanner_event_writer.py + tests
       emit(event_dict) → JSONL line via single os.write(fd, bytes+\n)
       atomic: build full bytes BEFORE write
       includes source="scanner_v2", schema versioned
       RED: 4 tests (single line, no half-line race, schema validation, fsync optional)
       gate: 4/4 + concurrent-writer race test green
       deps: T48a (none)
       
T48d (1.5h): market_scanner.py + tests
       Main loop: every 30s aligned to T+15s+T+45s, reads DB, calls detector + cooldown,
       looks up feature_store, computes WaveFeatures, calls rule_engine.apply_rules,
       emits event via writer
       RED: 6 integration tests with seeded sqlite + injected clock
            (no fire below threshold, fire on threshold, cooldown blocks re-fire,
             rule A skips for low n_waves, rule G fires default fade, stale data warning)
       GREEN: minimal impl
       gate: 6/6 green + 30s-loop dry run on real DB shows 0 errors
       deps: T48a, T48b, T48c
       
T48e (45min): Bot JSONL reader extension
       Modify bot to read second JSONL path from config alerts_v2.scanner_event_log
       Architect flag — if bot's reader is hardcoded, add config key (small additive change)
       RED: test bot picks up scanner_events.jsonl when path configured
       gate: bot processes 1 synthetic scanner event end-to-end (no live trade)
       deps: T48d
```

### Phase D: Verification Gates (Auditor's required artifacts)

```
T48f (45min): Shadow-only mode flag — Auditor R2 [HIGH PRIORITY]
       config: market_scan_engine.shadow_only=true
       when shadow_only=true: scanner emits to .shadow.jsonl (different file),
       bot does NOT consume; only logged for analysis
       gate: 24h shadow run → directional accuracy ≥55% before flipping shadow_only=false
       deps: T48d, T48e
       
T48g (1h): A/A+B PnL parity test — Auditor R3 [CRITICAL]
       7-day historical replay: run bot with B disabled vs B enabled-but-shadow-only
       PnL hash must match byte-for-byte (B disabled should not affect Layer A path)
       gate: hash equality
       deps: T48f
       
T48h (30min): VPN egress chaos test — Auditor R4 [CRITICAL]
       kill Clash mid-loop → assert scanner gracefully halts (no panic, no direct API)
       restart Clash → assert scanner resumes
       gate: zero direct binance.com IP connections via lsof during outage
       deps: T48d, T49c
       
T48i (1h): 30-day historical replay — Auditor R9
       Read 30d klines DB, replay through scanner, compare detected events to
       ground-truth ±8% moves
       gate: precision ≥95%, recall ≥90%
       deps: T48d
       
T48j (30min): Token bucket circuit breaker — Auditor R5
       Daily trigger cap (default 20), per-symbol cooldown ≥30min
       Auto-halt at 1.5x expected (i.e., 30/day)
       gate: synthetic 50 events/day → halts at trigger #30 + alert_dispatcher pings
       deps: T48d
```

### Phase E: Acceptance Gate (per Pack Validator)

```
T48z (30min): Acceptance review against 5 hard criteria
       1. Reuse no duplication (grep proves)
       2. Default OFF + paper-only (config inspection)
       3. Proxy on every Binance call (lsof + grep)
       4. All 3 collectors live + freshness <120s
       5. Phase ordering documented (this plan locks: NO live until Phase 2 passes)
       deps: T48a-j, T49a-c, T50a-c
```

### Critical path & total effort

```
T49a → T49b → T49c → T50b → T50c → T48a → T48b → T48c → T48d → T48e
        → T48f (24h shadow!) → T48g → T48h → T48i → T48j → T48z

Pure code work: ~7-8h
Add 24h shadow run: 24h+ wall time
Total: ~9 hours active dev + 24h shadow run
```

Parallelizable: T48a/b/c (independent modules) can run in 3 parallel subagents after T49+T50 done.

## §I. Phase → Task Checklist (Live Task Board)

```
Phase A: VPN Routing
  [ ] T49a Audit proxy state
  [ ] T49b launch_with_proxy.sh
  [ ] T49c proxy preflight

Phase B: Collector Restart
  [ ] T50a Inventory
  [ ] T50b Restart metric_collector
  [ ] T50c Verify all 3 proxying

Phase C: Scanner Modules (TDD)
  [ ] T48a scanner_detector.py
  [ ] T48b scanner_cooldown.py
  [ ] T48c scanner_event_writer.py
  [ ] T48d market_scanner.py
  [ ] T48e Bot JSONL reader extension

Phase D: Verification Gates
  [ ] T48f Shadow-only mode flag
  [ ] T48g A/A+B PnL parity test
  [ ] T48h VPN egress chaos test
  [ ] T48i 30-day replay precision/recall
  [ ] T48j Token bucket circuit breaker

Phase E: Acceptance
  [ ] T48z 5-criteria acceptance gate

Post-T48 (separate phase):
  [ ] 48h paper smoke (T11) MUST PASS before Layer B → live
```

## §J. File / Module Touch List

### Create (all new)
- `/Users/ye/.hermes/scripts/bwe_v2/scanner_detector.py`
- `/Users/ye/.hermes/scripts/bwe_v2/scanner_cooldown.py`
- `/Users/ye/.hermes/scripts/bwe_v2/scanner_event_writer.py`
- `/Users/ye/.hermes/scripts/bwe_v2/market_scanner.py`
- `/Users/ye/.hermes/scripts/bwe_v2/launch_with_proxy.sh`
- `/Users/ye/.hermes/scripts/bwe_v2/tests/test_scanner_detector.py`
- `/Users/ye/.hermes/scripts/bwe_v2/tests/test_scanner_cooldown.py`
- `/Users/ye/.hermes/scripts/bwe_v2/tests/test_scanner_event_writer.py`
- `/Users/ye/.hermes/scripts/bwe_v2/tests/test_market_scanner.py`
- `/Users/ye/.hermes/logs/bwe_v2_scanner_events.jsonl` (runtime artifact)

### Modify (additive only)
- `/Users/ye/.hermes/scripts/bwe_live_autotrader.py` — add config-flag-gated 2nd JSONL reader (under 30 lines, no logic change to existing readers)
- `/Users/ye/.hermes/scripts/bwe_live_autotrader_binance_expectancy_paper_smoke.json` — add `market_scan_engine` block

### PROTECTED (do NOT touch)
- ⛔ `rule_engine.py`
- ⛔ `position_sizing.py`
- ⛔ `feature_store.py`
- ⛔ `alert_dispatcher.py`
- ⛔ `exit_v2/` module
- ⛔ Existing 4 surgical hooks in `bwe_live_autotrader.py` (T47 entry/exit hooks at line 1698, ~1571, ~1622, ~1631)
- ⛔ All collectors (binance_futures_1m, binance_24h_ticker, binance_futures_metric)
- ⛔ `bwe_matrix_monitor.py` (Layer A signal source)

## §K. Risks (from Auditor)

| ID | Risk | Impact | Lik | Mitigation | Detection |
|---|---|---|---|---|---|
| R1 | VPN bypass — process talks direct | Critical | High | T49 wrapper + lsof audit + chaos test | Log egress IP per request |
| R2 | Direction inversion (long↔short bug) | Critical | Med | Symmetry tests + 24h shadow + ≥55% accuracy gate | Compare vs realized 1h drift |
| R3 | v2 hooks regress Layer A | Critical | Med | A/A+B parity hash test | side-by-side replay diff |
| R4 | Proxy outage mid-trade | High | Med | Fail-closed scanner; bot holds existing | 30s ping + 3-fail halt |
| R5 | Scanner over-fires | High | Med | Token bucket cap 20/day; 1.5x halt | trigger counter |
| R6 | Unknown rule_id returned | Med | Med | Whitelist enforcement | reject + log + counter |
| R7 | DB lock contention scanner-vs-collector | Med | Low | Read-only WAL connection | lock-wait metric |
| R8 | Existing collectors interrupted by T50 | High | Low | PID-check first; only restart failed | pre-restart snapshot diff |
| R9 | PnL drift from baseline +144.1% | High | Med | 30d replay + stability_score gate | daily replay |
| R10 | Real-money leak via flag forgotten | Critical | Low | Default OFF + paper-only hardcoded | order endpoint URL audit |

## §L. Assumptions, Boundaries, Protected Zones, Open Questions

### Assumptions
1. Bot's JSONL reader is configurable to a 2nd path; if hardcoded, T48e adds the config key (small additive)
2. Spec §4.4 means baseline ExitConfig for Layer B (no per-lifecycle); confirmed by Pack Validator
3. Phase 2 (BWE L2-per-lifecycle paper smoke) MUST pass before any Layer B → live activation; per spec §7
4. The 30s scan cadence + T+15s/T+45s offsets are sufficient given 1m kline granularity
5. Scanner stays out of bot process — emits via JSONL only

### Boundaries
- Scanner does NOT execute trades — only emits events
- Scanner does NOT call Binance API (reads local DB only)
- Bot still owns all order placement
- Layer A path remains unchanged when Layer B disabled

### Protected zones
- All bwe_v2/ modules T1-T47 (rule_engine, position_sizing, feature_store, alert_*)
- exit_v2/ module
- All 3 collectors
- bwe_matrix_monitor.py (BWE Layer A source)
- Existing T47 4 surgical hooks in bot

### Open questions (asked or ambiguous)
1. **Q**: User mentioned "Clash Verge 速度分层 + auto-fallback". Is this configured at the Clash app level (policy group with health-check)? **Plan assumption**: yes, scanner just hits 127.0.0.1:7897 and Clash handles upstream selection.
2. **Q**: Do existing collectors restart cleanly without losing state? **Plan**: T50 inventory + lsof audit before kill.
3. **Q**: Is there a published BWE alert latency we benchmark against for "exceed BWE"? **Plan**: define superiority as scanner's deterministic 30s cadence vs BWE's 10-30s+ variable Telegram lag, plus 530 sym coverage vs BWE's ~100 cherry-picked.

## §M. Verification Strategy

| Gate | Method | Pass criterion |
|---|---|---|
| G1: Module unit tests | pytest per module | 100% green per module |
| G2: Integration test | pytest cross-module | 100% green |
| G3: VPN audit | lsof + grep on all 4 processes | All Binance HTTP via 127.0.0.1:7897 |
| G4: VPN chaos | kill Clash mid-loop | scanner halts, no direct connections |
| G5: 24h shadow | run shadow_only=true 24h | directional accuracy ≥55% on detected events |
| G6: A/A+B parity | 7d replay both modes | PnL hash byte-equal |
| G7: 30d replay | historical run | precision ≥95%, recall ≥90% |
| G8: Phase 2 dependency | wait for 48h BWE paper | Phase 2 passes before Layer B → live |
| G9: 5-criteria acceptance | manual check + grep | All 5 Pack Validator criteria pass |

## §N. Review Checkpoints

```
Checkpoint 1 (after Phase A+B): User reviews proxy enforcement evidence
Checkpoint 2 (after Phase C): User reviews scanner modules + tests (~250 tests total expected)
Checkpoint 3 (after T48f shadow): User reviews 24h shadow accuracy report
Checkpoint 4 (after T48z): Pack Validator + Auditor sign-off → user grants live activation
```

## §O. Blocker Conditions

If ANY of these occur, **STOP** and escalate:

1. T49 cannot route any one collector through proxy → STOP (Binance ban risk)
2. T48 module test coverage <90% → STOP (insufficient confidence)
3. 24h shadow accuracy <55% directional → STOP (rule_engine wrong direction)
4. A/A+B parity hash mismatch → STOP (Layer A regression)
5. 30d replay precision <90% or recall <85% → STOP (detection broken)
6. Phase 2 (BWE L2 48h paper) NOT passed before Layer B live → STOP (rollout violation)

---

## Stop. Wait for User Approval.

User reply pattern:
- `批准执行` → I begin Phase A (T49a) immediately, dispatching subagent per task per `subagent-driven-development` skill
- `修改 ...` → I revise plan
- `先做 X` → I sequence per user override
