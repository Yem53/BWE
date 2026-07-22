---
type: plan
tags: [scanner, infrastructure, bwe-replica, data-collection, round9, tdd]
created: 2026-05-22
status: ready
priority: high
---

# Self-Hosted BWE Scanner — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone EC2 service that replicates + surpasses BWE — real-time multi-window price/OI anomaly detection across all Binance USDT-M perps → fire alerts → archive as structured JSONL (research corpus) + push a high-signal subset to Telegram.

**Architecture:** One isolated Python process. A Binance `!markPrice@arr@1s` websocket feeds per-symbol rolling price buffers; an OI poller + a 24h-ticker + market-cap cache supply context. Pure detector functions turn buffers into `Detection`s (multi-window thresholds + cooldown); each is enriched into an `Alert`, appended to a daily JSONL, and (if high-signal) pushed to Telegram. Zero changes to the live trading bot.

**Tech Stack:** Python 3.10 (stdlib + `requests` + `websocket-client`), pytest, systemd. Spec: `../specs/2026-05-22-self-bwe-scanner-design.md`.

**Layout (flat modules, same-dir imports — dev on Mac, deploy to EC2):**

| File | Responsibility |
|---|---|
| `detectors.py` | PURE: `Detection`/`Alert` dataclasses, window Δ math, cooldown, OI logic, alert assembly |
| `store.py` | append `Alert` dict → daily JSONL |
| `notify.py` | push-filter predicate (pure) + Telegram format/send |
| `enrich.py` | `Ticker24hCache` (Binance 24h) + `MarketCapCache` (CoinGecko supply) |
| `ws_feed.py` | `parse_markprice_array` (pure) + `PriceBuffers` + `WSFeed` + `OIPoller` |
| `scanner.py` | main loop: wire feed→detect→enrich→store+notify; config; heartbeat; `--dry-run` |
| `config.json` | windows, thresholds, cooldowns, push filter, paths, telegram |
| `tests/` | pytest unit tests; `conftest.py` puts package dir on `sys.path` |

**Dev path:** `/Volumes/T9/BWE/infrastructure/collectors/bwe_scanner/`
**Deploy path (EC2):** `/home/ubuntu/bwe-scanner/` (flat modules + `config.json` + `data/` + `logs/`)
**Run tests:** `cd <dev path> && python3 -m pytest tests/ -v`

> **Geo note:** the Mac is US-geo-blocked from Binance. All unit tests are pure/mocked (run on Mac). Live websocket + Binance/CoinGecko calls are validated only in the EC2 smoke test (Task 14).

---

### Task 0: Scaffold package + config + pytest

**Files:**
- Create: `infrastructure/collectors/bwe_scanner/__init__.py` (empty)
- Create: `infrastructure/collectors/bwe_scanner/config.json`
- Create: `infrastructure/collectors/bwe_scanner/conftest.py`
- Create: `infrastructure/collectors/bwe_scanner/tests/__init__.py` (empty)

- [ ] **Step 1: Create the directory + empty files**

```bash
cd /Volumes/T9/BWE/infrastructure/collectors
mkdir -p bwe_scanner/tests
touch bwe_scanner/__init__.py bwe_scanner/tests/__init__.py
```

- [ ] **Step 2: Write `config.json`**

```json
{
  "windows": {
    "price_3s":  {"sec": 3,   "thr_pct": 2.0},
    "price_5s":  {"sec": 5,   "thr_pct": 3.0},
    "price_10s": {"sec": 10,  "thr_pct": 3.0},
    "price_30s": {"sec": 30,  "thr_pct": 4.0},
    "price_60s": {"sec": 60,  "thr_pct": 5.0},
    "price_90s": {"sec": 90,  "thr_pct": 5.0},
    "price_180s_extreme": {"sec": 180, "thr_pct": 8.0}
  },
  "oi_price_1h": {"sec": 3600, "price_thr_pct": 5.0, "oi_thr_pct": 5.0},
  "store_cooldown_sec": 600,
  "push_cooldown_sec": 600,
  "push_filter": {
    "types": ["price_180s_extreme", "oi_price_1h"],
    "short_window_types": ["price_60s", "price_90s"],
    "short_window_min_pct": 8.0
  },
  "exclude_mainstream": false,
  "oi_poll_sec": 300,
  "ticker24h_poll_sec": 60,
  "supply_refresh_sec": 86400,
  "ws_url": "wss://fstream.binance.com/ws/!markPrice@arr@1s",
  "fapi_base": "https://fapi.binance.com",
  "paths": {"jsonl_dir": "/home/ubuntu/bwe-scanner/data", "cg_map": "symbol_cg_map.json"},
  "telegram": {"enabled": true, "chat_id_env": "BWE_SCANNER_TELEGRAM_CHAT_ID", "token_env": "BWE_LIVE_TELEGRAM_BOT_TOKEN"}
}
```

- [ ] **Step 3: Write `conftest.py` so tests can import the flat modules**

```python
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
```

- [ ] **Step 4: Verify pytest collects (no tests yet → exit 5 is fine)**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/ -v`
Expected: `no tests ran` (exit code 5). Confirms layout + conftest load.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/T9/BWE
git add infrastructure/collectors/bwe_scanner/
git commit -m "feat(scanner): scaffold bwe_scanner package + config + pytest"
```

---

### Task 1: `pct_change_over_window` (pure window math)

**Files:**
- Create: `infrastructure/collectors/bwe_scanner/detectors.py`
- Create: `infrastructure/collectors/bwe_scanner/tests/test_detectors.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_detectors.py
from detectors import pct_change_over_window


def test_pct_change_basic_rise():
    # samples ascending: (ts_ms, price). now=10_000ms, window=3s → compare vs price at/just before 7_000ms
    samples = [(4000, 100.0), (7000, 100.0), (8000, 105.0), (10000, 110.0)]
    # past price = last sample with ts <= 7000 → 100.0 ; now = 110.0 → +10%
    assert pct_change_over_window(samples, now_ms=10000, window_sec=3) == 10.0


def test_pct_change_negative():
    samples = [(0, 200.0), (5000, 180.0)]
    # window 5s: past = sample <= 0 → 200 ; now 180 → -10%
    assert pct_change_over_window(samples, now_ms=5000, window_sec=5) == -10.0


def test_pct_change_insufficient_history_returns_none():
    samples = [(9000, 100.0), (10000, 101.0)]
    # window 3s needs a sample <= 7000; none exists
    assert pct_change_over_window(samples, now_ms=10000, window_sec=3) is None


def test_pct_change_empty_returns_none():
    assert pct_change_over_window([], now_ms=10000, window_sec=3) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_detectors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'detectors'` / `ImportError`.

- [ ] **Step 3: Write minimal implementation**

```python
# detectors.py
from __future__ import annotations


def pct_change_over_window(
    samples: list[tuple[int, float]], now_ms: int, window_sec: int
) -> float | None:
    """Percent change of the latest price vs the price at/just before (now - window).

    `samples` is ascending by ts_ms: [(ts_ms, price), ...]. Returns None if there is
    no sample old enough to anchor the window (insufficient history) or no samples.
    """
    if not samples:
        return None
    cutoff = now_ms - window_sec * 1000
    past_price = None
    for ts, price in samples:
        if ts <= cutoff:
            past_price = price
        else:
            break
    if past_price is None or past_price == 0:
        return None
    now_price = samples[-1][1]
    return (now_price / past_price - 1.0) * 100.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_detectors.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/T9/BWE
git add infrastructure/collectors/bwe_scanner/detectors.py infrastructure/collectors/bwe_scanner/tests/test_detectors.py
git commit -m "feat(scanner): pure pct_change_over_window window math"
```

---

### Task 2: `Detection` dataclass + `detect_price_ladder`

**Files:**
- Modify: `infrastructure/collectors/bwe_scanner/detectors.py`
- Modify: `infrastructure/collectors/bwe_scanner/tests/test_detectors.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_detectors.py
from detectors import Detection, detect_price_ladder


def test_detect_price_ladder_fires_windows_over_threshold():
    # price doubled recently; windows: 60s thr 5%, 180s thr 8%
    samples = [(0, 100.0), (60_000, 100.0), (120_000, 100.0), (180_000, 112.0)]
    windows = {"price_60s": {"sec": 60, "thr_pct": 5.0},
               "price_180s_extreme": {"sec": 180, "thr_pct": 8.0}}
    dets = detect_price_ladder("ABCUSDT", samples, now_ms=180_000, windows=windows)
    by_type = {d.window_type: d for d in dets}
    # 60s: vs price at 120_000 (100) → +12% ≥5% fires; 180s: vs price at 0 (100) → +12% ≥8% fires
    assert set(by_type) == {"price_60s", "price_180s_extreme"}
    assert by_type["price_60s"].price_chg_pct == 12.0
    assert by_type["price_60s"].price == 112.0
    assert by_type["price_60s"].symbol == "ABCUSDT"
    assert by_type["price_180s_extreme"].window_sec == 180


def test_detect_price_ladder_below_threshold_no_fire():
    samples = [(0, 100.0), (180_000, 103.0)]  # +3%
    windows = {"price_180s_extreme": {"sec": 180, "thr_pct": 8.0}}
    assert detect_price_ladder("ABCUSDT", samples, now_ms=180_000, windows=windows) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_detectors.py -k price_ladder -v`
Expected: FAIL — `ImportError: cannot import name 'Detection'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to detectors.py
from dataclasses import dataclass


@dataclass(frozen=True)
class Detection:
    ts_ms: int
    symbol: str
    window_type: str
    window_sec: int
    price_chg_pct: float
    price: float
    oi_chg_pct: float | None = None
    oi_usd: float | None = None


def detect_price_ladder(
    symbol: str,
    samples: list[tuple[int, float]],
    now_ms: int,
    windows: dict[str, dict],
) -> list[Detection]:
    """Fire a Detection for each price window whose |Δ%| >= its threshold."""
    out: list[Detection] = []
    if not samples:
        return out
    price_now = samples[-1][1]
    for wtype, cfg in windows.items():
        chg = pct_change_over_window(samples, now_ms, cfg["sec"])
        if chg is None:
            continue
        if abs(chg) >= cfg["thr_pct"]:
            out.append(Detection(ts_ms=now_ms, symbol=symbol, window_type=wtype,
                                 window_sec=cfg["sec"], price_chg_pct=round(chg, 4),
                                 price=price_now))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_detectors.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/T9/BWE
git add infrastructure/collectors/bwe_scanner/detectors.py infrastructure/collectors/bwe_scanner/tests/test_detectors.py
git commit -m "feat(scanner): Detection dataclass + multi-window price ladder detector"
```

---

### Task 3: `apply_cooldown` (pure cooldown gate)

**Files:**
- Modify: `infrastructure/collectors/bwe_scanner/detectors.py`
- Modify: `infrastructure/collectors/bwe_scanner/tests/test_detectors.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_detectors.py
from detectors import apply_cooldown


def _det(sym, wtype, ts):
    return Detection(ts_ms=ts, symbol=sym, window_type=wtype, window_sec=60,
                     price_chg_pct=6.0, price=1.0)


def test_apply_cooldown_first_fire_passes_and_records():
    last_fired = {}
    dets = [_det("A", "price_60s", 1000)]
    kept = apply_cooldown(dets, last_fired, cooldown_sec=600, now_ms=1000)
    assert len(kept) == 1
    assert last_fired[("A", "price_60s")] == 1000


def test_apply_cooldown_suppresses_within_window():
    last_fired = {("A", "price_60s"): 1000}
    dets = [_det("A", "price_60s", 300_000)]  # 299s later < 600s
    kept = apply_cooldown(dets, last_fired, cooldown_sec=600, now_ms=300_000)
    assert kept == []
    assert last_fired[("A", "price_60s")] == 1000  # unchanged


def test_apply_cooldown_passes_after_window():
    last_fired = {("A", "price_60s"): 1000}
    dets = [_det("A", "price_60s", 601_001)]  # >600s later
    kept = apply_cooldown(dets, last_fired, cooldown_sec=600, now_ms=601_001)
    assert len(kept) == 1
    assert last_fired[("A", "price_60s")] == 601_001
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_detectors.py -k cooldown -v`
Expected: FAIL — `ImportError: cannot import name 'apply_cooldown'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to detectors.py
def apply_cooldown(
    detections: list[Detection],
    last_fired: dict[tuple[str, str], int],
    cooldown_sec: int,
    now_ms: int,
) -> list[Detection]:
    """Drop detections whose (symbol, window_type) fired within cooldown. Mutates
    last_fired for kept detections."""
    kept: list[Detection] = []
    for d in detections:
        key = (d.symbol, d.window_type)
        prev = last_fired.get(key)
        if prev is not None and (now_ms - prev) < cooldown_sec * 1000:
            continue
        last_fired[key] = now_ms
        kept.append(d)
    return kept
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_detectors.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/T9/BWE
git add infrastructure/collectors/bwe_scanner/detectors.py infrastructure/collectors/bwe_scanner/tests/test_detectors.py
git commit -m "feat(scanner): per-(symbol,window) cooldown gate"
```

---

### Task 4: `detect_oi_price_1h` (1h price-OR-OI detector)

**Files:**
- Modify: `infrastructure/collectors/bwe_scanner/detectors.py`
- Modify: `infrastructure/collectors/bwe_scanner/tests/test_detectors.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_detectors.py
from detectors import detect_oi_price_1h


def test_oi_price_1h_fires_on_price_only():
    samples = [(0, 100.0), (3_600_000, 106.0)]  # +6% over 1h
    d = detect_oi_price_1h("ABCUSDT", samples, oi_chg_pct=1.0, oi_usd=5e6,
                           now_ms=3_600_000, price_thr=5.0, oi_thr=5.0)
    assert d is not None
    assert d.window_type == "oi_price_1h"
    assert d.price_chg_pct == 6.0
    assert d.oi_chg_pct == 1.0
    assert d.oi_usd == 5e6


def test_oi_price_1h_fires_on_oi_only():
    samples = [(0, 100.0), (3_600_000, 101.0)]  # +1% price (below thr)
    d = detect_oi_price_1h("ABCUSDT", samples, oi_chg_pct=12.0, oi_usd=5e6,
                           now_ms=3_600_000, price_thr=5.0, oi_thr=5.0)
    assert d is not None and d.oi_chg_pct == 12.0


def test_oi_price_1h_no_fire_when_both_below():
    samples = [(0, 100.0), (3_600_000, 102.0)]
    d = detect_oi_price_1h("ABCUSDT", samples, oi_chg_pct=2.0, oi_usd=5e6,
                           now_ms=3_600_000, price_thr=5.0, oi_thr=5.0)
    assert d is None


def test_oi_price_1h_handles_missing_oi():
    samples = [(0, 100.0), (3_600_000, 107.0)]  # price alone fires
    d = detect_oi_price_1h("ABCUSDT", samples, oi_chg_pct=None, oi_usd=None,
                           now_ms=3_600_000, price_thr=5.0, oi_thr=5.0)
    assert d is not None and d.oi_chg_pct is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_detectors.py -k oi_price -v`
Expected: FAIL — `ImportError: cannot import name 'detect_oi_price_1h'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to detectors.py
def detect_oi_price_1h(
    symbol: str,
    price_samples: list[tuple[int, float]],
    oi_chg_pct: float | None,
    oi_usd: float | None,
    now_ms: int,
    price_thr: float,
    oi_thr: float,
) -> Detection | None:
    """Fire if |1h price Δ| >= price_thr OR |1h OI Δ| >= oi_thr."""
    price_chg = pct_change_over_window(price_samples, now_ms, 3600)
    price_hit = price_chg is not None and abs(price_chg) >= price_thr
    oi_hit = oi_chg_pct is not None and abs(oi_chg_pct) >= oi_thr
    if not (price_hit or oi_hit):
        return None
    return Detection(
        ts_ms=now_ms, symbol=symbol, window_type="oi_price_1h", window_sec=3600,
        price_chg_pct=round(price_chg, 4) if price_chg is not None else 0.0,
        price=price_samples[-1][1] if price_samples else 0.0,
        oi_chg_pct=round(oi_chg_pct, 4) if oi_chg_pct is not None else None,
        oi_usd=oi_usd,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_detectors.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/T9/BWE
git add infrastructure/collectors/bwe_scanner/detectors.py infrastructure/collectors/bwe_scanner/tests/test_detectors.py
git commit -m "feat(scanner): 1h price-OR-OI detector"
```

---

### Task 5: `Alert` + `to_alert` + `alert_to_dict` (enriched record)

**Files:**
- Modify: `infrastructure/collectors/bwe_scanner/detectors.py`
- Modify: `infrastructure/collectors/bwe_scanner/tests/test_detectors.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_detectors.py
from detectors import Alert, to_alert, alert_to_dict


def test_to_alert_merges_context_and_marketcap():
    det = Detection(ts_ms=1_700_000_000_000, symbol="ABCUSDT", window_type="price_60s",
                    window_sec=60, price_chg_pct=6.2, price=0.5, oi_usd=4.9e6)
    ctx = {"chg_24h_pct": 15.0, "quote_vol_24h": 1_234_567.0}
    a = to_alert(det, ctx, market_cap_usd=8_000_000.0)
    assert isinstance(a, Alert)
    assert a.symbol == "ABCUSDT"
    assert a.chg_24h_pct == 15.0
    assert a.market_cap_usd == 8_000_000.0
    # oi_mc_ratio = oi_usd / market_cap * 100
    assert round(a.oi_mc_ratio_pct, 1) == round(4.9e6 / 8e6 * 100, 1)
    assert a.fired_at.endswith("Z")


def test_to_alert_null_marketcap_keeps_ratio_none():
    det = Detection(ts_ms=1_700_000_000_000, symbol="ABCUSDT", window_type="price_3s",
                    window_sec=3, price_chg_pct=2.5, price=0.5)
    a = to_alert(det, {"chg_24h_pct": None, "quote_vol_24h": None}, market_cap_usd=None)
    assert a.market_cap_usd is None and a.oi_mc_ratio_pct is None


def test_alert_to_dict_is_json_round_trippable():
    import json
    det = Detection(ts_ms=1, symbol="ABCUSDT", window_type="price_3s", window_sec=3,
                    price_chg_pct=2.5, price=0.5)
    a = to_alert(det, {"chg_24h_pct": None, "quote_vol_24h": None}, market_cap_usd=None)
    d = alert_to_dict(a)
    assert json.loads(json.dumps(d))["symbol"] == "ABCUSDT"
    assert set(d) >= {"ts_ms", "symbol", "window_type", "price_chg_pct", "fired_at"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_detectors.py -k alert -v`
Expected: FAIL — `ImportError: cannot import name 'Alert'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to detectors.py
from dataclasses import asdict
from datetime import datetime, timezone


@dataclass(frozen=True)
class Alert:
    ts_ms: int
    symbol: str
    window_type: str
    window_sec: int
    price_chg_pct: float
    oi_chg_pct: float | None
    price: float
    chg_24h_pct: float | None
    quote_vol_24h: float | None
    oi_usd: float | None
    market_cap_usd: float | None
    oi_mc_ratio_pct: float | None
    fired_at: str


def to_alert(det: Detection, ctx: dict, market_cap_usd: float | None) -> Alert:
    """Combine a Detection with 24h context + market cap into a storable Alert."""
    oi_mc = None
    if market_cap_usd and det.oi_usd:
        oi_mc = round(det.oi_usd / market_cap_usd * 100.0, 4)
    return Alert(
        ts_ms=det.ts_ms, symbol=det.symbol, window_type=det.window_type,
        window_sec=det.window_sec, price_chg_pct=det.price_chg_pct,
        oi_chg_pct=det.oi_chg_pct, price=det.price,
        chg_24h_pct=ctx.get("chg_24h_pct"), quote_vol_24h=ctx.get("quote_vol_24h"),
        oi_usd=det.oi_usd, market_cap_usd=market_cap_usd, oi_mc_ratio_pct=oi_mc,
        fired_at=datetime.fromtimestamp(det.ts_ms / 1000, timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def alert_to_dict(alert: Alert) -> dict:
    return asdict(alert)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_detectors.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/T9/BWE
git add infrastructure/collectors/bwe_scanner/detectors.py infrastructure/collectors/bwe_scanner/tests/test_detectors.py
git commit -m "feat(scanner): Alert record + enrichment assembly (incl. OI/MC ratio)"
```

---

### Task 6: `store.py` — daily JSONL append (+ live-bot parse compat)

**Files:**
- Create: `infrastructure/collectors/bwe_scanner/store.py`
- Create: `infrastructure/collectors/bwe_scanner/tests/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_store.py
import json
from store import append_alert


def test_append_alert_writes_daily_file(tmp_path):
    alert = {"ts_ms": 1_700_000_000_000, "symbol": "ABCUSDT", "window_type": "price_60s",
             "price_chg_pct": 6.2, "fired_at": "2023-11-14T22:13:20Z"}
    path = append_alert(str(tmp_path), alert, now_ms=1_700_000_000_000)
    assert path.exists()
    assert "alerts_2023-11-14.jsonl" in path.name
    line = json.loads(path.read_text().strip())
    assert line["symbol"] == "ABCUSDT"


def test_append_alert_appends_multiple_lines(tmp_path):
    for i in range(3):
        append_alert(str(tmp_path), {"symbol": f"S{i}USDT"}, now_ms=1_700_000_000_000)
    f = list(tmp_path.glob("alerts_*.jsonl"))[0]
    assert len(f.read_text().strip().splitlines()) == 3


def test_emitted_line_is_parseable_by_live_bot_loader(tmp_path):
    # The live bot's load_recent_bwe_symbols reads d.get("symbol") + d.get("ts_ms").
    # Assert our line carries both so the (optional, future) bot feed works.
    alert = {"ts_ms": 1_700_000_000_000, "symbol": "ABCUSDT", "window_type": "price_60s"}
    path = append_alert(str(tmp_path), alert, now_ms=1_700_000_000_000)
    d = json.loads(path.read_text().strip())
    assert d.get("symbol", "").endswith("USDT") and int(d.get("ts_ms", 0)) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'store'`.

- [ ] **Step 3: Write minimal implementation**

```python
# store.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def append_alert(jsonl_dir: str, alert: dict, now_ms: int) -> Path:
    """Append one alert as a JSON line to alerts_YYYY-MM-DD.jsonl (UTC date)."""
    day = datetime.fromtimestamp(now_ms / 1000, timezone.utc).strftime("%Y-%m-%d")
    d = Path(jsonl_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"alerts_{day}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(alert, ensure_ascii=False) + "\n")
    return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_store.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/T9/BWE
git add infrastructure/collectors/bwe_scanner/store.py infrastructure/collectors/bwe_scanner/tests/test_store.py
git commit -m "feat(scanner): daily JSONL alert store (bot-loader compatible)"
```

---

### Task 7: `notify.py` — push-filter predicate (pure)

**Files:**
- Create: `infrastructure/collectors/bwe_scanner/notify.py`
- Create: `infrastructure/collectors/bwe_scanner/tests/test_notify.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_notify.py
from notify import should_push

FILTER = {"types": ["price_180s_extreme", "oi_price_1h"],
          "short_window_types": ["price_60s", "price_90s"], "short_window_min_pct": 8.0}


def test_push_extreme_type_always():
    assert should_push({"window_type": "price_180s_extreme", "price_chg_pct": 8.1}, FILTER)
    assert should_push({"window_type": "oi_price_1h", "price_chg_pct": 1.0}, FILTER)


def test_push_short_window_only_if_big():
    assert should_push({"window_type": "price_60s", "price_chg_pct": 9.0}, FILTER)
    assert should_push({"window_type": "price_60s", "price_chg_pct": -8.5}, FILTER)
    assert not should_push({"window_type": "price_60s", "price_chg_pct": 6.0}, FILTER)


def test_no_push_for_micro_windows():
    assert not should_push({"window_type": "price_3s", "price_chg_pct": 4.0}, FILTER)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_notify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'notify'`.

- [ ] **Step 3: Write minimal implementation**

```python
# notify.py
from __future__ import annotations


def should_push(alert: dict, push_filter: dict) -> bool:
    """High-signal subset: always-push types, plus short windows only when |Δ| is big."""
    wtype = alert.get("window_type", "")
    if wtype in push_filter.get("types", []):
        return True
    if wtype in push_filter.get("short_window_types", []):
        return abs(alert.get("price_chg_pct", 0.0)) >= push_filter.get("short_window_min_pct", 1e9)
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_notify.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/T9/BWE
git add infrastructure/collectors/bwe_scanner/notify.py infrastructure/collectors/bwe_scanner/tests/test_notify.py
git commit -m "feat(scanner): high-signal Telegram push-filter predicate"
```

---

### Task 8: `notify.py` — format message + Telegram send (mocked)

**Files:**
- Modify: `infrastructure/collectors/bwe_scanner/notify.py`
- Modify: `infrastructure/collectors/bwe_scanner/tests/test_notify.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_notify.py
from unittest.mock import patch
from notify import format_alert_msg, send_telegram


def test_format_alert_msg_contains_key_fields():
    msg = format_alert_msg({"symbol": "ABCUSDT", "window_type": "price_180s_extreme",
                            "window_sec": 180, "price_chg_pct": 8.4, "chg_24h_pct": 15.0,
                            "quote_vol_24h": 1_200_000.0, "oi_mc_ratio_pct": None})
    assert "ABCUSDT" in msg and "8.4" in msg and "180" in msg


def test_send_telegram_posts_and_returns_true_on_200():
    class Resp:
        status_code = 200
    with patch("notify.requests.post", return_value=Resp()) as p:
        ok = send_telegram("tok", "chat123", "hello")
    assert ok is True
    assert "tok" in p.call_args[0][0]  # url contains token


def test_send_telegram_returns_false_on_error():
    with patch("notify.requests.post", side_effect=Exception("net")):
        assert send_telegram("tok", "chat123", "hello") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_notify.py -k "format or send" -v`
Expected: FAIL — `ImportError: cannot import name 'format_alert_msg'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to notify.py
import requests

_LABEL = {"price_3s": "3s", "price_5s": "5s", "price_10s": "10s", "price_30s": "30s",
          "price_60s": "60s", "price_90s": "90s", "price_180s_extreme": "180s",
          "oi_price_1h": "1h OI"}


def format_alert_msg(alert: dict) -> str:
    sym = alert.get("symbol", "?")
    win = _LABEL.get(alert.get("window_type", ""), alert.get("window_type", ""))
    chg = alert.get("price_chg_pct", 0.0)
    arrow = "🟢" if chg >= 0 else "🔻"
    parts = [f"{arrow} {sym} {chg:+.1f}% / {win}"]
    if alert.get("chg_24h_pct") is not None:
        parts.append(f"24h {alert['chg_24h_pct']:+.0f}%")
    if alert.get("oi_chg_pct") is not None:
        parts.append(f"OI {alert['oi_chg_pct']:+.0f}%")
    if alert.get("oi_mc_ratio_pct") is not None:
        parts.append(f"OI/MC {alert['oi_mc_ratio_pct']:.1f}%")
    if alert.get("quote_vol_24h"):
        parts.append(f"vol ${alert['quote_vol_24h']/1e6:.1f}M")
    return " · ".join(parts)


def send_telegram(token: str, chat_id: str, text: str) -> bool:
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
        return r.status_code == 200
    except Exception:
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_notify.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/T9/BWE
git add infrastructure/collectors/bwe_scanner/notify.py infrastructure/collectors/bwe_scanner/tests/test_notify.py
git commit -m "feat(scanner): Telegram message format + send"
```

---

### Task 9: `enrich.py` — `Ticker24hCache` (Binance 24h context)

**Files:**
- Create: `infrastructure/collectors/bwe_scanner/enrich.py`
- Create: `infrastructure/collectors/bwe_scanner/tests/test_enrich.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_enrich.py
from unittest.mock import patch
from enrich import Ticker24hCache

FAKE_24H = [
    {"symbol": "ABCUSDT", "priceChangePercent": "15.0", "quoteVolume": "1234567", "lastPrice": "0.5"},
    {"symbol": "XYZUSDT", "priceChangePercent": "-3.2", "quoteVolume": "999", "lastPrice": "2.0"},
    {"symbol": "BTCUSDC", "priceChangePercent": "1.0", "quoteVolume": "5", "lastPrice": "60000"},
]


def test_ticker24h_refresh_and_get():
    c = Ticker24hCache("https://fapi.binance.com")
    with patch("enrich.requests.get") as g:
        g.return_value.json.return_value = FAKE_24H
        g.return_value.status_code = 200
        c.refresh()
    ctx = c.get("ABCUSDT")
    assert ctx["chg_24h_pct"] == 15.0
    assert ctx["quote_vol_24h"] == 1234567.0
    assert c.get("XYZUSDT")["chg_24h_pct"] == -3.2
    # non-USDT quote pairs ignored
    assert c.get("BTCUSDC") is None


def test_ticker24h_get_unknown_returns_none():
    c = Ticker24hCache("https://fapi.binance.com")
    assert c.get("NOPEUSDT") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_enrich.py -k ticker -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'enrich'`.

- [ ] **Step 3: Write minimal implementation**

```python
# enrich.py
from __future__ import annotations

import requests


class Ticker24hCache:
    """Snapshot of /fapi/v1/ticker/24hr keyed by USDT-perp symbol."""

    def __init__(self, fapi_base: str):
        self._base = fapi_base
        self._data: dict[str, dict] = {}

    def refresh(self) -> None:
        r = requests.get(f"{self._base}/fapi/v1/ticker/24hr", timeout=15)
        rows = r.json()
        data = {}
        for x in rows:
            sym = x.get("symbol", "")
            if not sym.endswith("USDT"):
                continue
            data[sym] = {
                "chg_24h_pct": float(x.get("priceChangePercent", 0.0)),
                "quote_vol_24h": float(x.get("quoteVolume", 0.0)),
                "last_price": float(x.get("lastPrice", 0.0)),
            }
        self._data = data

    def get(self, symbol: str) -> dict | None:
        return self._data.get(symbol)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_enrich.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/T9/BWE
git add infrastructure/collectors/bwe_scanner/enrich.py infrastructure/collectors/bwe_scanner/tests/test_enrich.py
git commit -m "feat(scanner): 24h ticker context cache"
```

---

### Task 10: `enrich.py` — `MarketCapCache` (CoinGecko supply → MC parity)

**Files:**
- Modify: `infrastructure/collectors/bwe_scanner/enrich.py`
- Modify: `infrastructure/collectors/bwe_scanner/tests/test_enrich.py`
- Create: `infrastructure/collectors/bwe_scanner/symbol_cg_map.json` (seed: `{}` — grown over time)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_enrich.py
from enrich import MarketCapCache


def test_marketcap_from_cached_supply_times_price():
    c = MarketCapCache(cg_map={"ABCUSDT": "abc-coin"})
    c._supply = {"abc-coin": 16_000_000.0}  # circulating supply (units)
    # MC = supply * price
    assert c.market_cap("ABCUSDT", price=0.5) == 8_000_000.0


def test_marketcap_unmapped_symbol_returns_none():
    c = MarketCapCache(cg_map={})
    assert c.market_cap("NOPEUSDT", price=1.0) is None


def test_marketcap_mapped_but_no_supply_returns_none():
    c = MarketCapCache(cg_map={"ABCUSDT": "abc-coin"})  # supply not loaded
    assert c.market_cap("ABCUSDT", price=1.0) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_enrich.py -k marketcap -v`
Expected: FAIL — `ImportError: cannot import name 'MarketCapCache'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to enrich.py
import json
import time
from pathlib import Path


class MarketCapCache:
    """Market cap = cached CoinGecko circulating supply × live price (BWE parity).

    Supply changes slowly → refresh daily. cg_map: {binance_symbol: coingecko_id}.
    Unmapped symbol or missing supply → market_cap returns None (logged by caller).
    """

    def __init__(self, cg_map: dict[str, str]):
        self._cg_map = cg_map
        self._supply: dict[str, float] = {}
        self._last_refresh = 0.0

    @classmethod
    def from_file(cls, path: str) -> "MarketCapCache":
        p = Path(path)
        cg_map = json.loads(p.read_text()) if p.exists() else {}
        return cls(cg_map)

    def market_cap(self, symbol: str, price: float) -> float | None:
        cg_id = self._cg_map.get(symbol)
        if not cg_id:
            return None
        supply = self._supply.get(cg_id)
        if not supply:
            return None
        return supply * price

    def refresh_supply(self, ids: list[str] | None = None) -> None:
        """Fetch circulating supply for mapped ids from CoinGecko (paged, free API)."""
        ids = ids if ids is not None else list(set(self._cg_map.values()))
        out: dict[str, float] = {}
        for i in range(0, len(ids), 100):
            chunk = ids[i:i + 100]
            try:
                r = requests.get(
                    "https://api.coingecko.com/api/v3/coins/markets",
                    params={"vs_currency": "usd", "ids": ",".join(chunk), "per_page": 100},
                    timeout=20,
                )
                for row in r.json():
                    cs = row.get("circulating_supply")
                    if cs:
                        out[row["id"]] = float(cs)
            except Exception:
                continue
            time.sleep(2.5)  # CoinGecko free rate limit
        if out:
            self._supply.update(out)
            self._last_refresh = time.time()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_enrich.py -v`
Expected: all passed.

- [ ] **Step 5: Seed the cg map + commit**

```bash
cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner
echo '{}' > symbol_cg_map.json
cd /Volumes/T9/BWE
git add infrastructure/collectors/bwe_scanner/enrich.py infrastructure/collectors/bwe_scanner/tests/test_enrich.py infrastructure/collectors/bwe_scanner/symbol_cg_map.json
git commit -m "feat(scanner): CoinGecko market-cap cache (BWE parity)"
```

> Note: `symbol_cg_map.json` starts empty (MC null until populated). Populate it incrementally
> from CoinGecko's `/coins/list` (a separate one-off script) — out of scope for v1 launch;
> alerts simply carry `market_cap_usd: null` until mapped. This does not block any alert.

---

### Task 11: `ws_feed.py` — `parse_markprice_array` (pure) + `PriceBuffers`

**Files:**
- Create: `infrastructure/collectors/bwe_scanner/ws_feed.py`
- Create: `infrastructure/collectors/bwe_scanner/tests/test_ws_feed.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ws_feed.py
from ws_feed import parse_markprice_array, PriceBuffers


def test_parse_markprice_array_extracts_symbol_price_ts():
    msg = ('[{"e":"markPriceUpdate","E":1700000000000,"s":"ABCUSDT","p":"0.5000"},'
           '{"e":"markPriceUpdate","E":1700000000000,"s":"XYZUSDT","p":"2.0"},'
           '{"e":"markPriceUpdate","E":1700000000000,"s":"BTCUSDC","p":"60000"}]')
    rows = parse_markprice_array(msg)
    # only USDT perps kept
    syms = {r[0] for r in rows}
    assert syms == {"ABCUSDT", "XYZUSDT"}
    abc = [r for r in rows if r[0] == "ABCUSDT"][0]
    assert abc == ("ABCUSDT", 1700000000000, 0.5)


def test_parse_markprice_ignores_malformed():
    assert parse_markprice_array("not json") == []
    assert parse_markprice_array('{"not":"array"}') == []


def test_pricebuffers_add_and_window_samples():
    pb = PriceBuffers(short_max_sec=200, long_step_sec=10, long_max_sec=3600)
    for ts in range(0, 5000, 1000):  # 0,1,2,3,4 s
        pb.add("ABCUSDT", ts, 100.0 + ts / 1000)
    s = pb.samples("ABCUSDT")
    assert s[0][0] == 0 and s[-1][1] == 104.0
    assert all(s[i][0] <= s[i + 1][0] for i in range(len(s) - 1))  # ascending


def test_pricebuffers_evicts_old_short_samples():
    pb = PriceBuffers(short_max_sec=10, long_step_sec=10, long_max_sec=3600)
    pb.add("ABCUSDT", 0, 100.0)
    pb.add("ABCUSDT", 20_000, 110.0)  # 20s later; 0 is older than short_max → only in long ring
    short = pb.short_samples("ABCUSDT")
    assert short[0][0] == 20_000  # the 0ms sample evicted from short ring
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_ws_feed.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ws_feed'`.

- [ ] **Step 3: Write minimal implementation**

```python
# ws_feed.py
from __future__ import annotations

import json
from collections import defaultdict, deque


def parse_markprice_array(msg: str) -> list[tuple[str, int, float]]:
    """Parse a !markPrice@arr payload → [(symbol, ts_ms, mark_price)] for USDT perps only."""
    try:
        arr = json.loads(msg)
    except Exception:
        return []
    if not isinstance(arr, list):
        return []
    out = []
    for x in arr:
        try:
            sym = x["s"]
            if not sym.endswith("USDT"):
                continue
            out.append((sym, int(x["E"]), float(x["p"])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


class PriceBuffers:
    """Per-symbol rolling price samples.

    Two rings per symbol: a full-resolution short ring (last `short_max_sec`, ~1s steps)
    for fast windows, and a downsampled long ring (1 sample / `long_step_sec`, up to
    `long_max_sec`) for the 1h window. `samples()` merges them ascending.
    """

    def __init__(self, short_max_sec: int = 200, long_step_sec: int = 10, long_max_sec: int = 3600):
        self._short_max_ms = short_max_sec * 1000
        self._long_step_ms = long_step_sec * 1000
        self._long_max_ms = long_max_sec * 1000
        self._short: dict[str, deque] = defaultdict(deque)
        self._long: dict[str, deque] = defaultdict(deque)
        self._last_long_ts: dict[str, int] = {}

    def add(self, symbol: str, ts_ms: int, price: float) -> None:
        s = self._short[symbol]
        s.append((ts_ms, price))
        while s and ts_ms - s[0][0] > self._short_max_ms:
            s.popleft()
        last = self._last_long_ts.get(symbol)
        if last is None or ts_ms - last >= self._long_step_ms:
            lg = self._long[symbol]
            lg.append((ts_ms, price))
            self._last_long_ts[symbol] = ts_ms
            while lg and ts_ms - lg[0][0] > self._long_max_ms:
                lg.popleft()

    def short_samples(self, symbol: str) -> list[tuple[int, float]]:
        return list(self._short.get(symbol, ()))

    def samples(self, symbol: str) -> list[tuple[int, float]]:
        """Merged ascending samples (long + short), deduped by ts."""
        merged = dict(self._long.get(symbol, ()))
        merged.update(self._short.get(symbol, ()))
        return sorted(merged.items())

    def symbols(self) -> list[str]:
        return list(self._short.keys())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_ws_feed.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/T9/BWE
git add infrastructure/collectors/bwe_scanner/ws_feed.py infrastructure/collectors/bwe_scanner/tests/test_ws_feed.py
git commit -m "feat(scanner): markPrice parse + dual-ring price buffers"
```

---

### Task 12: `ws_feed.py` — `WSFeed` (websocket client) + `OIPoller`

**Files:**
- Modify: `infrastructure/collectors/bwe_scanner/ws_feed.py`
- Modify: `infrastructure/collectors/bwe_scanner/tests/test_ws_feed.py`

> Network behavior (real WS / real OI HTTP) is validated in the EC2 smoke test (Task 14).
> Here we unit-test only the message-handling path (pure) via the existing `parse_markprice_array`
> and a fake OI payload parser.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_ws_feed.py
from ws_feed import oi_chg_from_hist


def test_oi_chg_from_hist_computes_1h_change_and_usd():
    # openInterestHist rows: oldest→newest, sumOpenInterestValue is USD notional
    rows = [{"sumOpenInterest": "1000", "sumOpenInterestValue": "5000000"},
            {"sumOpenInterest": "1100", "sumOpenInterestValue": "5500000"},
            {"sumOpenInterest": "1200", "sumOpenInterestValue": "6000000"}]
    chg_pct, oi_usd = oi_chg_from_hist(rows)
    assert round(chg_pct, 1) == 20.0   # (1200-1000)/1000
    assert oi_usd == 6_000_000.0       # latest USD notional


def test_oi_chg_from_hist_empty_returns_none():
    assert oi_chg_from_hist([]) == (None, None)
    assert oi_chg_from_hist([{"sumOpenInterest": "0", "sumOpenInterestValue": "0"}]) == (None, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_ws_feed.py -k oi_chg -v`
Expected: FAIL — `ImportError: cannot import name 'oi_chg_from_hist'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to ws_feed.py
import threading
import time

import requests
import websocket  # websocket-client


def oi_chg_from_hist(rows: list[dict]) -> tuple[float | None, float | None]:
    """From openInterestHist rows (oldest→newest) → (1h %% change of contracts, latest USD OI)."""
    if len(rows) < 2:
        return None, None
    try:
        first = float(rows[0]["sumOpenInterest"])
        last = float(rows[-1]["sumOpenInterest"])
        oi_usd = float(rows[-1]["sumOpenInterestValue"])
    except (KeyError, ValueError):
        return None, None
    if first == 0:
        return None, None
    return (last / first - 1.0) * 100.0, oi_usd


class WSFeed:
    """Subscribes !markPrice@arr@1s; pushes (symbol, ts, price) into PriceBuffers.
    Auto-reconnect with exponential backoff. Runs its own thread via start()."""

    def __init__(self, ws_url: str, buffers: PriceBuffers, on_tick=None):
        self._url = ws_url
        self._buffers = buffers
        self._on_tick = on_tick  # optional callback(now_ms) after each batch
        self._stop = threading.Event()
        self.last_msg_ms = 0

    def _on_message(self, ws, message: str) -> None:
        rows = parse_markprice_array(message)
        if not rows:
            return
        now_ms = rows[0][1]
        for sym, ts, price in rows:
            self._buffers.add(sym, ts, price)
        self.last_msg_ms = int(time.time() * 1000)
        if self._on_tick:
            self._on_tick(now_ms)

    def _run_forever(self) -> None:
        backoff = 1
        while not self._stop.is_set():
            try:
                ws = websocket.WebSocketApp(self._url, on_message=self._on_message)
                ws.run_forever(ping_interval=15, ping_timeout=8)
            except Exception:
                pass
            if self._stop.is_set():
                break
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)

    def start(self) -> threading.Thread:
        t = threading.Thread(target=self._run_forever, daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        self._stop.set()


class OIPoller:
    """Polls openInterestHist (period=5m, limit=13 → ~1h) for a set of symbols.
    Exposes {symbol: (oi_chg_1h_pct, oi_usd)}; refreshes round-robin under a throttle."""

    def __init__(self, fapi_base: str, poll_sec: int = 300):
        self._base = fapi_base
        self._poll_sec = poll_sec
        self._data: dict[str, tuple[float | None, float | None]] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._symbols: list[str] = []

    def set_universe(self, symbols: list[str]) -> None:
        with self._lock:
            self._symbols = list(symbols)

    def get(self, symbol: str) -> tuple[float | None, float | None]:
        return self._data.get(symbol, (None, None))

    def _poll_symbol(self, sym: str) -> None:
        try:
            r = requests.get(f"{self._base}/futures/data/openInterestHist",
                             params={"symbol": sym, "period": "5m", "limit": 13}, timeout=10)
            chg, usd = oi_chg_from_hist(r.json())
            self._data[sym] = (chg, usd)
        except Exception:
            pass

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                syms = list(self._symbols)
            t0 = time.time()
            for sym in syms:
                if self._stop.is_set():
                    break
                self._poll_symbol(sym)
                time.sleep(0.3)  # throttle (weight budget; shares EC2 IP with bot)
            elapsed = time.time() - t0
            self._stop.wait(max(1.0, self._poll_sec - elapsed))

    def start(self) -> threading.Thread:
        t = threading.Thread(target=self._run, daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        self._stop.set()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_ws_feed.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/T9/BWE
git add infrastructure/collectors/bwe_scanner/ws_feed.py infrastructure/collectors/bwe_scanner/tests/test_ws_feed.py
git commit -m "feat(scanner): websocket feed + OI poller (1h OI from openInterestHist)"
```

---

### Task 13: `scanner.py` — main wiring + `--dry-run` + heartbeat

**Files:**
- Create: `infrastructure/collectors/bwe_scanner/scanner.py`
- Create: `infrastructure/collectors/bwe_scanner/tests/test_scanner.py`

- [ ] **Step 1: Write the failing test** (the pure per-tick pipeline, no network)

```python
# tests/test_scanner.py
from scanner import run_detection_tick
import detectors


def test_run_detection_tick_emits_enriched_alerts():
    # one symbol with a fresh 60s pump; minimal config
    samples = {"ABCUSDT": [(0, 100.0), (60_000, 100.0), (120_000, 112.0)]}
    cfg = {"windows": {"price_60s": {"sec": 60, "thr_pct": 5.0}},
           "oi_price_1h": {"sec": 3600, "price_thr_pct": 5.0, "oi_thr_pct": 5.0},
           "store_cooldown_sec": 600}
    ctx = {"ABCUSDT": {"chg_24h_pct": 15.0, "quote_vol_24h": 1e6}}
    oi = {"ABCUSDT": (None, None)}
    last_fired = {}
    alerts = run_detection_tick(cfg, samples, ctx, oi, mc=None,
                                now_ms=120_000, last_fired=last_fired)
    assert len(alerts) == 1
    a = alerts[0]
    assert a["symbol"] == "ABCUSDT" and a["window_type"] == "price_60s"
    assert a["chg_24h_pct"] == 15.0
    # cooldown now recorded → second identical tick emits nothing
    assert run_detection_tick(cfg, samples, ctx, oi, mc=None,
                              now_ms=120_500, last_fired=last_fired) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/test_scanner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scanner'`.

- [ ] **Step 3: Write minimal implementation**

```python
# scanner.py
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time

import detectors
import store
import notify
from enrich import Ticker24hCache, MarketCapCache
from ws_feed import PriceBuffers, WSFeed, OIPoller


def run_detection_tick(cfg, samples, ctx, oi, mc, now_ms, last_fired):
    """PURE pipeline: per-symbol buffers → detections → cooldown → enriched alert dicts.

    samples: {sym: [(ts,price)]}; ctx: {sym: {chg_24h_pct, quote_vol_24h}}; oi: {sym: (chg,usd)}.
    mc: MarketCapCache | None. Returns list of alert dicts (ready to store/push)."""
    detections = []
    for sym, sm in samples.items():
        if not sm:
            continue
        detections += detectors.detect_price_ladder(sym, sm, now_ms, cfg["windows"])
        oi_chg, oi_usd = oi.get(sym, (None, None))
        oc = cfg["oi_price_1h"]
        d = detectors.detect_oi_price_1h(sym, sm, oi_chg, oi_usd, now_ms,
                                         oc["price_thr_pct"], oc["oi_thr_pct"])
        if d:
            detections.append(d)
    kept = detectors.apply_cooldown(detections, last_fired, cfg["store_cooldown_sec"], now_ms)
    alerts = []
    for d in kept:
        sym_ctx = ctx.get(d.symbol, {})
        price = d.price or sym_ctx.get("last_price", 0.0)
        mcap = mc.market_cap(d.symbol, price) if mc else None
        alerts.append(detectors.alert_to_dict(detectors.to_alert(d, sym_ctx, mcap)))
    return alerts


class Scanner:
    def __init__(self, cfg: dict, dry_run: bool = False):
        self.cfg = cfg
        self.dry_run = dry_run
        self.buffers = PriceBuffers()
        self.ticker = Ticker24hCache(cfg["fapi_base"])
        self.mc = MarketCapCache.from_file(cfg["paths"]["cg_map"])
        self.oi = OIPoller(cfg["fapi_base"], cfg.get("oi_poll_sec", 300))
        self.feed = WSFeed(cfg["ws_url"], self.buffers)
        self.last_fired_store: dict = {}
        self.last_fired_push: dict = {}
        self._stop = False
        self._tg_token = os.environ.get(cfg["telegram"]["token_env"], "")
        self._tg_chat = os.environ.get(cfg["telegram"]["chat_id_env"], "")
        self._last_24h = 0.0
        self._last_supply = 0.0
        self._last_hb = 0.0
        self._alert_count = 0

    def _log(self, msg: str) -> None:
        print(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] {msg}", flush=True)

    def _maybe_refresh(self, now: float) -> None:
        if now - self._last_24h >= self.cfg.get("ticker24h_poll_sec", 60):
            try:
                self.ticker.refresh()
                self.oi.set_universe([s for s in self.buffers.symbols()])
            except Exception as e:
                self._log(f"24h refresh err: {e}")
            self._last_24h = now
        if now - self._last_supply >= self.cfg.get("supply_refresh_sec", 86400):
            try:
                self.mc.refresh_supply()
            except Exception as e:
                self._log(f"supply refresh err: {e}")
            self._last_supply = now

    def _ctx_map(self) -> dict:
        out = {}
        for sym in self.buffers.symbols():
            c = self.ticker.get(sym)
            if c:
                out[sym] = c
        return out

    def _oi_map(self) -> dict:
        return {sym: self.oi.get(sym) for sym in self.buffers.symbols()}

    def tick(self) -> None:
        now_ms = int(time.time() * 1000)
        samples = {sym: self.buffers.samples(sym) for sym in self.buffers.symbols()}
        alerts = run_detection_tick(self.cfg, samples, self._ctx_map(), self._oi_map(),
                                    self.mc, now_ms, self.last_fired_store)
        for a in alerts:
            self._alert_count += 1
            store.append_alert(self.cfg["paths"]["jsonl_dir"], a, now_ms)
            if self.dry_run:
                self._log("ALERT " + notify.format_alert_msg(a))
            elif self.cfg["telegram"]["enabled"] and notify.should_push(a, self.cfg["push_filter"]):
                kept = detectors.apply_cooldown(
                    [type("D", (), {"symbol": a["symbol"], "window_type": a["window_type"]})()],
                    self.last_fired_push, self.cfg["push_cooldown_sec"], now_ms)
                if kept and self._tg_token and self._tg_chat:
                    notify.send_telegram(self._tg_token, self._tg_chat, notify.format_alert_msg(a))

    def _heartbeat(self, now: float) -> None:
        if now - self._last_hb >= 300:
            age = (int(time.time() * 1000) - self.feed.last_msg_ms) / 1000 if self.feed.last_msg_ms else -1
            self._log(f"HB symbols={len(self.buffers.symbols())} alerts={self._alert_count} "
                      f"ws_age={age:.0f}s")
            self._last_hb = now

    def run(self) -> int:
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "_stop", True))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "_stop", True))
        self.feed.start()
        self.oi.start()
        self._log(f"scanner started (dry_run={self.dry_run})")
        while not self._stop:
            now = time.time()
            self._maybe_refresh(now)
            try:
                self.tick()
            except Exception as e:
                self._log(f"tick err: {e}")
            self._heartbeat(now)
            time.sleep(1.0)
        self.feed.stop()
        self.oi.stop()
        self._log("scanner stopped")
        return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    cfg = json.load(open(args.config))
    return Scanner(cfg, dry_run=args.dry_run).run()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes** (+ full suite)

Run: `cd /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner && python3 -m pytest tests/ -v`
Expected: ALL tests pass (every module).

- [ ] **Step 5: Commit**

```bash
cd /Volumes/T9/BWE
git add infrastructure/collectors/bwe_scanner/scanner.py infrastructure/collectors/bwe_scanner/tests/test_scanner.py
git commit -m "feat(scanner): main loop wiring + pure detection tick + dry-run + heartbeat"
```

---

### Task 14: Deploy to EC2 — systemd, swapfile, secrets, smoke test, archive sync

**Files:**
- Create: `infrastructure/collectors/bwe_scanner/bwe-scanner.service`
- Create: `infrastructure/collectors/bwe_scanner/deploy.sh`
- Modify (EC2 only): `/etc/systemd/system/bwe-scanner.service`, `/home/ubuntu/bwe-scanner/secrets.env`

- [ ] **Step 1: Write the systemd unit**

```ini
# bwe-scanner.service
[Unit]
Description=BWE Self-Hosted Scanner (Binance all-perp anomaly detector)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/bwe-scanner
EnvironmentFile=/home/ubuntu/bwe-scanner/secrets.env
ExecStartPre=/bin/bash -c 'pkill -9 -f "scanner.py --config" 2>/dev/null || true; sleep 1'
ExecStart=/usr/bin/python3 -u scanner.py --config config.json
Restart=on-failure
RestartSec=5
StandardOutput=append:/home/ubuntu/bwe-scanner/logs/stdout.log
StandardError=append:/home/ubuntu/bwe-scanner/logs/stderr.log

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Write `deploy.sh` (run from Mac; ships code to EC2)**

```bash
#!/bin/bash
set -euo pipefail
EC2=ubuntu@<EC2_HOST>
KEY=~/.ssh/bwe-tokyo.pem
SRC=/Volumes/T9/BWE/infrastructure/collectors/bwe_scanner
DST=/home/ubuntu/bwe-scanner

ssh -i $KEY $EC2 "mkdir -p $DST/data $DST/logs"
# ship flat modules + config (NOT tests)
scp -i $KEY $SRC/{scanner.py,detectors.py,ws_feed.py,enrich.py,store.py,notify.py,config.json,symbol_cg_map.json} $EC2:$DST/
scp -i $KEY $SRC/bwe-scanner.service $EC2:/tmp/bwe-scanner.service
ssh -i $KEY $EC2 "sudo mv /tmp/bwe-scanner.service /etc/systemd/system/ && sudo systemctl daemon-reload"
echo "deployed to $DST"
```

- [ ] **Step 3: Add 1 GB swapfile on EC2 (cheap OOM insurance — spec §11)**

```bash
ssh -i ~/.ssh/bwe-tokyo.pem ubuntu@<EC2_HOST> '
if ! sudo swapon --show | grep -q /swapfile; then
  sudo fallocate -l 1G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
  echo "/swapfile none swap sw 0 0" | sudo tee -a /etc/fstab
fi
free -h'
```
Expected: `Swap: 1.0Gi` shown.

- [ ] **Step 4: Set the scanner Telegram chat id + deps on EC2**

```bash
ssh -i ~/.ssh/bwe-tokyo.pem ubuntu@<EC2_HOST> '
python3 -c "import websocket" 2>/dev/null || pip3 install --user websocket-client requests
# secrets.env: reuse the bot token; set a separate scanner chat id (ask user for the chat id value)
grep -q BWE_LIVE_TELEGRAM_BOT_TOKEN /home/ubuntu/bwe-scanner/secrets.env 2>/dev/null || \
  cp /home/ubuntu/bwe-live/secrets.env /home/ubuntu/bwe-scanner/secrets.env
echo "BWE_SCANNER_TELEGRAM_CHAT_ID=<USER_PROVIDES>" | sudo tee -a /home/ubuntu/bwe-scanner/secrets.env'
```
> The scanner chat id value must be provided by the user (a Telegram chat/channel id). Until set,
> run with `telegram.enabled=false` or in `--dry-run`.

- [ ] **Step 5: Deploy + 5-min dry-run smoke test (verify detections match reality)**

```bash
bash /Volumes/T9/BWE/infrastructure/collectors/bwe_scanner/deploy.sh
ssh -i ~/.ssh/bwe-tokyo.pem ubuntu@<EC2_HOST> '
cd /home/ubuntu/bwe-scanner && timeout 330 python3 -u scanner.py --config config.json --dry-run 2>&1 | tail -40'
```
Expected: after ~60s warm-up, `HB symbols=~400 ...` heartbeats; `ALERT 🟢/🔻 XXXUSDT ...` lines whose
moves can be eyeballed against Binance. No tracebacks. (3s/10s micro-alerts will appear first; 1h needs
~60 min warm-up so may be absent in a 5-min run — that's expected.)

- [ ] **Step 6: Enable the service + verify healthy**

```bash
ssh -i ~/.ssh/bwe-tokyo.pem ubuntu@<EC2_HOST> '
sudo systemctl enable --now bwe-scanner.service && sleep 90
systemctl is-active bwe-scanner.service
tail -15 /home/ubuntu/bwe-scanner/logs/stdout.log
ls -la /home/ubuntu/bwe-scanner/data/'
```
Expected: `active`; heartbeat lines; a growing `alerts_YYYY-MM-DD.jsonl`.

- [ ] **Step 7: Archive sync to H: (Mac cron pulls EC2 data into 30_DATA for research)**

```bash
mkdir -p /Volumes/T9/BWE/30_DATA/bwe_scanner_alerts
# add to Mac crontab (crontab -e): hourly pull
# 0 * * * * rsync -az -e "ssh -i ~/.ssh/bwe-tokyo.pem" ubuntu@<EC2_HOST>:/home/ubuntu/bwe-scanner/data/ /Volumes/T9/BWE/30_DATA/bwe_scanner_alerts/ 2>>/tmp/bwe_scanner_rsync.log
echo "add the above line via: crontab -e"
```

- [ ] **Step 8: Commit deploy artifacts**

```bash
cd /Volumes/T9/BWE
git add infrastructure/collectors/bwe_scanner/bwe-scanner.service infrastructure/collectors/bwe_scanner/deploy.sh
git commit -m "feat(scanner): systemd unit + deploy script + EC2 ops (swap, smoke test, archive sync)"
```

---

## Self-Review (against spec)

**1. Spec coverage:**
- §4 modules → Tasks 0,1-5 (detectors), 6 (store), 7-8 (notify), 9-10 (enrich), 11-12 (ws_feed), 13 (scanner). ✓
- §5 windows + thresholds → config (Task 0) + `detect_price_ladder` (Task 2) + `detect_oi_price_1h` (Task 4). ✓
- §6 storage schema (incl. market_cap_usd, oi_mc_ratio_pct) → `Alert`/`to_alert` (Task 5) + `append_alert` (Task 6). ✓
- §7 Telegram high-signal subset → `should_push` (Task 7) + format/send (Task 8) + wiring (Task 13). ✓
- §2.5 BWE parity (market cap) → `MarketCapCache` (Task 10) + `oi_mc_ratio` in `to_alert` (Task 5). ✓
- §8 reliability (systemd, WS reconnect, heartbeat) → `WSFeed` backoff (Task 12) + heartbeat/signals (Task 13) + unit (Task 14). ✓
- §9 testing → unit tests every core task; dry-run + EC2 smoke (Task 14). ✓
- §11 t3.micro + swapfile → Task 14 Step 3. ✓
- Zero bot changes → confirmed (separate dir, separate service, separate chat id). ✓

**2. Placeholder scan:** No "TBD"/"add error handling here". The one external dependency left
unpopulated (`symbol_cg_map.json` empty) is explicitly handled: `market_cap` returns null, never
blocks an alert (Task 10 note). The `<USER_PROVIDES>` scanner chat id (Task 14 Step 4) is a real
human input, flagged.

**3. Type consistency:** `Detection`/`Alert` fields defined Task 2/5, used identically in Tasks
13. `run_detection_tick(cfg, samples, ctx, oi, mc, now_ms, last_fired)` signature consistent between
Task 13 impl and test. `should_push(alert, push_filter)`, `append_alert(jsonl_dir, alert, now_ms)`,
`oi_chg_from_hist(rows)->(pct,usd)` consistent across definition/use. `PriceBuffers.samples()` used
by scanner tick. ✓

## Out of scope (deferred — spec §11)
News/listing parity module; extra surpass windows (5m/15m, CVD); SQLite mirror; optional B-feed hook;
incremental population of `symbol_cg_map.json`.
