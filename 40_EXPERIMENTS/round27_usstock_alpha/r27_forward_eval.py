#!/usr/bin/env python3
"""Round27 forward记录器(EC2每日): D_PEAD_rxn_sign_h2 + E_afterhours_drift_v1 两条冻结规则的paper账本。
不下真单。规则冻结于2026-07-03(见ROUND27_PROTOCOL.md), 含verify要求的3处修正:
- 信号用15:55 ET perp价(vs pre_report收盘)算reaction代理(perp与正股reaction相关0.9996), UW reaction仅记录对照
- 流动性下限: 进场±5min成交额≥$50k, 否则记录但标not_executable
- perp须在report_date时已有≥7天K线
FORWARD_START=2026-06-16(dev/val用到06-15, 之后全是处女forward)。
每日流程: 1)顶补K线(调bf_full_tradfi.py, 断点续传) 2)UW拉近7天财报 3)评估已成熟事件 4)账本+记分JSON
"""
import json, os, sqlite3, time, urllib.request, subprocess
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo

BASE = "/home/ubuntu/stockusbinance"
DB = BASE + "/tradfi_full_history.sqlite3"
OUT = BASE + "/r27_forward"
ET = ZoneInfo("America/New_York")
FORWARD_START = "2026-06-16"
os.makedirs(OUT, exist_ok=True)

def env():
    d = {}
    for l in open(BASE + "/.env"):
        if "=" in l and not l.startswith("#"):
            k, v = l.strip().split("=", 1); d[k] = v
    return d
E = env()

def log(m):
    line = "[%s] %s" % (datetime.now(timezone.utc).strftime("%m-%d %H:%M"), m)
    print(line, flush=True)
    open(OUT + "/run.log", "a").write(line + "\n")

def uw(path):
    req = urllib.request.Request("https://api.unusualwhales.com/api" + path,
        headers={"Authorization": "Bearer " + E["UNUSUAL_WHALES_API_KEY"], "User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read().decode())

# ---- 1) 顶补K线 ----
log("顶补K线...")
subprocess.run(["python3", "/tmp/bf_full_tradfi.py"], capture_output=True, timeout=3000)

kc = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
def px_win(sym, ts0, ts1):
    return kc.execute("SELECT ot, cl, qv FROM klines_1m WHERE symbol=? AND ot>=? AND ot<=? ORDER BY ot",
                      (sym, ts0, ts1)).fetchall()
def px_at(sym, ts, tol_min=10, fwd=True):
    if fwd:
        r = kc.execute("SELECT ot, cl FROM klines_1m WHERE symbol=? AND ot>=? ORDER BY ot LIMIT 1", (sym, ts)).fetchone()
        if r and r[0] - ts <= tol_min*60000: return r
    else:
        r = kc.execute("SELECT ot, cl FROM klines_1m WHERE symbol=? AND ot<=? ORDER BY ot DESC LIMIT 1", (sym, ts)).fetchone()
        if r and ts - r[0] <= tol_min*60000: return r
    return None
def listed_before(sym, ts_ms, days=7):
    r = kc.execute("SELECT MIN(ot) FROM klines_1m WHERE symbol=?", (sym,)).fetchone()
    return r and r[0] and (ts_ms - r[0]) >= days*86400000
def et_ts(dstr, hh, mm):
    d = datetime.strptime(dstr, "%Y-%m-%d").replace(hour=hh, minute=mm, tzinfo=ET)
    return int(d.timestamp()*1000)
def next_trading_day(dstr, n=1):
    HOL = {"2026-07-03","2026-09-07","2026-11-26","2026-12-25"}
    d = datetime.strptime(dstr, "%Y-%m-%d").date()
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5 and d.isoformat() not in HOL: n -= 1
    return d.isoformat()
def ew_ret(ts0, ts1, exclude):
    rows = kc.execute("""SELECT symbol FROM (SELECT symbol, MAX(qv) q FROM klines_1m
        WHERE ot BETWEEN ? AND ? GROUP BY symbol) ORDER BY q DESC LIMIT 30""", (ts0, ts1)).fetchall()
    rets = []
    for (s,) in rows:
        if s == exclude: continue
        a = px_at(s, ts0, 15); b = px_at(s, ts1, 15, fwd=False)
        if a and b and a[1] > 0: rets.append((b[1]-a[1])/a[1]*100)
    return sum(rets)/len(rets) if rets else None

# ---- 2) UW近7天财报 ----
seen = set()
EVP = OUT + "/events.jsonl"
if os.path.exists(EVP):
    for l in open(EVP):
        try: e0 = json.loads(l); seen.add((e0["symbol"], e0["report_date"]))
        except: pass
newn = 0
with open(EVP, "a") as f:
    for back in range(9):
        d = (date.today() - timedelta(days=back))
        if d.weekday() >= 5: continue
        for sess in ("afterhours", "premarket"):
            try: r = uw("/earnings/%s?date=%s&limit=200" % (sess, d.isoformat()))
            except Exception as ex: log("UW err %s: %s" % (d, str(ex)[:60])); continue
            for ev in (r.get("data") or []):
                key = (ev.get("symbol"), ev.get("report_date"))
                if key in seen: continue
                seen.add(key); ev["_session"] = sess
                f.write(json.dumps(ev) + "\n"); newn += 1
            time.sleep(0.5)
log("UW新事件: %d" % newn)

# ---- 3) 评估成熟事件 ----
LP = OUT + "/ledger_D.jsonl"; LE = OUT + "/ledger_E.jsonl"
done_D = set(); done_E = set()
for p, s in ((LP, done_D), (LE, done_E)):
    if os.path.exists(p):
        for l in open(p):
            try: e0 = json.loads(l); s.add((e0["symbol"], e0["report_date"]))
            except: pass
perps = set(r[0] for r in kc.execute("SELECT DISTINCT symbol FROM klines_1m"))
today = date.today().isoformat()
evs = [json.loads(l) for l in open(EVP)]
fD = open(LP, "a"); fE = open(LE, "a")
nD = nE = 0
for ev in evs:
    sym = (ev.get("symbol") or "").upper() + "USDT"
    rd = ev.get("report_date")
    if not rd or rd < FORWARD_START or sym not in perps: continue
    rt_ms = et_ts(rd, 16, 0)
    if not listed_before(sym, rt_ms): continue
    sess = ev.get("_session") or ("premarket" if ev.get("report_time") == "premarket" else "afterhours")
    # D: 锚点日 = premarket报→当日 / afterhours报→次交易日; 入场=锚点16:00, 出场=+2交易日16:00
    anchor = rd if sess == "premarket" else next_trading_day(rd)
    exit_day = next_trading_day(anchor, 2)
    key = (ev.get("symbol"), rd)
    if key not in done_D and exit_day < today:
        sig_ts = et_ts(anchor, 15, 55)
        pre = px_at(sym, et_ts(rd, 15, 55) - (0 if sess == "afterhours" else 86400000), 30, fwd=False)
        sig = px_at(sym, sig_ts, 10, fwd=False)
        ein = px_at(sym, et_ts(anchor, 16, 0), 10, fwd=False)
        eout = px_at(sym, et_ts(exit_day, 16, 0), 10, fwd=False)
        if pre and sig and ein and eout and pre[1] > 0 and ein[1] > 0:
            rx = (sig[1]-pre[1])/pre[1]
            side = 1 if rx > 0 else -1
            raw = side * (eout[1]-ein[1])/ein[1]*100
            liq = sum(x[2] for x in px_win(sym, ein[0]-5*60000, ein[0]+5*60000))
            ew = ew_ret(ein[0], eout[0], sym)
            rec = {"symbol": ev.get("symbol"), "report_date": rd, "anchor": anchor, "session": sess,
                   "rx_proxy": round(rx*100,3), "uw_reaction": ev.get("reaction"), "side": side,
                   "raw_net": round(raw-0.12,3), "ew_win": round(ew,3) if ew is not None else None,
                   "stripped": round(raw-0.12-(side*ew if ew is not None else 0),3),
                   "liq10m": round(liq), "executable": liq >= 50000}
            fD.write(json.dumps(rec)+"\n"); nD += 1; done_D.add(key)
    # E: afterhours & |r22|>=2% → 22:00顺势, 次日开盘平
    if sess == "afterhours" and key not in done_E and next_trading_day(rd) < today:
        c16 = px_at(sym, et_ts(rd, 16, 0), 10, fwd=False)
        c22 = px_at(sym, et_ts(rd, 22, 0), 10, fwd=False)
        o930 = px_at(sym, et_ts(next_trading_day(rd), 9, 30), 10)
        if c16 and c22 and o930 and c16[1] > 0 and c22[1] > 0:
            r22 = (c22[1]-c16[1])/c16[1]*100
            if abs(r22) >= 2.0:
                side = 1 if r22 > 0 else -1
                raw = side*(o930[1]-c22[1])/c22[1]*100
                liq = sum(x[2] for x in px_win(sym, c22[0]-5*60000, c22[0]+5*60000))
                rec = {"symbol": ev.get("symbol"), "report_date": rd, "r22": round(r22,3), "side": side,
                       "raw_net": round(raw-0.24,3), "liq10m": round(liq), "executable": liq >= 25000}
                fE.write(json.dumps(rec)+"\n"); nE += 1; done_E.add(key)
fD.close(); fE.close()
log("新增 D账本: %d | E账本: %d" % (nD, nE))

# ---- 3b) J族: 结算V形 (J_settle_v1冻结: |预测费率|>=10bp → T-1min顺费率方向taker进, T+15min出) ----
# 预测费率来源=collector实时采样(tradfi_capture.sqlite3 funding表, 60s一采) — T-60s前最后一条=当时真实可知
LJ = OUT + "/ledger_J.jsonl"
done_J = set()
if os.path.exists(LJ):
    for l in open(LJ):
        try: e0 = json.loads(l); done_J.add((e0["symbol"], e0["settle_ts"]))
        except: pass
cap = sqlite3.connect("file:%s/tradfi_capture.sqlite3?mode=ro" % BASE, uri=True)
now_ms = int(time.time()*1000)
fJ = open(LJ, "a"); nJ = 0
t0 = int(datetime.strptime(FORWARD_START, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()*1000)
T = (t0 // 28800000 + 1) * 28800000
while T < now_ms - 30*60000:
    for sym in sorted(perps):
        if (sym, T) in done_J: continue
        pr = cap.execute("SELECT funding_rate FROM funding WHERE symbol=? AND ts<=? AND ts>=? ORDER BY ts DESC LIMIT 1",
                         (sym, T-60000, T-1800000)).fetchone()
        if not pr or pr[0] is None or abs(pr[0]) < 0.0010: continue
        ein = px_at(sym, T-60000, 5, fwd=False)
        eout = px_at(sym, T+15*60000, 5, fwd=False)
        if not (ein and eout and ein[1] > 0): continue
        side = 1 if pr[0] > 0 else -1
        settled = kc.execute("SELECT funding_rate FROM funding WHERE symbol=? AND funding_time BETWEEN ? AND ?",
                             (sym, T-300000, T+300000)).fetchone()
        pay = abs(settled[0])*100 if settled and settled[0] is not None else abs(pr[0])*100
        raw = side*(eout[1]-ein[1])/ein[1]*100
        fJ.write(json.dumps({"symbol": sym.replace("USDT",""), "settle_ts": T,
            "settle_utc": datetime.fromtimestamp(T/1000, timezone.utc).strftime("%m-%d %H:00"),
            "pred_rate_bp": round(pr[0]*1e4,1), "side": side,
            "px_move": round(raw,3), "funding_paid": round(pay,3),
            "net": round(raw - pay - 0.12, 3)})+"\n"); nJ += 1; done_J.add((sym, T))
    T += 28800000
fJ.close(); log("新增 J账本: %d" % nJ)

# ---- 3c) H族: 新上市day1空 (H_list_d1_short_v1: day0收盘空→day1收盘平, 空头收资金费) ----
LH = OUT + "/ledger_H.jsonl"
done_H = set()
if os.path.exists(LH):
    for l in open(LH):
        try: done_H.add(json.loads(l)["symbol"])
        except: pass
fH = open(LH, "a"); nH = 0
for sym in sorted(perps):
    if sym in done_H: continue
    r0 = kc.execute("SELECT MIN(ot) FROM klines_1m WHERE symbol=?", (sym,)).fetchone()
    if not r0 or not r0[0]: continue
    if r0[0] < t0: continue   # 只记forward期上市
    d0 = datetime.fromtimestamp(r0[0]/1000, timezone.utc).astimezone(ET).strftime("%Y-%m-%d")
    d1 = next_trading_day(d0)
    if d1 >= today: continue  # 未成熟
    ein = px_at(sym, et_ts(d0, 16, 0), 10, fwd=False)
    eout = px_at(sym, et_ts(d1, 16, 0), 10, fwd=False)
    if not (ein and eout and ein[1] > 0) or ein[0] <= r0[0]: continue
    raw = (ein[1]-eout[1])/ein[1]*100   # short
    fs = kc.execute("SELECT SUM(funding_rate) FROM funding WHERE symbol=? AND funding_time BETWEEN ? AND ?",
                    (sym, ein[0], eout[0])).fetchone()
    frecv = (fs[0] or 0)*100            # short收正费率
    fH.write(json.dumps({"symbol": sym.replace("USDT",""), "day0": d0,
        "raw_short": round(raw,3), "fund_recv": round(frecv,3),
        "net": round(raw + frecv - 0.18, 3)})+"\n"); nH += 1; done_H.add(sym)
fH.close(); log("新增 H账本: %d" % nH)

# ---- 4) 记分 ----
def score(path, name, n_gate, extra=""):
    if not os.path.exists(path): return
    rows = [json.loads(l) for l in open(path)]
    if not rows: log("%s: 0事件" % name); return
    import statistics as st
    key = "stripped" if name == "D" else "raw_net"
    v = [r[key] for r in rows if r.get(key) is not None]
    ex = [r for r in rows if r.get("executable")]
    if v:
        log("%s: n=%d(可执行%d) 净均%+.2f%% 中%+.2f%% 胜%.0f%% | 门n≥%d%s" % (
            name, len(v), len(ex), st.mean(v), st.median(v),
            100*sum(1 for x in v if x > 0)/len(v), n_gate, extra))
score(LP, "D", 15, " 过门=剥β净>0∧两侧非负∧1.5×成本")
score(LE, "E", 10, " kill=净≤0或胜<60%")
def score_simple(path, name, key, gate):
    if not os.path.exists(path): return
    rows = [json.loads(l) for l in open(path)]
    v = [r[key] for r in rows if r.get(key) is not None]
    if not v: log("%s: 0事件" % name); return
    import statistics as st
    log("%s: n=%d 净均%+.3f%% 中%+.3f%% 胜%.0f%% | %s" % (
        name, len(v), st.mean(v), st.median(v), 100*sum(1 for x in v if x>0)/len(v), gate))
score_simple(LJ, "J", "net", "过门=n≥50后净>0(含付费)∧按结算簇稳")
score_simple(LH, "H", "net", "过门=n≥15后1.5×成本净>0∧≥60%批次负; kill=n≥10净≤0")
log("run done")
