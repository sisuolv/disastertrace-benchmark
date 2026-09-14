"""Descriptive model comparison with paired task counts and a trivial comparator."""

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1] / "reports/large_model_analysis_01"
rows = json.loads((ROOT / "E_TABLES.json").read_text())
out = ROOT / "figures_02"
out.mkdir(exist_ok=False)
conditions = ("common_only", "fixed_one", "all_registered")
labels = ("Common forecast only", "One supplemental query", "All registered evidence")
fig, axes = plt.subplots(1, 2, figsize=(13, 5.4), sharey=True, constrained_layout=True)
colors = {"qwen235b_fp8": "#155e75", "qwen8b_control": "#ca6b27"}
for ax, head, title in zip(axes, ("e_only", "joint"), ("Evidence task alone", "Evidence and forecast jointly"), strict=True):
    groups = [r for r in rows if r["head"] == head]
    for index, model in enumerate(colors):
        table = {r["condition"]: r for r in groups if r["model"] == model}
        values = [100 * table[c]["correct"] / table[c]["n"] for c in conditions]
        positions = np.arange(3) + (index - 0.5) * 0.31
        bars = ax.bar(positions, values, 0.29, color=colors[model],
                      label="235B MoE Instruct FP8" if index == 0 else "8B control")
        for bar, cond in zip(bars, conditions, strict=True):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.8,
                    f"{table[cond]['correct']}/48", ha="center", fontsize=10)
    unknown = [100 * next(r["always_unknown_correct"] for r in groups if r["condition"] == c) / 48
               for c in conditions]
    ax.plot(np.arange(3), unknown, color="#555555", marker="x", linestyle="--",
            label="Always unknown", linewidth=1.2)
    ax.set_xticks(np.arange(3), labels, fontsize=9)
    ax.set_title(title, fontsize=13, loc="left")
    ax.set_ylim(0, 115)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.18)
    ax.set_axisbelow(True)
axes[0].set_ylabel("Correct factual answers (%)")
axes[1].legend(loc="upper center", bbox_to_anchor=(0.52, -0.12), ncol=1, frameon=False)
fig.suptitle("Two Qwen models show different complete- and partial-evidence errors", fontsize=14)
fig.supxlabel("48 shared development opportunities per condition; descriptive, not independent confirmation", fontsize=10)
for suffix in ("png", "pdf"):
    fig.savefig(out / ("evidence_comparison." + suffix), dpi=180)
plt.close(fig)
manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
(out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"output": str(out), "files": list(manifest)}))
