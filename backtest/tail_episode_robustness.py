"""Materiality-aware classification of frozen tail episodes."""

from __future__ import annotations

import pandas as pd


def classify_tail_episodes(
    episodes: pd.DataFrame,
    material_improvement_threshold: float,
    material_deterioration_threshold: float,
) -> pd.DataFrame:
    """Return episode deltas, normalized improvements and fixed classifications."""
    required = {"d1_return", "candidate_return"}
    missing = required.difference(episodes.columns)
    if missing:
        raise ValueError(f"missing episode columns: {sorted(missing)}")
    if episodes["d1_return"].eq(0).any():
        raise ValueError("D1 episode return cannot be zero")
    result = episodes.copy()
    result["delta"] = result["candidate_return"] - result["d1_return"]
    result["normalized_improvement"] = result["delta"].div(result["d1_return"].abs())
    result["materiality_class"] = "neutral"
    boundary_tolerance = 1e-12
    result.loc[
        result["normalized_improvement"].ge(
            material_improvement_threshold - boundary_tolerance
        ),
        "materiality_class",
    ] = "material_improvement"
    result.loc[
        result["normalized_improvement"].le(
            material_deterioration_threshold + boundary_tolerance
        ),
        "materiality_class",
    ] = "material_deterioration"
    return result


def tail_gate_summary(classified: pd.DataFrame, rules: dict) -> dict:
    """Evaluate the three simultaneous Protocol v2 tail conditions."""
    improvement_count = int(
        classified["materiality_class"].eq("material_improvement").sum()
    )
    deterioration_count = int(
        classified["materiality_class"].eq("material_deterioration").sum()
    )
    aggregate = float(classified["delta"].sum() / classified["d1_return"].abs().sum())
    checks = {
        "breadth": improvement_count >= rules["minimum_material_improvements"],
        "no_material_deterioration": deterioration_count
        <= rules["maximum_material_deteriorations"],
        "aggregate_fixed_tail_improvement": aggregate > 0,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "material_improvement_count": improvement_count,
        "neutral_count": int(classified["materiality_class"].eq("neutral").sum()),
        "material_deterioration_count": deterioration_count,
        "aggregate_fixed_tail_improvement": aggregate,
    }
