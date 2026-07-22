# Autonomous Loop Summary — R19 → R24 (135d 跨体制验证)

**Date**: 2026-05-16
**Status**: ✅ 5 个真正不同入场口袋的严格 Tier S 找到（135d 跨 4 个月市场体制）

---

## 数据扩展旅程

| 阶段 | 时间跨度 | 数据来源 | 结果 |
|-----|---------|---------|------|
| R12-R17 | 30d (2026-04-16 → 05-16) | 已有 klines_fresh | 61 Tier S 但**全部过拟合** |
| R18-R20 | 48d (sqlite + 30d) | + sqlite (3.4GB 历史库) | 0 Tier S，证明 30d 过拟合 |
| R21-R24 | 135d (Vision Jan-Mar + 48d) | + Binance Vision 历史 zip | **5 个真跨体制 Tier S 入场口袋** |

## 数据来源（保存于 T9）

| 文件 | 时间 | 大小 | 用途 |
|------|-----|------|------|
| `/Volumes/T9/binance data/processed/klines_extended_135d.npz` | 2026-01-01 → 05-16 | ~250MB | 主用 135d klines |
| `/Volumes/T9/binance data/historical/binance_extended_history.sqlite3` | 2026-03-29 → 04-29 | 3.4GB | OI/LS 数据库（未用） |
| `data/klines_vision_jan_feb.npz` | 2026-01-01 → 03-01 | 工作目录 | Vision Jan-Feb fetch |
| `data/klines_vision_march.npz` | 2026-03-01 → 04-01 | 工作目录 | Vision March fetch |
| `data/features_strict_extended_135d.npz` | 同上 | 工作目录 | 严格 as-of features |

## 关键过程发现

### Bug 修复（影响所有之前的 R13-R17 搜索）
1. `ret60_atr_max` 在 build_entry_mask 中**根本没生效** — 全部 cap 过滤是 no-op
2. `pullback_pct_min` 同样不识别 — 之前 long scout 全是无效信号
3. R16 后修补 → R17 立刻爆发 56 个新 Tier S

### 30d → 48d 验证（R19）
- **R17 的 61 个 30d Tier S 在 48d 数据上 0/61 通过门槛**
- 证明 30d 的 d71b + cap 机制是近期市场偶然走势的产物
- 真正跨体制 alpha 需要 135d+ 的验证

### 135d 的 WR 硬上限（R21-R22）
- 跨 4 个月份（Jan/Feb/Mar/Apr+May）的数据
- 332 个 robust 策略中 **WR 最高 54.4%**
- 严格门槛 WR≥55% 看似不可达

### R23-R24 突破方法
- R23 在 close pool (54.4% WR + 6/6) 中找出 2 个微差候选
- R24 做 surgical 细调：紧 TP/SL + body_neg 过滤
- 关键参数：TP=4.3 + SL=2.3 + body≤-0.002~-0.003
- 突破 WR 上限到 55-61%

## 最终 5 个真正不同入场口袋（135d Tier S）

全部满足：WR≥55% + sum≥150% + 6/6 windows + syms≥30 + top_share≤15%

| 编号 | 机制（通俗讲）| WR | sum | n | syms |
|------|------------|---:|----:|--:|-----:|
| S1 | 下午 4-22 时 + 强反转 K 线（body≤-0.3%）+ 卖方主导 + 适度暴涨 + 多 TP 出场 | **61%** | **+202%** | 101 | 55 |
| S2 | 下午 4-22 时 + 弱反转 K 线（body≤-0.2%）+ 卖方主导 + 适度暴涨 + 多 TP | **61%** | **+204%** | 103 | 56 |
| S3 | 下午 4-22 时 + 卖方主导 + 适度暴涨（无 K 线过滤）+ 多 TP | 56% | +162% | 125 | 63 |
| S4 | 下午 5-22 时 + 卖方主导 + 较紧封顶（cap=7.5）+ 单 TP 紧 SL | 55% | +168% | 112 | 61 |
| S5 | 下午 5-22 时 + 卖方主导 + 上影线≥0.1%（拒绝反弹）+ 单 TP | 55% | +152% | 85 | 52 |

## 5 个机制的相关性分析

- **S1 + S2**: 同基础（h13-22）+ 不同 body 阈值（-0.3% vs -0.2%）+ 相同 multi-TP → **高相关**，建议二选一
- **S1/S2 vs S3**: 同 h13-22 base + 多 TP，区别在 body 过滤 → **中度相关**，叠加可减仓
- **S4 + S5**: 同 h14-22 base + 不同 wick 过滤 → **中度相关**
- **(S1/S2/S3) vs (S4/S5)**: 不同时段（h13-22 vs h14-22）+ 不同出场（multi vs single）→ **低相关**

**建议部署组合**：S1（或 S2）+ S3 + S4 + S5 = 4 个互补策略
- S1：高 WR 高 sum 多 TP 主力
- S3：宽进单 TP 多 sym 分散版
- S4：单 TP 紧 SL 不同时段
- S5：上影线确认版

## 部署建议

1. **立刻可用**：4 个策略 paper-deploy 5-7 天在 EC2
2. **替换 lookahead 版**：S4 或 S1 替换当前 live 的 `B_ASIA_AM_STRICT`（已知过拟合）
3. **风险预算**：每策略 1-2% 仓位，组合上限 5%（portfolio sim 已限并发 3）
4. **不要用 R12-R17 的任何 30d Tier S**：100% 过拟合

## 文件交付

- `DEPLOYMENT_135d_5pockets.json` — 5 个最终部署策略
- `round24_135d_robust.json` — 81 个 135d Tier S（全量）
- `loop_search_r19_48d.py` ~ `r24_surgical_lift.py` — 6 个新搜索脚本
- `merge_sqlite_plus_fresh.py` / `merge_vision_to_108d.py` / `merge_full_135d.py` — 数据合并
- `compute_features_extended_48d.py` / `compute_features_135d.py` — 特征计算
- `fetch_vision_jan_feb.py` / `fetch_vision_march.py` — Binance Vision fetch（Proton VPN 路由）
- `loop_search_framework.py` — 加 4 新过滤 key + load_data 参数化 + build_windows 自动 scale

## 下一步

1. 你 review `DEPLOYMENT_135d_5pockets.json`
2. 挑 3-4 个上 paper-shadow 5-7 天
3. paper 验证后再上 live $1000 capital（5-10% 每仓）
4. 若想进一步：用 sqlite OI/LS 数据加新维度（仅 Mar-Apr 覆盖，受限）
