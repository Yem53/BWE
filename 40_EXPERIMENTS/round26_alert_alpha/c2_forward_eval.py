#!/usr/bin/env python3
"""C2 forward paper 评估器 (跑在EC2, 每日一次, oneshot幂等)。
验证对象(终审幸存的唯一信号): oi_price_1h警报中 oi_chg>15% 的币,
未来24h是否持续跑输同日其它oi_price_1h警报币(同日配对超额, 历史240天=+0.97%/天)。
设计:
- FORWARD_START=2026-06-09 (处女holdout止于06-08, 之前数据一律不进forward账本)
- 只评估"已成熟"的日子: now >= 当日24:00 + 25h (24h持有+1h缓冲)
- 输出到 data/c2_forward/ (被现有scanner-rsync免费带回Mac)
- 每alert记录: net_short(不含资金费, 信号纯度) + fund_pct(单独记, 验证"资金费杀独立做空"结论)
- 非ASCII symbol用URL编码(修V3发现的回填器bug同类问题)
- 内存: 逐symbol流式, EC2 914MB内存安全
"""
import json, os, glob, time, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

BASE = "/home/ubuntu/bwe-scanner"
DATA = os.path.join(BASE, "data")
OUT = os.path.join(DATA, "c2_forward")
FAPI = "https://fapi.binance.com"
FORWARD_START = "2026-06-09"
COST_RT = 0.94          # 往返: 0.14费 + 0.8滑点
OI_THR = 15.0

os.makedirs(OUT, exist_ok=True)

def log(m):
    line = "[%s] %s" % (datetime.now(timezone.utc).strftime("%H:%M:%S"), m)
    print(line, flush=True)
    with open(os.path.join(OUT, "run.log"), "a") as f:
        f.write(line + "\n")

def get(path, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(FAPI + path, headers={"User-Agent": "Mozilla/5.0"})
            return json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
        except Exception as e:
            if "429" in str(e) and i < tries - 1:
                time.sleep(12); continue
            if i < tries - 1:
                time.sleep(3); continue
            raise

def klines_range(sym, t0, t1):
    """拉[t0,t1]的1m K线, 返回[(ot, close)]升序。symbol URL编码。"""
    enc = urllib.parse.quote(sym, safe="")
    out = []; cur = t0
    while cur < t1:
        kl = get("/fapi/v1/klines?symbol=%s&interval=1m&startTime=%d&endTime=%d&limit=1500" % (enc, cur, t1))
        if not kl: break
        for k in kl:
            out.append((int(k[0]), float(k[4])))
        nxt = int(kl[-1][0]) + 60000
        if nxt <= cur: break
        cur = nxt
        if len(kl) < 1500: break
        time.sleep(0.15)
    return out

def funding_sum(sym, t0, t1):
    """[t0,t1]内资金费率结算之和。费率正=多头付空头(空头收益+)。失败返回None。"""
    enc = urllib.parse.quote(sym, safe="")
    try:
        ev = get("/fapi/v1/fundingRate?symbol=%s&startTime=%d&endTime=%d&limit=100" % (enc, t0, t1))
        return sum(float(e["fundingRate"]) for e in ev)
    except Exception:
        return None

def eval_day(day):
    """评估某一天的全部oi_price_1h警报, 写c2fwd_<day>.jsonl + summary行。"""
    src = os.path.join(DATA, "alerts_%s.jsonl" % day)
    if not os.path.exists(src):
        log("%s: 无警报文件, 跳过" % day); return
    seen = set(); by_sym = {}
    n_raw = 0
    with open(src) as f:
        for l in f:
            try: a = json.loads(l)
            except: continue
            if a.get("window_type") != "oi_price_1h": continue
            key = (a["symbol"], a["ts_ms"])
            if key in seen: continue
            seen.add(key); n_raw += 1
            by_sym.setdefault(a["symbol"], []).append(a)
    log("%s: oi_price_1h警报 %d 条 / %d symbols" % (day, n_raw, len(by_sym)))
    recs = []; n_fail_sym = 0
    for sym, evs in sorted(by_sym.items()):
        ts_min = min(e["ts_ms"] for e in evs); ts_max = max(e["ts_ms"] for e in evs)
        try:
            kl = klines_range(sym, ts_min - 120000, ts_max + 1441 * 60000 + 600000)
        except Exception as e:
            log("  %s K线失败: %s" % (sym, str(e)[:80])); n_fail_sym += 1; continue
        if len(kl) < 100:
            n_fail_sym += 1; continue
        ots = [k[0] for k in kl]; cls = [k[1] for k in kl]
        import bisect
        for a in evs:
            ts = a["ts_ms"]
            i = bisect.bisect_right(ots, ts - 59999)
            while i < len(ots) and ots[i] + 60000 <= ts: i += 1
            if i >= len(ots) or ots[i] + 60000 - ts > 180000: continue
            entry = cls[i]; entry_ct = ots[i] + 60000
            target = entry_ct + 1440 * 60000
            j = bisect.bisect_left(ots, target)
            if j >= len(ots) or ots[j] - target > 300000 or entry <= 0: continue
            net_short = (entry - cls[j]) / entry * 100 - COST_RT
            fs = funding_sum(sym, entry_ct, target)
            time.sleep(0.1)
            recs.append({
                "date": day, "symbol": sym, "ts_ms": ts,
                "oi_chg": a.get("oi_chg_pct"), "is_c2": (a.get("oi_chg_pct") or 0) > OI_THR,
                "net_short": round(net_short, 4),
                "fund_pct": round(fs * 100, 4) if fs is not None else None,
            })
        time.sleep(0.15)
    # 写per-alert
    with open(os.path.join(OUT, "c2fwd_%s.jsonl" % day), "w") as f:
        for r in recs: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # 日度summary
    c2 = [r["net_short"] for r in recs if r["is_c2"]]
    ot = [r["net_short"] for r in recs if not r["is_c2"]]
    c2f = [r["net_short"] + r["fund_pct"] for r in recs if r["is_c2"] and r["fund_pct"] is not None]
    mean = lambda v: round(sum(v) / len(v), 4) if v else None
    summ = {"date": day, "n_c2": len(c2), "n_other": len(ot), "n_fail_sym": n_fail_sym,
            "c2_mean": mean(c2), "other_mean": mean(ot),
            "excess_day": round(mean(c2) - mean(ot), 4) if c2 and ot else None,
            "c2_mean_postfund": mean(c2f)}
    with open(os.path.join(OUT, "summary.jsonl"), "a") as f:
        f.write(json.dumps(summ, ensure_ascii=False) + "\n")
    log("%s 完成: %s" % (day, json.dumps(summ, ensure_ascii=False)))

def main():
    now = datetime.now(timezone.utc)
    done = set()
    sp = os.path.join(OUT, "summary.jsonl")
    if os.path.exists(sp):
        for l in open(sp):
            try: done.add(json.loads(l)["date"])
            except: pass
    d = datetime.strptime(FORWARD_START, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    while True:
        mature_at = d + timedelta(days=1) + timedelta(hours=25)   # 当日结束+25h
        if mature_at > now: break
        day = d.strftime("%Y-%m-%d")
        if day not in done:
            eval_day(day)
        d += timedelta(days=1)
    log("run done")

if __name__ == "__main__":
    main()
