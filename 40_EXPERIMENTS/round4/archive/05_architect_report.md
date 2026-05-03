# Architect Report — BWE Per-Symbol 妖币 Strategy v2 Implementation

> Role: **Architect (fallback role agent)** — no official team bootstrap, per /Agent-teams-plan honesty rule.
> Date: 2026-04-29
> Scope: Module decomposition + interface contracts + integration points + risk delta over Auditor B1-B5 + open-question resolution.
> Cross-references:
> - Spec v2: `/Volumes/T9/BWE/40_EXPERIMENTS/round4/per_symbol_design_v2.md`
> - Execution Lead: `/Volumes/T9/BWE/40_EXPERIMENTS/round4/archive/06_execution_lead_report.md` (38 tasks T1-T38)
> - Auditor: `/Volumes/T9/BWE/40_EXPERIMENTS/round4/archive/07_auditor_report.md` (5 blockers B1-B5)
> - Pack Validator: `/Volumes/T9/BWE/40_EXPERIMENTS/round4/archive/08_pack_validator_report.md` (66 reqs REQ-001 .. REQ-066)

---

## 1. Module Decomposition

All new Python modules live under `/Users/ye/.hermes/scripts/bwe_v2/` (sibling to existing scripts) to keep new code physically separate from production live bot.

### 1.1 Feature & state layer

| Module | Path | Responsibility | LOC est | Test |
|---|---|---|---|---|
| `compute_symbol_features.py` | `bwe_v2/compute_symbol_features.py` | Daily batch — reads 30d kline + 5m metrics from `binance_extended_history.sqlite3` + live `binance_futures_1m.sqlite3`, computes yaobi_score / lifecycle / reaction / n_waves_14d per symbol, writes to `symbol_features` table. | ~300 | `tests/test_compute_features.py` |
| `feature_store.py` | `bwe_v2/feature_store.py` | Read-only interface to `symbol_features` table. Single class `FeatureStore` with `get(symbol)` and `staleness(symbol)` methods. Cached in-memory with 5-min TTL. | ~120 | `tests/test_feature_store.py` |
| `lifecycle_aware_config.py` | `bwe_v2/lifecycle_aware_config.py` | Pure function `build_exit_config(lifecycle: str) -> ExitConfig`. Returns wide / tight / baseline based on lifecycle label. | ~60 | `tests/test_lifecycle_config.py` |

### 1.2 Entry & rule engine layer

| Module | Path | Responsibility | LOC est | Test |
|---|---|---|---|---|
| `rule_engine.py` | `bwe_v2/rule_engine.py` | Pure function `apply_rules_l4_tier(features, wave_features, side) -> Decision`. 7 rules, 4-tier position sizing. Returns `Decision(action, position_pct, direction, rule_id)`. No side effects. | ~150 | `tests/test_rule_engine.py` |
| `bwe_market_scan_entry.py` | `bwe_v2/bwe_market_scan_entry.py` | Layer B engine — separate process. Polls `binance_futures_1m.sqlite3` every 60s, detects ±8% events, calls `apply_rules`, creates trade orders via Hermes IPC (signal file or shared SQLite trade_request table). | ~250 | `tests/test_market_scan.py` |
| `position_sizing.py` | `bwe_v2/position_sizing.py` | Pure function `compute_position_pct(rule_id, score) -> float`. Tier mapping 3/5/8/12. Uses `score >= 85` threshold for max-tier upgrade on rule C/D. | ~50 | `tests/test_pos_sizing.py` |
| `entry_decisions_logger.py` | `bwe_v2/entry_decisions_logger.py` | Append-only writer to `entry_decisions` SQLite table. Single function `log_decision(trade_id, source, features_json, ..., reason)`. | ~80 | `tests/test_decisions_logger.py` |

### 1.3 Integration helpers (live bot side)

| Module | Path | Responsibility | LOC est |
|---|---|---|---|
| `bwe_v2/integration_helpers.py` | (lives next to bot scripts) | Thin glue layer importable from `bwe_live_autotrader.py`. Functions: `select_exit_config(symbol)`, `should_use_v2_exit(config)`, `record_decision(trade)`. Designed so live bot imports ~3 functions max. | ~80 |

### 1.4 Scripts (operational)

| Script | Path | Responsibility |
|---|---|---|
| `daily_features_batch.sh` | `bwe_v2/daily_features_batch.sh` | Cron-driven shell wrapper that invokes `compute_symbol_features.py`. Schedule 04:00 UTC daily. |
| `weekly_reaction_refresh.sh` | `bwe_v2/weekly_reaction_refresh.sh` | Cron-driven, computes only `reaction` column (slower path — rolling 14d). Schedule Sunday 04:30 UTC. |
| `regression_check.py` | `bwe_v2/regression_check.py` | Replay last 30d Hermes paper trades + 1425-event broader sample, compare to lock-in baselines. Alert if drift > acceptable. |

### 1.5 Test infrastructure

```
bwe_v2/
├── tests/
│   ├── conftest.py          # fixtures: in-memory SQLite, sample features, sample bars
│   ├── test_compute_features.py
│   ├── test_feature_store.py
│   ├── test_lifecycle_config.py
│   ├── test_rule_engine.py
│   ├── test_market_scan.py
│   ├── test_pos_sizing.py
│   ├── test_decisions_logger.py
│   └── test_integration_helpers.py
└── ...
```

Test framework: **pytest** (per user `~/.claude/rules/testing.md`). Coverage target: **80%+** (per same).

---

## 2. Interface Contracts (concrete signatures)

### 2.1 `feature_store.py`

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class SymbolFeatures:
    symbol: str
    yaobi_score: float
    n_waves_14d: int
    lifecycle: str  # sustained|late_burst|spike_decay|single_burst|quiet
    reaction: str   # mean_revert|trend_continue|mixed|n_a
    historical_fade_winrate: float
    historical_follow_winrate: float
    computed_at_ms: int
    reaction_computed_at_ms: int

class FeatureStore:
    def __init__(self, db_path: str, cache_ttl_sec: int = 300):
        ...
    def get(self, symbol: str) -> Optional[SymbolFeatures]:
        """Returns None if symbol not in store."""
    def staleness_ms(self, symbol: str) -> int:
        """Age of feature record. Use to decide if stale-skip should fire."""
    def all_symbols(self) -> list[str]:
        """For batch operations like daily refresh."""
```

### 2.2 `lifecycle_aware_config.py`

```python
from exit_v2 import ExitConfig

def build_exit_config(lifecycle: str) -> ExitConfig:
    """Pure function. Returns ExitConfig variant based on lifecycle.
    
    sustained, late_burst → wider trail (let runners run)
    spike_decay → tighter trail (lock fast)
    quiet, single_burst, n_a → baseline (default)
    """
```

### 2.3 `rule_engine.py`

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class WaveFeatures:
    duration_min: int
    pre_vol_ratio: float
    magnitude_pct: float

@dataclass(frozen=True)
class Decision:
    action: Literal["ENTER", "SKIP"]
    position_pct: int  # 0 if SKIP, else 3/5/8/12
    direction: Optional[Literal["long", "short"]]  # None if SKIP
    rule_id: Literal["A", "B", "C", "D", "E", "F", "G"]
    reason: str

def apply_rules_l4_tier(
    features: SymbolFeatures,
    wave: WaveFeatures,
    event_side: Literal["pump", "dump"],  # natural side of the event
) -> Decision:
    """Apply 7-rule engine with 4-tier position sizing. Pure function."""
```

### 2.4 `position_sizing.py`

```python
def compute_position_pct(rule_id: str, score: float) -> int:
    """Returns 0 / 3 / 5 / 8 / 12.
    
    Rule A, E, F-skip → 0
    Rule G + score < 50 → 3
    Rule B, F-follow, G default → 5
    Rule C, D + score < 85 → 8
    Rule C, D + score >= 85 → 12
    """
```

### 2.5 `entry_decisions_logger.py`

```python
def log_decision(
    trade_id: str,
    symbol: str,
    ts_ms: int,
    source: Literal["BWE", "MARKET_SCAN"],
    features_json: dict,
    rule_id: Optional[str],  # None for BWE source
    action: str,
    position_pct: int,
    direction: Optional[str],
    exit_config_label: Literal["baseline", "wider", "tighter"],
    reason: str,
    db_path: str = LIVE_DB_PATH,
) -> None:
    """Append to entry_decisions SQLite table. Idempotent on trade_id."""
```

### 2.6 `bwe_market_scan_entry.py` (process boundary)

```python
class MarketScanEngine:
    def __init__(self, config: dict, feature_store: FeatureStore, ...):
        ...
    def run_forever(self) -> None:
        """Main loop — every 60s, scan all symbols, detect events, decide, dispatch."""
    def detect_events(self, since_ms: int) -> list[Event]:
        """Returns ±8% events in 5min window since last poll."""
    def dispatch_trade_request(self, decision: Decision, event: Event) -> None:
        """Writes trade_request row to shared table for live bot to pick up."""
```

**Process model**: `bwe_market_scan_entry.py` runs as **separate process** (started by watchdog like other collectors). It does NOT directly call the live bot's `_open_position`. Instead it writes to a `trade_request` SQLite table that live bot polls.

### 2.7 `integration_helpers.py` (live bot side)

```python
def select_exit_config(symbol: str, config_flags: dict) -> ExitConfig:
    """Live bot calls this in _open_position. Backwards-compat:
    - if exit_engine.use_v2=False: returns sentinel signaling 'use legacy'
    - if exit_engine.use_v2=True + per_lifecycle_config=False: ExitConfig() default
    - if both True: build_exit_config(features.lifecycle) — per-lifecycle variant
    """

def should_use_v2_exit(config_flags: dict) -> bool:
    """Single-line flag check, called early in _handle_position."""

def record_entry_decision(trade: dict, source: str, **kwargs) -> None:
    """Wrapper around entry_decisions_logger.log_decision — non-fatal on failure."""
```

---

## 3. Integration Points

### 3.1 Live bot hook 1: Exit config selection

**Location**: `bwe_live_autotrader.py:_open_position` (around line 1404 per spec v1 reference)

**Change**:
```python
# AFTER existing position dict creation:
if self.config.get("exit_engine", {}).get("use_v2"):
    from bwe_v2.integration_helpers import select_exit_config
    exit_config = select_exit_config(symbol, self.config["exit_engine"])
    pos["v2_exit_config"] = exit_config  # stash on pos for use in _handle_position
```

**Backwards-compat**: When `use_v2=false` (default), this branch is dead code. Live bot behavior unchanged.

### 3.2 Live bot hook 2: Exit engine dispatch

**Location**: `bwe_live_autotrader.py:_handle_position` (the position state machine)

**Change**:
```python
def _handle_position(self, positions, *, symbol, pos, last, hold_min):
    if self.config.get("exit_engine", {}).get("use_v2") and pos.get("v2_exit_config"):
        return self._handle_with_v2_engine(positions, symbol=symbol, pos=pos, last=last, hold_min=hold_min)
    return self._handle_prove_then_hourly_state(positions, symbol=symbol, pos=pos, last=last, hold_min=hold_min)
```

**Backwards-compat**: Default flag false → existing `_handle_prove_then_hourly_state` runs unchanged.

The new `_handle_with_v2_engine` method already has skeleton in `exit_v2/integration_spec.md`.

### 3.3 Live bot hook 3: Decision logging (optional)

**Location**: end of `_open_position` after position created.

**Change**:
```python
if self.config.get("exit_engine", {}).get("log_decisions", False):
    from bwe_v2.integration_helpers import record_entry_decision
    try:
        record_entry_decision(pos, source="BWE", rule_id=None, ...)
    except Exception:
        pass  # non-fatal
```

**Backwards-compat**: Default false → no logging, no behavior change.

### 3.4 Market scan integration (Layer B)

**No live bot code change**. Market scan engine writes to a `trade_request` table:

```sql
CREATE TABLE IF NOT EXISTS trade_request (
  trade_id TEXT PRIMARY KEY,
  source TEXT NOT NULL,         -- "MARKET_SCAN"
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,           -- long/short
  position_pct REAL NOT NULL,
  exit_config_label TEXT NOT NULL,
  features_json TEXT,
  created_ms INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',  -- pending/picked/filled/rejected/expired
  picked_ms INTEGER,
  filled_ms INTEGER
);
```

Live bot adds new poll loop:
```python
# In bot main loop, after BWE channel poll:
if self.config.get("market_scan_engine", {}).get("enabled"):
    self._consume_market_scan_requests()  # new method
```

`_consume_market_scan_requests` reads pending rows, applies same `_open_position` logic with source="MARKET_SCAN".

**Backwards-compat**: Flag false → method never called.

### 3.5 Daily batch via cron

```cron
# 04:00 UTC daily — recompute symbol features
0 4 * * * /Users/ye/.hermes/runtime-venv/bin/python3 /Users/ye/.hermes/scripts/bwe_v2/compute_symbol_features.py --mode=daily >> /Users/ye/.hermes/research/logs/daily_features.log 2>&1

# 04:30 UTC Sunday — refresh reaction labels (rolling 14d)
30 4 * * 0 /Users/ye/.hermes/runtime-venv/bin/python3 /Users/ye/.hermes/scripts/bwe_v2/compute_symbol_features.py --mode=reaction-only >> /Users/ye/.hermes/research/logs/weekly_reaction.log 2>&1
```

**Backwards-compat**: New cron entries do not touch existing watchdog crontab.

### 3.6 Watchdog extension (minimal)

`collectors_watchdog.sh` extended with one new section:

```bash
# Optional: market scan engine (only if config flag set)
if [ -f /Users/ye/.hermes/state/market_scan_enabled.flag ]; then
    restart_if_dead_or_stale \
        "market_scan_engine" \
        "bwe_market_scan_entry.py" \
        "trade_request" \
        "created_ms" \
        "$STALE_TICKER_MS" \
        ""
fi
```

**Backwards-compat**: No flag file → no market_scan_engine action. Existing 3 collectors continue unchanged.

---

## 4. Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│  COLLECTORS (existing, untouched)                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐    │
│  │ 1m_collector     │  │ metric_collector │  │ 24h_ticker_collector │    │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────┬───────────┘    │
│           ↓                      ↓                       ↓                │
│         ┌────────────────────────────────────────────────┐               │
│         │ binance_futures_1m.sqlite3 (LIVE, hot)         │               │
│         │  ├ klines_1m, mark, oi_5m, ls_5m, taker_5m,    │               │
│         │  │  basis_5m, ticker_24h                       │               │
│         │  └ NEW (added by spec v2):                     │               │
│         │     symbol_features, entry_decisions,           │               │
│         │     trade_request                              │               │
│         └────────────────────────────────────────────────┘               │
└──────────────────────────────────────────────────────────────────────────┘
                                ↓ (read-only)
┌──────────────────────────────────────────────────────────────────────────┐
│  DAILY BATCH (cron 04:00 UTC) — compute_symbol_features.py                │
│  ┌──────────────────────────────────────────────────────┐                │
│  │ Reads: 30d klines from extended_history.sqlite3      │                │
│  │      + last 5d klines from live DB                   │                │
│  │ Computes: yaobi_score, lifecycle, n_waves_14d        │                │
│  │ Writes: symbol_features table (live DB)              │                │
│  └──────────────────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────────┘
                                ↓
┌────────────────────────────────────┐    ┌─────────────────────────────────┐
│  ENTRY SOURCE A: BWE Telegram       │    │  ENTRY SOURCE B: Market scan    │
│  (existing)                          │    │  (new, separate process)        │
│  ┌────────────────────────────────┐ │    │ ┌────────────────────────────┐ │
│  │ bwe_live_autotrader.py         │ │    │ │ bwe_market_scan_entry.py   │ │
│  │ - reads BWE channel            │ │    │ │ - polls live DB every 60s  │ │
│  │ - decides direction            │ │    │ │ - detects ±8% events       │ │
│  │ - calls _open_position         │ │    │ │ - calls apply_rules_l4_tier│ │
│  │   (with v2 exit config flag)   │ │    │ │ - writes to trade_request  │ │
│  └────────────────────────────────┘ │    │ └────────────────────────────┘ │
└─────────────┬──────────────────────┘    └──────────┬──────────────────────┘
              ↓                                       ↓
              ↓                            (live bot polls trade_request)
              ↓                                       ↓
┌──────────────────────────────────────────────────────────────────────────┐
│  EXIT LAYER (existing exit_v2 module, used by bot)                        │
│  ┌──────────────────────────────────────────────────────┐                │
│  │ exit_v2/exit_v2.py                                   │                │
│  │ - ExitEngine.decide(pos, bars) → ExitDecision        │                │
│  │ - Dynamic trail + ATR-aware stop + G2 + volume conf  │                │
│  │ - Per-lifecycle config selected by integration_helper│                │
│  └──────────────────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────────┘
                                ↓
                       ┌─────────────────┐
                       │  trade_journal  │
                       │  (existing)      │
                       └─────────────────┘
```

---

## 5. Backwards-Compat Surface

### 5.1 Config flags (in `bwe_live_autotrader_binance_expectancy_live.json`)

```json
{
  "exit_engine": {
    "use_v2": false,                 // master switch for v2 exit
    "per_lifecycle_config": false,   // sub-flag, only effective if use_v2=true
    "log_decisions": false           // optional audit trail
  },
  "market_scan_engine": {
    "enabled": false,                // master switch for Layer B
    "event_threshold_pct": 8.0,
    "max_concurrent_trades": 3,
    "min_score_to_consider": 30      // skip "quiet" symbols
  }
}
```

### 5.2 Default behavior preservation matrix

| All flags FALSE | bot behavior |
|---|---|
| `exit_engine.use_v2 = false` | `_handle_position` calls `_handle_prove_then_hourly_state` (existing) — exit_v2 module never imported by live bot |
| `exit_engine.per_lifecycle_config = false` | Even if use_v2=true, falls back to `ExitConfig()` default |
| `exit_engine.log_decisions = false` | No decision rows written, no SQLite write contention |
| `market_scan_engine.enabled = false` | No new process started by watchdog, no `trade_request` polling |

**Test obligation (REQ-N from pack validator)**: Add explicit regression test that runs the bot with all flags false on a snapshot and verifies behavior identical to pre-v2 bot.

### 5.3 Schema additions (no DROP/ALTER on existing tables)

```sql
-- Live DB additions (binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3)
CREATE TABLE IF NOT EXISTS symbol_features (
  symbol TEXT PRIMARY KEY,
  yaobi_score REAL NOT NULL,
  n_waves_14d INTEGER NOT NULL,
  lifecycle TEXT NOT NULL,
  reaction TEXT NOT NULL,
  historical_fade_winrate REAL,
  historical_follow_winrate REAL,
  computed_at_ms INTEGER NOT NULL,
  reaction_computed_at_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sf_lifecycle ON symbol_features(lifecycle);
CREATE INDEX IF NOT EXISTS idx_sf_score ON symbol_features(yaobi_score);

CREATE TABLE IF NOT EXISTS entry_decisions (
  trade_id TEXT PRIMARY KEY,
  symbol TEXT NOT NULL, ts_ms INTEGER NOT NULL,
  source TEXT NOT NULL,
  features_json TEXT,
  rule_id TEXT,
  action TEXT NOT NULL,
  position_pct REAL NOT NULL,
  direction TEXT,
  exit_config_label TEXT,
  reason TEXT
);

CREATE TABLE IF NOT EXISTS trade_request (
  trade_id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  position_pct REAL NOT NULL,
  exit_config_label TEXT NOT NULL,
  features_json TEXT,
  created_ms INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  picked_ms INTEGER, filled_ms INTEGER
);
```

All `CREATE TABLE IF NOT EXISTS` — idempotent and additive only. No `ALTER` or `DROP`.

---

## 6. Architectural Risks (with delta over Auditor B1-B5)

### 6.1 Already covered by Auditor (acknowledged + mitigation noted)

- **B1 robustness of L2-per-lifecycle**: Auditor covers. Architect adds → expose `EXIT_CONFIG_OVERRIDE` env var so we can quickly revert to L2-base by setting `EXIT_CONFIG_OVERRIDE=baseline` without redeploy.

- **B2 position concentration**: Add `max_total_capital_pct=25` config + `max_per_tier_concurrent={12: 1, 8: 2, 5: 3}` enforcement in `_open_position`. Reject new entries if cap exceeded.

- **B3 fee/slippage realism**: Architect adds → in `regression_check.py`, apply 5+5 bps round-trip overhead before comparing to baseline. Refresh `archive/04_phase4_optimization.md` baseline column with after-fee numbers.

- **B4 phase gate softness**: Auditor covers. Architect concur, no extra surface.

- **B5 regression detector missing**: Architect ships `bwe_v2/regression_check.py` per spec.

### 6.2 New architectural risks NOT in auditor

| ID | Risk | Severity | Mitigation | Detection |
|---|---|---|---|---|
| AR-1 | **SQLite write contention**: 3 collectors + daily batch + market scan + bot all writing same DB. WAL mode helps but stale-read is possible. | Med | All readers use `PRAGMA query_only=1` and reopen connection per cycle. Writers use 60s busy_timeout. Daily batch uses **separate Python connection** with WAL. | Watchdog adds `SELECT 1` health probe; alert if > 30s lock |
| AR-2 | **Process boundary**: market_scan as separate process means trade_request polling latency (60s). A pump→short event might miss optimal entry by ~1 min. | Low | Acceptable for paper validation. Phase 5 may move to in-process if data shows alpha loss. | Compare market_scan-detected entry timestamp to trade fill timestamp; alert if avg > 90s |
| AR-3 | **Stale lifecycle on intraday spike**: Lifecycle computed at 04:00 UTC; if a coin starts a spike at 06:00 UTC, its lifecycle label is 22h stale. | Med | `feature_store.staleness_ms()` exposed to caller. Live bot logs staleness to decision_log. Phase 4 review: if stale > X% trades hit catastrophe, downgrade to hourly refresh. | Decision log analytics — group by staleness bucket, watch catastrophe rate |
| AR-4 | **Feature store cache TTL**: 5min in-memory cache means feature update at 04:00 visible in bot at 04:05 latest. Acceptable. | Low | Document in spec. | n/a |
| AR-5 | **trade_request orphans**: market_scan writes pending; if bot crashes, rows stuck. | Low | TTL on pending rows: cleanup if status='pending' AND created_ms > now-300s. | Daily count of orphans in monitoring |
| AR-6 | **exit_v2 module version drift**: spec assumes exit_v2 module is "production". If we update it, integration_helpers may break. | Med | Pin `from exit_v2 import ExitConfig, ExitEngine` to specific commit. Add unit test asserting `ExitConfig().__dict__` keys haven't changed. | CI on spec-required keys |

---

## 7. Spec Section 10 Open Questions Resolved

| Q | Spec phrasing | Architect resolution |
|---|---|---|
| Q1 | Lifecycle 标签每天还是每周? | **Daily for lifecycle, weekly for reaction** (matches spec §5.3). Downgrade trigger: if Phase 4 paper shows > 5% catastrophe rate caused by stale lifecycle, switch lifecycle to hourly. |
| Q2 | Market scan 加 long-short / OI / funding 维度? | **Defer to v3** (after Phase 5 lock-in baselines hold). Current 4 维 yaobi_score validated on 1407 waves; adding dims is optimization not blocker. |
| Q3 | 新 entry signal source (e.g., 量价分歧)? | **Out of scope for v2**. Spec §11 explicitly. Revisit only after Layer A + B both stable in live. |
| Q4 | 跨交易所 (OKX) 信号? | **Out of scope**. OKX requires separate collector + API integration; not core alpha. |
| Q5 | LLM 辅助决策? | **Out of scope per NG4**. Latency unacceptable for ±8% spike entries. |

---

## 8. Protected Zones (DO NOT MODIFY during implementation)

| Path | Why protected | Allowed change |
|---|---|---|
| `/Users/ye/.hermes/scripts/bwe_live_autotrader.py` | 92KB live trading bot, 24/7 hot | Only via 3 documented hooks (§3.1, 3.2, 3.3 of this report). Each hook is a config-flag-gated single function call. |
| `/Users/ye/.hermes/scripts/binance_futures_1m_collector.py` | Live collector, sub-1min data | None — read schema only |
| `/Users/ye/.hermes/scripts/binance_futures_metric_collector.py` | Live collector | None — read schema only |
| `/Users/ye/.hermes/scripts/binance_24h_ticker_collector.py` | New but already deployed | None — read only |
| `/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3` | Live DB, hot writes | `CREATE TABLE IF NOT EXISTS` only. **No ALTER, no DROP, no UPDATE on existing tables**. |
| `/Users/ye/.hermes/research/binance_extended_history.sqlite3` | 30d backfill, 3.3GB | Read-only by new code |
| `/Users/ye/.hermes/scripts/collectors_watchdog.sh` | Cron-managed, sub-minute health | Append market_scan section only behind flag file. Do not change existing 3 daemon checks. |
| `/Volumes/T9/BWE/40_EXPERIMENTS/round4/exit_v2/exit_v2.py` | Production exit module, used by backtest | Treat as library. Pin import. No modifications without bumping `EXIT_V2_VERSION`. |
| Crontab user `ye` | Existing entries managed by other systems | New entries only, no modifications to existing |

---

## 9. Architectural Decisions Summary (for ADR)

1. **New code in `bwe_v2/` directory** — physical separation from production scripts.
2. **Module decomposition by single-responsibility** — feature compute / store / config / rules / sizing / scan / logger separate.
3. **All public functions are pure where possible** — testable, no hidden state.
4. **Process boundary: market_scan = separate process** — fault isolation, watchdog-managed.
5. **IPC via SQLite trade_request table** — same pattern as existing live bot infra.
6. **Feature store has 5-min TTL cache** — live bot doesn't pay DB hit per trade.
7. **Schema additions only, no breaking changes** — backwards-compat absolute.
8. **All v2 features behind 4 config flags** (use_v2, per_lifecycle_config, log_decisions, market_scan_engine.enabled).
9. **Cron for daily/weekly batch** — same operational pattern as existing collectors.
10. **Test framework: pytest with conftest fixtures** — per user's `~/.claude/rules/testing.md`.

---

## 10. Architect Sign-off

All 5 auditor blockers (B1-B5) have known mitigation paths. Module decomposition is complete with concrete signatures. Backwards-compat surface is fully documented (all 4 flags + schema additions only). Protected zones are explicit. Open questions resolved or deferred with rationale.

**Architect sign-off: ARCHITECTURE READY FOR PLAN**
