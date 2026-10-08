"""Causal hard-stop layer over the frozen v29.4 D1 controller."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtest.etf_drawdown_overlay import hard_kill_targets, shadow_drawdown


def hard_stop_targets(
    d1: pd.DataFrame, stop_drawdown: float | None, cfg: dict
) -> tuple[pd.Series, pd.DataFrame]:
    """Build a hard-stop state from immutable D1 NAV with D1's re-entry rule."""
    if stop_drawdown is None:
        target = pd.Series(1.0, index=d1.index, name="hard_stop_target")
        return target, pd.DataFrame()
    spec = {
        "kill_drawdown": stop_drawdown,
        "reentry_half_rebound": cfg["reentry_half_rebound"],
        "reentry_full_rebound": cfg["reentry_full_rebound"],
    }
    target, events = hard_kill_targets(d1["nav"], shadow_drawdown(d1["nav"]), spec)
    target.name = "hard_stop_target"
    if not events.empty:
        events = events.rename(
            columns={
                "shadow_drawdown": "d1_drawdown",
                "shadow_nav": "d1_nav",
            }
        )
    return target, events


def run_hard_stop(
    raw: pd.DataFrame,
    d1: pd.DataFrame,
    stop_drawdown: float | None,
    cfg: dict,
) -> dict[str, pd.DataFrame]:
    """Combine frozen D1 targets with a lagged, higher-priority hard stop."""
    stop_target, stop_events = hard_stop_targets(d1, stop_drawdown, cfg)
    combined_target = pd.concat([d1["decision_multiplier"], stop_target], axis=1).min(
        axis=1
    )
    combined_target.name = "decision_multiplier"
    executed = combined_target.shift(cfg["decision_delay_sessions"]).fillna(1.0)
    applied = executed.shift(1).fillna(1.0)

    prior_raw_nav = raw["nav"].shift(1).fillna(raw["nav"].iloc[0])
    raw_cost_return = raw["cost"].div(prior_raw_nav.where(prior_raw_nav.gt(0)))
    overlay_turnover = executed.diff().abs().fillna(0.0) * raw["long_exposure"]
    overlay_cost_return = overlay_turnover * cfg["transaction_cost_one_way"]
    controlled_return = (
        applied * raw["gross_return"] - executed * raw_cost_return - overlay_cost_return
    )
    nav = cfg["initial_nav"] * (1 + controlled_return).cumprod()
    prior_nav = nav.shift(1).fillna(cfg["initial_nav"])
    alpha_cost = executed * raw_cost_return * prior_nav
    overlay_cost = overlay_cost_return * prior_nav
    daily = pd.DataFrame(
        {
            "d1_shadow_nav": d1["nav"],
            "d1_shadow_drawdown": shadow_drawdown(d1["nav"]),
            "d1_decision_multiplier": d1["decision_multiplier"],
            "hard_stop_target": stop_target,
            "decision_multiplier": combined_target,
            "executed_multiplier": executed,
            "applied_return_multiplier": applied,
            "controlled_return": controlled_return,
            "nav": nav,
            "raw_long_exposure": raw["long_exposure"],
            "controlled_long_exposure": executed * raw["long_exposure"],
            "cash_exposure": 1 - executed * raw["long_exposure"],
            "alpha_turnover": executed * raw["turnover"],
            "overlay_turnover": overlay_turnover,
            "alpha_cost": alpha_cost,
            "overlay_cost": overlay_cost,
            "total_cost": alpha_cost + overlay_cost,
        },
        index=raw.index,
    )
    changes = executed.diff().fillna(0.0)
    execution_events = daily.loc[
        changes.ne(0),
        [
            "d1_shadow_nav",
            "d1_shadow_drawdown",
            "d1_decision_multiplier",
            "hard_stop_target",
            "decision_multiplier",
            "executed_multiplier",
            "controlled_long_exposure",
            "overlay_turnover",
            "overlay_cost",
        ],
    ].reset_index()
    execution_events["event"] = np.where(
        changes.loc[changes.ne(0)].to_numpy() < 0,
        "de_risk_execution",
        "re_entry_execution",
    )
    return {
        "daily": daily,
        "stop_decision_events": stop_events,
        "execution_events": execution_events,
    }


def performance_metrics(
    daily: pd.DataFrame, raw_p3_cagr: float, d1_cagr: float
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
        "time_multiplier_zero": float(daily["executed_multiplier"].eq(0).mean()),
        "de_risk_events": int(daily["executed_multiplier"].diff().lt(0).sum()),
        "re_entry_events": int(daily["executed_multiplier"].diff().gt(0).sum()),
        "annual_alpha_turnover": float(daily["alpha_turnover"].sum() / years),
        "annual_overlay_turnover": float(daily["overlay_turnover"].sum() / years),
        "annual_total_turnover": float(
            (daily["alpha_turnover"].sum() + daily["overlay_turnover"].sum()) / years
        ),
        "alpha_cost": float(daily["alpha_cost"].sum()),
        "overlay_cost": float(daily["overlay_cost"].sum()),
        "total_cost": float(daily["total_cost"].sum()),
        "raw_p3_cagr_retention": float(cagr / raw_p3_cagr),
        "d1_cagr_retention": float(cagr / d1_cagr),
    }
