---
name: Max out all Claude calls in BWE Autoresearch
description: User has plenty Max-plan quota, wants every Claude subprocess call to use highest-effort/deepest-thinking config
type: feedback
originSessionId: 9aa9a58b-6062-4d43-83be-5004328027b2
---
For all `claude -p` subprocess calls in BWE Autoresearch (especially `bwe_loop_llm_team.py`), enable maximum-quality config:

- `--model claude-opus-4-7` (already default — gives 1M context, 64K output)
- `--effort max` (highest extended-thinking budget)
- `--exclude-dynamic-system-prompt-sections` (better cross-call cache reuse, lowers cost without hurting quality)

**Why:** User has Max $200/mo plan with plenty of headroom; their Round 3 deep debate (~110 calls) cost ~$11-13 of API-equivalent burn, leaving lots of slack. They explicitly said "下一轮启用，所有 Claude 调用的参数拉满，我的额度够用" on 2026-04-27.

**How to apply:**
- Always include `--effort max` for any role/critic call in this project
- Don't downgrade for "speed" reasons — slower deeper thinking is what they want
- If a single call's elapsed time spikes 3-5×, that's expected with `--effort max` and acceptable
- Round 3 (in flight at the moment this memory was saved) does NOT have `--effort max` — it's intentional to not interrupt the running debate. Round 4+ should always have it on.
