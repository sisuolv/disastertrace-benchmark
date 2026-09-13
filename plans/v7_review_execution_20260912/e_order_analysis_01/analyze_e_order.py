"""Compare unchanged E messages across the four bounded execution-order audits."""

from __future__ import annotations

import argparse
import json
import random
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from analyze_e_diagnostics import digest, load, paired, write

BASE = Path(__file__).resolve().parent
CONDITIONS = ("E_only", "E_fact_table")
EXPECTED = {
    "gpu_e_order_8b_ab_01": ("qwen3_8b", 2026091301, CONDITIONS),
    "gpu_e_order_8b_ba_01": ("qwen3_8b", 2026091302, CONDITIONS[::-1]),
    "gpu_e_order_32b_ab_01": ("qwen3vl_32b", 2026091301, CONDITIONS),
    "gpu_e_order_32b_ba_01": ("qwen3vl_32b", 2026091302, CONDITIONS[::-1]),
}


def index_cases(cases):
    indexed = {case["case_id"]: case for case in cases}
    if len(indexed) != len(cases):
        raise ValueError("Duplicate case identity")
    return indexed


def compare_calls(candidate, reference, labels):
    result = paired(candidate, reference, labels)
    result.update(
        status_changed=sum(candidate[k]["reported_e"] != reference[k]["reported_e"] for k in labels),
        raw_changed=sum(candidate[k]["raw"] != reference[k]["raw"] for k in labels),
        validity_changed=sum(bool(candidate[k]["error"]) != bool(reference[k]["error"]) for k in labels),
    )
    return result


def audit_run(batch, checked_path, labels, bindings):
    def bound(path):
        bindings[str(path.resolve())] = digest(path)
        return load(path)

    checked = bound(checked_path)
    plan = bound(batch / "PLAN.json")
    if checked["plan_sha256"] != digest(batch / "PLAN.json"):
        raise ValueError("Verification does not match the frozen plan")
    if checked["execution_kind"] != "current_evidence_diagnostic":
        raise ValueError("Not an independently verified E diagnostic")
    for name, expected in plan["files"].items():
        if digest(batch / name) != expected:
            raise ValueError("Frozen source or input changed")
    data = bound(batch / "environment.json")
    cases = index_cases(data["cases"])
    if set(cases) != set(labels):
        raise ValueError("E denominator changed")
    calls, reports = {}, {}
    for task in plan["workers"]["0"]:
        condition = task["config"]["condition"]
        if condition not in CONDITIONS:
            continue
        directory = batch / "worker-0" / task["run_id"]
        trace = bound(directory / "TRACE.json")
        if trace["plan_sha256"] != digest(batch / "PLAN.json"):
            raise ValueError("Trace identity differs")
        if [c["case_id"] for c in trace["calls"]] != list(cases):
            raise ValueError("Actual case order differs from the frozen order")
        calls[condition] = index_cases(trace["calls"])
        token_sum = 0
        for case_id, call in calls[condition].items():
            request = bound(directory / (call["call_id"] + "-request.json"))
            response = bound(directory / (call["call_id"] + "-response.json"))
            raw_path = directory / (call["call_id"] + "-raw.txt")
            bindings[str(raw_path.resolve())] = digest(raw_path)
            messages = [
                {"role": "system", "content": data["systems"][condition]},
                {"role": "user", "content": json.dumps(cases[case_id]["requests"][condition], separators=(",", ":"))},
            ]
            if request["messages"] != messages or raw_path.read_text() != call["raw"]:
                raise ValueError("Actual message or raw output differs")
            if any(call["details"].get(k) != v for k, v in response.items() if k != "output_ids"):
                raise ValueError("Response receipt differs from the verified trace")
            token_sum += response["input_tokens"] + response["output_tokens"]
            call["input_ids"] = request["input_ids"]
            call["output_ids"] = response["output_ids"]
        counts = {
            "cases": len(cases),
            "correct": sum(c["reported_e"] == labels[k] for k, c in calls[condition].items()),
            "invalid": sum(bool(c["error"]) for c in calls[condition].values()),
            "confusion": dict(Counter(f"{labels[k]} -> {c['reported_e']}" for k, c in calls[condition].items())),
            "costs": trace["resource_spent"],
        }
        if counts != checked["reports"][condition] or token_sum != counts["costs"]["tokens"]:
            raise ValueError("Counts or costs differ from independent verification")
        reports[condition] = counts
    if set(calls) != set(CONDITIONS):
        raise ValueError("Missing paired E conditions")
    return plan, data, calls, reports


def main(args):
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "analyze_e_order.py")
    label_path = BASE / "E_DIAGNOSTIC_LABELS_01.json"
    labels = load(label_path)["labels"]
    bindings = {str(label_path.resolve()): digest(label_path)}
    results, rows, missing, used_calls = {}, [], [], 0
    parents = {}
    for name, (model, seed, condition_order) in EXPECTED.items():
        checked_path = BASE / (name + "_validation_01") / "VERIFIED.json"
        if not checked_path.exists():
            missing.append(name)
            continue
        batch = BASE / name
        plan, data, calls, reports = audit_run(batch, checked_path, labels, bindings)
        parent = BASE / Path(plan["parent_case_freeze"]).name
        parent_check = BASE / (parent.name + "_validation_01") / "VERIFIED.json"
        if parent.name not in parents:
            parents[parent.name] = audit_run(parent, parent_check, labels, bindings)
        old_plan, old_data, old_calls, old_reports = parents[parent.name]
        if plan["parent_plan_sha256"] != digest(parent / "PLAN.json") or plan["parent_verification_sha256"] != digest(parent_check):
            raise ValueError("Parent binding changed")
        if plan["evaluation_bindings"] != old_plan["evaluation_bindings"] or digest(label_path) not in plan["evaluation_bindings"].values():
            raise ValueError("Label contract changed")
        if plan["worker_models"]["0"] != model or plan["case_order_seed"] != seed:
            raise ValueError("Audit model or shuffle seed differs")
        if tuple(plan["condition_order"]) != condition_order or tuple(t["config"]["condition"] for t in plan["workers"]["0"]) != condition_order:
            raise ValueError("Frozen condition execution order differs")
        for field in ("models", "worker_models", "runtime_versions", "seed", "max_new_tokens", "context_limit", "max_generation_seconds"):
            if plan[field] != old_plan[field]:
                raise ValueError("Model or generation settings changed")
        old_tasks = {t["config"]["condition"]: t["config"] for t in old_plan["workers"]["0"]}
        if any(t["config"] != old_tasks[t["config"]["condition"]] for t in plan["workers"]["0"]):
            raise ValueError("Diagnostic budget or configuration changed")
        expected_order = list(old_data["cases"])
        random.Random(seed).shuffle(expected_order)
        if data["cases"] != expected_order or data["systems"] != old_data["systems"]:
            raise ValueError("Shuffle changed messages or does not match the declared seed")
        if data["systems"][CONDITIONS[0]] != data["systems"][CONDITIONS[1]]:
            raise ValueError("Paired E output contracts differ")
        comparisons = {}
        for condition in CONDITIONS:
            if any(calls[condition][k]["input_ids"] != old_calls[condition][k]["input_ids"] for k in labels):
                raise ValueError("Original and repeated actual input tokens differ")
            comparisons[condition] = compare_calls(calls[condition], old_calls[condition], labels)
            comparisons[condition]["output_tokens_changed"] = sum(
                calls[condition][k]["output_ids"] != old_calls[condition][k]["output_ids"] for k in labels
            )
            for case_id, call in calls[condition].items():
                old = old_calls[condition][case_id]
                rows.append({"batch": name, "model": model, "condition": condition, "case_id": case_id,
                             "expected_e": labels[case_id], "reported_e": call["reported_e"],
                             "original_reported_e": old["reported_e"], "error": call["error"],
                             "raw_changed": call["raw"] != old["raw"],
                             "raw": call["raw"], "original_raw": old["raw"]})
        actual = load(checked_path)["actual_calls"]
        if actual != sum(r["cases"] for r in reports.values()) or actual != 192:
            raise ValueError("Repeat call denominator differs")
        used_calls += actual
        results[name] = {"model": model, "condition_order": list(condition_order), "case_order_seed": seed,
                         "original": old_reports, "reports": reports,
                         "compared_with_original": comparisons,
                         "fact_table_vs_E_only": compare_calls(calls["E_fact_table"], calls["E_only"], labels),
                         "actual_input_tokens_identical_to_original": True,
                         "actual_case_order_matches_freeze": True,
                         "condition_order_evidence": "Frozen serial worker follows PLAN workers[0]; no cross-task synchronized timestamps are recorded."}
    if missing and not args.allow_partial:
        raise ValueError("Unverified audit batches remain: " + ", ".join(missing))
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "cases_per_condition": len(labels),
              "status_distribution": dict(Counter(labels.values())), "completed": results, "unverified": missing,
              "verified_repeat_model_calls": used_calls, "new_model_calls_in_analysis": 0,
              "input_bindings": bindings, "implementation_sha256": digest(args.output / "analyze_e_order.py"),
              "interpretation": [
                  "Post-hoc development audit of two declared case/condition permutations; all original cases retained.",
                  "Same messages and greedy generation do not imply independent statistical replicates.",
                  "Case and condition order both change; differences do not isolate either causal factor.",
                  "No independent-weather confidence interval, new F result or native-image effect is claimed.",
                  "Full per-case raw differences are retained; unchanged runs do not prove absence of all hardware effects.",
              ]}
    write(args.output / "REPORT.json", result)
    write(args.output / "CASES.json", rows)
    lines = ["# Bounded E execution-order audit", "",
             "These are the same 96 exposed-development cases with unchanged messages and settings.",
             "Each row is one executed condition; repeated cases are not new weather samples.", "",
             "| Batch | Condition | Correct | Original correct | Invalid | Status changes | Raw changes | Tokens | Compute ms |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, result in results.items():
        for condition in result["condition_order"]:
            values = result["reports"][condition]
            change = result["compared_with_original"][condition]
            lines.append(f"| {name} | {condition} | {values['correct']}/96 | {result['original'][condition]['correct']}/96 | "
                         f"{values['invalid']} | {change['status_changed']} | {change['raw_changed']} | "
                         f"{values['costs']['tokens']} | {values['costs']['compute_ms']} |")
    lines += ["", "Unverified batches: " + (", ".join(missing) or "none"), "",
              "REPORT.json records complete confusion matrices and paired changes; CASES.json retains raw answers for every paired case.",
              "Case order is checked against trace order. Condition order is bound by the frozen sequential worker, with no synchronized cross-task timestamps.",
              "This analysis makes no F, isolated causal-effect, independent-weather or multimodal improvement claim.", ""]
    (args.output / "REPORT.md").write_text("\n".join(lines))
    print(json.dumps({"completed": len(results), "unverified": missing, "verified_repeat_model_calls": used_calls}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-partial", action="store_true")
    main(parser.parse_args())
