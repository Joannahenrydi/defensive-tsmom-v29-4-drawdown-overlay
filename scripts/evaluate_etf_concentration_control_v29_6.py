"""Run the frozen v29.6 concentration-aware allocation experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backtest.etf_concentration_control import (
    cluster_risk_scales,
    performance_metrics,
    reconstruct_symbol_weights,
    run_concentration_variant,
    sleeve_cap_scales,
    symbol_return_contributions,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/etf_concentration_control_v29_6.json"
PROTOCOL = ROOT / "docs/ETF_CONCENTRATION_CONTROL_PROTOCOL_V29_6.md"
ENGINE = ROOT / "backtest/etf_concentration_control.py"
DEFAULT_OUTPUT = ROOT / "reports/etf_concentration_control_v29_6"


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


def paths(cfg: dict) -> dict[str, Path]:
    keys = [
        "source_d1_daily",
        "source_d1_episodes",
        "source_v29_4_decision",
        "source_v29_5_decision",
        "source_p3_daily",
        "source_p3_ledger",
        "source_p3_trades",
        "source_market",
    ]
    return {key: ROOT / cfg[key] for key in keys}


def verify_sources(cfg: dict, source: dict[str, Path]) -> dict:
    observed = {
        "v29_4_decision_sha256": sha256(source["source_v29_4_decision"]),
        "v29_5_decision_sha256": sha256(source["source_v29_5_decision"]),
        "d1_daily_sha256": sha256(source["source_d1_daily"]),
        "p3_ledger_sha256": sha256(source["source_p3_ledger"]),
        "p3_trades_sha256": sha256(source["source_p3_trades"]),
        "market_sha256": sha256(source["source_market"]),
    }
    mismatches = {
        key: {"expected": cfg["source_hashes"][key], "observed": value}
        for key, value in observed.items()
        if cfg["source_hashes"][key] != value
    }
    v29_4 = json.loads(source["source_v29_4_decision"].read_text())
    v29_5 = json.loads(source["source_v29_5_decision"].read_text())
    passed = bool(
        not mismatches
        and v29_4["frozen_train_winner"] == "D1"
        and v29_4["status"] == "V29_4_TRAIN_DD_PASS_PROSPECTIVE_REQUIRED"
        and v29_5["status"] == "V29_5_TARGETED_PROTECTION_REJECTED_KEEP_D1"
        and not v29_4["development_read"]
        and not v29_5["development_read"]
    )
    return {
        "passed": passed,
        "observed_hashes": observed,
        "mismatches": mismatches,
    }


def load_market_returns(path: Path, end: pd.Timestamp) -> pd.DataFrame:
    market = pd.read_csv(
        path, usecols=["symbol", "date", "adj_close"], parse_dates=["date"]
    )
    if market["date"].max() > end:
        raise RuntimeError("post-train market observations entered v29.6")
    prices = market.pivot(
        index="date", columns="symbol", values="adj_close"
    ).sort_index()
    return prices.pct_change(fill_method=None)


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
                "average_exposure": float(frame["long_exposure"].mean()),
            }
        )
    return pd.DataFrame(rows)


def episode_comparison(
    daily: pd.DataFrame, control: pd.DataFrame, episodes: pd.DataFrame, variant: str
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
    difference = pivot[row["variant"]] - pivot["C0"]
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
    report = f"""# v29.6 Concentration-Aware Long Risk Allocation

## Decision

**{decision["status"]}**

P3 alpha, D1 timing and D1 re-entry remained frozen. C1 capped economic-sleeve exposure at 40%;
C2 capped causal 120-session correlation-cluster risk at 35% of median-ETF volatility-equivalent
capital. Every removed dollar remained cash. No short, replacement asset, crash rule, options
hedge, development data or OOS data entered the run.

{markdown_table(matrix.loc[:, columns])}

Selected result: **{decision["frozen_train_winner"] or "keep v29.4 D1"}**. A candidate had to
retain at least 90% of raw P3 CAGR, improve D1 maximum drawdown, Calmar and worst month, remain
within cost/turnover limits, improve at least three of D1's five deepest windows and avoid broad
non-2011 deterioration.

C0 reproduced D1 with maximum daily return error
{decision["audit"]["c0_maximum_daily_return_error"]:.3e}. The report directory contains daily
paths, annual returns, fixed-episode comparisons, sleeve/cluster cap audits and source hashes.
"""
    (output / "REPORT.md").write_text(report)


def main(config: Path = CONFIG, output: Path = DEFAULT_OUTPUT) -> None:
    cfg = json.loads(config.read_text())
    source = paths(cfg)
    source_audit = verify_sources(cfg, source)
    if not source_audit["passed"]:
        raise RuntimeError("v29.6 source lock failed")

    raw = pd.read_csv(source["source_p3_daily"], parse_dates=["date"]).set_index("date")
    d1 = pd.read_csv(source["source_d1_daily"], parse_dates=["date"]).set_index("date")
    trades = pd.read_csv(
        source["source_p3_trades"], parse_dates=["entry_date", "exit_date"]
    )
    ledger = pd.read_csv(source["source_p3_ledger"], parse_dates=["date"])
    episodes = pd.read_csv(
        source["source_d1_episodes"], parse_dates=["start", "trough", "recovery"]
    ).head(5)
    if raw.index.max() > pd.Timestamp(cfg["train_end"]):
        raise RuntimeError("development data entered v29.6")

    weights, groups, weight_error = reconstruct_symbol_weights(raw, trades, ledger)
    gross, costs, gross_error, cost_error = symbol_return_contributions(
        raw, trades, ledger
    )
    market_returns = load_market_returns(
        source["source_market"], pd.Timestamp(cfg["train_end"])
    )
    if len(market_returns.columns) != 45:
        raise RuntimeError("v29.6 market snapshot is not the frozen 45-ETF universe")
    output.mkdir(parents=True, exist_ok=True)

    results = {}
    audit_tables = {}
    for variant, spec in cfg["variants"].items():
        if spec["type"] == "control":
            scales = pd.DataFrame(1.0, index=weights.index, columns=weights.columns)
            cap_audit = pd.DataFrame()
        elif spec["type"] == "sleeve_cap":
            scales, cap_audit = sleeve_cap_scales(
                weights,
                d1["executed_multiplier"],
                groups,
                spec["maximum_sleeve_exposure"],
            )
        elif spec["type"] == "correlation_cluster_risk_cap":
            scales, cap_audit = cluster_risk_scales(
                weights,
                d1["executed_multiplier"],
                market_returns,
                spec,
            )
        else:
            raise ValueError(f"unknown concentration variant {spec['type']}")
        daily = run_concentration_variant(
            raw, d1, weights, gross, costs, scales, cfg, variant
        )
        results[variant] = daily
        audit_tables[variant] = cap_audit

    c0_return_error = float(
        (results["C0"]["controlled_return"] - d1["controlled_return"]).abs().max()
    )
    c0_nav_error = float((results["C0"]["nav"] - d1["nav"]).abs().max())
    if max(weight_error, gross_error, cost_error, c0_return_error) >= 1e-12:
        raise RuntimeError("v29.6 reconstruction or C0 replication failed")
    if c0_nav_error >= 1e-6:
        raise RuntimeError("v29.6 C0 NAV replication failed")

    v29_4 = json.loads(source["source_v29_4_decision"].read_text())
    raw_p3_cagr = float(v29_4["raw_p3"]["cagr"])
    d1_cagr = float(v29_4["variants"]["D1"]["net_cagr"])
    rows = []
    annual_frames = []
    episode_frames = []
    for variant, daily in results.items():
        metrics = performance_metrics(daily, raw_p3_cagr, d1_cagr)
        rows.append({"variant": variant, **metrics})
        annual_frames.append(annual_returns(daily, variant))
        episode_frames.append(
            episode_comparison(daily, results["C0"], episodes, variant)
        )
        write_frame(daily.reset_index(), output / f"variant_{variant}_daily.csv")
        write_frame(audit_tables[variant], output / f"variant_{variant}_cap_audit.csv")

    matrix = pd.DataFrame(rows)
    annual = pd.concat(annual_frames, ignore_index=True)
    episode_table = pd.concat(episode_frames, ignore_index=True)
    control = matrix.loc[matrix["variant"].eq("C0")].iloc[0].to_dict()
    matrix["improved_deepest_drawdowns"] = 0
    matrix["eligible"] = False
    matrix["materially_worse_non_2011_years"] = 0
    gate_details = {}
    for index, row in matrix.iterrows():
        variant = row["variant"]
        variant_episodes = episode_table.loc[episode_table["variant"].eq(variant)]
        improved = int(variant_episodes["improved"].sum())
        matrix.loc[index, "improved_deepest_drawdowns"] = improved
        if variant == "C0":
            continue
        candidate = row.to_dict()
        candidate["improved_deepest_drawdowns"] = improved
        passed, detail = gate_candidate(
            candidate, control, annual, variant_episodes, cfg
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
        status = "V29_6_REJECTED_KEEP_D1"
    else:
        order = {
            name: rank for rank, name in enumerate(cfg["admission"]["selection_order"])
        }
        qualified["tie_order"] = qualified["variant"].map(order)
        winner = qualified.sort_values(
            [cfg["admission"]["selection_metric"], "tie_order"],
            ascending=[False, True],
        ).iloc[0]["variant"]
        status = "V29_6_CONCENTRATION_CONTROL_PASS_PROSPECTIVE_REQUIRED"

    audit = {
        **source_audit,
        "maximum_weight_reconstruction_error": weight_error,
        "maximum_gross_contribution_error": gross_error,
        "maximum_cost_contribution_error": cost_error,
        "c0_maximum_daily_return_error": c0_return_error,
        "c0_maximum_nav_error": c0_nav_error,
        "train_last_date": str(raw.index.max().date()),
        "market_last_date": str(market_returns.index.max().date()),
        "market_symbol_count": int(len(market_returns.columns)),
        "development_read": False,
        "passed": True,
    }
    decision = {
        "status": status,
        "frozen_train_winner": winner,
        "fallback": "v29.4 D1" if winner is None else None,
        "development_read": False,
        "orders_allowed": False,
        "risk_admitted": False,
        "protocol_sha256": sha256(PROTOCOL),
        "config_sha256": sha256(config),
        "engine_sha256": sha256(ENGINE),
        "evaluator_sha256": sha256(Path(__file__)),
        "variants": {
            row["variant"]: {key: finite(value) for key, value in row.items()}
            for row in matrix.to_dict("records")
        },
        "gates": gate_details,
        "audit": audit,
    }
    (output / "RUN_AUDIT.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "v29_6_decision.json").write_text(json.dumps(decision, indent=2) + "\n")
    write_report(output, decision, matrix)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    main(arguments.config, arguments.output)
