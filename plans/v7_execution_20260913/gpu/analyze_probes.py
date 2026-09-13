"""Join the three retained experiments without treating prompt variants as storms."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from gpu_worker import digest, save
from launch_fixed import requested_gpus

HERE = Path(__file__).resolve().parent


def main():
    output = HERE / "combined_analysis_01"
    output.mkdir(exist_ok=False)
    sources = [
        "verification_01",
        "prompt_verification_01",
        "fact_truth_verification_01",
    ]
    all_rows, inputs, totals = [], {}, Counter()
    for name in sources:
        report_path, rows_path = HERE / name / "REPORT.json", HERE / name / "ROWS.json"
        report = json.loads(report_path.read_text())
        if not report["verified"]:
            raise ValueError("Unverified input")
        totals["actual_calls"] += report["actual_new_calls"]
        totals.update(report["tokens"])
        inputs[name] = {"report": digest(report_path), "rows": digest(rows_path)}
        for row in json.loads(rows_path.read_text()):
            all_rows.append(
                {
                    **row,
                    "prompt_variant": row.get(
                        "prompt_variant", "original_filled_example"
                    ),
                }
            )
    variants = {}
    for name in sorted({r["prompt_variant"] for r in all_rows}):
        group = [r for r in all_rows if r["prompt_variant"] == name]
        confusion = Counter((r["expected_e"], r["model_e"]) for r in group)
        variants[name] = {
            "calls": len(group),
            "E_correct": sum(r["e_correct"] for r in group),
            "E_accuracy": sum(r["e_correct"] for r in group) / len(group),
            "probability_counts": {
                str(k): v for k, v in Counter(r["model"] for r in group).items()
            },
            "E_confusion": [
                {"expected": a, "predicted": b, "count": count}
                for (a, b), count in sorted(confusion.items())
            ],
            "baseline_copies": sum(
                r["model"] == r["base"] for r in group if r["model"] is not None
            ),
            "F_submissions": sum(r["model"] is not None for r in group),
        }
    pairs = {}
    for row in all_rows:
        if row["prompt_variant"] in {
            "explicit_truth_E_only",
            "explicit_truth_joint_EF",
        }:
            pairs.setdefault(row["bundle_hash"], {})[row["prompt_variant"]] = row
    counts = Counter()
    for pair in pairs.values():
        if len(pair) != 2:
            raise ValueError("Unpaired task-head comparison")
        a, b = pair["explicit_truth_E_only"], pair["explicit_truth_joint_EF"]
        if a["expected_e"] != b["expected_e"]:
            raise ValueError("Changed E reference")
        counts[(a["e_correct"], b["e_correct"])] += 1
    events, jobs = [], []
    for name in ["fixed_matrix_01", "prompt_probe_01", "fact_truth_probe_01"]:
        for path in sorted((HERE / name / "status_01").glob("pt-*.json")):
            job = json.loads(path.read_text())
            count = requested_gpus(job)
            if job["state"] != "SUCCEEDED" or count != 1:
                raise ValueError("Expected successful single GPU job")
            start = datetime.fromisoformat(job["create_time"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(job["complete_time"].replace("Z", "+00:00"))
            events.extend([(start, 1), (end, -1)])
            jobs.append(
                {
                    "job_id": job["name"],
                    "batch": name,
                    "created": job["create_time"],
                    "completed": job["complete_time"],
                    "state": job["state"],
                    "gpus": count,
                }
            )
    active = peak = 0
    for _, delta in sorted(events):
        active += delta
        peak = max(peak, active)
    if active != 0 or peak > 4 or len(jobs) != 12:
        raise ValueError("GPU scope violated or incomplete")
    result = {
        "totals": dict(totals),
        "total_tokens": totals["input_tokens"] + totals["output_tokens"],
        "variants": variants,
        "paired_head_counts": [
            {"E_only_correct": a, "joint_correct": b, "count": n}
            for (a, b), n in sorted(counts.items())
        ],
        "jobs": jobs,
        "max_requested_gpu_overlap": peak,
        "active_requested_gpus_at_last_account_check": json.loads(
            (HERE / "fact_truth_probe_01/status_01/ACCOUNT.json").read_text()
        )["active_requested_gpus"],
        "inputs": inputs,
        "source_sha256": digest(Path(__file__)),
        "scope": "720 calls on 144 evidence conditions from48 exposed opportunities; no independent weather confirmation",
        "causal_limits": [
            "Changed example sensitivity is paired at fixed input",
            "Explicit truth changes wording/schema; not an isolated label-renaming estimate",
            "E-only vs joint uses shared truth wording but different requested tasks",
            "No significance claim from correlated repeated conditions",
            "E-only has no F prediction; all missing/invalid model results remain represented",
        ],
    }
    save(output / "REPORT.json", result)
    lines = [
        "# 固定证据与提示语义诊断总表",
        "",
        f"本轮三批共 {totals['actual_calls']} 次真实调用，{result['total_tokens']:,} tokens；12 个单 H100 作业成功，最大并发4，最终0张仍占用。",
        "",
        "| 条件 | 调用 | E正确 | F输出行为 |",
        "| --- | ---: | ---: | --- |",
    ]
    descriptions = {
        "original_filled_example": "全部复制示例0.1/undetermined",
        "alternate_filled_example": "全部复制示例0.7/refuted",
        "no_filled_example": "全部复制共同基线；E常把有证据误作命题为真",
        "explicit_truth_E_only": "只提交E，不计F成绩",
        "explicit_truth_joint_EF": "大多保留基线；11次无补证条件输出0.5",
    }
    for name, value in variants.items():
        lines.append(
            f"| {name} | {value['calls']} | {value['E_correct']}/{value['calls']} | {descriptions[name]} |"
        )
    lines += [
        "",
        "这些结果证明当前接口、输入响应及E/F干扰可以被单独测量；并不证明LLM增益或完整C1/C2跨过程贡献。",
        "",
        "填值示例引起复制的失败必须保留。去除示例后E错误仍在，不能把所有错误都归于格式示例。显式真值改善后的仍存错误、少量支持真命题的低召回，以及部分取证时联合任务过早判假的情况，需要在独立材料中继续验证。",
        "",
        "联合任务在无补证时有11次输出0.5，补证后的表面改善可能来自避免自造的基线退化；必须同时报告共同专业/研究基线。不能把这种差异直接叫主动取证价值。",
        "",
        "后续不扩大相同模型调用矩阵；先固定无填值示例的明确合同，E-only/F-only分开，联合头作为消融；再用更强本地基线和有物理增量依据的资料检验F。",
        "",
    ]
    (output / "REPORT_CN.md").write_text("\n".join(lines))
    print(
        json.dumps(
            {
                "calls": totals["actual_calls"],
                "tokens": result["total_tokens"],
                "jobs": len(jobs),
                "max_gpus": peak,
            }
        )
    )


if __name__ == "__main__":
    main()
