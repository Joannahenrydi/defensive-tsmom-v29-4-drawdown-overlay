import numpy as np
import pandas as pd

from backtest.etf_drawdown_overlay import (
    decision_targets,
    hard_kill_targets,
    progressive_multiplier,
    run_overlay,
)


def config() -> dict:
    return {
        "initial_nav": 100000.0,
        "decision_delay_sessions": 1,
        "transaction_cost_one_way": 0.001,
        "variants": {
            "D0": {"type": "control"},
            "D1": {
                "type": "hard_kill",
                "kill_drawdown": -0.20,
                "reentry_half_rebound": 0.05,
                "reentry_full_rebound": 0.10,
            },
            "D2": {
                "type": "progressive",
                "tiers": [
                    {"minimum_drawdown": -0.10, "multiplier": 1.0},
                    {"minimum_drawdown": -0.15, "multiplier": 0.75},
                    {"minimum_drawdown": -0.20, "multiplier": 0.50},
                    {"minimum_drawdown": -0.25, "multiplier": 0.25},
                    {"minimum_drawdown": -1.00, "multiplier": 0.00},
                ],
            },
            "D3": {"type": "smooth", "zero_exposure_drawdown": -0.25},
        },
    }


def raw_frame(returns: list[float]) -> pd.DataFrame:
    index = pd.date_range("2020-01-01", periods=len(returns), freq="B")
    returns_series = pd.Series(returns, index=index)
    nav = 100000 * (1 + returns_series).cumprod()
    return pd.DataFrame(
        {
            "nav": nav,
            "net_return": returns_series,
            "gross_return": returns_series,
            "cost": 0.0,
            "turnover": 0.0,
            "long_exposure": 1.0,
        }
    )


def test_d0_exactly_reproduces_raw_stream_without_costs() -> None:
    raw = raw_frame([0.0, 0.01, -0.02, 0.03])
    daily = run_overlay(raw, "D0", config())["daily"]
    np.testing.assert_allclose(
        daily["controlled_return"], raw["net_return"], atol=1e-15
    )
    np.testing.assert_allclose(daily["nav"], raw["nav"], atol=1e-10)
    assert daily["executed_multiplier"].eq(1).all()


def test_progressive_tier_boundaries_are_frozen() -> None:
    tiers = config()["variants"]["D2"]["tiers"]
    assert progressive_multiplier(-0.099, tiers) == 1.0
    assert progressive_multiplier(-0.10, tiers) == 0.75
    assert progressive_multiplier(-0.15, tiers) == 0.50
    assert progressive_multiplier(-0.20, tiers) == 0.25
    assert progressive_multiplier(-0.25, tiers) == 0.0


def test_smooth_target_uses_shadow_drawdown() -> None:
    raw = raw_frame([0.0, -0.10, -1 / 9, -0.0625])
    targets, _ = decision_targets(raw, "D3", config())
    np.testing.assert_allclose(targets.to_numpy(), [1.0, 0.6, 0.2, 0.0], atol=1e-12)


def test_decision_execution_and_return_application_are_causally_lagged() -> None:
    raw = raw_frame([0.0, -0.20, 0.10, 0.10, 0.10])
    daily = run_overlay(raw, "D3", config())["daily"]
    assert daily["decision_multiplier"].iloc[1] < 1.0
    assert daily["executed_multiplier"].iloc[1] == 1.0
    assert daily["executed_multiplier"].iloc[2] == daily["decision_multiplier"].iloc[1]
    assert daily["applied_return_multiplier"].iloc[2] == 1.0
    assert (
        daily["applied_return_multiplier"].iloc[3]
        == daily["decision_multiplier"].iloc[1]
    )


def test_hard_kill_reenters_from_post_kill_trough() -> None:
    index = pd.date_range("2020-01-01", periods=6, freq="B")
    nav = pd.Series([100.0, 79.0, 75.0, 79.0, 82.6, 83.0], index=index)
    drawdown = nav.div(nav.cummax()).sub(1)
    targets, events = hard_kill_targets(nav, drawdown, config()["variants"]["D1"])
    assert targets.tolist() == [1.0, 0.0, 0.0, 0.5, 1.0, 1.0]
    assert events["event"].tolist() == ["de_risk", "re_entry", "re_entry"]
