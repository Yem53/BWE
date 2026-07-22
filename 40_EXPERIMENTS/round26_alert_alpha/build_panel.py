#!/usr/bin/env python3
"""round26: 警报×前向收益 共享面板。22万真实触发警报 join 归档K线+aux, 一次建好供全部角度筛选。
因果: 进场=fired后第一根已收盘1m bar的close; 前向从进场算。逐symbol流式, 内存<600MB。
dev: ts<=2026-05-15 | val: 05-16~05-28 | 处女holdout: 05-30+(K线回填后另建)。"""
import json, glob, sqlite3, time, os, sys
import numpy as np
from datetime import datetime, timezone
from collections import defaultdict

ALERTS = "/Volumes/T9/BWE/30_DATA/bwe_scanner_alerts"
ARCH = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/binance_futures_klines_archive.sqlite3"
AUX = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/binance_futures_aux_archive.sqlite3"
OUT = "/Volumes/T9/BWE/40_EXPERIMENTS/round26_alert_alpha/alert_panel.sqlite3"
LOG = "/Volumes/T9/BWE/40_EXPERIMENTS/round26_alert_alpha/build.log"

def logw(m):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), m)
    open(LOG, "a").write(line + "\n"); print(line, flush=True)

# ---------- 1. 载入警报(slim) ----------
logw("loading alerts...")
alerts_by_sym = defaultdict(list)
minute_count = defaultdict(int)      # 全市场每分钟警报数(广度)
hour_count = defaultdict(int)
seen = set()
n_raw = 0
for f in sorted(glob.glob(ALERTS + "/*.jsonl")):
    for l in open(f):
        try: d = json.loads(l)
        except: continue
        n_raw += 1
        key = (d["symbol"], d["ts_ms"], d["window_type"])
        if key in seen: continue
        seen.add(key)
        alerts_by_sym[d["symbol"]].append(d)
        minute_count[d["ts_ms"] // 60000] += 1
        hour_count[d["ts_ms"] // 3600000] += 1
seen = None
logw("alerts: raw=%d dedup=%d symbols=%d" % (n_raw, sum(len(v) for v in alerts_by_sym.values()), len(alerts_by_sym)))

# ---------- 2. BTC regime ----------
kcon = sqlite3.connect("file:%s?mode=ro" % ARCH, uri=True)
bt = kcon.execute("SELECT open_time_ms, close FROM klines_5m WHERE symbol='BTCUSDT' ORDER BY open_time_ms").fetchall()
ba = np.array(bt, float); btt = ba[:, 0]; bcc = ba[:, 1]; bt = None
def btc_reg(ts):
    i = np.searchsorted(btt, ts) - 1
    if i < 288: return 1
    r24 = (bcc[i] - bcc[i-288]) / bcc[i-288] * 100
    return 2 if r24 > 1 else (0 if r24 < -1 else 1)

# ---------- 3. aux loaders(per-symbol) ----------
acon = sqlite3.connect("file:%s?mode=ro" % AUX, uri=True)
def aux_asof(sym):
    fund = acon.execute("SELECT funding_time_ms, funding_rate FROM funding WHERE symbol=? ORDER BY funding_time_ms", (sym,)).fetchall()
    prem = acon.execute("SELECT open_time_ms, premium_pct FROM premium_5m WHERE symbol=? ORDER BY open_time_ms", (sym,)).fetchall()
    ls = acon.execute("SELECT ts_ms, toptrader_ls FROM metrics_5m WHERE symbol=? ORDER BY ts_ms", (sym,)).fetchall()
    def mk(rows):
        if not rows: return None, None
        a = np.array(rows, float); return a[:, 0], a[:, 1]
    return mk(fund), mk(prem), mk(ls)
def asof(ts, tx, vx):
    if tx is None: return None
    i = np.searchsorted(tx, ts) - 1
    return float(vx[i]) if i >= 0 else None

# ---------- 4. 建表 ----------
os.makedirs(os.path.dirname(OUT), exist_ok=True)
out = sqlite3.connect(OUT)
out.execute("""CREATE TABLE IF NOT EXISTS panel(
 symbol TEXT, ts_ms INTEGER, wt TEXT, chg REAL, oi_chg REAL, chg24 REAL, qv24 REAL,
 oi_usd REAL, mc REAL, oimc REAL, px_alert REAL,
 entry_ts INTEGER, entry_px REAL, lag_s REAL, bar_amp REAL, atr_pct REAL,
 dist_hi24 REAL, dist_lo24 REAL,
 f5 REAL, f15 REAL, f60 REAL, f240 REAL, f1440 REAL,
 mfe60 REAL, mae60 REAL, mfe240 REAL, mae240 REAL,
 n1h INTEGER, n24h INTEGER, mins_prev REAL, first_day INTEGER, xwin INTEGER,
 breadth_min INTEGER, breadth_1h INTEGER,
 fund REAL, prem REAL, ttls REAL, breg INTEGER, hour INTEGER, dow INTEGER,
 PRIMARY KEY(symbol, ts_ms, wt))""")
out.commit()

# ---------- 5. 逐symbol流式 ----------
syms = sorted(alerts_by_sym.keys(), key=lambda s: -len(alerts_by_sym[s]))
done = 0; rows_total = 0; skipped_nokl = 0
for sym in syms:
    evs = sorted(alerts_by_sym[sym], key=lambda d: d["ts_ms"])
    r = kcon.execute("SELECT open_time_ms, open, high, low, close FROM klines_1m WHERE symbol=? ORDER BY open_time_ms", (sym,)).fetchall()
    if len(r) < 200:
        skipped_nokl += len(evs); done += 1; continue
    a = np.array(r, float); r = None
    ot = a[:, 0]; hi = a[:, 2]; lo = a[:, 3]; cl = a[:, 4]
    n = len(cl)
    # ATR60(1m粒度的1h ATR%)
    pc = np.roll(cl, 1); pc[0] = cl[0]
    tr = np.maximum(hi - lo, np.maximum(np.abs(hi - pc), np.abs(lo - pc)))
    cs = np.cumsum(np.insert(tr, 0, 0.0))
    atr = np.full(n, np.nan); atr[60:] = (cs[60:n] - cs[:n-60]) / 60
    atrp = atr / cl * 100
    # 24h滚动高低(1440根)
    (ftx, ffx), (ptx, pfx), (ltx, lfx) = aux_asof(sym)
    rows = []
    # per-symbol 警报序列特征
    prev_ts = None; day_seen = set()
    ts_list = [e["ts_ms"] for e in evs]
    ts_arr = np.array(ts_list, float)
    for idx, e in enumerate(evs):
        ts = e["ts_ms"]
        # 进场: fired后第一根已收盘1m bar (close_time = ot+60000 > ts)
        i = int(np.searchsorted(ot, ts - 59999))   # 候选起点
        while i < n and ot[i] + 60000 <= ts:
            i += 1
        if i >= n or ot[i] + 60000 - ts > 180000:  # 3分钟内找不到bar=数据缺口
            continue
        entry_idx = i
        entry_ts = int(ot[i] + 60000); entry = cl[i]
        if not (entry > 0 and np.isfinite(entry)): continue
        lag_s = (entry_ts - ts) / 1000
        bar_amp = (hi[i] - lo[i]) / cl[i] * 100 if cl[i] > 0 else None
        def fwd(mins):
            j = entry_idx + mins
            return float((cl[j] - entry) / entry * 100) if j < n else None
        f5, f15, f60, f240, f1440 = fwd(5), fwd(15), fwd(60), fwd(240), fwd(1440)
        def mfemae(mins):
            j = min(entry_idx + 1 + mins, n)
            if j <= entry_idx + 1: return None, None
            mx = float((np.max(hi[entry_idx+1:j]) - entry) / entry * 100)
            mn = float((np.min(lo[entry_idx+1:j]) - entry) / entry * 100)
            return mx, mn
        mfe60, mae60 = mfemae(60); mfe240, mae240 = mfemae(240)
        # 24h位置
        k0 = max(0, entry_idx - 1440)
        h24 = np.max(hi[k0:entry_idx+1]); l24 = np.min(lo[k0:entry_idx+1])
        dist_hi = (entry - h24) / h24 * 100 if h24 > 0 else None
        dist_lo = (entry - l24) / l24 * 100 if l24 > 0 else None
        # 序列特征
        n1h = int(np.sum((ts_arr >= ts - 3600000) & (ts_arr < ts)))
        n24h = int(np.sum((ts_arr >= ts - 86400000) & (ts_arr < ts)))
        mins_prev = (ts - prev_ts) / 60000 if prev_ts else None
        prev_ts = ts
        dkey = ts // 86400000
        first_day = 1 if dkey not in day_seen else 0
        day_seen.add(dkey)
        xwin = 1 if any(abs(ts_list[j] - ts) <= 120000 and evs[j]["window_type"] != e["window_type"]
                        for j in range(max(0, idx-6), min(len(evs), idx+7)) if j != idx) else 0
        rows.append((sym, ts, e["window_type"], e.get("price_chg_pct"), e.get("oi_chg_pct"),
                     e.get("chg_24h_pct"), e.get("quote_vol_24h"), e.get("oi_usd"),
                     e.get("market_cap_usd"), e.get("oi_mc_ratio_pct"), e.get("price"),
                     entry_ts, float(entry), lag_s, bar_amp,
                     float(atrp[entry_idx]) if np.isfinite(atrp[entry_idx]) else None,
                     dist_hi, dist_lo, f5, f15, f60, f240, f1440,
                     mfe60, mae60, mfe240, mae240,
                     n1h, n24h, mins_prev, first_day, xwin,
                     minute_count.get(ts // 60000, 0), hour_count.get(ts // 3600000, 0),
                     asof(ts, ftx, ffx), asof(ts, ptx, pfx), asof(ts, ltx, lfx),
                     btc_reg(ts), datetime.fromtimestamp(ts/1000, timezone.utc).hour,
                     datetime.fromtimestamp(ts/1000, timezone.utc).weekday()))
    if rows:
        out.executemany("INSERT OR IGNORE INTO panel VALUES(%s)" % ",".join("?"*40), rows)
        out.commit(); rows_total += len(rows)
    a = ot = hi = lo = cl = atr = atrp = None
    done += 1
    if done % 50 == 0:
        logw("  %d/%d syms, %d rows" % (done, len(syms), rows_total))
logw("DONE: %d rows (skipped no-kline alerts: %d)" % (rows_total, skipped_nokl))
out.execute("CREATE INDEX IF NOT EXISTS ix_ts ON panel(ts_ms)"); out.commit()
logw("panel ready: %s" % OUT)
