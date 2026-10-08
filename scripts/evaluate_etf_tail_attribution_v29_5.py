"""Diagnose v29.4 D1 left-tail losses and run one conditional v29.5 treatment."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backtest.etf_drawdown_overlay import overlay_metrics, run_overlay
from backtest.etf_tail_attribution import (
    daily_return_attribution,
    event_attribution,
    ledger_return_attribution,
    summarize_window,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/etf_tail_attribution_v29_5.json"
PROTOCOL = ROOT / "docs/ETF_TAIL_ATTRIBUTION_PROTOCOL_V29_5.md"
ENGINE = ROOT / "backtest/etf_tail_attribution.py"
OVERLAY_ENGINE = ROOT / "backtest/etf_drawdown_overlay.py"
DEFAULT_OUTPUT = ROOT / "reports/etf_tail_attribution_v29_5"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finite(value: object) -> object:
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(value).date())
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
        "decision": ROOT / cfg["source_decision"],
        "d1_daily": ROOT / cfg["source_d1_daily"],
        "episodes": ROOT / cfg["source_d1_episodes"],
        "p3_daily": ROOT / cfg["source_p3_daily"],
        "ledger": ROOT / cfg["source_p3_ledger"],
        "trades": ROOT / cfg["source_p3_trades"],
    }


def verify_sources(cfg: dict, paths: dict[str, Path], decision: dict) -> dict:
    observed = {
        "v29_4_decision_sha256": sha256(paths["decision"]),
        "d1_daily_sha256": sha256(paths["d1_daily"]),
        "p3_ledger_sha256": sha256(paths["ledger"]),
        "p3_trades_sha256": sha256(paths["trades"]),
    }
    mismatches = {
        key: {"expected": cfg["source_hashes"][key], "observed": value}
        for key, value in observed.items()
        if cfg["source_hashes"][key] != value
    }
    passed = bool(
        not mismatches
        and decision["status"] == "V29_4_TRAIN_DD_PASS_PROSPECTIVE_REQUIRED"
        and decision["frozen_train_winner"] == "D1"
        and not decision["development_read"]
        and not decision["orders_allowed"]
    )
    return {"passed": passed, "observed_hashes": observed, "mismatches": mismatches}


def asset_table(
    ledger: pd.DataFrame,
    windows: pd.DataFrame,
    field: str,
) -> pd.DataFrame:
    rows = []
    for window in windows.itertuples(index=False):
        mask = ledger["date"].between(
            pd.Timestamp(window.start), pd.Timestamp(window.end)
        )
        contribution = ledger.loc[mask].groupby(field)["net_contribution"].sum()
        negative_total = contribution.loc[contribution.lt(0)].abs().sum()
        for name, value in contribution.items():
            rows.append(
                {
                    "window": window.window,
                    field: name,
                    "arithmetic_return_contribution": float(value),
                    "share_of_negative_contribution": (
                        float(abs(value) / negative_total)
                        if value < 0 and negative_total > 0
                        else 0.0
                    ),
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["window", "arithmetic_return_contribution"], ascending=[True, True]
    )


def worst_month(
    daily: pd.DataFrame,
) -> tuple[pd.Period, pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    monthly = (1 + daily["d1_return"]).groupby(daily.index.to_period("M")).prod().sub(1)
    period = monthly.idxmin()
    dates = daily.index[daily.index.to_period("M") == period]
    month_path = (1 + daily.loc[dates, "d1_return"]).cumprod()
    return period, dates.min(), pd.Timestamp(month_path.idxmin()), dates.max()


def overlay_cfg(cfg: dict, variant: dict) -> dict:
    return {
        "initial_nav": cfg["execution"]["initial_nav"],
        "decision_delay_sessions": cfg["execution"]["decision_delay_sessions"],
        "transaction_cost_one_way": cfg["execution"]["transaction_cost_one_way"],
        "variants": {"candidate": variant},
    }


def candidate_metrics(
    cfg: dict,
    raw: pd.DataFrame,
    decision: dict,
    treatment: dict,
) -> tuple[dict, dict[str, pd.DataFrame]]:
    run_cfg = overlay_cfg(cfg, treatment)
    result = run_overlay(raw, "candidate", run_cfg)
    raw_metrics = {
        "cagr": decision["raw_p3"]["cagr"],
        "maximum_drawdown": decision["raw_p3"]["maximum_drawdown"],
    }
    metrics = overlay_metrics(result["daily"], raw_metrics, run_cfg)
    monthly = (
        (1 + result["daily"]["controlled_return"])
        .groupby(result["daily"].index.to_period("M"))
        .prod()
        .sub(1)
    )
    metrics["worst_month"] = float(monthly.min())
    return metrics, result


def candidate_passes(metrics: dict, decision: dict, cfg: dict) -> tuple[bool, dict]:
    gate = cfg["admission"]
    d1 = decision["variants"]["D1"]
    checks = {
        "raw_p3_cagr_retention": metrics["cagr_retention"]
        >= gate["minimum_raw_p3_cagr_retention"],
        "maximum_drawdown_better_than_d1": metrics["maximum_drawdown"]
        > d1["maximum_drawdown"],
        "worst_month_above_floor": metrics["worst_month"] > gate["minimum_worst_month"],
        "calmar_better_than_d1": metrics["calmar"] > d1["calmar"],
        "cost_not_significantly_higher": metrics["total_cost"]
        <= d1["total_cost"] * (1 + gate["maximum_cost_increase_fraction"]),
        "de_risk_events_sparse": metrics["de_risk_events"]
        <= gate["maximum_de_risk_events"],
    }
    return all(checks.values()), checks


def write_report(
    output: Path,
    decision: dict,
    windows: pd.DataFrame,
    candidate: pd.DataFrame,
) -> None:
    window_columns = [
        "window",
        "d1_return",
        "raw_p3_return",
        "worst_day",
        "worst_five_day",
        "avoided_loss",
        "missed_rebound",
        "de_risk_lag_loss",
        "top_negative_etf",
        "top_negative_group",
        "labels",
        "primary_cause",
    ]
    candidate_text = (
        "No treatment was backtested because the frozen decision tree requires new data or a "
        "separate portfolio-design experiment for the diagnosed mechanism."
        if candidate.empty
        else markdown_table(candidate)
    )
    report = f"""# v29.5 D1 Tail-Loss Attribution

## Decision

**{decision["status"]}**

The v29.3 P3 alpha engine and v29.4 D1 controller were held fixed. The five deepest D1
drawdowns, the worst month and every D1 state transition were decomposed into full-exposure loss,
avoided loss, missed rebound, execution-lag loss, costs, ETF and sleeve contributions. No
development/OOS data was read and orders remain disabled.

{markdown_table(windows.loc[:, window_columns])}

Worst month: **{decision["worst_month"]}**. Frozen primary cause:
**{decision["worst_month_primary_cause"]}**.

## Conditional treatment

{candidate_text}

The only permitted candidate depended on the frozen worst-month classification. A candidate had
to retain at least 90% of raw P3 CAGR, improve both D1 maximum drawdown and Calmar, lift worst
month above -10%, keep total cost within 10% of D1 and remain sparse. Failure keeps D1.

The report directory contains the daily reconciliation, episode and month attribution, every
state-transition audit, ETF/sleeve contribution tables, source hashes and any conditional
candidate path.
"""
    (output / "REPORT.md").write_text(report)


def main(config: Path = CONFIG, output: Path = DEFAULT_OUTPUT) -> None:
    cfg = json.loads(config.read_text())
    paths = source_paths(cfg)
    prior_decision = json.loads(paths["decision"].read_text())
    source_audit = verify_sources(cfg, paths, prior_decision)
    if not source_audit["passed"]:
        raise RuntimeError("v29.5 source lock failed")

    d1 = pd.read_csv(paths["d1_daily"], parse_dates=["date"]).set_index("date")
    raw = pd.read_csv(paths["p3_daily"], parse_dates=["date"]).set_index("date")
    ledger = pd.read_csv(paths["ledger"], parse_dates=["date"])
    trades = pd.read_csv(paths["trades"], parse_dates=["entry_date", "exit_date"])
    episodes = pd.read_csv(
        paths["episodes"], parse_dates=["start", "trough", "recovery"]
    ).head(cfg["attribution"]["deepest_episodes"])
    if d1.index.max() > pd.Timestamp(cfg["train_end"]):
        raise RuntimeError("development data entered v29.5")

    output.mkdir(parents=True, exist_ok=True)
    daily = daily_return_attribution(d1, raw, cfg["execution"]["initial_nav"])
    ledger_attr = ledger_return_attribution(
        ledger, trades, d1, raw, cfg["execution"]["initial_nav"]
    )
    daily_ledger = (
        ledger_attr.groupby("date")["net_contribution"]
        .sum()
        .reindex(daily.index, fill_value=0.0)
    )
    ledger_reconciliation = (
        daily_ledger + daily["overlay_cost_effect"] - daily["d1_return"]
    )
    max_daily_error = float(daily["reconciliation_error"].abs().max())
    max_ledger_error = float(ledger_reconciliation.abs().max())
    if max_daily_error >= 1e-12 or max_ledger_error >= 1e-12:
        raise RuntimeError("v29.5 attribution reconciliation failed")

    window_rows = []
    for rank, episode in enumerate(episodes.itertuples(index=False), start=1):
        row = summarize_window(
            f"drawdown_{rank}",
            pd.Timestamp(episode.start),
            pd.Timestamp(episode.trough),
            pd.Timestamp(episode.trough),
            daily,
            ledger_attr,
            cfg,
            recovery=pd.Timestamp(episode.recovery),
        )
        row["kind"] = "drawdown"
        window_rows.append(row)
    month, month_start, month_trough, month_end = worst_month(daily)
    month_row = summarize_window(
        f"worst_month_{month}",
        month_start,
        month_trough,
        month_end,
        daily,
        ledger_attr,
        cfg,
    )
    month_row["kind"] = "worst_month"
    window_rows.append(month_row)
    windows = pd.DataFrame(window_rows)

    events = event_attribution(daily)
    by_etf = asset_table(ledger_attr, windows, "symbol")
    by_group = asset_table(ledger_attr, windows, "group")
    write_frame(daily.reset_index(), output / "daily_return_attribution.csv")
    write_frame(events, output / "d1_event_attribution.csv")
    write_frame(windows, output / "window_attribution.csv")
    write_frame(by_etf, output / "window_etf_attribution.csv")
    write_frame(by_group, output / "window_group_attribution.csv")

    primary = month_row["primary_cause"]
    treatment_key = primary if primary in cfg["conditional_treatments"] else None
    candidate_frame = pd.DataFrame()
    candidate_decision = None
    if treatment_key is None:
        status = "V29_5_ATTRIBUTED_NEW_DATA_REQUIRED_KEEP_D1"
    else:
        treatment = cfg["conditional_treatments"][treatment_key]
        frozen_d1 = run_overlay(raw, "candidate", overlay_cfg(cfg, cfg["frozen_d1"]))
        d1_error = float(
            (frozen_d1["daily"]["controlled_return"] - d1["controlled_return"])
            .abs()
            .max()
        )
        if d1_error >= 1e-12:
            raise RuntimeError("frozen D1 failed to reproduce")
        metrics, candidate_result = candidate_metrics(
            cfg, raw, prior_decision, treatment
        )
        passed, checks = candidate_passes(metrics, prior_decision, cfg)
        candidate_decision = {
            "treatment": treatment["name"],
            "mechanism": treatment_key,
            "passed": passed,
            "checks": checks,
            "metrics": {key: finite(value) for key, value in metrics.items()},
            "d1_replication_error": d1_error,
        }
        candidate_frame = pd.DataFrame(
            [{"candidate": treatment["name"], "passed": passed, **metrics}]
        )
        write_frame(
            candidate_result["daily"].reset_index(), output / "candidate_daily.csv"
        )
        write_frame(
            candidate_result["decision_events"],
            output / "candidate_decision_events.csv",
        )
        write_frame(
            candidate_result["execution_events"],
            output / "candidate_execution_events.csv",
        )
        candidate_frame.to_csv(output / "candidate_metrics.csv", index=False)
        status = (
            "V29_5_TARGETED_PROTECTION_PASS_PROSPECTIVE_REQUIRED"
            if passed
            else "V29_5_TARGETED_PROTECTION_REJECTED_KEEP_D1"
        )

    audit = {
        **source_audit,
        "maximum_daily_identity_error": max_daily_error,
        "maximum_ledger_identity_error": max_ledger_error,
        "train_last_date": str(d1.index.max().date()),
        "development_read": False,
        "passed": True,
    }
    (output / "RUN_AUDIT.json").write_text(json.dumps(audit, indent=2) + "\n")
    decision = {
        "status": status,
        "frozen_control": "v29.4 D1",
        "selected_treatment": (
            candidate_decision["treatment"]
            if candidate_decision and candidate_decision["passed"]
            else None
        ),
        "worst_month": str(month),
        "worst_month_primary_cause": primary,
        "worst_month_labels": month_row["labels"],
        "candidate": candidate_decision,
        "development_read": False,
        "orders_allowed": False,
        "risk_admitted": False,
        "protocol_sha256": sha256(PROTOCOL),
        "config_sha256": sha256(config),
        "engine_sha256": sha256(ENGINE),
        "overlay_engine_sha256": sha256(OVERLAY_ENGINE),
        "evaluator_sha256": sha256(Path(__file__)),
        "windows": [
            {key: finite(value) for key, value in row.items()} for row in window_rows
        ],
        "run_audit_passed": True,
    }
    (output / "v29_5_decision.json").write_text(json.dumps(decision, indent=2) + "\n")
    write_report(output, decision, windows, candidate_frame)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    main(arguments.config, arguments.output)
