"""Trade-episode loss stops layered over frozen P3 and D1."""

from __future__ import annotations

import numpy as np
import pandas as pd


def build_trade_panels(
    raw: pd.DataFrame,
    trades: pd.DataFrame,
    ledger: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Reconstruct immutable trade-level values, PnL, costs and active episodes."""
    dates = raw.index
    trade_ids = sorted(trades["trade_id"].astype(int).unique())
    gross = ledger.pivot_table(
        index="date",
        columns="trade_id",
        values="gross_pnl",
        aggfunc="sum",
        fill_value=0.0,
    ).reindex(index=dates, columns=trade_ids, fill_value=0.0)
    costs = ledger.pivot_table(
        index="date",
        columns="trade_id",
        values="cost",
        aggfunc="sum",
        fill_value=0.0,
    ).reindex(index=dates, columns=trade_ids, fill_value=0.0)
    active = pd.DataFrame(False, index=dates, columns=trade_ids)
    marked_value = pd.DataFrame(0.0, index=dates, columns=trade_ids)
    for trade in trades.itertuples(index=False):
        trade_id = int(trade.trade_id)
        mask = dates.to_series().between(
            pd.Timestamp(trade.entry_date),
            pd.Timestamp(trade.exit_date),
            inclusive="left",
        )
        active.loc[mask.to_numpy(), trade_id] = True
        value = float(trade.entry_notional) + gross[trade_id].cumsum()
        marked_value.loc[mask.to_numpy(), trade_id] = value.loc[mask.to_numpy()]
    return {
        "gross": gross,
        "costs": costs,
        "active": active,
        "marked_value": marked_value,
    }


def position_stop_plan(
    dates: pd.DatetimeIndex,
    trades: pd.DataFrame,
    prices: pd.DataFrame,
    d1_executed: pd.Series,
    active: pd.DataFrame,
    threshold: float | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return EOD episode admission and causal stop events."""
    admitted = active.astype(float)
    if threshold is None:
        return admitted, pd.DataFrame()
    rows = []
    for trade in trades.itertuples(index=False):
        trade_id = int(trade.trade_id)
        entry_price = float(trade.entry_notional) / float(trade.shares)
        loss = prices[trade.symbol].div(entry_price).sub(1)
        eligible = active[trade_id] & d1_executed.gt(0) & loss.le(threshold)
        eligible_dates = dates[eligible.fillna(False).to_numpy()]
        if eligible_dates.empty:
            continue
        decision_date = eligible_dates[0]
        decision_location = dates.get_loc(decision_date)
        if decision_location + 1 >= len(dates):
            continue
        execution_date = dates[decision_location + 1]
        original_exit = pd.Timestamp(trade.exit_date)
        if execution_date >= original_exit:
            continue
        lock = dates.to_series().between(
            execution_date, original_exit, inclusive="left"
        )
        admitted.loc[lock.to_numpy(), trade_id] = 0.0
        rows.append(
            {
                "trade_id": trade_id,
                "symbol": trade.symbol,
                "group": trade.group,
                "entry_date": pd.Timestamp(trade.entry_date),
                "original_exit_date": original_exit,
                "decision_date": decision_date,
                "execution_date": execution_date,
                "entry_price": entry_price,
                "decision_price": float(prices.loc[decision_date, trade.symbol]),
                "decision_loss": float(loss.loc[decision_date]),
                "threshold": threshold,
            }
        )
    return admitted, pd.DataFrame(rows)


def run_position_stop(
    raw: pd.DataFrame,
    d1: pd.DataFrame,
    trades: pd.DataFrame,
    panels: dict[str, pd.DataFrame],
    prices: pd.DataFrame,
    threshold: float | None,
    cfg: dict,
) -> dict[str, pd.DataFrame]:
    """Apply independent episode stops while preserving every other D1 exposure."""
    dates = raw.index
    admitted, events = position_stop_plan(
        dates,
        trades,
        prices,
        d1["executed_multiplier"],
        panels["active"],
        threshold,
    )
    prior_admitted = admitted.shift(1).fillna(0.0)
    cost_admitted = pd.DataFrame(1.0, index=dates, columns=admitted.columns)
    if not events.empty:
        for event in events.itertuples(index=False):
            cost_admitted.loc[
                cost_admitted.index >= event.execution_date, event.trade_id
            ] = 0.0
    prior_raw_nav = raw["nav"].shift(1).fillna(raw["nav"].iloc[0])
    gross_return = (
        panels["gross"]
        .mul(prior_admitted)
        .mul(d1["applied_return_multiplier"], axis=0)
        .sum(axis=1)
        .div(prior_raw_nav)
    )
    alpha_cost_return = (
        panels["costs"]
        .mul(cost_admitted)
        .mul(d1["executed_multiplier"], axis=0)
        .sum(axis=1)
        .div(prior_raw_nav)
    )
    admitted_value = panels["marked_value"].mul(admitted).sum(axis=1)
    admitted_raw_exposure = admitted_value.div(raw["nav"])
    d1_overlay_turnover = (
        d1["executed_multiplier"].diff().abs().fillna(0.0) * admitted_raw_exposure
    )
    d1_overlay_cost_return = d1_overlay_turnover * cfg["transaction_cost_one_way"]

    position_stop_turnover = pd.Series(0.0, index=dates)
    if not events.empty:
        events = events.copy()
        for event_index, event in enumerate(events.itertuples(index=False)):
            marked = panels["marked_value"].loc[event.execution_date, event.trade_id]
            held_multiplier = d1.loc[event.execution_date, "applied_return_multiplier"]
            position_stop_turnover.loc[event.execution_date] += (
                marked * held_multiplier / prior_raw_nav.loc[event.execution_date]
            )
            execution_price = float(prices.loc[event.execution_date, event.symbol])
            events.loc[event_index, "execution_price"] = execution_price
            events.loc[event_index, "execution_loss"] = (
                execution_price / event.entry_price - 1
            )
            events.loc[event_index, "execution_marked_value"] = marked
            events.loc[event_index, "d1_multiplier_at_execution"] = held_multiplier
            events.loc[event_index, "exit_cost"] = (
                marked * held_multiplier * cfg["transaction_cost_one_way"]
            )
    position_stop_cost_return = position_stop_turnover * cfg["transaction_cost_one_way"]
    controlled_return = (
        gross_return
        - alpha_cost_return
        - d1_overlay_cost_return
        - position_stop_cost_return
    )
    nav = cfg["initial_nav"] * (1 + controlled_return).cumprod()
    prior_nav = nav.shift(1).fillna(cfg["initial_nav"])
    controlled_exposure = admitted_raw_exposure * d1["executed_multiplier"]
    alpha_turnover = alpha_cost_return.div(cfg["transaction_cost_one_way"])
    total_cost_return = (
        alpha_cost_return + d1_overlay_cost_return + position_stop_cost_return
    )
    daily = pd.DataFrame(
        {
            "controlled_return": controlled_return,
            "nav": nav,
            "gross_return": gross_return,
            "raw_long_exposure": raw["long_exposure"],
            "admitted_raw_exposure": admitted_raw_exposure,
            "d1_multiplier": d1["executed_multiplier"],
            "controlled_long_exposure": controlled_exposure,
            "cash_exposure": 1 - controlled_exposure,
            "alpha_turnover": alpha_turnover,
            "d1_overlay_turnover": d1_overlay_turnover,
            "position_stop_turnover": position_stop_turnover,
            "total_turnover": alpha_turnover
            + d1_overlay_turnover
            + position_stop_turnover,
            "alpha_cost": alpha_cost_return * prior_nav,
            "d1_overlay_cost": d1_overlay_cost_return * prior_nav,
            "position_stop_cost": position_stop_cost_return * prior_nav,
            "total_cost": total_cost_return * prior_nav,
            "stopped_trade_count": panels["active"].sum(axis=1) - admitted.sum(axis=1),
        },
        index=dates,
    )
    return {"daily": daily, "events": events, "admitted": admitted}


def performance_metrics(
    daily: pd.DataFrame,
    raw_p3_cagr: float,
    d1_cagr: float,
    stop_event_count: int,
) -> dict[str, float]:
    returns = daily["controlled_return"]
    years = len(returns) / 252
    total_return = daily["nav"].iloc[-1] / 100000.0 - 1
    cagr = (1 + total_return) ** (1 / years) - 1
    volatility = returns.std(ddof=1)
    drawdown = daily["nav"].div(daily["nav"].cummax()).sub(1)
    maximum_drawdown = float(drawdown.min())
    monthly = (1 + returns).groupby(returns.index.to_period("M")).prod().sub(1)
    return {
        "net_cagr": float(cagr),
        "net_total_return": float(total_return),
        "sharpe": (
            float(returns.mean() / volatility * np.sqrt(252))
            if volatility > 1e-12
            else np.nan
        ),
        "maximum_drawdown": maximum_drawdown,
        "calmar": (
            float(cagr / abs(maximum_drawdown)) if maximum_drawdown < 0 else np.nan
        ),
        "worst_month": float(monthly.min()),
        "average_exposure": float(daily["controlled_long_exposure"].mean()),
        "stop_event_count": int(stop_event_count),
        "average_stopped_trades": float(daily["stopped_trade_count"].mean()),
        "annual_alpha_turnover": float(daily["alpha_turnover"].sum() / years),
        "annual_d1_overlay_turnover": float(daily["d1_overlay_turnover"].sum() / years),
        "annual_position_stop_turnover": float(
            daily["position_stop_turnover"].sum() / years
        ),
        "annual_total_turnover": float(daily["total_turnover"].sum() / years),
        "alpha_cost": float(daily["alpha_cost"].sum()),
        "d1_overlay_cost": float(daily["d1_overlay_cost"].sum()),
        "position_stop_cost": float(daily["position_stop_cost"].sum()),
        "total_cost": float(daily["total_cost"].sum()),
        "raw_p3_cagr_retention": float(cagr / raw_p3_cagr),
        "d1_cagr_retention": float(cagr / d1_cagr),
    }
