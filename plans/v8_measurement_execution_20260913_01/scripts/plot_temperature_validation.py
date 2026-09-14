"""Export a descriptive figure from the already-scored native temperature report."""

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "temperature_extension_01/decoded_01/REPORT.json"
OUT = ROOT / "temperature_extension_01/figures_01"


def main():
    report = json.loads(SOURCE.read_text())
    OUT.mkdir(exist_ok=False)
    plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    colors = ["#14605E", "#BD5D34"]
    leads = sorted(map(int, report["by_lead_hours"]))
    for name, color in zip(("mean", "median"), colors):
        axes[0, 0].plot(leads, [report["by_lead_hours"][str(h)]["arms"][name]["MAE_K"] for h in leads],
                        marker="o", ms=3, color=color, label="51-member " + name)
    axes[0, 0].set(title="A. Point-temperature error", xlabel="Lead time (hours)", ylabel="MAE (K)")
    axes[0, 0].legend(frameon=False)
    for name, label, color in [("cold_point_lt_273_15K", "Below 0 C", colors[0]),
                                ("hot_point_ge_303_15K", "At least 30 C", colors[1])]:
        axes[0, 1].plot(leads, [report["by_lead_hours"][str(h)][name]["raw_ensemble_Brier"] for h in leads],
                        marker="o", ms=3, color=color, label=label)
    axes[0, 1].set(title="B. Raw ensemble event probabilities", xlabel="Lead time (hours)", ylabel="Brier loss")
    axes[0, 1].legend(frameon=False)
    seasons = ["DJF", "MAM", "JJA", "SON"]
    xx = np.arange(len(seasons))
    for i, (name, color) in enumerate(zip(("mean", "median"), colors)):
        axes[1, 0].bar(xx+(i-0.5)*0.32, [report["by_season"][s]["arms"][name]["MAE_K"] for s in seasons],
                      width=0.32, color=color, label=name)
    axes[1, 0].set(title="C. Seasonal coverage", xticks=xx, xticklabels=seasons, ylabel="MAE (K)")
    axes[1, 0].legend(frameon=False)
    bars = axes[1, 1].bar(seasons, [report["by_season"][s]["missing_native_outcome"] for s in seasons], color="#A2A6A0")
    axes[1, 1].bar_label(bars, padding=3)
    axes[1, 1].set(title="D. Missing outcomes remain registered", ylabel="Missing opportunity outcomes", ylim=(0, 190))
    for ax in axes.flat:
        ax.set_axisbelow(True)
        ax.grid(axis="y", color="#D9DDD8", linewidth=0.6)
    fig.suptitle("Native EUPP / DWD temperature validation", fontsize=17, y=0.99)
    fig.text(0.5, 0.945, "Berus station, 2017-2018 initializations | 14,600 future opportunities | 14,430 settled", ha="center")
    fig.text(0.5, 0.025, "Repeated leads and adjacent hours are dependent. No confidence intervals or independent confirmation.\n"
             "Hot/cold point targets do not establish heatwaves, cold waves, or calibrated probability skill.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.075, 1, 0.92), h_pad=2, w_pad=2)
    for suffix in ("png", "pdf"):
        fig.savefig(OUT / ("temperature_validation." + suffix), dpi=180)
    plt.close(fig)
    (OUT / "MANIFEST.json").write_text(json.dumps({"source_report_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file()}}, indent=2)+"\n")


if __name__ == "__main__":
    main()
