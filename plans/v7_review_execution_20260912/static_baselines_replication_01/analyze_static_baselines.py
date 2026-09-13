"""Zero-event and frozen prior-frequency checks on the full common denominator."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from analyze_calendar import digest, load, paired_gain, write
from disastertrace.monitoring_v1.scoring import brier_report


def main(args):
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "analyze_static_baselines.py")
    bank = load(args.bank)
    key = json.dumps([args.threshold, "pooled"], separators=(",", ":"))
    cell = bank["cells"][key]
    prior = (cell["positive"] + 1) / (cell["n"] + 2)
    probabilities = {"zero_event": 0.0, "frozen_prior_month_frequency": prior}
    rows = load(args.analysis / "ROWS.json")
    report = load(args.analysis / "REPORT.json")
    if set(rows) != set(report["arms"]):
        raise ValueError("Analysis arm identities differ")
    anchor = next(iter(rows.values()))
    if any(
        not row["target_id"].endswith(f"-vis-lt-{args.threshold}m") for row in anchor
    ):
        raise ValueError("Threshold differs from the frozen probability cell")
    baselines, comparisons = {}, {}
    for name, probability in probabilities.items():
        predictions = [dict(row, prediction=probability) for row in anchor]
        baselines[name] = {
            "probability": probability,
            "scores": brier_report(predictions),
            "requests": 0,
            "model_calls": 0,
            "scope": "Standalone constant predictor for every registered opportunity; not an override-wrapper trajectory",
        }
        for label, candidate in rows.items():
            comparisons[label + " VS " + name] = paired_gain(candidate, predictions)
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "design": "Post-hoc strong-baseline diagnostic registered after the 2024 base-protocol results; no confirmatory or policy-adaptation claim",
        "threshold_m": args.threshold,
        "baselines": baselines,
        "paired_comparisons": comparisons,
        "prior_cell": cell,
        "prior_bank_version": bank["mapping_version"],
        "prior_semantics": "Pooled source-region prior-month target frequency; no target-calendar outcomes used in the probability formula and no target-region-specific calibration guarantee",
        "input_bindings": {
            str(args.bank.resolve()): digest(args.bank),
            str((args.analysis / "ROWS.json").resolve()): digest(
                args.analysis / "ROWS.json"
            ),
            str((args.analysis / "REPORT.json").resolve()): digest(
                args.analysis / "REPORT.json"
            ),
        },
        "implementation_sha256": digest(args.output / "analyze_static_baselines.py"),
        "paired_bound_implementation_sha256": digest(
            Path(__file__).with_name("analyze_calendar.py")
        ),
        "new_model_calls": 0,
        "new_network_requests": 0,
        "interpretation": "Proper loss can favor a low constant forecast in rare-event calendars. Report this alongside positive-target counts and evidence diagnostics; it does not show useful warning recall.",
    }
    write(args.output / "REPORT.json", result)
    lines = [
        "# 稀有事件的简单强对照",
        "",
        "本对照在看到 2024 年首轮结果后补充，属于明确的事后诊断；不作为预注册确认实验。",
        "两条规则固定为全零概率、此前月份已冻结映射中的总体频率，不使用评测期结果拟合参数。",
        "它们对每个登记机会直接提供常数预测，不是两种修订 wrapper 的执行轨迹。",
        "",
        "| 对照 | 固定概率 | Brier | 可结算机会 | 模型调用 / 查询 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, value in baselines.items():
        lines.append(
            f"| {name} | {value['probability']:.8f} | {value['scores']['system_brier']:.8f} | "
            f"{value['scores']['settled']} | 0 / 0 |"
        )
    lines += [
        "",
        "## 已测模型相对简单对照的差异",
        "",
        "正值表示模型 Brier 更低；所有方法保留同一结果掩膜和全部目标。",
        "",
        "| 模型方法 | 相对全零预测增益 | 相对历史频率增益 |",
        "| --- | ---: | ---: |",
    ]
    for label in rows:
        if label.startswith("model/"):
            zero = comparisons[label + " VS zero_event"]["mean_gain"]
            prior_gain = comparisons[label + " VS frozen_prior_month_frequency"][
                "mean_gain"
            ]
            lines.append(f"| {label} | {zero:+.8f} | {prior_gain:+.8f} |")
    lines += [
        "",
        "全零预测即使取得较小 Brier，也没有识别正例的能力。应联合报告事件率、正例目标数、",
        "概率质量和已冻结的 E 诊断，不因大多数样本无事件而声称预警能力已得到验证。",
        "历史频率来自湾区校准月；迁移到 Front Range 时只是明确的跨区常数基线。",
        "按目标共享未知结果的缺测界与所有程序方法的比较见 REPORT.json。",
        "",
    ]
    (args.output / "REPORT_CN.md").write_text("\n".join(lines))
    print(
        json.dumps(
            {name: value["scores"]["system_brier"] for name, value in baselines.items()}
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--bank", type=Path, required=True)
    parser.add_argument("--threshold", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
