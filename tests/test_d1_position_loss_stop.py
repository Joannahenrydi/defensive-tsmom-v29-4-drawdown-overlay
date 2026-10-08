import pandas as pd

from backtest.d1_position_loss_stop import position_stop_plan


def test_stop_locks_only_breached_trade_until_original_exit() -> None:
    dates = pd.date_range("2020-01-01", periods=6, freq="D")
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "symbol": "AAA",
                "group": "equity",
                "shares": 10.0,
                "entry_notional": 1000.0,
                "entry_date": dates[0],
                "exit_date": dates[5],
            },
            {
                "trade_id": 2,
                "symbol": "BBB",
                "group": "rates",
                "shares": 10.0,
                "entry_notional": 1000.0,
                "entry_date": dates[0],
                "exit_date": dates[5],
            },
        ]
    )
    prices = pd.DataFrame(
        {"AAA": [100, 94, 93, 98, 100, 101], "BBB": [100] * 6}, index=dates
    )
    active = pd.DataFrame(
        {1: [True] * 5 + [False], 2: [True] * 5 + [False]}, index=dates
    )
    d1 = pd.Series(1.0, index=dates)

    admitted, events = position_stop_plan(dates, trades, prices, d1, active, -0.05)

    assert events.loc[0, "decision_date"] == dates[1]
    assert events.loc[0, "execution_date"] == dates[2]
    assert admitted[1].tolist() == [1, 1, 0, 0, 0, 0]
    assert admitted[2].tolist() == [1, 1, 1, 1, 1, 0]


def test_stop_requires_positive_d1_exposure() -> None:
    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "symbol": "AAA",
                "group": "equity",
                "shares": 10.0,
                "entry_notional": 1000.0,
                "entry_date": dates[0],
                "exit_date": dates[4],
            }
        ]
    )
    prices = pd.DataFrame({"AAA": [100, 90, 89, 88, 87]}, index=dates)
    active = pd.DataFrame({1: [True, True, True, True, False]}, index=dates)
    d1 = pd.Series([0.0, 0.0, 1.0, 1.0, 1.0], index=dates)

    _, events = position_stop_plan(dates, trades, prices, d1, active, -0.05)

    assert events.loc[0, "decision_date"] == dates[2]
