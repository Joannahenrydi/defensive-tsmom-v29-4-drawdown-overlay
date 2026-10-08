"""Run the frozen v30 hard-drawdown-stop experiment over v29.4 D1."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backtest.d1_hard_drawdown_stop import performance_metrics, run_hard_stop

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/d1_hard_drawdown_stop_v30.json"
PROTOCOL = ROOT / "docs/D1_HARD_DRAWDOWN_STOP_PROTOCOL_V30.md"
ENGINE = ROOT / "backtest/d1_hard_drawdown_stop.py"
D1_ENGINE = ROOT / "backtest/etf_drawdown_overlay.py"
DEFAULT_OUTPUT = ROOT / "reports/d1_hard_drawdown_stop_v30"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finite(value: object) -> object:
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return None
    return value


def write_frame(frame: pd.DataFrame, path: Path, index: bool = False) -> None:
    if frame.empty:
        frame = pd.DataFrame({"status": ["NO_ROWS"]})
    frame.to_csv(path, index=index)


def markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        values = []
        for value in row:
            if pd.isna(value):
                values.append("")
            elif isinstance(value, (float, np.floating)):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def source_paths(cfg: dict) -> dict[str, Path]:
    return {
        "p3_daily": ROOT / cfg["source_p3_daily"],
        "d1_daily": ROOT / cfg["source_d1_daily"],
        "d1_episodes": ROOT / cfg["source_d1_episodes"],
        "v29_4_decision": ROOT / cfg["source_v29_4_decision"],
        "v29_6_decision": ROOT / cfg["source_v29_6_decision"],
        "d1_engine": D1_ENGINE,
    }


def verify_sources(cfg: dict, paths: dict[str, Path]) -> dict:
    observed = {
        "p3_daily_sha256": sha256(paths["p3_daily"]),
        "d1_daily_sha256": sha256(paths["d1_daily"]),
        "d1_episodes_sha256": sha256(paths["d1_episodes"]),
        "v29_4_decision_sha256": sha256(paths["v29_4_decision"]),
        "v29_6_decision_sha256": sha256(paths["v29_6_decision"]),
        "d1_engine_sha256": sha256(paths["d1_engine"]),
    }
    mismatches = {
        key: {"expected": cfg["source_hashes"][key], "observed": value}
        for key, value in observed.items()
        if cfg["source_hashes"][key] != value
    }
    v29_4 = json.loads(paths["v29_4_decision"].read_text())
    v29_6 = json.loads(paths["v29_6_decision"].read_text())
    passed = bool(
        not mismatches
        and v29_4["status"] == "V29_4_TRAIN_DD_PASS_PROSPECTIVE_REQUIRED"
        and v29_4["frozen_train_winner"] == "D1"
        and v29_6["status"] == "V29_6_REJECTED_KEEP_D1"
        and v29_6["frozen_train_winner"] is None
        and not v29_4["development_read"]
        and not v29_6["development_read"]
    )
    return {
        "passed": passed,
        "observed_hashes": observed,
        "mismatches": mismatches,
    }


def compounded_return(returns: pd.Series) -> float:
    return float((1 + returns).prod() - 1)


def annual_returns(daily: pd.DataFrame, variant: str) -> pd.DataFrame:
    rows = []
    for year, frame in daily.groupby(daily.index.year):
        rows.append(
            {
                "variant": variant,
                "year": int(year),
                "net_return": compounded_return(frame["controlled_return"]),
                "average_exposure": float(frame["controlled_long_exposure"].mean()),
            }
        )
    return pd.DataFrame(rows)


def episode_comparison(
    daily: pd.DataFrame,
    control: pd.DataFrame,
    episodes: pd.DataFrame,
    variant: str,
) -> pd.DataFrame:
    rows = []
    for rank, episode in enumerate(episodes.itertuples(index=False), start=1):
        start, trough = pd.Timestamp(episode.start), pd.Timestamp(episode.trough)
        control_return = compounded_return(
            control.loc[start:trough, "controlled_return"]
        )
        candidate_return = compounded_return(
            daily.loc[start:trough, "controlled_return"]
        )
        rows.append(
            {
                "variant": variant,
                "episode": rank,
                "start": start,
                "trough": trough,
                "d1_return": control_return,
                "candidate_return": candidate_return,
                "improvement": candidate_return - control_return,
                "improved": candidate_return > control_return + 1e-12,
            }
        )
    return pd.DataFrame(rows)


def gate_candidate(
    row: dict,
    control: dict,
    annual: pd.DataFrame,
    episodes: pd.DataFrame,
    cfg: dict,
) -> tuple[bool, dict]:
    rules = cfg["admission"]
    pivot = annual.pivot(index="year", columns="variant", values="net_return")
    difference = pivot[row["variant"]] - pivot["D1_CONTROL"]
    materially_worse = int(
        difference.drop(index=2011, errors="ignore")
        .lt(rules["material_annual_underperformance"])
        .sum()
    )
    checks = {
        "raw_p3_cagr_retention": row["raw_p3_cagr_retention"]
        >= rules["minimum_raw_p3_cagr_retention"],
        "maximum_drawdown_better_than_d1": row["maximum_drawdown"]
        > control["maximum_drawdown"],
        "calmar_better_than_d1": row["calmar"] > control["calmar"],
        "worst_month_better_than_d1": row["worst_month"] > control["worst_month"],
        "cost_within_limit": row["total_cost"]
        <= control["total_cost"] * rules["maximum_cost_multiple_of_d1"],
        "turnover_within_limit": row["annual_total_turnover"]
        <= control["annual_total_turnover"] * rules["maximum_turnover_multiple_of_d1"],
        "deepest_drawdowns_improved": int(episodes["improved"].sum())
        >= rules["minimum_improved_deepest_drawdowns"],
        "non_2011_years_not_broadly_worse": materially_worse
        <= rules["maximum_non_2011_materially_worse_years"],
    }
    diagnostics = {
        "materially_worse_non_2011_years": materially_worse,
        "improved_deepest_drawdowns": int(episodes["improved"].sum()),
    }
    return all(checks.values()), {"checks": checks, "diagnostics": diagnostics}


def write_report(output: Path, decision: dict, matrix: pd.DataFrame) -> None:
    columns = [
        "variant",
        "stop_drawdown",
        "eligible",
        "net_cagr",
        "sharpe",
        "maximum_drawdown",
        "calmar",
        "worst_month",
        "raw_p3_cagr_retention",
        "average_exposure",
        "annual_total_turnover",
        "total_cost",
        "improved_deepest_drawdowns",
        "materially_worse_non_2011_years",
    ]
    winner = decision["frozen_train_winner"] or "keep v29.4 D1"
    report = f"""# v30 D1 Hard Drawdown Stop

## Decision

**{decision["status"]}**

P3, the complete D1 controller and D1's 5%/10% re-entry eligibility remained frozen. Five
pre-registered stops observed immutable D1 drawdown and overrode D1 exposure only after a
one-session execution delay. No concentration control, development/OOS data or orders entered
the experiment.

{markdown_table(matrix.loc[:, columns])}

Selected result: **{winner}**. A candidate had to retain at least 90% of raw P3 CAGR, improve D1
maximum drawdown, Calmar and worst month, remain within cost/turnover limits, improve at least
three fixed drawdown windows and avoid broad non-2011 deterioration. Among fully eligible
candidates, the least severe maximum drawdown wins.

The control reproduced D1 with maximum daily return error
{decision["audit"]["control_maximum_daily_return_error"]:.3e}. The report directory contains
daily paths, stop decisions, execution events, annual returns, fixed-episode comparisons, all
gate results and source hashes.
"""
    (output / "REPORT.md").write_text(report)


def main(config: Path = CONFIG, output: Path = DEFAULT_OUTPUT) -> None:
    cfg = json.loads(config.read_text())
    paths = source_paths(cfg)
    source_audit = verify_sources(cfg, paths)
    if not source_audit["passed"]:
        raise RuntimeError("v30 source lock failed")

    raw = pd.read_csv(paths["p3_daily"], parse_dates=["date"]).set_index("date")
    d1 = pd.read_csv(paths["d1_daily"], parse_dates=["date"]).set_index("date")
    episodes = pd.read_csv(
        paths["d1_episodes"], parse_dates=["start", "trough", "recovery"]
    ).head(5)
    if not raw.index.equals(d1.index):
        raise RuntimeError("P3 and D1 daily indices do not match")
    if raw.index.min() < pd.Timestamp(cfg["train_start"]):
        raise RuntimeError("v30 source begins before frozen train")
    if raw.index.max() > pd.Timestamp(cfg["train_end"]):
        raise RuntimeError("development data entered v30")
    if not raw.index.is_monotonic_increasing or raw.index.has_duplicates:
        raise RuntimeError("v30 source dates are not unique and ordered")

    output.mkdir(parents=True, exist_ok=True)
    v29_4 = json.loads(paths["v29_4_decision"].read_text())
    raw_p3_cagr = float(v29_4["raw_p3"]["cagr"])
    d1_cagr = float(v29_4["variants"]["D1"]["net_cagr"])
    results = {}
    rows = []
    annual_frames = []
    stop_events = {}
    for variant, spec in cfg["variants"].items():
        result = run_hard_stop(raw, d1, spec["stop_drawdown"], cfg)
        daily = result["daily"]
        results[variant] = daily
        stop_events[variant] = result["stop_decision_events"]
        metrics = performance_metrics(daily, raw_p3_cagr, d1_cagr)
        rows.append(
            {
                "variant": variant,
                "stop_drawdown": spec["stop_drawdown"],
                **metrics,
            }
        )
        annual_frames.append(annual_returns(daily, variant))
        write_frame(daily.reset_index(), output / f"variant_{variant}_daily.csv")
        write_frame(
            result["stop_decision_events"],
            output / f"variant_{variant}_stop_decision_events.csv",
        )
        write_frame(
            result["execution_events"],
            output / f"variant_{variant}_execution_events.csv",
        )

    control = results["D1_CONTROL"]
    control_return_error = float(
        (control["controlled_return"] - d1["controlled_return"]).abs().max()
    )
    control_nav_error = float((control["nav"] - d1["nav"]).abs().max())
    control_multiplier_error = float(
        (control["executed_multiplier"] - d1["executed_multiplier"]).abs().max()
    )
    if control_return_error >= 1e-12 or control_multiplier_error >= 1e-12:
        raise RuntimeError("v30 D1 control replication failed")
    if control_nav_error >= 1e-6:
        raise RuntimeError("v30 D1 control NAV replication failed")

    matrix = pd.DataFrame(rows)
    annual = pd.concat(annual_frames, ignore_index=True)
    episode_frames = [
        episode_comparison(daily, control, episodes, variant)
        for variant, daily in results.items()
    ]
    episode_table = pd.concat(episode_frames, ignore_index=True)
    control_metrics = matrix.loc[matrix["variant"].eq("D1_CONTROL")].iloc[0].to_dict()
    matrix["improved_deepest_drawdowns"] = 0
    matrix["eligible"] = False
    matrix["materially_worse_non_2011_years"] = 0
    gate_details = {}
    for index, row in matrix.iterrows():
        variant = row["variant"]
        variant_episodes = episode_table.loc[episode_table["variant"].eq(variant)]
        improved = int(variant_episodes["improved"].sum())
        matrix.loc[index, "improved_deepest_drawdowns"] = improved
        if variant == "D1_CONTROL":
            continue
        candidate = row.to_dict()
        candidate["improved_deepest_drawdowns"] = improved
        passed, detail = gate_candidate(
            candidate, control_metrics, annual, variant_episodes, cfg
        )
        matrix.loc[index, "eligible"] = passed
        matrix.loc[index, "materially_worse_non_2011_years"] = detail["diagnostics"][
            "materially_worse_non_2011_years"
        ]
        gate_details[variant] = detail

    matrix.to_csv(output / "performance_matrix.csv", index=False)
    annual.to_csv(output / "annual_returns.csv", index=False)
    episode_table.to_csv(output / "deepest_drawdown_comparison.csv", index=False)

    qualified = matrix.loc[matrix["eligible"]].copy()
    if qualified.empty:
        winner = None
        status = "V30_REJECTED_KEEP_D1"
    else:
        order = {
            name: rank for rank, name in enumerate(cfg["admission"]["selection_order"])
        }
        qualified["tie_order"] = qualified["variant"].map(order)
        winner = qualified.sort_values(
            [cfg["admission"]["selection_metric"], "tie_order"],
            ascending=[False, True],
        ).iloc[0]["variant"]
        status = "V30_HARD_STOP_PASS_PROSPECTIVE_REQUIRED"

    audit = {
        **source_audit,
        "control_maximum_daily_return_error": control_return_error,
        "control_maximum_nav_error": control_nav_error,
        "control_maximum_multiplier_error": control_multiplier_error,
        "train_last_date": str(raw.index.max().date()),
        "development_read": False,
        "passed": True,
    }
    decision = {
        "status": status,
        "frozen_train_winner": winner,
        "fallback": "v29.4 D1" if winner is None else None,
        "source_version": cfg["source_version"],
        "source_winner": cfg["source_winner"],
        "development_read": False,
        "orders_allowed": False,
        "risk_admitted": False,
        "prospective_validation_required": winner is not None,
        "protocol_sha256": sha256(PROTOCOL),
        "config_sha256": sha256(config),
        "engine_sha256": sha256(ENGINE),
        "evaluator_sha256": sha256(Path(__file__)),
        "minimum_cagr": raw_p3_cagr * cfg["admission"]["minimum_raw_p3_cagr_retention"],
        "variants": {
            row["variant"]: {key: finite(value) for key, value in row.items()}
            for row in matrix.to_dict("records")
        },
        "gates": gate_details,
        "audit": audit,
    }
    (output / "RUN_AUDIT.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "v30_decision.json").write_text(json.dumps(decision, indent=2) + "\n")
    write_report(output, decision, matrix)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    main(arguments.config, arguments.output)
