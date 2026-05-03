"""Validate alpha of BWE_Reserved6 channel signals.

Parses all historical BWE_Reserved6 events from bwe_matrix_posts.jsonl,
computes forward 60min returns, tests both fade and follow direction
hypotheses to find which has alpha.

Output: per-direction stats, decision on whether to add a strategy.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter
from statistics import mean, stdev


JSONL = "/Users/ye/.hermes/logs/bwe_matrix_posts.jsonl"
DB = (
    "/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/"
    "binance_futures_1m.sqlite3"
)
EXTENDED_DB = "/Volumes/T9/binance data/historical/binance_extended_history.sqlite3"

# Match symbol (ALL CAPS letters/digits ending USDT) and pct (X.X% or X%)
SYMBOL_RE = re.compile(r"\b([A-Z][A-Z0-9]+USDT)\b")
PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def parse_event(text: str) -> dict | None:
    """Extract symbol + side + pct from BWE_Reserved6 text."""
    sym_m = SYMBOL_RE.search(text)
    pct_m = PCT_RE.search(text)
    if not sym_m or not pct_m:
        return None
    pct = float(pct_m.group(1))
    # Determine direction
    if "🟢" in text or "飙升" in text or "上涨" in text or "surged" in text.lower():
        side = "pump"
    elif "🔻" in text or "下跌" in text or "drop" in text.lower():
        side = "dump"
    else:
        # ambiguous
        return None
    # For dump events, magnitude should be negative (signed)
    signed_pct = pct if side == "pump" else -pct
    return {
        "symbol": sym_m.group(1),
        "side": side,
        "pct": pct,
        "signed_pct": signed_pct,
    }


def forward_return(con, sym: str, ts_ms: int, horizon_min: int = 60) -> float | None:
    """Compute forward Nmin return.

    BWE event ts_ms is second-level; klines are minute-aligned.
    Round target to minute, query nearest kline within ±2min window.
    """
    cur = con.execute(
        "SELECT close FROM klines_1m WHERE symbol=? AND open_time_ms <= ? "
        "ORDER BY open_time_ms DESC LIMIT 1", (sym, ts_ms)
    ).fetchone()
    target_ms = ts_ms + horizon_min * 60_000
    target_min = (target_ms // 60_000) * 60_000  # round down to minute
    fut = con.execute(
        "SELECT close FROM klines_1m WHERE symbol=? AND open_time_ms BETWEEN ? AND ? "
        "ORDER BY ABS(open_time_ms - ?) LIMIT 1",
        (sym, target_min - 60_000, target_min + 120_000, target_min)
    ).fetchone()
    if not cur or not fut or cur[0] <= 0:
        return None
    return (fut[0] - cur[0]) / cur[0] * 100


def main():
    print("=" * 70)
    print("BWE_Reserved6 Channel Alpha Validation")
    print("=" * 70)

    # Load all BWE_Reserved6 events
    events = []
    with open(JSONL) as f:
        for line in f:
            try:
                d = json.loads(line)
            except:
                continue
            ch = d.get("channel") or d.get("source")
            if ch != "BWE_Reserved6":
                continue
            if d.get("type") != "post":
                continue
            text = d.get("text", "")
            parsed = parse_event(text)
            if parsed is None:
                continue
            events.append({
                **parsed,
                "ts_ms": int(d.get("event_ts_ms") or d.get("ts_ms") or 0),
                "text": text[:120],
            })
    print(f"  parsed {len(events)} BWE_Reserved6 events with valid symbol+pct")

    if not events:
        print("  No events to test.")
        return 1

    # Direction breakdown
    pump_events = [e for e in events if e["side"] == "pump"]
    dump_events = [e for e in events if e["side"] == "dump"]
    print(f"  pump (sudden up): {len(pump_events)}")
    print(f"  dump (sudden down): {len(dump_events)}")
    pcts = [e["pct"] for e in events]
    if pcts:
        print(f"  pct range: {min(pcts):.1f}% – {max(pcts):.1f}%, median {sorted(pcts)[len(pcts)//2]:.1f}%")

    # Try both DBs to maximize klines coverage
    con_live = sqlite3.connect(DB, timeout=30)
    con_live.execute("PRAGMA query_only=1")
    try:
        con_ext = sqlite3.connect(f"file:{EXTENDED_DB}?mode=ro", uri=True, timeout=30)
    except Exception:
        con_ext = None

    def get_fwd(sym, ts_ms, horizon):
        r = forward_return(con_live, sym, ts_ms, horizon)
        if r is not None:
            return r
        if con_ext:
            return forward_return(con_ext, sym, ts_ms, horizon)
        return None

    # Compute forward returns for each event
    enriched = []
    for e in events:
        for hz in [30, 60, 120]:
            fwd = get_fwd(e["symbol"], e["ts_ms"], hz)
            if fwd is None:
                continue
            enriched.append({
                **e,
                "horizon_min": hz,
                "forward_return": fwd,
            })

    print(f"\n  enriched {len(enriched)} (event × horizon) datapoints")

    # ============= 4 Direction Hypotheses =============
    print("\n" + "=" * 70)
    print("Direction Hypothesis Test (per side × per horizon)")
    print("=" * 70)
    print(f"{'side':<6s} {'hz':<5s} {'n':>4s} {'fade_short':>12s} {'follow':>12s} {'win_fade':>10s} {'win_follow':>11s}")

    for side in ["pump", "dump"]:
        for hz in [30, 60, 120]:
            sub = [e for e in enriched if e["side"] == side and e["horizon_min"] == hz]
            if len(sub) < 5:
                continue
            # Fade hypothesis: pump → short (gain when fwd<0); dump → long (gain when fwd>0)
            if side == "pump":
                fade_outcomes = [-e["forward_return"] for e in sub]  # short wins when fwd negative
                follow_outcomes = [e["forward_return"] for e in sub]  # long wins when fwd positive
            else:  # dump
                fade_outcomes = [e["forward_return"] for e in sub]   # long wins when fwd positive
                follow_outcomes = [-e["forward_return"] for e in sub] # short wins when fwd negative
            fade_mean = mean(fade_outcomes)
            follow_mean = mean(follow_outcomes)
            win_fade = sum(1 for o in fade_outcomes if o > 0) / len(fade_outcomes) * 100
            win_follow = sum(1 for o in follow_outcomes if o > 0) / len(follow_outcomes) * 100
            print(f"  {side:<6s} {hz:<5d} {len(sub):>4d} {fade_mean:>+11.2f}% {follow_mean:>+11.2f}% {win_fade:>9.1f}% {win_follow:>10.1f}%")

    print("\n" + "=" * 70)
    print("Decision")
    print("=" * 70)

    # Best combo
    best = None
    for side in ["pump", "dump"]:
        for hz in [30, 60, 120]:
            sub = [e for e in enriched if e["side"] == side and e["horizon_min"] == hz]
            if len(sub) < 30:
                continue
            for direction in ["fade", "follow"]:
                if direction == "fade":
                    if side == "pump":
                        outcomes = [-e["forward_return"] for e in sub]
                        intent = "short"
                    else:
                        outcomes = [e["forward_return"] for e in sub]
                        intent = "long"
                else:
                    if side == "pump":
                        outcomes = [e["forward_return"] for e in sub]
                        intent = "long"
                    else:
                        outcomes = [-e["forward_return"] for e in sub]
                        intent = "short"
                m = mean(outcomes)
                w = sum(1 for o in outcomes if o > 0) / len(outcomes) * 100
                if m > 0.3 and w > 52:
                    if not best or m > best["mean"]:
                        best = {"side": side, "hz": hz, "direction": direction,
                                "intent": intent, "mean": m, "win": w, "n": len(sub)}

    if best:
        print(f"  ✅ Best alpha combo: side={best['side']}, horizon={best['hz']}min, {best['direction']} → {best['intent']}")
        print(f"     n={best['n']}, mean={best['mean']:+.2f}%, win={best['win']:.1f}%")
        print(f"  → 建议添加 BWE_Reserved6 strategy: 当 {best['side']} 触发 → {best['intent']} entry, hold {best['hz']}min")
    else:
        print("  ❌ No combo passes alpha threshold (mean > 0.3% AND win > 52% AND n >= 30)")
        print("  → BWE_Reserved6 不增加 alpha,建议不添加 strategy (Layer B 后续会通过 ±8% 扫描覆盖)")

    con_live.close()
    if con_ext:
        con_ext.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
