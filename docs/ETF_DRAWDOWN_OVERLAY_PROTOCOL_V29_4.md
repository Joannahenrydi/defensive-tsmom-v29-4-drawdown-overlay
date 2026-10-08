# v29.4 — Long-Only ETF + Drawdown Overlay

Specified on 2026-10-08 after the v29.3 train result was inspected and before any v29.4 result was
read. This is the long-only drawdown-control stage reserved in the frozen route. The user's later
description called it v30 and referred to v29.2 P3; under the immediately preceding numbering lock,
those names map to v29.4 and v29.3 P3. The futures trend/carry v30 remains unchanged.

v29.4 may run only if v29.3 reports `V29_3_LONG_ALPHA_FOUND_RISK_UNASSESSED` and freezes P3 as its
winner. It changes exposure only. It may not change the 45-ETF universe, economic pairs, signal,
causal calibration, ranking, Top-5 rule, long-leg selection, entry/exit, holding period, raw cost
model or next-close execution. The controlled portfolio always satisfies:

    individual ETF weights >= 0
    sum of ETF weights <= 1
    residual capital = cash

The P3 desired long weights remain exactly as produced by v29.3. A multiplier scales every desired
weight proportionally; signal scarcity is never filled with another ETF.

## Evidence status and source lock

The v29.3 raw result is known: net CAGR 9.3978%, Sharpe 0.6325, maximum drawdown -26.5541%, profit
factor 1.8115 and average long exposure 77.2409%. v29.4 is therefore post-result design, not a clean
holdout. It still reads only 2008-01-02–2016-12-30 train data and may not read development/OOS.
Orders remain disabled.

Before running, verify the v29.3 data, protocol, config, engine and evaluator hashes recorded in the
machine-readable v29.4 config, reproduce P3 daily NAV exactly, and stop on any mismatch. P3 runs as
a shadow portfolio even when the controlled portfolio holds cash. Drawdown is always computed from
this shadow P3 net NAV so a cash account cannot become permanently stuck.

## Causal execution and cost

The multiplier decision uses shadow information through close t and takes effect no earlier than
close t+1. Controlled close-to-close return is the prior effective multiplier times the same-share
P3 return, less overlay transition cost. Scale raw P3 trading costs with exposure and charge an
additional 10bp one way on every dollar traded solely because the multiplier changes. Cash earns
zero; no leverage, financing, short, options hedge, VIX, volatility target, moving average,
correlation regime or crash predictor is permitted.

## Four frozen variants

**D0 — control.** Multiplier is always 1.0. It must reproduce v29.3 P3 within numerical tolerance;
failure invalidates the implementation.

**D1 — hard 20% kill switch.** A causal crossing of shadow drawdown from above -20% to -20% or
worse sets the next-session multiplier to zero. While in cash, track the lowest subsequent shadow
NAV. A rebound of 5% from that trough restores 0.5 exposure; a rebound of 10% restores 1.0. If the
rebound falls below 5% before full recovery, return to cash and update the trough. After full
re-entry, the kill switch rearms only after shadow drawdown improves above -20%; this prevents an
immediate cash/rebuy loop while shadow NAV remains below the old threshold.

**D2 — progressive de-risking.** Apply the following multiplier to shadow drawdown, with the same
one-session delay:

| Shadow drawdown | Multiplier |
|---|---:|
| better than -10% | 1.00 |
| -10% to -15% | 0.75 |
| -15% to -20% | 0.50 |
| -20% to -25% | 0.25 |
| -25% or worse | 0.00 |

Because this uses the independently running shadow NAV, improvement through the same thresholds is
the explicit re-entry rule; controlled NAV recovery is not required.

**D3 — smooth scaling.** With shadow drawdown magnitude `d=max(-DD,0)`:

    multiplier = max(0, 1 - d / 0.25)

The shadow drawdown supplies continuous, HWM-independent re-entry. No smoothing or alternate floor
is tested.

## Metrics and admission

For D0–D3 report net CAGR, total return, Sharpe, Sortino, maximum drawdown, Calmar, daily profit
factor, average exposure, time in cash, CAGR retention, drawdown improvement, worst month, number
of de-risk events, re-entry count, overlay turnover and all costs. Also report annual returns,
state transitions and the five largest controlled loss episodes.

    CAGR retention = controlled CAGR / raw P3 CAGR
    DD improvement = 1 - abs(controlled MaxDD) / abs(raw P3 MaxDD)

D1–D3 are eligible only if CAGR retention is at least 80%, maximum drawdown improves strictly, and
Calmar exceeds raw P3 Calmar. Among eligible overlays choose the highest Calmar, with D1, D2, D3 as
the deterministic tie order. D0 is a control and cannot win. If no overlay qualifies, the decision
is `V29_4_REJECTED_KEEP_RAW_P3`. Otherwise it is
`V29_4_TRAIN_DD_PASS_PROSPECTIVE_REQUIRED`. Neither state authorizes orders or development access.
