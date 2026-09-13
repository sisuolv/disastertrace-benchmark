"""Describe native report co-occurrence and coverage without claiming storm independence."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from analyze_calendar import digest, load, write

BASE = Path(__file__).resolve().parent
HOUR = 3_600_000_000


def stamp(value):
    return datetime.fromtimestamp(value / 1_000_000, timezone.utc).isoformat()


def profile(directory, threshold):
    audit = load(directory / "REGIONAL_JOIN_AUDIT.json")
    opportunities = [
        row
        for row in load(directory / "public/OPPORTUNITIES.json")
        if row["threshold_m"] == threshold
    ]
    ids = {row["target_id"] for row in opportunities}
    targets = {row["target_id"]: row for row in load(directory / "public/TARGETS.json")}
    outcomes = {
        row["target_id"]: row for row in load(directory / "private/OUTCOMES.json")
    }
    reports = {
        (row["source_id"], row["source_line"]): row
        for row in load(directory / "private/DECODED_REPORTS.json")
    }
    positives, coverage, codes = [], [], Counter()
    for ident in sorted(ids):
        result, target = outcomes[ident], targets[ident]
        coverage.append(
            {
                "target_id": ident,
                "station": target["entity"],
                "physical_start": target["physical_start"],
                "outcome": result["outcome"],
                "quality": result["status"],
            }
        )
        if result["outcome"] == 1:
            if len(result["references"]) != 1:
                raise ValueError(
                    "Positive unique-report target has no unique raw reference"
                )
            reference = result["references"][0]
            native = reports[(reference["source_id"], reference["source_line"])]
            tags = tuple(native["weather"])
            codes[tags] += 1
            positives.append(
                {
                    "target_id": ident,
                    "station": target["entity"],
                    "physical_start": target["physical_start"],
                    "time_utc": stamp(target["physical_start"]),
                    "weather_codes": list(tags),
                    "raw_report": native["raw"],
                    "reference": reference,
                }
            )
    check = audit["by_threshold"][str(threshold)]
    if (
        len(opportunities) != check["opportunities"]
        or len(positives) != check["unique_positive_targets"]
        or sum(outcomes[row["target_id"]]["outcome"] == 1 for row in opportunities)
        != check["positive_opportunities"]
    ):
        raise ValueError("Source audit and target-level positive counts differ")
    # This fixed gap rule is a descriptive grouping, not a meteorological attribution.
    groups = []
    for row in sorted(
        positives, key=lambda row: (row["physical_start"], row["station"])
    ):
        if (
            not groups
            or row["physical_start"] - groups[-1][-1]["physical_start"] > 6 * HOUR
        ):
            groups.append([])
        groups[-1].append(row)
    segments = [
        {
            "segment": number,
            "start": group[0]["time_utc"],
            "end": group[-1]["time_utc"],
            "positive_target_slots": len(group),
            "stations": sorted({row["station"] for row in group}),
            "weather_codes": sorted(
                {code for row in group for code in row["weather_codes"]}
            ),
        }
        for number, group in enumerate(groups)
    ]
    return {
        "dataset": directory.name,
        "threshold_m": threshold,
        "opportunities": len(opportunities),
        "unique_target_slots": len(ids),
        "unique_positive_slots": len(positives),
        "positive_opportunities": check["positive_opportunities"],
        "unresolved_target_slots": sum(row["outcome"] is None for row in coverage),
        "weather_code_combinations": [
            {"codes": list(tags), "count": count} for tags, count in codes.items()
        ],
        "positive_reports": positives,
        "coverage": coverage,
        "exploratory_6h_gap_segments": segments,
        "independent_process_count": None,
        "input_bindings": {
            str(path.resolve()): digest(path)
            for path in [
                directory / "REGIONAL_JOIN_AUDIT.json",
                directory / "public/OPPORTUNITIES.json",
                directory / "public/TARGETS.json",
                directory / "private/OUTCOMES.json",
                directory / "private/DECODED_REPORTS.json",
            ]
        },
    }


def draw(rows, diagnostic, output):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
        }
    )
    figure, axes = plt.subplots(3, 1, figsize=(12.8, 7.0), constrained_layout=True)
    for axis, row in zip(axes, rows):
        coverage = row["coverage"]
        stations = sorted({item["station"] for item in coverage})
        start = min(item["physical_start"] for item in coverage)
        end = max(item["physical_start"] for item in coverage)
        values = np.full((len(stations), (end - start) // HOUR + 1), 3)
        for item in coverage:
            values[
                stations.index(item["station"]),
                (item["physical_start"] - start) // HOUR,
            ] = 2 if item["outcome"] is None else item["outcome"]
        left, right = [
            mdates.date2num(datetime.fromtimestamp(value / 1_000_000, timezone.utc))
            for value in (start, end + HOUR)
        ]
        axis.imshow(
            values,
            interpolation="nearest",
            aspect="auto",
            origin="lower",
            vmin=0,
            vmax=3,
            cmap=ListedColormap(["#E2E7E9", "#D45B36", "#263D53", "#FFFFFF"]),
            extent=(left, right, -0.5, len(stations) - 0.5),
        )
        axis.set_yticks(range(len(stations)), stations)
        axis.xaxis_date()
        axis.xaxis.set_major_locator(mdates.DayLocator(interval=4))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        title = (
            row["dataset"]
            .replace("extension_", "")
            .replace("_01", "")
            .replace("_03", "")
        )
        axis.set_title(
            f"{title} | visibility < {row['threshold_m']} m | "
            f"{row['unique_positive_slots']} positive / {row['unique_target_slots']} target slots; "
            f"{row['unresolved_target_slots']} unresolved",
            loc="left",
            fontsize=10,
            pad=9,
        )
    figure.suptitle(
        "Native report coverage in the fixed evaluation calendars",
        fontsize=17,
        fontfamily="DejaVu Serif",
    )
    axes[-1].legend(
        handles=[
            Patch(facecolor=color, label=label)
            for color, label in [
                ("#E2E7E9", "Reported event absent"),
                ("#D45B36", "Reported event present"),
                ("#263D53", "Unresolved report"),
            ]
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.25),
        ncol=3,
        frameon=False,
    )
    for extension in ("svg", "png"):
        figure.savefig(output / ("report_coverage." + extension), dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(10.6, 4.8), constrained_layout=True)
    conditions = ["joint_F_E", "E_only", "E_examples", "E_fact_table"]
    positions = np.arange(len(conditions))
    for index, (model, color) in enumerate(
        [("qwen3_8b", "#237B8A"), ("qwen3vl_32b", "#D45B36")]
    ):
        results = diagnostic["reports"][model]
        bars = axis.bar(
            positions + (index - 0.5) * 0.35,
            [results[condition]["correct"] / 96 * 100 for condition in conditions],
            width=0.35,
            color=color,
            label=model,
        )
        axis.bar_label(
            bars,
            labels=[f"{results[c]['correct']}/96" for c in conditions],
            padding=3,
            fontsize=10,
        )
    axis.set_xticks(
        positions,
        ["Joint F + E", "E only", "E + rule examples", "E + canonical fact table"],
    )
    axis.set_ylim(0, 105)
    axis.set_ylabel("Correct E status (%)")
    axis.set_title(
        "Same-case evidence diagnostic: assistance effects differ by model",
        loc="left",
        pad=16,
        fontsize=15,
        fontfamily="DejaVu Serif",
    )
    axis.legend(loc="upper left", frameon=False)
    axis.text(
        0.0,
        -0.16,
        "Balanced fixed-disclosure cases; text inputs; no independent-event or future-forecast gain claim.",
        transform=axis.transAxes,
        fontsize=9,
        color="#41505A",
    )
    for extension in ("svg", "png"):
        figure.savefig(output / ("e_diagnostic." + extension), dpi=160)
    plt.close(figure)
    return {
        "matplotlib": matplotlib.__version__,
        "numpy": np.__version__,
        "figures": {
            path.name: digest(path)
            for path in sorted(output.glob("*.svg")) + sorted(output.glob("*.png"))
        },
    }


def main(args):
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "profile_report_events.py")
    rows = [
        profile(BASE / name, threshold)
        for name, threshold in [
            ("extension_bay_area_01", 5000),
            ("extension_front_range_03", 1000),
            ("replication_2026_01", 1000),
        ]
    ]
    write(
        args.output / "REPORT.json",
        {
            "cohorts": rows,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "new_model_calls": 0,
            "scope": "Native reported weather-code co-occurrence, not causal attribution; 6h gap segments are exploratory and not independent storms",
        },
    )
    lines = [
        "# 真实正例、天气码与连续日历覆盖",
        "",
        "每个正例只计算一次目标报告槽位，多个提前量不重复计为事件。天气码来自原生 METAR；",
        "共现说明报告记载，不证明某种天气是全部能见度下降的独立物理成因。",
        "",
        "| 日历 | 阈值 | 名义机会 | 正例报告槽位 | 未结算报告槽位 | 探索性时间段 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['dataset']} | {row['threshold_m']} m | {row['opportunities']} | "
            f"{row['unique_positive_slots']} | {row['unresolved_target_slots']} | {len(row['exploratory_6h_gap_segments'])} |"
        )
    for row in rows:
        lines += ["", "## " + row["dataset"], ""]
        lines += [
            f"- `{', '.join(item['codes']) or 'no weather code'}`: {item['count']} 个正例报告槽位。"
            for item in row["weather_code_combinations"]
        ]
    lines += [
        "",
        "## 解释边界",
        "",
        "RA 为雨，BR 为轻雾，SN 为雪，FZFG 为冻雾；强弱前缀和共现组合保持原样。",
        "湾区宽阈值正例不能整体命名为纯浓雾。Front Range 的严格正例涉及冻雾与降雪，",
        "也不能在没有额外成因合同的情况下重复计入多个独立灾害。",
        "时间段按区域内相邻正例间隔不超过 6 小时连接，是看到数据后的描述规则；它不提供",
        "天气过程独立性、事件分割真实性或论文确认集资格。正式独立过程分组仍需单独冻结。",
        "",
    ]
    (args.output / "REPORT_CN.md").write_text("\n".join(lines))
    if args.figures:
        record = draw(
            rows, load(BASE / "e_diagnostic_analysis_01/REPORT.json"), args.output
        )
        write(args.output / "FIGURES.json", record)
    print(json.dumps({row["dataset"]: row["unique_positive_slots"] for row in rows}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--figures", action="store_true")
    main(parser.parse_args())
