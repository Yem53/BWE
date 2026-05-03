# Codex Task #2 — Generate ~20 Round 4 Wide-TP Exit Archetypes (X300+)

## Mission

Generate exactly **20 new exit archetype JSONL rows** for the BWE Autoresearch Round 4 GPU loop, covering the 妖币 regime's wide-TP / wide-SL / multi-stage exit space that Round 3 entirely missed.

These will be appended to `hypothesis_registry.jsonl` and consumed by the 5090 GPU loop's variant grid.

## Hard safety rules

- Read-only on existing files. Do not modify `hypothesis_registry.jsonl` directly.
- No exchange API calls. No secrets. Do not touch `/Users/ye/.hermes/`.
- Write output **only** to `/Volumes/T9/BWE/40_EXPERIMENTS/round4/01_archetypes/round4_exits.jsonl`.

## Required reads

1. **`/Volumes/T9/BWE/20_CODE/Autoresearch/bwe_autoresearch/bwe_loop_exit_kernels.py`** — the 4 GPU exit kernel implementations: `eval_time_only`, `eval_breakeven`, `eval_trailing_pct`, `eval_multi_tp_50_50`. **Each archetype's exit family MUST match one of these kernels OR the default fixed kernel.** If you propose an exit that none of these can evaluate, it's dead on arrival.
2. **`/Volumes/T9/BWE/20_CODE/Autoresearch/bwe_autoresearch/bwe_loop_exit_kernels.py:313-360`** — `classify_exit_family()` — the routing logic that maps archetype name → kernel.
3. **`/Volumes/T9/BWE/20_CODE/Autoresearch/prompts/TEAM_PHILOSOPHY.md`** — 妖币 Round 4 thesis.
4. **`/Volumes/T9/BWE/40_EXPERIMENTS/round4/00_planning/02_max_forward_return.md`** — D1 实证: 5h max=209%, p99=166%; supports TP grid up to 500%.
5. **`/Volumes/T9/BWE/40_EXPERIMENTS/hypothesis_registry.jsonl`** — existing 106 exits (X001-X106 already used; R3 19:49 generator proposed X107-X108 but those are still ≤2% TP and rejected by R4 — your X300+ replaces the missing wide-TP region).

## Round 3 lessons that MUST be encoded

1. **R3 keep 7 行全是 fixed exit, TP=0.20-0.51%, SL=4.40-6.00%** — paper-shadow 全部亏损。R4 的 wide-TP exit 必须填补这个区。
2. **Trail family eval_trailing_pct 用 `sl_pct` 作为 trail step**（`bwe_loop_exit_kernels.py:172-225`）。所以 trail family 的 sl 字段 = trail step。R4 wide trail 应当 trail_step ∈ {2, 4, 6}%。
3. **Multi_tp_50_50 kernel** 在 `eval_multi_tp_50_50` 里硬编码 50/50 比例（`bwe_loop_exit_kernels.py:231-310`）。如果想要 30/70 ladder，会被 fall through 不被评估——除非 archetype 名 + family 匹配现有 kernel。
4. **Breakeven kernel** 当 TP 触发后 SL 移到入场点；妖币 regime 大 TP grid 下应该重新好转（R3 X100 -0.08 floor 是 TP=0.20 太小的 artifact）。

## Exit family quota (HARD CONSTRAINT)

| family | count | classify_exit_family pattern (must satisfy) | TP × SL × hold geometry |
|---|---:|---|---|
| **fixed** | **8** | name does NOT contain `breakeven`, `composite_exit_be`, `time_only`, `trail`, `multi_tp` | TP ∈ {5, 10, 25, 40, 70, 120, 200, 350}, SL ∈ {3, 5, 7, 10}, hold {2h, 5h} |
| **trail** | **4** | name contains `trail` | trail_step (= sl_pct) ∈ {2, 4, 6}, hold {2h, 4h, 5h} |
| **breakeven (composite)** | **4** | name starts with `composite_exit_be` or contains `breakeven`, `_be_` | wide TP {15, 30, 50, 100} BE trigger, then ride to hold close, hold {3h, 5h} |
| **multi_tp** | **4** | name contains `multi_tp` | TP ladder 50/50; TP1 small (like 5%, 10%), TP2 wide (25%, 50%, 100%) |
| **TOTAL** | **20** | | |

(Exit kernels do not encode hold inside the archetype name — hold comes from variant grid; but archetype's `notes` should hint preferred hold range.)

## Naming convention

- Snake_case: `<family_prefix>_<geometry>` e.g. `fixed_tp25_sl5_wide`, `trail_4pct_step_5h`, `composite_exit_be_tp30_sl7`, `multi_tp_5_50_ladder`
- ID range: **X300 to X319** (20 sequential ids; X001-X108 already used in registry)
- Archetype family classification will be auto-derived by `classify_exit_family()` based on name — make sure your name matches the pattern in the table above.

## Design principles (HARD CONSTRAINTS)

1. **No TP < 3%** in fixed family. Round 3 demonstrated TP < 1% is a fee trap; spirit of R4 is wide TP.
2. **No SL < 2%** in any family. Spec from user: "SL 在 10 以内找到合适的参数" — search range 2-10%.
3. **Cover the geometry corners**: fixed family must include at least one (TP=350% or 500%), one (TP=10%, SL=10%), one balanced (TP=25%, SL=5%).
4. **multi_tp ladder design**: TP1 should be hittable (5-10%) so the ladder collects something even on average events; TP2 should be wide (25-100%) to capture right-tail.
5. **trail family**: trail_step (= sl in archetype) controls how loose the trail is. Wider step = let winners run more; narrower = tighter ratchet. Spec: 2/4/6%.

## Output schema (mandatory)

Each line is a single JSON object:

```json
{
  "id": "X300",
  "type": "exit",
  "archetype": "fixed_tp25_sl5_balanced",
  "channel": "NA",
  "side": "NA",
  "novel_dim": ["tp_pct=25", "sl_pct=5"],
  "expected_distinct": true,
  "notes": "Balanced wide-TP fixed exit (5x asymmetric). TP=25% 适配妖币 5h hold p75-p90 区间, SL=5% 适配妖币正常震荡。"
}
```

Field rules:
- `id`: exactly `X300` to `X319` (20 sequential ids)
- `type`: always `"exit"`
- `archetype`: snake_case, must classify into intended family via `classify_exit_family()` — verify yourself
- `channel`: always `"NA"` for exit (channel is paired entry's attribute)
- `side`: always `"NA"` for exit
- `novel_dim`: list of `tp_pct=N`, `sl_pct=N` strings (these are read by `bwe_loop_entry_filter.py` as exit kernel parameters per SUPPORTED_FIELDS section 4); for trail, only `sl_pct=N` (= trail step); for breakeven, both `tp_pct=N` (BE trigger) and `sl_pct=N` (initial SL pre-TP)
- `expected_distinct`: boolean (always true if your design is novel)
- `notes`: 1-2 sentence Chinese rationale referencing 妖币 regime + 5h hold

## Output file

Write to: `/Volumes/T9/BWE/40_EXPERIMENTS/round4/01_archetypes/round4_exits.jsonl`

40 → 20 lines, each one JSON object, UTF-8.

## Verification before exit

Run yourself:

1. `wc -l round4_exits.jsonl` outputs `20`
2. `python3 -c "import json; [json.loads(l) for l in open('round4_exits.jsonl')]; print('OK')"`
3. ID uniqueness X300-X319, no overlap with X001-X108 in existing registry
4. Family quota: 8 fixed + 4 trail + 4 breakeven + 4 multi_tp = 20
5. For each archetype, verify `classify_exit_family(name)` would return the intended family (run it via:
   ```python
   import sys; sys.path.insert(0, '/Volumes/T9/BWE/20_CODE/Autoresearch')
   from bwe_autoresearch.bwe_loop_exit_kernels import classify_exit_family
   for line in open('round4_exits.jsonl'):
       a = json.loads(line)
       print(a['id'], a['archetype'], '->', classify_exit_family(a['archetype']))
   ```
   Note: this needs torch import-able; if torch is missing, run the classification logic manually by reading the `if/elif` chain in `classify_exit_family`.
6. Every TP ≥ 3 in fixed family, every SL ≥ 2 in all families.

## Output format for your final response

Concise 中文, 5 sections:
- 完成情况：file written, 20 archetypes, schema valid
- Family 分布：8 fixed + 4 trail + 4 BE + 4 multi_tp ✓
- TP/SL 几何核对：fixed 上限 NN%, trail step 范围 NN%, ...
- 关键创新点：列出最 distinctive 的 5 个 archetype 名 + 思路
- 安全确认：未触动 ~/.hermes/, 未读 secrets, output only in T9 round4/
