#!/usr/bin/env python3
"""方向①面板: stockusbot radar每日打分 → 因果对齐的永续前向收益。
中性多空回测用。一次建好供工作流多agent共享。
因果铁律: 进场 = radar日期+1天 00:00 UTC 后第一根永续bar(radar最晚21:10生成, 次日0点必已可知, 杜绝forward-ahead)。
前向: 进场后 1/2/3/5 天(1440min粒度)的close收益。市场代理=当日全universe等权(beta中性化用)。"""
import json, glob, sqlite3, numpy as np
from datetime import datetime, timezone, timedelta

ST = "/Users/ye/.hermes/profiles/stockusbot/state/radar"
KDB = "/Volumes/T9/BWE/40_EXPERIMENTS/round25_stockusbinance/radar_klines.sqlite3"
OUT = "/Volumes/T9/BWE/40_EXPERIMENTS/round25_stockusbinance/radar_panel.jsonl"

kc = sqlite3.connect("file:%s?mode=ro" % KDB, uri=True)
KL = {}
def kl(sym):
    if sym not in KL:
        r = kc.execute("SELECT ot,c FROM klines_1m WHERE symbol=? ORDER BY ot", (sym,)).fetchall()
        KL[sym] = (np.array([x[0] for x in r], dtype=np.int64), np.array([x[1] for x in r], float)) if r else None
    return KL[sym]

def px_at_or_after(sym, ts_ms, tol_min=180):
    a = kl(sym)
    if a is None: return None, None
    ot, cl = a
    i = int(np.searchsorted(ot, ts_ms))
    if i >= len(ot) or ot[i] - ts_ms > tol_min*60000: return None, None
    if cl[i] <= 0 or not np.isfinite(cl[i]): return None, None
    return int(ot[i]), float(cl[i])

def fwd(sym, entry_ts, days):
    a = kl(sym)
    if a is None: return None
    ot, cl = a
    _, e = px_at_or_after(sym, entry_ts, 0) if False else (None, None)
    i = int(np.searchsorted(ot, entry_ts))
    if i >= len(ot): return None
    entry = cl[i]
    tgt = ot[i] + days*1440*60000
    j = int(np.searchsorted(ot, tgt))
    if j >= len(ot) or ot[j]-tgt > 300*60000 or entry <= 0: return None
    return (cl[j]-entry)/entry*100

rows = []
for f in sorted(glob.glob(ST + "/*radar.json")):
    date = f.split("/")[-1][:10]
    try:
        d = json.load(open(f))
    except: continue
    rdr = d.get("radar", [])
    # 进场: 次日00:00 UTC
    entry_day = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
    entry_ms = int(entry_day.timestamp()*1000)
    day_rows = []
    for x in rdr:
        sym = x["ticker"].upper() + "USDT"
        ets, entry = px_at_or_after(sym, entry_ms)
        if entry is None: continue   # 不可交易/无K线
        rec = {
            "date": date, "ticker": x["ticker"].upper(), "symbol": sym,
            "combined_score": x.get("combined_score"), "tech_score": x.get("tech_score"),
            "sentiment": x.get("sentiment"), "momentum_20d_pct": x.get("momentum_20d_pct"),
            "theme": x.get("theme"), "flag": x.get("flag"),
            "entry_ts": ets, "entry_px": entry,
            "f1": fwd(sym, ets, 1), "f2": fwd(sym, ets, 2), "f3": fwd(sym, ets, 3), "f5": fwd(sym, ets, 5),
        }
        day_rows.append(rec)
    # 市场代理: 当日等权均(每个horizon), 写进每行供beta中性化
    for h in ("f1","f2","f3","f5"):
        vals = [r[h] for r in day_rows if r[h] is not None]
        mkt = float(np.mean(vals)) if vals else None
        for r in day_rows:
            r["mkt_"+h] = mkt
    rows += day_rows

with open(OUT, "w") as out:
    for r in rows: out.write(json.dumps(r, ensure_ascii=False) + "\n")

# 摘要
from collections import Counter
bd = Counter(r["date"] for r in rows)
print("面板: %d 行 / %d 天 / %d 标的" % (len(rows), len(bd), len(set(r["symbol"] for r in rows))))
print("每天可交易名数: 中位 %.0f, 范围 %d~%d" % (
    np.median(list(bd.values())), min(bd.values()), max(bd.values())))
nf5 = sum(1 for r in rows if r["f5"] is not None)
print("有f5前向(完整5天)的行: %d (其余因数据末端截断)" % nf5)
print("写出:", OUT)
