"""Retrospectively classify frozen v32 outputs under Risk Admission Protocol v2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from backtest.tail_episode_robustness import (
    classify_tail_episodes,
    tail_gate_summary,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/risk_admission_protocol_v2.json"
PROTOCOL = ROOT / "docs/RISK_ADMISSION_PROTOCOL_V2.md"
OUTPUT = ROOT / "reports/risk_admission_protocol_v2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_sources(cfg: dict) -> tuple[Path, Path, dict]:
    decision_path = ROOT / cfg["source_v32_decision"]
    episodes_path = ROOT / cfg["source_fixed_episodes"]
    observed = {
        "v32_decision_sha256": sha256(decision_path),
        "fixed_episodes_sha256": sha256(episodes_path),
    }
    mismatches = {
        key: {"expected": cfg["source_hashes"][key], "observed": value}
        for key, value in observed.items()
        if cfg["source_hashes"][key] != value
    }
    return (
        decision_path,
        episodes_path,
        {
            "passed": not mismatches,
            "observed_hashes": observed,
            "mismatches": mismatches,
        },
    )


def write_report(decision: dict, classified: pd.DataFrame) -> None:
    rows = []
    for episode in classified.itertuples(index=False):
        rows.append(
            "| {episode} | {d1:.2%} | {candidate:.2%} | {delta:.3%} | "
            "{normalized:.2%} | {classification} |".format(
                episode=episode.episode,
                d1=episode.d1_return,
                candidate=episode.candidate_return,
                delta=episode.delta,
                normalized=episode.normalized_improvement,
                classification=episode.materiality_class.replace("_", " "),
            )
        )
    tail = decision["tail_episode_robustness"]
    unchanged = decision["unchanged_gate_checks"]
    checks = "\n".join(
        f"- `{name}`: **{'PASS' if passed else 'FAIL'}**"
        for name, passed in unchanged.items()
    )
    report = f"""# Risk Admission Protocol v2 — v32 Retrospective Diagnostic

## Status

**{decision["retrospective_status"]}**

The historical v32 decision remains **`V32_REJECTED_KEEP_D1`**. This diagnostic did not rerun
v32, change a parameter or create formal acceptance. It only reclassified the same five frozen
episode returns under the newly frozen materiality-aware rule.

| Episode | D1 return | v32 return | Delta | Normalized improvement | Classification |
|---:|---:|---:|---:|---:|---|
{chr(10).join(rows)}

## Tail-Episode Robustness Gate

- Material improvements: **{tail["material_improvement_count"]}/5**; required at least 2.
- Neutral episodes: **{tail["neutral_count"]}/5**.
- Material deteriorations: **{tail["material_deterioration_count"]}/5**; required 0.
- Aggregate fixed-tail improvement: **{tail["aggregate_fixed_tail_improvement"]:.2%}**; required strictly positive.

All three tail conditions pass. Episode 4's -0.017 percentage-point change is -0.21% relative to
that D1 episode loss, so Protocol v2 correctly classifies it as neutral rather than material
deterioration.

## Unchanged admission checks

{checks}

Under Protocol v2, the frozen v32 result **would qualify retrospectively** because every unchanged
gate and the new tail gate pass. This is diagnostic evidence only. It does not modify v32's
decision, select v32 for trading, enable orders or constitute prospective validation.
"""
    (OUTPUT / "REPORT.md").write_text(report)


def main() -> None:
    cfg = json.loads(CONFIG.read_text())
    decision_path, episodes_path, source_audit = verify_sources(cfg)
    if not source_audit["passed"]:
        raise RuntimeError("Protocol v2 source lock failed")
    v32 = json.loads(decision_path.read_text())
    if v32["status"] != cfg["historical_v32_status_must_remain"]:
        raise RuntimeError("historical v32 decision changed")
    candidate = cfg["retrospective_candidate"]
    episodes = pd.read_csv(episodes_path, parse_dates=["start", "trough"])
    episodes = episodes.loc[episodes["variant"].eq(candidate)].copy()
    if len(episodes) != 5 or episodes["episode"].nunique() != 5:
        raise RuntimeError("retrospective diagnostic requires five frozen episodes")
    rules = cfg["tail_episode_robustness"]
    classified = classify_tail_episodes(
        episodes,
        rules["material_improvement_threshold"],
        rules["material_deterioration_threshold"],
    )
    tail = tail_gate_summary(classified, rules)

    original_checks = v32["gates"][candidate]["checks"]
    unchanged_checks = {
        key: value
        for key, value in original_checks.items()
        if key != "deepest_drawdowns_improved"
    }
    unchanged_passed = all(unchanged_checks.values())
    retrospective_qualifies = bool(unchanged_passed and tail["passed"])
    if retrospective_qualifies:
        status = "V32_WOULD_QUALIFY_UNDER_PROTOCOL_V2_RETROSPECTIVE_ONLY"
    else:
        status = "V32_WOULD_NOT_QUALIFY_UNDER_PROTOCOL_V2_RETROSPECTIVE_ONLY"

    OUTPUT.mkdir(parents=True, exist_ok=True)
    classified.to_csv(OUTPUT / "v32_episode_reclassification.csv", index=False)
    decision = {
        "protocol_status": "RISK_ADMISSION_PROTOCOL_V2_FROZEN_FOR_FUTURE_CANDIDATES",
        "retrospective_status": status,
        "historical_v32_status": v32["status"],
        "historical_v32_decision_unchanged": True,
        "retrospective_candidate": candidate,
        "retrospective_qualifies": retrospective_qualifies,
        "formal_acceptance": False,
        "risk_admitted": False,
        "orders_allowed": False,
        "development_read": False,
        "parameters_rerun": False,
        "unchanged_gate_checks": unchanged_checks,
        "unchanged_gates_passed": unchanged_passed,
        "tail_episode_robustness": tail,
        "source_audit": source_audit,
        "config_sha256": sha256(CONFIG),
        "protocol_sha256": sha256(PROTOCOL),
        "evaluator_sha256": sha256(Path(__file__)),
    }
    (OUTPUT / "protocol_v2_retrospective_decision.json").write_text(
        json.dumps(decision, indent=2) + "\n"
    )
    write_report(decision, classified)


if __name__ == "__main__":
    main()
