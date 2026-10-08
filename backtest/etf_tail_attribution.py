"""Attribution helpers for the frozen v29.5 D1 left-tail diagnosis."""

from __future__ import annotations

import numpy as np
import pandas as pd


def daily_return_attribution(
    d1: pd.DataFrame, raw: pd.DataFrame, initial_nav: float = 100000.0
) -> pd.DataFrame:
    """Reconcile D1 return to raw P3, exposure scaling, and cost effects."""
    if not d1.index.equals(raw.index):
        raise ValueError("D1 and raw P3 dates do not match")
    prior_raw_nav = raw["nav"].shift(1).fillna(initial_nav)
    prior_d1_nav = d1["nav"].shift(1).fillna(initial_nav)
    raw_cost_return = raw["cost"].div(prior_raw_nav)
    overlay_cost_effect = -d1["overlay_cost"].div(prior_d1_nav)
    exposure_effect = d1["applied_return_multiplier"].sub(1).mul(raw["gross_return"])
    scaled_alpha_cost_effect = d1["executed_multiplier"].rsub(1).mul(raw_cost_return)
    reconstructed = (
        raw["net_return"]
        + exposure_effect
        + scaled_alpha_cost_effect
        + overlay_cost_effect
    )
    previous_decision = d1["decision_multiplier"].shift(1).fillna(1.0)
    lag_effect = (
        d1["applied_return_multiplier"].sub(previous_decision).mul(raw["gross_return"])
    )
    return pd.DataFrame(
        {
            "raw_p3_return": raw["net_return"],
            "d1_return": d1["controlled_return"],
            "reconstructed_d1_return": reconstructed,
            "reconciliation_error": reconstructed - d1["controlled_return"],
            "full_exposure_loss": raw["net_return"].where(
                d1["applied_return_multiplier"].ge(1 - 1e-12) & raw["net_return"].lt(0),
                0.0,
            ),
            "avoided_loss": exposure_effect.where(raw["gross_return"].lt(0), 0.0),
            "missed_rebound": exposure_effect.where(raw["gross_return"].gt(0), 0.0),
            "scaled_alpha_cost_effect": scaled_alpha_cost_effect,
            "overlay_cost_effect": overlay_cost_effect,
            "de_risk_lag_loss": lag_effect.where(
                d1["applied_return_multiplier"].gt(previous_decision)
                & raw["gross_return"].lt(0),
                0.0,
            ),
            "reentry_lag_loss": lag_effect.where(
                d1["applied_return_multiplier"].lt(previous_decision)
                & raw["gross_return"].gt(0),
                0.0,
            ),
            "decision_multiplier": d1["decision_multiplier"],
            "executed_multiplier": d1["executed_multiplier"],
            "applied_multiplier": d1["applied_return_multiplier"],
        },
        index=d1.index,
    )


def ledger_return_attribution(
    ledger: pd.DataFrame,
    trades: pd.DataFrame,
    d1: pd.DataFrame,
    raw: pd.DataFrame,
    initial_nav: float = 100000.0,
) -> pd.DataFrame:
    """Map the frozen P3 trade ledger into D1 ETF and sleeve return contributions."""
    mapping = trades[["trade_id", "symbol", "group"]].drop_duplicates("trade_id")
    frame = ledger.merge(mapping, on="trade_id", how="left", validate="many_to_one")
    if frame[["symbol", "group"]].isna().any().any():
        raise ValueError("unmapped P3 trade ledger item")
    frame["date"] = pd.to_datetime(frame["date"])
    prior_raw_nav = raw["nav"].shift(1).fillna(initial_nav)
    frame = frame.join(prior_raw_nav.rename("prior_raw_nav"), on="date")
    frame = frame.join(
        d1[["applied_return_multiplier", "executed_multiplier"]], on="date"
    )
    frame["gross_contribution"] = (
        frame["applied_return_multiplier"] * frame["gross_pnl"] / frame["prior_raw_nav"]
    )
    frame["alpha_cost_contribution"] = (
        -frame["executed_multiplier"] * frame["cost"] / frame["prior_raw_nav"]
    )
    frame["net_contribution"] = (
        frame["gross_contribution"] + frame["alpha_cost_contribution"]
    )
    return frame


def compounded_return(returns: pd.Series) -> float:
    return float((1 + returns).prod() - 1)


def worst_rolling_return(returns: pd.Series, sessions: int) -> float:
    if len(returns) < sessions:
        return compounded_return(returns)
    rolling = (1 + returns).rolling(sessions).apply(np.prod, raw=True).sub(1)
    return float(rolling.min())


def contribution_concentration(
    ledger: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, field: str
) -> tuple[float, str | None]:
    window = ledger.loc[ledger["date"].between(start, end)]
    contribution = window.groupby(field)["net_contribution"].sum()
    negative = contribution.loc[contribution.lt(0)]
    if negative.empty:
        return 0.0, None
    share = negative.abs().div(negative.abs().sum())
    return float(share.max()), str(share.idxmax())


def classify_window(row: dict, cfg: dict) -> tuple[list[str], str]:
    rules = cfg["attribution"]
    labels = []
    sudden = bool(
        row["worst_day"] <= rules["sudden_crash_one_day"]
        or row["worst_five_day"] <= rules["sudden_crash_five_day"]
    )
    loss = abs(min(row["d1_return"], 0.0))
    lag_share = abs(min(row["de_risk_lag_loss"], 0.0)) / loss if loss > 0 else 0.0
    if sudden:
        labels.append("sudden_crash")
    if (
        row["sessions_to_trough"] >= rules["slow_drawdown_minimum_sessions"]
        and not sudden
    ):
        labels.append("slow_drawdown")
    if (
        row["de_risk_lag_loss"] <= rules["material_lag_loss"]
        and lag_share >= rules["material_lag_share"]
    ):
        labels.append("signal_lag")
    if (
        row["missed_rebound"] <= rules["material_missed_rebound"]
        and abs(row["missed_rebound"]) > row["avoided_loss"]
    ):
        labels.append("missed_rebound")
    if (
        max(row["top_etf_negative_share"], row["top_group_negative_share"])
        >= rules["concentration_share"]
    ):
        labels.append("concentration")

    if "missed_rebound" in labels:
        primary = "missed_rebound"
    elif "sudden_crash" in labels and "signal_lag" in labels:
        primary = "sudden_crash_signal_lag"
    elif "sudden_crash" in labels:
        primary = "sudden_crash"
    elif "slow_drawdown" in labels:
        primary = "slow_drawdown"
    elif "concentration" in labels:
        primary = "concentration"
    else:
        primary = "mixed"
    return labels, primary


def summarize_window(
    name: str,
    start: pd.Timestamp,
    trough: pd.Timestamp,
    end: pd.Timestamp,
    daily: pd.DataFrame,
    ledger: pd.DataFrame,
    cfg: dict,
    recovery: pd.Timestamp | None = None,
) -> dict:
    window = daily.loc[start:end]
    etf_share, etf = contribution_concentration(ledger, start, end, "symbol")
    group_share, group = contribution_concentration(ledger, start, end, "group")
    row = {
        "window": name,
        "start": start,
        "trough": trough,
        "end": end,
        "recovery": recovery,
        "sessions_to_trough": int(len(daily.loc[start:trough])),
        "d1_return": compounded_return(window["d1_return"]),
        "raw_p3_return": compounded_return(window["raw_p3_return"]),
        "worst_day": float(window["d1_return"].min()),
        "worst_five_day": worst_rolling_return(window["d1_return"], 5),
        "full_exposure_loss": float(window["full_exposure_loss"].sum()),
        "avoided_loss": float(window["avoided_loss"].sum()),
        "missed_rebound": float(window["missed_rebound"].sum()),
        "de_risk_lag_loss": float(window["de_risk_lag_loss"].sum()),
        "reentry_lag_loss": float(window["reentry_lag_loss"].sum()),
        "scaled_alpha_cost_effect": float(window["scaled_alpha_cost_effect"].sum()),
        "overlay_cost_effect": float(window["overlay_cost_effect"].sum()),
        "de_risk_events": int(window["executed_multiplier"].diff().lt(0).sum()),
        "reentry_events": int(window["executed_multiplier"].diff().gt(0).sum()),
        "top_etf_negative_share": etf_share,
        "top_negative_etf": etf,
        "top_group_negative_share": group_share,
        "top_negative_group": group,
    }
    labels, primary = classify_window(row, cfg)
    row["labels"] = ";".join(labels) if labels else "mixed"
    row["primary_cause"] = primary
    return row


def event_attribution(daily: pd.DataFrame) -> pd.DataFrame:
    decision_change = daily["decision_multiplier"].diff().fillna(0)
    execution_change = daily["executed_multiplier"].diff().fillna(0)
    dates = daily.index[decision_change.ne(0) | execution_change.ne(0)]
    rows = []
    for date in dates:
        location = daily.index.get_loc(date)
        future = daily.iloc[location : location + 5]
        rows.append(
            {
                "date": date,
                "decision_change": float(decision_change.loc[date]),
                "execution_change": float(execution_change.loc[date]),
                "decision_multiplier": float(daily.loc[date, "decision_multiplier"]),
                "executed_multiplier": float(daily.loc[date, "executed_multiplier"]),
                "applied_multiplier": float(daily.loc[date, "applied_multiplier"]),
                "same_day_d1_return": float(daily.loc[date, "d1_return"]),
                "next_five_d1_return": compounded_return(future["d1_return"]),
                "next_five_raw_return": compounded_return(future["raw_p3_return"]),
                "de_risk_lag_loss": float(future["de_risk_lag_loss"].sum()),
                "reentry_lag_loss": float(future["reentry_lag_loss"].sum()),
                "avoided_loss": float(future["avoided_loss"].sum()),
                "missed_rebound": float(future["missed_rebound"].sum()),
            }
        )
    return pd.DataFrame(rows)
