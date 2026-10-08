import pandas as pd

from backtest.d1_hard_drawdown_stop import hard_stop_targets


def test_hard_stop_reuses_five_and_ten_percent_reentry() -> None:
    dates = pd.date_range("2020-01-01", periods=7, freq="D")
    d1 = pd.DataFrame({"nav": [100.0, 91.0, 89.0, 92.0, 94.0, 98.0, 99.0]}, index=dates)
    cfg = {"reentry_half_rebound": 0.05, "reentry_full_rebound": 0.10}
    target, events = hard_stop_targets(d1, -0.10, cfg)

    assert target.tolist() == [1.0, 1.0, 0.0, 0.0, 0.5, 1.0, 1.0]
    assert events["new_multiplier"].tolist() == [0.0, 0.5, 1.0]


def test_control_target_never_overrides_d1() -> None:
    dates = pd.date_range("2020-01-01", periods=2, freq="D")
    d1 = pd.DataFrame({"nav": [100.0, 99.0]}, index=dates)
    target, events = hard_stop_targets(d1, None, {})

    assert target.eq(1.0).all()
    assert events.empty
