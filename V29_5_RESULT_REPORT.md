# v29.5 D1 Tail-Loss Attribution

## Decision

**V29_5_TARGETED_PROTECTION_REJECTED_KEEP_D1**

The P3 alpha stream and v29.4 D1 controller were held fixed. The five deepest D1 drawdowns, the
worst month and every D1 state transition were decomposed into full-exposure loss, avoided loss,
missed rebound, execution-lag loss, costs, ETF and sleeve contributions. No development/OOS data
was read and orders remain disabled.

| window | d1_return | raw_p3_return | worst_day | worst_five_day | avoided_loss | missed_rebound | de_risk_lag_loss | top_negative_etf | top_negative_group | labels | primary_cause |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| drawdown_1 | -0.2349 | -0.2249 | -0.0574 | -0.1380 | 0.2356 | -0.2529 | -0.0308 | XLF | us_equity | sudden_crash;missed_rebound;concentration | missed_rebound |
| drawdown_2 | -0.1638 | -0.1638 | -0.0367 | -0.1030 | 0.0000 | 0.0000 | 0.0000 | XLI | us_equity | sudden_crash;concentration | sudden_crash |
| drawdown_3 | -0.1399 | -0.1399 | -0.0450 | -0.0826 | 0.0000 | 0.0000 | 0.0000 | XLF | us_equity | sudden_crash;concentration | sudden_crash |
| drawdown_4 | -0.0805 | -0.0805 | -0.0220 | -0.0441 | 0.0000 | 0.0000 | 0.0000 | FXI | international_equity | slow_drawdown;concentration | slow_drawdown |
| drawdown_5 | -0.0739 | -0.0739 | -0.0364 | -0.0434 | 0.0000 | 0.0000 | 0.0000 | EWU | international_equity | concentration | concentration |
| worst_month_2011-08 | -0.1383 | -0.0959 | -0.0574 | -0.1380 | 0.0624 | -0.1129 | -0.0088 | XLF | us_equity | sudden_crash;missed_rebound;concentration | missed_rebound |

Worst month: **2011-08**. Frozen primary cause: **missed_rebound**.

## Conditional treatment

| candidate | passed | net_cagr | sharpe | maximum_drawdown | calmar | worst_month | de_risk_events | total_cost | cagr_retention |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1_DIRECT_FULL_AT_5_PERCENT_REBOUND | False | 0.0773 | 0.5425 | -0.3605 | 0.2143 | -0.1683 | 4 | 14129.8242 | 0.8221 |

The only permitted treatment failed the frozen gate: it retained less than 90% of raw P3 CAGR,
worsened maximum drawdown and Calmar, and pushed the worst month further below -10%. The decision
therefore keeps v29.4 D1 and performs no further parameter search.

The full output directory contains daily reconciliation, event attribution, ETF/sleeve
contributions, source hashes and the rejected candidate path:
[`reports/etf_tail_attribution_v29_5/`](reports/etf_tail_attribution_v29_5/).
