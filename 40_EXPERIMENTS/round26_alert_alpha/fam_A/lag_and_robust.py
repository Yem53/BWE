#!/usr/bin/env python3
"""fam_A 补充: (1) lag 敏感角度  (2) block-bootstrap 稳健性复核 best 短horizon短候选。
确认主筛选的死亡判决不是 bootstrap 独立性假设造成的假阴/假阳。"""
import sqlite3, json, os
import numpy as np
import pandas as pd

DB = "/Volumes/T9/BWE/40_EXPERIMENTS/round26_alert_alpha/alert_panel.sqlite3"
OUT = "/Volumes/T9/BWE/40_EXPERIMENTS/round26_alert_alpha/fam_A"
DEV_CUTOFF = 1778803200000
RNG = np.random.default_rng(7)

def slip_oneside(a):
    a = np.where(np.isnan(a), 0.0, a)
    s = np.zeros_like(a, float)
    s = np.where(a >= 1.5, 0.4, s); s = np.where(a >= 3.0, 0.6, s)
    return s
def net_ret(f, atr, side):
    return side * f - (0.14 + 2.0 * slip_oneside(atr))

def load():
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    df = pd.read_sql_query("SELECT symbol,ts_ms,wt,chg,atr_pct,lag_s,f5,f15,f60,f240 FROM panel", con)
    con.close()
    df["day"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True).dt.strftime("%Y-%m-%d")
    df["dev"] = df["ts_ms"] <= DEV_CUTOFF
    return df

# ---- block bootstrap by (symbol, day): 重抽样整组, 保留簇内相关 ----
def block_boot_p(g, side, h):
    """g: DataFrame for one cell. 返回 (net_mean, p_gt0_block)."""
    g = g.dropna(subset=[h])
    if len(g) < 20: return np.nan, 1.0, 0
    net = net_ret(g[h].values, g["atr_pct"].values, side)
    keys = (g["symbol"] + "|" + g["day"]).values
    uk = pd.unique(keys)
    # 预分组
    idx_by_key = {k: np.where(keys == k)[0] for k in uk}
    obs_mean = net.mean()
    B = 5000; bmeans = np.empty(B)
    nk = len(uk)
    for b in range(B):
        pick = uk[RNG.integers(0, nk, size=nk)]
        sel = np.concatenate([idx_by_key[k] for k in pick])
        bmeans[b] = net[sel].mean()
    p = float((bmeans <= 0).mean())
    return float(obs_mean), p, len(g)

def main():
    df = load()
    dev = df[df["dev"]]
    out = {}

    # ===== (1) LAG 敏感: 对方向性最强的几个 window, 比较 lag 低/高 两半的 gross 反应 =====
    lag_rows = []
    for wt in ["price_3s","price_60s","oi_price_1h","price_180s_extreme","price_30s"]:
        g = dev[dev["wt"] == wt].dropna(subset=["f60","lag_s"])
        if len(g) < 100: continue
        med_lag = g["lag_s"].median()
        for half, mask in [("fast_lowlag", g["lag_s"] <= med_lag), ("slow_highlag", g["lag_s"] > med_lag)]:
            gg = g[mask]
            if len(gg) == 0:
                continue
            lag_rows.append(dict(wt=wt, half=half, n=int(len(gg)),
                med_lag_s=round(float(g["lag_s"].median()),1),
                gross_f60_long=round(float(gg["f60"].mean()),3),
                gross_f60_short=round(float(-gg["f60"].mean()),3),
                net_f60_short=round(float(net_ret(gg["f60"].values, gg["atr_pct"].values, -1).mean()),3),
                net_f60_long=round(float(net_ret(gg["f60"].values, gg["atr_pct"].values, +1).mean()),3)))
    out["lag_sensitivity"] = lag_rows

    # ===== (2) block-bootstrap 复核: 把 IID bootstrap 里 raw-p 最小的短horizon短候选拿来重测 =====
    # 候选: 这些在 IID 下 raw p<0.10 但被 FDR 杀。看 block-boot 是否更严。
    checks = [
        ("price_5s","short","f5"), ("price_5s","short","f15"), ("price_5s","short","f240"),
        ("price_180s_extreme","short","f240"),
        ("price_60s","short","f240"),  # 24h 那个最"强"的
    ]
    rob = []
    for wt, side, h in checks:
        g = dev[dev["wt"] == wt]
        s = -1 if side == "short" else 1
        m, p, n = block_boot_p(g, s, h)
        rob.append(dict(wt=wt, side=side, horizon=h, n=n,
            net_mean=round(m,3) if not np.isnan(m) else None,
            block_p_gt0=round(p,4)))
    out["block_bootstrap_recheck"] = rob

    with open(os.path.join(OUT, "lag_and_robust.json"), "w") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    print("=== LAG SENSITIVITY (dev, gross + net f60) ===")
    print(pd.DataFrame(lag_rows).to_string(index=False))
    print("\n=== BLOCK-BOOTSTRAP RECHECK (cluster by symbol|day) ===")
    print(pd.DataFrame(rob).to_string(index=False))
    print("\nwrote lag_and_robust.json")

if __name__ == "__main__":
    main()
