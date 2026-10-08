"""Run the frozen v29.4 drawdown overlay on the admitted v29.3 P3 train stream."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backtest.etf_drawdown_overlay import (
    drawdown_episodes,
    overlay_metrics,
    run_overlay,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/etf_drawdown_overlay_v29_4.json"
PROTOCOL = ROOT / "docs/ETF_DRAWDOWN_OVERLAY_PROTOCOL_V29_4.md"
ENGINE = ROOT / "backtest/etf_drawdown_overlay.py"
DEFAULT_OUTPUT = ROOT / "reports/etf_drawdown_overlay_v29_4"


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


def verify_source(cfg: dict, decision: dict, source_daily: Path) -> dict[str, object]:
    expected = cfg["source_hashes"]
    observed = {
        "market_data_sha256": decision["source_sha256"],
        "v29_3_protocol_sha256": decision["protocol_sha256"],
        "v29_3_config_sha256": decision["config_sha256"],
        "v29_3_engine_sha256": decision["engine_sha256"],
        "v29_3_evaluator_sha256": decision["evaluator_sha256"],
    }
    mismatches = {
        key: {"expected": expected[key], "observed": observed[key]}
        for key in expected
        if expected[key] != observed[key]
    }
    passed = bool(
        not mismatches
        and decision["status"] == "V29_3_LONG_ALPHA_FOUND_RISK_UNASSESSED"
        and decision["frozen_train_winner"] == cfg["source_winner"]
        and not decision["development_read"]
        and not decision["orders_allowed"]
        and source_daily.exists()
    )
    return {
        "passed": passed,
        "expected_status": "V29_3_LONG_ALPHA_FOUND_RISK_UNASSESSED",
        "observed_status": decision["status"],
        "expected_winner": cfg["source_winner"],
        "observed_winner": decision["frozen_train_winner"],
        "hashes": observed,
        "hash_mismatches": mismatches,
        "source_daily_sha256": sha256(source_daily) if source_daily.exists() else None,
    }


def raw_metrics(raw: pd.DataFrame, decision: dict) -> dict[str, float]:
    cagr = float(decision["variants"]["P3"]["net_cagr"])
    maximum_drawdown = float(raw["nav"].div(raw["nav"].cummax()).sub(1).min())
    return {
        "cagr": cagr,
        "maximum_drawdown": maximum_drawdown,
        "calmar": cagr / abs(maximum_drawdown),
        "sharpe": float(decision["variants"]["P3"]["sharpe"]),
        "trade_profit_factor": float(decision["variants"]["P3"]["profit_factor"]),
    }


def annual_returns(daily: pd.DataFrame, variant: str) -> pd.DataFrame:
    rows = []
    for year, frame in daily.groupby(daily.index.year):
        rows.append(
            {
                "variant": variant,
                "year": int(year),
                "controlled_return": float((1 + frame["controlled_return"]).prod() - 1),
                "average_exposure": float(frame["controlled_long_exposure"].mean()),
                "average_multiplier": float(frame["executed_multiplier"].mean()),
                "overlay_cost": float(frame["overlay_cost"].sum()),
            }
        )
    return pd.DataFrame(rows)


def run_audit(
    raw: pd.DataFrame, result: dict[str, pd.DataFrame], variant: str, cfg: dict
) -> dict[str, object]:
    daily = result["daily"]
    nav_rebuilt = cfg["initial_nav"] * (1 + daily["controlled_return"]).cumprod()
    audit = {
        "variant": variant,
        "nav_reconciliation_error": float((daily["nav"] - nav_rebuilt).abs().max()),
        "maximum_controlled_exposure": float(daily["controlled_long_exposure"].max()),
        "minimum_cash_exposure": float(daily["cash_exposure"].min()),
        "last_date": str(daily.index.max().date()),
        "d0_nav_replication_error": None,
        "d0_return_replication_error": None,
    }
    if variant == "D0":
        audit["d0_nav_replication_error"] = float(
            (daily["nav"] - raw["nav"]).abs().max()
        )
        audit["d0_return_replication_error"] = float(
            (daily["controlled_return"] - raw["net_return"]).abs().max()
        )
    audit["passed"] = bool(
        audit["nav_reconciliation_error"] < 1e-8
        and audit["maximum_controlled_exposure"] <= cfg["maximum_gross"] + 1e-9
        and audit["minimum_cash_exposure"] >= -1e-9
        and daily.index.max() <= pd.Timestamp(cfg["train_end"])
        and (
            variant != "D0"
            or (
                audit["d0_nav_replication_error"] < 1e-6
                and audit["d0_return_replication_error"] < 1e-12
            )
        )
    )
    return audit


def write_report(output: Path, decision: dict, matrix: pd.DataFrame) -> None:
    columns = [
        "variant",
        "eligible",
        "net_cagr",
        "sharpe",
        "maximum_drawdown",
        "calmar",
        "cagr_retention",
        "drawdown_improvement",
        "average_exposure",
        "time_multiplier_zero",
        "worst_month",
        "de_risk_events",
        "re_entry_events",
        "total_cost",
    ]
    winner = decision["frozen_train_winner"] or "raw P3"
    report = f"""# v29.4 Long-Only ETF Drawdown Overlay

## Decision

**{decision["status"]}**

The frozen v29.3 P3 train return stream was left unchanged. D0–D3 changed only the long-exposure
multiplier and residual cash. Every state decision used the shadow P3 close and was executed one
session later; the resulting exposure first earned the following close-to-close return. The run
read no development/OOS data and did not authorize orders.

{markdown_table(matrix.loc[:, columns])}

Selected result: **{winner}**. Eligibility required at least 80% of raw P3 CAGR, a strict maximum
drawdown improvement and a Calmar ratio above raw P3. D0 is an implementation control and cannot
win. If the decision keeps raw P3, none of the preregistered overlays cleared all three gates.

Raw P3 benchmark: CAGR {decision["raw_p3"]["cagr"]:.4%}, maximum drawdown
{decision["raw_p3"]["maximum_drawdown"]:.4%}, Calmar {decision["raw_p3"]["calmar"]:.4f}.

The output directory also contains daily multiplier/exposure histories, decision and execution
events, annual results, the five deepest drawdown episodes, source verification and run audits.
Daily profit factor is reported as a portfolio-return diagnostic; it is not the v29.3 trade-ledger
profit factor and is not an admission gate.
"""
    (output / "REPORT.md").write_text(report)


def main(config: Path = CONFIG, output: Path = DEFAULT_OUTPUT) -> None:
    cfg = json.loads(config.read_text())
    source_decision = ROOT / cfg["source_decision"]
    source_daily = ROOT / cfg["source_daily"]
    prior_decision = json.loads(source_decision.read_text())
    source_audit = verify_source(cfg, prior_decision, source_daily)
    if not source_audit["passed"]:
        raise RuntimeError("v29.3 source lock failed")

    raw = pd.read_csv(source_daily, parse_dates=["date"]).set_index("date")
    if raw.index.min() < pd.Timestamp(cfg["train_start"]):
        raise RuntimeError("source daily begins before frozen train")
    if raw.index.max() > pd.Timestamp(cfg["train_end"]):
        raise RuntimeError("development data entered v29.4")
    if not raw.index.is_monotonic_increasing or raw.index.has_duplicates:
        raise RuntimeError("source daily dates are not unique and ordered")

    output.mkdir(parents=True, exist_ok=True)
    baseline = raw_metrics(raw, prior_decision)
    rows = []
    annual = []
    audits = []
    for variant in cfg["variants"]:
        result = run_overlay(raw, variant, cfg)
        metrics = overlay_metrics(result["daily"], baseline, cfg)
        eligible = bool(
            variant in cfg["admission"]["selection_variants"]
            and metrics["cagr_retention"] >= cfg["admission"]["minimum_cagr_retention"]
            and metrics["maximum_drawdown"] > baseline["maximum_drawdown"]
            and metrics["calmar"] > baseline["calmar"]
        )
        rows.append({"variant": variant, "eligible": eligible, **metrics})
        annual.append(annual_returns(result["daily"], variant))
        audits.append(run_audit(raw, result, variant, cfg))
        write_frame(
            result["daily"].reset_index(), output / f"variant_{variant}_daily.csv"
        )
        write_frame(
            result["decision_events"], output / f"variant_{variant}_decision_events.csv"
        )
        write_frame(
            result["execution_events"],
            output / f"variant_{variant}_execution_events.csv",
        )
        episodes = drawdown_episodes(result["daily"]["nav"])
        if not episodes.empty:
            episodes = episodes.sort_values("maximum_drawdown").head(5)
        write_frame(episodes, output / f"variant_{variant}_deepest_drawdowns.csv")

    matrix = pd.DataFrame(rows)
    matrix.to_csv(output / "performance_matrix.csv", index=False)
    pd.concat(annual, ignore_index=True).to_csv(
        output / "annual_returns.csv", index=False
    )
    (output / "SOURCE_AUDIT.json").write_text(json.dumps(source_audit, indent=2) + "\n")
    (output / "RUN_AUDIT.json").write_text(json.dumps(audits, indent=2) + "\n")
    if not all(row["passed"] for row in audits):
        raise RuntimeError("v29.4 run audit failed")

    qualified = matrix.loc[matrix["eligible"]].copy()
    if qualified.empty:
        winner = None
        status = "V29_4_REJECTED_KEEP_RAW_P3"
    else:
        tie_order = {
            name: rank
            for rank, name in enumerate(cfg["admission"]["selection_variants"])
        }
        qualified["tie_order"] = qualified["variant"].map(tie_order)
        winner = qualified.sort_values(
            [cfg["admission"]["selection_metric"], "tie_order"],
            ascending=[False, True],
        ).iloc[0]["variant"]
        status = "V29_4_TRAIN_DD_PASS_PROSPECTIVE_REQUIRED"

    decision = {
        "status": status,
        "frozen_train_winner": winner,
        "source_version": cfg["source_version"],
        "source_winner": cfg["source_winner"],
        "risk_admitted": False,
        "prospective_validation_required": True,
        "development_read": False,
        "orders_allowed": False,
        "raw_p3": baseline,
        "source_daily_sha256": source_audit["source_daily_sha256"],
        "protocol_sha256": sha256(PROTOCOL),
        "config_sha256": sha256(config),
        "engine_sha256": sha256(ENGINE),
        "evaluator_sha256": sha256(Path(__file__)),
        "train_start": cfg["train_start"],
        "train_end": cfg["train_end"],
        "variants": {
            row["variant"]: {key: finite(value) for key, value in row.items()}
            for row in rows
        },
        "run_audit_passed": True,
    }
    (output / "v29_4_decision.json").write_text(json.dumps(decision, indent=2) + "\n")
    write_report(output, decision, matrix)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    main(arguments.config, arguments.output)
