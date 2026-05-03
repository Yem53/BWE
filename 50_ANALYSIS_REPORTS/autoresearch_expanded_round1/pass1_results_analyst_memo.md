# Results Analyst Round 1 Memo

## Evidence Summary
- Best sample>15 strategy median: `23.294341564178467` with p10 `14.810827374458311`.
- Best stability strategy: `v6_28d858af6439dc2b01` with stability score `0.8921219250000001`.
- Discovery rows: `80`.
- Hypotheses logged: `80`.

## Interpretation
The alpha signal should be reported by tier. Smaller samples above 15 are not rejected; they are kept as early-alpha evidence with explicit confidence labeling.

## Tier Interpretation
- Early-alpha count: `19569`.
- Exploratory watchlist count: `28228`.
- Validated watchlist count: `22023`.
- Higher-confidence watchlist count: `130180`.

## Reporting Standard
Every headline strategy should be reported as raw rank, stability rank, sample tier, stressed median, p10, future-safety status, and baseline lift. A result missing any of those fields remains a research lead rather than a paper-shadow candidate.
