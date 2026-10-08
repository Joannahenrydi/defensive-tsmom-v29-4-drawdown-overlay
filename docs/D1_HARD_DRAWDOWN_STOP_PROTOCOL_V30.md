# v30 — D1 Hard Drawdown Stop

This protocol is frozen before any v30 candidate is run. v30 leaves the P3 alpha engine, every
P3 holding, the complete v29.4 D1 state machine, D1's 5%/10% trough-rebound re-entry eligibility,
next-close execution and the cost model unchanged. v29.6 concentration allocation is not used.
The only new variable is a higher-priority portfolio hard-stop threshold.

## Causal state and execution

The stop observes the immutable D1 control NAV, not the candidate's own NAV. This avoids a
self-locking cash path and keeps every candidate on the same causal state history:

    D1_DD_t = D1_NAV_t / max(D1_NAV_s for s <= t) - 1

When D1 drawdown crosses a candidate threshold at close t, the hard-stop target becomes zero.
The target executes at close t+1, and that executed exposure first affects the following
close-to-close return. A threshold is therefore a trigger, not a mechanical bound on realized
maximum drawdown.

After a stop, the existing D1 re-entry eligibility is reused without another parameter search:
the stop target becomes 50% after the immutable D1 NAV rebounds 5% from its post-trigger trough
and 100% after a 10% rebound. The final target is:

    min(frozen D1 target, hard-stop target)

Thus the stop can override D1 exposure but cannot force exposure above D1's own target.

## Frozen variants

- `D1_CONTROL`: exact v29.4 D1 reproduction.
- `STOP_10`: stop at -10% D1 drawdown.
- `STOP_12_5`: stop at -12.5% D1 drawdown.
- `STOP_15`: stop at -15% D1 drawdown.
- `STOP_17_5`: stop at -17.5% D1 drawdown.
- `STOP_20`: stop at -20% D1 drawdown.

No threshold interpolation, re-entry variant, concentration cap, crash rule, volatility target,
short position or options hedge is permitted.

## Frozen admission and selection

Every candidate must satisfy all conditions:

    CAGR / raw P3 CAGR >= 90% (CAGR >= 8.4580% using the frozen raw-P3 result)
    maximum drawdown is strictly better than D1
    Calmar is strictly better than D1
    worst month is strictly better than D1
    total cost <= 110% of D1 cost
    annualized total turnover <= 110% of D1 turnover
    at least 3 of D1's 5 fixed deepest start-to-trough windows improve
    no more than 1 non-2011 year underperforms D1 by over 2 percentage points

Among candidates passing every gate, select the one with the least severe maximum drawdown. The
listed threshold order is used only for an exact tie. If none passes, retain D1 and issue
`V30_REJECTED_KEEP_D1`; otherwise issue `V30_HARD_STOP_PASS_PROSPECTIVE_REQUIRED`. Neither state
admits orders or permits development/OOS data.
