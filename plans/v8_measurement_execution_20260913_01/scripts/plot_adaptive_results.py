"""Plot audited adaptive E coverage and F gain with unscored arms visible."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

LABELS = {
    "A00_follow": "Follow",
    "A01_base_program": "Base / program F",
    "A02_one_program": "One read / program F",
    "A03_batch_program": "Batch / program F",
    "A04_risk_program": "Risk / program F",
    "A05_coverage_program": "Coverage / program F",
    "A06_llm_program": "LLM select / program F",
    "A07_base_llm": "Base / LLM F",
    "A08_one_llm": "One read / LLM F",
    "A09_batch_llm": "Batch / LLM F",
    "A10_risk_llm": "Risk / LLM F",
    "A11_coverage_llm": "Coverage / LLM F",
    "A12_llm_llm": "LLM select / LLM F",
}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = read(args.analysis / "ARMS.json")
    validation = read(args.analysis / "VALIDATION.json")
    assert validation["all_metrics_match_independent_scores"]
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(Path(__file__), args.output / Path(__file__).name)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titleweight": "bold",
            "pdf.fonttype": 42,
        }
    )
    groups = sorted({row["group"] for row in rows})
    figure, axes = plt.subplots(
        len(groups), 2, figsize=(15, 4.8 * len(groups)), squeeze=False
    )
    colours = {"program": "#31556D", "model": "#AB522F", "follow": "#65726F"}
    plotted = []
    for index, group in enumerate(groups):
        data = {r["arm"]: r for r in rows if r["group"] == group}
        available = [r for r in data.values() if r["status"] == "qualified"]
        gains = [r["F_metrics"]["net_realized_gain"] for r in available]
        extent = max([abs(gain) for gain in gains] + [0.00005]) * 1.2
        for column, ax in enumerate(axes[index]):
            ax.set_yticks(range(len(LABELS)), list(LABELS.values()), fontsize=9)
            ax.invert_yaxis()
            ax.set_axisbelow(True)
            ax.grid(axis="x", color="#D8DDE0", linewidth=0.7)
            ax.spines["left"].set_visible(False)
            ax.tick_params(axis="y", length=0)
            if column == 0:
                ax.set_xlim(0, 105)
                ax.set_xlabel("E determined at cutoff (% of registered opportunities)")
            else:
                ax.set_xlim(-extent, extent)
                ax.axvline(0, color="#263841", linewidth=1)
                ax.set_xlabel("Brier gain vs common baseline (positive = better)")
                ax.ticklabel_format(axis="x", style="sci", scilimits=(-3, 3))
        for position, arm in enumerate(LABELS):
            row = data.get(arm)
            if row is None or row["status"] != "qualified":
                for ax in axes[index]:
                    ax.text(
                        0,
                        position,
                        "  unscored",
                        color="#8C9699",
                        fontsize=8,
                        va="center",
                    )
                continue
            colour = colours[
                "follow"
                if arm == "A00_follow"
                else "model"
                if row["config"]["predictor_kind"] == "llm"
                else "program"
            ]
            n = row["registered_opportunities"]
            coverage = row["E_determined_at_cutoff"] / n * 100
            gain = row["F_metrics"]["net_realized_gain"]
            axes[index, 0].barh(position, coverage, color=colour, height=0.65)
            axes[index, 0].text(
                min(coverage + 1, 99),
                position,
                str(row["E_determined_at_cutoff"]),
                fontsize=8,
                va="center",
                ha="left",
            )
            axes[index, 1].barh(position, gain, color=colour, height=0.65)
            if gain == 0:
                axes[index, 1].plot(0, position, "|", color=colour, markersize=9)
            plotted.append(
                {
                    "case": row["case"],
                    "registered_opportunities": n,
                    "E_determined": row["E_determined_at_cutoff"],
                    "brier_gain": gain,
                }
            )
        title = group.replace("__", " m | ").replace("_", " ")
        axes[index, 0].set_title(
            title + "\nEvidence availability", loc="left", fontsize=11
        )
        axes[index, 1].set_title("Future forecast loss", loc="left", fontsize=11)
        if available:
            baseline = available[0]["F_metrics"]["base_brier"]
            positives = available[0]["positive_opportunities"]
            axes[index, 1].text(
                0.98,
                1.02,
                f"Baseline Brier {baseline:.6f}; positives {positives}",
                transform=axes[index, 1].transAxes,
                ha="right",
                fontsize=8,
            )
    title = "Qwen3-235B adaptive development: evidence coverage and future prediction"
    if validation["engineering_rehearsal"]:
        title = "ENGINEERING REHEARSAL - NO MODEL INFERENCE\n" + title
    figure.suptitle(title, fontsize=17, x=0.02, ha="left", y=0.995)
    figure.legend(
        handles=[
            Patch(color=colours[k], label=label)
            for k, label in [
                ("follow", "Follow"),
                ("program", "Program predictor"),
                ("model", "LLM predictor"),
            ]
        ],
        loc="upper center",
        ncol=3,
        bbox_to_anchor=(0.66, 0.975),
        frameon=False,
    )
    figure.text(
        0.02,
        0.006,
        "Exposed 2025-02-03 development calendar. E bar labels show determined counts; axes show percentages.\nProgram timing is declared; model delivery is measured. No independent-process confidence intervals.\nUnfinished or unaudited arms remain unscored.",
        fontsize=9,
        color="#4D5D62",
    )
    figure.tight_layout(rect=(0, 0.035, 1, 0.955), h_pad=2)
    for suffix in ("png", "pdf"):
        figure.savefig(
            args.output / ("adaptive_E_F." + suffix),
            dpi=180,
            bbox_inches="tight",
            facecolor="white",
        )
    plt.close(figure)
    with (args.output / "PROVENANCE.json").open("x") as handle:
        json.dump(
            {
                "analysis_validation_sha256": sha(args.analysis / "VALIDATION.json"),
                "arms_sha256": sha(args.analysis / "ARMS.json"),
                "script_sha256": sha(Path(__file__)),
                "plotted_qualified_arms": plotted,
                "engineering_rehearsal": validation["engineering_rehearsal"],
                "new_model_calls": 0,
            },
            handle,
            indent=2,
        )
        handle.write("\n")
    print(
        json.dumps(
            {
                "groups": len(groups),
                "qualified_arms_plotted": len(plotted),
                "engineering_rehearsal": validation["engineering_rehearsal"],
            }
        )
    )


if __name__ == "__main__":
    main()
