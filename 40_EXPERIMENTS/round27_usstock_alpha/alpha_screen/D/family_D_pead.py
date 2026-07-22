#!/usr/bin/env python3
"""
Round27 Family D — PEAD 财报后漂移 (post-earnings announcement drift)
====================================================================
PRE-REGISTERED DESIGN (frozen before running; n≈79 events => EXPLORATORY.
Goal of this round = freeze a rule for July Q2 earnings-season forward test,
NOT to claim tradability.)

Events
  uw_earnings_events.jsonl, skip "_empty" rows, keep events where
  symbol+"USDT" is in the perp panel universe AND _date <= 2026-06-15.
  dev = anchor date <= 2026-05-31, val = 2026-06-01..15 (val is tiny, n~6:
  reported for the frozen rule only, labeled as such).

Anchor
  First RTH open AFTER the report:
    _session == "premarket"  -> panel row of report_date (same-day open)
    _session == "afterhours" -> first panel date > report_date
  VALIDITY (added after first run, before any val look): anchor must be
  within 4 calendar days of report_date. Binance listed these perps
  staggered through 2026-02..06, so 53/79 matched events happened BEFORE
  the perp existed (verified vs klines_1m MIN(ot)); those are dropped as
  untradeable, not anchored to the listing date. Effective n ~= 26.
  Entry for PEAD = anchor-day RTH CLOSE (literature standard: skip the
  day-0 reaction; day-0 open reaction is Family E's turf).
  Exits = RTH close of anchor+h trading days, h in {1,2,3,5}, using the
  symbol's own panel date sequence. Exits beyond the panel (2026-06-15
  holdout wall) are dropped, not extrapolated.
  DST is inherited from the panel's rth_*_ts anchors (built in ET).

Surprise definitions (direction = sign of signal; sign==0 or None dropped)
  S_eps : eps_surprise = (actual_eps - street_mean_est)/|street_mean_est|
  S_rxn : reaction (UW actual stock reaction pre->post close)
  Normalized "惊讶度":
  S_epsN: eps_surprise / expected_move_perc
  S_rxnN: reaction    / expected_move_perc
  Tercile boundaries for |signal| computed on DEV events only, frozen,
  applied to val.

Cells counted for FDR (all dev cells)
  ALL directional      : 2 signals (S_eps,S_rxn) x 4 horizons        =  8
  Tercile |S_eps|      : 3 terciles x 4 horizons                     = 12
  Tercile |S_rxn|      : 3 x 4                                       = 12
  Tercile |S_epsN|     : 3 x 4                                       = 12
  Tercile |S_rxnN|     : 3 x 4                                       = 12
  CS weekly LS         : 2 signals x 4 horizons                      =  8
  TOTAL                                                              = 64

PnL per event (all in %)
  raw   = (close_exit/close_entry - 1)*100
  mkt   = same-span equal-weight mean of raw over ALL panel symbols that
          have both entry & exit dates (beta strip, round25 lesson)
  fund  = sum of real funding rates settled in (entry_ts, exit_ts];
          long pays positive funding: fund_pnl = -side*fund*100
  COST  = 0.12 round-trip flat (protocol spec); sensitivity = 1.5x = 0.18
  net        = side*raw       - COST + fund_pnl
  strip_net  = side*(raw-mkt) - COST + fund_pnl   (primary metric)
  CS weekly LS: ISO week of anchor date; weeks needing >=1 event per side;
  week ret = 0.5*mean(strip_net pos-side) + 0.5*mean(strip_net neg-side)
  (each leg pays its own cost; stats over weeks).

Gates (frozen): candidate = dev strip_net mean>0 AND |t|>=2 with mean>0
  AND n>=20 AND max single anchor-date |PnL| share <=40% AND max single
  symbol |PnL| share <=40% AND net at 1.5x cost >0; then val same sign.
  BH-FDR (normal-approx p, two-sided) reported across all 64 dev cells.

Diagnostics (not cells): reaction vs perp same-span move correlation
  (Pearson+Spearman) — does the perp track the underlying stock's
  earnings reaction at all; tercile monotonicity table.

Hard rule: nothing beyond 2026-06-15 (panel pre-cut; funding filtered).
"""
import json, sqlite3, math
import numpy as np
from collections import defaultdict
from datetime import date as _date

ROOT = "/Volumes/T9/BWE/40_EXPERIMENTS/round27_usstock_alpha"
CUTOFF_MS = 1781654399000
HORIZONS = [1, 2, 3, 5]
COST = 0.12          # % round-trip
COST_STRESS = 0.18   # 1.5x

# ---------------- panel ----------------
panel = [json.loads(l) for l in open(f"{ROOT}/panel_devval.jsonl")]
bysym = defaultdict(dict)           # sym -> date -> row
for r in panel:
    bysym[r["symbol"]][r["date"]] = r
symdates = {s: sorted(d.keys()) for s, d in bysym.items()}
psyms = set(bysym.keys())

# ---------------- funding ----------------
db = sqlite3.connect(f"{ROOT}/tradfi_full.sqlite3")
fund = defaultdict(list)
for s, ft, fr in db.execute(
    "SELECT symbol, funding_time, funding_rate FROM funding WHERE funding_time <= ?",
    (CUTOFF_MS,)):
    fund[s].append((ft, fr))
for s in fund:
    fund[s].sort()

def fund_long(sym, t0, t1):
    """sum of funding rates (as %) settled in (t0, t1] — cost to a long."""
    return sum(fr for ft, fr in fund.get(sym, ()) if t0 < ft <= t1) * 100.0

# ---------------- market (beta strip) ----------------
_mkt_cache = {}
def mkt_ret(d0, d1):
    key = (d0, d1)
    if key not in _mkt_cache:
        rs = []
        for s in psyms:
            a, b = bysym[s].get(d0), bysym[s].get(d1)
            if a and b:
                rs.append((b["rth_close"] / a["rth_close"] - 1) * 100)
        _mkt_cache[key] = float(np.mean(rs)) if rs else 0.0
    return _mkt_cache[key]

# ---------------- events ----------------
MAX_GAP_DAYS = 4  # anchor must be a true first post-report session, not a late listing

def _d(s):
    y, m, dd = map(int, s.split("-"))
    return _date(y, m, dd)

events = []
n_matched = n_unlisted = 0
for line in open(f"{ROOT}/data/uw_earnings_events.jsonl"):
    line = line.strip()
    if not line or "_empty" in line:
        continue
    e = json.loads(line)
    if e["symbol"] + "USDT" not in psyms or e["_date"] > "2026-06-15":
        continue
    n_matched += 1
    sym = e["symbol"] + "USDT"
    ds = symdates[sym]
    if e["_session"] == "premarket":
        anchor = e["report_date"] if e["report_date"] in bysym[sym] else None
    else:  # afterhours (or unknown -> treated as afterhours; none present)
        anchor = next((d for d in ds if d > e["report_date"]), None)
    if anchor is not None and (_d(anchor) - _d(e["report_date"])).days > MAX_GAP_DAYS:
        anchor = None  # perp listed after the event -> untradeable
    if anchor is None:
        n_unlisted += 1
        continue
    ai = ds.index(anchor)
    ev = {
        "symbol": sym, "stock": e["symbol"], "anchor": anchor, "ai": ai,
        "session": e["_session"], "report_date": e["report_date"],
        "sector": e.get("sector"),
        "reaction": float(e["reaction"]) if e["reaction"] is not None else None,
        "emp": float(e["expected_move_perc"]) if e["expected_move_perc"] else None,
        "pre_close_dt": e.get("pre_earnings_date"),
        "post_close_dt": e.get("post_earnings_date"),
    }
    if e.get("actual_eps") is not None and e.get("street_mean_est") is not None \
            and abs(float(e["street_mean_est"])) > 0:
        ev["eps_sur"] = (float(e["actual_eps"]) - float(e["street_mean_est"])) \
                        / abs(float(e["street_mean_est"]))
    else:
        ev["eps_sur"] = None
    # signals
    ev["S_eps"] = ev["eps_sur"]
    ev["S_rxn"] = ev["reaction"]
    ev["S_epsN"] = (ev["eps_sur"] / ev["emp"]) if (ev["eps_sur"] is not None and ev["emp"]) else None
    ev["S_rxnN"] = (ev["reaction"] / ev["emp"]) if (ev["reaction"] is not None and ev["emp"]) else None
    # forward legs
    ent = bysym[sym][anchor]
    ev["legs"] = {}
    for h in HORIZONS:
        if ai + h < len(ds):
            dx = ds[ai + h]
            ex = bysym[sym][dx]
            raw = (ex["rth_close"] / ent["rth_close"] - 1) * 100
            ev["legs"][h] = {
                "exit_date": dx, "raw": raw,
                "mkt": mkt_ret(anchor, dx),
                "fund": fund_long(sym, ent["rth_close_ts"], ex["rth_close_ts"]),
            }
    events.append(ev)

dev = [e for e in events if e["anchor"] <= "2026-05-31"]
val = [e for e in events if e["anchor"] > "2026-05-31"]

# ---------------- helpers ----------------
def tstat(x):
    x = np.asarray(x, float)
    if len(x) < 3 or x.std(ddof=1) == 0:
        return 0.0
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x))))

def p_norm(t):  # two-sided normal approx (no scipy on this box)
    return 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))

def pnl_shares(items, key):
    """max share of any single <key> in sum(|pnl|)."""
    agg = defaultdict(float)
    for it in items:
        agg[it[key]] += it["pnl"]
    tot = sum(abs(v) for v in agg.values())
    if tot == 0:
        return 0.0, None
    k, v = max(agg.items(), key=lambda kv: abs(kv[1]))
    return abs(v) / tot, k

def lodo_min(items):
    """min mean pnl when leaving out each anchor date."""
    dts = set(it["date"] for it in items)
    if len(dts) < 2:
        return None
    worst = None
    for d in dts:
        sub = [it["pnl"] for it in items if it["date"] != d]
        m = float(np.mean(sub))
        worst = m if worst is None or m < worst else worst
    return worst

def event_pnls(evs, sig, h, stress=False):
    """per-event dicts with net + stripped pnl for signal sig, horizon h."""
    cost = COST_STRESS if stress else COST
    out = []
    for e in evs:
        s = e[sig]
        if s is None or s == 0 or h not in e["legs"]:
            continue
        side = 1.0 if s > 0 else -1.0
        L = e["legs"][h]
        fp = -side * L["fund"]
        out.append({
            "date": e["anchor"], "symbol": e["symbol"], "side": side,
            "net": side * L["raw"] - cost + fp,
            "pnl": side * (L["raw"] - L["mkt"]) - cost + fp,   # stripped = primary
        })
    return out

def cell_stats(evs, sig, h, subset=None):
    items = event_pnls(evs, sig, h)
    if subset is not None:
        items = [it for it, keep in zip(items, subset) if keep]
    if not items:
        return {"n": 0}
    strip = [it["pnl"] for it in items]
    net = [it["net"] for it in items]
    dsh, dwho = pnl_shares(items, "date")
    ssh, swho = pnl_shares(items, "symbol")
    stress = event_pnls(evs, sig, h, stress=True)
    if subset is not None:
        stress = [it for it, keep in zip(stress, subset) if keep]
    return {
        "n": len(items),
        "n_long": sum(1 for it in items if it["side"] > 0),
        "strip_mean": round(float(np.mean(strip)), 4),
        "strip_t": round(tstat(strip), 3),
        "strip_win": round(100 * np.mean([x > 0 for x in strip]), 1),
        "net_mean": round(float(np.mean(net)), 4),
        "net_t": round(tstat(net), 3),
        "stress_strip_mean": round(float(np.mean([it["pnl"] for it in stress])), 4) if stress else None,
        "max_date_share": round(dsh, 3), "max_date": dwho,
        "max_sym_share": round(ssh, 3), "max_sym": swho,
        "lodo_min_mean": round(lodo_min(items), 4) if lodo_min(items) is not None else None,
    }

# ---------------- build cells ----------------
cells = {}

# 1) ALL directional
for sig in ["S_eps", "S_rxn"]:
    for h in HORIZONS:
        cells[f"ALL|{sig}|h{h}"] = cell_stats(dev, sig, h)

# 2) terciles by |signal| (dev-frozen boundaries)
terc_bounds = {}
for sig in ["S_eps", "S_rxn", "S_epsN", "S_rxnN"]:
    mags = sorted(abs(e[sig]) for e in dev if e[sig] not in (None, 0))
    q1, q2 = mags[len(mags)//3], mags[2*len(mags)//3]
    terc_bounds[sig] = (q1, q2)
    def terc_of(v):
        a = abs(v)
        return 1 if a <= q1 else (2 if a <= q2 else 3)
    for t in [1, 2, 3]:
        for h in HORIZONS:
            evs_t = [e for e in dev if e[sig] not in (None, 0) and terc_of(e[sig]) == t]
            cells[f"T{t}|{sig}|h{h}"] = cell_stats(evs_t, sig, h)

# 3) CS weekly LS
def iso_week(dstr):
    y, m, d = map(int, dstr.split("-"))
    iy, iw, _ = _date(y, m, d).isocalendar()
    return f"{iy}-W{iw:02d}"

def cs_weekly(evs, sig, h, stress=False):
    wk = defaultdict(lambda: {"pos": [], "neg": []})
    for it in event_pnls(evs, sig, h, stress=stress):
        wk[iso_week(it["date"])]["pos" if it["side"] > 0 else "neg"].append(it["pnl"])
    rets, weeks = [], []
    for w in sorted(wk):
        g = wk[w]
        if g["pos"] and g["neg"]:
            rets.append(0.5 * float(np.mean(g["pos"])) + 0.5 * float(np.mean(g["neg"])))
            weeks.append(w)
    return rets, weeks

for sig in ["S_eps", "S_rxn"]:
    for h in HORIZONS:
        rets, weeks = cs_weekly(dev, sig, h)
        sr, _ = cs_weekly(dev, sig, h, stress=True)
        if rets:
            cells[f"CS|{sig}|h{h}"] = {
                "n": len(rets), "unit": "weeks",
                "strip_mean": round(float(np.mean(rets)), 4),
                "strip_t": round(tstat(rets), 3),
                "strip_win": round(100 * np.mean([x > 0 for x in rets]), 1),
                "stress_strip_mean": round(float(np.mean(sr)), 4),
                "weeks": weeks,
            }
        else:
            cells[f"CS|{sig}|h{h}"] = {"n": 0}

# ---------------- BH-FDR over all dev cells ----------------
pvals = []
for k, c in cells.items():
    if c.get("n", 0) >= 3 and "strip_t" in c:
        pvals.append((k, p_norm(c["strip_t"])))
pvals.sort(key=lambda kv: kv[1])
m = len(pvals)
bh_sig = []
for i, (k, p) in enumerate(pvals, 1):
    if p <= 0.10 * i / m:
        bh_sig.append((k, round(p, 5)))
for k, c in cells.items():
    if c.get("n", 0) >= 3 and "strip_t" in c:
        c["p_raw"] = round(p_norm(c["strip_t"]), 5)

# ---------------- candidate gate on dev ----------------
def passes_gate(name, c):
    if c.get("n", 0) < 20 or "strip_mean" not in c:
        return False
    ok = (c["strip_mean"] > 0 and c["strip_t"] >= 2.0
          and (c.get("stress_strip_mean") or -1) > 0)
    if name.startswith("CS"):
        return ok  # CS: shares/lodo not applicable per-week the same way
    return ok and c["max_date_share"] <= 0.40 and c["max_sym_share"] <= 0.40
candidates = [k for k, c in cells.items() if passes_gate(k, c)]

# ---------------- val re-score for candidates (+ best dev cells for context) ----------------
def val_score(name):
    part, sig, hs = name.split("|")
    h = int(hs[1:])
    if part == "ALL":
        return cell_stats(val, sig, h)
    if part.startswith("T"):
        t = int(part[1:])
        q1, q2 = terc_bounds[sig]
        evs_t = [e for e in val if e[sig] not in (None, 0)
                 and (1 if abs(e[sig]) <= q1 else (2 if abs(e[sig]) <= q2 else 3)) == t]
        return cell_stats(evs_t, sig, h)
    if part == "CS":
        rets, weeks = cs_weekly(val, sig, h)
        return {"n": len(rets), "unit": "weeks",
                "strip_mean": round(float(np.mean(rets)), 4) if rets else None,
                "weeks": weeks}

val_results = {k: val_score(k) for k in candidates}

# ---------------- diagnostics ----------------
# (a) reaction vs perp same-span move (does the perp track the stock?)
pairs = []
for e in events:
    if e["reaction"] is None or not e["pre_close_dt"] or not e["post_close_dt"]:
        continue
    a = bysym[e["symbol"]].get(e["pre_close_dt"])
    b = bysym[e["symbol"]].get(e["post_close_dt"])
    if a and b:
        pairs.append((e["reaction"] * 100, (b["rth_close"] / a["rth_close"] - 1) * 100))
if len(pairs) >= 3:
    x = np.array([p[0] for p in pairs]); y = np.array([p[1] for p in pairs])
    pear = float(np.corrcoef(x, y)[0, 1])
    rx = np.argsort(np.argsort(x)); ry = np.argsort(np.argsort(y))
    spear = float(np.corrcoef(rx, ry)[0, 1])
else:
    pear = spear = None
track = {"n": len(pairs), "pearson": round(pear, 4) if pear is not None else None,
         "spearman": round(spear, 4) if spear is not None else None}

# (b) monotonicity table: strip_mean by tercile for each sig at h=3
mono = {sig: {f"T{t}": cells[f"T{t}|{sig}|h3"].get("strip_mean")
              for t in [1, 2, 3]} for sig in ["S_eps", "S_rxn", "S_epsN", "S_rxnN"]}

# (c) sign agreement eps vs reaction
both = [e for e in dev if e["S_eps"] not in (None, 0) and e["S_rxn"] not in (None, 0)]
agree = sum(1 for e in both if (e["S_eps"] > 0) == (e["S_rxn"] > 0))

# (d) side split for the reaction-sign directional cells (做空看均值 rule)
side_split = {}
for h in HORIZONS:
    items = event_pnls(dev, "S_rxn", h)
    L = [it["pnl"] for it in items if it["side"] > 0]
    S = [it["pnl"] for it in items if it["side"] < 0]
    side_split[f"h{h}"] = {
        "long_n": len(L), "long_strip_mean": round(float(np.mean(L)), 4) if L else None,
        "short_n": len(S), "short_strip_mean": round(float(np.mean(S)), 4) if S else None,
    }

out = {
    "family": "D_PEAD",
    "design": "entry=anchor-day RTH close (skip day-0 reaction), exit=+{1,2,3,5} trading-day RTH close; direction=sign(surprise); primary metric=beta-stripped net (cost 0.12% RT + real funding)",
    "n_events_matched": n_matched,
    "n_events_dropped_perp_not_listed": n_unlisted,
    "n_events_total": len(events),
    "n_events_dev": len(dev), "n_events_val": len(val),
    "sessions": {"afterhours": sum(1 for e in events if e["session"] == "afterhours"),
                 "premarket": sum(1 for e in events if e["session"] == "premarket")},
    "n_cells": len(cells),
    "tercile_bounds_dev": {k: [round(a, 4), round(b, 4)] for k, (a, b) in terc_bounds.items()},
    "dev_cells": cells,
    "bh_fdr_q10_significant": bh_sig,
    "candidates_dev_gate": candidates,
    "val_rescore": val_results,
    "diag_perp_tracks_stock": track,
    "diag_tercile_monotonicity_h3_strip_mean": mono,
    "diag_eps_vs_reaction_sign_agree": {"n": len(both), "agree": agree,
                                        "pct": round(100 * agree / len(both), 1) if both else None},
    "diag_side_split_S_rxn": side_split,
    "caveats": [
        "EXPLORATORY: effective n=26 events (dev 23 / val 3); 53/79 matched events dropped because the Binance perp did not exist yet at report time (staggered listings 2026-02..06). Val is uninformative (2 usable events at h2).",
        "CS weekly t-stats on n=5 weeks: normal-approx p-values unreliable (CS|S_rxn|h2 t=10 is a small-sample artifact); direction only.",
        "Tercile cells have n=7-8 each; monotonicity readings are noise-level.",
        "p-values are normal-approx (no scipy); with n~23 they are slightly anti-conservative.",
    ],
    "frozen_rule_for_forward_2026Q2_july": {
        "name": "D_PEAD_rxn_sign_h2",
        "event": "UW earnings event, symbol+USDT listed on Binance at report time (anchor within 4 calendar days of report_date)",
        "signal": "sign of UW `reaction` (stock pre->post close move). EPS surprise is NOT used (45% sign agreement, wrong-way returns on dev).",
        "anchor": "premarket report -> same-day RTH; afterhours report -> next trading day",
        "entry": "anchor-day 16:00 ET RTH close, direction = sign(reaction)",
        "exit_primary": "+2 trading days RTH close",
        "exit_secondary_monitor": "+3 and +5 trading days RTH close (report only)",
        "filters": "none (all events; no tercile filter — tercile structure was not robust on dev)",
        "costs": "0.12% round-trip + real funding settlements crossed",
        "dev_evidence": "strip_net +2.13%/event, t=2.25, n=23, win 61%, long +1.00%/short +3.37%, LODO min +1.77%, max date share 17%, survives 1.5x cost (+2.07%)",
        "forward_pass_gate": "forward beta-stripped net mean > 0 with n>=15 events AND both sides' mean not strongly negative AND survives 1.5x cost",
    },
}
with open(f"{ROOT}/alpha_screen/D/results_D.json", "w") as f:
    json.dump(out, f, indent=1)

# console summary
print(f"matched: {n_matched}, dropped (perp not yet listed): {n_unlisted}")
print(f"events: {len(events)} (dev {len(dev)} / val {len(val)}), cells: {len(cells)}")
print(f"perp-tracks-stock: n={track['n']} pearson={track['pearson']} spearman={track['spearman']}")
print(f"eps/reaction sign agreement: {out['diag_eps_vs_reaction_sign_agree']}")
print("\ntop dev cells by |strip_t| (n>=10):")
top = sorted([(k, c) for k, c in cells.items() if c.get("n", 0) >= 10],
             key=lambda kc: -abs(kc[1]["strip_t"]))[:12]
for k, c in top:
    print(f"  {k:18s} n={c['n']:3d} strip={c['strip_mean']:+7.3f}% t={c['strip_t']:+5.2f} "
          f"win={c['strip_win']:5.1f}% stress={c.get('stress_strip_mean')} "
          f"dshare={c.get('max_date_share')} p={c.get('p_raw')}")
print(f"\nBH-FDR q=0.10 significant: {bh_sig}")
print(f"dev-gate candidates: {candidates}")
for k in candidates:
    print(f"  VAL {k}: {val_results[k]}")
print("\nmonotonicity h3 (strip_mean by tercile):")
for sig, r in mono.items():
    print(f"  {sig}: {r}")
