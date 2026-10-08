# v32 Hybrid Static + Dynamic Position Loss Stop

## Decision

**V32_REJECTED_KEEP_D1**

The experiment calibrated exactly one multiplier from all frozen P3 entry episodes:
`k = 13.75% / median(entry 20d annualized volatility)`. Each trade's threshold was then frozen
at entry and clipped to 12.5%-15.0%. No alternative k or rail was tested.

| variant | eligible | net_cagr | sharpe | maximum_drawdown | calmar | worst_month | raw_p3_cagr_retention | average_exposure | stop_event_count | annual_total_turnover | total_cost | improved_deepest_drawdowns | materially_worse_non_2011_years |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1_CONTROL | False | 0.0893 | 0.6264 | -0.2349 | 0.3799 | -0.1383 | 0.9498 | 0.7584 | 0 | 9.9899 | 14997.4382 | 0 | 0 |
| HYBRID_20D_ENTRY_VOL | False | 0.0898 | 0.6406 | -0.2110 | 0.4255 | -0.1235 | 0.9552 | 0.7485 | 7 | 9.8507 | 14641.1204 | 2 | 1 |

Median entry volatility was **18.1740%**, producing
**k = 0.756573**. The 216 thresholds contained
93 floor, 35 interior and
88 ceiling observations.

Selected result: **keep v29.4 D1**. The hybrid candidate had to pass every frozen v31 gate. The
control reproduced D1 with maximum daily return error
1.917e-16. Development/OOS data were not read.
