"""Aggregate the two completed, exposed-calendar static comparisons."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
THRESHOLDS = (1000, 5000)
BANKS = (
    "bay_transferred_original",
    "front_local_matched_window",
    "front_local_expanded_window",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    bindings = {}

    def load(path):
        bindings[str(path.relative_to(REPO))] = sha(path)
        return json.loads(path.read_text())

    rows, fits = [], []
    for year, folder in ((2024, "local_calibration_precheck"), (2026, "local_calibration_2025")):
        directory = HERE.parent / folder
        validation = load(directory / "FULL_VALIDATION.json")
        report_path = directory / "static_comparison_01/REPORT.json"
        report = load(report_path)
        if validation["static_arms_recomputed"] != 6 or not validation["all_static_arms_common_mask"]:
            raise ValueError("Static comparison has not passed common-mask validation")
        if validation["input_bindings"][str(report_path.relative_to(REPO))] != sha(report_path):
            raise ValueError("Report no longer matches the completed validation")
        arms = report["arms"]
        bay = arms[BANKS[0] + "/common_only"]["scores"]["system_brier"]
        denominators = set()
        for bank_name in BANKS:
            own_common = arms[bank_name + "/common_only"]["scores"]["system_brier"]
            for condition in ("common_only", "all_registered"):
                score = arms[bank_name + "/" + condition]["scores"]
                denominators.add(tuple(score[k] for k in ("opportunities", "settled", "missing")))
                rows.append({
                    "evaluation_year": year, "evaluation_threshold_m": 1000,
                    "bank": bank_name, "evidence_condition": condition,
                    "brier": score["system_brier"],
                    "brier_minus_own_common": score["system_brier"] - own_common,
                    "brier_minus_bay_common": score["system_brier"] - bay,
                    "opportunities": score["opportunities"], "settled": score["settled"],
                    "missing": score["missing"],
                })
            bank_path = (
                REPO / report["design"]["original_bay_bank"] if bank_name == BANKS[0]
                else directory / ("bank_matched_01" if bank_name == BANKS[1] else "bank_expanded_01") / "BANK.json"
            )
            bank = load(bank_path)
            check_report = load(bank_path.parent / "CHECK_REPORT.json")
            check_rows = load(bank_path.parent / "CHECK_ROWS.json")
            by_threshold = {}
            for threshold in THRESHOLDS:
                selected = [r for r in check_rows if r["threshold"] == threshold]
                if any("-cutoff-" not in r["opportunity_id"] for r in selected):
                    raise ValueError("Cannot derive check target identity")
                positives = [r for r in selected if r["outcome"] == 1]
                pool = bank["cells"][json.dumps([threshold, "pooled"], separators=(",", ":"))]
                by_threshold[str(threshold)] = {
                    "fit_unique_targets": pool["n"], "fit_positive_targets": pool["positive"],
                    "check_opportunities": len(selected),
                    "check_settled": sum(r["outcome"] is not None for r in selected),
                    "check_positive_opportunities": len(positives),
                    "check_positive_unique_targets": len({r["opportunity_id"].split("-cutoff-", 1)[0] for r in positives}),
                    "zero_positive_check": not positives,
                }
            fits.append({
                "evaluation_year": year, "bank": bank_name,
                "fit_opportunities_two_thresholds": bank["fit_opportunities"],
                "fit_start": check_report["fit_start"],
                "fit_end_exclusive": check_report["fit_end_exclusive"],
                "check_start": check_report["check_start"],
                "check_end_exclusive": check_report["check_end_exclusive"],
                "by_threshold": by_threshold,
                "formal_calibration_guarantee": False,
                "unique_targets_are_not_independent_weather_processes": True,
            })
        if len(denominators) != 1:
            raise ValueError("Within-year static comparison denominators changed")

    for path, expected in bindings.items():
        if sha(REPO / path) != expected:
            raise ValueError("Frozen input changed during summary")
    output = {
        "schema": "disastertrace.two_year_static_summary.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "delta_convention": "arm Brier minus reference Brier; negative is lower loss",
        "rows": rows, "fit_check_support": fits,
        "limitations": {
            "previously_exposed_development_calendars": True,
            "posthoc_best_bank_selection_allowed": False,
            "independent_confirmation": False,
            "new_model_calls": 0,
            "adaptive_policy_rerun": False,
            "all_registered_is_fixed_information_diagnostic": True,
            "local_expanded_changes_region_and_fit_duration": True,
            "historical_first_seen_verified": False,
            "formal_calibration_guarantee": False,
        },
        "input_sha256": bindings, "builder_sha256": sha(Path(__file__)),
    }
    with (HERE / "SUMMARY.json").open("x") as stream:
        json.dump(output, stream, indent=2, allow_nan=False)
        stream.write("\n")
    lines = [
        "# 两年度固定资料对照", "",
        "机器入口为 `SUMMARY.json`。差值定义为当前 Brier 减参照 Brier，负值表示损失降低。",
        "每年三版本映射各保留 common/all 两格，两个年份的既有验证与六格报告均绑定 SHA256。", "",
        "| 年份 | 映射 | 资料 | Brier | 减自身 common | 减 Bay common | 机会/结算/缺失 |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    short = dict(zip(BANKS, ("Bay", "Front matched", "Front expanded"), strict=True))
    for row in rows:
        lines.append(
            f"| {row['evaluation_year']} | {short[row['bank']]} | {row['evidence_condition']} | "
            f"{row['brier']:.9f} | {row['brier_minus_own_common']:+.9f} | "
            f"{row['brier_minus_bay_common']:+.9f} | {row['opportunities']}/{row['settled']}/{row['missing']} |"
        )
    lines += [
        "", "本地 common 映射在 Jan2024 降低损失，在 Jan2026 增加损失；不能事后挑年份或银行来宣称普遍改进。",
        "all 仅为固定可用邻站资料诊断，不是主动调度或共享预算收益，也没有新增模型推理。", "",
        "`fit_check_support` 按阈值列出训练唯一目标/正例，以及检查期正例机会/唯一目标。",
        "Front matched 两年检查期两个阈值均无正例；Front expanded 的 Dec2023 检查期 1000m 无正例，",
        "Dec2025 检查期 1000m 仅 3 个正例机会。无正例或少正例检查不能证明极端类别区分能力或校准保证。",
        "同一小时结果被多个时距复用；唯一目标也不等于独立天气过程。expanded 同时改变地区与拟合天数。", "",
        "两套 January 日历都已暴露于开发。后续主比较与日期应预先固定；旧模型分数不能替换基线后当作新运行。", "",
    ]
    with (HERE / "README_CN.md").open("x") as stream:
        stream.write("\n".join(lines))
    print(json.dumps({"rows": len(rows), "fit_check_records": len(fits), "bound_files": len(bindings)}))


if __name__ == "__main__":
    main()
