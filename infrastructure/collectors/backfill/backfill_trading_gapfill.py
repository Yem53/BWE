import json, os, sqlite3, time, threading
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

DB = "/Volumes/T9_HOT/binance_collectors_runtime/binance_futures_1m.sqlite3"
LOG = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/logs/overnight_trading_gapfill.log"
BASE = "https://fapi.binance.com"
PROXY = "http://127.0.0.1:7897"
INTERVALS = ['1m','3m','5m','15m','1h']
INTERVAL_MS = {'1m':60_000,'3m':180_000,'5m':300_000,'15m':900_000,'1h':3_600_000}
DAYS = 30
KLINE_LIMIT = 1500
WORKERS = 2
RATE_PER_WORKER = 700

print_lock = threading.Lock()
def log(d):
    d['ts_ms'] = int(time.time()*1000)
    with print_lock:
        line = json.dumps(d, ensure_ascii=False)
        print(line, flush=True)
        with open(LOG,'a') as f: f.write(line+'\n')

class RL:
    def __init__(self, b):
        self.b=b; self.t=float(b); self.last=time.time(); self.lock=threading.Lock()
    def acquire(self,w):
        while True:
            with self.lock:
                now=time.time(); el=now-self.last
                self.t = min(self.b, self.t + el*(self.b/60))
                self.last = now
                if self.t >= w:
                    self.t -= w; return
                wait = (w-self.t)/(self.b/60)
            time.sleep(min(wait, 5))

def hget(url,w,rl,r=6):
    h = urllib.request.ProxyHandler({'http':PROXY,'https':PROXY})
    op = urllib.request.build_opener(h)
    req = urllib.request.Request(url, headers={'User-Agent':'Hermes/1.0'})
    bf=1.0
    for a in range(r):
        rl.acquire(w)
        try:
            with op.open(req,timeout=20) as rs:
                if rs.status==200: return json.loads(rs.read())
        except urllib.error.HTTPError as e:
            if e.code==418: time.sleep(min(300,bf*30)); bf*=2
            elif e.code==429: time.sleep(min(60,bf*5)); bf*=2
            elif e.code in (400,404): return None
            else: time.sleep(bf); bf*=2
        except Exception as e:
            log({'event':'net_err','err':str(e)[:80]})
            time.sleep(bf); bf*=2
    return None

def get_trading_syms(rl):
    info = hget(f"{BASE}/fapi/v1/exchangeInfo", 1, rl)
    if not info: return []
    return sorted([s['symbol'] for s in info.get('symbols',[])
                   if s.get('contractType')=='PERPETUAL'
                   and s.get('quoteAsset')=='USDT'
                   and s.get('status')=='TRADING'
                   and s['symbol'].isascii()])

def gap_fetch(conn, rl, sym, itv, status):
    end_ms = int(time.time()*1000)
    target_start = end_ms - DAYS*86400*1000
    row = conn.execute("SELECT MIN(open_time_ms),MAX(open_time_ms) FROM klines_1m WHERE symbol=? AND interval=?", (sym,itv)).fetchone()
    emin, emax = row if row else (None,None)
    gaps = []
    if emin is None:
        gaps.append((target_start, end_ms))
    else:
        if target_start < emin: gaps.append((target_start, emin-1))
        if emax < end_ms - INTERVAL_MS[itv]: gaps.append((emax + INTERVAL_MS[itv], end_ms))
    total = 0
    for g_start, g_end in gaps:
        cur = g_start
        while cur < g_end:
            url = f"{BASE}/fapi/v1/klines?symbol={sym}&interval={itv}&startTime={cur}&endTime={g_end}&limit={KLINE_LIMIT}"
            ks = hget(url, 2, rl)
            if not ks: break
            rows=[]
            now=int(time.time()*1000)
            for k in ks:
                try:
                    rows.append((sym,itv,int(k[0]),int(k[6]),float(k[1]),float(k[2]),float(k[3]),float(k[4]),float(k[5]),
                        float(k[7]),int(k[8]),float(k[9]),float(k[10]),str(k[11]),'PERPETUAL',status,0,now,''))
                except (ValueError,IndexError,TypeError): continue
            if rows:
                rs = conn.executemany('''INSERT OR IGNORE INTO klines_1m
                    (symbol,interval,open_time_ms,close_time_ms,open,high,low,close,volume,
                     quote_volume,trade_count,taker_buy_base_volume,taker_buy_quote_volume,
                     ignore_value,contract_type,status,listing_ts_ms,collected_at_ms,raw_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', rows)
                conn.commit()
                total += rs.rowcount
            last = int(ks[-1][0])
            if len(ks) < KLINE_LIMIT: break
            cur = last + INTERVAL_MS[itv]
    return total

_ctr = {}
_clk = threading.Lock()
def worker(sym, rl, wid):
    conn = sqlite3.connect(DB, timeout=180)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA wal_autocheckpoint=2000")
    t0=time.time(); total=0
    for itv in INTERVALS:
        total += gap_fetch(conn, rl, sym, itv, 'TRADING')
    with _clk:
        _ctr[wid] = _ctr.get(wid,0)+1
        n = _ctr[wid]
    if n % 10 == 0:
        try: conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        except: pass
    conn.close()
    log({'event':'sym_done','sym':sym,'inserted':total,'elapsed':round(time.time()-t0,1)})

def main():
    boot_rl = RL(60)
    syms = get_trading_syms(boot_rl)
    log({'event':'start','workers':WORKERS,'rate_per_worker':RATE_PER_WORKER,'syms':len(syms)})
    rls = [RL(RATE_PER_WORKER) for _ in range(WORKERS)]
    done=0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs={}
        for i,s in enumerate(syms):
            wid = i % WORKERS
            futs[ex.submit(worker, s, rls[wid], wid)] = s
        for f in as_completed(futs):
            try: f.result(); done+=1
            except Exception as e: log({'event':'err','sym':futs[f],'err':str(e)[:100]})
            if done % 25 == 0:
                log({'event':'progress','done':done,'total':len(syms)})
    log({'event':'done','done':done})
if __name__=='__main__': main()
