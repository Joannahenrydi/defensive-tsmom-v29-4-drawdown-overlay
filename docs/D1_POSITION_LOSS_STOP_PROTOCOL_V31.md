# v31 — D1 Position-Level Loss Stop

This protocol is frozen before any v31 candidate is run. v31 does not use portfolio drawdown and
does not scale or stop the whole portfolio. It freezes the P3 alpha engine, P3 trade episodes,
the complete D1 controller, concentration allocation, next-close execution and the existing cost
model. It may liquidate only an individual losing P3 trade held by D1.

## Position loss and causal execution

Each immutable P3 `trade_id` is a separate holding episode. Its reference price is the adjusted
close actually recorded at P3 entry:

    entry_price = entry_notional / shares
    position_loss_i,t = adjusted_close_i,t / entry_price_i - 1

A position is eligible to trigger only while its original P3 episode is active and D1's executed
multiplier is positive. When its loss first reaches a candidate threshold at close t, the stop
decision is recorded. The trade earns its normal close-t to close-(t+1) return and is liquidated
at close t+1. The stop therefore cannot be treated as a mechanical loss bound.

Only the breached `trade_id` is removed. Every other P3 trade continues with the frozen D1
multiplier. Proceeds remain cash and are not reassigned. After execution, the stopped trade stays
at zero through its original P3 exit date. It cannot re-enter because of a price rebound, D1
state change or continued P3 long signal. The same ETF becomes eligible again only through a new
P3 `trade_id` episode.

Original entry costs remain. A stopped episode does not pay its later scheduled P3 exit cost; it
pays a 10bp one-way exit cost on marked position value at the causal stop execution instead. D1
transition costs apply only to episodes still held. These rules reproduce D1 exactly in the
control and avoid double-counting an exit.

## Frozen variants

- `D1_CONTROL`: exact v29.4 D1 reproduction.
- `PSTOP_5`: stop one trade at -5% since P3 entry.
- `PSTOP_7_5`: stop one trade at -7.5% since P3 entry.
- `PSTOP_10`: stop one trade at -10% since P3 entry.
- `PSTOP_12_5`: stop one trade at -12.5% since P3 entry.
- `PSTOP_15`: stop one trade at -15% since P3 entry.

No alternate reference price, trailing stop, rebound re-entry, portfolio stop, replacement asset,
concentration cap, volatility target, short position or options hedge is permitted.

## Frozen admission and selection

Every candidate must satisfy all conditions:

    CAGR / raw P3 CAGR >= 90% (CAGR >= 8.4580%)
    maximum drawdown is strictly better than D1
    Calmar is strictly better than D1
    worst month is strictly better than D1
    total cost <= 110% of D1 cost
    annualized total turnover <= 110% of D1 turnover
    at least 3 of D1's 5 fixed deepest start-to-trough windows improve
    no more than 1 non-2011 year underperforms D1 by over 2 percentage points

Among candidates passing every gate, select the least severe maximum drawdown; use the listed
threshold order only for an exact tie. If none passes, retain D1 and issue
`V31_REJECTED_KEEP_D1`; otherwise issue `V31_POSITION_STOP_PASS_PROSPECTIVE_REQUIRED`. Neither
state admits orders or permits development/OOS data.
