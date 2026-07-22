#!/usr/bin/env python3
"""stockusbinance 采集器: 80只EQUITY永续 + pre-IPO的 1m K线 + 盘口快照 + 资金费 → sqlite。
历史只有6周(2026-01起), 故 forward 每分钟都是未来回测的样本——越早跑越值钱。
设计: 单进程循环, 每60s一轮(REST批量), 内存轻, 限速友好, 断点续采(INSERT OR IGNORE)。
跑在EC2(api.binance.com不被墙)更稳; Mac用 fapi.binance.com(实测可达)。"""
import json, sqlite3, time, os, urllib.request, sys
from datetime import datetime, timezone

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tradfi_capture.sqlite3")
# Mac可达 fapi.binance.com; EC2也可用api.binance.com。默认fapi(两端通)
BASE = os.environ.get("TRADFI_BASE", "https://fapi.binance.com")
UA = {"User-Agent": "Mozilla/5.0"}
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "collector.log")

def get(path, t=15):
    r = urllib.request.Request(BASE + path, headers=UA)
    with urllib.request.urlopen(r, timeout=t) as resp:
        return json.loads(resp.read().decode())

def logw(m):
    line = "[%s] %s" % (datetime.now(timezone.utc).strftime("%F %T"), m)
    with open(LOG, "a") as f: f.write(line + "\n")
    print(line, flush=True)

def init_db():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS klines_1m(
        symbol TEXT, ot INTEGER, o REAL, h REAL, l REAL, c REAL, v REAL, qv REAL, trades INTEGER,
        PRIMARY KEY(symbol, ot))""")
    c.execute("""CREATE TABLE IF NOT EXISTS book(
        symbol TEXT, ts INTEGER, bid REAL, bidqty REAL, ask REAL, askqty REAL, mid REAL, spread_bp REAL,
        PRIMARY KEY(symbol, ts))""")
    c.execute("""CREATE TABLE IF NOT EXISTS funding(
        symbol TEXT, ts INTEGER, mark REAL, index_px REAL, funding_rate REAL, next_funding INTEGER,
        PRIMARY KEY(symbol, ts))""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_book ON book(symbol, ts)")
    c.commit()
    return c

def universe():
    ei = get("/fapi/v1/exchangeInfo")
    return [s["symbol"] for s in ei["symbols"] if s.get("underlyingType") == "EQUITY"]

def collect_once(c, syms):
    nk = nb = nf = 0
    for s in syms:
        try:
            # 1m klines (last 3); 只存已收盘bar (close_time<=now), 防partial冻结
            kl = get("/fapi/v1/klines?symbol=%s&interval=1m&limit=3" % s)
            now_ms = int(time.time()*1000)
            for k in kl:
                if int(k[6]) > now_ms:
                    continue   # bar未收盘, 跳过(下轮收盘后用REPLACE写终值)
                c.execute("INSERT OR REPLACE INTO klines_1m VALUES(?,?,?,?,?,?,?,?,?)",
                          (s, int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]),
                           float(k[5]), float(k[7]), int(k[8])))
                nk += 1
            # book ticker (best bid/ask)
            bk = get("/fapi/v1/ticker/bookTicker?symbol=%s" % s)
            bid = float(bk["bidPrice"]); ask = float(bk["askPrice"])
            mid = (bid + ask) / 2 if bid and ask else 0
            sp = (ask - bid) / mid * 1e4 if mid else 0
            c.execute("INSERT INTO book VALUES(?,?,?,?,?,?,?,?)",
                      (s, int(time.time()*1000), bid, float(bk["bidQty"]), ask, float(bk["askQty"]), mid, sp))
            nb += 1
            # premium/funding (mark, index, funding)
            pr = get("/fapi/v1/premiumIndex?symbol=%s" % s)
            c.execute("INSERT OR IGNORE INTO funding VALUES(?,?,?,?,?,?)",
                      (s, int(time.time()*1000), float(pr.get("markPrice", 0)),
                       float(pr.get("indexPrice", 0)), float(pr.get("lastFundingRate", 0)),
                       int(pr.get("nextFundingTime", 0))))
            nf += 1
            time.sleep(0.05)
        except Exception as e:
            logw("  %s err: %s" % (s, repr(e)[:80]))
    c.commit()
    return nk, nb, nf

def main():
    c = init_db()
    syms = universe()
    logw("collector start: %d EQUITY perps, db=%s" % (len(syms), DB))
    loops = 0
    while True:
        t0 = time.time()
        # 每30轮(~30min)刷新universe(捕获每天新上的合约)
        if loops % 30 == 0 and loops > 0:
            try: syms = universe(); logw("universe refreshed: %d" % len(syms))
            except Exception: pass
        nk, nb, nf = collect_once(c, syms)
        loops += 1
        if loops % 10 == 0:
            logw("loop %d: %d klines, %d books, %d funding (%.0fs)" % (loops, nk, nb, nf, time.time()-t0))
        sleep = max(5, 60 - (time.time() - t0))
        time.sleep(sleep)

if __name__ == "__main__":
    if "--once" in sys.argv:
        c = init_db(); syms = universe()
        print("universe:", len(syms))
        print("collected:", collect_once(c, syms[:5]))  # smoke test 5 syms
    else:
        main()
