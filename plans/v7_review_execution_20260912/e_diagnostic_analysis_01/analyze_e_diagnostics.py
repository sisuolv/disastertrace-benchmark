"""Compare verified E diagnostics on identical cases without an IID claim."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, record):
    with path.open("x") as stream:
        json.dump(record, stream, indent=2, allow_nan=False)
        stream.write("\n")


def paired(candidate, reference, labels):
    if set(candidate) != set(reference) or set(candidate) != set(labels):
        raise ValueError("Paired cases differ")
    outcomes = Counter()
    for case, expected in labels.items():
        left = candidate[case]["reported_e"] == expected
        right = reference[case]["reported_e"] == expected
        outcomes[
            "both_correct"
            if left and right
            else "candidate_only_correct"
            if left
            else "reference_only_correct"
            if right
            else "both_wrong"
        ] += 1
    return {
        "cases": len(labels),
        **dict(outcomes),
        "net_correct_change": outcomes["candidate_only_correct"]
        - outcomes["reference_only_correct"],
        "inference": "Descriptive paired counts; related cases are not IID trials.",
    }


def main(args):
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "analyze_e_diagnostics.py")
    label_record = load(args.labels)
    labels = label_record["labels"]
    bindings = {str(args.labels.resolve()): digest(args.labels)}
    reports, all_calls, environment_hash = {}, {}, None
    for path in args.verifications:
        verified = load(path)
        if verified["execution_kind"] != "current_evidence_diagnostic":
            raise ValueError("Not a verified fixed-disclosure E diagnostic")
        batch = BASE / Path(verified["batch"]).name
        plan_path = batch / "PLAN.json"
        plan = load(plan_path)
        if digest(plan_path) != verified["plan_sha256"]:
            raise ValueError("Frozen model plan differs")
        if plan["evaluation_bindings"].get(str(args.labels.resolve())) != digest(
            args.labels
        ):
            raise ValueError("Label binding differs")
        environment = batch / "environment.json"
        if digest(environment) != plan["files"]["environment.json"]:
            raise ValueError("Frozen cases changed")
        if environment_hash is not None and digest(environment) != environment_hash:
            raise ValueError(
                "The models did not receive identical case/message definitions"
            )
        environment_hash = digest(environment)
        model = plan["worker_models"]["0"]
        if model in reports:
            raise ValueError("Duplicate model")
        bindings[str(path.resolve())] = digest(path)
        bindings[str(plan_path.resolve())] = digest(plan_path)
        bindings[str(environment.resolve())] = digest(environment)
        cases = load(environment)["cases"]
        case_ids = {row["case_id"] for row in cases}
        if len(case_ids) != len(cases) or case_ids != set(labels):
            raise ValueError("Diagnostic case denominator changed")
        reports[model], all_calls[model] = {}, {}
        for condition, checked in verified["reports"].items():
            trace_path = batch / "worker-0" / condition / "TRACE.json"
            trace = load(trace_path)
            calls = {c["case_id"]: c for c in trace["calls"]}
            if set(calls) != case_ids or len(calls) != len(trace["calls"]):
                raise ValueError("Trace lost or duplicated cases")
            correct = sum(c["reported_e"] == labels[key] for key, c in calls.items())
            invalid = sum(c["error"] is not None for c in calls.values())
            confusion = Counter(
                f"{labels[key]} -> {c['reported_e']}" for key, c in calls.items()
            )
            if (
                correct != checked["correct"]
                or invalid != checked["invalid"]
                or dict(confusion) != checked["confusion"]
                or trace["resource_spent"] != checked["costs"]
            ):
                raise ValueError("Reconstructed descriptive counts differ from audit")
            by_status = {}
            for status in sorted(set(labels.values())):
                keys = [key for key, value in labels.items() if value == status]
                by_status[status] = {
                    "cases": len(keys),
                    "correct": sum(calls[key]["reported_e"] == status for key in keys),
                    "predictions": dict(
                        Counter(calls[key]["reported_e"] for key in keys)
                    ),
                }
            reports[model][condition] = {
                **checked,
                "accuracy": correct / len(cases),
                "by_status": by_status,
                "mean_tokens": checked["costs"]["tokens"] / len(cases),
                "mean_compute_ms": checked["costs"]["compute_ms"] / len(cases),
            }
            all_calls[model][condition] = calls
            bindings[str(trace_path.resolve())] = digest(trace_path)

    pairs = {}
    models = list(reports)
    for model in models:
        for condition in reports[model]:
            if condition != "E_only":
                pairs[f"{model}/{condition} VS {model}/E_only"] = paired(
                    all_calls[model][condition], all_calls[model]["E_only"], labels
                )
    for index, candidate in enumerate(models):
        for reference in models[:index]:
            for condition in reports[candidate]:
                pairs[f"{candidate}/{condition} VS {reference}/{condition}"] = paired(
                    all_calls[candidate][condition],
                    all_calls[reference][condition],
                    labels,
                )
    rows = []
    for case in cases:
        keys = case["requests"]["E_only"]["registered_query_ids"]
        rows.append(
            {
                "case_id": case["case_id"],
                "expected_e": labels[case["case_id"]],
                "registered_query_ids": keys,
                "read_query_ids": case["read_query_ids"],
                "predictions": {
                    model: {
                        condition: calls[case["case_id"]]["reported_e"]
                        for condition, calls in conditions.items()
                    }
                    for model, conditions in all_calls.items()
                },
            }
        )
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cases": len(labels),
        "status_distribution": dict(Counter(labels.values())),
        "case_environment_sha256": environment_hash,
        "reports": reports,
        "paired_comparisons": pairs,
        "input_bindings": bindings,
        "sampling": label_record["sampling"],
        "independent_weather_process_claim": False,
        "new_model_calls": 0,
        "new_api_calls": 0,
        "interpretation": [
            "Balanced real disclosed-product cases; no F outcome or policy benefit is tested.",
            "The canonical table is a declared same-read-product interpretation aid, not hidden Gold.",
            "Both models use text inputs; the VL model does not demonstrate image benefit here.",
            "Conditions change instructions/input length as well as representation; timing includes actual runtime overhead.",
            "Paired counts describe this fixed set; related station/hour cases are not independent weather events.",
        ],
        "implementation_sha256": digest(args.output / "analyze_e_diagnostics.py"),
    }
    write(args.output / "REPORT.json", report)
    write(args.output / "CASES.json", rows)
    lines = [
        "# 同案例的证据判断诊断",
        "",
        "两个模型接收字节一致的 96 个案例和条件定义；每种真实 E 状态各 32 例。",
        "这是固定披露的诊断，不是未来 F 收益或主动调度实验。",
        "",
        "| 模型 | 条件 | 正确 / 96 | supported | refuted | undetermined | token / 例 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for model, conditions in reports.items():
        for condition, r in conditions.items():
            status = r["by_status"]
            lines.append(
                f"| {model} | {condition} | {r['correct']} | "
                f"{status['supported']['correct']}/32 | {status['refuted']['correct']}/32 | "
                f"{status['undetermined']['correct']}/32 | {r['mean_tokens']:.1f} |"
            )
    lines += [
        "",
        "## 成对变化",
        "",
        "下表以右侧条件为参照，完整保留两边同时正确和同时错误的情况。",
        "",
        "| 候选 VS 参照 | 仅候选正确 | 仅参照正确 | 净正确变化 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for label, pair in pairs.items():
        lines.append(
            f"| {label} | {pair.get('candidate_only_correct', 0)} | "
            f"{pair.get('reference_only_correct', 0)} | {pair['net_correct_change']:+d} |"
        )
    lines += [
        "",
        "## 解释边界",
        "",
        "规则示例与标准事实表的效应随模型而变；因此不能假设提示增强或表格化总会改善 C2。",
        "事实表来自同一组已读产品的确定性解释，没有额外隐藏标签，但属于明确辅助条件。",
        "联合 F/E 条件同时改变任务负荷、输出合同和输入长度，准确率差不能归因给单一机制。",
        "Qwen3-VL-32B 在这里只接收文本；本结果不支持图像收益。",
        "记录的 token 与运行时间可复核，但实际耗时包含框架开销，且没有重复种子或独立过程确认。",
        "未来损失、预算调度收益与两种 wrapper 效果由独立的完整日历实验检验。",
        "",
    ]
    (args.output / "REPORT_CN.md").write_text("\n".join(lines))
    print(json.dumps({"models": models, "cases": len(labels), "new_model_calls": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--verifications", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
