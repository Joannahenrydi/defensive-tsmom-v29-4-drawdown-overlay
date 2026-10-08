# v29.4 Long-Only ETF Drawdown Overlay

## Decision

**V29_4_TRAIN_DD_PASS_PROSPECTIVE_REQUIRED**

The frozen v29.3 P3 train return stream was left unchanged. D0–D3 changed only the long-exposure
multiplier and residual cash. Every state decision used the shadow P3 close and was executed one
session later; the resulting exposure first earned the following close-to-close return. The run
read no development/OOS data and did not authorize orders.

| variant | eligible | net_cagr | sharpe | maximum_drawdown | calmar | cagr_retention | drawdown_improvement | average_exposure | time_multiplier_zero | worst_month | de_risk_events | re_entry_events | total_cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D0 | False | 0.0940 | 0.6325 | -0.2655 | 0.3539 | 1.0000 | -0.0000 | 0.7724 | 0.0000 | -0.1028 | 0 | 0 | 14891.9815 |
| D1 | True | 0.0893 | 0.6264 | -0.2349 | 0.3799 | 0.9498 | 0.1152 | 0.7584 | 0.0115 | -0.1383 | 6 | 7 | 14997.4382 |
| D2 | False | 0.0701 | 0.5345 | -0.2175 | 0.3225 | 0.7461 | 0.1811 | 0.7440 | 0.0004 | -0.0994 | 33 | 33 | 14873.1832 |
| D3 | False | 0.0485 | 0.4470 | -0.1872 | 0.2590 | 0.5159 | 0.2950 | 0.6405 | 0.0004 | -0.0748 | 902 | 954 | 16578.1600 |

Selected result: **D1**. Eligibility required at least 80% of raw P3 CAGR, a strict maximum
drawdown improvement and a Calmar ratio above raw P3. D0 is an implementation control and cannot
win. If the decision keeps raw P3, none of the preregistered overlays cleared all three gates.

Raw P3 benchmark: CAGR 9.3978%, maximum drawdown
-26.5541%, Calmar 0.3539.

The output directory also contains daily multiplier/exposure histories, decision and execution
events, annual results, the five deepest drawdown episodes, source verification and run audits.
Daily profit factor is reported as a portfolio-return diagnostic; it is not the v29.3 trade-ledger
profit factor and is not an admission gate.
