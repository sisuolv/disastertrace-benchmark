"""Summarize independently audited X09 pairs without scoring empty captures."""

import argparse
import csv
import hashlib
import json
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mean(values):
    return sum(values) / len(values) if values else None


def summarize(validation, calls, targets, tables, pairs, *, allow_unlaunched=False):
    if not validation["integrity_passed"]:
        raise ValueError("An independent integrity pass is required")
    measured = validation["real_model_results"]
    if not measured and not allow_unlaunched:
        raise ValueError("Unlaunched captures are not model results")
    if (len(calls), len(targets), len(pairs)) != (384, 576, 288):
        raise ValueError("All registered requests and target positions are required")
    by_call = {row["call_id"]: row for row in calls}
    if len(by_call) != len(calls):
        raise ValueError("Duplicate request identity")
    positions, cohorts = defaultdict(dict), defaultdict(list)
    call_targets = defaultdict(set)
    for row in targets:
        call = by_call[row["call_id"]]
        for key in ("group_id", "head", "scope", "condition", "threshold_m"):
            if row[key] != call[key]:
                raise ValueError("Target/call comparison identity differs")
        key = (row["group_id"], row["head"], row["opportunity_id"])
        if row["scope"] in positions[key]:
            raise ValueError("Duplicate paired target position")
        positions[key][row["scope"]] = row
        cohorts[
            (row["threshold_m"], row["condition"], row["head"], row["scope"])
        ].append(row)
        call_targets[row["call_id"]].add(row["target_id"])
    if any(
        len(call_targets[cid]) != row["requested_targets"]
        for cid, row in by_call.items()
    ):
        raise ValueError("A failed multi-target request cannot lose target positions")
    if len(positions) != 288 or any(
        set(p) != {"single", "multi"} for p in positions.values()
    ):
        raise ValueError("Missing single/multi pair")
    canonical = {
        (r["threshold_m"], r["condition"], r["head"], r["scope"]): r for r in tables
    }
    if len(canonical) != 24 or set(canonical) != set(cohorts):
        raise ValueError("Changed threshold/condition/head/scope cells")
    summaries = []
    for key, rows in sorted(cohorts.items()):
        if len(rows) != 24:
            raise ValueError("Changed target denominator")
        current_calls = [by_call[cid] for cid in sorted({r["call_id"] for r in rows})]
        has_e, has_f = key[2] != "f_only", key[2] != "e_only"
        f_rows = [r for r in rows if r["F_brier"] is not None]
        if not has_f and any(r["effective_probability"] is not None for r in rows):
            raise ValueError("E-only must not contribute a future probability")
        e_correct = sum(r["E_correct_by_cutoff"] for r in rows) if has_e else None
        f_brier = mean([r["F_brier"] for r in f_rows])
        base_brier = mean([r["baseline_brier"] for r in f_rows])
        if canonical[key]["E_correct"] != e_correct or canonical[key][
            "F_scored"
        ] != len(f_rows):
            raise ValueError("Independent cell score mismatch")
        for field, computed in (("F_brier", f_brier), ("baseline_brier", base_brier)):
            expected = canonical[key][field]
            if expected is None or computed is None:
                if expected is not computed:
                    raise ValueError("Independent missing-score mismatch")
            elif not math.isclose(expected, computed, rel_tol=0, abs_tol=1e-14):
                raise ValueError("Independent numerical score mismatch")
        metrics = None
        if measured:
            metrics = {
                "E_correct": e_correct,
                "E_unsupported_determination": sum(
                    r["E_unsupported_determination"] for r in rows
                )
                if has_e
                else None,
                "E_unsupported_determination_admitted": sum(
                    r["E_unsupported_determination"] and r["admitted"] for r in rows
                )
                if has_e
                else None,
                "E_always_unknown_control_correct": sum(
                    r["expected_E"] == "undetermined" for r in rows
                )
                if has_e
                else None,
                "F_brier": f_brier,
                "baseline_brier": base_brier,
                "F_gain_vs_baseline": base_brier - f_brier if f_rows else None,
                "F_probability_changed_proposals": sum(
                    r["candidate_probability"] is not None
                    and r["candidate_probability"] != r["baseline_probability"]
                    for r in rows
                )
                if has_f
                else None,
                "F_probability_changed_effective": sum(
                    r["effective_probability"] != r["baseline_probability"]
                    for r in rows
                )
                if has_f
                else None,
                "F_same_value_overrides": sum(
                    r["mode"] == "OVERRIDE"
                    and r["effective_probability"] == r["baseline_probability"]
                    for r in rows
                )
                if has_f
                else None,
            }
        summaries.append(
            {
                "threshold_m": key[0],
                "condition": key[1],
                "head": key[2],
                "scope": key[3],
                "registered_target_answers": len(rows),
                "unique_opportunities": len({r["opportunity_id"] for r in rows}),
                "registered_calls": len(current_calls),
                "requested_output_cap_per_call": 512,
                "planned_output_token_budget": 512 * len(current_calls),
                "attempted_calls": sum(
                    c["disposition"] != "unattempted" for c in current_calls
                ),
                "admitted_calls": sum(c["admitted"] for c in current_calls),
                "admitted_target_answers": sum(r["admitted"] for r in rows),
                "dispositions": dict(Counter(c["disposition"] for c in current_calls)),
                "requested_input_tokens": sum(c["input_tokens"] for c in current_calls),
                "returned_output_tokens": sum(
                    c["output_tokens"] for c in current_calls
                ),
                "F_mature_registered_positions": len(f_rows),
                "metrics": metrics,
            }
        )
    original_pairs = {(r["group_id"], r["head"], r["opportunity_id"]): r for r in pairs}
    if set(original_pairs) != set(positions):
        raise ValueError("Independent pair identities differ")
    differences = defaultdict(list)
    for key, pair in sorted(positions.items()):
        a, b = pair["single"], pair["multi"]
        de = (
            int(b["E_correct_by_cutoff"]) - int(a["E_correct_by_cutoff"])
            if key[1] != "f_only"
            else None
        )
        df = a["F_brier"] - b["F_brier"] if a["F_brier"] is not None else None
        if (
            original_pairs[key]["E_correct_multi_minus_single"] != de
            or original_pairs[key]["F_brier_single_minus_multi"] != df
        ):
            raise ValueError("Independent paired score differs")
        differences[(a["threshold_m"], a["condition"], key[1])].append(
            {
                "E_difference": de,
                "F_difference": df,
                "both_admitted": a["admitted"] and b["admitted"],
            }
        )
    contrasts = []
    for key, rows in sorted(differences.items()):
        contrasts.append(
            {
                "threshold_m": key[0],
                "condition": key[1],
                "head": key[2],
                "registered_pairs": len(rows),
                "both_admitted": sum(r["both_admitted"] for r in rows),
                "E_correctness_difference_counts": dict(
                    Counter(str(r["E_difference"]) for r in rows)
                )
                if measured and key[2] != "f_only"
                else None,
                "E_accuracy_multi_minus_single": mean(
                    [r["E_difference"] for r in rows if r["E_difference"] is not None]
                )
                if measured
                else None,
                "F_brier_single_minus_multi": mean(
                    [r["F_difference"] for r in rows if r["F_difference"] is not None]
                )
                if measured
                else None,
            }
        )
    batches = defaultdict(list)
    for row in calls:
        if row["batch_elapsed_us"] is not None:
            batches[row["batch_offset"]].append(row)
    physical_time = 0
    for rows in batches.values():
        elapsed = {r["batch_elapsed_us"] for r in rows}
        if len(elapsed) != 1:
            raise ValueError("One physical batch has conflicting elapsed-time receipts")
        physical_time += next(iter(elapsed))
    return {
        "real_model_results": measured,
        "all_planned_completed": validation["all_planned_completed"],
        "registered_calls": len(calls),
        "registered_target_answers": len(targets),
        "unique_opportunities": len({r["opportunity_id"] for r in targets}),
        "paired_positions": len(positions),
        "actual_benchmark_requests": sum(
            c["disposition"] != "unattempted" for c in calls
        ),
        "compatibility_requests": validation["compatibility_requests"],
        "completed_physical_batches": len(batches),
        "completed_physical_batch_elapsed_seconds": physical_time / 1e6,
        "scope_specific_GPU_time": None,
        "cells": summaries,
        "contrasts": contrasts,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-unlaunched", action="store_true")
    args = parser.parse_args()
    names = (
        "VALIDATION.json",
        "CALLS.json",
        "TARGETS.json",
        "TABLES.json",
        "PAIRS.json",
    )
    result = summarize(
        *(read(args.audit / n) for n in names), allow_unlaunched=args.allow_unlaunched
    )
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(Path(__file__), args.output / Path(__file__).name)
    for name, value in (
        ("SUMMARY.json", result),
        ("CELLS.json", result["cells"]),
        ("CONTRASTS.json", result["contrasts"]),
    ):
        with (args.output / name).open("x") as handle:
            json.dump(value, handle, indent=2, allow_nan=False)
            handle.write("\n")
    for name, rows in (
        ("CELLS.csv", result["cells"]),
        ("CONTRASTS.csv", result["contrasts"]),
    ):
        with (args.output / name).open("x", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    receipt = {
        "all_metrics_match_independent_scores": True,
        "source_audit": str(args.audit.resolve()),
        "source_sha256": {n: sha(args.audit / n) for n in names},
        "real_model_results": result["real_model_results"],
        "all_planned_completed": result["all_planned_completed"],
        "analysis_new_model_calls": 0,
        "limits": [
            "Repeated exposed opportunities are not independent weather processes; thresholds, heads and conditions stay separate.",
            "The complete planned denominator includes failed and unattempted calls. Admission failures retain F baseline and fail E.",
            "Both scopes receive identical information, but requested output arity and total output budget differ: three single calls versus one three-target call.",
            "Per-request 512-token caps do not constitute equal per-group output budgets. Report completion and output length before reasoning interpretations.",
            "Physical batch timing is counted once overall; mixed batches do not identify scope-specific GPU time or deployment speed.",
            "Dryruns have no model metrics even though their hypothetical fallback losses are defined by the evaluator.",
        ],
    }
    with (args.output / "VALIDATION.json").open("x") as handle:
        json.dump(receipt, handle, indent=2)
        handle.write("\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
