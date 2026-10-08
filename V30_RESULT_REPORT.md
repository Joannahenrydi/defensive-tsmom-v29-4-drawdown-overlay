# v30 D1 Hard Drawdown Stop

## Decision

**V30_REJECTED_KEEP_D1**

The P3 alpha engine, frozen v29.4 D1 controller and D1's 5%/10% trough-rebound re-entry
eligibility were unchanged. Five pre-registered stops observed immutable D1 portfolio drawdown.
A stop decision made at close t executed at close t+1, so no threshold was treated as a mechanical
maximum-drawdown bound. The hard-stop target could only reduce D1 exposure; residual capital
remained cash.

| Variant | Stop | CAGR | Sharpe | Max DD | Calmar | Worst month | Raw-P3 CAGR retention | Fixed DDs improved |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D1 control | — | 8.93% | 0.626 | -23.49% | 0.380 | -13.83% | 94.98% | 0/5 |
| STOP_10 | -10.0% | 3.59% | 0.325 | -24.66% | 0.145 | -10.82% | 38.16% | 2/5 |
| STOP_12_5 | -12.5% | 4.10% | 0.354 | -24.25% | 0.169 | -10.82% | 43.62% | 1/5 |
| STOP_15 | -15.0% | 5.76% | 0.460 | -25.21% | 0.229 | -12.60% | 61.33% | 1/5 |
| STOP_17_5 | -17.5% | 8.21% | 0.609 | -21.49% | 0.382 | -12.60% | 87.39% | 1/5 |
| STOP_20 | -20.0% | 7.61% | 0.560 | -24.40% | 0.312 | -13.50% | 80.94% | 1/5 |

No candidate passed every frozen gate. `STOP_17_5` was the closest: it improved maximum drawdown,
Calmar and worst month while satisfying cost, turnover and cross-year robustness limits. It still
failed two decisive requirements:

- CAGR was 8.21%, below the frozen 8.458% minimum and equivalent to only 87.39% of raw P3 CAGR.
- It improved only one of the five fixed D1 drawdown windows, below the required three.

The tighter stops also suffered severe missed-rebound damage. `STOP_10`, `STOP_12_5` and
`STOP_15` produced lower CAGR and in several cases worse maximum drawdown than D1. `STOP_20`
triggered too late to improve maximum drawdown and still reduced CAGR to 7.61%.

## Frozen gates

A candidate had to retain at least 90% of raw P3 CAGR, improve D1 maximum drawdown, Calmar and
worst month, remain within 110% of D1 cost and turnover, improve at least three of five fixed
drawdown windows, and materially underperform D1 by more than two percentage points in no more
than one non-2011 year. No post-run threshold or re-entry search was performed.

## Audit

`D1_CONTROL` reproduced committed D1 with maximum daily-return error `9.97e-17`, maximum NAV
error `2.91e-11` and zero multiplier error. The train ended on 2016-12-30; no development/OOS
data was read and orders remain disabled.

The complete machine-readable output is in
[`reports/d1_hard_drawdown_stop_v30/`](reports/d1_hard_drawdown_stop_v30/), including daily paths,
stop decisions, execution events, annual returns, fixed-episode comparisons, source hashes and
every gate result.
