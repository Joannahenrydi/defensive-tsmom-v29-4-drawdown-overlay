# ETF Drawdown Research — v29.4 to v32

## Result reports

- [v29.4 result report](V29_4_RESULT_REPORT.md)
- [v29.5 result report](V29_5_RESULT_REPORT.md)
- [v29.6 result report](V29_6_RESULT_REPORT.md)
- [v30 result report](V30_RESULT_REPORT.md)
- [v31 result report](V31_RESULT_REPORT.md)
- [v29.4 D1 versus v31 result figures](V31_RESULT_FIGURES.md)
- [v32 result report](V32_RESULT_REPORT.md)
- [v32 required result figures](V32_RESULT_FIGURES.md)

This private repository contains only the six frozen research stages requested for the long-only
ETF strategy:

- **v29.4** applies causal drawdown-driven exposure scaling to the frozen P3 long-and-cash return
  stream. D1 is the train winner.
- **v29.5** attributes D1's remaining left tail by episode, month, event, ETF and economic sleeve.
  Its single permitted re-entry treatment fails admission, so the final decision keeps D1.
- **v29.6** holds P3 and D1 fixed while testing a 40% sleeve cap and a causal 120-session
  correlation-cluster risk cap. Both reduce the measured left tail but sacrifice too much return,
  so the final decision again keeps D1.
- **v30** tests five pre-registered, causal D1 portfolio-drawdown stops while preserving the
  original D1 re-entry eligibility. No candidate passes every frozen gate, so D1 remains selected.
- **v31** replaces the portfolio stop with independent trade-episode loss stops. The -15% stop
  improves return and tail metrics but misses the frozen fixed-episode gate, so D1 remains selected.
- **v32** replaces v31's fixed threshold with one entry-volatility-calibrated threshold clipped to
  12.5%-15.0%. It improves aggregate return and tail metrics but still improves only two of five
  fixed drawdown windows, so the frozen decision again keeps D1.

The repository does not contain earlier strategy implementations. `inputs/frozen_p3/` holds only
the immutable P3 decision, daily return stream and trade-ledger evidence needed to reproduce
v29.4–v32. `inputs/frozen_market/` supplies the locked 45-ETF adjusted-close history needed for
v29.6's causal correlation clusters and v31/v32's trade-entry loss measurement.

## Results

| Stage | Decision | Selected result |
|---|---|---|
| v29.4 | `V29_4_TRAIN_DD_PASS_PROSPECTIVE_REQUIRED` | D1 |
| v29.5 | `V29_5_TARGETED_PROTECTION_REJECTED_KEEP_D1` | Keep D1 |
| v29.6 | `V29_6_REJECTED_KEEP_D1` | Keep D1 |
| v30 | `V30_REJECTED_KEEP_D1` | Keep D1 |
| v31 | `V31_REJECTED_KEEP_D1` | Keep D1 |
| v32 | `V32_REJECTED_KEEP_D1` | Keep D1 |

Raw P3 had 9.40% CAGR and -26.55% maximum drawdown. D1 retained 8.93% CAGR and reduced maximum
drawdown to -23.49%. v29.5 identified August 2011 as the -13.83% worst month: the controller
avoided 6.24% of negative-return exposure but missed 11.29% of positive-return exposure. XLF
supplied 58.62% of negative contribution and the US-equity sleeve supplied 86.59%.

In v29.6, the 40% sleeve cap improved all five fixed drawdown windows, maximum drawdown to
-16.90% and worst month to -8.85%, but CAGR fell to 5.26% and Calmar to 0.312. The cluster cap
also improved all five windows but reduced CAGR to 1.92%. Neither retained the required 90% of
raw P3 CAGR, and both materially lagged D1 in six non-2011 years.

In v30, the closest candidate was the -17.5% D1-drawdown stop. It improved maximum drawdown to
-21.49%, Calmar to 0.382 and worst month to -12.60%, but CAGR fell to 8.21%, below the frozen
8.458% floor, and only one of five fixed D1 drawdown windows improved.

In v31, the -15% position stop raised CAGR to 9.00%, reduced maximum drawdown to -21.10%, raised
Calmar to 0.427 and improved worst month to -12.35%. It improved only two of five fixed D1
drawdown windows, below the required three. The -12.5% stop improved four windows and retained
8.57% CAGR but materially lagged D1 in two non-2011 years, above the permitted one.

In v32, the one-shot hybrid threshold produced 8.98% CAGR, 0.641 Sharpe, -21.10% maximum drawdown,
0.425 Calmar and a -12.35% worst month. It passed seven of eight gates but improved only two of
five fixed D1 drawdown windows. Following the pre-registered rule, v32 is rejected and the
position-stop optimization sequence ends with D1 retained.

## Reproduce

```bash
python -m pip install -r requirements.txt
PYTHONPATH=. python scripts/evaluate_etf_drawdown_overlay_v29_4.py
PYTHONPATH=. python scripts/evaluate_etf_tail_attribution_v29_5.py
PYTHONPATH=. python scripts/evaluate_etf_concentration_control_v29_6.py
PYTHONPATH=. python scripts/evaluate_d1_hard_drawdown_stop_v30.py
PYTHONPATH=. python scripts/evaluate_d1_position_loss_stop_v31.py
PYTHONPATH=. python scripts/evaluate_d1_hybrid_position_stop_v32.py
MPLCONFIGDIR=/tmp/mplconfig python scripts/plot_d1_hybrid_position_stop_results.py
python -m pytest -q
```

The evaluators are train-only, validate their source hashes, reconcile daily returns and leave
orders disabled. Full protocols and machine-readable decisions are in `docs/` and `reports/`.
