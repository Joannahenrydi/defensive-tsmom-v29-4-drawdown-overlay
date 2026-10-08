# Risk Admission Protocol v2 — v32 Retrospective Diagnostic

## Status

**V32_WOULD_QUALIFY_UNDER_PROTOCOL_V2_RETROSPECTIVE_ONLY**

The historical v32 decision remains **`V32_REJECTED_KEEP_D1`**. This diagnostic did not rerun
v32, change a parameter or create formal acceptance. It only reclassified the same five frozen
episode returns under the newly frozen materiality-aware rule.

| Episode | D1 return | v32 return | Delta | Normalized improvement | Classification |
|---:|---:|---:|---:|---:|---|
| 1 | -23.49% | -21.02% | 2.478% | 10.55% | material improvement |
| 2 | -16.38% | -14.90% | 1.484% | 9.06% | material improvement |
| 3 | -13.99% | -13.99% | 0.000% | 0.00% | neutral |
| 4 | -8.05% | -8.06% | -0.017% | -0.21% | neutral |
| 5 | -7.39% | -7.39% | 0.000% | 0.00% | neutral |

## Tail-Episode Robustness Gate

- Material improvements: **2/5**; required at least 2.
- Neutral episodes: **3/5**.
- Material deteriorations: **0/5**; required 0.
- Aggregate fixed-tail improvement: **5.69%**; required strictly positive.

All three tail conditions pass. Episode 4's -0.017 percentage-point change is -0.21% relative to
that D1 episode loss, so Protocol v2 correctly classifies it as neutral rather than material
deterioration.

## Unchanged admission checks

- `raw_p3_cagr_retention`: **PASS**
- `maximum_drawdown_better_than_d1`: **PASS**
- `calmar_better_than_d1`: **PASS**
- `worst_month_better_than_d1`: **PASS**
- `cost_within_limit`: **PASS**
- `turnover_within_limit`: **PASS**
- `non_2011_years_not_broadly_worse`: **PASS**

Under Protocol v2, the frozen v32 result **would qualify retrospectively** because every unchanged
gate and the new tail gate pass. This is diagnostic evidence only. It does not modify v32's
decision, select v32 for trading, enable orders or constitute prospective validation.
