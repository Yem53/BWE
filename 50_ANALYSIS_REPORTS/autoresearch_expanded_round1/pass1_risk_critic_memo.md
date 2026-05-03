# Risk Critic Round 1 Memo

## Risk View
The run includes execution-cost stress, future-safety checks, cluster similarity, and baseline comparison. The remaining risk is over-selecting narrow clusters or small-sample leaders.

## Required Controls
- Any paper candidate must pass future-safety checks.
- Any paper candidate must retain positive stressed median under fee/slippage/latency.
- Small-sample candidates can be studied, but they need confidence-tier labels and shadow sizing.
- Cluster concentration should be penalized before any forward path.

## Failure Modes To Watch
- Exit family overfitting: a strong exit may be harvesting one path shape rather than reusable behavior.
- Timing leakage by proxy: delayed entries must keep future-safety checks visible.
- Symbol/day concentration: top-symbol share can make a strategy look stable when it is not.
- Cost cliff: candidates near zero stressed median should be demoted even if raw median is attractive.

## Risk Decision
No direct escalation. The correct risk posture is controlled paper-sandbox ablation after component isolation and neighborhood confirmation.
