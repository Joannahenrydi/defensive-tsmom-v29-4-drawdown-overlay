# v29.6 Concentration-Aware Long Risk Allocation

## Decision

**V29_6_REJECTED_KEEP_D1**

The frozen P3 alpha, v29.4 D1 drawdown controller and D1 re-entry logic were unchanged. This
train-only experiment changed only concentration allocation. Removed exposure stayed in cash;
the run added no shorts, replacement assets, crash rules or options. It read no development/OOS
data and did not authorize orders.

| Variant | Rule | CAGR | Sharpe | Max DD | Calmar | Worst month | Raw-P3 CAGR retention | Average exposure | Deepest DDs improved |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| C0 | Frozen D1 control | 8.93% | 0.626 | -23.49% | 0.380 | -13.83% | 94.98% | 75.84% | 0/5 |
| C1 | 40% economic-sleeve cap | 5.26% | 0.570 | -16.90% | 0.312 | -8.85% | 56.02% | 48.81% | 5/5 |
| C2 | 120-day causal correlation-cluster risk cap | 1.92% | 0.275 | -17.25% | 0.112 | -8.71% | 20.48% | 41.56% | 5/5 |

C1 and C2 both reduced maximum drawdown, improved the worst month and improved all five fixed D1
drawdown windows. Neither passed the frozen admission gate. C1 retained only 56.02% of raw P3
CAGR; C2 retained 20.48%. Their Calmar ratios fell below D1, and both materially underperformed
D1 in six non-2011 calendar years. The controls therefore removed profitable exposure too broadly
instead of selectively removing duplicate downside risk.

## Frozen gates

A candidate had to satisfy every condition:

- retain at least 90% of raw P3 CAGR;
- improve D1 maximum drawdown, Calmar and worst month;
- keep total cost and annual turnover within 110% of D1;
- improve at least three of D1's five deepest fixed drawdown windows;
- materially underperform D1 by more than two percentage points in no more than one non-2011 year.

C1 and C2 passed the drawdown, worst-month, cost, turnover and fixed-episode tests. They failed
CAGR retention, Calmar and cross-year robustness. No candidate was selected and no follow-on
parameter search was performed.

## Audit

C0 reproduced the committed D1 path with maximum daily-return error `1.93e-16` and maximum NAV
error below `1e-9`. Position reconstruction error was `4.44e-16`; gross and cost contribution
reconciliation errors were below `1.05e-16`. The final train observation was 2016-12-30.

The complete machine-readable output is in
[`reports/etf_concentration_control_v29_6/`](reports/etf_concentration_control_v29_6/), including
daily paths, annual returns, cap audits, fixed-episode comparisons, source hashes and all gate
results.
