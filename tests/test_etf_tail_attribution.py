import numpy as np
import pandas as pd

from backtest.etf_tail_attribution import (
    classify_window,
    daily_return_attribution,
    ledger_return_attribution,
)


def test_daily_attribution_reconciles_exposure_and_cost_effects() -> None:
    index = pd.date_range("2020-01-01", periods=3, freq="B")
    raw = pd.DataFrame(
        {
            "nav": [100000.0, 98000.0, 98980.0],
            "net_return": [0.0, -0.02, 0.01],
            "gross_return": [0.0, -0.02, 0.01],
            "cost": [0.0, 0.0, 0.0],
        },
        index=index,
    )
    d1 = pd.DataFrame(
        {
            "nav": [100000.0, 98000.0, 98490.0],
            "controlled_return": [0.0, -0.02, 0.005],
            "decision_multiplier": [1.0, 0.5, 0.5],
            "executed_multiplier": [1.0, 1.0, 0.5],
            "applied_return_multiplier": [1.0, 1.0, 0.5],
            "overlay_cost": [0.0, 0.0, 0.0],
        },
        index=index,
    )
    result = daily_return_attribution(d1, raw)
    np.testing.assert_allclose(result["reconciliation_error"], 0.0, atol=1e-15)
    assert result["missed_rebound"].iloc[-1] == -0.005


def test_ledger_attribution_maps_trade_to_symbol_and_group() -> None:
    index = pd.date_range("2020-01-01", periods=2, freq="B")
    raw = pd.DataFrame({"nav": [100000.0, 101000.0]}, index=index)
    d1 = pd.DataFrame(
        {
            "applied_return_multiplier": [1.0, 0.5],
            "executed_multiplier": [1.0, 0.5],
        },
        index=index,
    )
    ledger = pd.DataFrame(
        {"date": [index[1]], "trade_id": [7], "gross_pnl": [1000.0], "cost": [10.0]}
    )
    trades = pd.DataFrame({"trade_id": [7], "symbol": ["SPY"], "group": ["us_equity"]})
    result = ledger_return_attribution(ledger, trades, d1, raw)
    assert result.loc[0, "symbol"] == "SPY"
    assert result.loc[0, "net_contribution"] == 0.00495


def test_classification_prioritizes_missed_rebound() -> None:
    cfg = {
        "attribution": {
            "sudden_crash_one_day": -0.04,
            "sudden_crash_five_day": -0.08,
            "slow_drawdown_minimum_sessions": 20,
            "material_lag_loss": -0.01,
            "material_lag_share": 0.20,
            "material_missed_rebound": -0.01,
            "concentration_share": 0.50,
        }
    }
    row = {
        "worst_day": -0.05,
        "worst_five_day": -0.09,
        "sessions_to_trough": 22,
        "d1_return": -0.10,
        "de_risk_lag_loss": -0.03,
        "missed_rebound": -0.04,
        "avoided_loss": 0.02,
        "top_etf_negative_share": 0.30,
        "top_group_negative_share": 0.40,
    }
    labels, primary = classify_window(row, cfg)
    assert "missed_rebound" in labels
    assert "signal_lag" in labels
    assert primary == "missed_rebound"
