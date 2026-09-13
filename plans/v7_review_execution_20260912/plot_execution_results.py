"""Plot recorded full-calendar F loss and certified E coverage without pooling."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path

from analyze_calendar import digest, load, write

BASE = Path(__file__).resolve().parent
COHORTS = (
    ("Bay 2024 | visibility < 5000 m", "calendar_analysis_bay_02", "joint_E_analysis_bay_01"),
    ("Front Range 2024 | visibility < 1000 m", "calendar_analysis_front_02", "joint_E_analysis_front_01"),
    ("Front Range 2026 | visibility < 1000 m", "calendar_analysis_replication_01", "joint_E_analysis_replication_01"),
)
METHODS = ("round_robin", "risk", "batch_complete", "llm")
LABELS = ("Round robin", "Risk", "Batch complete", "LLM selector")


def main(args):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "plot_execution_results.py")
    bindings, values = {}, []
    for title, calendar, joint in COHORTS:
        paths = [BASE / calendar / "REPORT.json", BASE / joint / "REPORT.json"]
        for path in paths:
            bindings[str(path.resolve())] = digest(path)
        forecast, coverage = map(load, paths)
        row = {"title": title, "F_gain": {}, "E_certified": {},
               "joint_E_reference": coverage["references_by_source_budget"]["144"]["joint_E_utility"]}
        for method in METHODS:
            name = "model/qwen3_8b/" + method + "/"
            row["F_gain"][method] = {p: forecast["arms"][name + p]["scores"]["net_realized_gain"]
                                     for p in ("base_bound_override", "persistent_override")}
            row["E_certified"][method] = coverage["arms"][name + "base_bound_override"]["certified_E_opportunities"]
        row["E_opportunities"] = coverage["references_by_source_budget"]["144"]["opportunities"]
        values.append(row)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                         "axes.spines.right": False, "svg.fonttype": "none"})
    fig, axes = plt.subplots(3, 2, figsize=(11.2, 10.3), gridspec_kw={"width_ratios": [1, 1.18]})
    colors = ("#167A7B", "#C26635")
    for index, row in enumerate(values):
        ax, ea = axes[index]
        x = np.arange(len(METHODS))
        for p, protocol in enumerate(("base_bound_override", "persistent_override")):
            heights = np.array([row["F_gain"][m][protocol] * 10000 for m in METHODS])
            places = x + (p - 0.5) * 0.34
            ax.bar(places, heights, width=0.32, color=colors[p], label=("Base-bound" if p == 0 else "Persistent"), zorder=3)
            ax.scatter(places[heights == 0], np.zeros(sum(heights == 0)), color=colors[p], s=18, zorder=4)
        ax.axhline(0, color="#333333", linewidth=0.8)
        ax.set_xticks(x, LABELS, rotation=18, ha="right")
        ax.set_ylabel("Brier gain over shared R base (x 1e-4)")
        ax.set_title(row["title"], loc="left", fontsize=10, fontweight="bold")
        ax.grid(axis="y", alpha=0.2, zorder=0)
        if index == 0:
            ax.legend(loc="lower left", frameon=False)
        resolved = [row["E_certified"][m] for m in METHODS] + [row["joint_E_reference"]]
        bars = ea.bar(np.arange(5), resolved, color=["#457E90"] * 4 + ["#E8E8E3"], edgecolor="#333333", linewidth=0.5, zorder=3)
        bars[-1].set_hatch("///")
        for bar, value in zip(bars, resolved, strict=True):
            ea.text(bar.get_x() + bar.get_width() / 2, value + 75, str(int(value)), ha="center", fontsize=9)
        ea.set_xticks(np.arange(5), [*LABELS, "Joint E upper"], rotation=18, ha="right")
        ea.set_ylim(0, row["E_opportunities"] * 1.02)
        ea.set_ylabel("Certified E / all " + str(row["E_opportunities"]) + " opportunities")
        ea.set_title("Source budget: 144 requests per 72h session", loc="left", fontsize=9)
        ea.grid(axis="y", alpha=0.2, zorder=0)
    fig.suptitle("Qwen3-8B: future loss and available evidence", fontsize=15, y=0.993)
    fig.text(0.02, 0.009,
             "Left: two separately executed model protocols; positive gain is better. Full strong controls are in the tables.\n"
             "Right: base-bound acquisition traces. Hatched bars are offline source-only feasible references, not online methods.\n"
             "E coverage is not model E accuracy or an F objective. Calendars/lead times are not independent weather samples.",
             fontsize=8, color="#444444", va="bottom")
    fig.tight_layout(rect=(0, 0.065, 1, 0.972), h_pad=2.0, w_pad=2.7)
    for suffix in ("png", "svg"):
        fig.savefig(args.output / ("F_and_E_overview." + suffix), dpi=200, facecolor="white")
    plt.close(fig)
    write(args.output / "PLOT_VALUES.json", {"created_at": datetime.now(timezone.utc).isoformat(),
        "cohorts": values, "input_bindings": bindings, "implementation_sha256": digest(args.output / "plot_execution_results.py"),
        "model": "Qwen3-8B", "python_version": platform.python_version(),
        "matplotlib_version": matplotlib.__version__, "numpy_version": np.__version__,
        "new_model_calls": 0, "pooled_statistical_claim": False})
    print(json.dumps({"cohorts": len(values), "panels": 6, "new_model_calls": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
