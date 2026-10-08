# v31 D1 Position-Level Loss Stop

## Decision

**V31_REJECTED_KEEP_D1**

Each stop acted independently on one frozen P3 trade episode held by D1. A breach at close t
liquidated only that trade at close t+1 and locked it out until its original P3 exit; proceeds
remained cash. P3, D1 and every other position were unchanged. Portfolio drawdown was never an
input.

| variant | position_loss_stop | eligible | net_cagr | sharpe | maximum_drawdown | calmar | worst_month | raw_p3_cagr_retention | average_exposure | stop_event_count | annual_total_turnover | total_cost | improved_deepest_drawdowns | materially_worse_non_2011_years |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1_CONTROL |  | False | 0.0893 | 0.6264 | -0.2349 | 0.3799 | -0.1383 | 0.9498 | 0.7584 | 0 | 9.9899 | 14997.4382 | 0 | 0 |
| PSTOP_5 | -0.0500 | False | 0.0657 | 0.5811 | -0.1687 | 0.3897 | -0.0873 | 0.6995 | 0.6109 | 59 | 9.7583 | 14118.4612 | 4 | 3 |
| PSTOP_7_5 | -0.0750 | False | 0.0766 | 0.6071 | -0.2030 | 0.3774 | -0.1112 | 0.8150 | 0.6811 | 34 | 9.8522 | 14115.1422 | 4 | 3 |
| PSTOP_10 | -0.1000 | False | 0.0799 | 0.6055 | -0.2327 | 0.3431 | -0.1477 | 0.8497 | 0.7200 | 20 | 9.8464 | 14123.6690 | 4 | 3 |
| PSTOP_12_5 | -0.1250 | False | 0.0857 | 0.6227 | -0.2110 | 0.4064 | -0.1235 | 0.9123 | 0.7396 | 9 | 9.8479 | 14546.4925 | 4 | 2 |
| PSTOP_15 | -0.1500 | False | 0.0900 | 0.6397 | -0.2110 | 0.4266 | -0.1235 | 0.9576 | 0.7506 | 6 | 9.8513 | 14709.5972 | 2 | 1 |

Selected result: **keep v29.4 D1**. A candidate had to retain at least 90% of raw P3 CAGR, improve D1
maximum drawdown, Calmar and worst month, stay within cost/turnover limits, improve at least three
fixed drawdown windows and avoid broad non-2011 deterioration. Among fully eligible candidates,
the least severe maximum drawdown wins.

The control reproduced D1 with maximum daily return error
1.917e-16. The output includes every causal
stop event, daily path, annual result, fixed-episode comparison, source hash and gate result.
