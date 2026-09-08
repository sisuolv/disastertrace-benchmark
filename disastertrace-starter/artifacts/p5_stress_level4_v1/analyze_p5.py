"""Reconstruct P5 result tables, errors and usage from audited actual captures."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from compare_stress import FACTORS, HERE, audited_input

from disastertrace.automated.common import fingerprint, read_jsonl
from disastertrace.local_eval.storage import read, seal, verify_seal, write

METRIC_NAMES = (
    "schema_success",
    "known_value_accuracy",
    "known_grounded_accuracy",
    "unknown_accuracy",
    "all_correct_checkpoints",
    "action_accuracy",
)


def generate(runs_root=None):
    units = {}
    lines = [
        "# P5 actual Qwen3-8B level-4 stress results",
        "",
        "Fixed denominators; independent deterministic audit; no answer repair.",
        "",
        "| Factor | Method | Contract | Known Value | Known Grounded | Unknown | All Correct | Action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for factor in FACTORS:
        unit = HERE / "units" / factor
        path = unit / "execution_live"
        plan = read(path / "execution.json")
        run = (
            (Path(runs_root) / Path(plan["run_path"]).name) if runs_root else Path(plan["run_path"])
        )
        plan, report = audited_input(
            path, unit / "model_report", run, "local_model_vllm_stress_constrained_v1"
        )
        slots = read_jsonl(path / "dataset/schedule.jsonl")
        tokens, lengths, batches = defaultdict(Counter), [], {}
        invalid = []
        for file in sorted((run / "captures").glob("*.json")):
            capture = read(file)
            slot = slots[capture["slot_index"]]
            tokens[slot["method"]].update(
                prompt=capture["prompt_tokens"],
                generated=capture["completion_tokens"],
                reasoning=capture["extracted"]["reasoning_tokens"],
                final_content=capture["extracted"]["content_tokens"],
            )
            lengths.append(capture["completion_tokens"])
            index, seconds = capture["batch_index"], capture["batch_wall_seconds"]
            if index in batches and batches[index] != seconds:
                raise ValueError("shared batch timing differs between captures")
            batches[index] = seconds
            if not capture["output_validity"]["task_contract_valid"]:
                invalid.append(
                    {
                        "slot_index": slot["slot_index"],
                        "slot_id": slot["slot_id"],
                        "method": slot["method"],
                        "finish_reason": capture["result"]["finish_reason"],
                        "completion_tokens": capture["completion_tokens"],
                        "extraction_error": capture["extracted"]["extraction_error"],
                        "validity": capture["output_validity"],
                    }
                )
        methods = {}
        error_fields = report["errors"]["fields"]
        error_actions = report["errors"]["actions"]
        key = lambda row: (row["method"], row["episode_id"], row["checkpoint_id"])
        wind_errors = {key(r) for r in error_fields if r["field"] == "maximum_wind_mph"}
        action_keys = {key(r) for r in error_actions}
        for method, score in report["methods"].items():
            layers = report["format_layers"][method]
            if not (
                layers["json_valid"]["numerator"]
                >= layers["structure_valid"]["numerator"]
                >= layers["task_contract_valid"]["numerator"]
                == score["metrics"]["schema_success"]["numerator"]
            ):
                raise ValueError("validity layers disagree with task scorer")
            strata = {}
            for label, predicate in (
                ("c0", lambda r: r["checkpoint_id"] == "c0"),
                ("c1_to_c4", lambda r: r["checkpoint_id"] != "c0"),
            ):
                selected = [r for r in score["per_checkpoint"] if predicate(r)]
                strata[label] = {
                    "all_correct": sum(r["counts"]["all_correct"] for r in selected),
                    "planned": len(selected),
                }
            methods[method] = {
                "metrics": score["metrics"],
                "checkpoint_strata": strata,
                "field_error_reasons": dict(
                    Counter(r["reason"] for r in error_fields if r["method"] == method)
                ),
                "action_errors": sum(r["method"] == method for r in error_actions),
                "incorrect_checkpoints": sum(
                    not r["counts"]["all_correct"] for r in score["per_checkpoint"]
                ),
                "tokens": dict(tokens[method]),
            }
            values = [
                f"{score['metrics'][n]['numerator']}/{score['metrics'][n]['denominator']}"
                for n in METRIC_NAMES
            ]
            lines.append("| " + " | ".join([factor, method, *values]) + " |")
        collected = read(HERE / "acp/phase_001" / factor / "collect_result.json")
        wall = (
            datetime.fromisoformat(collected["finished_at"])
            - datetime.fromisoformat(collected["started_at"])
        ).total_seconds()
        completion = read(run / "completion.json")
        units[factor] = {
            "execution_id": plan["execution_id"],
            "audit_id": report["audit_id"],
            "report_package_id": read(unit / "model_report/manifest.json")["package_id"],
            "complete": report["complete"],
            "received": report["received"],
            "attempted": report["attempted"],
            "planned": report["planned"],
            "stop_reason": completion["stop_reason"],
            "methods": methods,
            "format_screens": report["reliability"],
            "invalid_outputs": invalid,
            "field_error_reasons": dict(Counter(r["reason"] for r in error_fields)),
            "action_errors": len(action_keys),
            "action_errors_overlapping_wind_errors": len(action_keys & wind_errors),
            "error_checkpoints": len({key(r) for r in error_fields} | action_keys),
            "usage": report["usage"],
            "finish_reasons": report["finish_reasons"],
            "extraction_errors": report["extraction_errors"],
            "generation_batches": len(batches),
            "sum_generation_batch_seconds": sum(batches.values()),
            "collector_wall_seconds": wall,
            "generation_tokens_min": min(lengths) if lengths else None,
            "generation_tokens_max": max(lengths) if lengths else None,
            "gpu_hardware": read(HERE / "acp/phase_001" / factor / "hardware.json"),
            "completion_at": completion["finished_at"],
        }
    total_usage = dict(sum((Counter(v["usage"]) for v in units.values()), Counter()))
    analysis = {
        "schema_version": "p5_actual_analysis_v1",
        "units": units,
        "received_total": sum(v["received"] for v in units.values()),
        "planned_total": 1620,
        "attempted_total": sum(v["attempted"] for v in units.values()),
        "complete": all(v["complete"] for v in units.values()),
        "usage": total_usage,
        "additional_model_calls": 0,
        "paid_api_calls": 0,
        "gpu_cost_usd": None,
        "interpretation": "One repeat, three dependent source groups, full H100 workers. Timings are descriptive shared-batch measurements, not per-request latency or a hardware-controlled P4 comparison.",
    }
    analysis["analysis_id"] = fingerprint(analysis)
    lines += ["", analysis["interpretation"], ""]
    return analysis, "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--runs-root", type=Path)
    args = parser.parse_args()
    result, tables = generate(args.runs_root)
    output = HERE / "analysis"
    if args.verify:
        verify_seal(output)
        if (
            read(output / "analysis.json") != result
            or (output / "RESULT_TABLES.md").read_text() != tables
        ):
            raise ValueError("analysis reconstruction differs")
    else:
        output.mkdir(exist_ok=False)
        write(output / "analysis.json", result)
        with (output / "RESULT_TABLES.md").open("x") as stream:
            stream.write(tables)
        seal(output)
    print(
        {
            "status": "passed",
            "analysis_id": result["analysis_id"],
            "received": result["received_total"],
        }
    )


if __name__ == "__main__":
    main()
