"""Plot the registered fixed-selector factorial controls without confidence claims."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parents[1]


def main():
    original = HERE / "reports/program_calendar_analysis_01"
    out = original / "figures_01"
    out.mkdir(exist_ok=False)
    rows = json.loads((original / "ARMS.json").read_text())
    arms = ["P06_qp", "P06_qs", "P06_gp", "P06_gs"]
    labels = [
        "Fixed quota\nPrivate",
        "Fixed quota\nShared",
        "Global budget\nPrivate",
        "Global budget\nShared",
    ]
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    for i, threshold in enumerate((1000, 5000)):
        selected = {
            r["arm"]: r
            for r in rows
            if r["threshold_m"] == threshold and r["protocol"] == "base_bound_override"
        }
        color = "#146466" if threshold == 1000 else "#b75c32"
        counts = [selected[a]["E_determined"] for a in arms]
        gains = [selected[a]["gain_vs_follow"] for a in arms]
        ax = axes[i, 0]
        ax.bar(labels, counts, color=color, width=0.64)
        for j, value in enumerate(counts):
            ax.text(j, value + 4, f"{value}/216", ha="center")
        ax.set_ylim(0, 245)
        ax.set_ylabel("Determinate E opportunities")
        ax.set_title(f"Visibility below {threshold / 1000:g} km: lawful evidence")
        ax = axes[i, 1]
        ax.bar(labels, gains, color=color, width=0.64)
        ax.axhline(0, color="#444444", linewidth=1)
        ax.set_title(f"Visibility below {threshold / 1000:g} km: future forecast")
        ax.set_ylabel("Follow Brier - method Brier\n(positive is improvement)")
        ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
        for target in axes[i]:
            target.set_axisbelow(True)
            target.grid(axis="y", alpha=0.2)
    fig.suptitle(
        "Shared evidence can determine more facts without improving forecasts",
        fontsize=17,
    )
    fig.supxlabel(
        "Fixed round-robin selector; 72-query budget; base-bound override; one exposed development day.\nNo independent-process confidence intervals; columns and thresholds retain distinct scales.",
        fontsize=10,
    )
    for ext in ("png", "pdf"):
        fig.savefig(out / ("program_controls." + ext), dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(str(out))


if __name__ == "__main__":
    main()
