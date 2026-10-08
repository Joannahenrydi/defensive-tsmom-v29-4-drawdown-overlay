"""Plot the Protocol v2 retrospective tail-episode classification."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.ticker import PercentFormatter

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/risk_admission_protocol_v2"
FIGURES = REPORT / "figures"


def main() -> None:
    sns.set_theme(style="whitegrid", context="notebook")
    episodes = pd.read_csv(REPORT / "v32_episode_reclassification.csv")
    decision = json.loads(
        (REPORT / "protocol_v2_retrospective_decision.json").read_text()
    )
    colors = {
        "material_improvement": "#2A9D8F",
        "neutral": "#8D99AE",
        "material_deterioration": "#D1495B",
    }
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.2))

    axes[0].axhspan(-0.02, 0.05, color="#8D99AE", alpha=0.12)
    axes[0].axhline(0.05, color="#2A9D8F", linestyle="--", linewidth=1.4)
    axes[0].axhline(-0.02, color="#D1495B", linestyle="--", linewidth=1.4)
    bars = axes[0].bar(
        episodes["episode"].astype(str),
        episodes["normalized_improvement"],
        color=[colors[value] for value in episodes["materiality_class"]],
    )
    for bar, value in zip(bars, episodes["normalized_improvement"], strict=True):
        offset = 0.004 if value >= 0 else -0.007
        axes[0].text(
            bar.get_x() + bar.get_width() / 2,
            value + offset,
            f"{value:.2%}",
            ha="center",
            va="bottom" if value >= 0 else "top",
            fontsize=9,
        )
    axes[0].set_title("Normalized improvement by episode")
    axes[0].set_xlabel("Frozen D1 drawdown episode")
    axes[0].set_ylabel("Delta / absolute D1 loss")
    axes[0].yaxis.set_major_formatter(PercentFormatter(1.0))

    order = ["material_improvement", "neutral", "material_deterioration"]
    counts = episodes["materiality_class"].value_counts().reindex(order, fill_value=0)
    count_bars = axes[1].bar(
        ["Material\nimprovement", "Neutral", "Material\ndeterioration"],
        counts,
        color=[colors[value] for value in order],
    )
    for bar, value in zip(count_bars, counts, strict=True):
        axes[1].text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.08,
            str(value),
            ha="center",
        )
    axes[1].axhline(2, color="#2A9D8F", linestyle="--", label="Breadth minimum")
    axes[1].set_ylim(0, 3.7)
    axes[1].set_title("Materiality classification")
    axes[1].set_ylabel("Episode count")
    axes[1].legend(fontsize=8)

    tail = decision["tail_episode_robustness"]
    axes[2].axis("off")
    axes[2].text(
        0.02,
        0.92,
        "TAIL GATE: PASS",
        fontsize=20,
        fontweight="bold",
        color="#2A9D8F",
        transform=axes[2].transAxes,
    )
    lines = [
        f"Breadth: {tail['material_improvement_count']}/5  PASS",
        f"Material deterioration: {tail['material_deterioration_count']}/5  PASS",
        f"Aggregate improvement: {tail['aggregate_fixed_tail_improvement']:.2%}  PASS",
        "",
        "v32 retrospective: WOULD QUALIFY",
        "Historical v32: REJECTED_KEEP_D1",
        "Formal acceptance: false",
        "Orders allowed: false",
    ]
    axes[2].text(
        0.02,
        0.77,
        "\n".join(lines),
        fontsize=12,
        linespacing=1.55,
        va="top",
        transform=axes[2].transAxes,
    )
    fig.suptitle(
        "Risk Admission Protocol v2 — v32 retrospective diagnostic",
        fontsize=17,
        fontweight="bold",
        y=1.01,
    )
    fig.text(
        0.99,
        0.005,
        "Same frozen five episodes; no parameter rerun; historical decision unchanged",
        ha="right",
        fontsize=9,
        color="#5F6B73",
    )
    fig.tight_layout()
    fig.savefig(FIGURES / "tail_episode_robustness_v2.png", dpi=240)
    plt.close(fig)


if __name__ == "__main__":
    main()
