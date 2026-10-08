# v30 D1 Hard Drawdown Stop

## Decision

**V30_REJECTED_KEEP_D1**

P3, the complete D1 controller and D1's 5%/10% re-entry eligibility remained frozen. Five
pre-registered stops observed immutable D1 drawdown and overrode D1 exposure only after a
one-session execution delay. No concentration control, development/OOS data or orders entered
the experiment.

| variant | stop_drawdown | eligible | net_cagr | sharpe | maximum_drawdown | calmar | worst_month | raw_p3_cagr_retention | average_exposure | annual_total_turnover | total_cost | improved_deepest_drawdowns | materially_worse_non_2011_years |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1_CONTROL |  | False | 0.0893 | 0.6264 | -0.2349 | 0.3799 | -0.1383 | 0.9498 | 0.7584 | 9.9899 | 14997.4382 | 0 | 0 |
| STOP_10 | -0.1000 | False | 0.0359 | 0.3249 | -0.2466 | 0.1454 | -0.1082 | 0.3816 | 0.6665 | 10.9888 | 13168.0026 | 2 | 3 |
| STOP_12_5 | -0.1250 | False | 0.0410 | 0.3538 | -0.2425 | 0.1690 | -0.1082 | 0.4362 | 0.7037 | 10.9655 | 13541.5706 | 1 | 4 |
| STOP_15 | -0.1500 | False | 0.0576 | 0.4604 | -0.2521 | 0.2286 | -0.1260 | 0.6133 | 0.7239 | 10.6791 | 14728.9967 | 1 | 2 |
| STOP_17_5 | -0.1750 | False | 0.0821 | 0.6090 | -0.2149 | 0.3823 | -0.1260 | 0.8739 | 0.7380 | 9.8983 | 14312.9119 | 1 | 0 |
| STOP_20 | -0.2000 | False | 0.0761 | 0.5603 | -0.2440 | 0.3117 | -0.1350 | 0.8094 | 0.7440 | 9.8760 | 13773.0916 | 1 | 0 |

Selected result: **keep v29.4 D1**. A candidate had to retain at least 90% of raw P3 CAGR, improve D1
maximum drawdown, Calmar and worst month, remain within cost/turnover limits, improve at least
three fixed drawdown windows and avoid broad non-2011 deterioration. Among fully eligible
candidates, the least severe maximum drawdown wins.

The control reproduced D1 with maximum daily return error
9.975e-17. The report directory contains
daily paths, stop decisions, execution events, annual returns, fixed-episode comparisons, all
gate results and source hashes.
