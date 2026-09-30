from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter


def plot_chances(rows: list[dict], names: dict[str, str], output: Path):
    display = list(reversed(rows))
    fig, ax = plt.subplots(figsize=(9, 5))
    probabilities = [row["win_probability"] for row in display]
    errors = [[row["win_probability"] - row["mc_lower"] for row in display],
              [row["mc_upper"] - row["win_probability"] for row in display]]
    bars = ax.barh([names[row["team_id"]] for row in display], probabilities,
                   color="#267B73", xerr=errors, capsize=3)
    ax.bar_label(bars, labels=[f"{value:.1%}" for value in probabilities], padding=8)
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.set_xlim(0, max(probabilities) * 1.22)
    ax.set_xlabel("Simulated championship probability")
    ax.set_title("Champions Paris 2025: before the playoffs", loc="left", pad=18)
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(0, -0.20, "Error bars show Monte Carlo sampling uncertainty, not uncertainty in the Elo model.",
            transform=ax.transAxes, fontsize=9, color="#555555")
    fig.tight_layout()
    fig.savefig(output, dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_sensitivity(samples: dict[int, list[dict]], names: dict[str, str], output: Path):
    fig, ax = plt.subplots(figsize=(9, 5))
    teams = [row["team_id"] for row in samples[32]]
    colors = ["#267B73", "#A64366", "#6D5CA5", "#BF751C", "#4D6FA7", "#677F33", "#B64B3B", "#555555"]
    for team, color in zip(teams, colors):
        values = [next(row["win_probability"] for row in samples[k] if row["team_id"] == team) for k in samples]
        ax.plot(list(samples), values, marker="o", label=names[team], color=color)
    ax.set_xticks(list(samples))
    ax.set_xlabel("Elo update factor K (larger values respond faster to recent maps)")
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_ylabel("Championship probability")
    ax.set_title("How much does the rating choice change the result?", loc="left", pad=18)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1), frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=160, bbox_inches="tight")
    plt.close(fig)
