---
type: plan
tags: [round27, usstock, tradfi-perp, alpha-search, protocol]
created: 2026-07-02
status: wip
priority: high
---

# Round27 美股永续 alpha 搜索 — 预注册协议(动手前冻结)

## Goal(用户原话)
"产出有效的美股量化 alpha, 在 binance 上进行美股代币合约交易"。不做高级的; 简单新闻/事件驱动可接受。

## 数据(全部已到位/在跑)
- **价格**: 105只 EQUITY 永续全历史 1m K线 + 真实8h资金费(2026-01~今, EC2回填中, tradfi_full_history.sqlite3)
- **财报**: UW /earnings/afterhours + /premarket + /earnings/{ticker}(report_date/time, actual vs street, 盘后反应, expected_move)
- **宏观日历**: FRED release dates(CPI/NFP/PCE) + FOMC静态日程
- **期权流**(次级): UW market-tide / flow-alerts
- **forward期新增**: Finnhub 财报日历(只给当前窗) + AlphaVantage news(25/天, 只选择性用)
- ❌ FMP免费档=废; Twitter=噪声, 本轮不用

## 候选族(全部过"坟场滤镜": 无裸方向、无选股、事件/结构型)
| 族 | 假设 | 数据 |
|---|---|---|
| A 时段回归 | 闭市时段(隔夜/周末)永续漂移过头 → 开盘窗回归 | K线 |
| B 周末效应 | 周五收→周日/周一的perp行为与周一开盘收敛 | K线 |
| C 宏观事件窗 | CPI/FOMC/NFP固定时刻前后, perp过冲/回归/漂移模式 | K线+FRED |
| D PEAD | 财报后1-5天沿surprise方向漂移(文献经典) | K线+UW |
| E 财报隔夜过冲 | 盘后财报→perp即时反应过冲→次日开盘回归 | K线+UW |
| F 资金费横截面 | 费率极端分位的币, 未来1-3天相对(非绝对)表现 | K线+funding |
| G 期权流(次级) | UW净call/put premium极值 → 次日perp表现 | UW+K线 |

## 纪律(与round26同一套, 全部强制)
1. **切分**: dev = 2026-01-01~05-31 | val = 06-01~06-15 | **处女holdout = 06-16~今(任何脚本不得触碰, 终审一次性揭晓)**
2. **成本**: taker 0.04%×2 + 实测点差(book表/保守2bp/边); 持仓跨结算算真实资金费
3. **BH-FDR** 全族统一校正(报总cell数); LODO(单日占比>40%毙); 做空看均值; n<100探索性
4. **β剥离**: 一切方向性结果必须同时报"扣同期QQQ永续β后的残差"(round25教训: 方向edge=β伪装)
5. **执行现实**: 滞后衰减曲线(+0/+1/+5/+15min) + 滑点加压; 容量现实(B教训)
6. 幸存者 → 对抗验证agent + Codex跨模型复审 → 处女holdout一次揭晓 → forward paper(预注册门)
7. **零真钱**; 上钱前置条件不变: 子账户隔离 + 用户显式确认

## 预注册验收门(holdout后适用于任何幸存族)
- holdout净期望>0 且 与dev/val同号
- 扣QQQ-β残差仍>0
- LODO过 + 单名占比<40%(MRVL教训)
- 执行加压(+1bar × 1.5×成本)仍>0

## 产出
- `alpha_screen/` 各族脚本+JSON | `FINAL_VERDICT.md` 终审 | 幸存者 → forward记分台(EC2, 复用c2框架)

## 🔁 循环状态(goal: 找到有效alpha才退出 — 用户2026-07-02指令)
**退出条件(冻结)**: ≥1族同时满足 dev+val通过 ∧ 处女holdout(06-16+)同号为正 ∧ 对抗+Codex存活 ∧ β剥离后仍正。
不满足 → 不退出: 新机制族 → forward数据长大 → 再战。绝不为退出放宽标准。

### 进度日志
- [2026-07-02] 协议冻结; 105只全历史回填启动(EC2, Monitor挂); UW财报+FRED日历拉取启动(Mac后台, Monitor挂)
- [2026-07-02] 回填完成(738万K线/105只/8796结算, integrity ok); 面板建成(3389行, devval 2262行结构隔离)
- [2026-07-02] 🔎发现: 永续周末bar占29.5% = 周末真在交易, B族结构成立
- [2026-07-02] A/B/C/F四族Workflow发射(wf_12348938); D/E等UW财报拉取完成
- [2026-07-03] A/B/C/F四族判决: **276 cells 零幸存** (4/4对抗verify=holds)
  - A(108): β伪装+val反号 | B(64): 周末结构真但=β+流动性不可执行 | C(96): 闭市print独家定价结构成立但幅度<成本, n太小 | F(8): 费率太小+单名集中
  - 死因排序: β伪装 > 聚类t虚胖(iid t虚报40-70%) > 成本墙 > 单名集中
  - **holdout不揭晓(零候选, 完整保留)**; C族宏观结构地图留作forward假设(FOMC 7-29优先)
  - 方法学升级(D/E起强制): 公平β̂剥离(非β=1) + 事件日聚类t≥2 + 时间戳尖峰校验
- [2026-07-06] D/E族判决:
  - **D族PEAD = 本轮最强发现(verify=holds且复算后更强)**: 沿正股reaction符号持2天 = +2.13%剥β净/事件, 聚类t2.25, n=23, 两侧均正, LOSO最差+1.60, 单cell perm p=0.0054, 过门族max-t校正p=0.032, 0.5%RT成本仍+1.75。**但n=23探索性 → 冻结规则D_PEAD_rxn_sign_h2, 7月Q2财报季forward验证(过门=剥β净>0∧n≥15∧两侧非负∧1.5×成本)**
  - E族(隔夜drift) = verify降级weakened: 66cell null搜索下t=2.62有1/3概率纯噪声产生; 冻结E_afterhours_drift_v1只做forward陪跑(kill=n≥10后净≤0或胜<60%)
  - 关键数据坑(已修): 53/79事件时perp未上线 → 有效n远小于表面; 7月财报季时87+只已上线, forward样本会大得多
- [2026-07-06] **r27-forward记录器部署EC2**(每日04:20UTC: 顶补K线→UW拉新财报→评估成熟事件→D/E账本), 含verify三修正(15:55信号价/流动性下限$50k/上线≥7天)
- [2026-07-06] 第二波workflow发射(wf_f9f356): H新上市效应 / I跨品种lead-lag / J结算时刻
- [2026-07-06] 第二波H/I/J判决(207 cells):
  - H(27): 上市泵不存在; "上市拥挤→day1衰减"两期同号但perm搜索null p=0.246 → 零幸存, 冻结H_list_d1_short_v1 forward陪跑(verify=holds, 逐位复现)
  - I(96): 闭市lead-lag结构真实(CCF=RTH对照3-4倍)但毛0.09% vs 双腿成本0.27% = 3.7倍成本墙 → 全灭, 无forward规则
  - **J(72): 结算V形=全轮最强现象**(聚类t=8.4, perm p<0.001, β三法稳健, 4个月全正, val方向复现): 结算前逆费率漂移→结算后顺费率回弹(首分钟24bp)。可交易性未决(T-1进场要付结算费≥10bp), verify=weakened(现象实、经济性悬) → 冻结J_settle_v1 forward裁决
  - 累计: 三波613 cells, 即时可交易幸存=0; forward假设池: D(主)+J(快)+E/H(陪跑)+C宏观(FOMC 7-29)
- [2026-07-06] 记录器扩展: J账本(预测费率来自collector实时采样=T-1真实可知; 净值含结算费支付)+H账本(06-16后新上市回补)已部署, 下轮自动回补
- [2026-07-06] 首批forward账本出数: D n=2(淡季) | E n=2 | J n=165(+0.069%, 右尾拉的) | H n=10(+5.12%! 胜70%, 未到门槛n=15)
- [2026-07-06] **数据补全(用户质询"是否用全"后)**: ①UW期权流历史全绿(tide/每票量/darkpool/greeks/net-prem分时全可回溯3月+) → G族拉取中(~9k请求) ②实测点差入账: 全105只中位7.7bp但TSLA/MU/QQQ/SPY仅0.1-0.4bp ③Finnhub每票EPS surprise已落盘(补D)
- [2026-07-06] **J预登记细分(非事后选择, 立即注册)**: J_settle_v1_tight = 只做book中位点差≤2bp的窄票; 初始证据: 真实成本重打 窄组+0.127%/胜53%(n=17) vs 宽组死。过门=窄组n≥50后净>0∧按结算簇稳
- [ ] G族数据齐 → G族筛选workflow(期权流→次日永续截面, 中性构造) → 循环继续
- [ ] J窄组攒n(~0.8/天, 6-8周) | D财报季(下周) | H再等5个上市 → 任一过门 → Codex终审
- [ ] 有幸存者 → forward记分台(EC2) | 无 → 记录死因, 开新族循环
