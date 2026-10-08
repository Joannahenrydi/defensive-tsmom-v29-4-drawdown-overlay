import numpy as np
import pandas as pd

from backtest.d1_hybrid_position_stop import calibrate_entry_thresholds


def test_hybrid_calibration_maps_median_sigma_to_midpoint() -> None:
    dates = pd.date_range("2020-01-01", periods=30, freq="D")
    prices = pd.DataFrame(
        {
            "AAA": 100 * np.cumprod(1 + np.tile([0.01, -0.005], 15)),
            "BBB": 100 * np.cumprod(1 + np.tile([0.02, -0.01], 15)),
            "CCC": 100 * np.cumprod(1 + np.tile([0.03, -0.015], 15)),
        },
        index=dates,
    )
    trades = pd.DataFrame(
        [
            {"trade_id": 1, "symbol": "AAA", "group": "x", "entry_date": dates[25]},
            {"trade_id": 2, "symbol": "BBB", "group": "x", "entry_date": dates[25]},
            {"trade_id": 3, "symbol": "CCC", "group": "x", "entry_date": dates[25]},
        ]
    )
    cfg = {
        "volatility_window": 20,
        "volatility_annualization": 252,
        "median_target_loss": 0.1375,
        "minimum_loss_rail": 0.125,
        "maximum_loss_rail": 0.15,
    }

    calibration, diagnostics = calibrate_entry_thresholds(trades, prices, cfg)

    assert np.isclose(calibration.loc[1, "allowed_loss"], 0.1375)
    assert np.isclose(diagnostics["median_allowed_loss"], 0.1375)
    assert calibration["allowed_loss"].between(0.125, 0.15).all()


def test_hybrid_calibration_applies_both_static_rails() -> None:
    dates = pd.date_range("2020-01-01", periods=30, freq="D")
    prices = pd.DataFrame(
        {
            "LOW": 100 * np.cumprod(1 + np.tile([0.001, -0.0005], 15)),
            "MID": 100 * np.cumprod(1 + np.tile([0.01, -0.005], 15)),
            "HIGH": 100 * np.cumprod(1 + np.tile([0.10, -0.05], 15)),
        },
        index=dates,
    )
    trades = pd.DataFrame(
        [
            {"trade_id": 1, "symbol": "LOW", "group": "x", "entry_date": dates[25]},
            {"trade_id": 2, "symbol": "MID", "group": "x", "entry_date": dates[25]},
            {"trade_id": 3, "symbol": "HIGH", "group": "x", "entry_date": dates[25]},
        ]
    )
    cfg = {
        "volatility_window": 20,
        "volatility_annualization": 252,
        "median_target_loss": 0.1375,
        "minimum_loss_rail": 0.125,
        "maximum_loss_rail": 0.15,
    }

    calibration, _ = calibrate_entry_thresholds(trades, prices, cfg)

    assert calibration.loc[0, "allowed_loss"] == 0.125
    assert calibration.loc[2, "allowed_loss"] == 0.15
