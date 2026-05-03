# Codex Task #1 — Generate ~40 Round 4 Entry Archetypes (Manipulator Detection)

## Mission

Generate exactly **40 new entry archetype JSONL rows** for the BWE Autoresearch Round 4 GPU loop. The user trades small-cap manipulator-driven coins ("妖币"), so each archetype must encode a "庄家控盘特征" detection logic, NOT generic price-momentum.

These will be appended to `hypothesis_registry.jsonl` and consumed by the 5090 GPU loop's variant grid.

## Hard safety rules

- Read-only on existing files. **Do not modify** `hypothesis_registry.jsonl` directly — write to a new file.
- Do not call any exchange API.
- Do not read or print secrets / API keys / .env.
- Do not touch `/Users/ye/.hermes/` (live trading bot — out of scope).
- Write output **only** to `/Volumes/T9/BWE/40_EXPERIMENTS/round4/01_archetypes/round4_entries.jsonl`.

## Required reads (mandatory)

1. **`/Volumes/T9/BWE/20_CODE/Autoresearch/prompts/SUPPORTED_FIELDS.md`** — single source of truth for novel_dim conditions. **Any field NOT listed here will silently fall-through and ruin the archetype.** All sections 1.A through 2 are valid; sections 3 onward are forbidden.
2. **`/Volumes/T9/BWE/20_CODE/Autoresearch/prompts/TEAM_PHILOSOPHY.md`** — 妖币 Round 4 thesis (TP up to 500%, SL ≤ 10%, 庄家识别 core).
3. **`/Volumes/T9/BWE/40_EXPERIMENTS/round4/00_planning/00_overview.md`** — Round 4 master overview, especially section 4 (channel quotas) and section 11 (output spec).
4. **`/Volumes/T9/BWE/40_EXPERIMENTS/hypothesis_registry.jsonl`** — existing 543 archetypes; new ones must be distinct.

## Round 3 lessons that MUST be encoded

1. **`price_5m_neg`, `price_5m_pos`, `pretrend_5m_pos`, `burst_count_5m>=N`** are NOT in SUPPORTED_FIELDS — they fall through. **Forbidden.** Many Round 3 archetypes used these and silently turned into channel-baseline (= n=5000 trigger saturation).
2. **Funding extreme + low_liq + small_mc 三连 AND** triggered 9% crash in Round 3. Avoid 3+ AND combinations; max 2 AND.
3. Round 3 surfaced 7 keeps all in `pricechange/long` with TP 0.20-0.51% — wrong-regime. R4 must redistribute toward OI (40%) and R6 (30%).

## Channel quota (HARD CONSTRAINT)

| channel | side preference | count | Round 3 issue → R4 fix |
|---|---|---|---|
| `BWE_OI_Price_monitor` | mostly long (庄家加仓) + some short | **16** | R3: 0 keep here. R4 main battleground. OI rising + smallcap + low_liq = 庄家加仓 telegraph |
| `BWE_Reserved6` | both | **12** | R3: -0.17 mean baseline. R4: extremely loose filter (max 1 condition) since events are sparse (332 in 30d) |
| `BWE_pricechange_monitor` | both | **10** | R3: dominated keeps but all wrong-regime. R4: ONLY include if novel_dim has explicit manipulator filter; pure pricechange baseline is forbidden |
| `*` (cross-channel) | both | **2** | R3: all 5000-saturated. R4: tight 60s window OI+PC double-fire only |
| **TOTAL** | | **40** | |

## Design principles (HARD CONSTRAINTS)

### Novel_dim composition (D2 user request)

- **Hard cap**: ≤ 2 AND conditions per archetype
- **30-40% (≈12-16 archetypes)**: single-dimension strong signal
- **40-50% (≈16-20 archetypes)**: two-dimension OR-style (one of two conditions)
   - Encode OR by creating TWO sibling archetypes with one condition each, NOT a single archetype with both — this gives the GPU loop room to pick the better half independently
- **≤ 20% (≈8 archetypes)**: two-dimension AND
- **0%**: three-dimension AND (forbidden)

### Manipulator detection signal vocabulary (use SUPPORTED_FIELDS only)

| Manipulator behavior | SUPPORTED_FIELDS encoding |
|---|---|
| 加仓拉升 (OI rising + price rising) | `oi_change_pct>=8` AND `event_type=pump` (when channel=OI_Price) |
| Smallcap pump | `marketcap_bucket=small` |
| Low-liquidity pump (easy to manipulate) | `liquidity_bucket=low` |
| Aggressive taker buying | `taker_buy_ratio_5m>=0.65` (mid) or `>=0.75` (extreme) |
| Smart-money positioning | `top_trader_position_ratio_high` (flag, p75) or `_low` |
| Retail trapped on wrong side | `global_long_ratio_extreme` (p90) or `global_short_ratio_extreme` |
| Volume burst (24h) | `volume_pct_top_decile` (flag, p90) or `volume_pct_above_p75` |
| Newly listed | `listing_age_days<=30` |
| Premium dislocation | `premium_bps>=20` (perp ≥ 0.20% above index) |
| OI unwind = shorts capitulate | `oi_change_pct<=-8` AND `event_type=pump` |
| US session liquidity regime | `session=US` |
| Funding extreme (positive = pile-on long) | `funding>=0.05pct` |
| Funding extreme (negative = piled short) | `funding<=-0.05pct` |

### Direction logic for OI_Price channel

- OI rising + price rising + smallcap = 庄家加仓 → **long continuation** (NOT short reversal — Round 3's pricechange/short bias was misapplied here)
- OI rising + funding extreme positive = late longs trapped → **short reversal**
- OI dropping + price rising = shorts capitulate → **long squeeze**
- OI dropping + price falling = liquidation cascade → **short continuation**

Round 4 must give the long side at least 50% of OI archetype budget (R3 was almost entirely short for OI).

### Naming convention

- Snake_case: `<channel_prefix>_<signal>_<side>` e.g. `oi_pump_smallcap_long`, `r6_extreme_long`, `pc_taker_buy_smallcap_long`, `cc_oi_pc_60s_double_long`
- Channel prefixes: `oi_*`, `r6_*`, `pc_*`, `cc_*`
- ID range: **E300 to E339** (E001-E213 already used; E300+ reserves clear separation from R3 19:49 generator's E202-E213)

## Output schema (mandatory)

Each line is a single JSON object with this exact structure:

```json
{
  "id": "E300",
  "type": "entry",
  "archetype": "oi_pump_smallcap_long",
  "channel": "OI_Price",
  "side": "long",
  "novel_dim": ["oi_change_pct>=8", "marketcap_bucket=small"],
  "expected_distinct": true,
  "notes": "庄家在小盘币加仓拉升 — OI 上涨叠加小市值容易被控盘。Round 4 主线方向。"
}
```

Field rules:
- `id`: exactly `E300` through `E339` (40 sequential ids)
- `type`: always `"entry"`
- `archetype`: snake_case, must be unique across all 40 + existing 213 entries
- `channel`: one of `"OI_Price"`, `"Reserved6"`, `"pricechange"`, `"*"` (literal strings, matches existing registry style — note: `OI_Price` not `BWE_OI_Price_monitor` for the channel field)
- `side`: `"long"` | `"short"` | `"both"`
- `novel_dim`: list of 1-2 strings, each must be a valid SUPPORTED_FIELDS condition
- `expected_distinct`: boolean
- `notes`: 1-2 sentence Chinese rationale, must reference the 庄家 detection thesis

## Output file

Write to: `/Volumes/T9/BWE/40_EXPERIMENTS/round4/01_archetypes/round4_entries.jsonl`

Format: 40 lines, each one JSON object, no header, no trailing newline issues. UTF-8.

## Verification before exit

Run these checks yourself and report results:

1. Line count: `wc -l round4_entries.jsonl` should output exactly `40`
2. Each line is valid JSON: `python3 -c "import json; [json.loads(l) for l in open('round4_entries.jsonl')]; print('OK')"`
3. ID uniqueness within file + no overlap with E001-E213 in existing registry
4. Channel quota: 16 OI_Price + 12 Reserved6 + 10 pricechange + 2 cross-channel = 40
5. Novel_dim each ≤ 2 conditions
6. Every condition in novel_dim appears in SUPPORTED_FIELDS sections 1 or 2 (grep check)
7. No duplicates of existing archetype names (case-insensitive grep against hypothesis_registry.jsonl `archetype` field)

## Output format for your final response

Concise 中文, 5 sections:
- 完成情况：file written, 40 archetypes, schema valid
- Channel 分布：16 OI / 12 R6 / 10 PC / 2 CC = 40 ✓
- 设计原则核对：(单维度 N) (双维度 OR N) (双维度 AND N)
- 关键创新点：列出最 distinctive 的 5 个 archetype 名 + 思路
- 安全确认：未触动 ~/.hermes/, 未读 secrets, output only in T9 round4/
