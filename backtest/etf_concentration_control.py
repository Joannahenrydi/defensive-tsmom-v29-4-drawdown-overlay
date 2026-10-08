"""Causal concentration controls for the frozen v29.6 P3 + D1 experiment."""

from __future__ import annotations

import numpy as np
import pandas as pd


def reconstruct_symbol_weights(
    raw: pd.DataFrame, trades: pd.DataFrame, ledger: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, str], float]:
    """Rebuild end-of-day P3 holdings from immutable trade and PnL records."""
    dates = raw.index
    symbols = sorted(trades["symbol"].unique())
    values = pd.DataFrame(0.0, index=dates, columns=symbols)
    symbol_groups = (
        trades[["symbol", "group"]].drop_duplicates().set_index("symbol")["group"]
    )
    if symbol_groups.index.has_duplicates:
        raise ValueError("a traded symbol maps to more than one economic group")
    gross_by_trade = ledger.pivot_table(
        index="date",
        columns="trade_id",
        values="gross_pnl",
        aggfunc="sum",
        fill_value=0.0,
    ).reindex(dates, fill_value=0.0)
    for trade in trades.itertuples(index=False):
        gross = (
            gross_by_trade[trade.trade_id]
            if trade.trade_id in gross_by_trade
            else pd.Series(0.0, index=dates)
        )
        marked_value = float(trade.entry_notional) + gross.cumsum()
        active = dates.to_series().between(
            pd.Timestamp(trade.entry_date),
            pd.Timestamp(trade.exit_date),
            inclusive="left",
        )
        values.loc[active.to_numpy(), trade.symbol] += marked_value.loc[
            active.to_numpy()
        ].to_numpy()
    weights = values.div(raw["nav"], axis=0)
    error = float((weights.sum(axis=1) - raw["long_exposure"]).abs().max())
    return weights, symbol_groups.to_dict(), error


def symbol_return_contributions(
    raw: pd.DataFrame, trades: pd.DataFrame, ledger: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, float, float]:
    mapping = trades[["trade_id", "symbol"]].drop_duplicates("trade_id")
    frame = ledger.merge(mapping, on="trade_id", how="left", validate="many_to_one")
    if frame["symbol"].isna().any():
        raise ValueError("unmapped ledger trade")
    prior_nav = raw["nav"].shift(1).fillna(raw["nav"].iloc[0])
    gross = frame.pivot_table(
        index="date",
        columns="symbol",
        values="gross_pnl",
        aggfunc="sum",
        fill_value=0.0,
    ).reindex(raw.index, fill_value=0.0)
    cost = frame.pivot_table(
        index="date", columns="symbol", values="cost", aggfunc="sum", fill_value=0.0
    ).reindex(raw.index, fill_value=0.0)
    gross = gross.div(prior_nav, axis=0)
    cost = cost.div(prior_nav, axis=0)
    gross_error = float((gross.sum(axis=1) - raw["gross_return"]).abs().max())
    raw_cost_return = raw["cost"].div(prior_nav)
    cost_error = float((cost.sum(axis=1) - raw_cost_return).abs().max())
    return gross, cost, gross_error, cost_error


def connected_components(
    correlation: pd.DataFrame, threshold: float
) -> list[list[str]]:
    remaining = set(correlation.columns)
    output = []
    while remaining:
        root = min(remaining)
        stack = [root]
        component = []
        remaining.remove(root)
        while stack:
            symbol = stack.pop()
            component.append(symbol)
            neighbors = {
                other
                for other in remaining
                if np.isfinite(correlation.loc[symbol, other])
                and correlation.loc[symbol, other] >= threshold
            }
            remaining.difference_update(neighbors)
            stack.extend(sorted(neighbors, reverse=True))
        output.append(sorted(component))
    return output


def sleeve_cap_scales(
    weights: pd.DataFrame,
    executed_d1: pd.Series,
    groups: dict[str, str],
    cap: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scales = pd.DataFrame(1.0, index=weights.index, columns=weights.columns)
    rows = []
    for date in weights.index:
        desired = weights.loc[date] * executed_d1.loc[date]
        for group in sorted(set(groups.values())):
            members = [symbol for symbol in weights.columns if groups[symbol] == group]
            exposure = float(desired.loc[members].sum())
            scale = min(1.0, cap / exposure) if exposure > 0 else 1.0
            scales.loc[date, members] = scale
            rows.append(
                {
                    "date": date,
                    "group": group,
                    "pre_cap_exposure": exposure,
                    "scale": scale,
                    "post_cap_exposure": exposure * scale,
                    "binding": scale < 1.0,
                }
            )
    return scales, pd.DataFrame(rows)


def cluster_risk_scales(
    weights: pd.DataFrame,
    executed_d1: pd.Series,
    market_returns: pd.DataFrame,
    spec: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scales = pd.DataFrame(1.0, index=weights.index, columns=weights.columns)
    rows = []
    for date in weights.index:
        desired = weights.loc[date] * executed_d1.loc[date]
        active = desired.index[desired.gt(1e-12)].tolist()
        if not active:
            continue
        history = market_returns.loc[:date, active].tail(spec["correlation_window"])
        history = history.dropna(how="any")
        if len(history) < spec["minimum_observations"]:
            continue
        covariance = history.cov()
        correlation = history.corr()
        annual_volatility = np.sqrt(np.diag(covariance) * 252)
        positive_volatility = annual_volatility[annual_volatility > 1e-12]
        if not len(positive_volatility):
            continue
        reference_volatility = float(np.median(positive_volatility))
        components = connected_components(correlation, spec["correlation_threshold"])
        for cluster_id, members in enumerate(components):
            cluster_weights = desired.loc[members].to_numpy(dtype=float)
            cluster_covariance = covariance.loc[members, members].to_numpy(dtype=float)
            variance = float(cluster_weights @ cluster_covariance @ cluster_weights)
            standalone_volatility = np.sqrt(max(variance, 0.0) * 252)
            normalized_risk = standalone_volatility / reference_volatility
            scale = (
                min(1.0, spec["maximum_normalized_cluster_risk"] / normalized_risk)
                if normalized_risk > 1e-12
                else 1.0
            )
            scales.loc[date, members] = scale
            rows.append(
                {
                    "date": date,
                    "cluster_id": cluster_id,
                    "members": ";".join(members),
                    "member_count": len(members),
                    "pre_cap_exposure": float(desired.loc[members].sum()),
                    "normalized_cluster_risk": normalized_risk,
                    "scale": scale,
                    "post_cap_exposure": float(desired.loc[members].sum() * scale),
                    "binding": scale < 1.0,
                }
            )
    return scales, pd.DataFrame(rows)


def run_concentration_variant(
    raw: pd.DataFrame,
    d1: pd.DataFrame,
    weights: pd.DataFrame,
    gross_contribution: pd.DataFrame,
    cost_contribution: pd.DataFrame,
    scales: pd.DataFrame,
    cfg: dict,
    variant: str,
) -> pd.DataFrame:
    symbols = weights.columns
    gross_contribution = gross_contribution.reindex(columns=symbols, fill_value=0.0)
    cost_contribution = cost_contribution.reindex(columns=symbols, fill_value=0.0)
    executed_d1 = d1["executed_multiplier"]
    combined = scales.mul(executed_d1, axis=0)
    applied = combined.shift(1).fillna(1.0)
    gross_return = applied.mul(gross_contribution).sum(axis=1)
    if variant == "C0":
        cost_multiplier = combined
    else:
        cost_multiplier = combined.where(weights.gt(0), applied)
    alpha_cost_return = cost_multiplier.mul(cost_contribution).sum(axis=1)

    capped_raw_exposure = scales.mul(weights).sum(axis=1)
    d1_turnover = executed_d1.diff().abs().fillna(0.0) * capped_raw_exposure
    continuing = weights.gt(0) & weights.shift(1).fillna(0.0).gt(0)
    concentration_turnover = (
        scales.diff()
        .abs()
        .fillna(0.0)
        .mul(weights)
        .mul(executed_d1, axis=0)
        .where(continuing, 0.0)
        .sum(axis=1)
    )
    overlay_turnover = d1_turnover + concentration_turnover
    overlay_cost_return = overlay_turnover * cfg["transaction_cost_one_way"]
    controlled_return = gross_return - alpha_cost_return - overlay_cost_return
    nav = cfg["initial_nav"] * (1 + controlled_return).cumprod()
    prior_nav = nav.shift(1).fillna(cfg["initial_nav"])
    exposure = combined.mul(weights).sum(axis=1)
    return pd.DataFrame(
        {
            "raw_p3_return": raw["net_return"],
            "d1_return": d1["controlled_return"],
            "controlled_return": controlled_return,
            "nav": nav,
            "long_exposure": exposure,
            "cash_exposure": 1 - exposure,
            "gross_return": gross_return,
            "alpha_cost": alpha_cost_return * prior_nav,
            "d1_overlay_turnover": d1_turnover,
            "concentration_turnover": concentration_turnover,
            "overlay_turnover": overlay_turnover,
            "overlay_cost": overlay_cost_return * prior_nav,
            "total_cost": (alpha_cost_return + overlay_cost_return) * prior_nav,
        },
        index=raw.index,
    )


def performance_metrics(
    daily: pd.DataFrame,
    raw_p3_cagr: float,
    d1_cagr: float,
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
        "average_exposure": float(daily["long_exposure"].mean()),
        "alpha_cost": float(daily["alpha_cost"].sum()),
        "overlay_cost": float(daily["overlay_cost"].sum()),
        "total_cost": float(daily["total_cost"].sum()),
        "annual_alpha_turnover": float(
            daily["alpha_cost"].div(daily["nav"].shift(1).fillna(100000.0)).sum()
            / 0.001
            / years
        ),
        "annual_overlay_turnover": float(daily["overlay_turnover"].sum() / years),
        "annual_total_turnover": float(
            daily["alpha_cost"].div(daily["nav"].shift(1).fillna(100000.0)).sum()
            / 0.001
            / years
            + daily["overlay_turnover"].sum() / years
        ),
        "raw_p3_cagr_retention": float(cagr / raw_p3_cagr),
        "d1_cagr_retention": float(cagr / d1_cagr),
    }
