# BWE 项目设计规则 — Claude 必读

> 这份文件是用户在 round 5 交互中反复纠正 Claude 的总结。
> 每次新 session 开始处理 BWE 项目时, **先读完整份再动手**, 避免重犯错。

---

## ⚡ Rule #0: 数据驱动 (DATA-DRIVEN IMPERATIVE)

**这是最高优先级原则。其他所有规则都是这条的下位规则。**

### 强制流程 — 任何策略相关回答前必做

```
用户问: "X 策略好不好?" / "X vs Y 哪个强?" / "加这个 filter 行吗?" / "magnitude 改 5-12 还是 3-10?"
                                ↓
        ❌ 不允许: 凭直觉/经验/逻辑推理回答
        ❌ 不允许: "我觉得 X 应该好, 因为 ..."
        ❌ 不允许: "理论上 X 比 Y 好"
                                ↓
        ✅ 必须: "我先跑一下 30 天数据, 然后告诉你结果"
        ✅ 必须: 跑 backtest → 拿 sum/mean/win/cap 数字 → 用数字回答
        ✅ 必须: 多策略比较用同一个 candidate pool + 同一个 exit
                                ↓
                只用数据说话
```

### 这条规则适用所有场景

| 场景 | ❌ 错误做法 | ✅ 正确做法 |
|---|---|---|
| 推荐策略 | "我推荐 ATR×10 因为 mean-reverting 适合宽 SL" | 跑 ATR×{5,8,10,12,15} 5 个变体, 报 sum 最高的 |
| 比较策略 | "BROAD 应该比 QUAL 好因为样本大" | 跑两个在同 30 天数据 + 同 exit, 看 sum 排名 |
| 调参 | "magnitude 改 3-12 试试看, 直觉上更好" | 跑 mag {3-10, 3-11, 3-12, 3-13} 4 个变体, 看哪个 sum 最高 |
| 加 filter | "加 funding>0 应该筛出更高质量信号" | 跑 ablation: 加 filter 前后 sum/mean 对比, 升才加 |
| 频率合理? | "1 小时 0 个 open 看起来低" | 算 backtest 期望频率 vs 实际, 用 Poisson 评估偏差 |
| Bug 影响 | "这个 bug 应该影响不大" | 跑数据复现 bug, 量化丢失多少 alpha |
| 风控决策 | "3x 杠杆应该够安全" | 算强平价格 vs SL 距离, 用具体数字论证 |

### 数据驱动的 4 个具体工具

**1. ablation 测试 (验证单 filter 是否保 alpha)**:
```python
baseline = run_backtest(events_with_yao_filter)  # baseline strategy
test = run_backtest(events_with_yao_filter + new_filter_X)
if test.sum >= baseline.sum: keep filter X
else: drop filter X (它在剪 alpha 不是加)
```

**2. 同口径对比 (多策略横向比较)**:
- 同 candidate pool (例如 833 个 5-15% pricechange-pumps)
- 同 exit (例如 60min ATR×10 + lock 35→18@12)
- 同评估指标 (sum, mean, win, capture)
- 用单一指标排序 (推荐 sum, 因为兼顾频率 + 质量)

**3. Poisson 频率检验 (实际 vs 期望)**:
- backtest 期望: N trades / 30 days = N/(30*24) per hour
- 实际 X hours 内: 应该有 X * N/(30*24) ± sqrt(X * N/(30*24)) (Poisson 标准差)
- 偏差 > 2 sigma → 数据有问题, audit

**4. 完美 MFE 上限对比 (capture 率)**:
- 跑 ideal: 每个 trade 用最大 MFE 退出 → 这是 100% capture
- 当前策略 sum / ideal sum = capture rate
- < 30%: 还能优化 / > 60%: 接近天花板

### 如果数据矛盾用户 intuition

**用户原话: "数据是真的, 我的 intuition 可能错"**

例子: 用户主张「妖币 = 小盘币」, 数据显示 vol_24h ∈ [5M, 50M] 过滤会让 sum 从 +2035 → -1500。

✅ 正确: "数据上你的假设不成立, 我建议改方向" + 数据 sheet
❌ 错误: 跟着用户直觉走, 不跑数据

**"我去验证一下" 是正确回答**, "这听起来对" / "这听起来不对" 都不是。

### 例外 — 真实可豁免 data-driven 的少数场景

只有这 4 种情况不必跑数据:
1. **代码 bug 修复** (算法对错可以直接看代码)
2. **基础设施问题** (parser/database/cache, 跟策略无关)
3. **用户偏好确认** (例如杠杆几倍, 用户直接说就行)
4. **明确的数学不等式** (例如 "0.5 < 1.0 是对的")

其他**所有策略 / 参数 / 信号 / filter** 相关回答 → 必须先跑数据。

---

## 核心原则 (按优先级)

### 1. 数据先于直觉 — 任何假设都要 backtest 验证

**❌ 我犯过的错**: 凭直觉给 entry 选择 single-indicator (magnitude / yao / funding 任一), 没跑数据就给用户推荐。
**✅ 用户要求**: 必须用真实 30 天数据测每个 hypothesis, 用 sum/win/cap 排序。
**规则**:
- 所有策略/参数选择必须有数据支持
- "我觉得 X 应该好" → "我跑了数据看 X 在 30天里实际表现是 Y"
- 任何单 filter / 单参数变体都要用 ablation 测过

### 2. 妖币 ≠ 小盘币

**❌ 我犯过的错**: 把"妖币策略"理解成"小市值币" → 推荐 vol_24h ∈ [5M, 50M] 过滤。
**✅ 数据反驳**: 这个过滤 sum 从 +2035 变成 -1500 (vol cap 大幅减 alpha)。
**用户原话**: "做妖币（但不是做小盘币，不要理解偏差了）"。
**正确定义**: 妖币 = **行为特征** (24h 内反复 pump/dump, lifecycle = sustained, prior_pumps ≥ 3)。
**规则**:
- 永远不要用市值/vol_24h 做妖币定义
- 用 prior_pumps_24h count + has_dump_24h + lifecycle 来识别妖币
- 妖币行为指纹: 反复 pump-dump-pump 节奏 + 高换手率

### 3. 多 indicator 组合 - 不要 single-indicator 策略

**❌ 我犯过的错**: 第一次给用户列 entry/exit 策略时全是 "fade 单条件" 的。
**✅ 用户要求**: "exit 一定要吃饱利润, entry 一定不要漏 alpha", 每个策略要有清晰 thesis + 4-6 个互不冗余指标。
**规则**:
- 每个策略 = **coherent thesis** (1 句话: 为什么这个能 alpha) + **4-6 个互不冗余 filter**
- 每个 filter 必须独立贡献 evidence, 不能两个 filter 测同一件事
- 例子: 「极妖币 + 拥挤多」= prior_pumps≥7 (操纵深度) + funding>0 (持仓拥挤) → 2 个独立维度

### 4. Exit 一定要吃饱, Entry 一定不要漏 alpha

**用户原话**: "entry 一定不要漏 alpha, exit 一定要吃饱利润"。
**Exit 规则**:
- 不要早出 (TP cap kills alpha — 数据上 TP +5% sum 直接腰斩)
- Wide TP / 没 TP, 让大反转跑完
- Dynamic exit (但要小心 — 见规则 #5)

**Entry 规则**:
- 每个 filter 加上后必须 **保住或提升** 数据上的 mean, 否则就是损失 alpha
- ablation 验证: 加 filter 前后 sum 对比, 不升就不要加

### 5. "动态 exit" 真正含义 - 不是反应噪音

**❌ 我犯过的错**: 设计「ATR×0.5 紧 trail」 / 「MFE retrace 30%」 — 被 path noise 打穿, capture 仅 22%。
**✅ 数据真相**: 这个 yao 信号 path 极嘈杂 (50%+ trades 反向跑 5-15% 才反转), 任何看 path state 的 dynamic exit 都被 oscillation 误触。
**用户原则**: time 不能是 primary trigger, 但 time 可以是 factor (e.g., MFE 阶梯触发后的兜底)。
**规则**:
- Path-based exit (trail / retrace) 在 mean-reverting 信号上**反向 reduce alpha**
- 真正的 dynamic = 反应**经济状态变化** (momentum, flow, fundamentals 翻转), 不是反应价格 oscillation
- 如果数据显示 4h hold 是最优, 接受这个事实, 但加 SL/MFE-lock 兜底使其更"动态"

### 6. 风控不可妥协 — 合约必须有 SL

**用户原话**: "做的是合约，一次爆仓就全盘皆输"。
**规则**:
- 任何 exit 必须有 SL 兜底
- SL 距离强平点必须有 ≥10% 安全垫 (见 round 5 文档「杠杆 vs SL 数学」)
- 对妖币 high-vol 信号: ATR-scaled SL 比固定 % SL 更适合 (calm 币紧, vol 币宽)
- 杠杆推荐: 2-3x 配 ATR×10 SL, **绝对不超 5x**

### 7. 真 40 轮搜索 — 每轮新机制不重复

**❌ 我犯过的错**: 第一次 entry 搜索 phase 2-4 大部分是同一机制改参数。
**✅ 用户要求**: 严格 40 轮, 每轮**真正不同的机制**, phase 4 才是 deep refinement。
**规则**:
- Phase 1 (R1-10): 10 个最基础 single dimension
- Phase 2 (R11-20): 10 个不同 mechanism (新维度)
- Phase 3 (R21-30): 10 个 derived/microstructure 特征
- Phase 4 (R31-40): 取前面前 5 名做参数 deep grid
- **10 轮无 breakthrough → 反思 + 换方向**, 不能继续在同一机制上转
- 任何 round 如果是「上一轮 winner 的参数变体」→ 跳过, 换真正新的

### 8. Codex audit + 自审 — 重大代码改动必做

**用户原话**: "代码改好之后要自己全部审查一遍。这遍改完之后再次审查一遍"。
**规则**:
- 任何修复 critical / high bug 后:
  1. 调 codex 做 audit
  2. 自己 verify codex 每条 finding (用数据 / 阅读代码)
  3. 修复后再调 codex 做 round 2 audit (查 regression)
  4. 修 round 2 发现的 regression
- **不能盲信 codex** (它也会漏 / 误判)
- **不能跳过自审** (codex 不一定看到 cross-cutting issue)

### 9. BWE 消息 = 触发器, 不是数据源

**❌ 我犯过的错**: 把 BWE 消息文本当 ground truth (parse magnitude, parse direction, 当成"该交易对的事实")。
**✅ 用户原话**: "我是想让你看到一条消息主要提取消息中的交易对，然后立马搜索这个交易对事实的数据是否符合要求，而不是让你通过 emoji 去过滤的"。
**规则**:
- BWE 消息只用来**指向**交易对 (extract symbol)
- 真实数据从 binance API / klines 拿 (price/funding/OI/orderbook/CVD)
- 任何依赖 message text content 的逻辑都是设计错误 (e.g., 用 emoji 分 pump/dump)

### 10. 跨函数依赖必须追踪

**❌ 我犯过的错**: `recent_events` window=60min, 但 `yao_min` 在 _evaluate_v4_entry 用 24h cutoff → BROAD/QUAL 系统性 0 fire。
**✅ 教训**: 函数独立看都对, 组合错。
**规则**:
- 加新 filter / 改数据结构时, 列出**所有调用方**, 验证它们的假设跟新设计一致
- 写注释说明依赖关系: `# Note: this assumes recent_events covers ≥X hours`
- 测试时跑端到端, 不只是 unit test

---

## 我犯过的具体错误清单 (反面教材)

按 session 时间顺序:

### 1. Round 5 v3: parser 漏 "上涨"
- bug: `events.py` 不识别中文 "上涨", 漏 47% pricechange-pump events
- 影响: v4 strategies 在 paper 永远不 fire
- 教训: 字符串匹配规则要看真实数据, 不能凭直觉假设

### 2. v3 grid math 爆炸 146M
- bug: 13 个新维度叠加 → 146,623,068 combinations, 远超 stage1_runner 的 4,323 设计容量
- 教训: 加维度前算总组合数 (Cartesian product), 超过几万就要 smart_sample

### 3. Stage 3 用 live DB, Stage 1/2 用 cache shim
- bug: 同一 spec 在两个 stage 数据视角不一致 → stage 3 出 0 winners
- 教训: 跨 pipeline stage 必须用同一 data view

### 4. 把妖币 = 小盘币
- bug: 推 vol_24h ∈ [5M, 50M] 作为妖币 filter, 数据上完全错
- 教训: 别用市值定义行为, 用历史 pump 频率 / lifecycle

### 5. 单 indicator 策略 (第一轮)
- bug: 给用户 20 个 entries / 20 个 exits 全是单条件 fade
- 教训: 多 indicator 组合, 每个 indicator 提供独立证据

### 6. 4 phases 实际只是参数搜索
- bug: 40 轮中 phase 2-4 大部分是 winner 参数 fine-tune, 不是新机制
- 教训: 每轮先问"这是新机制吗?", 否则跳过

### 7. Codex 找到 10 个 bugs (paper_shadow.py)
- bug: 24h vs 60min, legacy pnl wrong, off-by-one bar index, SL exit_price/pnl 不一致, partial JSON line skip, etc
- 教训: 写代码时手算一个 case, 不能"看起来对就 commit"

### 8. 修完之后引入 3 regressions
- bug: cursor advance 时机错, atomic close 不对, load_state 不 trim
- 教训: 修 bug 后必再做一轮 audit (用户明确要求)

### 9. state_repair.py race condition
- bug: tmp file 路径跟 runner 一样, 两者同时跑会 race
- 教训: 任何写 state 的 script 必须检测同进程是否运行 + 用唯一 tmp 后缀

---

## 工作流模板

### A. 新策略 brainstorm
1. 用户提需求 → 我**确认理解** (复述需求, 等用户确认)
2. 列 hypothesis: 这个机制为什么有 alpha (1 句话)
3. **跑数据验证 hypothesis** (不要直接列策略)
4. 数据成立 → 设计多 indicator filter 组合 (4-6 个)
5. 数据不成立 → 换 hypothesis, 不硬上

### B. Grid search (40 轮)
1. Phase 1-3: 10 真不同机制 / phase
2. 每轮: 跑数据 → 看是否 break baseline → 不破 streak += 1
3. Streak ≥ 10 → 反思 (写一段) + 换方向
4. Phase 4: 取前 5 名做参数 deep grid
5. 输出 4 个不同风险等级 winner (AGGRESSIVE / BALANCED / SAFE / SAFEST)

### C. 修 bug
1. 复现 bug (数据上 / 代码上)
2. 修复
3. 跑测试
4. **Codex audit round 1**
5. 自己 verify codex 每条
6. 修 round 1 issues
7. **Codex audit round 2** (查 regression)
8. 修 round 2 issues
9. Commit + 写反思 (为啥之前没发现)

### D. Paper-shadow / Live 上线前
1. 14 天 paper 验证
2. backtest sum vs paper sum 比对 — 偏差 > 50% 必须 audit
3. 风控 check: SL 距强平 ≥10%, 杠杆 ≤3x, 仓位 5-7.5%
4. 心理 check: 用户明确同意上 live

---

## Quick Reference (常用数据)

### V4 paper-shadow 参数 (commit dc2ea2c 后)
```
13 strategies (4 v2/v3 + 9 v4)
v4 entry: 3 distinct (BROAD / CHAMP / QUAL)
v4 exit: 3 distinct (AGG / SAFE / SAFEST)
heartbeat 30 min, OPEN 30s batched, CLOSE 仅 heartbeat
24h recent_events window + bootstrap on start
SL: ATR×10 (cap 30% on SAFE/SAFEST)
hold_min: 60
```

### Backtest 期望 (30 天)
```
v4 BROAD:  ~600 trades / 30d, mean +X%, win 68%
v4 CHAMP:  ~525 trades / 30d, mean +Y%, win 74% (sum +4177)
v4 QUAL:   ~414 trades / 30d, mean +Z%, win 77%
ST15_v2:   ~65 trades / 30d (经典 baseline)
```

### 关键路径
```
Live DB:        /Users/ye/.hermes/research/binance_futures_1m_collector_runtime/binance_futures_1m.sqlite3
Ext DB:         /Volumes/T9/binance data/historical/binance_extended_history.sqlite3
JSONL:          /Users/ye/.hermes/logs/bwe_matrix_posts.jsonl
Paper runtime:  /Volumes/T9/BWE/40_EXPERIMENTS/round5/paper_shadow/runtime/
Memory shared:  /Volumes/T9/BWE/.claude_memory_shared/
```

### 重要的 commit
```
dc2ea2c   fix: 10 codex audit + 3 self-review regressions
48f25e0   fix: parser captures 上涨 pricechange-pump events
638be85   feat: paper-shadow 13 strategies + batched tele
b0f08dd   archive: v4 exit + entry search results + v5 prompt
26159dd   feat: stage3_runner uses cache shim for filter consistency
ee50abc   fix: extend db_shim with v3 filter query patterns + BTCUSDT cache
```

### 重要的 spec / archive
```
specs/2026-04-30-v4-exit-search-archive.md   v4 exit 80 轮搜索结果
specs/2026-04-30-v4-entry-search-archive.md  v4 entry 40 轮搜索结果
specs/2026-05-01-v5-search-prompt.md         明天 v5 搜索 prompt
specs/2026-04-30-round6-architecture-audit.md Round 6 BWE 重构 spec
```

---

## 当 Claude 不知道怎么办时

1. **不确定的时候问用户**, 不要瞎推
2. **数据不支持的方向**, 直接说"数据上这个不成立, 我换方向"
3. **代码改大动作**, 每步骤说明你在做什么
4. **bug fix 后**, 调 codex audit, 不要假设 fix 完美
5. **paper / live 之前**, 必须用户明确确认杠杆 / 仓位 / SL

---

## 用户偏好 (Memory)

- 主力: Mac mini (5090 备用)
- 不喜欢 time-based exit 作为 primary
- 妖币 strategy: wide TP + dynamic exit + wider SL
- 实战 alpha > 字段优化
- 普适性 exit > 单币精调
- 偏好快增长但不爆仓 (推 2.5x × 7.5%, Half Kelly)
- 喜欢中文沟通, 但代码注释/git message 用中英混
- 不喜欢被打断思路, 出门前要"打通到完整可运行"
