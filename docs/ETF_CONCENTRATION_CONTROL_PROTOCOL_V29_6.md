# v29.6 — Concentration-Aware Long Risk Allocation

Specified after v29.5 showed concentration in all five deepest D1 drawdowns and before any v29.6
variant was run. v29.6 freezes the P3 alpha engine, every P3 desired holding, the D1 -20% kill,
the D1 5%/10% re-entry hysteresis, next-close execution and the cost model. It may only reduce
duplicated long risk and send the removed capital to cash. It may not replace a capped holding,
add a short, change a signal, tune D1 timing or add an options hedge.

## Frozen source reconstruction

Reconstruct every end-of-day P3 ETF holding from the hash-locked trade ledger and verify that its
aggregate market value divided by P3 NAV equals the recorded P3 long exposure every day. Map
trade-level gross PnL and cost to ETF and economic sleeve, then reproduce v29.4 D1 exactly as C0.
Any daily return, NAV, exposure or source-hash mismatch invalidates the experiment.

The 45-ETF train-period adjusted-close snapshot is frozen by SHA-256 and is used only for C2's
causal correlation and covariance estimates. The file ends on 2016-12-30. All estimates use data
through close t and affect returns only after the existing next-close execution chain.
Development/OOS is not present or read.

## Variants

**C0 — control.** Exact v29.4 D1 reproduction.

**C1 — sleeve exposure cap.** After applying D1, cap every economic sleeve at 40% of portfolio
capital. Scale holdings inside a binding sleeve proportionally and leave the excess in cash. Do
not reallocate it to another sleeve.

**C2 — correlation-cluster risk cap.** Use a trailing 120-session adjusted-close return window
with at least 100 observations. Active ETFs are connected when their causal correlation is at
least 0.70; connected components form the clusters. For each cluster calculate standalone
annualized volatility divided by the median active-ETF annualized volatility. This produces a
cash-aware normalized cluster-risk load in capital-equivalent units. Scale a cluster
proportionally when its load exceeds 35%; leave the excess in cash. No alternate window,
threshold, clustering method or cap is tested.

P3 entry/exit cost is scaled by the admitted allocation. Charge 10bp one way for D1 exposure
transitions and for concentration-scale changes on continuing holdings. C0 must reproduce D1's
cost exactly.

## Admission

C1 and C2 are eligible only when all conditions hold:

    CAGR / raw P3 CAGR >= 90%
    maximum drawdown is strictly better than D1
    Calmar is strictly better than D1
    worst month is strictly better than D1
    total cost <= 110% of D1 cost
    annualized total turnover <= 110% of D1 turnover
    at least 3 of D1's 5 deepest start-to-trough windows improve
    no more than 1 non-2011 year underperforms D1 by over 2 percentage points

Among eligible candidates select the highest Calmar, with C1 then C2 as deterministic tie order.
If neither passes, keep D1. Possible final states are
`V29_6_CONCENTRATION_CONTROL_PASS_PROSPECTIVE_REQUIRED` and
`V29_6_REJECTED_KEEP_D1`. Neither state admits orders or development/OOS use.
