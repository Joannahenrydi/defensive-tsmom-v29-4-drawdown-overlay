# ETF Drawdown Research — v29.4 and v29.5

This private repository contains only the two frozen research stages requested for the long-only
ETF strategy:

- **v29.4** applies causal drawdown-driven exposure scaling to the frozen P3 long-and-cash return
  stream. D1 is the train winner.
- **v29.5** attributes D1's remaining left tail by episode, month, event, ETF and economic sleeve.
  Its single permitted re-entry treatment fails admission, so the final decision keeps D1.

The repository does not contain earlier strategy implementations. `inputs/frozen_p3/` holds only
the immutable P3 decision, daily return stream and trade-ledger evidence needed to reproduce
v29.4 and v29.5.

## Results

| Stage | Decision | Selected result |
|---|---|---|
| v29.4 | `V29_4_TRAIN_DD_PASS_PROSPECTIVE_REQUIRED` | D1 |
| v29.5 | `V29_5_TARGETED_PROTECTION_REJECTED_KEEP_D1` | Keep D1 |

Raw P3 had 9.40% CAGR and -26.55% maximum drawdown. D1 retained 8.93% CAGR and reduced maximum
drawdown to -23.49%. v29.5 identified August 2011 as the -13.83% worst month: the controller
avoided 6.24% of negative-return exposure but missed 11.29% of positive-return exposure. XLF
supplied 58.62% of negative contribution and the US-equity sleeve supplied 86.59%.

## Reproduce

```bash
python -m pip install -r requirements.txt
PYTHONPATH=. python scripts/evaluate_etf_drawdown_overlay_v29_4.py
PYTHONPATH=. python scripts/evaluate_etf_tail_attribution_v29_5.py
python -m pytest -q
```

The evaluators are train-only, validate their source hashes, reconcile daily returns and leave
orders disabled. Full protocols and machine-readable decisions are in `docs/` and `reports/`.
