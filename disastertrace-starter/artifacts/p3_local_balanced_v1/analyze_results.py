"""Deterministic descriptive tables from the independently verified local report."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from disastertrace.automated.common import fingerprint, read_jsonl
from disastertrace.controlled.schema import parse_decision
from disastertrace.local_eval.storage import inventory, read, seal, verify_seal, write

HERE = Path(__file__).resolve().parent


def generate():
    report_root = HERE / "model_report"
    verify_seal(report_root)
    report = read(report_root / "report.json")
    audited = read(report_root / "audit.json")
    plan = read(HERE / "execution/execution.json")
    if (
        report["origin"] != "local_model_vllm"
        or audited["origin"] != "local_model_vllm"
        or report["execution_id"] != plan["execution_id"]
        or report["audit_id"] != audited["audit_id"]
    ):
        raise ValueError("matching independently audited local model report required")
    run = Path(plan["run_path"])
    if inventory(run) != audited["run_files"]:
        raise ValueError("run changed since independent audit")
    slots = read_jsonl(HERE / "execution/dataset/schedule.jsonl")
    captures = [read(p) for p in sorted((run / "captures").glob("*.json"))]
    lookup = {(s["episode_id"], s["checkpoint_id"], s["method"]): s for s in slots}
    detailed = defaultdict(Counter)
    after_evidence, invalid, per_method_tokens = {}, [], defaultdict(Counter)
    valid_only = defaultdict(Counter)
    for method, score in report["methods"].items():
        after_evidence[method] = {"correct": 0, "planned": 0}
        for row in score["per_checkpoint"]:
            slot = lookup[row["episode_id"], row["checkpoint_id"], method]
            if row["status"] == "ok":
                valid_only[method].update(
                    {
                        k: row["counts"][k]
                        for k in (
                            "checkpoints",
                            "all_correct",
                            "known",
                            "unknown",
                            "known_value_correct",
                            "known_grounded_correct",
                            "unknown_correct",
                            "action_correct",
                        )
                    }
                )
            key = (method, slot["family"], slot["case"])
            detailed[key].update(
                planned=1,
                schema_valid=row["counts"]["schema_valid"],
                all_correct=row["counts"]["all_correct"],
                known_grounded=row["counts"]["known_grounded_correct"],
                known_planned=row["counts"]["known"],
            )
            if row["checkpoint_id"] != "c0":
                after_evidence[method]["planned"] += 1
                after_evidence[method]["correct"] += row["counts"]["all_correct"]
    batch_seconds, completion_lengths = {}, []
    for capture in captures:
        slot = slots[capture["slot_index"]]
        method = slot["method"]
        per_method_tokens[method].update(
            prompt=capture["prompt_tokens"],
            completion=capture["completion_tokens"],
            reasoning=capture["extracted"]["reasoning_tokens"],
            final_content=capture["extracted"]["content_tokens"],
        )
        seconds = capture["batch_wall_seconds"]
        index = capture["batch_index"]
        if index in batch_seconds and batch_seconds[index] != seconds:
            raise ValueError("inconsistent shared batch latency")
        batch_seconds[index] = seconds
        completion_lengths.append(capture["completion_tokens"])
        try:
            parse_decision(capture["extracted"]["content"])
        except (ValueError, KeyError, TypeError, RecursionError) as exc:
            invalid.append(
                {
                    "slot_index": slot["slot_index"],
                    "slot_id": slot["slot_id"],
                    "method": method,
                    "finish_reason": capture["result"]["finish_reason"],
                    "completion_tokens": capture["completion_tokens"],
                    "extraction_error": capture["extracted"]["extraction_error"],
                    "parser_error_type": type(exc).__name__,
                    "parser_message": str(exc),
                }
            )
    elapsed = sum(batch_seconds.values())
    collect_result = read(HERE / "runtime/collect_result.json")
    wall = (
        datetime.fromisoformat(collect_result["finished_at"])
        - datetime.fromisoformat(collect_result["started_at"])
    ).total_seconds()
    analysis = {
        "execution_id": report["execution_id"],
        "audit_id": report["audit_id"],
        "report_package_id": read(report_root / "manifest.json")["package_id"],
        "family_case_method": [
            {"method": k[0], "family": k[1], "case": k[2], **v} for k, v in sorted(detailed.items())
        ],
        "after_first_evidence": after_evidence,
        "invalid_outputs": invalid,
        "invalid_parser_error_types": dict(Counter(r["parser_error_type"] for r in invalid)),
        "valid_only_conditional_diagnostic": {m: dict(v) for m, v in valid_only.items()},
        "valid_only_is_not_primary_score": True,
        "field_error_reasons": dict(Counter(r["reason"] for r in report["errors"]["fields"])),
        "per_method_tokens": {m: dict(v) for m, v in per_method_tokens.items()},
        "generation_batches": len(batch_seconds),
        "sum_generation_batch_seconds": elapsed,
        "collector_subprocess_wall_seconds": wall,
        "aggregate_output_tokens_per_generation_second": sum(completion_lengths) / elapsed
        if elapsed
        else None,
        "completion_tokens_min": min(completion_lengths) if completion_lengths else None,
        "completion_tokens_max": max(completion_lengths) if completion_lengths else None,
        "not_per_request_latency": True,
        "no_confidence_interval_independence_claim": True,
        "primary_score_denominators_unchanged": True,
    }
    analysis["analysis_id"] = fingerprint(analysis)
    lines = [
        "# Qwen3-8B balanced development results",
        "",
        "Automatically generated from independently audited captures.",
        "",
        "| Method | Schema | Known Value | Known Grounded | Unknown | All Correct | Action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    names = [
        "schema_success",
        "known_value_accuracy",
        "known_grounded_accuracy",
        "unknown_accuracy",
        "all_correct_checkpoints",
        "action_accuracy",
    ]
    for method, score in report["methods"].items():
        values = [
            f"{score['metrics'][n]['numerator']}/{score['metrics'][n]['denominator']}"
            for n in names
        ]
        lines.append("| " + " | ".join([method, *values]) + " |")
    lines += [
        "",
        "| Family | Method | Schema | Length | Screen |",
        "| --- | --- | --- | --- | --- |",
    ]
    for cell in report["reliability"]["cells"]:
        lines.append(
            f"| {cell['family']} | {cell['method']} | {cell['schema_valid']}/{cell['planned']} | "
            f"{cell['length_finishes']} | {'pass' if cell['passed'] else 'fail'} |"
        )
    lines += [
        "",
        "Development only; three source groups, dependent checkpoints, one repeat.",
        "Historical 270-version scores are not ranked with this 540-version result.",
        "",
    ]
    return analysis, "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    analysis, tables = generate()
    output = HERE / "analysis"
    if args.verify:
        verify_seal(output)
        if (
            read(output / "analysis.json") != analysis
            or (output / "RESULT_TABLES.md").read_text() != tables
        ):
            raise ValueError("analysis reconstruction mismatch")
    else:
        output.mkdir(exist_ok=False)
        write(output / "analysis.json", analysis)
        (output / "RESULT_TABLES.md").write_text(tables)
        seal(output)
    print(
        {
            "status": "passed",
            "analysis_id": analysis["analysis_id"],
            "invalid_outputs": len(analysis["invalid_outputs"]),
        }
    )
