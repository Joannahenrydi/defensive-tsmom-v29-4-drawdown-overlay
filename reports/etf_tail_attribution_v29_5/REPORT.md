# v29.5 D1 Tail-Loss Attribution

## Decision

**V29_5_TARGETED_PROTECTION_REJECTED_KEEP_D1**

The v29.3 P3 alpha engine and v29.4 D1 controller were held fixed. The five deepest D1
drawdowns, the worst month and every D1 state transition were decomposed into full-exposure loss,
avoided loss, missed rebound, execution-lag loss, costs, ETF and sleeve contributions. No
development/OOS data was read and orders remain disabled.

| window | d1_return | raw_p3_return | worst_day | worst_five_day | avoided_loss | missed_rebound | de_risk_lag_loss | top_negative_etf | top_negative_group | labels | primary_cause |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| drawdown_1 | -0.2349 | -0.2249 | -0.0574 | -0.1380 | 0.2356 | -0.2529 | -0.0308 | XLF | us_equity | sudden_crash;missed_rebound;concentration | missed_rebound |
| drawdown_2 | -0.1638 | -0.1638 | -0.0367 | -0.1030 | 0.0000 | 0.0000 | 0.0000 | XLI | us_equity | sudden_crash;concentration | sudden_crash |
| drawdown_3 | -0.1399 | -0.1399 | -0.0450 | -0.0826 | 0.0000 | 0.0000 | 0.0000 | XLF | us_equity | sudden_crash;concentration | sudden_crash |
| drawdown_4 | -0.0805 | -0.0805 | -0.0220 | -0.0441 | 0.0000 | 0.0000 | 0.0000 | FXI | international_equity | slow_drawdown;concentration | slow_drawdown |
| drawdown_5 | -0.0739 | -0.0739 | -0.0364 | -0.0434 | 0.0000 | 0.0000 | 0.0000 | EWU | international_equity | concentration | concentration |
| worst_month_2011-08 | -0.1383 | -0.0959 | -0.0574 | -0.1380 | 0.0624 | -0.1129 | -0.0088 | XLF | us_equity | sudden_crash;missed_rebound;concentration | missed_rebound |

Worst month: **2011-08**. Frozen primary cause:
**missed_rebound**.

## Conditional treatment

| candidate | passed | net_cagr | net_total_return | sharpe | sortino | maximum_drawdown | calmar | daily_profit_factor | average_exposure | time_multiplier_zero | worst_month | de_risk_events | re_entry_events | overlay_turnover | alpha_turnover | alpha_cost | overlay_cost | total_cost | cagr_retention | drawdown_improvement |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1_DIRECT_FULL_AT_5_PERCENT_REBOUND | False | 0.0773 | 0.9533 | 0.5425 | 0.7721 | -0.3605 | 0.2143 | 1.1112 | 0.7658 | 0.0071 | -0.1683 | 4 | 4 | 0.7744 | 9.3908 | 13276.2734 | 853.5509 | 14129.8242 | 0.8221 | -0.3578 |

The only permitted candidate depended on the frozen worst-month classification. A candidate had
to retain at least 90% of raw P3 CAGR, improve both D1 maximum drawdown and Calmar, lift worst
month above -10%, keep total cost within 10% of D1 and remain sparse. Failure keeps D1.

The report directory contains the daily reconciliation, episode and month attribution, every
state-transition audit, ETF/sleeve contribution tables, source hashes and any conditional
candidate path.
