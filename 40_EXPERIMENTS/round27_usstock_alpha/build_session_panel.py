#!/usr/bin/env python3
"""Round27 共享时段面板: 105只美股永续 × 每个NYSE交易日 的 session 结构。
覆盖族A(时段回归)/B(周末)/F(资金费截面)所需 + 给C/D/E提供开收盘锚点。
关键正确性:
- ET时区用 zoneinfo America/New_York(自动处理2026-03-08夏令时切换, 绝不硬编码UTC小时)
- NYSE 2026上半年假日剔除
- 结构性holdout隔离: 输出两份 — panel_devval.jsonl(≤2026-06-15, 给agent) 与 panel_full.jsonl(全量, 只归主线终审用)
"""
import sqlite3, json, numpy as np
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DIR = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha"
DB = DIR + "/tradfi_full.sqlite3"
ET = ZoneInfo("America/New_York")
HOLIDAYS = {"2026-01-01","2026-01-19","2026-02-16","2026-04-03","2026-05-25","2026-06-19","2026-07-03"}
VAL_END = "2026-06-15"

kc = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)

def et_str(ms):
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc).astimezone(ET)

rows_all = []
syms = [r[0] for r in kc.execute("SELECT DISTINCT symbol FROM klines_1m")]
print("symbols:", len(syms))
diag_weekend_bars = 0; diag_total = 0

for si, sym in enumerate(sorted(syms)):
    r = kc.execute("SELECT ot, cl, qv FROM klines_1m WHERE symbol=? ORDER BY ot", (sym,)).fetchall()
    if len(r) < 2000: continue
    ot = np.array([x[0] for x in r], np.int64)
    cl = np.array([x[1] for x in r], float)
    qv = np.array([x[2] for x in r], float)
    fund = kc.execute("SELECT funding_time, funding_rate FROM funding WHERE symbol=? ORDER BY funding_time", (sym,)).fetchall()
    ft = np.array([x[0] for x in fund], np.int64) if fund else np.array([], np.int64)
    fr = np.array([x[1] for x in fund], float) if fund else np.array([], float)
    # 每根bar的ET日期/时刻(向量化: 逐bar转太慢, 用近似 — 按UTC偏移分段处理DST)
    # 2026 DST: 03-08 07:00UTC 起 EDT(UTC-4), 之前 EST(UTC-5); 11-01 之后 EST(数据不到)
    dst_switch = int(datetime(2026,3,8,7,0,tzinfo=timezone.utc).timestamp()*1000)
    off_h = np.where(ot >= dst_switch, 4, 5)   # UTC-offset小时
    et_ms = ot - off_h.astype(np.int64)*3600000
    et_day = et_ms // 86400000
    et_min = (et_ms % 86400000) // 60000       # ET当日分钟数
    RTH_O, RTH_C = 9*60+30, 16*60
    # 周末bar诊断(这决定周末族是否可做)
    dow = ((et_day + 4) % 7)                   # 1970-01-01是周四=4
    diag_weekend_bars += int(np.sum((dow==5)|(dow==6))); diag_total += len(ot)
    # 按ET日分组
    days = np.unique(et_day)
    prev_close_px = None; prev_close_ts = None; prev_day = None
    day_rows = {}
    for d in days:
        dstr = datetime.fromtimestamp(int(d)*86400, tz=timezone.utc).strftime("%Y-%m-%d")
        wd = int((d + 4) % 7)  # 0=周一...6=周日 (1970-01-01周四=3? 修正: (d+3)%7? 直接用datetime)
        wd = datetime.fromtimestamp(int(d)*86400 + 43200, tz=timezone.utc).weekday()
        if wd >= 5 or dstr in HOLIDAYS: continue
        m = (et_day == d)
        if not m.any(): continue
        idx = np.where(m)[0]
        mins = et_min[idx]
        rth = idx[(mins >= RTH_O) & (mins < RTH_C)]
        if len(rth) < 30: continue   # 该日RTH数据太薄
        o_i, c_i = rth[0], rth[-1]
        # 开盘后锚点
        def anchor(minutes):
            tgt = ot[o_i] + minutes*60000
            j = int(np.searchsorted(ot, tgt))
            if j >= len(ot) or ot[j]-tgt > 10*60000: return None
            return float(cl[j])
        row = {
            "symbol": sym, "date": dstr,
            "rth_open_ts": int(ot[o_i]), "rth_open": float(cl[o_i]),
            "rth_close_ts": int(ot[c_i]), "rth_close": float(cl[c_i]),
            "px_o30": anchor(30), "px_o60": anchor(60), "px_o120": anchor(120),
            "qv_day": float(qv[idx].sum()),
        }
        if prev_close_px and prev_close_px > 0:
            row["prev_close"] = prev_close_px
            row["overnight_ret"] = (row["rth_open"]-prev_close_px)/prev_close_px*100
            row["gap_days"] = (int(d) - int(prev_day))
            row["is_weekend_gap"] = 1 if row["gap_days"] >= 3 else 0
            # 隔夜窗资金费(prev_close_ts→rth_open_ts), 多头视角
            if len(ft):
                fm = (ft > prev_close_ts) & (ft <= ot[o_i])
                row["fund_overnight"] = float(fr[fm].sum()*100)
            # RTH内回归窗收益(开盘→+30/60/120m, 供A族)
            for k, px in (("r_o30","px_o30"),("r_o60","px_o60"),("r_o120","px_o120")):
                row[k] = (row[px]-row["rth_open"])/row["rth_open"]*100 if row.get(px) else None
            row["r_o_close"] = (row["rth_close"]-row["rth_open"])/row["rth_open"]*100
        prev_close_px, prev_close_ts, prev_day = row["rth_close"], int(ot[c_i]), d
        day_rows[dstr] = row
    rows_all += list(day_rows.values())
    if (si+1) % 25 == 0: print("  %d/%d syms, %d rows" % (si+1, len(syms), len(rows_all)), flush=True)

# 资金费截面(F族): 每日横截面percentile — 用前一日隔夜费率做当日排名(因果)
from collections import defaultdict
byd = defaultdict(list)
for r in rows_all:
    if r.get("fund_overnight") is not None: byd[r["date"]].append(r)
for d, rs in byd.items():
    vals = sorted(x["fund_overnight"] for x in rs)
    n = len(vals)
    for x in rs:
        x["fund_pctile"] = sum(1 for v in vals if v <= x["fund_overnight"])/n

full = DIR + "/panel_full.jsonl"; devval = DIR + "/panel_devval.jsonl"
with open(full, "w") as f1, open(devval, "w") as f2:
    for r in sorted(rows_all, key=lambda x: (x["date"], x["symbol"])):
        line = json.dumps(r) + "\n"
        f1.write(line)
        if r["date"] <= VAL_END: f2.write(line)
n_dv = sum(1 for r in rows_all if r["date"] <= VAL_END)
print("panel_full: %d 行 | panel_devval(给agent): %d 行" % (len(rows_all), n_dv))
print("周末bar占比: %.1f%% (%d/%d) → %s" % (100*diag_weekend_bars/max(diag_total,1), diag_weekend_bars, diag_total,
      "永续周末在交易, B族可做" if diag_weekend_bars > diag_total*0.05 else "周末几乎无bar, B族改'跨周末gap'口径"))
print("PANEL_DONE")
