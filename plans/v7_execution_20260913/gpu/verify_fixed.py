"""Rebuild fixed evidence, prompts, tokens, outputs and scores independently."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.aviation import (
    FrozenFrequencyPredictor,
    model_messages,
    parse_response,
    visible_e_status,
)
from disastertrace.monitoring_fixed_v1.contracts import (
    EvidenceBundle,
    Forecast,
    fingerprint,
)
from gpu_worker import digest, save
from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def verify(batch, output):
    output.mkdir(exist_ok=False)
    matrix = HERE.parent / "evidence_bundle/matrix_01"
    bindings = json.loads((matrix / "EVALUATOR_BINDINGS.json").read_text())
    for rel, sha in bindings.items():
        if digest(ROOT / rel) != sha:
            raise ValueError("Evaluator reference changed")
    plan = json.loads((batch / "PLAN.json").read_text())
    plan_sha = digest(batch / "PLAN.json")
    if plan["matrix_manifest_sha256"] != digest(matrix / "MANIFEST.json"):
        raise ValueError("Matrix registry changed")
    for rel, sha in plan["files"].items():
        if digest(batch / rel) != sha:
            raise ValueError("Frozen worker input changed: " + rel)
    for module, symbol in {
        "contracts.py": EvidenceBundle,
        "aviation.py": FrozenFrequencyPredictor,
    }.items():
        imported_path = Path(sys.modules[symbol.__module__].__file__)
        if digest(imported_path) != digest(
            batch / "source/disastertrace/monitoring_fixed_v1" / module
        ):
            raise ValueError("Use this batch's frozen source on PYTHONPATH for replay")
    tokenizer = AutoTokenizer.from_pretrained(
        plan["model"]["directory"], local_files_only=True
    )
    eos = json.loads(
        (Path(plan["model"]["directory"]) / "generation_config.json").read_text()
    )["eos_token_id"]
    eos = eos if isinstance(eos, list) else [eos]
    bank = json.loads((matrix / "BANK.json").read_text())
    predictor = FrozenFrequencyPredictor(bank)
    labels = {
        (r["region"], r["opportunity_id"]): r
        for r in json.loads((matrix / "evaluator/OUTCOMES.json").read_text())
    }
    rows, failures, counts = [], [], Counter()
    durations, worker_counts = [], {}
    for worker, tasks in plan["workers"].items():
        directory = batch / ("worker-" + worker)
        complete = json.loads((directory / "COMPLETE.json").read_text())
        if complete["plan_sha256"] != plan_sha or complete["model_calls"] != len(tasks):
            raise ValueError("Worker completion mismatches")
        hardware = json.loads((directory / "HARDWARE.json").read_text())
        if (
            hardware["count"] != 1
            or "H100" not in hardware["name"]
            or hardware["hostname"] == plan["cci_hostname"]
        ):
            raise ValueError("GPU hardware/host mismatch")
        subtotals = Counter()
        for item in tasks:
            call_id = item["call_id"]
            bundle = EvidenceBundle.restore(
                json.loads((batch / "policy" / (call_id + ".json")).read_text())
            )
            request = json.loads((directory / (call_id + "-request.json")).read_text())
            response = json.loads(
                (directory / (call_id + "-response.json")).read_text()
            )
            messages = model_messages(bundle)
            if request["messages"] != messages or request[
                "messages_sha256"
            ] != fingerprint(messages):
                raise ValueError("Recorded prompt differs from lawful frozen bundle")
            rendered = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            input_ids = tokenizer(rendered, add_special_tokens=False)["input_ids"]
            if (
                request["input_ids"] != input_ids
                or len(input_ids) != item["input_tokens"]
            ):
                raise ValueError("Recorded input tokens differ")
            if (
                len(input_ids) != request["input_tokens"]
                or len(input_ids) != response["input_tokens"]
            ):
                raise ValueError("Input token accounting mismatch")
            if (
                tokenizer.decode(response["output_ids"], skip_special_tokens=True)
                != response["raw"]
            ):
                raise ValueError("Output tokens do not reconstruct raw response")
            if (
                response["raw_sha256"]
                != hashlib.sha256(response["raw"].encode()).hexdigest()
            ):
                raise ValueError("Raw output hash mismatch")
            if (
                response["output_tokens"] != len(response["output_ids"])
                or response["output_tokens"] > plan["max_new_tokens"]
            ):
                raise ValueError("Output token cap or accounting mismatch")
            if response["ended_with_eos"] != bool(
                response["output_ids"] and response["output_ids"][-1] in eos
            ):
                raise ValueError("Finish reason mismatch")
            for record in (request, response):
                if (
                    record["plan_sha256"] != plan_sha
                    or record["bundle_hash"] != bundle.bundle_hash
                ):
                    raise ValueError("Capture belongs to another freeze")
            row = bundle.policy_view()
            baseline = Forecast(**row["baseline"]["forecast"])
            program, details = predictor.predict_with_details(bundle)
            expected_e = visible_e_status(bundle)
            valid, actual_e, error = True, None, None
            try:
                if not response["ended_with_eos"]:
                    raise ValueError("length_or_time_stop")
                model, actual_e = parse_response(response["raw"], bundle)
            except (ValueError, TypeError) as exc:
                model, valid, error = baseline, False, str(exc)
                failures.append({"call_id": call_id, "error": error})
            label = labels[(item["region"], item["opportunity_id"])]
            y = label["outcome"]
            rows.append(
                {
                    **item,
                    "outcome": y,
                    "outcome_status": label["status"],
                    "base": baseline.value,
                    "program": program.value,
                    "model": model.value,
                    "model_valid": valid,
                    "model_e": actual_e,
                    "expected_e": expected_e,
                    "e_correct": actual_e == expected_e,
                    "program_mapping_details": details,
                    "program_evidence_changed_base": program.value != baseline.value,
                    "model_changed_base": model.value != baseline.value,
                    "model_gain": (baseline.value - y) ** 2 - (model.value - y) ** 2
                    if y is not None
                    else None,
                    "program_gain": (baseline.value - y) ** 2 - (program.value - y) ** 2
                    if y is not None
                    else None,
                    "input_tokens": len(input_ids),
                    "output_tokens": response["output_tokens"],
                    "inference_seconds": response["inference_seconds"],
                }
            )
            for key in ("input_tokens", "output_tokens"):
                counts[key] += response[key]
                subtotals[key] += response[key]
            durations.append(response["inference_seconds"])
        if any(subtotals[k] != complete[k] for k in subtotals):
            raise ValueError("Worker token totals differ")
        worker_counts[worker] = len(tasks)
    if len(rows) != plan["expected_calls"] or len({r["call_id"] for r in rows}) != len(
        rows
    ):
        raise ValueError("Incomplete/duplicate frozen matrix")
    groups = defaultdict(list)
    for row in rows:
        groups[(row["region"], row["condition"])].append(row)
    summary = {}
    for (region, condition), group in groups.items():
        settled = [r for r in group if r["outcome"] is not None]
        summary[region + "/" + condition] = {
            "registered": len(group),
            "settled": len(settled),
            "positives": sum(r["outcome"] == 1 for r in settled),
            "model_valid": sum(r["model_valid"] for r in group),
            "e_correct": sum(r["e_correct"] for r in group),
            "E_expected": dict(Counter(r["expected_e"] for r in group)),
            "mean_brier": {
                method: sum((r[method] - r["outcome"]) ** 2 for r in settled)
                / len(settled)
                for method in ["base", "program", "model"]
            },
            "mean_gain": {
                method: sum(r[method + "_gain"] for r in settled) / len(settled)
                for method in ["program", "model"]
            },
            "model_changes": sum(r["model_changed_base"] for r in group),
        }
    responses = {}
    for region in sorted({r["region"] for r in rows}):
        lookup = {
            (r["opportunity_id"], r["condition"]): r
            for r in rows
            if r["region"] == region
        }
        for condition in ["fixed_one", "all_registered"]:
            for method in ["program", "model"]:
                gains = []
                for opportunity_id in sorted({k[0] for k in lookup}):
                    control, treated = (
                        lookup[(opportunity_id, "common_only")],
                        lookup[(opportunity_id, condition)],
                    )
                    if (
                        control["base_hash"] != treated["base_hash"]
                        or control["outcome"] != treated["outcome"]
                    ):
                        raise ValueError("Fixed-current-state comparison is mismatched")
                    if control["outcome"] is not None:
                        y = control["outcome"]
                        gains.append(
                            (control[method] - y) ** 2 - (treated[method] - y) ** 2
                        )
                responses[region + "/" + method + "/" + condition] = {
                    "mean_loss_improvement_over_common_input": sum(gains) / len(gains),
                    "paired": len(gains),
                    "positive": sum(x > 0 for x in gains),
                    "negative": sum(x < 0 for x in gains),
                }
    result = {
        "verified": True,
        "verifier_sha256": digest(Path(__file__)),
        "actual_new_calls": len(rows),
        "workers": worker_counts,
        "tokens": dict(counts),
        "sum_inference_gpu_seconds": sum(durations),
        "valid_outputs": len(rows) - len(failures),
        "failures": failures,
        "E_correct_total": sum(r["e_correct"] for r in rows),
        "summary": summary,
        "fixed_predictor_evidence_responses": responses,
        "plan_sha256": plan_sha,
        "source_outcome_bindings": bindings,
        "limits": [
            "48 exposed development opportunities, 2 positive outcomes; not independent weather confirmation",
            "Native text plus fixed parser representation, not pure native perception or multimodal",
            "Direct candidate probability, no action/gate/delay effects; not the earlier adaptive policy",
            "Archive logical source costs; actual inference tokens and time measured separately",
            "No bootstrap significance or broad 16-hazard generalization from this diagnostic",
        ],
    }
    save(output / "ROWS.json", rows)
    save(output / "REPORT.json", result)
    lines = [
        "# 固定证据 GPU 小矩阵",
        "",
        "本轮是真实新增推理。固定快照、共同基线和当前状态；单独比较资料利用，不能当端到端调度收益。",
        "",
        f"144 次调用中 {result['valid_outputs']} 次输出合同有效，E 判断正确 {result['E_correct_total']}/144。",
        "",
        "| 地区/证据 | 机会 | E正确 | 基线Brier | 统计映射Brier | Qwen Brier | Qwen相对基线增益 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, value in sorted(summary.items()):
        b = value["mean_brier"]
        lines.append(
            f"| {key} | {value['registered']} | {value['e_correct']} | {b['base']:.6f} | {b['program']:.6f} | {b['model']:.6f} | {value['mean_gain']['model']:+.6f} |"
        )
    lines += [
        "",
        "只有48个开发机会、2个正例；三个证据条件和两类预测器不增加独立天气过程数量。",
        "不使用这张表选择灾害、确认期或宣布LLM普遍提高预报。具体逐条输出、失败、费用与资料响应见REPORT.json和ROWS.json。",
        "",
    ]
    (output / "REPORT_CN.md").write_text("\n".join(lines))
    print(
        json.dumps(
            {
                "verified_calls": len(rows),
                "valid": result["valid_outputs"],
                "e_correct": result["E_correct_total"],
                "tokens": dict(counts),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.batch.resolve(), args.output.resolve())
