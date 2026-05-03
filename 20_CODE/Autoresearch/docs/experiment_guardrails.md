# BWE AutoResearch Experiment Guardrails

## Hard boundary

This repository is used as a BWE strategy research sandbox. It is not a live trading system.

Allowed:
- Read historical BWE research artifacts under `/Users/ye/.hermes/research/`.
- Read three-channel Telegram Desktop exports under `/Users/ye/Desktop/Telegram/` when needed.
- Read existing markdown/config/code in `/Users/ye/Desktop/GitHub/Autoresearch`.
- Write generated candidates, configs, scoreboards, reject logs, tests, and reports under:
  - `/Users/ye/Desktop/GitHub/Autoresearch`
  - `/Users/ye/.hermes/research/bwe_autoresearch_sandbox_*`

Forbidden:
- Do not place orders.
- Do not call exchange order endpoints.
- Do not modify live autotrader config or code.
- Do not restart launchd jobs or live trading processes.
- Do not read, dump, print, or summarize API keys/tokens/secrets.
- Do not promote any candidate to live automatically.
- Do not send Telegram reports unless explicitly requested.

## Definition of new strategy

A result is not a new strategy if it only changes a threshold, entry delay, holding horizon, or TP/SL number inside an existing family.

A result may be considered a new strategy only if it has at least one of:
- a new explainable alpha source;
- a materially different entry rule;
- a materially different exit/risk mechanism that changes the return distribution;
- a cross-channel interaction not present in the baseline;
- a state-machine / burst / regime behavior that is not just a scalar threshold.

## Stop condition

Do not search indefinitely for high historical win rate / return. Stop a direction when:
- the round budget is exhausted;
- at least 3 candidates reach `promote_to_paper`;
- 3 consecutive rounds fail to improve the current champion;
- improvements are driven by small samples, one symbol, or top 1% winners;
- fee/slippage and outlier stress invalidate the direction.

## Promotion ladder

1. `reject`: fails median, left-tail, or sanity gates.
2. `need_more_data`: sample/symbol count insufficient.
3. `watchlist`: promising but not champion-grade.
4. `promote_to_paper`: historical candidate worthy of paper shadow only.
5. Live review: only after 20+ clean complete paper/live-aligned trades per active strategy and manual review.

## Reporting

Reports should be Chinese, concise, action-first:
- top candidates;
- why they might work;
- why rejected candidates failed;
- whether result is paper-ready or only watchlist;
- no secrets, no raw tokens, no live order data dumps.
