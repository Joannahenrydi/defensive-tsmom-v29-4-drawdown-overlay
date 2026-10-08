"""Entry-volatility position stop layered over frozen v31 mechanics."""

from __future__ import annotations

import numpy as np
import pandas as pd


def calibrate_entry_thresholds(
    trades: pd.DataFrame,
    prices: pd.DataFrame,
    cfg: dict,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Derive one k from median entry volatility and freeze every trade threshold."""
    returns = prices.pct_change(fill_method=None)
    volatility = returns.rolling(
        cfg["volatility_window"], min_periods=cfg["volatility_window"]
    ).std(ddof=1) * np.sqrt(cfg["volatility_annualization"])
    rows = []
    for trade in trades.itertuples(index=False):
        entry_date = pd.Timestamp(trade.entry_date)
        sigma = float(volatility.loc[entry_date, trade.symbol])
        if not np.isfinite(sigma) or sigma <= 0:
            raise ValueError(f"invalid entry volatility for trade {trade.trade_id}")
        rows.append(
            {
                "trade_id": int(trade.trade_id),
                "symbol": trade.symbol,
                "group": trade.group,
                "entry_date": entry_date,
                "sigma_20d_annualized": sigma,
            }
        )
    calibration = pd.DataFrame(rows).sort_values("trade_id").reset_index(drop=True)
    median_sigma = float(calibration["sigma_20d_annualized"].median())
    k = float(cfg["median_target_loss"] / median_sigma)
    calibration["unclipped_allowed_loss"] = k * calibration["sigma_20d_annualized"]
    calibration["allowed_loss"] = calibration["unclipped_allowed_loss"].clip(
        lower=cfg["minimum_loss_rail"], upper=cfg["maximum_loss_rail"]
    )
    calibration["stop_threshold"] = -calibration["allowed_loss"]
    calibration["rail"] = np.select(
        [
            calibration["unclipped_allowed_loss"].le(cfg["minimum_loss_rail"]),
            calibration["unclipped_allowed_loss"].ge(cfg["maximum_loss_rail"]),
        ],
        ["12.5% floor", "15.0% ceiling"],
        default="dynamic interior",
    )
    diagnostics = {
        "median_sigma_20d_annualized": median_sigma,
        "k": k,
        "minimum_allowed_loss": float(calibration["allowed_loss"].min()),
        "median_allowed_loss": float(calibration["allowed_loss"].median()),
        "maximum_allowed_loss": float(calibration["allowed_loss"].max()),
        "floor_trade_count": int(calibration["rail"].eq("12.5% floor").sum()),
        "interior_trade_count": int(calibration["rail"].eq("dynamic interior").sum()),
        "ceiling_trade_count": int(calibration["rail"].eq("15.0% ceiling").sum()),
    }
    return calibration, diagnostics


def hybrid_stop_plan(
    dates: pd.DatetimeIndex,
    trades: pd.DataFrame,
    prices: pd.DataFrame,
    d1_executed: pd.Series,
    active: pd.DataFrame,
    calibration: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply each trade's frozen hybrid threshold once per original episode."""
    admitted = active.astype(float)
    thresholds = calibration.set_index("trade_id")
    rows = []
    for trade in trades.itertuples(index=False):
        trade_id = int(trade.trade_id)
        calibrated = thresholds.loc[trade_id]
        entry_price = float(trade.entry_notional) / float(trade.shares)
        loss = prices[trade.symbol].div(entry_price).sub(1)
        eligible = (
            active[trade_id]
            & d1_executed.gt(0)
            & loss.le(float(calibrated["stop_threshold"]))
        )
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
                "sigma_20d_annualized": float(calibrated["sigma_20d_annualized"]),
                "allowed_loss": float(calibrated["allowed_loss"]),
                "threshold": float(calibrated["stop_threshold"]),
                "rail": calibrated["rail"],
                "decision_price": float(prices.loc[decision_date, trade.symbol]),
                "decision_loss": float(loss.loc[decision_date]),
            }
        )
    return admitted, pd.DataFrame(rows)


def run_hybrid_stop(
    raw: pd.DataFrame,
    d1: pd.DataFrame,
    trades: pd.DataFrame,
    panels: dict[str, pd.DataFrame],
    prices: pd.DataFrame,
    calibration: pd.DataFrame | None,
    cfg: dict,
) -> dict[str, pd.DataFrame]:
    """Run control or the single hybrid candidate using frozen v31 mechanics."""
    dates = raw.index
    if calibration is None:
        admitted = panels["active"].astype(float)
        events = pd.DataFrame()
    else:
        admitted, events = hybrid_stop_plan(
            dates,
            trades,
            prices,
            d1["executed_multiplier"],
            panels["active"],
            calibration,
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
