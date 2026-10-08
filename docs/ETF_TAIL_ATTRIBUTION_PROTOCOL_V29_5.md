# v29.5 — D1 Tail-Loss Attribution and Targeted Protection

Specified on 2026-10-08 after v29.4 selected D1 and before the D1 worst month, episode path or
asset contribution was decomposed. v29.5 may not change the v29.3 P3 universe, signal,
calibration, ranking, Top-5 selection, entries, exits, cost model or next-close execution. It may
not search generic D4/D5 exposure controllers. D1 remains the frozen control.

## Objective and evidence status

The train-known facts are D1 CAGR 8.9263%, maximum drawdown -23.4949%, Calmar 0.3799 and worst
month -13.8327%. The objective is to identify why the left tail remains and, only when the
attribution identifies an addressable mechanism, test one preregistered mechanism-specific
candidate. This is post-result train research. A pass requires prospective validation and never
authorizes orders or development/OOS access.

All source decisions and daily/ledger/trade files are hash locked. The evaluator must reconcile
the following identity every day:

    D1 return = raw P3 net return
              + low-exposure gross-return effect
              + scaled alpha-cost effect
              - overlay transition cost

The low-exposure effect is split into avoided losses on negative P3 days and missed rebounds on
positive P3 days. The one-session signal/execution lag is measured separately as the return
difference between the actual exposure and the exposure requested at the preceding close. This is
a diagnostic counterfactual, not a tradable same-close backtest.

## Required attribution

Analyze the five deepest D1 drawdowns from start through trough, the D1 worst calendar month and
every D1 de-risk/re-entry event. For each window report D1 and raw P3 return, worst one- and
five-session returns, time to trough, full-exposure loss, avoided loss, missed rebound, de-risk
lag loss, re-entry lag loss, alpha-cost scaling, overlay cost, and event counts.

Map every P3 ledger item through trade ID to ETF and economic group. Report the negative
contribution by ETF and sleeve for every episode and the worst month, and verify that ledger plus
overlay cost reconciles to the D1 daily return stream.

The diagnostic labels are frozen as follows:

- `sudden_crash`: worst day <= -4% or worst rolling five-session return <= -8%.
- `slow_drawdown`: at least 20 sessions from start to trough without a sudden-crash flag.
- `signal_lag`: de-risk lag loss is at least 1% and at least 20% of the window loss.
- `missed_rebound`: foregone positive-return contribution is at least 1% and exceeds avoided loss.
- `concentration`: one ETF or sleeve supplies at least 50% of negative attributed contribution.

Labels may overlap. Primary cause precedence is missed rebound, sudden crash with signal lag,
sudden crash, slow drawdown, concentration, then mixed. The worst month determines the single
conditional treatment path; the five episodes supply corroborating evidence.

## Frozen conditional decision tree

If the worst month is primarily `missed_rebound`, test only
`R1_DIRECT_FULL_AT_5_PERCENT_REBOUND`: retain D1's -20% kill, but restore full exposure at a 5%
shadow-P3 rebound. If it is primarily `slow_drawdown`, test only `S1_KILL_AT_18_PERCENT`: retain
D1's 5% half/10% full re-entry and move only the kill threshold from -20% to -18%.

If the primary cause is sudden crash, signal lag or concentration, do not fabricate an options
history, same-close fill or sleeve cap. The result must identify the required new data or separate
portfolio-design experiment and keep D1. No alternate candidate may be substituted after results
are read.

## Targeted-candidate gate

A conditional candidate passes only if all conditions hold against frozen D1:

    CAGR / raw P3 CAGR >= 90%
    maximum drawdown is strictly better than D1
    worst month > -10%
    Calmar is strictly better than D1
    total cost <= 110% of D1 total cost
    total de-risk events <= 10

Failure keeps D1. Possible final states are
`V29_5_ATTRIBUTED_NEW_DATA_REQUIRED_KEEP_D1`,
`V29_5_TARGETED_PROTECTION_REJECTED_KEEP_D1`, and
`V29_5_TARGETED_PROTECTION_PASS_PROSPECTIVE_REQUIRED`.
