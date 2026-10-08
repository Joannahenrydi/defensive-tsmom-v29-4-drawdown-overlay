# Risk Admission Protocol v2 — Materiality-Aware Tail Episodes

This protocol retires the strict `at least 3 of 5 fixed D1 drawdowns improve` rule for future
candidates. That rule treated any positive difference as improvement and any zero or negative
difference as failure, even when the difference was economically immaterial. It also did not
distinguish a neutral episode from material deterioration.

The change does not revise, overwrite or accept v32. The original v32 decision remains
`V32_REJECTED_KEEP_D1`. The frozen v32 outputs may be reclassified only as a retrospective
diagnostic. A formal acceptance under this protocol requires a new candidate whose specification
is committed and frozen after Protocol v2.

## Tail-Episode Robustness Gate

Use the same five frozen D1 start-to-trough windows. For episode `j`:

    delta_j = candidate_return_j - d1_return_j
    normalized_improvement_j = delta_j / abs(d1_return_j)

Classify each episode using fixed, inclusive boundaries:

- material improvement: `normalized_improvement >= 5%`;
- neutral: `-2% < normalized_improvement < 5%`;
- material deterioration: `normalized_improvement <= -2%`.

All three conditions must pass:

    material improvement count >= 2
    material deterioration count = 0
    aggregate fixed-tail improvement > 0

where:

    aggregate fixed-tail improvement = sum(delta_j) / sum(abs(d1_return_j))

This preserves breadth, prohibits meaningful collateral damage and requires the five windows to
improve in aggregate. Economically immaterial changes remain neutral.

## Full admission gate for future candidates

The other frozen conditions remain unchanged:

1. CAGR at least 8.4580%, equal to at least 90% of raw P3 CAGR;
2. maximum drawdown strictly better than D1's -23.4949%;
3. Calmar strictly better than D1's 0.379924;
4. worst month strictly better than D1's -13.8327%;
5. total cost no more than 110% of D1;
6. annualized total turnover no more than 110% of D1;
7. no more than one non-2011 year trails D1 by over two percentage points;
8. the complete Tail-Episode Robustness Gate above.

Protocol v2 is frozen for future candidates. Retrospective diagnostics cannot change a historical
decision, enable orders or create risk admission.
