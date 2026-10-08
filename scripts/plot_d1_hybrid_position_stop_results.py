"""Create the required v32 hybrid position-stop result figures."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import PercentFormatter

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/d1_hybrid_position_stop_v32"
V31_REPORT = ROOT / "reports/d1_position_loss_stop_v31"
FIGURES = REPORT / "figures"

VARIANTS = ["D1_CONTROL", "PSTOP_12_5", "PSTOP_15", "HYBRID_20D_ENTRY_VOL"]
LABELS = {
    "D1_CONTROL": "v29.4 D1",
    "PSTOP_12_5": "v31 fixed -12.5%",
    "PSTOP_15": "v31 fixed -15%",
    "HYBRID_20D_ENTRY_VOL": "v32 hybrid",
}
COLORS = {
    "D1_CONTROL": "#161A1D",
    "PSTOP_12_5": "#277DA1",
    "PSTOP_15": "#D1495B",
    "HYBRID_20D_ENTRY_VOL": "#2A9D8F",
}
LINEWIDTHS = {variant: 2.5 for variant in VARIANTS}


def configure_style() -> None:
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "#FBFCFD",
            "axes.edgecolor": "#B7C0C8",
            "axes.titleweight": "bold",
            "axes.titlesize": 14,
            "axes.labelsize": 11,
            "legend.frameon": False,
            "font.family": "DejaVu Sans",
            "savefig.bbox": "tight",
        }
    )


def load_daily() -> dict[str, pd.DataFrame]:
    paths = {
        "D1_CONTROL": REPORT / "variant_D1_CONTROL_daily.csv",
        "PSTOP_12_5": V31_REPORT / "variant_PSTOP_12_5_daily.csv",
        "PSTOP_15": V31_REPORT / "variant_PSTOP_15_daily.csv",
        "HYBRID_20D_ENTRY_VOL": REPORT / "variant_HYBRID_20D_ENTRY_VOL_daily.csv",
    }
    return {
        variant: pd.read_csv(path, parse_dates=["date"]).set_index("date")
        for variant, path in paths.items()
    }


def load_matrix() -> pd.DataFrame:
    v31 = pd.read_csv(V31_REPORT / "performance_matrix.csv").set_index("variant")
    v32 = pd.read_csv(REPORT / "performance_matrix.csv").set_index("variant")
    return pd.concat(
        [
            v32.loc[["D1_CONTROL"]],
            v31.loc[["PSTOP_12_5", "PSTOP_15"]],
            v32.loc[["HYBRID_20D_ENTRY_VOL"]],
        ]
    )


def load_annual() -> pd.DataFrame:
    v31 = pd.read_csv(V31_REPORT / "annual_returns.csv")
    v32 = pd.read_csv(REPORT / "annual_returns.csv")
    return pd.concat(
        [
            v32.loc[v32["variant"].eq("D1_CONTROL")],
            v31.loc[v31["variant"].isin(["PSTOP_12_5", "PSTOP_15"])],
            v32.loc[v32["variant"].eq("HYBRID_20D_ENTRY_VOL")],
        ],
        ignore_index=True,
    )


def load_episodes() -> pd.DataFrame:
    v31 = pd.read_csv(V31_REPORT / "deepest_drawdown_comparison.csv")
    v32 = pd.read_csv(REPORT / "deepest_drawdown_comparison.csv")
    return pd.concat(
        [
            v32.loc[v32["variant"].eq("D1_CONTROL")],
            v31.loc[v31["variant"].isin(["PSTOP_12_5", "PSTOP_15"])],
            v32.loc[v32["variant"].eq("HYBRID_20D_ENTRY_VOL")],
        ],
        ignore_index=True,
    )


def save_figure(fig: plt.Figure, name: str, pdf: PdfPages) -> None:
    fig.text(
        0.99,
        0.995,
        "Train only: 2008-01-02 to 2016-12-30 | No development/OOS read",
        ha="right",
        va="top",
        fontsize=9,
        color="#5F6B73",
    )
    fig.savefig(FIGURES / f"{name}.png", dpi=240)
    pdf.savefig(fig)
    plt.close(fig)


def format_time_axis(axis: plt.Axes) -> None:
    axis.xaxis.set_major_locator(mdates.YearLocator(1))
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def plot_executive(
    daily: dict[str, pd.DataFrame],
    matrix: pd.DataFrame,
    minimum_cagr: float,
    pdf: PdfPages,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for variant in VARIANTS:
        nav = daily[variant]["nav"] / daily[variant]["nav"].iloc[0] * 100
        dd = daily[variant]["nav"].div(daily[variant]["nav"].cummax()).sub(1)
        axes[0, 0].plot(
            nav.index,
            nav,
            color=COLORS[variant],
            linewidth=LINEWIDTHS[variant],
            label=LABELS[variant],
        )
        axes[0, 1].plot(
            dd.index, dd, color=COLORS[variant], linewidth=LINEWIDTHS[variant]
        )
    axes[0, 0].set_title("Growth of $100")
    axes[0, 0].legend(ncol=2, fontsize=9)
    axes[0, 1].set_title("Underwater curve")
    axes[0, 1].yaxis.set_major_formatter(PercentFormatter(1.0))
    for axis in axes[0]:
        format_time_axis(axis)
    axes[1, 0].bar(
        [LABELS[v] for v in VARIANTS],
        matrix.loc[VARIANTS, "net_cagr"],
        color=[COLORS[v] for v in VARIANTS],
    )
    axes[1, 0].axhline(
        minimum_cagr, color="#277DA1", linestyle="--", label="8.458% gate"
    )
    axes[1, 0].set_title("Net CAGR")
    axes[1, 0].yaxis.set_major_formatter(PercentFormatter(1.0))
    axes[1, 0].legend()
    axes[1, 1].bar(
        [LABELS[v] for v in VARIANTS],
        matrix.loc[VARIANTS, "maximum_drawdown"],
        color=[COLORS[v] for v in VARIANTS],
    )
    axes[1, 1].axhline(
        matrix.loc["D1_CONTROL", "maximum_drawdown"],
        color="#161A1D",
        linestyle="--",
    )
    axes[1, 1].set_title("Maximum drawdown")
    axes[1, 1].yaxis.set_major_formatter(PercentFormatter(1.0))
    for axis in axes[1]:
        axis.tick_params(axis="x", rotation=14)
    fig.suptitle(
        "v32 hybrid position-stop executive dashboard",
        fontsize=17,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    save_figure(fig, "00_executive_dashboard", pdf)


def plot_paths(
    daily: dict[str, pd.DataFrame], column: str, title: str, name: str, pdf: PdfPages
) -> None:
    fig, axis = plt.subplots(figsize=(12, 6.5))
    for variant in VARIANTS:
        if column == "nav":
            values = daily[variant][column] / daily[variant][column].iloc[0] * 100
        elif column == "drawdown":
            values = daily[variant]["nav"].div(daily[variant]["nav"].cummax()).sub(1)
        elif column == "rolling":
            values = (
                daily[variant]["controlled_return"]
                .add(1)
                .rolling(252)
                .apply(np.prod, raw=True)
                .sub(1)
            )
        else:
            values = daily[variant]["controlled_long_exposure"].rolling(63).mean()
        axis.plot(
            values.index,
            values,
            label=LABELS[variant],
            color=COLORS[variant],
            linewidth=LINEWIDTHS[variant],
        )
    if column in {"drawdown", "rolling"}:
        axis.axhline(0, color="#5F6B73", linewidth=1)
        axis.yaxis.set_major_formatter(PercentFormatter(1.0))
    elif column == "exposure":
        axis.set_ylim(0, 1.05)
        axis.yaxis.set_major_formatter(PercentFormatter(1.0))
    axis.set_title(title, pad=14)
    axis.legend(ncol=2, loc="best")
    format_time_axis(axis)
    save_figure(fig, name, pdf)


def plot_annual(annual: pd.DataFrame, pdf: PdfPages) -> None:
    pivot = annual.pivot(index="variant", columns="year", values="net_return").loc[
        VARIANTS
    ]
    pivot = pivot.loc[:, pivot.columns >= 2009] * 100
    fig, axis = plt.subplots(figsize=(12, 5.5))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".1f",
        center=0,
        cmap=sns.diverging_palette(12, 145, s=78, l=48, as_cmap=True),
        linewidths=0.7,
        linecolor="white",
        cbar_kws={"label": "Annual return (%)"},
        ax=axis,
    )
    axis.set_yticklabels([LABELS[v] for v in VARIANTS], rotation=0)
    axis.set_title("Calendar-year net returns", pad=14)
    axis.set_xlabel("")
    axis.set_ylabel("")
    save_figure(fig, "04_annual_return_heatmap", pdf)


def plot_episodes(episodes: pd.DataFrame, pdf: PdfPages) -> None:
    pivot = episodes.pivot(
        index="variant", columns="episode", values="candidate_return"
    ).loc[VARIANTS]
    fig, axis = plt.subplots(figsize=(10.5, 5.5))
    sns.heatmap(
        pivot * 100,
        annot=True,
        fmt=".1f",
        cmap="RdYlGn",
        center=-8,
        linewidths=0.7,
        linecolor="white",
        cbar_kws={"label": "Fixed start-to-trough return (%)"},
        ax=axis,
    )
    axis.set_yticklabels([LABELS[v] for v in VARIANTS], rotation=0)
    axis.set_xticklabels([f"Episode {i}" for i in pivot.columns], rotation=0)
    axis.set_title("D1's five fixed deepest drawdown windows", pad=14)
    axis.set_xlabel("")
    axis.set_ylabel("")
    save_figure(fig, "06_fixed_drawdown_episodes", pdf)


def plot_risk_return(matrix: pd.DataFrame, minimum_cagr: float, pdf: PdfPages) -> None:
    fig, axis = plt.subplots(figsize=(9.5, 6.8))
    for variant in VARIANTS:
        row = matrix.loc[variant]
        axis.scatter(
            abs(row["maximum_drawdown"]),
            row["net_cagr"],
            s=210,
            color=COLORS[variant],
            edgecolor="white",
            linewidth=1.2,
        )
        axis.annotate(
            LABELS[variant],
            (abs(row["maximum_drawdown"]), row["net_cagr"]),
            xytext=(7, 6),
            textcoords="offset points",
            fontsize=9,
        )
    axis.axhline(minimum_cagr, color="#277DA1", linestyle="--")
    axis.axvline(
        abs(matrix.loc["D1_CONTROL", "maximum_drawdown"]),
        color="#161A1D",
        linestyle="--",
    )
    axis.set_title("CAGR versus maximum drawdown", pad=14)
    axis.set_xlabel("Absolute maximum drawdown")
    axis.set_ylabel("Net CAGR")
    axis.xaxis.set_major_formatter(PercentFormatter(1.0))
    axis.yaxis.set_major_formatter(PercentFormatter(1.0))
    save_figure(fig, "07_risk_return_tradeoff", pdf)


def plot_gates(v31: dict, v32: dict, pdf: PdfPages) -> None:
    checks = [
        "raw_p3_cagr_retention",
        "maximum_drawdown_better_than_d1",
        "calmar_better_than_d1",
        "worst_month_better_than_d1",
        "cost_within_limit",
        "turnover_within_limit",
        "deepest_drawdowns_improved",
        "non_2011_years_not_broadly_worse",
    ]
    short = [
        "CAGR",
        "Max DD",
        "Calmar",
        "Worst month",
        "Cost",
        "Turnover",
        "3/5 episodes",
        "Cross-year",
    ]
    sources = {
        "PSTOP_12_5": v31["gates"]["PSTOP_12_5"]["checks"],
        "PSTOP_15": v31["gates"]["PSTOP_15"]["checks"],
        "HYBRID_20D_ENTRY_VOL": v32["gates"]["HYBRID_20D_ENTRY_VOL"]["checks"],
    }
    values = pd.DataFrame(
        {
            variant: [int(source[check]) for check in checks]
            for variant, source in sources.items()
        },
        index=short,
    ).T
    annotations = values.replace({1: "PASS", 0: "FAIL"})
    fig, axis = plt.subplots(figsize=(12, 4.6))
    sns.heatmap(
        values,
        annot=annotations,
        fmt="",
        cmap=sns.color_palette(["#D1495B", "#2A9D8F"], as_cmap=True),
        vmin=0,
        vmax=1,
        linewidths=1,
        linecolor="white",
        cbar=False,
        ax=axis,
    )
    axis.set_yticklabels([LABELS[v] for v in sources], rotation=0)
    axis.set_xticklabels(short, rotation=25, ha="right")
    axis.set_title(
        "Frozen admission gates: hybrid fails only the 3/5 episode rule", pad=14
    )
    axis.set_xlabel("")
    axis.set_ylabel("")
    save_figure(fig, "08_admission_gate_dashboard", pdf)


def plot_calibration(pdf: PdfPages) -> None:
    calibration = pd.read_csv(REPORT / "entry_threshold_calibration.csv")
    events = pd.read_csv(REPORT / "variant_HYBRID_20D_ENTRY_VOL_stop_events.csv")
    palette = {
        "12.5% floor": "#277DA1",
        "dynamic interior": "#F4A261",
        "15.0% ceiling": "#D1495B",
    }
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    for rail, frame in calibration.groupby("rail"):
        axes[0].scatter(
            frame["sigma_20d_annualized"],
            frame["allowed_loss"],
            s=25,
            alpha=0.75,
            color=palette[rail],
            label=rail,
        )
    axes[0].set_title("Entry volatility to frozen threshold")
    axes[0].set_xlabel("20d annualized volatility")
    axes[0].set_ylabel("Allowed loss")
    axes[0].xaxis.set_major_formatter(PercentFormatter(1.0))
    axes[0].yaxis.set_major_formatter(PercentFormatter(1.0))
    axes[0].legend(fontsize=8)
    sns.histplot(calibration["allowed_loss"], bins=16, color="#2A9D8F", ax=axes[1])
    axes[1].axvline(0.1375, color="#161A1D", linestyle="--")
    axes[1].set_title("Threshold distribution (216 entries)")
    axes[1].set_xlabel("Allowed loss")
    axes[1].xaxis.set_major_formatter(PercentFormatter(1.0))
    counts = calibration["rail"].value_counts().reindex(palette)
    bars = axes[2].bar(
        ["12.5%\nfloor", "dynamic\ninterior", "15.0%\nceiling"],
        counts,
        color=list(palette.values()),
    )
    for bar, count in zip(bars, counts, strict=True):
        axes[2].text(
            bar.get_x() + bar.get_width() / 2, count + 2, str(count), ha="center"
        )
    axes[2].set_title(f"Rail allocation and {len(events)} realized stops")
    axes[2].set_ylabel("Entry trade count")
    fig.suptitle(
        "v32 one-shot k calibration and entry-frozen thresholds",
        fontsize=15,
        fontweight="bold",
        y=1.03,
    )
    save_figure(fig, "09_threshold_calibration", pdf)


def plot_operations(matrix: pd.DataFrame, pdf: PdfPages) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8))
    labels = [LABELS[v] for v in VARIANTS]
    colors = [COLORS[v] for v in VARIANTS]
    axes[0].bar(labels, matrix.loc[VARIANTS, "stop_event_count"], color=colors)
    axes[0].set_title("Stop events")
    axes[0].set_ylabel("Count")
    axes[1].bar(labels, matrix.loc[VARIANTS, "annual_total_turnover"], color=colors)
    axes[1].set_title("Annual total turnover")
    axes[1].set_ylabel("Turnover multiple")
    axes[2].bar(labels, matrix.loc[VARIANTS, "total_cost"], color=colors)
    axes[2].set_title("Total train cost")
    axes[2].set_ylabel("Portfolio currency")
    for axis in axes:
        axis.tick_params(axis="x", rotation=15)
    fig.suptitle("Operational impact", fontsize=15, fontweight="bold", y=1.03)
    save_figure(fig, "10_stop_activity_turnover_cost", pdf)


def plot_monthly_tail(daily: dict[str, pd.DataFrame], pdf: PdfPages) -> None:
    rows = []
    for variant in VARIANTS:
        monthly = (
            daily[variant]["controlled_return"]
            .add(1)
            .groupby(daily[variant].index.to_period("M"))
            .prod()
            .sub(1)
        )
        rows.extend(
            {"variant": LABELS[variant], "monthly_return": value}
            for value in monthly.to_numpy()
        )
    frame = pd.DataFrame(rows)
    fig, axis = plt.subplots(figsize=(11.5, 6))
    sns.boxplot(
        data=frame,
        x="variant",
        y="monthly_return",
        hue="variant",
        order=[LABELS[v] for v in VARIANTS],
        hue_order=[LABELS[v] for v in VARIANTS],
        palette=[COLORS[v] for v in VARIANTS],
        width=0.62,
        legend=False,
        ax=axis,
    )
    axis.axhline(0, color="#5F6B73", linewidth=1)
    axis.set_title("Monthly return distribution and left tail", pad=14)
    axis.set_xlabel("")
    axis.set_ylabel("Monthly return")
    axis.yaxis.set_major_formatter(PercentFormatter(1.0))
    save_figure(fig, "11_monthly_tail_distribution", pdf)


def main() -> None:
    configure_style()
    FIGURES.mkdir(parents=True, exist_ok=True)
    daily = load_daily()
    matrix = load_matrix()
    annual = load_annual()
    episodes = load_episodes()
    v31 = json.loads((V31_REPORT / "v31_decision.json").read_text())
    v32 = json.loads((REPORT / "v32_decision.json").read_text())
    with PdfPages(FIGURES / "v29_4_D1_v31_endpoints_v32_all_figures.pdf") as pdf:
        plot_executive(daily, matrix, v32["minimum_cagr"], pdf)
        plot_paths(daily, "nav", "Growth of $100", "01_nav_growth", pdf)
        plot_paths(daily, "drawdown", "Underwater curves", "02_drawdown_paths", pdf)
        plot_paths(
            daily,
            "rolling",
            "Rolling 252-session compounded return",
            "03_rolling_252d_returns",
            pdf,
        )
        plot_annual(annual, pdf)
        plot_paths(
            daily,
            "exposure",
            "63-session average long exposure",
            "05_exposure_paths",
            pdf,
        )
        plot_episodes(episodes, pdf)
        plot_risk_return(matrix, v32["minimum_cagr"], pdf)
        plot_gates(v31, v32, pdf)
        plot_calibration(pdf)
        plot_operations(matrix, pdf)
        plot_monthly_tail(daily, pdf)


if __name__ == "__main__":
    main()
