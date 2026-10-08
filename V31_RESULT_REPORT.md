# v31 D1 Position-Level Loss Stop

## Decision

**V31_REJECTED_KEEP_D1**

Unlike v30, v31 never used portfolio drawdown. Each candidate independently monitored every
frozen P3 `trade_id` held by D1. When one trade breached its loss threshold at close t, only that
trade was liquidated at close t+1. Its proceeds remained cash and it stayed locked out until the
original P3 exit; all other P3/D1 exposures continued unchanged.

| Variant | Position stop | CAGR | Sharpe | Max DD | Calmar | Worst month | Raw-P3 CAGR retention | Stops | Fixed DDs improved |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D1 control | — | 8.93% | 0.626 | -23.49% | 0.380 | -13.83% | 94.98% | 0 | 0/5 |
| PSTOP_5 | -5.0% | 6.57% | 0.581 | -16.87% | 0.390 | -8.73% | 69.95% | 59 | 4/5 |
| PSTOP_7_5 | -7.5% | 7.66% | 0.607 | -20.30% | 0.377 | -11.12% | 81.50% | 34 | 4/5 |
| PSTOP_10 | -10.0% | 7.99% | 0.606 | -23.27% | 0.343 | -14.77% | 84.97% | 20 | 4/5 |
| PSTOP_12_5 | -12.5% | 8.57% | 0.623 | -21.10% | 0.406 | -12.35% | 91.23% | 9 | 4/5 |
| PSTOP_15 | -15.0% | 9.00% | 0.640 | -21.10% | 0.427 | -12.35% | 95.76% | 6 | 2/5 |

The position-level mechanism preserved substantially more return than v30's whole-portfolio
stops. It nevertheless produced no candidate satisfying every frozen gate.

`PSTOP_15` was strongest on aggregate performance. It exceeded D1 CAGR, Sharpe and Calmar while
reducing maximum drawdown and improving the worst month. It passed CAGR retention, cost,
turnover and cross-year robustness, but improved only two of the five fixed D1 drawdown windows;
the frozen gate required at least three.

`PSTOP_12_5` retained 8.57% CAGR and improved four fixed windows. It passed every other gate but
materially underperformed D1 by more than two percentage points in two non-2011 calendar years;
the frozen limit was one. No intermediate threshold or alternative re-entry rule was tested after
seeing these results.

## Execution and cost treatment

The reference price was each trade's actual adjusted-close P3 entry price. A trade could trigger
only while its original episode was active and D1 had positive exposure. The stopped trade earned
the return through its next-close liquidation, paid a 10bp exit cost at marked value, skipped its
later scheduled P3 exit cost and could return only under a new P3 `trade_id`.

The six `PSTOP_15` events involved XLF three times, plus FXI, DBC and EWZ; three were US equity,
two international equity and one commodity exposure. This is consistent
with v29.5's concentration attribution, but the fixed multi-episode gate still prevents admission.

## Audit

The evaluator reconstructed all 216 P3 trade episodes. Maximum reconciliation errors were
`1.82e-12` for gross P&L, `2.84e-14` for costs, `4.44e-16` for exposure and `5.68e-14` for entry
prices. `D1_CONTROL` reproduced D1 with daily-return error `1.92e-16`, NAV error below `1e-9` and
exposure error `4.44e-16`. The train ended on 2016-12-30; no development/OOS data was read and
orders remain disabled.

The complete output is in
[`reports/d1_position_loss_stop_v31/`](reports/d1_position_loss_stop_v31/), including every stop
event, daily paths, annual returns, fixed-episode comparisons, source hashes and gate results.
