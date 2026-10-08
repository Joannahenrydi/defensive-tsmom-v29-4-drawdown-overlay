# v32 Hybrid Static + Dynamic Position Loss Stop

## Decision

**V32_REJECTED_KEEP_D1**

v32 tested exactly one pre-registered hybrid position stop. It used 20-session annualized realized
volatility known at each P3 trade entry, calibrated one multiplier across all 216 frozen entry
episodes, and froze the resulting threshold for the entire trade:

\[
k=\frac{13.75\%}{\operatorname{median}(\sigma_{20d,entry})}=0.756573
\]

\[
L_i=\operatorname{clip}(k\sigma_{i,entry},12.5\%,15.0\%)
\]

No alternative multiplier, volatility window, rail or re-entry rule was tested. P3, D1 and
concentration allocation remained unchanged.

## Results

| Variant | CAGR | Sharpe | Max DD | Calmar | Worst month | Raw-P3 CAGR retention | Stops | Fixed DDs improved | Non-2011 years >2pp worse |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v29.4 D1 control | 8.93% | 0.626 | -23.49% | 0.380 | -13.83% | 94.98% | 0 | 0/5 | 0 |
| v32 hybrid | 8.98% | 0.641 | -21.10% | 0.425 | -12.35% | 95.52% | 7 | 2/5 | 1 |

The hybrid improved aggregate performance: CAGR rose by 0.05 percentage points, Sharpe rose from
0.626 to 0.641, maximum drawdown improved by 2.40 percentage points and the worst month improved
by 1.48 percentage points. Turnover and cost also remained inside their limits. The candidate
passed seven of eight frozen admission checks.

It failed the fixed-episode rule. Only the first two of D1's five deepest fixed drawdown windows
improved; the gate required at least three. Episode 4 was marginally worse by 0.017 percentage
points, while episodes 3 and 5 were unchanged. The result therefore cannot replace D1 despite its
strong aggregate metrics.

## Threshold calibration

The median 20-session annualized entry volatility was 18.1740%, so the unique calibrated
multiplier was 0.756573. The entry-frozen thresholds were distributed as follows:

- 93 trades at the 12.5% floor;
- 35 trades inside the dynamic range;
- 88 trades at the 15.0% ceiling.

Seven trade episodes triggered. They were FXI, XLF three times across separate episodes, DBC, EWZ
and XLB. The close-t decision and close-t+1 liquidation convention was preserved. Each stopped
trade paid the 10bp exit cost, skipped its later scheduled exit cost and stayed locked out until
its original P3 episode ended. Proceeds remained cash and all other positions stayed unchanged.

## Frozen gate result

| Gate | Result |
|---|---|
| CAGR ≥ 8.458% | PASS |
| Max DD better than D1 | PASS |
| Calmar > D1 | PASS |
| Worst month better than D1 | PASS |
| Cost ≤ 110% of D1 | PASS |
| Turnover ≤ 110% of D1 | PASS |
| At least 3/5 fixed D1 drawdowns improve | **FAIL — 2/5** |
| At most one non-2011 year trails D1 by >2pp | PASS — 1 year |

Following the pre-registered stopping rule, position-stop optimization ends here. The retained
strategy remains **v29.4 D1**.

## Audit

The evaluator covered all 216 P3 trade episodes and all 45 frozen ETFs. Maximum reconstruction
errors were `1.82e-12` for gross P&L, `2.84e-14` for costs, `4.44e-16` for exposure and `5.68e-14`
for entry prices. `D1_CONTROL` reproduced D1 with daily-return error `1.92e-16`, NAV error below
`1e-9` and exposure error `4.44e-16`.

The train ended on 2016-12-30. Development/OOS data were not read, orders remain disabled, and
the result is not risk-admitted.

The full machine-readable output is in
[`reports/d1_hybrid_position_stop_v32/`](reports/d1_hybrid_position_stop_v32/). The full chart set
and combined PDF are linked from [`V32_RESULT_FIGURES.md`](V32_RESULT_FIGURES.md).
