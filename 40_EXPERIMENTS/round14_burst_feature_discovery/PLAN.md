# Round 14 — 妖币爆发特征发现 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:subagent-driven-development(推荐)或 executing-plans 逐任务执行。步骤用 `- [ ]` 复选框跟踪。
> 研究型计划:用 sanity 断言 / 结构验证 / 无前视审计 / holdout 纪律 代替单元测试。真钱研究——只读数据、不碰实盘、本机省资源(单线程/分批/微sleep),产物只写 `round14_burst_feature_discovery/`。

**Goal:** 在 ~4 个月全市场爆发上,逐类(A-F)×6粒度×3层(方向两面/时机/风险)挖可识别的入场/方向/风控特征规律,组合探索后用封存 holdout 确认,诚实判定真信号 vs 噪声。

**Architecture:** 路线 C 分阶段——Phase0 重扫+持久性+流动性+as-of特征面板 → Phase1 逐类描述筛 → Phase2 组合 → Phase3 holdout 确认。事件锚点复用爆发扫描去重事件;特征全部在"进场时刻"因果重算;一切以封存 holdout 为唯一裁判。

**Tech Stack:** Python3(numpy/pandas/sqlite3,本机已装);复用 `round12.../volatility_burst_scan_all.py`(重扫)、`round8_calibration/calibrate.py`(ATR/btc_regime/退出/eval_window)。

---

## 文件结构(全部在 `40_EXPERIMENTS/round14_burst_feature_discovery/`)

| 文件 | 职责 |
|---|---|
| `r14_common.py` | 公共:只读连库、UTC↔ms、**切分定义(holdout/dev折)**、币波动分层、流动性档 |
| `phase0_rescan_cmd.md` | 重扫命令记录(复用现成脚本,不重写) |
| `persistence_check.py` | 持久性劈半:惯犯榜重合度 → 猎场池/历史频次能否用 |
| `liquidity_filter.py` | 可交易性过滤 → `tradable_universe.json`(剔除做不了的币) |
| `build_panel.py` | **as-of 因果特征面板(A×6粒度 + B-F)+ 无前视断言** → `panel.parquet` |
| `labels.py` | 三层前向标签(方向两面/时机/风险,H∈{60,120,240}min)→ 并入 panel |
| `screen.py` | Phase1 逐类×逐层描述筛(分位价差+Spearman+跨折跨币组一致)→ 信号榜 |
| `combine.py` | Phase2 组合探索(AND/打分→受限浅树,嵌套CV,打赢最好单特征) |
| `holdout_confirm.py` | Phase3 每层 holdout 验一次 |
| `experiments.jsonl` / `REPORT_CN.md` | 全实验记录(含失败)/ 最终中文报告 |

---

## Phase 0 — 地基(跑完给用户看:事件量 + 持久性 + 流动性分布)

### Task 0.0:补全衍生品数据到 4 个月(C/D 特征用)

> 现状:K线归档 4 个月✓;但 OI/taker/多空比/premium/funding 库只到 03-26/03-30(~2个月)。从 data.binance.vision 官方归档补全 01-27→05-25 到一个**独立 aux 归档库**(只读不碰收集器活表,ATTACH 可联查)。已验证 CDN 上 01-27 的 metrics/premiumIndexKlines/fundingRate 全部 http=200。

**Files:** Create `aux_archive_builder.py` → 产物 `30_DATA/binance_collectors_runtime/binance_futures_aux_archive.sqlite3`(表 `metrics_5m`(OI+大户/散户多空比+taker比)、`premium_5m`、`funding`)

- [ ] **Step 1:** smoke 测 3 币(BTCUSDT,MEUSDT,BSBUSDT)验下载+解析+入库通,且 01-27 起有数据。
- [ ] **Step 2:** 全量 640 币并发后台跑(metrics 日档为主,premium/funding 月档;12 并发,缓存+负缓存404,bulk-load)。
- [ ] **Step 3:** 验覆盖:`metrics_5m` 起始 ≤01-28、币数≈600+、无内部集体缺口;打印行数+范围报用户。

### Task 0.1:重扫爆发事件到全归档(01-27→05-25)

**Files:** Create `phase0_rescan_cmd.md`(记录命令);产物 `volatility_bursts_all4mo_{events,symbol_counts,symbol_coverage,raw_windows}.csv`

- [ ] **Step 1:** 跑重扫(复用现成脚本,归档已含数据故 `--no-download-extra`):
```bash
cd /Volumes/T9/BWE/40_EXPERIMENTS/round12_post_pump_direction/entry_search
nice -n 10 python3 volatility_burst_scan_all.py \
  --start 2026-01-27 --end 2026-05-25 --tag all4mo --no-download-extra \
  > /tmp/r14_rescan.log 2>&1 &
```
- [ ] **Step 2:** 等完成,验产物行数 + meta:
```bash
cd /Volumes/T9/BWE/40_EXPERIMENTS/round12_post_pump_direction/entry_search
wc -l volatility_bursts_all4mo_events.csv volatility_bursts_all4mo_symbol_counts.csv
python3 -c "import json;m=json.load(open('volatility_bursts_all4mo_meta.json'));print({k:m[k] for k in ('start_utc','end_utc','dedup_events','up_bursts','down_bursts','range_only_bursts')})"
```
Expected: dedup_events ≈ 2500-3500(比 2 月的 1551 明显增多),start_utc=2026-01-27,无报错。
- [ ] **Step 3:** 复制事件到 round14 目录固定快照(防上游被覆盖):
```bash
cp /Volumes/T9/BWE/40_EXPERIMENTS/round12_post_pump_direction/entry_search/volatility_bursts_all4mo_*.csv /Volumes/T9/BWE/40_EXPERIMENTS/round14_burst_feature_discovery/
```

### Task 0.2:公共模块 + 切分定义

**Files:** Create `r14_common.py`

- [ ] **Step 1:** 写公共模块(切分 + 分层是后续一切的基准,必须先定死):
```python
import sqlite3
from datetime import datetime, timezone
ARCHIVE = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/binance_futures_klines_archive.sqlite3"
FEATDB  = "/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/binance_futures_1m.sqlite3"
DIR     = "/Volumes/T9/BWE/40_EXPERIMENTS/round14_burst_feature_discovery"

def ms(y,m,d): return int(datetime(y,m,d,tzinfo=timezone.utc).timestamp()*1000)
# 切分(事件 event_start_ms 归属):holdout 封存只验一次
HOLDOUT_LO = ms(2026,4,20); WIN_HI = ms(2026,5,25)            # holdout = 04-20→05-25
DEV_LO     = ms(2026,1,27); DEV_HI = HOLDOUT_LO               # dev = 01-27→04-20
# dev walk-forward 3 折(连续三等分,要求信号每折一致)
FOLDS = [(ms(2026,1,27),ms(2026,2,24)), (ms(2026,2,24),ms(2026,3,23)), (ms(2026,3,23),ms(2026,4,20))]

def ro(db): 
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)

def vol_tier(atr_pct):                 # 币波动分层(跨组一致性检验用)
    return "majors" if atr_pct<1.0 else ("mid" if atr_pct<2.5 else "yao")

def split_of(ts_ms):
    if ts_ms>=HOLDOUT_LO: return "holdout"
    return "dev" if ts_ms>=DEV_LO else "pre"
```
- [ ] **Step 2:** Sanity:打印各切分的事件数,确认 holdout≈30%、dev 三折各≈非空:
```bash
cd /Volumes/T9/BWE/40_EXPERIMENTS/round14_burst_feature_discovery
python3 -c "
import csv,r14_common as C
ev=list(csv.DictReader(open('volatility_bursts_all4mo_events.csv')))
from collections import Counter
c=Counter(C.split_of(int(r['event_start_ms'])) for r in ev)
print('事件切分:',dict(c),' holdout占比=%.0f%%'%(100*c['holdout']/len(ev)))
"
```
Expected: dev 与 holdout 都非空,holdout 占比 ~25-35%。

### Task 0.3:持久性劈半检验(猎场池能否用的前置闸)

**Files:** Create `persistence_check.py`

- [ ] **Step 1:** 写检验——把 dev 期再劈两半,比"惯犯榜"重合:
```python
import csv, r14_common as C
from collections import Counter
ev=[r for r in csv.DictReader(open(f"{C.DIR}/volatility_bursts_all4mo_events.csv"))]
mid=(C.DEV_LO+C.DEV_HI)//2
h1=Counter(); h2=Counter()
for r in ev:
    t=int(r["event_start_ms"])
    if C.DEV_LO<=t<mid: h1[r["symbol"]]+=1
    elif mid<=t<C.DEV_HI: h2[r["symbol"]]+=1
topN=30
a=set([s for s,_ in h1.most_common(topN)]); b=set([s for s,_ in h2.most_common(topN)])
overlap=len(a&b)/topN
# 频次的秩相关(全体共现币)
common=set(h1)&set(h2)
import statistics as st
print(f"前{topN}惯犯榜 上半vs下半 重合: {overlap*100:.0f}%  (>=50%=猎场池可用)")
print(f"共现币数={len(common)}  上半总事件={sum(h1.values())} 下半={sum(h2.values())}")
print("上半TOP10:",[s for s,_ in h1.most_common(10)])
print("下半TOP10:",[s for s,_ in h2.most_common(10)])
```
- [ ] **Step 2:** 跑 + 判定:
```bash
cd /Volumes/T9/BWE/40_EXPERIMENTS/round14_burst_feature_discovery && python3 persistence_check.py
```
Expected & 判定:重合 ≥50% → 猎场池/历史频次特征**可用**;<30% → 在 REPORT 标注"猎场池=事后幸存者偏差,历史频次特征作废",后续 E 类的 `hist_burst_freq` 降级。**这步结果先报用户。**

### Task 0.4:流动性/可交易性过滤

**Files:** Create `liquidity_filter.py` → 产物 `tradable_universe.json`

- [ ] **Step 1:** 写过滤(用 symbol_counts 的 median_daily_quote_volume 看分布,再剔除):
```python
import csv, json, r14_common as C
rows=list(csv.DictReader(open(f"{C.DIR}/volatility_bursts_all4mo_symbol_counts.csv")))
qv=sorted(float(r["median_daily_quote_volume"]) for r in rows if r["median_daily_quote_volume"])
import numpy as np
print("日均成交额分位: p10=%.2e p25=%.2e p50=%.2e p75=%.2e"%(np.percentile(qv,10),np.percentile(qv,25),np.percentile(qv,50),np.percentile(qv,75)))
THRESH=3_000_000  # 默认 $300万/日 下限;Step2 看分布后可调,需用户确认
keep=[r["symbol"] for r in rows if float(r["median_daily_quote_volume"] or 0)>=THRESH]
json.dump({"threshold_usd":THRESH,"kept":keep,"n_kept":len(keep),"n_total":len(rows)},
          open(f"{C.DIR}/tradable_universe.json","w"),indent=2)
print(f"保留 {len(keep)}/{len(rows)} 币 (阈值 ${THRESH:,})")
```
- [ ] **Step 2:** 跑 + 把成交额分位分布 + 保留币数**报用户**,确认阈值(默认 $300万):
```bash
cd /Volumes/T9/BWE/40_EXPERIMENTS/round14_burst_feature_discovery && python3 liquidity_filter.py
```
Expected: 打印分位 + 保留币数。**CHECKPOINT:把 0.1(事件量)+0.3(持久性)+0.4(流动性分布)一起报用户,确认阈值后再进 0.5。**

### Task 0.5:as-of 因果特征面板 + 无前视断言(本计划最关键、最易错)

**Files:** Create `build_panel.py` → 产物 `panel.parquet`

- [ ] **Step 1:** 写无前视核心约定 + 断言(先写断言,逼着实现遵守):
```python
# 约定:对每个事件,锚点 anchor_ts = event_start_ms(进场时刻)。
# 所有特征只能用 open_time_ms < anchor_ts 的"已收盘"K线(严格小于,不含当根)。
# 前向标签只能用 open_time_ms >= anchor_ts 的1m路径。两者集合不相交。
def assert_causal(anchor_ts, feat_max_ot, label_min_ot):
    assert feat_max_ot < anchor_ts, f"前视!特征用了>=锚点的bar: {feat_max_ot}>={anchor_ts}"
    assert label_min_ot >= anchor_ts, f"标签错位: {label_min_ot}<{anchor_ts}"
```
- [ ] **Step 2:** 写特征计算(A×6粒度 + B-F),每个特征=精确公式。在每个锚点对每粒度 g 取**最后一根 open_time_ms<anchor_ts 的已收盘bar**为 t,回看 k 根:

**A 形态(g∈{1m,3m,5m,15m,30m,1h},命名 `a_<feat>_<g>`):**
`ret1_atr`=(c[t]-c[t-1])/atr14; `ret3_atr`=(c[t]-c[t-3])/atr14; `accel`=ret1_atr[t]-ret1_atr[t-1]; `consec`=末尾连续同向bar数; `body_ratio`=|c-o|/(h-l); `upper_wick`=(h-max(o,c))/(h-l); `range_exp`=(h-l)/mean(h-l,末12根); `compression`=std(ret,末12根)/std(ret,末48根)(<1=蓄势); `dist_base`=(c[t]-c[t-12])/c[t-12]

**B 量(在5m上,`b_*`):** `vol_zs`=(v-mean(v,30))/std(v,30); `vol_trend`=mean(v,末3)/mean(v,末12); `qvol_log`=log(quote_volume[t]); `avg_trade`=quote_volume/trades; `taker_ratio`=taker_buy_base/v
**C 衍生品(特征库,按覆盖期;缺则NaN,`c_*`):** `oi_level`,`oi_chg_1h`,`funding`,`premium`,`top_ls`,`global_ls`(取 ts<anchor 最近一条)
**D 截面(`d_*`):** `xsec_rank_ret60`=该币60min涨幅在全市场所有币该时刻的百分位; `concurrent_bursts`=±30min内其他币的事件数; `btc_ret24h`; `btc_regime`=calibrate.btc_regime_at(anchor_ts)
**E 静态(`e_*`):** `atr_pct`=atr14/c*100; `liq_tier`=log(median_daily_quote_volume); `coin_age_days`=(anchor−首archive bar)/天; `hist_burst_freq`=该币 event_start_ms<anchor 的累计事件数(**只用截止当时**)
**F 时间(`f_*`):** `hour_utc`; `mins_since_last_burst`=anchor−该币上一事件

- [ ] **Step 3:** 全程对每个锚点调用 `assert_causal`;另加随机抽 5 个事件**手工核对**特征 bar 的 open_time 全 < anchor:
```bash
cd /Volumes/T9/BWE/40_EXPERIMENTS/round14_burst_feature_discovery
python3 build_panel.py --selftest   # 内置:抽5事件打印 max(feat_ot) vs anchor,断言通过
python3 build_panel.py              # 全量 → panel.parquet
```
Expected: selftest 全部 `feat_max_ot < anchor_ts` 通过;panel 行数=事件数,列含全部 a_*/b_*/c_*/d_*/e_*/f_* + split 标记。

### Task 0.6:三层前向标签 + 基础率 sanity

**Files:** Create `labels.py`(并入 panel)

- [ ] **Step 1:** 对每锚点从 1m 路径算 H∈{60,120,240}min:
```python
# fwd_ret_H = c1[anchor+H]/entry-1 ; mfe_up_H=max(high)/entry-1 ; mae_dn_H=min(low)/entry-1
# 方向(两面): long_ret_H = fwd_ret_H ; short_ret_H = -fwd_ret_H
# 时机: rem_mfe_H = mfe_up_H ; bars_to_peak_H = argmax(high) 距锚点bar数(大=进得早)
# 风险(按side): short_risk_H = mfe_up_H(逼空逆向); long_risk_H = -mae_dn_H
#   runaway_short = mfe_up_H >= 0.11 ; runaway_long = mae_dn_H <= -0.11  (3x≈11%价位打爆)
entry = c1[j0]  # j0 = 第一根 open_time_ms>=anchor_ts 的1m
```
- [ ] **Step 2:** 跑 + 打印各层**基础率**(无条件下的均值/胜率,作为后续超额的基准):
```bash
cd /Volumes/T9/BWE/40_EXPERIMENTS/round14_burst_feature_discovery && python3 labels.py
```
Expected & **CHECKPOINT 报用户**:打印 dev 上 long_ret/short_ret 的均值+胜率(应≈0,印证"需要选择")、runaway 比例、各层标签覆盖率(无NaN)。

---

## Phase 1 — 逐类描述筛(A→B→C→D→E→F,每类 ×3 层)

### Task 1.1:筛选引擎

**Files:** Create `screen.py`

- [ ] **Step 1:** 写引擎(对一个特征列、一个标签列:dev 上 Spearman + 五分位价差,且**dev 3 折同号 + 妖币/中/大三组同号**才算信号):
```python
import numpy as np, json, pandas as pd, r14_common as C
def spearman(x,y):
    m=~(np.isnan(x)|np.isnan(y)); x,y=x[m],y[m]
    if len(x)<30: return 0.0,0
    rx=np.argsort(np.argsort(x)).astype(float); ry=np.argsort(np.argsort(y)).astype(float)
    rx-=rx.mean(); ry-=ry.mean(); d=(rx**2).sum()**.5*(ry**2).sum()**.5
    return (float((rx*ry).sum()/d) if d else 0.0), len(x)
def qspread(x,y,n=5):
    m=~(np.isnan(x)|np.isnan(y)); x,y=x[m],y[m]
    if len(x)<n*10: return 0.0
    o=np.argsort(x); s=len(x)//n; return float(y[o[-s:]].mean()-y[o[:s]].mean())
def consistent(df, feat, label):   # 3折同号 + 3波动组同号
    signs=[]
    for lo,hi in C.FOLDS:
        sub=df[(df.event_start_ms>=lo)&(df.event_start_ms<hi)]
        if len(sub)>=50: signs.append(np.sign(spearman(sub[feat].values,sub[label].values)[0]))
    for tier in ("majors","mid","yao"):
        sub=df[df.vol_tier==tier]
        if len(sub)>=50: signs.append(np.sign(spearman(sub[feat].values,sub[label].values)[0]))
    return len(set(s for s in signs if s!=0))==1 and len(signs)>=4
```
- [ ] **Step 2:** 对每类(A-F)× 每层标签(long_ret/short_ret/rem_mfe/short_risk/long_risk,H=120主)在 **dev only** 跑筛,输出信号榜 + BH-FDR 标注 + 共试组合数,写 `screen_results.jsonl`。Expected:每类一张榜,明确"信号/弱/噪声";holdout 不碰。

---

## Phase 2 — 组合探索

### Task 2.1:把各类幸存 alpha 点组合

**Files:** Create `combine.py`

- [ ] **Step 1:** 取 Phase1 各类信号榜里"信号"级的特征(每层分别),先 AND/打分组合,再受限浅树(max_depth≤3,min_leaf≥50)+ 嵌套CV(内层调参/外层泛化,全在 dev)。判定:组合的 dev 外层指标必须**打赢该层最好单特征**,否则因复杂度否决。写 `combine_results.jsonl`。Expected:每层给"组合是否 1+1>2"的结论 + 候选规则。

---

## Phase 3 — Holdout 确认(每层一次)

### Task 3.1:封存集最终验

**Files:** Create `holdout_confirm.py`

- [ ] **Step 1:** 取每层最终候选(Phase1 最佳单特征 + Phase2 组合),在 **holdout(04-20→05-25)验一次**:算均值/胜率/Spearman/分位价差 + 扣成本(taker来回0.14%)+ 含死币池子的幸存者偏差复核。写 `holdout_results.json`。判定:dev 强 + holdout 同号同量级才"确认";否则"未通过/噪声"。**此后不得再调参回测。**

### Task 3.2:最终报告

**Files:** Create `REPORT_CN.md`

- [ ] **Step 1:** 中文白话报告,每层(方向/时机/风险):holdout 确认的规则(精确定义+指标)或诚实"无";持久性检验结果;共试 (特征×粒度×层) 组合数 + FDR;前视/成交性/幸存者偏差顾虑;给实盘的下一步建议(是否值得 forward paper-shadow)。

---

## Self-Review(写完计划自查)

**1. Spec 覆盖**:Phase0=spec§5 Phase0(重扫✓持久性✓流动性✓面板✓标签✓);Phase1=逐类筛✓(A 6粒度在 0.5 已含);Phase2=组合✓;Phase3=holdout✓+报告✓;三层标签✓(方向两面 0.6);切分✓(0.2);反过拟合(FDR/跨折跨币组/因果断言/死币/诚实报负)分布在 0.5/1.1/3.1✓;流动性过滤✓(0.4)。**无遗漏。**
**2. 占位符扫描**:无 TBD;流动性阈值 $300万是"默认+看分布+用户确认"非占位;Phase2/3 的"取幸存特征"是数据依赖输入非占位(方法代码完整)。
**3. 类型一致**:`event_start_ms`/`anchor_ts`/`split_of`/`vol_tier`/`FOLDS` 全程一致;特征命名 `a_*_<g>`/`b_*`..`f_*` 一致;标签 `long_ret_H/short_ret_H/rem_mfe_H/short_risk_H/long_risk_H/runaway_*` 一致。
