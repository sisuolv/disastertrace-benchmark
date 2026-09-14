"""Reconstruct disclosed interval witnesses and preserve paired model examples.

This posthoc analysis neither changes the scorer nor submits model requests.
The independent interval calculation is deliberately limited to the qualified
single-report, exact-product inputs in this fixed-input diagnostic.
"""

import argparse
import hashlib
import json
import math
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

MODELS = ("qwen235b_fp8", "qwen8b_control")
CONDITIONS = ("common_only", "fixed_one", "all_registered")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def iso(value):
    return datetime.fromtimestamp(value / 1_000_000, timezone.utc).isoformat()


def interval_witness(payload):
    question = payload["baseline"]["content"]["E_question"]
    assert question["predicate"] == "any_registered_neighbor_slot_below_threshold"
    queries = question["query_ids"]
    assert len(set(queries)) == len(queries)
    threshold = question["threshold_m"]
    disclosed = {}
    for asset in payload["assets"]:
        content = asset["content"]
        query = content["query_id"]
        assert query in queries and query not in disclosed
        assert content["status"] == "disclosed_product_fact"
        assert content["reference_kind"] == "product_label"
        assert content["support_assumption"] == "product_exact"
        assert len(content["reports"]) == 1
        report = content["reports"][0]
        assert report["decoded"] and not report["quality_flags"]
        bounds = report["visibility"]
        lo, hi = float(bounds["lower"]), float(bounds["upper"])
        assert not math.isnan(lo) and not math.isnan(hi)
        assert lo < hi or (
            lo == hi and bounds["lower_closed"] and bounds["upper_closed"]
        )
        below = hi < threshold or (hi == threshold and not bounds["upper_closed"])
        not_below = lo >= threshold
        assert not (below and not_below)
        disclosed[query] = {
            "query_id": query,
            "raw": report["raw"],
            "reported_at_utc": iso(report["observation_time"]),
            "visibility_m": bounds,
            "slot_truth": "true" if below else "false" if not_below else "unknown",
        }
    missing = sorted(set(queries) - set(disclosed))
    truths = [row["slot_truth"] for row in disclosed.values()]
    expected = (
        "supported"
        if "true" in truths
        else "refuted"
        if not missing and truths and all(value == "false" for value in truths)
        else "undetermined"
    )
    return {
        "threshold_m": threshold,
        "registered_query_ids": queries,
        "disclosed_reports": list(disclosed.values()),
        "missing_query_ids": missing,
        "independent_expected_E": expected,
        "basis": "Visible exact-product intervals only; no hidden report or outcome read.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    execution = args.execution.resolve()
    batch = execution / "gpu/large_diagnostic_02"
    audit = execution / "reports/large_model_diagnostic_01"
    validation = read(audit / "VALIDATION.json")
    assert validation["integrity_passed"] and validation["registered"] == 1008
    tasks = {row["call_id"]: row for row in read(batch / "PLAN.json")["tasks"]}
    records = {
        model: {row["call_id"]: row for row in read(audit / model / "RECORDS.json")}
        for model in MODELS
    }
    assert all(set(rows) == set(tasks) for rows in records.values())
    references = {
        row["identity"]: row["reference"]
        for row in read(batch / "evaluator/NATIVE_REFERENCES.json")
    }
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(Path(__file__), args.output / Path(__file__).name)
    bindings = {
        str((audit / "VALIDATION.json").relative_to(execution)): sha(
            audit / "VALIDATION.json"
        )
    }
    rows, taf_rows, examples = [], [], []
    selected = set()
    for call_id, task in sorted(tasks.items()):
        if task["head"] == "f_only":
            continue
        policy_path = batch / "policy" / (call_id + ".json")
        policy = read(policy_path)
        bindings[str(policy_path.relative_to(execution))] = sha(policy_path)
        answers = {}
        for model in MODELS:
            request_path = batch / model / (call_id + "-request.json")
            response_path = batch / model / (call_id + "-response.json")
            request, response = read(request_path), read(response_path)
            row = records[model][call_id]
            assert request["messages"] == policy["messages"]
            assert row["raw"] == response["raw"]
            for path in (request_path, response_path):
                bindings[str(path.relative_to(execution))] = sha(path)
            answers[model] = {
                "raw": row["raw"],
                "E_answer": row["e_answer"],
                "correct": row["e_correct"],
                "input_tokens": row["input_tokens"],
                "output_tokens": row["output_tokens"],
                "original_request": str(request_path.relative_to(execution)),
                "original_response": str(response_path.relative_to(execution)),
            }
        if task["input_kind"] == "bundle":
            witness = interval_witness(policy["input"]["payload"])
            for model in MODELS:
                row = records[model][call_id]
                assert row["e_expected"] == witness["independent_expected_E"]
                category = (
                    "correct"
                    if row["e_correct"]
                    else "unwarranted_determination"
                    if row["e_expected"] == "undetermined"
                    and row["e_answer"] in {"supported", "refuted"}
                    else "unnecessary_unknown"
                    if row["e_expected"] in {"supported", "refuted"}
                    and row["e_answer"] == "undetermined"
                    else "contrary_or_other_error"
                )
                item = {
                    "model": model,
                    "call_id": call_id,
                    "opportunity_id": row["opportunity_id"],
                    "head": task["head"],
                    "condition": task["condition"],
                    "category": category,
                    "expected_E": row["e_expected"],
                    "answer_E": row["e_answer"],
                    "witness": witness,
                }
                rows.append(item)
                key = (model, category, task["condition"])
                if category != "correct" and key not in selected:
                    selected.add(key)
                    examples.append(
                        {
                            "kind": "bundle",
                            "selection_key": key,
                            "call_id": call_id,
                            "head": task["head"],
                            "opportunity_id": row["opportunity_id"],
                            "witness": witness,
                            "paired_original_answers": answers,
                        }
                    )
        else:
            reference = references[task["identity"]]
            for model in MODELS:
                row = records[model][call_id]
                assert row["e_expected"] == reference["answer"]
                taf_rows.append(
                    {
                        "model": model,
                        "call_id": call_id,
                        "head": task["head"],
                        "representation": task["representation"],
                        "expected": row["e_expected"],
                        "answer": row["e_answer"],
                        "correct": row["e_correct"],
                    }
                )
                key = (model, task["head"], task["representation"])
                if not row["e_correct"] and key not in selected:
                    selected.add(key)
                    examples.append(
                        {
                            "kind": "taf_task",
                            "selection_key": key,
                            "call_id": call_id,
                            "original_input": policy["input"],
                            "evaluator_reference": reference,
                            "paired_original_answers": answers,
                            "reference_scope": "Original native parser reference; not an additional independent TAF parser.",
                        }
                    )
    assert len(rows) == 576 and len(taf_rows) == 144
    tables = []
    for model in MODELS:
        for head in ("e_only", "joint"):
            for condition in CONDITIONS:
                group = [
                    row
                    for row in rows
                    if (row["model"], row["head"], row["condition"])
                    == (model, head, condition)
                ]
                assert len(group) == 48
                tables.append(
                    {
                        "model": model,
                        "head": head,
                        "condition": condition,
                        "n": len(group),
                        "categories": dict(Counter(row["category"] for row in group)),
                        "expected_distribution": dict(
                            Counter(row["expected_E"] for row in group)
                        ),
                        "missing_slot_witnesses": sum(
                            bool(row["witness"]["missing_query_ids"]) for row in group
                        ),
                    }
                )
    for model in MODELS:
        path = audit / model / "RECORDS.json"
        bindings[str(path.relative_to(execution))] = sha(path)
    save(args.output / "ALL_E_WITNESSES.json", rows)
    save(args.output / "ALL_TAF_RESULTS.json", taf_rows)
    save(args.output / "TABLES.json", tables)
    save(args.output / "EXAMPLES.json", examples)
    save(args.output / "INPUT_HASHES.json", bindings)
    result = {
        "passed": True,
        "bundle_E_answers": len(rows),
        "unique_bundle_opportunities": len({row["opportunity_id"] for row in rows}),
        "taf_answers": len(taf_rows),
        "descriptive_examples": len(examples),
        "all_disclosed_interval_labels_match_original_scorer": True,
        "all_selected_requests_and_raw_answers_bound": True,
        "selection": "First lexicographic call ID for each displayed model/error/condition or model/TAF-head/time-encoding category; all counts retain the complete denominator.",
        "new_model_calls": 0,
        "scorer_changed": False,
        "independent_confirmation": False,
        "limits": [
            "Posthoc examples illustrate observable errors; no chain of thought or internal cause is inferred.",
            "The independent rule covers the current exact, single-report native product inputs only; it is not a generic sensor-truth validator.",
            "TAF references reuse the original native parser and are not independently redecoded here.",
            "These are the same exposed opportunities across heads, evidence conditions and models.",
        ],
    }
    save(args.output / "VALIDATION.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
