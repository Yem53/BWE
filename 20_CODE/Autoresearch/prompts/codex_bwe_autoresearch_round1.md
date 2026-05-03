# Codex Prompt: BWE Three-Channel AutoResearch Round 1

You are running inside `/Users/ye/Desktop/GitHub/Autoresearch`.

Goal: improve the BWE three-channel sandbox AutoResearch workflow for strategy discovery and optimization.

Read first:
- `program_bwe_three_channel.md`
- `BWE_THREE_CHANNEL_AUTORESEARCH_FLOW.md`
- `configs/round1_open_discovery_search_space.yaml`
- `configs/metric_contract.json`
- `schemas/candidate_schema.json`
- `docs/experiment_guardrails.md`
- `bwe_autoresearch/discovery.py`
- `tests/test_bwe_autoresearch_discovery.py`

Historical data you may read:
- `/Users/ye/.hermes/research/bwe_three_channel_fullrun3/forward.parquet`
- `/Users/ye/.hermes/research/bwe_three_channel_fullrun3/event_hourly_2h_pre_48h_post.parquet`
- `/Users/ye/.hermes/research/bwe_next_optimization_20260424/`
- `/Users/ye/.hermes/research/bwe_live_exit_optimization_run5/`
- `/Users/ye/Desktop/Telegram/` exports if needed for parser validation.

Hard safety rules:
- Do not modify live configs, live autotrader code, launchd jobs, runtime state, or order scripts.
- Do not call live exchange order endpoints.
- Do not read, print, dump, or summarize secrets/tokens/API keys.
- Do not send messages or reports through Telegram.
- Write outputs only under this repository or `/Users/ye/.hermes/research/bwe_autoresearch_sandbox_*`.
- This is a research agent, not a trading agent.

What counts as success:
1. Keep tests passing:
   `/Users/ye/.hermes/runtime-venv/bin/python3 -m pytest tests/test_bwe_autoresearch_discovery.py -q`
2. Improve candidate generation or scoring while preserving the definition of new strategy.
3. Run a sandbox discovery output to `/Users/ye/.hermes/research/bwe_autoresearch_sandbox_20260424/codex_round1`.
4. Produce/update these artifacts:
   - `new_hypotheses.jsonl`
   - `new_entry_candidates.jsonl`
   - `new_exit_candidates.jsonl`
   - `discovery_scoreboard.csv`
   - `neighborhood_stability.csv`
   - `hypothesis_reject_log.csv`
   - `round1_discovery_report_zh.md`
5. Final answer must be concise Chinese with:
   - top promote_to_paper/watchlist candidates;
   - rejected reason categories;
   - next action;
   - confirmation that live was not touched.

Optimization target:
- high win rate + high median net first;
- high mean return as a bonus;
- punish p25/p10 left tail, drawdown, losing streak, symbol concentration, and top 1% outlier dependency.

Do not chase historical best mean return if stability fails.
