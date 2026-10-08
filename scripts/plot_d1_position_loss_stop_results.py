"""Create the required v29.4 D1 versus v31 result figures."""

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
REPORT = ROOT / "reports/d1_position_loss_stop_v31"
FIGURES = REPORT / "figures"
D1_DAILY = ROOT / "reports/etf_drawdown_overlay_v29_4/variant_D1_daily.csv"

VARIANTS = [
    "D1_CONTROL",
    "PSTOP_5",
    "PSTOP_7_5",
    "PSTOP_10",
    "PSTOP_12_5",
    "PSTOP_15",
]
LABELS = {
    "D1_CONTROL": "v29.4 D1",
    "PSTOP_5": "v31 stop -5%",
    "PSTOP_7_5": "v31 stop -7.5%",
    "PSTOP_10": "v31 stop -10%",
    "PSTOP_12_5": "v31 stop -12.5%",
    "PSTOP_15": "v31 stop -15%",
}
COLORS = {
    "D1_CONTROL": "#161A1D",
    "PSTOP_5": "#BFD7EA",
    "PSTOP_7_5": "#8ECAE6",
    "PSTOP_10": "#4EA8DE",
    "PSTOP_12_5": "#277DA1",
    "PSTOP_15": "#D1495B",
}
LINEWIDTHS = {
    variant: 2.7 if variant in {"D1_CONTROL", "PSTOP_15"} else 1.7
    for variant in VARIANTS
}


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
    daily = {
        "D1_CONTROL": pd.read_csv(D1_DAILY, parse_dates=["date"]).set_index("date")
    }
    for variant in VARIANTS[1:]:
        daily[variant] = pd.read_csv(
            REPORT / f"variant_{variant}_daily.csv", parse_dates=["date"]
        ).set_index("date")
    return daily


def save_figure(fig: plt.Figure, name: str, pdf: PdfPages) -> None:
    fig.text(
        0.99,
        0.995,
        "Train period: 2008-01-02 to 2016-12-30",
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
    axis.tick_params(axis="x", rotation=0)


def plot_nav(daily: dict[str, pd.DataFrame], pdf: PdfPages) -> None:
    fig, axis = plt.subplots(figsize=(12, 6.5))
    for variant in VARIANTS:
        nav = daily[variant]["nav"] / daily[variant]["nav"].iloc[0] * 100
        axis.plot(
            nav.index,
            nav,
            label=LABELS[variant],
            color=COLORS[variant],
            linewidth=LINEWIDTHS[variant],
            alpha=0.98,
        )
    axis.set_title("Growth of $100: v29.4 D1 versus all v31 position stops", pad=14)
    axis.set_ylabel("Portfolio value")
    axis.set_xlabel("")
    axis.legend(ncol=3, loc="upper left")
    format_time_axis(axis)
    save_figure(fig, "01_nav_growth", pdf)


def plot_drawdowns(daily: dict[str, pd.DataFrame], pdf: PdfPages) -> None:
    fig, axis = plt.subplots(figsize=(12, 6.5))
    for variant in VARIANTS:
        drawdown = daily[variant]["nav"].div(daily[variant]["nav"].cummax()).sub(1)
        axis.plot(
            drawdown.index,
            drawdown,
            label=LABELS[variant],
            color=COLORS[variant],
            linewidth=LINEWIDTHS[variant],
        )
    axis.axhline(
        -0.2349485066, color="#161A1D", linestyle="--", linewidth=1, alpha=0.65
    )
    axis.set_title("Underwater curves and realized drawdown penetration", pad=14)
    axis.set_ylabel("Drawdown")
    axis.yaxis.set_major_formatter(PercentFormatter(1.0))
    axis.legend(
        ncol=3,
        loc="lower left",
        frameon=True,
        facecolor="white",
        framealpha=0.92,
    )
    format_time_axis(axis)
    save_figure(fig, "02_drawdown_paths", pdf)


def plot_rolling_returns(daily: dict[str, pd.DataFrame], pdf: PdfPages) -> None:
    fig, axis = plt.subplots(figsize=(12, 6.5))
    for variant in VARIANTS:
        rolling = (
            daily[variant]["controlled_return"]
            .add(1)
            .rolling(252)
            .apply(np.prod, raw=True)
            .sub(1)
        )
        axis.plot(
            rolling.index,
            rolling,
            label=LABELS[variant],
            color=COLORS[variant],
            linewidth=LINEWIDTHS[variant],
        )
    axis.axhline(0, color="#5F6B73", linewidth=1)
    axis.set_title("Rolling 252-session compounded return", pad=14)
    axis.set_ylabel("Rolling return")
    axis.yaxis.set_major_formatter(PercentFormatter(1.0))
    axis.legend(ncol=3, loc="lower left")
    format_time_axis(axis)
    save_figure(fig, "03_rolling_252d_returns", pdf)


def plot_annual_returns(pdf: PdfPages) -> None:
    annual = pd.read_csv(REPORT / "annual_returns.csv")
    pivot = annual.pivot(index="variant", columns="year", values="net_return").loc[
        VARIANTS
    ]
    pivot = pivot.loc[:, pivot.columns >= 2009] * 100
    fig, axis = plt.subplots(figsize=(12, 5.8))
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


def plot_exposure(daily: dict[str, pd.DataFrame], pdf: PdfPages) -> None:
    fig, axis = plt.subplots(figsize=(12, 6.5))
    for variant in VARIANTS:
        exposure = (
            daily[variant]["controlled_long_exposure"].rolling(63, min_periods=1).mean()
        )
        axis.plot(
            exposure.index,
            exposure,
            label=LABELS[variant],
            color=COLORS[variant],
            linewidth=LINEWIDTHS[variant],
        )
    axis.set_title("63-session average long exposure", pad=14)
    axis.set_ylabel("Long exposure")
    axis.set_ylim(0, 1.05)
    axis.yaxis.set_major_formatter(PercentFormatter(1.0))
    axis.legend(ncol=3, loc="lower right")
    format_time_axis(axis)
    save_figure(fig, "05_exposure_paths", pdf)


def plot_fixed_episodes(pdf: PdfPages) -> None:
    episodes = pd.read_csv(REPORT / "deepest_drawdown_comparison.csv")
    pivot = episodes.pivot(
        index="variant", columns="episode", values="candidate_return"
    ).loc[VARIANTS]
    pivot = pivot * 100
    fig, axis = plt.subplots(figsize=(10.5, 5.8))
    sns.heatmap(
        pivot,
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
    axis.set_title(
        "Performance inside D1's five fixed deepest drawdown windows", pad=14
    )
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
            s=190 if variant in {"D1_CONTROL", "PSTOP_15"} else 125,
            color=COLORS[variant],
            edgecolor="white",
            linewidth=1.2,
            zorder=3,
        )
        axis.annotate(
            LABELS[variant],
            (abs(row["maximum_drawdown"]), row["net_cagr"]),
            xytext=(7, 6),
            textcoords="offset points",
            fontsize=9,
        )
    d1_dd = abs(matrix.loc["D1_CONTROL", "maximum_drawdown"])
    axis.axhline(
        minimum_cagr,
        color="#277DA1",
        linestyle="--",
        linewidth=1.3,
        label="8.458% CAGR gate",
    )
    axis.axvline(
        d1_dd, color="#161A1D", linestyle="--", linewidth=1.3, label="D1 Max DD"
    )
    axis.fill_betweenx(
        [minimum_cagr, matrix["net_cagr"].max() + 0.005],
        0,
        d1_dd,
        color="#2A9D8F",
        alpha=0.08,
        label="CAGR + DD feasible region",
    )
    axis.set_title("CAGR versus maximum drawdown", pad=14)
    axis.set_xlabel("Absolute maximum drawdown")
    axis.set_ylabel("Net CAGR")
    axis.xaxis.set_major_formatter(PercentFormatter(1.0))
    axis.yaxis.set_major_formatter(PercentFormatter(1.0))
    axis.legend(loc="lower left")
    save_figure(fig, "07_risk_return_tradeoff", pdf)


def plot_gate_dashboard(decision: dict, pdf: PdfPages) -> None:
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
        "CAGR retention",
        "Max DD",
        "Calmar",
        "Worst month",
        "Cost",
        "Turnover",
        "3/5 episodes",
        "Cross-year",
    ]
    candidates = VARIANTS[1:]
    values = pd.DataFrame(
        {
            variant: [
                int(decision["gates"][variant]["checks"][check]) for check in checks
            ]
            for variant in candidates
        },
        index=short,
    ).T
    annotations = values.replace({1: "PASS", 0: "FAIL"})
    fig, axis = plt.subplots(figsize=(12, 4.8))
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
    axis.set_yticklabels([LABELS[v] for v in candidates], rotation=0)
    axis.set_xticklabels(short, rotation=25, ha="right")
    axis.set_title("Frozen v31 admission-gate dashboard", pad=14)
    axis.set_xlabel("")
    axis.set_ylabel("")
    save_figure(fig, "08_admission_gate_dashboard", pdf)


def plot_operations(matrix: pd.DataFrame, pdf: PdfPages) -> None:
    candidates = VARIANTS[1:]
    labels = [LABELS[v].replace("v31 stop ", "") for v in candidates]
    colors = [COLORS[v] for v in candidates]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8))
    axes[0].bar(labels, matrix.loc[candidates, "stop_event_count"], color=colors)
    axes[0].set_title("Stop events")
    axes[0].set_ylabel("Count")
    axes[1].bar(labels, matrix.loc[candidates, "annual_total_turnover"], color=colors)
    axes[1].axhline(
        matrix.loc["D1_CONTROL", "annual_total_turnover"],
        color="#161A1D",
        linestyle="--",
        label="D1",
    )
    axes[1].set_title("Annual total turnover")
    axes[1].set_ylabel("Turnover multiple")
    axes[1].legend()
    axes[2].bar(labels, matrix.loc[candidates, "total_cost"], color=colors)
    axes[2].axhline(
        matrix.loc["D1_CONTROL", "total_cost"],
        color="#161A1D",
        linestyle="--",
        label="D1",
    )
    axes[2].set_title("Total train cost")
    axes[2].set_ylabel("Portfolio currency")
    axes[2].legend()
    for axis in axes:
        axis.tick_params(axis="x", rotation=0)
    fig.suptitle(
        "Operational impact of position stops", fontsize=15, fontweight="bold", y=1.03
    )
    save_figure(fig, "09_stop_activity_turnover_cost", pdf)


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
    fig, axis = plt.subplots(figsize=(12, 6))
    sns.boxplot(
        data=frame,
        x="variant",
        y="monthly_return",
        hue="variant",
        order=[LABELS[v] for v in VARIANTS],
        hue_order=[LABELS[v] for v in VARIANTS],
        palette=[COLORS[v] for v in VARIANTS],
        width=0.62,
        showfliers=True,
        legend=False,
        ax=axis,
    )
    axis.axhline(0, color="#5F6B73", linewidth=1)
    axis.set_title("Monthly return distribution and left-tail observations", pad=14)
    axis.set_xlabel("")
    axis.set_ylabel("Monthly return")
    axis.yaxis.set_major_formatter(PercentFormatter(1.0))
    axis.tick_params(axis="x", rotation=15)
    save_figure(fig, "10_monthly_tail_distribution", pdf)


def plot_executive_dashboard(
    daily: dict[str, pd.DataFrame],
    matrix: pd.DataFrame,
    minimum_cagr: float,
    pdf: PdfPages,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for variant in VARIANTS:
        nav = daily[variant]["nav"] / daily[variant]["nav"].iloc[0] * 100
        axes[0, 0].plot(
            nav.index,
            nav,
            color=COLORS[variant],
            linewidth=LINEWIDTHS[variant],
            label=LABELS[variant],
        )
        dd = daily[variant]["nav"].div(daily[variant]["nav"].cummax()).sub(1)
        axes[0, 1].plot(
            dd.index, dd, color=COLORS[variant], linewidth=LINEWIDTHS[variant]
        )
    axes[0, 0].set_title("Growth of $100")
    axes[0, 0].legend(ncol=2, fontsize=8)
    axes[0, 1].set_title("Drawdown")
    axes[0, 1].yaxis.set_major_formatter(PercentFormatter(1.0))
    for axis in axes[0]:
        format_time_axis(axis)

    candidates = VARIANTS
    axes[1, 0].bar(
        [LABELS[v].replace("v31 stop ", "") for v in candidates],
        matrix.loc[candidates, "net_cagr"],
        color=[COLORS[v] for v in candidates],
    )
    axes[1, 0].axhline(
        minimum_cagr, color="#277DA1", linestyle="--", label="8.458% gate"
    )
    axes[1, 0].set_title("Net CAGR")
    axes[1, 0].yaxis.set_major_formatter(PercentFormatter(1.0))
    axes[1, 0].legend()
    axes[1, 1].bar(
        [LABELS[v].replace("v31 stop ", "") for v in candidates],
        matrix.loc[candidates, "maximum_drawdown"],
        color=[COLORS[v] for v in candidates],
    )
    axes[1, 1].axhline(
        matrix.loc["D1_CONTROL", "maximum_drawdown"], color="#161A1D", linestyle="--"
    )
    axes[1, 1].set_title("Maximum drawdown")
    axes[1, 1].yaxis.set_major_formatter(PercentFormatter(1.0))
    fig.suptitle(
        "v31 position-stop executive dashboard", fontsize=17, fontweight="bold", y=1.02
    )
    fig.tight_layout()
    save_figure(fig, "00_executive_dashboard", pdf)


def main() -> None:
    configure_style()
    FIGURES.mkdir(parents=True, exist_ok=True)
    daily = load_daily()
    matrix = pd.read_csv(REPORT / "performance_matrix.csv").set_index("variant")
    decision = json.loads((REPORT / "v31_decision.json").read_text())
    with PdfPages(FIGURES / "v29_4_D1_vs_v31_all_figures.pdf") as pdf:
        plot_executive_dashboard(daily, matrix, decision["minimum_cagr"], pdf)
        plot_nav(daily, pdf)
        plot_drawdowns(daily, pdf)
        plot_rolling_returns(daily, pdf)
        plot_annual_returns(pdf)
        plot_exposure(daily, pdf)
        plot_fixed_episodes(pdf)
        plot_risk_return(matrix, decision["minimum_cagr"], pdf)
        plot_gate_dashboard(decision, pdf)
        plot_operations(matrix, pdf)
        plot_monthly_tail(daily, pdf)


if __name__ == "__main__":
    main()
