#!/usr/bin/env python3
"""radar forward 记录器(Mac, launchd每日跑, 幂等)。
把"已成熟"的radar日期(date+1进场 + 5d持有 + 缓冲全部过去)的横截面面板行
追加到 radar_panel_forward.jsonl。价格用实时同步的采集库(EC2 collector→tradfi_capture_ec2)。
进场=radar日+1天00:00UTC首根永续bar(Codex确认因果, 不毁信号)。不实盘下单。
in-sample(<=2026-06-15)已在 radar_panel.jsonl; 本文件只攒 06-16+ 的 OOS 行。"""
import json, glob, sqlite3, os, numpy as np
from datetime import datetime, timezone, timedelta

ST = "/Users/ye/.hermes/profiles/stockusbot/state/radar"
KDB = "/Volumes/T9/BWE/40_EXPERIMENTS/round25_stockusbinance/tradfi_capture_ec2.sqlite3"  # 实时同步采集库
OUT = "/Volumes/T9/BWE/40_EXPERIMENTS/round25_stockusbinance/radar_panel_forward.jsonl"
IS_CUTOFF = "2026-06-15"   # in-sample止于此, 之后才记forward
HOLD_BUF_DAYS = 6          # 进场(+1) + f5(5) → date+6天后才成熟, 再加缓冲

def kc():
    return sqlite3.connect("file:%s?mode=ro" % KDB, uri=True) if os.path.exists(KDB) else None

def main():
    c = kc()
    if c is None:
        print("采集库未同步, 跳过"); return
    # 采集库表名/列名兼容
    cols = [r[1] for r in c.execute("PRAGMA table_info(klines_1m)")]
    otc = "ot" if "ot" in cols else "open_time_ms"
    clc = "c" if "c" in cols else "close"
    KL = {}
    def kl(sym):
        if sym not in KL:
            r = c.execute("SELECT %s,%s FROM klines_1m WHERE symbol=? ORDER BY %s" % (otc, clc, otc), (sym,)).fetchall()
            KL[sym] = (np.array([x[0] for x in r], np.int64), np.array([x[1] for x in r], float)) if r else None
        return KL[sym]
    def px_after(sym, ts):
        a = kl(sym)
        if a is None: return None, None
        ot, cl = a; i = int(np.searchsorted(ot, ts))
        if i >= len(ot) or ot[i]-ts > 180*60000 or cl[i] <= 0: return None, None
        return int(ot[i]), float(cl[i])
    def fwd(sym, ets, days):
        a = kl(sym)
        if a is None: return None
        ot, cl = a; i = int(np.searchsorted(ot, ets))
        if i >= len(ot): return None
        e = cl[i]; tgt = ot[i] + days*1440*60000; j = int(np.searchsorted(ot, tgt))
        if j >= len(ot) or ot[j]-tgt > 300*60000 or e <= 0: return None
        return (cl[j]-e)/e*100

    done = set()
    if os.path.exists(OUT):
        for l in open(OUT):
            try: done.add(json.loads(l)["date"])
            except: pass
    now = datetime.now(timezone.utc)
    new_rows = []
    for f in sorted(glob.glob(ST + "/*radar.json")):
        date = f.split("/")[-1][:10]
        if date <= IS_CUTOFF or date in done: continue
        mature = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=HOLD_BUF_DAYS)
        if mature > now: continue   # 还没成熟, 下次再记
        try: d = json.load(open(f))
        except: continue
        entry_ms = int((datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)).timestamp()*1000)
        day_rows = []
        for x in d.get("radar", []):
            sym = x["ticker"].upper()+"USDT"
            ets, e = px_after(sym, entry_ms)
            if e is None: continue
            day_rows.append({
                "date": date, "ticker": x["ticker"].upper(), "symbol": sym,
                "combined_score": x.get("combined_score"), "tech_score": x.get("tech_score"),
                "sentiment": x.get("sentiment"), "momentum_20d_pct": x.get("momentum_20d_pct"),
                "theme": x.get("theme"), "entry_ts": ets, "entry_px": e,
                "f1": fwd(sym,ets,1), "f2": fwd(sym,ets,2), "f3": fwd(sym,ets,3), "f5": fwd(sym,ets,5),
            })
        if day_rows:
            new_rows += day_rows
            print("记录 forward 日 %s: %d 名" % (date, len(day_rows)))
    if new_rows:
        with open(OUT, "a") as out:
            for r in new_rows: out.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("追加 %d 行 → %s" % (len(new_rows), OUT))
    else:
        print("无新成熟日 (forward起点06-16, 各日需+6天成熟)")

if __name__ == "__main__":
    main()
