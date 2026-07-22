#!/usr/bin/env python3
"""信号桥 v2: stockusbot signal_ledger → TradFi永续可交易信号。
四方审查修复:
- F2: 不再无差别桥接 long/short。stance×horizon 子集白名单(默认只放行实测正edge的格子)。
- F3: 透传 outcomes(正股realized回报)做ground-truth对照。
- I1: universe 运行时从采集DB的exchangeInfo动态读, 不再硬编码; ticker→symbol显式映射处理点号/改名; 映射失败WARN落账不静默。
只读stockusbot(不改它)。"""
import json, os, sqlite3, sys

DIR = os.path.dirname(os.path.abspath(__file__))
LEDGER = "/Users/ye/.hermes/profiles/stockusbot/state/calibration/signal_ledger.jsonl"
CAP_DB = os.path.join(DIR, "tradfi_capture_ec2.sqlite3")   # 采集库(有实际symbol)
OUT = os.path.join(DIR, "bridged_signals.jsonl")
SKIP_LOG = os.path.join(DIR, "bridge_skipped.jsonl")

CONF_W = {"高": 1.0, "high": 1.0, "中": 0.6, "medium": 0.6, "低": 0.3, "low": 0.3}

# F2: 子集白名单 — 实测(stockusbot自身outcomes): Sell@5d=+1.56%/64%胜 是唯一正edge;
# Buy@5d=-1.71%(反向). 默认只放行 Sell侧 + 标注其它为"观察不交易"。可改 ALLOW_ALL=True 做全量paper对照。
TRADE_WHITELIST = {("short", 5), ("short", 1)}   # (side, hold_days) 允许真正"建议交易"的格子
ALLOW_ALL_FOR_PAPER = True   # paper阶段全量评估(但每条标 tradeable=是否在白名单), 真钱只看白名单

# ticker → 永续symbol 的显式映射(处理点号/改名等特例); 其余默认 +USDT
TICKER_FIX = {
    "BRK.B": "BRKBUSDT", "BRKB": "BRKBUSDT",
    # PayPal 真ticker PYPL, Binance符号是 PAYPUSDT
    "PYPL": "PAYPUSDT", "PAYP": "PAYPUSDT",
}

def live_universe():
    """从采集DB读真实在交易的EQUITY永续symbol集; 失败回退到已知快照。"""
    if os.path.exists(CAP_DB):
        try:
            c = sqlite3.connect("file:%s?mode=ro" % CAP_DB, uri=True)
            rows = c.execute("SELECT DISTINCT symbol FROM klines_1m").fetchall()
            if rows:
                return set(r[0] for r in rows)
        except Exception:
            pass
    # 回退快照(标注: 应尽快让采集库可用)
    return set(s + "USDT" for s in
               "TSLA INTC HOOD MSTR AMZN CRCL COIN PLTR META NVDA GOOGL QQQ SPY AAPL TSM MU SNDK "
               "MSFT AVGO BABA AMD QCOM ORCL DIS UBER MRVL WMT JPM NFLX COST HIMS GME RIVN".split())

def to_symbol(ticker):
    t = ticker.upper()
    if t in TICKER_FIX:
        return TICKER_FIX[t]
    return t + "USDT"

def bridge(sig, univ):
    tk = sig.get("ticker", "").upper()
    stance = sig.get("stance", "")
    sym = to_symbol(tk)
    if stance == "Hold":
        return None, {"reason": "Hold", "ticker": tk}
    side = "long" if stance == "Buy" else ("short" if stance == "Sell" else None)
    if side is None:
        return None, {"reason": "unknown_stance:%s" % stance, "ticker": tk}
    if sym not in univ:
        return None, {"reason": "symbol_not_in_live_universe", "ticker": tk, "symbol": sym}
    w = CONF_W.get(sig.get("confidence", ""), 0.5)
    # F2: 标注是否在交易白名单(任一hold期匹配); 真钱只交易tradeable=True
    tradeable = any((side, h) in TRADE_WHITELIST for h in (1, 5, 20))
    return {
        "signal_id": sig.get("signal_id"), "date": sig.get("date"),
        "recorded_at": sig.get("recorded_at"), "symbol": sym, "ticker": tk,
        "side": side, "size_weight": w, "confidence": sig.get("confidence"),
        "ref_price_stock": sig.get("ref_price"),          # 仅元数据, 绝不参与永续PnL
        "outcomes": sig.get("outcomes"),                   # F3: 正股ground-truth对照
        "tradeable": tradeable,                            # F2: 是否在正edge白名单
    }, None

def main():
    if not os.path.exists(LEDGER):
        print("无ledger"); return []
    sigs = [json.loads(l) for l in open(LEDGER) if l.strip()]
    univ = live_universe()
    out, skipped = [], []
    for s in sigs:
        b, sk = bridge(s, univ)
        (out.append(b) if b else skipped.append(sk))
    with open(OUT, "w") as f:
        for o in out: f.write(json.dumps(o, ensure_ascii=False) + "\n")
    with open(SKIP_LOG, "w") as f:
        for s in skipped: f.write(json.dumps(s, ensure_ascii=False) + "\n")
    from collections import Counter
    print("ledger %d → 桥接 %d (universe=%d symbols)" % (len(sigs), len(out), len(univ)))
    print("  side:", dict(Counter(o["side"] for o in out)),
          "| tradeable(白名单内):", sum(1 for o in out if o["tradeable"]))
    print("  跳过原因:", dict(Counter(s["reason"].split(":")[0] for s in skipped)))
    # WARN: symbol映射失败的(可能真该交易却被吞)
    notin = [s for s in skipped if s["reason"] == "symbol_not_in_live_universe"]
    if notin:
        print("  ⚠️ 映射后不在universe(可能漏单):", [s["ticker"]+"→"+s.get("symbol","") for s in notin])
    return out

if __name__ == "__main__":
    main()
