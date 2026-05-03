"""Deep analysis: Hermes live + paper trades vs 1m kline ground truth.

Questions answered:
1. 哪些币赢/输? Per-trade pnl, grouped by strategy/symbol/channel/side
2. 为什么赢/输? Entry conditions vs forward kline behavior
3. 赢了的有没吃到最大价值? Realized pnl vs theoretical max_fav over hold period
4. Strategy-level: edge persistence, dispersion, win rate, R/R
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

LIVE_JOURNAL = Path("/Users/ye/.hermes/research/bwe_live_autotrader_binance_expectancy_runtime/trade_journal.jsonl")
PAPER_JOURNAL = Path("/Users/ye/.hermes/research/bwe_paper_multilot_observer_runtime/trade_journal.jsonl")
KLINE_DB = "/Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3"
OUT_DIR = Path("/Volumes/T9/BWE/40_EXPERIMENTS/round4/05_audits")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_trades(journal_path: Path) -> list[dict]:
    """Pair entry+exit by trade_id, return one row per closed trade."""
    by_id: dict[str, dict] = {}
    for line in journal_path.open():
        j = json.loads(line)
        tid = j.get("trade_id")
        if not tid:
            continue
        if j["action"] == "entry":
            by_id[tid] = {**j, "exits": []}
        elif j["action"] in ("exit", "partial_exit"):
            if tid not in by_id:
                continue
            by_id[tid]["exits"].append(j)

    closed = []
    for tid, t in by_id.items():
        if not t.get("exits"):
            continue  # still open
        # Use last exit (final close) for primary analysis
        final = t["exits"][-1]
        closed.append({
            "trade_id": tid,
            "symbol": t["symbol"],
            "market_symbol": t["market_symbol"],
            "strategy": t["strategy_name"],
            "side": t["side"],
            "channel": t["channel"],
            "priority": t.get("priority", "?"),
            "post_id": t.get("post_id", "?"),
            "trigger_reason": t.get("trigger_reason", ""),
            "entry_ts": t.get("entry_ts", t["ts"]),
            "entry_px": t.get("entry_px", t.get("fill_price")),
            "exit_ts": final["ts"],
            "exit_px": final.get("fill_price"),
            "exit_reason": final.get("exit_reason", "?"),
            "hold_minutes_limit": t.get("hold_minutes_limit", 0),
            "hold_minutes": final.get("hold_minutes", 0),
            "pnl_pct": final.get("pnl_pct", 0),
            "n_partial": len([e for e in t["exits"] if e["action"] == "partial_exit"]),
        })
    return closed


def fetch_kline_window(con, symbol: str, start_ms: int, end_ms: int) -> list[dict]:
    """Fetch 1m kline bars from sqlite for [start, end] inclusive."""
    sym_norm = symbol if symbol.endswith("USDT") else symbol + "USDT"
    cur = con.execute(
        "SELECT open_time_ms, open, high, low, close, volume, taker_buy_quote_volume "
        "FROM klines_1m WHERE symbol=? AND open_time_ms BETWEEN ? AND ? "
        "ORDER BY open_time_ms",
        (sym_norm, start_ms, end_ms),
    )
    return [
        {"ts": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4],
         "volume": r[5], "taker_buy_quote": r[6]}
        for r in cur.fetchall()
    ]


def compute_theoretical_max(trade: dict, con) -> dict:
    """Find theoretical max favorable + adverse excursion within hold period."""
    entry_ts_ms = int(trade["entry_ts"] * 1000)
    exit_ts_ms = int(trade["exit_ts"] * 1000)
    sym = trade["market_symbol"]
    bars = fetch_kline_window(con, sym, entry_ts_ms, exit_ts_ms)
    if not bars:
        return {"n_bars": 0, "max_fav_pct": None, "max_adv_pct": None,
                "captured_ratio": None, "max_fav_minute": None}
    entry_px = trade["entry_px"]
    side = trade["side"]
    if side == "long":
        max_fav_px = max(b["high"] for b in bars)
        max_adv_px = min(b["low"] for b in bars)
        max_fav_pct = (max_fav_px - entry_px) / entry_px * 100
        max_adv_pct = (max_adv_px - entry_px) / entry_px * 100
        max_fav_idx = next(i for i, b in enumerate(bars) if b["high"] == max_fav_px)
    else:  # short
        max_fav_px = min(b["low"] for b in bars)
        max_adv_px = max(b["high"] for b in bars)
        max_fav_pct = (entry_px - max_fav_px) / entry_px * 100
        max_adv_pct = (entry_px - max_adv_px) / entry_px * 100
        max_fav_idx = next(i for i, b in enumerate(bars) if b["low"] == max_fav_px)

    pnl = trade["pnl_pct"]
    # Captured ratio: how much of theoretical max did we get?
    if max_fav_pct > 0.01:
        captured = pnl / max_fav_pct
    else:
        captured = None

    return {
        "n_bars": len(bars),
        "max_fav_pct": max_fav_pct,
        "max_adv_pct": max_adv_pct,
        "max_fav_minute": max_fav_idx,
        "captured_ratio": captured,
    }


def main() -> int:
    print("=" * 80)
    print("Hermes Live + Paper Trade Analysis")
    print("=" * 80)

    con = sqlite3.connect(KLINE_DB)

    for label, journal_path in [("LIVE", LIVE_JOURNAL), ("PAPER", PAPER_JOURNAL)]:
        print(f"\n{'#'*60}\n# {label}\n{'#'*60}")
        trades = load_trades(journal_path)
        print(f"closed trades: {len(trades)}")
        if not trades:
            continue

        # Compute max_fav per trade
        for t in trades:
            theo = compute_theoretical_max(t, con)
            t.update(theo)

        # Aggregate
        wins = [t for t in trades if t["pnl_pct"] > 0]
        losses = [t for t in trades if t["pnl_pct"] <= 0]
        total_pnl = sum(t["pnl_pct"] for t in trades)
        win_rate = len(wins) / len(trades) * 100
        avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0
        rr = abs(avg_win / avg_loss) if avg_loss else 0

        print(f"\n=== Headline ===")
        print(f"  total trades:    {len(trades)}")
        print(f"  win rate:        {win_rate:.1f}% ({len(wins)} wins / {len(losses)} losses)")
        print(f"  total pnl_pct:   {total_pnl:+.2f}% (sum, not compound)")
        print(f"  avg win:         {avg_win:+.2f}%")
        print(f"  avg loss:        {avg_loss:+.2f}%")
        print(f"  R/R ratio:       {rr:.2f} (>1 = winners larger)")

        # By strategy
        by_strat = defaultdict(list)
        for t in trades:
            by_strat[t["strategy"]].append(t)
        print(f"\n=== By Strategy ===")
        print(f"{'strategy':40s} {'n':>4} {'win%':>6} {'mean':>7} {'pnl_total':>10} {'avg_win':>8} {'avg_loss':>9}")
        for strat, ts in sorted(by_strat.items(), key=lambda x: -len(x[1])):
            wins_s = [t for t in ts if t["pnl_pct"] > 0]
            losses_s = [t for t in ts if t["pnl_pct"] <= 0]
            win_pct = len(wins_s) / len(ts) * 100
            mean_pnl = sum(t["pnl_pct"] for t in ts) / len(ts)
            total = sum(t["pnl_pct"] for t in ts)
            aw = sum(t["pnl_pct"] for t in wins_s) / len(wins_s) if wins_s else 0
            al = sum(t["pnl_pct"] for t in losses_s) / len(losses_s) if losses_s else 0
            print(f"{strat[:40]:40s} {len(ts):>4} {win_pct:>5.1f}% {mean_pnl:>+6.2f}% {total:>+9.2f}% {aw:>+7.2f}% {al:>+8.2f}%")

        # Captured ratio analysis (did we exit at the right time?)
        cap_data = [(t["pnl_pct"], t.get("max_fav_pct"), t.get("max_adv_pct"),
                     t.get("captured_ratio"), t["strategy"], t["symbol"], t["hold_minutes"])
                    for t in trades if t.get("max_fav_pct") is not None]
        if cap_data:
            print(f"\n=== Capture Efficiency (realized PnL / theoretical max_fav) ===")
            valid = [c for c in cap_data if c[3] is not None]
            if valid:
                avg_capture = sum(c[3] for c in valid) / len(valid)
                positive_capture = [c for c in valid if c[3] > 0]
                print(f"  trades with theoretical max_fav > 0:  {len(valid)} / {len(cap_data)}")
                print(f"  avg captured ratio:                   {avg_capture*100:+.1f}% (1.0 = perfect, 0 = exited at entry, neg = exited at loss)")
                # 5 worst capture (left big money on table)
                worst = sorted(valid, key=lambda x: x[3])[:5]
                print(f"\n  5 trades that left BIGGEST money on the table:")
                for pnl, fav, adv, cap, strat, sym, hold_m in worst:
                    print(f"    {sym}/{strat[:30]:30s} pnl={pnl:+.1f}%  max_fav={fav:+.1f}%  cap={cap*100:.0f}%  hold={hold_m:.0f}m")
                # 5 best capture
                best = sorted(valid, key=lambda x: -x[3])[:5]
                print(f"\n  5 trades that captured BEST:")
                for pnl, fav, adv, cap, strat, sym, hold_m in best:
                    print(f"    {sym}/{strat[:30]:30s} pnl={pnl:+.1f}%  max_fav={fav:+.1f}%  cap={cap*100:.0f}%  hold={hold_m:.0f}m")

        # Adverse excursion (drawdown during trade) for losers
        losers = sorted([t for t in trades if t["pnl_pct"] <= 0 and t.get("max_adv_pct") is not None],
                       key=lambda x: x["max_adv_pct"])[:5]
        if losers:
            print(f"\n=== 5 worst losers (deepest drawdown) ===")
            for t in losers:
                print(f"    {t['symbol']}/{t['strategy'][:30]:30s} pnl={t['pnl_pct']:+.1f}%  max_adv={t['max_adv_pct']:+.1f}%  max_fav={t['max_fav_pct']:+.1f}%  hold={t['hold_minutes']:.0f}m  exit={t['exit_reason']}")

        # Top 10 winners
        top_winners = sorted(trades, key=lambda t: -t["pnl_pct"])[:10]
        print(f"\n=== Top 10 winners ===")
        for t in top_winners:
            fav = t.get("max_fav_pct", "?")
            cap = t.get("captured_ratio")
            cap_str = f"{cap*100:.0f}%" if cap else "?"
            print(f"    {t['symbol']}/{t['strategy'][:30]:30s} pnl={t['pnl_pct']:+.2f}%  fav_max={fav if fav=='?' else f'{fav:+.1f}%'}  captured={cap_str}  hold={t['hold_minutes']:.0f}m")

        # Save full per-trade data
        out_path = OUT_DIR / f"hermes_{label.lower()}_trades_analyzed.json"
        with out_path.open("w") as f:
            json.dump(trades, f, indent=2, default=str)
        print(f"\n  saved: {out_path}")

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
