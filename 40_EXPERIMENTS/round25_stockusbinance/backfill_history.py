#!/usr/bin/env python3
"""回填历史: 从 Binance fapi 拉 TradFi永续的历史1m K线 + 真实8h资金费 → 单独的 backfill 表。
解锁28条bridged信号的当天评估(否则只能等forward)。在EC2跑(Mac被墙451)。
诚实: 历史K线是永续真实价(非正股价); 资金费用fundingRate端点的真实8h结算序列。
回填表与forward采集表分开(source标注), 避免边界混淆。"""
import json, sqlite3, time, sys, urllib.request
from datetime import datetime, timezone

DB = "/home/ubuntu/stockusbinance/tradfi_capture.sqlite3"   # EC2路径; 与采集同库但独立表
BASE = "https://fapi.binance.com"
UA = {"User-Agent": "Mozilla/5.0"}

def get(path, t=20):
    r = urllib.request.Request(BASE + path, headers=UA)
    with urllib.request.urlopen(r, timeout=t) as resp:
        return json.loads(resp.read().decode())

def init(c):
    c.execute("""CREATE TABLE IF NOT EXISTS bf_klines_1m(
        symbol TEXT, ot INTEGER, o REAL, h REAL, l REAL, c REAL, v REAL, qv REAL, trades INTEGER,
        PRIMARY KEY(symbol, ot))""")
    c.execute("""CREATE TABLE IF NOT EXISTS bf_funding(
        symbol TEXT, funding_time INTEGER, funding_rate REAL,
        PRIMARY KEY(symbol, funding_time))""")
    c.commit()

def backfill_klines(c, sym, start_ms, end_ms):
    """分页拉1m K线 (1500根/请求)。"""
    n = 0; cur = start_ms
    while cur < end_ms:
        try:
            kl = get("/fapi/v1/klines?symbol=%s&interval=1m&startTime=%d&limit=1500" % (sym, cur))
        except Exception as e:
            print("  %s klines err @%d: %s" % (sym, cur, repr(e)[:60])); break
        if not kl:
            break
        for k in kl:
            ct = int(k[6])
            if ct > int(time.time()*1000):
                continue  # 未收盘bar不存
            c.execute("INSERT OR IGNORE INTO bf_klines_1m VALUES(?,?,?,?,?,?,?,?,?)",
                      (sym, int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]),
                       float(k[5]), float(k[7]), int(k[8])))
            n += 1
        cur = int(kl[-1][0]) + 60000
        if len(kl) < 1500:
            break
        time.sleep(0.15)
    c.commit(); return n

def backfill_funding(c, sym, start_ms):
    n = 0; cur = start_ms
    while True:
        try:
            fh = get("/fapi/v1/fundingRate?symbol=%s&startTime=%d&limit=1000" % (sym, cur))
        except Exception as e:
            print("  %s funding err: %s" % (sym, repr(e)[:60])); break
        if not fh:
            break
        for f in fh:
            c.execute("INSERT OR IGNORE INTO bf_funding VALUES(?,?,?)",
                      (sym, int(f["fundingTime"]), float(f["fundingRate"])))
            n += 1
        cur = int(fh[-1]["fundingTime"]) + 1
        if len(fh) < 1000:
            break
        time.sleep(0.15)
    c.commit(); return n

def main():
    c = sqlite3.connect(DB)
    init(c)
    # 回填窗口: 信号最早2026-05-22, 给前置buffer从05-15起到现在
    start = int(datetime(2026, 5, 15, tzinfo=timezone.utc).timestamp()*1000)
    end = int(time.time()*1000)
    # 信号涉及的标的(从bridged读) + 几个核心
    bridged = "/home/ubuntu/stockusbinance/bridged_signals.jsonl"
    import os
    syms = set()
    if os.path.exists(bridged):
        for l in open(bridged):
            if l.strip(): syms.add(json.loads(l)["symbol"])
    syms |= {"NVDAUSDT","MUUSDT","QQQUSDT","TSLAUSDT","METAUSDT","AMZNUSDT","AVGOUSDT","GOOGLUSDT","TSMUSDT","MRVLUSDT"}
    syms = sorted(syms)
    print("回填 %d 标的, 窗口 %s -> now" % (len(syms), datetime.fromtimestamp(start/1000,timezone.utc).strftime("%Y-%m-%d")))
    for s in syms:
        nk = backfill_klines(c, s, start, end)
        nf = backfill_funding(c, s, start)
        sp = c.execute("SELECT MIN(ot),MAX(ot) FROM bf_klines_1m WHERE symbol=?", (s,)).fetchone()
        first = datetime.fromtimestamp(sp[0]/1000,timezone.utc).strftime("%m-%d") if sp[0] else "无"
        print("  %-12s klines+%-6d funding+%-3d 起于%s" % (s, nk, nf, first))
    print("回填完成。")

if __name__ == "__main__":
    main()
