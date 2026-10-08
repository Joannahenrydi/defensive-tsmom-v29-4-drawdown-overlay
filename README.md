# ETF Drawdown Research — v29.4 to v29.6

## Result reports

- [v29.4 result report](V29_4_RESULT_REPORT.md)
- [v29.5 result report](V29_5_RESULT_REPORT.md)
- [v29.6 result report](V29_6_RESULT_REPORT.md)

This private repository contains only the three frozen research stages requested for the long-only
ETF strategy:

- **v29.4** applies causal drawdown-driven exposure scaling to the frozen P3 long-and-cash return
  stream. D1 is the train winner.
- **v29.5** attributes D1's remaining left tail by episode, month, event, ETF and economic sleeve.
  Its single permitted re-entry treatment fails admission, so the final decision keeps D1.
- **v29.6** holds P3 and D1 fixed while testing a 40% sleeve cap and a causal 120-session
  correlation-cluster risk cap. Both reduce the measured left tail but sacrifice too much return,
  so the final decision again keeps D1.

The repository does not contain earlier strategy implementations. `inputs/frozen_p3/` holds only
the immutable P3 decision, daily return stream and trade-ledger evidence needed to reproduce
v29.4–v29.6. `inputs/frozen_market/` supplies the locked 45-ETF adjusted-close history needed only
for v29.6's causal correlation clusters.

## Results

| Stage | Decision | Selected result |
|---|---|---|
| v29.4 | `V29_4_TRAIN_DD_PASS_PROSPECTIVE_REQUIRED` | D1 |
| v29.5 | `V29_5_TARGETED_PROTECTION_REJECTED_KEEP_D1` | Keep D1 |
| v29.6 | `V29_6_REJECTED_KEEP_D1` | Keep D1 |

Raw P3 had 9.40% CAGR and -26.55% maximum drawdown. D1 retained 8.93% CAGR and reduced maximum
drawdown to -23.49%. v29.5 identified August 2011 as the -13.83% worst month: the controller
avoided 6.24% of negative-return exposure but missed 11.29% of positive-return exposure. XLF
supplied 58.62% of negative contribution and the US-equity sleeve supplied 86.59%.

In v29.6, the 40% sleeve cap improved all five fixed drawdown windows, maximum drawdown to
-16.90% and worst month to -8.85%, but CAGR fell to 5.26% and Calmar to 0.312. The cluster cap
also improved all five windows but reduced CAGR to 1.92%. Neither retained the required 90% of
raw P3 CAGR, and both materially lagged D1 in six non-2011 years.

## Reproduce

```bash
python -m pip install -r requirements.txt
PYTHONPATH=. python scripts/evaluate_etf_drawdown_overlay_v29_4.py
PYTHONPATH=. python scripts/evaluate_etf_tail_attribution_v29_5.py
PYTHONPATH=. python scripts/evaluate_etf_concentration_control_v29_6.py
python -m pytest -q
```

The evaluators are train-only, validate their source hashes, reconcile daily returns and leave
orders disabled. Full protocols and machine-readable decisions are in `docs/` and `reports/`.
