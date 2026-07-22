#!/usr/bin/env python3
"""
双腿资金费 carry 核算 (stockusbinance)
=====================================
策略: Binance 做空 TradFi 股票永续 + moomoo 买等值正股 -> 方向中性, 吃永续多头付的资金费.

数据 (只读): tradfi_capture_ec2.sqlite3
  - bf_funding: 真实 8h 结算资金费率 (11 标的, 2026-05-15 ~ 06-11)  -> 收入来源
  - funding:    forward 分钟级 mark/index 快照 (仅 06-11 一天)        -> 基差波动 (跟踪误差)
  - book:       永续盘口实测点差 spread_bp (06-11 一天)               -> 执行成本

诚实原则: 把所有真实成本扣干净, 负就是负. 不美化.

输出: carry_results.json + 终端核算表.
"""
import sqlite3, json, math, statistics, os

DB = os.path.join(os.path.dirname(__file__), "..", "tradfi_capture_ec2.sqlite3")
OUT = os.path.join(os.path.dirname(__file__), "carry_results.json")

# ---- 成本假设 (全部标注, 可调) ----
PERP_TAKER_FEE = 0.0004        # Binance USDT-M taker 0.04% / 边 (保守, 不假设 maker)
STOCK_SPREAD_BP_PER_SIDE = 2.0 # 美股大盘股点差假设 2bp/边 (NVDA/QQQ 等流动性好, 1-3bp 合理; 取中值)
STOCK_COMMISSION = 0.0         # moomoo 美股 0 佣金 (主流促销; 若有则 +)
# 注: 美股点差 2bp/边 是合理保守假设 — Binance 永续点差实测在 book 里, 美股侧无实测数据故用假设并标注.

HOLD_DAYS_SCENARIOS = [7, 30]  # 持仓 N 天的基差潜在偏离折算
HEDGE_LEG_USD = 500.0          # $1000 散户: 对冲腿 $500 (永续空 $500 名义, 正股 $500)
COST_RATIO_THRESHOLD = 0.20    # 成本占收入 <20% 视为"经济" -> 反推最小本金

CANDIDATES = ['NOKUSDT','MRVLUSDT','MUUSDT','GOOGLUSDT','NVDAUSDT',
              'QQQUSDT','AVGOUSDT','TSLAUSDT','METAUSDT','TSMUSDT','AMZNUSDT']

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row


def fetch_funding(sym):
    rows = con.execute(
        "SELECT funding_time, funding_rate FROM bf_funding WHERE symbol=? ORDER BY funding_time",
        (sym,)).fetchall()
    return [(r["funding_time"], r["funding_rate"]) for r in rows]


def fetch_basis(sym):
    """forward 表: (mark-index)/index, 单位 fraction. 仅 06-11 一天 (局限!)."""
    rows = con.execute(
        "SELECT mark, index_px FROM funding WHERE symbol=? AND index_px>0 ORDER BY ts",
        (sym,)).fetchall()
    return [(r["mark"] - r["index_px"]) / r["index_px"] for r in rows]


def fetch_spread_bp(sym):
    rows = con.execute(
        "SELECT spread_bp FROM book WHERE symbol=? AND spread_bp IS NOT NULL", (sym,)).fetchall()
    vals = [r["spread_bp"] for r in rows]
    return vals


def fetch_mark(sym):
    r = con.execute("SELECT AVG(mark) m FROM funding WHERE symbol=?", (sym,)).fetchone()
    return r["m"]


results = []
for sym in CANDIDATES:
    fund = fetch_funding(sym)
    if not fund:
        continue
    rates = [r for _, r in fund]
    n_settle = len(rates)
    avg_rate = statistics.mean(rates)                 # 平均每次 8h 结算费率 (fraction)
    # 年化: 每天 3 次结算 * 365
    ann_funding = avg_rate * 3 * 365                   # 做空收到的年化收入 (fraction)

    # --- 衰减检查: 前半 vs 后半 ---
    half = n_settle // 2
    early = statistics.mean(rates[:half]) if half > 0 else avg_rate
    recent = statistics.mean(rates[half:]) if half > 0 else avg_rate
    decay_ratio = (recent / early) if early != 0 else float("nan")

    # 负费率次数 (这些时段做空要倒付)
    neg_count = sum(1 for r in rates if r < 0)

    # --- 基差波动 (跟踪误差) ---
    basis = fetch_basis(sym)
    basis_std = statistics.pstdev(basis) if len(basis) > 1 else 0.0   # fraction, 日内
    basis_mean = statistics.mean(basis) if basis else 0.0
    basis_std_bp = basis_std * 1e4

    # --- 执行成本 ---
    spreads = fetch_spread_bp(sym)
    perp_spread_bp = statistics.median(spreads) if spreads else 4.0   # 实测中位数; 无则保守 4bp
    perp_spread_frac = perp_spread_bp / 1e4

    # 一次完整 carry = 建仓(开空+买股) + 平仓(平空+卖股), 即双边各往返
    # 永续往返成本 (fraction of notional, 单边名义):
    #   taker 2 次 (开+平) + 点差 2 次 (开吃 ask 平吃 bid, 1 次往返 = 1 个 spread)
    #   保守: 往返穿 1 个 spread (开+平各半个) -> 1*spread; taker 2*fee
    perp_rt_cost = 2 * PERP_TAKER_FEE + 1 * perp_spread_frac
    # 正股往返成本 (fraction):
    stock_rt_cost = 2 * STOCK_COMMISSION + 1 * (2 * STOCK_SPREAD_BP_PER_SIDE) / 1e4  # 开+平各 2bp = 4bp 往返
    # 情形 a: 需新建多头腿 -> 双腿往返成本都算
    total_rt_cost_a = perp_rt_cost + stock_rt_cost
    # 情形 b: 已持正股 (多头腿免费) -> 只算永续往返
    total_rt_cost_b = perp_rt_cost

    # 把一次性往返成本年化: 取决于持仓周期. carry 想吃满需长期持有.
    # 假设平均持仓 30 天换一次仓 (合理: carry 是慢策略) -> 年化摊销 = cost * (365/30)
    HOLD_FOR_AMORT = 30
    amort_factor = 365.0 / HOLD_FOR_AMORT
    ann_cost_a = total_rt_cost_a * amort_factor
    ann_cost_b = total_rt_cost_b * amort_factor

    # --- 净 carry (年化) ---
    net_carry_a = ann_funding - ann_cost_a
    net_carry_b = ann_funding - ann_cost_b

    # --- 基差风险折算到持仓 N 天 (随机游走近似: std_N = std_daily * sqrt(N)) ---
    basis_risk = {}
    for nd in HOLD_DAYS_SCENARIOS:
        basis_risk[f"{nd}d_std_bp"] = round(basis_std_bp * math.sqrt(nd), 2)

    # --- $ 收益 @ HEDGE_LEG_USD ---
    # 月资金费收入 (毛) = avg_rate * 3 * 30 * notional
    monthly_funding_gross = avg_rate * 3 * 30 * HEDGE_LEG_USD
    # 月净 (情形 b, 假设月初建月末平一次): 毛 - 一次双边往返(b)
    monthly_net_b = monthly_funding_gross - total_rt_cost_b * HEDGE_LEG_USD
    monthly_net_a = monthly_funding_gross - total_rt_cost_a * HEDGE_LEG_USD

    # --- 最小经济规模: 成本占收入<20%. 成本里有固定执行(往返), 收入随名义线性 ---
    # 月毛收入(/名义) = avg_rate*3*30; 月成本(/名义, 情形a一次往返) = total_rt_cost_a
    # 注: 二者都是 fraction-of-notional, 实际不随名义变 (都是比例) => 比率与本金无关!
    # 真正不随名义缩放的是"绝对最小手续费/最小下单"约束, 这里 Binance/moomoo 无显著最小额,
    # 故经济性由"比率"决定而非"规模". 我们改为算: 净收益为正所需的最低费率(已知), 并报月绝对$.
    monthly_funding_per_dollar = avg_rate * 3 * 30  # 每 $1 名义的月毛资金费
    # 成本占收入比 (情形 a, 按 30 天持仓摊销一次往返):
    cost_over_income_a = (total_rt_cost_a) / monthly_funding_per_dollar if monthly_funding_per_dollar > 0 else float("inf")
    cost_over_income_b = (total_rt_cost_b) / monthly_funding_per_dollar if monthly_funding_per_dollar > 0 else float("inf")

    results.append({
        "symbol": sym,
        "n_settlements": n_settle,
        "avg_rate_pct_per_8h": round(avg_rate * 100, 5),
        "ann_funding_pct": round(ann_funding * 100, 3),
        "early_pct_8h": round(early * 100, 5),
        "recent_pct_8h": round(recent * 100, 5),
        "decay_ratio_recent_over_early": round(decay_ratio, 3) if not math.isnan(decay_ratio) else None,
        "neg_funding_count": neg_count,
        "perp_spread_bp_median": round(perp_spread_bp, 3),
        "perp_rt_cost_pct": round(perp_rt_cost * 100, 4),
        "stock_rt_cost_pct": round(stock_rt_cost * 100, 4),
        "ann_cost_a_newleg_pct": round(ann_cost_a * 100, 3),
        "ann_cost_b_haveleg_pct": round(ann_cost_b * 100, 3),
        "net_carry_a_newleg_pct": round(net_carry_a * 100, 3),
        "net_carry_b_haveleg_pct": round(net_carry_b * 100, 3),
        "basis_mean_bp": round(basis_mean * 1e4, 2),
        "basis_std_daily_bp": round(basis_std_bp, 3),
        "basis_risk_holdN": basis_risk,
        "monthly_funding_gross_usd@500": round(monthly_funding_gross, 2),
        "monthly_net_a_usd@500": round(monthly_net_a, 2),
        "monthly_net_b_usd@500": round(monthly_net_b, 2),
        "cost_over_income_a": round(cost_over_income_a, 3),
        "cost_over_income_b": round(cost_over_income_b, 3),
        "avg_mark": round(fetch_mark(sym), 2),
    })

# 排序: 按情形 b (已持正股) 净 carry 降序 — 这是用户场景最优情况
results.sort(key=lambda x: x["net_carry_b_haveleg_pct"], reverse=True)

meta = {
    "assumptions": {
        "perp_taker_fee_per_side": PERP_TAKER_FEE,
        "stock_spread_bp_per_side": STOCK_SPREAD_BP_PER_SIDE,
        "stock_commission": STOCK_COMMISSION,
        "hold_days_amortization": 30,
        "hedge_leg_usd": HEDGE_LEG_USD,
        "annualization": "avg_8h_rate * 3 settlements/day * 365",
        "basis_risk_model": "daily pstdev * sqrt(N days)  [random walk approx]",
    },
    "data_limitations": {
        "bf_funding": "real 8h settlements 2026-05-15~06-11 (~27d), 11 symbols only",
        "funding_forward_basis": "ONLY 2026-06-11 single day -> basis std is intraday, not multi-day. sqrt-scaling is an approximation.",
        "book_spread": "ONLY 2026-06-11 single day intraday median",
        "negative_funding": "during neg-funding settlements the SHORT leg PAYS — already netted into avg_rate",
    },
    "results": results,
}

with open(OUT, "w") as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)

# ---- 终端核算表 ----
print("=" * 140)
print("双腿资金费 CARRY 核算表  (做空 Binance 永续 + moomoo 买正股, 吃多头付的资金费)")
print("数据: bf_funding 真实 8h 结算 2026-05-15~06-11 | basis/spread 仅 06-11 一天 (标注局限)")
print("=" * 140)
hdr = f"{'标的':<10}{'年化费率%':>9}{'永续往返%':>9}{'净@a新腿%':>10}{'净@b已持%':>10}{'基差std/日bp':>12}{'基差30d偏离bp':>13}{'月净@500$(b)':>13}{'衰减比':>8}{'负费次':>6}"
print(hdr)
print("-" * 140)
for r in results:
    print(f"{r['symbol']:<10}{r['ann_funding_pct']:>9.2f}{r['perp_rt_cost_pct']:>9.3f}"
          f"{r['net_carry_a_newleg_pct']:>10.2f}{r['net_carry_b_haveleg_pct']:>10.2f}"
          f"{r['basis_std_daily_bp']:>12.2f}{r['basis_risk_holdN']['30d_std_bp']:>13.2f}"
          f"{r['monthly_net_b_usd@500']:>13.2f}{(r['decay_ratio_recent_over_early'] if r['decay_ratio_recent_over_early'] is not None else float('nan')):>8.2f}"
          f"{r['neg_funding_count']:>6d}")
print("-" * 140)
print(f"成本假设: 永续 taker {PERP_TAKER_FEE*100:.2f}%/边×2 + 实测点差中位数; 正股 {STOCK_SPREAD_BP_PER_SIDE}bp/边往返{2*STOCK_SPREAD_BP_PER_SIDE}bp + 佣金{STOCK_COMMISSION}")
print(f"摊销: 一次双边往返成本按 30 天持仓年化 (carry 是慢策略)")
print(f"基差风险: 日内 std × sqrt(N) [随机游走近似] — 注意仅 1 天数据, 真实多日 std 大概率更大")
print(f"\nJSON -> {OUT}")

con.close()
