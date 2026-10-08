import numpy as np
import pandas as pd

from backtest.etf_concentration_control import (
    connected_components,
    reconstruct_symbol_weights,
    sleeve_cap_scales,
)


def test_reconstruct_symbol_weights_matches_entry_and_exit_timing() -> None:
    dates = pd.date_range("2020-01-01", periods=4, freq="B")
    raw = pd.DataFrame(
        {
            "nav": [100.0, 110.0, 105.0, 105.0],
            "long_exposure": [0.0, 1.0, 0.0, 0.0],
        },
        index=dates,
    )
    trades = pd.DataFrame(
        {
            "trade_id": [1],
            "symbol": ["SPY"],
            "group": ["us_equity"],
            "entry_notional": [110.0],
            "entry_date": [dates[1]],
            "exit_date": [dates[2]],
        }
    )
    ledger = pd.DataFrame(
        {
            "date": [dates[1], dates[2]],
            "trade_id": [1, 1],
            "gross_pnl": [0.0, -5.0],
            "cost": [0.0, 0.0],
        }
    )
    weights, groups, error = reconstruct_symbol_weights(raw, trades, ledger)
    assert groups == {"SPY": "us_equity"}
    assert weights["SPY"].tolist() == [0.0, 1.0, 0.0, 0.0]
    assert error == 0.0


def test_connected_components_groups_transitive_correlations() -> None:
    correlation = pd.DataFrame(
        [[1.0, 0.8, 0.1], [0.8, 1.0, 0.75], [0.1, 0.75, 1.0]],
        index=["A", "B", "C"],
        columns=["A", "B", "C"],
    )
    assert connected_components(correlation, 0.70) == [["A", "B", "C"]]


def test_sleeve_cap_scales_only_binding_group() -> None:
    date = pd.Timestamp("2020-01-01")
    weights = pd.DataFrame({"SPY": [0.3], "XLF": [0.3], "GLD": [0.2]}, index=[date])
    executed = pd.Series([1.0], index=[date])
    scales, audit = sleeve_cap_scales(
        weights,
        executed,
        {"SPY": "us_equity", "XLF": "us_equity", "GLD": "metals"},
        0.4,
    )
    np.testing.assert_allclose(scales.loc[date, ["SPY", "XLF"]], 2 / 3)
    assert scales.loc[date, "GLD"] == 1.0
    us = audit.loc[audit["group"].eq("us_equity")].iloc[0]
    assert np.isclose(us["post_cap_exposure"], 0.4)
