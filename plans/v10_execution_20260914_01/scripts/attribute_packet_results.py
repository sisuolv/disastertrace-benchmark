"""Posthoc numeric provenance and matched-failure-mask controls; no score repair."""

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from disastertrace.monitoring_v1.fixed_packet import parse
from disastertrace.monitoring_v1.spool_backend import publish, read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    rows = [json.loads(line) for line in (args.scores / "ROWS.jsonl").open()]
    groups, details = defaultdict(list), []
    for row in rows:
        r = {
            "call_id": row["call_id"],
            "model": row["model"],
            "cohort": row["cohort"],
            "condition": row["condition"],
            "reasoning": row["reasoning"],
            "valid": row["valid"],
            "copy_exact_if_valid": row["valid"] and row["model_F"] == row["FOLLOW"],
            "copy_near_1e12_if_valid": row["valid"]
            and abs(row["model_F"] - row["FOLLOW"]) <= 1e-12,
        }
        if row["reasoning"] == "slotwise":
            valid_slots = row["valid"] and not row.get("model_slots_rejected")
            masked = row["native_program_F"] if valid_slots else row["FOLLOW"]
            r.update(
                native_F_with_same_invalid_mask=masked,
                model_slot_pipeline_equals_masked_native=row["model_slots_F"] == masked,
                model_slots_correct=row["slots_correct"],
                valid_slot_error_without_F_difference=valid_slots
                and not row["slots_correct"]
                and row["model_slots_F"] == row["native_program_F"],
            )
            if (
                row["outcome"] is not None
                if "outcome" in row
                else row["future_value"] is not None
            ):
                y = row["future_value"]
                r.update(
                    masked_native_loss=(masked - y) ** 2,
                    model_slot_loss=(row["model_slots_F"] - y) ** 2,
                    full_native_loss=(row["native_program_F"] - y) ** 2,
                )
        if row["model"].startswith("Qwen") and not row["valid"]:
            path = next(
                (args.batch / "gpu").glob(
                    "worker_*/" + row["call_id"] + ".response.json"
                )
            )
            raw = read(path)["raw"]
            match = re.fullmatch(r"\s*```json\s*\n(.*?)\n```\s*", raw, re.DOTALL)
            r["failure_kind"] = (
                "single_entire_JSON_markdown_fence" if match else "other"
            )
            r["original_ended_with_eos"] = row["ended_with_eos"]
            if match:
                try:
                    answer = parse(
                        match[1],
                        row["query_ids"],
                        row["acquired_ids"],
                        row["reasoning"],
                    )
                    r.update(
                        fence_only_adapter_valid=True,
                        fence_only_adapter_E_correct=answer["fact_truth"]
                        == row["reference_E"],
                        fence_only_adapter_copies_visible_F=answer["probability"]
                        == row["FOLLOW"],
                    )
                except (ValueError, TypeError):
                    r["fence_only_adapter_valid"] = False
        groups[
            "__".join([row["model"], row["reasoning"], row["cohort"], row["condition"]])
        ].append(r)
        details.append(r)
    summaries = {}
    for key, group in groups.items():
        counts = Counter(registered=len(group))
        for r in group:
            counts.update(
                {
                    k: int(r.get(k, False))
                    for k in (
                        "valid",
                        "copy_exact_if_valid",
                        "copy_near_1e12_if_valid",
                        "model_slot_pipeline_equals_masked_native",
                        "valid_slot_error_without_F_difference",
                        "fence_only_adapter_valid",
                        "fence_only_adapter_E_correct",
                        "fence_only_adapter_copies_visible_F",
                    )
                }
            )
        item = dict(counts)
        for loss in ("masked_native_loss", "model_slot_loss", "full_native_loss"):
            available = [r[loss] for r in group if loss in r]
            if available:
                item[loss] = math.fsum(available) / len(available)
        summaries[key] = item
    result = {
        "scope": "posthoc explanatory controls on original captures, not replacements for preregistered scores",
        "original_valid_answers": sum(r["valid"] for r in details),
        "valid_exact_F_copies": sum(r["copy_exact_if_valid"] for r in details),
        "slot_pipeline_rows": sum(r["reasoning"] == "slotwise" for r in details),
        "slot_pipeline_equal_matched_mask_native": sum(
            r.get("model_slot_pipeline_equals_masked_native", False) for r in details
        ),
        "failure_kinds": dict(
            Counter(r["failure_kind"] for r in details if "failure_kind" in r)
        ),
        "groups": summaries,
        "new_model_calls": 0,
        "interpretation": "A matched raw-invalid mask fully explaining a pipeline difference is not semantic model forecast gain",
        "latency_limits": "Qwen capture meters generation, not complete prompt preparation/durable publication. Fixed-packet results do not qualify formal online latency.",
    }
    publish(args.out / "RESULT.json", result)
    with (args.out / "ATTRIBUTION.jsonl").open("x") as stream:
        for row in details:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "original_valid_answers",
                    "valid_exact_F_copies",
                    "slot_pipeline_rows",
                    "slot_pipeline_equal_matched_mask_native",
                    "failure_kinds",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
