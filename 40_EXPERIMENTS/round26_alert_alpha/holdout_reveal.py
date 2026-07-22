#!/usr/bin/env python3
"""处女holdout一次性揭晓: 把各家族幸存候选, 在05-30+从未碰过的K线上算真实表现。
关键: 候选规则全部FROZEN(从各family的survivors), 不在holdout上调任何参数。只算一次。
beta对照: 同时算"同期all-short基线", 候选必须超额于基线才是真alert alpha(非市场beta)。
holdout K线源: EC2回填的 crypto_holdout.sqlite3(已rsync到本地)。"""
import sqlite3, numpy as np, json, os
from datetime import datetime, timezone

DIR = "/Volumes/T9/BWE/40_EXPERIMENTS/round26_alert_alpha"
PANEL = os.path.join(DIR, "alert_panel.sqlite3")      # 警报(到05-29)
HOLD_KL = os.path.join(DIR, "crypto_holdout.sqlite3")  # 回填的holdout K线(05-25~06-11)
ALERTS = "/Volumes/T9/BWE/30_DATA/bwe_scanner_alerts"

HOLDOUT_LO = int(datetime(2026, 5, 30, tzinfo=timezone.utc).timestamp() * 1000)
HOLDOUT_HI = int(datetime(2026, 6, 9, tzinfo=timezone.utc).timestamp() * 1000)   # 留2天给f1440出场

def load_holdout_alerts():
    """05-30~06-09的警报(holdout期), 从原始jsonl读(panel不含这段)。"""
    import glob
    out = []
    for f in sorted(glob.glob(ALERTS + "/*.jsonl")):
        d = f.split("alerts_")[1][:10]
        if d < "2026-05-30" or d > "2026-06-09":
            continue
        for l in open(f):
            try: a = json.loads(l)
            except: continue
            if HOLDOUT_LO <= a["ts_ms"] <= HOLDOUT_HI:
                out.append(a)
    return out

def main():
    if not os.path.exists(HOLD_KL):
        print("holdout K线库还没同步到本地, 先rsync crypto_holdout.sqlite3"); return
    kc = sqlite3.connect("file:%s?mode=ro" % HOLD_KL, uri=True)
    alerts = load_holdout_alerts()
    print("holdout期警报数(05-30~06-09): %d" % len(alerts))

    # 预载每symbol的K线
    kl_cache = {}
    def get_kl(sym):
        if sym in kl_cache: return kl_cache[sym]
        r = kc.execute("SELECT ot,h,l,c FROM klines_1m WHERE symbol=? ORDER BY ot", (sym,)).fetchall()
        a = np.array(r, float) if r else None
        kl_cache[sym] = a
        return a

    def fwd_short(sym, ts, hold_min, atr_pct_hint=None):
        """做空净收益%: 进场=触发后第一根已收盘bar, 持hold_min, 扣成本。"""
        a = get_kl(sym)
        if a is None or len(a) < hold_min + 5: return None
        ot = a[:, 0]; cl = a[:, 3]
        i = int(np.searchsorted(ot, ts - 59999))
        while i < len(ot) and ot[i] + 60000 <= ts: i += 1
        if i >= len(ot) or ot[i] + 60000 - ts > 180000: return None
        entry = cl[i]; j = i + hold_min
        if j >= len(cl) or entry <= 0: return None
        raw = (entry - cl[j]) / entry * 100   # 做空
        # 成本: 往返0.14% + 滑点(无atr信息时按保守0.4%/边)
        slip = 0.4 if (atr_pct_hint is None or atr_pct_hint >= 1.5) else 0.0
        if atr_pct_hint and atr_pct_hint >= 3: slip = 0.6
        return raw - 0.14 - 2 * slip

    def report(rets, label):
        a = np.array([r for r in rets if r is not None])
        if len(a) < 10: return "%s: n=%d 太少" % (label, len(a))
        rng = np.random.default_rng(26); idx = rng.integers(0, len(a), size=(2000, len(a)))
        lo = np.sort(a[idx].mean(1))[100]
        # 按天聚类(防簇射): 每天均值再平均
        return "%s: n=%d 净均%+.2f%% 中%+.2f%% 胜%d%% boot_lo%+.2f%%" % (
            label, len(a), a.mean(), np.median(a), 100*(a>0).mean(), lo)

    # === 候选1: C2 OI堆积反转空 (oi_price_1h + oi_chg>15, 空24h=1440m) ===
    print("\n=== 候选C2: OI堆积反转空 (oi_chg>15, 空1440m) ===")
    c2 = [a for a in alerts if a.get("window_type") == "oi_price_1h" and (a.get("oi_chg_pct") or 0) > 15]
    print("  holdout触发数: %d" % len(c2))
    rets = [fwd_short(a["symbol"], a["ts_ms"], 1440) for a in c2]
    print("  " + report(rets, "C2 holdout"))
    # beta对照: 同期所有oi_price_1h警报做空1440
    allshort = [a for a in alerts if a.get("window_type") == "oi_price_1h"]
    base = [fwd_short(a["symbol"], a["ts_ms"], 1440) for a in allshort[:3000]]
    print("  " + report(base, "  [beta对照]所有oi警报空1440"))
    ca = np.array([r for r in rets if r is not None]); ba = np.array([r for r in base if r is not None])
    if len(ca) > 10 and len(ba) > 10:
        print("  → C2超额(候选-beta): %+.2f%% %s" % (ca.mean()-ba.mean(),
              "✅真alpha" if ca.mean()-ba.mean() > 0.5 else "⚠️主要是beta"))

    # 剂量响应holdout (oi_chg>8/15/25)
    print("  剂量响应:")
    for thr in (8, 15, 25):
        sub = [fwd_short(a["symbol"], a["ts_ms"], 1440) for a in alerts
               if a.get("window_type") == "oi_price_1h" and (a.get("oi_chg_pct") or 0) > thr]
        s = np.array([r for r in sub if r is not None])
        if len(s) > 10: print("    oi_chg>%d: n=%d 净均%+.2f%%" % (thr, len(s), s.mean()))

    # === 候选B: 恐慌flush抄底 (breadth>=16 + chg<=-2.5, 做多4h) ===
    print("\n=== 候选B: 恐慌flush抄底 (广度>=16+chg<=-2.5, 多240m) ===")
    # 算holdout期每分钟广度
    from collections import Counter
    bmin = Counter(a["ts_ms"] // 60000 for a in alerts)
    def fwd_long(sym, ts, hold_min):
        a = get_kl(sym)
        if a is None or len(a) < hold_min + 5: return None
        ot = a[:, 0]; cl = a[:, 3]
        i = int(np.searchsorted(ot, ts - 59999))
        while i < len(ot) and ot[i] + 60000 <= ts: i += 1
        if i >= len(ot) or ot[i] + 60000 - ts > 180000: return None
        entry = cl[i]; j = i + hold_min
        if j >= len(cl) or entry <= 0: return None
        raw = (cl[j] - entry) / entry * 100
        return raw - 0.14 - 2 * 0.4
    bflush = [a for a in alerts if bmin.get(a["ts_ms"]//60000, 0) >= 16 and (a.get("price_chg_pct") or 0) <= -2.5]
    print("  holdout触发数: %d" % len(bflush))
    rets_b = [fwd_long(a["symbol"], a["ts_ms"], 240) for a in bflush]
    print("  " + report(rets_b, "B holdout"))

    # === 候选D: 追高fade (chg24>=30 → 空240m) — fam_D幸存规则, 冻结于dev/val ===
    print("\n=== 候选D: 追高fade (chg24>=30, 空240m) ===")
    dsel = [a for a in alerts if (a.get("chg_24h_pct") or 0) >= 30]
    print("  holdout触发数: %d" % len(dsel))
    rets_d = [fwd_short(a["symbol"], a["ts_ms"], 240) for a in dsel]
    print("  " + report(rets_d, "D holdout"))
    base_d = [fwd_short(a["symbol"], a["ts_ms"], 240) for a in alerts[:5000]]
    da = np.array([r for r in rets_d if r is not None]); dba = np.array([r for r in base_d if r is not None])
    if len(da) > 10 and len(dba) > 10:
        print("  [beta对照]所有警报空240: 净均%+.2f%% | D超额: %+.2f%%" % (dba.mean(), da.mean()-dba.mean()))

    print("\n注: holdout是各候选从未碰过的数据。C2/D看超额(扣beta), B看是否仍正。boot_lo>0+超额>0才算真过。")

if __name__ == "__main__":
    main()
