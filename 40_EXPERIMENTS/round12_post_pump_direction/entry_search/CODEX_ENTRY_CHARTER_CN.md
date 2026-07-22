角色:自主量化研究员。目标:为币安U本位永续"波动暴增/拉升"事件找出有真alpha的入场信号(主:做多追延续;兼:做空追回调)。必须先粗筛每个方向有无alpha,再细筛幸存者。中文白话汇报。

[运行预算] 总跑24小时后退出。把24h在各方向/阶段平均分配(先估方向数再均摊,别在一个方向耗光);每跑完一个方向落盘一次中间结果以便续跑。

[本机性能] 这台Mac同时在跑实盘收集器,务必克制:SQLite只读、并发≤4、勿把20GB库全载内存(按币分批流式)、重循环加微sleep避免占满CPU/IO、先少量币验证脚本再全量。

[背景] 我们做空策略亏在"被拉升过冲、在回调前被止损"。用户想法:近5-15min涨幅÷过去1-2h平均波动≥N→做多持1-2h。已知基线(别重发现、须超越):裸"任意burst(ratio≥2)追多"=+1h/2h≈0%、胜率45%=无edge;仅高波动妖币(atr_pct≥1.5%)+中极端N≈3-5+放量有微弱信号(+2h+0.4~0.9%),但最大逆向≈−8%,杠杆下难吃。方向整体近抛硬币,edge只在"选择"。先验:多数方向是噪声,任务是诚实筛选,不是不惜代价找赢家。

[数据(全在本机;Mac被墙,勿curl币安fapi;data.binance.vision可用)]
1.K线归档(只读)/Volumes/T9/BWE/30_DATA/binance_collectors_runtime/binance_futures_klines_archive.sqlite3:klines_{1m,3m,5m,15m,30m,1h,2h,6h}(symbol,open_time_ms,OHLCV,close_time_ms,quote_volume,trades,taker_buy_base,taker_buy_quote);640币,01-27→05-25。
2.特征库(只读)同目录binance_futures_1m.sqlite3:liquidations(强平~24d)、open_interest、global_long_short_account_ratio_5m、basis_perpetual_5m、funding_rate;用.schema查列,可ATTACH联查。
3.已建标注/Volumes/T9/BWE/40_EXPERIMENTS/round12_post_pump_direction/pump_events.csv(23万事件,列含atr_pct/ret60_atr/ret5_atr/rsi/vol_zs/ratio_5m,10m,15m/ret_30m,1h,2h,4h/mfe_up,mae_dn);构建器phase0_build_events.py(加新特征改它)。
4.可复用round8_calibration/calibrate.py(ATR/退出/regime)。

[必须逐个粗筛的方向]
轴1分子:方向涨幅|绝对位移|真实波幅|已实现波动|ATR归一收益|单根振幅扩张|速度+加速度|量暴增|连阳数|taker失衡|OI跳增
轴2基线:1-2h均值|z分|ATR|滚动百分位|EWMA|24h波动|Parkinson|绝对阈值
轴3窗口:短窗{1,3,5,10,15min}×基线{30m,1h,2h,4h,24h};多粒度共振(3m&5m&15m);快爆+慢趋势同向
轴4阈值形式:固定N倍|z分|百分位|自适应N|多条件AND|复合打分
轴5条件:币种波动级(妖币vs大币,已知关键)|流动性|时段|BTC regime|在行情中的位置(早期vs力竭)|当日已涨过|资金费率/OI/逼空
轴6方向形态:只做多|实体vs上影|抛物线vs慢磨vs单尖|突破前高vs半空尖刺
轴7归一框架:时序(比自己近期)|截面(比此刻全市场,谁最猛)|混合
每方向同时看做多(延续)与做空(回调)两套标签。

[方法 粗→细→holdout]
切分:holdout=最近35天(ts≥now−35d≈04-22),封存,筛选前绝不读、不参与任何选择;DEV=更早55天用walk-forward(扩展30d训→12d验→滚动)。
①粗筛(便宜广快):每个轴取值在DEV上看前向收益的五分位价差+Spearman+分桶均值有无单调信号、且按妖币/大币分层仍成立=过,否则记噪声丢。不调参,只判有无,出粗筛榜。
②细筛(仅幸存者):扫参(N/W/L/条件)+walk-forward交叉验证+成本(taker费+滑点;急拉可能成交不了,实盘>0.8%滑点弃单)+简单退出(记前向收益与MFE/MAE使评判与退出解耦),出候选规则。
③holdout仅一次:top候选在封存集评一次,扛不住即否决。

[反过拟合硬规则(违则作废)]
-holdout全程封存,只在③用一次。
-"赢家"须:明显超基线+跨折跨币组一致+单调(非单桶走运)+holdout确认;单窗/单桶/变号=噪声。
-多重比较:会测上百组合,纯运气也蒙中→要一致性非单点显著;p值用BH-FDR;报共试多少组合。
-无前视:入场特征只用≤入场bar数据(前向收益是标签);结果好得离谱(胜率>65%或单笔>2%)先停查泄漏。
-全部方向含失败都报;诚实报负是主交付;"多数是噪声"可接受。

[输出]脚本+中间结果+最终报告写到.../round12_post_pump_direction/entry_search/。报告(中文白话):①粗筛榜(每方向 信号/噪声)②幸存者细筛③holdout确认的最佳入场规则+指标 或 诚实"无稳健alpha"④共试多少组合+FDR⑤前视/成交性顾虑。

[硬约束]数据只读;只写entry_search/;不碰任何实盘脚本/配置;不调用币安fapi(被墙);真钱研究,结果看强先默认泄漏/过拟合直到证伪。
