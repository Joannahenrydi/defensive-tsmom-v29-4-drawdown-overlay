"""Causal exposure overlays for the frozen v29.4 drawdown experiment."""

from __future__ import annotations

import numpy as np
import pandas as pd


def shadow_drawdown(nav: pd.Series) -> pd.Series:
    return nav.div(nav.cummax()).sub(1).rename("shadow_drawdown")


def progressive_multiplier(drawdown: float, tiers: list[dict]) -> float:
    for tier in tiers:
        if drawdown > tier["minimum_drawdown"]:
            return float(tier["multiplier"])
    return float(tiers[-1]["multiplier"])


def hard_kill_targets(
    shadow_nav: pd.Series, drawdown: pd.Series, spec: dict
) -> tuple[pd.Series, pd.DataFrame]:
    """Create the D1 target state with trough-based hysteretic re-entry."""
    targets = pd.Series(1.0, index=shadow_nav.index, name="decision_multiplier")
    events: list[dict] = []
    state = "full"
    trough = np.nan
    rearmed = True
    previous_drawdown = 0.0
    for date in shadow_nav.index:
        nav = float(shadow_nav.loc[date])
        dd = float(drawdown.loc[date])
        old_target = 1.0 if state == "full" else 0.5 if state == "half" else 0.0
        if state == "full":
            crossed = previous_drawdown > spec["kill_drawdown"] >= dd
            if rearmed and crossed:
                state = "cash"
                trough = nav
                rearmed = False
            elif not rearmed and dd > spec["kill_drawdown"]:
                rearmed = True
        else:
            trough = min(float(trough), nav)
            rebound = nav / trough - 1
            if rebound >= spec["reentry_full_rebound"]:
                state = "full"
                rearmed = dd > spec["kill_drawdown"]
            elif rebound >= spec["reentry_half_rebound"]:
                state = "half"
            else:
                state = "cash"
        target = 1.0 if state == "full" else 0.5 if state == "half" else 0.0
        targets.loc[date] = target
        if target != old_target:
            events.append(
                {
                    "decision_date": date,
                    "old_multiplier": old_target,
                    "new_multiplier": target,
                    "shadow_drawdown": dd,
                    "shadow_nav": nav,
                    "event": "de_risk" if target < old_target else "re_entry",
                }
            )
        previous_drawdown = dd
    return targets, pd.DataFrame(events)


def decision_targets(
    raw: pd.DataFrame, variant: str, cfg: dict
) -> tuple[pd.Series, pd.DataFrame]:
    drawdown = shadow_drawdown(raw["nav"])
    spec = cfg["variants"][variant]
    if spec["type"] == "control":
        targets = pd.Series(1.0, index=raw.index, name="decision_multiplier")
    elif spec["type"] == "hard_kill":
        return hard_kill_targets(raw["nav"], drawdown, spec)
    elif spec["type"] == "progressive":
        targets = drawdown.map(
            lambda value: progressive_multiplier(value, spec["tiers"])
        )
    elif spec["type"] == "smooth":
        floor = abs(spec["zero_exposure_drawdown"])
        targets = (1 - drawdown.abs() / floor).clip(lower=0, upper=1)
    else:
        raise ValueError(f"unknown overlay type: {spec['type']}")
    targets.name = "decision_multiplier"
    change = targets.diff().fillna(0)
    events = pd.DataFrame(
        {
            "decision_date": targets.index[change.ne(0)],
            "old_multiplier": targets.shift(1).loc[change.ne(0)].to_numpy(),
            "new_multiplier": targets.loc[change.ne(0)].to_numpy(),
            "shadow_drawdown": drawdown.loc[change.ne(0)].to_numpy(),
            "shadow_nav": raw.loc[change.ne(0), "nav"].to_numpy(),
            "event": np.where(
                change.loc[change.ne(0)].to_numpy() < 0, "de_risk", "re_entry"
            ),
        }
    )
    return targets, events


def run_overlay(raw: pd.DataFrame, variant: str, cfg: dict) -> dict[str, pd.DataFrame]:
    """Apply lagged multiplier decisions to the same-share raw P3 return stream."""
    raw = raw.copy()
    targets, decision_events = decision_targets(raw, variant, cfg)
    executed = targets.shift(cfg["decision_delay_sessions"]).fillna(1.0)
    applied = executed.shift(1).fillna(1.0)
    prior_raw_nav = raw["nav"].shift(1).fillna(raw["nav"].iloc[0])
    raw_cost_return = raw["cost"].div(prior_raw_nav.where(prior_raw_nav.gt(0)))
    transition_turnover = executed.diff().abs().fillna(0) * raw["long_exposure"]
    overlay_cost_return = transition_turnover * cfg["transaction_cost_one_way"]
    controlled_return = (
        applied * raw["gross_return"] - executed * raw_cost_return - overlay_cost_return
    )
    nav = cfg.get("initial_nav", 100000.0) * (1 + controlled_return).cumprod()
    prior_controlled_nav = nav.shift(1).fillna(cfg.get("initial_nav", 100000.0))
    alpha_cost = executed * raw_cost_return * prior_controlled_nav
    overlay_cost = overlay_cost_return * prior_controlled_nav
    controlled = pd.DataFrame(
        {
            "shadow_nav": raw["nav"],
            "shadow_drawdown": shadow_drawdown(raw["nav"]),
            "decision_multiplier": targets,
            "executed_multiplier": executed,
            "applied_return_multiplier": applied,
            "raw_net_return": raw["net_return"],
            "controlled_return": controlled_return,
            "nav": nav,
            "raw_long_exposure": raw["long_exposure"],
            "controlled_long_exposure": executed * raw["long_exposure"],
            "cash_exposure": 1 - executed * raw["long_exposure"],
            "raw_alpha_turnover": executed * raw["turnover"],
            "overlay_turnover": transition_turnover,
            "alpha_cost": alpha_cost,
            "overlay_cost": overlay_cost,
            "total_cost": alpha_cost + overlay_cost,
        },
        index=raw.index,
    )
    execution_changes = executed.diff().fillna(0)
    execution_events = controlled.loc[
        execution_changes.ne(0),
        [
            "shadow_nav",
            "shadow_drawdown",
            "decision_multiplier",
            "executed_multiplier",
            "controlled_long_exposure",
            "overlay_turnover",
            "overlay_cost",
        ],
    ].reset_index()
    execution_events["event"] = np.where(
        execution_changes.loc[execution_changes.ne(0)].to_numpy() < 0,
        "de_risk_execution",
        "re_entry_execution",
    )
    return {
        "daily": controlled,
        "decision_events": decision_events,
        "execution_events": execution_events,
    }


def drawdown_episodes(nav: pd.Series) -> pd.DataFrame:
    """Return completed and open drawdown episodes, ordered by severity later by the caller."""
    high = nav.cummax()
    drawdown = nav.div(high).sub(1)
    rows = []
    start = trough = None
    trough_value = 0.0
    for date, value in drawdown.items():
        if value < 0 and start is None:
            start = date
            trough = date
            trough_value = float(value)
        elif start is not None:
            if value < trough_value:
                trough = date
                trough_value = float(value)
            if value >= 0:
                rows.append(
                    {
                        "start": start,
                        "trough": trough,
                        "recovery": date,
                        "maximum_drawdown": trough_value,
                        "duration_sessions": int(
                            nav.index.get_loc(date) - nav.index.get_loc(start) + 1
                        ),
                    }
                )
                start = trough = None
                trough_value = 0.0
    if start is not None:
        rows.append(
            {
                "start": start,
                "trough": trough,
                "recovery": pd.NaT,
                "maximum_drawdown": trough_value,
                "duration_sessions": int(len(nav) - nav.index.get_loc(start)),
            }
        )
    return pd.DataFrame(rows)


def overlay_metrics(
    daily: pd.DataFrame, raw_metrics: dict, cfg: dict
) -> dict[str, float]:
    returns = daily["controlled_return"]
    years = len(returns) / 252
    total_return = daily["nav"].iloc[-1] / cfg.get("initial_nav", 100000.0) - 1
    cagr = (1 + total_return) ** (1 / years) - 1
    volatility = returns.std(ddof=1)
    downside = np.sqrt(np.mean(np.minimum(returns, 0) ** 2))
    drawdown = daily["nav"].div(daily["nav"].cummax()).sub(1)
    maximum_drawdown = float(drawdown.min())
    monthly = (1 + returns).groupby(returns.index.to_period("M")).prod().sub(1)
    losses = -returns.loc[returns.lt(0)].sum()
    raw_cagr = raw_metrics["cagr"]
    raw_drawdown = raw_metrics["maximum_drawdown"]
    return {
        "net_cagr": float(cagr),
        "net_total_return": float(total_return),
        "sharpe": (
            float(returns.mean() / volatility * np.sqrt(252))
            if volatility > 1e-12
            else np.nan
        ),
        "sortino": (
            float(returns.mean() / downside * np.sqrt(252))
            if downside > 1e-12
            else np.nan
        ),
        "maximum_drawdown": maximum_drawdown,
        "calmar": (
            float(cagr / abs(maximum_drawdown)) if maximum_drawdown < 0 else np.nan
        ),
        "daily_profit_factor": (
            float(returns.loc[returns.gt(0)].sum() / losses) if losses > 0 else np.nan
        ),
        "average_exposure": float(daily["controlled_long_exposure"].mean()),
        "time_multiplier_zero": float(daily["executed_multiplier"].eq(0).mean()),
        "worst_month": float(monthly.min()),
        "de_risk_events": int(daily["executed_multiplier"].diff().lt(0).sum()),
        "re_entry_events": int(daily["executed_multiplier"].diff().gt(0).sum()),
        "overlay_turnover": float(daily["overlay_turnover"].sum() / years),
        "alpha_turnover": float(daily["raw_alpha_turnover"].sum() / years),
        "alpha_cost": float(daily["alpha_cost"].sum()),
        "overlay_cost": float(daily["overlay_cost"].sum()),
        "total_cost": float(daily["total_cost"].sum()),
        "cagr_retention": float(cagr / raw_cagr) if raw_cagr != 0 else np.nan,
        "drawdown_improvement": (
            float(1 - abs(maximum_drawdown) / abs(raw_drawdown))
            if raw_drawdown != 0
            else np.nan
        ),
    }
