# v32 — Hybrid Static + Dynamic Position Loss Stop

This protocol is frozen before v32 is run. v32 changes only the v31 position-loss threshold. It
does not change P3, D1, concentration, reference prices, execution timing, cash treatment,
episode lockout, re-entry or costs. Portfolio drawdown is never an input.

## One pre-registered dynamic threshold

For each ETF, calculate adjusted-close daily returns and a trailing 20-session sample standard
deviation annualized by square root of 252. At each immutable P3 `trade_id` entry close, read the
volatility estimate using observations through that close:

    sigma_i,entry = std(20 adjusted-close returns through entry close) * sqrt(252)

Across all 216 frozen P3 entries, calculate one median entry volatility and one calibration
constant:

    k = 13.75% / median(sigma_20d,entry)

No alternate k is tested. The trade's allowed loss is frozen for its entire P3 episode:

    allowed_loss_i = clip(k * sigma_i,entry, 12.5%, 15.0%)

Low-volatility entries therefore use the 12.5% floor, the median entry maps to 13.75%, and
high-volatility entries use the 15% ceiling. The threshold cannot widen after entry.

## Execution inherited from v31

Loss is measured from the actual adjusted-close P3 entry price. A trade may trigger only while
its original episode is active and D1 has positive exposure. If trade loss at close t is at or
below the negative frozen allowed loss, only that trade is liquidated at close t+1. It earns the
return through liquidation, pays a 10bp marked-value exit cost, skips its later scheduled exit
cost, remains zero until the original P3 exit and may return only under a new `trade_id`. Every
other frozen P3/D1 exposure remains unchanged and proceeds stay cash.

## Frozen admission

The single hybrid candidate must satisfy every condition:

    CAGR / raw P3 CAGR >= 90% (CAGR >= 8.4580%)
    maximum drawdown is strictly better than D1
    Calmar is strictly better than D1
    worst month is strictly better than D1
    total cost <= 110% of D1 cost
    annualized total turnover <= 110% of D1 turnover
    at least 3 of D1's 5 fixed deepest start-to-trough windows improve
    no more than 1 non-2011 year underperforms D1 by over 2 percentage points

Passing every gate produces `V32_HYBRID_POSITION_STOP_ACCEPT_PROSPECTIVE_REQUIRED`. Failure of
any gate produces `V32_REJECTED_KEEP_D1`. There is no threshold, k, volatility-window or re-entry
follow-up search. Neither state admits orders or permits development/OOS data.
