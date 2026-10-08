import pandas as pd

from backtest.tail_episode_robustness import (
    classify_tail_episodes,
    tail_gate_summary,
)


def test_materiality_boundaries_are_inclusive() -> None:
    episodes = pd.DataFrame(
        {
            "d1_return": [-0.20, -0.20, -0.20],
            "candidate_return": [-0.19, -0.204, -0.195],
        }
    )
    classified = classify_tail_episodes(episodes, 0.05, -0.02)
    assert classified["materiality_class"].tolist() == [
        "material_improvement",
        "material_deterioration",
        "neutral",
    ]


def test_tail_gate_requires_all_three_conditions() -> None:
    episodes = pd.DataFrame(
        {
            "d1_return": [-0.20, -0.10, -0.08],
            "candidate_return": [-0.18, -0.094, -0.0801],
        }
    )
    rules = {
        "minimum_material_improvements": 2,
        "maximum_material_deteriorations": 0,
    }
    classified = classify_tail_episodes(episodes, 0.05, -0.02)
    summary = tail_gate_summary(classified, rules)
    assert summary["passed"]
    assert summary["material_improvement_count"] == 2
    assert summary["neutral_count"] == 1
    assert summary["material_deterioration_count"] == 0
    assert summary["aggregate_fixed_tail_improvement"] > 0
