"""Run the frozen v31 position-level loss-stop experiment over P3 + D1."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backtest.d1_position_loss_stop import (
    build_trade_panels,
    performance_metrics,
    run_position_stop,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/d1_position_loss_stop_v31.json"
PROTOCOL = ROOT / "docs/D1_POSITION_LOSS_STOP_PROTOCOL_V31.md"
ENGINE = ROOT / "backtest/d1_position_loss_stop.py"
DEFAULT_OUTPUT = ROOT / "reports/d1_position_loss_stop_v31"


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
    keys = [
        "source_p3_daily",
        "source_p3_trades",
        "source_p3_ledger",
        "source_market",
        "source_d1_daily",
        "source_d1_episodes",
        "source_v29_4_decision",
        "source_v30_decision",
    ]
    return {key: ROOT / cfg[key] for key in keys}


def verify_sources(cfg: dict, paths: dict[str, Path]) -> dict:
    observed = {
        "p3_daily_sha256": sha256(paths["source_p3_daily"]),
        "p3_trades_sha256": sha256(paths["source_p3_trades"]),
        "p3_ledger_sha256": sha256(paths["source_p3_ledger"]),
        "market_sha256": sha256(paths["source_market"]),
        "d1_daily_sha256": sha256(paths["source_d1_daily"]),
        "d1_episodes_sha256": sha256(paths["source_d1_episodes"]),
        "v29_4_decision_sha256": sha256(paths["source_v29_4_decision"]),
        "v30_decision_sha256": sha256(paths["source_v30_decision"]),
    }
    mismatches = {
        key: {"expected": cfg["source_hashes"][key], "observed": value}
        for key, value in observed.items()
        if cfg["source_hashes"][key] != value
    }
    v29_4 = json.loads(paths["source_v29_4_decision"].read_text())
    v30 = json.loads(paths["source_v30_decision"].read_text())
    passed = bool(
        not mismatches
        and v29_4["status"] == "V29_4_TRAIN_DD_PASS_PROSPECTIVE_REQUIRED"
        and v29_4["frozen_train_winner"] == "D1"
        and v30["status"] == "V30_REJECTED_KEEP_D1"
        and v30["frozen_train_winner"] is None
        and not v29_4["development_read"]
        and not v30["development_read"]
    )
    return {
        "passed": passed,
        "observed_hashes": observed,
        "mismatches": mismatches,
    }


def load_prices(path: Path, train_end: pd.Timestamp) -> pd.DataFrame:
    market = pd.read_csv(
        path, usecols=["symbol", "date", "adj_close"], parse_dates=["date"]
    )
    if market["date"].max() > train_end:
        raise RuntimeError("post-train market observations entered v31")
    prices = market.pivot(
        index="date", columns="symbol", values="adj_close"
    ).sort_index()
    if len(prices.columns) != 45:
        raise RuntimeError("v31 market snapshot is not the frozen 45-ETF universe")
    return prices


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
        "position_loss_stop",
        "eligible",
        "net_cagr",
        "sharpe",
        "maximum_drawdown",
        "calmar",
        "worst_month",
        "raw_p3_cagr_retention",
        "average_exposure",
        "stop_event_count",
        "annual_total_turnover",
        "total_cost",
        "improved_deepest_drawdowns",
        "materially_worse_non_2011_years",
    ]
    winner = decision["frozen_train_winner"] or "keep v29.4 D1"
    report = f"""# v31 D1 Position-Level Loss Stop

## Decision

**{decision["status"]}**

Each stop acted independently on one frozen P3 trade episode held by D1. A breach at close t
liquidated only that trade at close t+1 and locked it out until its original P3 exit; proceeds
remained cash. P3, D1 and every other position were unchanged. Portfolio drawdown was never an
input.

{markdown_table(matrix.loc[:, columns])}

Selected result: **{winner}**. A candidate had to retain at least 90% of raw P3 CAGR, improve D1
maximum drawdown, Calmar and worst month, stay within cost/turnover limits, improve at least three
fixed drawdown windows and avoid broad non-2011 deterioration. Among fully eligible candidates,
the least severe maximum drawdown wins.

The control reproduced D1 with maximum daily return error
{decision["audit"]["control_maximum_daily_return_error"]:.3e}. The output includes every causal
stop event, daily path, annual result, fixed-episode comparison, source hash and gate result.
"""
    (output / "REPORT.md").write_text(report)


def main(config: Path = CONFIG, output: Path = DEFAULT_OUTPUT) -> None:
    cfg = json.loads(config.read_text())
    paths = source_paths(cfg)
    source_audit = verify_sources(cfg, paths)
    if not source_audit["passed"]:
        raise RuntimeError("v31 source lock failed")

    raw = pd.read_csv(paths["source_p3_daily"], parse_dates=["date"]).set_index("date")
    d1 = pd.read_csv(paths["source_d1_daily"], parse_dates=["date"]).set_index("date")
    trades = pd.read_csv(
        paths["source_p3_trades"], parse_dates=["entry_date", "exit_date"]
    )
    ledger = pd.read_csv(paths["source_p3_ledger"], parse_dates=["date"])
    episodes = pd.read_csv(
        paths["source_d1_episodes"], parse_dates=["start", "trough", "recovery"]
    ).head(5)
    if not raw.index.equals(d1.index):
        raise RuntimeError("P3 and D1 daily indices do not match")
    if raw.index.min() < pd.Timestamp(cfg["train_start"]):
        raise RuntimeError("v31 source begins before frozen train")
    if raw.index.max() > pd.Timestamp(cfg["train_end"]):
        raise RuntimeError("development data entered v31")
    prices = load_prices(paths["source_market"], pd.Timestamp(cfg["train_end"]))
    prices = prices.reindex(raw.index)
    panels = build_trade_panels(raw, trades, ledger)

    gross_reconciliation_error = float(
        (panels["gross"].sum(axis=1) - raw["gross_pnl"]).abs().max()
    )
    cost_reconciliation_error = float(
        (panels["costs"].sum(axis=1) - raw["cost"]).abs().max()
    )
    exposure_reconstruction = panels["marked_value"].sum(axis=1).div(raw["nav"])
    exposure_reconciliation_error = float(
        (exposure_reconstruction - raw["long_exposure"]).abs().max()
    )
    entry_prices = trades.merge(
        prices.stack().rename("adj_close"),
        left_on=["entry_date", "symbol"],
        right_index=True,
        validate="many_to_one",
    )
    entry_price_error = float(
        (
            entry_prices["entry_notional"].div(entry_prices["shares"])
            - entry_prices["adj_close"]
        )
        .abs()
        .max()
    )
    if (
        max(
            gross_reconciliation_error,
            cost_reconciliation_error,
            exposure_reconciliation_error,
            entry_price_error,
        )
        >= 1e-10
    ):
        raise RuntimeError("v31 trade reconstruction failed")

    output.mkdir(parents=True, exist_ok=True)
    v29_4 = json.loads(paths["source_v29_4_decision"].read_text())
    raw_p3_cagr = float(v29_4["raw_p3"]["cagr"])
    d1_cagr = float(v29_4["variants"]["D1"]["net_cagr"])
    results = {}
    rows = []
    annual_frames = []
    all_events = []
    for variant, spec in cfg["variants"].items():
        result = run_position_stop(
            raw,
            d1,
            trades,
            panels,
            prices,
            spec["position_loss_stop"],
            cfg,
        )
        daily = result["daily"]
        events = result["events"].copy()
        results[variant] = daily
        metrics = performance_metrics(daily, raw_p3_cagr, d1_cagr, len(events))
        rows.append(
            {
                "variant": variant,
                "position_loss_stop": spec["position_loss_stop"],
                **metrics,
            }
        )
        annual_frames.append(annual_returns(daily, variant))
        if not events.empty:
            events.insert(0, "variant", variant)
            all_events.append(events)
        write_frame(daily.reset_index(), output / f"variant_{variant}_daily.csv")
        write_frame(events, output / f"variant_{variant}_stop_events.csv")

    control = results["D1_CONTROL"]
    control_return_error = float(
        (control["controlled_return"] - d1["controlled_return"]).abs().max()
    )
    control_nav_error = float((control["nav"] - d1["nav"]).abs().max())
    control_exposure_error = float(
        (control["controlled_long_exposure"] - d1["controlled_long_exposure"])
        .abs()
        .max()
    )
    if control_return_error >= 1e-12 or control_exposure_error >= 1e-12:
        raise RuntimeError("v31 D1 control replication failed")
    if control_nav_error >= 1e-6:
        raise RuntimeError("v31 D1 control NAV replication failed")

    matrix = pd.DataFrame(rows)
    annual = pd.concat(annual_frames, ignore_index=True)
    episode_table = pd.concat(
        [
            episode_comparison(daily, control, episodes, variant)
            for variant, daily in results.items()
        ],
        ignore_index=True,
    )
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
    write_frame(
        pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame(),
        output / "all_position_stop_events.csv",
    )

    qualified = matrix.loc[matrix["eligible"]].copy()
    if qualified.empty:
        winner = None
        status = "V31_REJECTED_KEEP_D1"
    else:
        order = {
            name: rank for rank, name in enumerate(cfg["admission"]["selection_order"])
        }
        qualified["tie_order"] = qualified["variant"].map(order)
        winner = qualified.sort_values(
            [cfg["admission"]["selection_metric"], "tie_order"],
            ascending=[False, True],
        ).iloc[0]["variant"]
        status = "V31_POSITION_STOP_PASS_PROSPECTIVE_REQUIRED"

    audit = {
        **source_audit,
        "maximum_gross_reconciliation_error": gross_reconciliation_error,
        "maximum_cost_reconciliation_error": cost_reconciliation_error,
        "maximum_exposure_reconciliation_error": exposure_reconciliation_error,
        "maximum_entry_price_error": entry_price_error,
        "control_maximum_daily_return_error": control_return_error,
        "control_maximum_nav_error": control_nav_error,
        "control_maximum_exposure_error": control_exposure_error,
        "trade_count": int(len(trades)),
        "market_symbol_count": int(len(prices.columns)),
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
    (output / "v31_decision.json").write_text(json.dumps(decision, indent=2) + "\n")
    write_report(output, decision, matrix)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    main(arguments.config, arguments.output)
