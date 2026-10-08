# v29.6 Concentration-Aware Long Risk Allocation

## Decision

**V29_6_REJECTED_KEEP_D1**

P3 alpha, D1 timing and D1 re-entry remained frozen. C1 capped economic-sleeve exposure at 40%;
C2 capped causal 120-session correlation-cluster risk at 35% of median-ETF volatility-equivalent
capital. Every removed dollar remained cash. No short, replacement asset, crash rule, options
hedge, development data or OOS data entered the run.

| variant | eligible | net_cagr | sharpe | maximum_drawdown | calmar | worst_month | raw_p3_cagr_retention | average_exposure | annual_total_turnover | total_cost | improved_deepest_drawdowns | materially_worse_non_2011_years |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | False | 0.0893 | 0.6264 | -0.2349 | 0.3799 | -0.1383 | 0.9498 | 0.7584 | 9.9899 | 14997.4382 | 0 | 0 |
| C1 | False | 0.0526 | 0.5705 | -0.1690 | 0.3116 | -0.0885 | 0.5602 | 0.4881 | 10.1238 | 12858.2724 | 5 | 6 |
| C2 | False | 0.0192 | 0.2746 | -0.1725 | 0.1116 | -0.0871 | 0.2048 | 0.4156 | 10.4140 | 10698.7606 | 5 | 6 |

Selected result: **keep v29.4 D1**. A candidate had to
retain at least 90% of raw P3 CAGR, improve D1 maximum drawdown, Calmar and worst month, remain
within cost/turnover limits, improve at least three of D1's five deepest windows and avoid broad
non-2011 deterioration.

C0 reproduced D1 with maximum daily return error
1.926e-16. The report directory contains daily
paths, annual returns, fixed-episode comparisons, sleeve/cluster cap audits and source hashes.
