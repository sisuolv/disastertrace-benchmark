"""Export descriptive scientific figures, with explicit development denominators."""

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from common import ROOT


def main():
    result = json.loads((ROOT / "analysis/FINAL_RESULTS_02.json").read_text())
    out = ROOT / "reports/figures"
    out.mkdir(exist_ok=False)
    plt.rcParams.update({"font.size": 10, "svg.fonttype": "none", "axes.spines.top": False,
                         "axes.spines.right": False, "figure.facecolor": "white"})
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
    colors = ["#1d6b74", "#dd8439", "#586d9c", "#877c61"]
    models = ["qwen3vl_8b", "qwen3vl_32b", "internvl3_5_8b"]
    labels = ["Qwen3-VL-8B", "Qwen3-VL-32B", "InternVL3.5-8B"]
    rows = {(r["model"], r["condition"]): r for r in result["main_model_table"]}
    x = np.arange(3)
    for i, (condition, label) in enumerate([("full_text", "Full text"), ("full_image", "Full table PNG"), ("active2_image", "Active table PNG, B=2")]):
        axes[0, 0].bar(x + (i - 1) * .25, [100 * rows[m, condition]["grounded_success"] for m in models],
                       width=.24, label=label, color=colors[i])
    axes[0, 0].set_xticks(x, labels)
    axes[0, 0].set_title("A. Product-fact pilot (92 paired episodes)")
    axes[0, 0].set_ylabel("Grounded success (%)")
    axes[0, 0].legend(fontsize=8)
    policies = [("metadata_rule", "Metadata + exact solver"), ("uniform_random_exact_mean", "Uniform random + exact solver"),
                ("latest_issued_rule", "Latest-issued + exact solver"), ("private_certificate_bound", "Private certificate bound")]
    for i, (policy, label) in enumerate(policies):
        data = sorted((r for r in result["program_budget_curves"] if r["policy"] == policy), key=lambda r: r["budget"])
        axes[0, 1].plot([r["budget"] for r in data], [100 * r["grounded_success"] for r in data],
                        label=label, marker="o", color=colors[i], linestyle="--" if i == 3 else "-")
    axes[0, 1].set_title("B. Acquisition bounds and program controls")
    axes[0, 1].set_xlabel("Read budget (cards)")
    axes[0, 1].set_ylabel("Grounded success (%)")
    axes[0, 1].set_xticks(range(5))
    axes[0, 1].legend(fontsize=8, loc="lower right")
    for i, (carrier, label) in enumerate([("full_history", "Delivered source history"), ("last_state", "Previous model state + new source")]):
        selected = {(r["model"], r["carrier"]): r for r in result["state_table_with_costs"]}
        axes[1, 0].bar(np.arange(2) + (i - .5) * .34,
                       [100 * selected[m, carrier]["exact_state"] for m in models[:2]], width=.33,
                       label=label, color=colors[i])
    axes[1, 0].set_xticks(range(2), labels[:2])
    axes[1, 0].set_ylabel("Exact state (%)")
    axes[1, 0].set_title("C. NHC state diagnostic (84 checks, 4 storms)")
    axes[1, 0].legend(fontsize=8)
    conditions = [("full_text", "Original counts"), ("native_vil_full", "Native VIL"),
                  ("compact_counts", "Compact counts"), ("computed_bounds", "Arithmetic aid")]
    natural = {(r["model"], r["condition"]): r for r in result["natural_coverage_table"] + result["natural_assistance_table"]}
    for i, (condition, label) in enumerate(conditions):
        axes[1, 1].bar(np.arange(2) + (i - 1.5) * .2,
                       [100 * natural[m, condition]["grounded_success"] for m in models[:2]],
                       width=.19, label=label, color=colors[i])
    axes[1, 1].set_xticks(range(2), labels[:2])
    axes[1, 1].set_ylabel("Grounded success (%)")
    axes[1, 1].set_title("D. Natural coverage diagnostic (12 frames)")
    axes[1, 1].legend(fontsize=8)
    for ax in axes.flat:
        ax.set_ylim(0, 106)
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
    fig.suptitle("DisasterTrace feasibility diagnostics: descriptive development results", fontsize=14)
    fig.supxlabel("Correlated episodes; no confirmatory intervals. Native pixels, counts, and arithmetic aid are different interfaces.", fontsize=9)
    fig.savefig(out / "feasibility_diagnostics.svg")
    fig.savefig(out / "feasibility_diagnostics.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
