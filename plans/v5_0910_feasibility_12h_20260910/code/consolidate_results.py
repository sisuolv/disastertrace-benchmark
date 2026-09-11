"""Summarize paired development diagnostics without treating frames as events."""

from collections import Counter, defaultdict
import argparse
import csv
from datetime import datetime, timezone
import json
from statistics import mean

from common import ROOT, dump
from model_adapter import sha_file


def read(name):
    return json.loads((ROOT / "analysis" / name).read_text())


def csv_file(path, rows):
    with path.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main(include_assistance=False):
    main_audits = [read(name + "_AUDIT.json") for name in ["WAVE2", "WAVE3", "WAVE4"]]
    diagnostics, natural = read("WAVE5_AUDIT.json"), read("WAVE6_AUDIT.json")
    table = []
    grouped = defaultdict(list)
    for audit in main_audits:
        for row in audit["rows"]:
            grouped[row["model"], row["condition"]].append(row)
    error_rows = []
    for (model, condition), rows in sorted(grouped.items()):
        families = defaultdict(list)
        for row in rows:
            families[row["family"]].append(row)
        calls = [call for row in rows for call in row["calls"]]
        sufficient = [row for row in rows if row["score"]["read_sufficient"]]
        row = {"model": model, "condition": condition, "episodes": len(rows),
            "goal_accuracy": mean(x["score"]["goal_correct"] for x in rows),
            "grounded_success": mean(x["score"]["grounded_success"] for x in rows),
            "source_macro_grounded": mean(mean(x["score"]["grounded_success"] for x in group) for group in families.values()),
            "acquired_sufficient": mean(x["score"]["read_sufficient"] for x in rows),
            "grounded_given_sufficient": mean(x["score"]["grounded_success"] for x in sufficient) if sufficient else None,
            "mean_reads": mean(x["score"]["spent"] for x in rows), "calls": len(calls),
            "input_tokens": sum(c["input_tokens"] for c in calls),
            "output_tokens": sum(c["output_tokens"] for c in calls),
            "generation_seconds": sum(c["seconds"] for c in calls)}
        table.append(row)
        for family, items in sorted(families.items()):
            categories = Counter()
            for item in items:
                score = item["score"]
                if item["status"] != "final":
                    category = "protocol_or_runtime_failure"
                elif score["grounded_success"]:
                    category = "grounded_success"
                elif not item["certificate_attainable"]:
                    category = "no_certificate_within_declared_budget"
                elif not score["read_sufficient"]:
                    category = "insufficient_acquisition_despite_budget_attainability"
                elif not score["goal_correct"]:
                    category = "decision_error_with_sufficient_acquired_evidence"
                else:
                    category = "citation_failure_with_correct_decision"
                categories[category] += 1
            error_rows.append({"model": model, "condition": condition, "family": family,
                "n": len(items), "groups": sorted({x["group"] for x in items}),
                "categories": dict(categories),
                "source_macro_grounded": mean(x["score"]["grounded_success"] for x in items)})
    paired = []
    for model in ["qwen3vl_8b", "qwen3vl_32b"]:
        active = {r["episode"]: r for r in grouped[model, "active2_image"]}
        fixed = {r["episode"]: r for r in diagnostics["static_rows"]
                 if r["model"] == model and r["condition"] == "fixed2_image"}
        if set(active) != set(fixed):
            raise ValueError("paired active/fixed denominator differs")
        paired.append({"model": model, "episodes": len(active),
            "active_grounded": mean(r["score"]["grounded_success"] for r in active.values()),
            "fixed_grounded": mean(r["score"]["grounded_success"] for r in fixed.values()),
            "active_only_success": sum(active[e]["score"]["grounded_success"] and not fixed[e]["score"]["grounded_success"] for e in active),
            "fixed_only_success": sum(fixed[e]["score"]["grounded_success"] and not active[e]["score"]["grounded_success"] for e in active),
            "limit": "One-shot fixed finalization and active multi-turn trajectories differ in interaction/context cost; not an isolated causal policy estimate."})
    state_costs = []
    state_tasks = {r["task"]: r for r in diagnostics["state_rows"]}
    for row in diagnostics["state_aggregate"]:
        tasks = {tid for tid, task in state_tasks.items() if task["model"] == row["model"] and task["carrier"] == row["carrier"]}
        calls = [c for c in diagnostics["calls"] if c["task"] in tasks]
        state_costs.append({**row, "input_tokens": sum(c["input_tokens"] for c in calls),
                           "output_tokens": sum(c["output_tokens"] for c in calls)})
    natural_table = []
    for row in natural["by_model_condition"]:
        selected = [r for r in natural["rows"] if r["model"] == row["model"] and r["condition"] == row["condition"]]
        matrix = Counter((r["score"]["goal_decision"], r["answer"]["decision"] if r["answer"] else "invalid") for r in selected)
        natural_table.append({**row, "confusion": [{"reference": g, "answer": a, "n": n} for (g, a), n in sorted(matrix.items())]})
    all_audits = [read("WAVE1_AUDIT.json"), *main_audits, diagnostics, natural]
    inputs = ["WAVE1_AUDIT.json", "WAVE2_AUDIT.json", "WAVE3_AUDIT.json", "WAVE4_AUDIT.json", "WAVE5_AUDIT.json", "WAVE6_AUDIT.json", "PROGRAM_BASELINES.json"]
    assistance = read("WAVE7_AUDIT.json") if include_assistance else None
    if assistance:
        all_audits.append(assistance)
        inputs.append("WAVE7_AUDIT.json")
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "main_model_table": table,
        "main_fixed_denominator_trajectories": sum(a["tasks"] for a in main_audits),
        "main_error_decomposition": error_rows, "fixed_acquisition_comparison": paired,
        "program_budget_curves": read("PROGRAM_BASELINES.json")["aggregate"],
        "state_table_with_costs": state_costs, "native_and_fixed_static": diagnostics["static_aggregate"],
        "natural_coverage_table": natural_table,
        "natural_assistance_table": assistance["by_model_condition"] if assistance else [],
        "total_captured_calls": sum(a.get("captured_model_calls", a.get("captured_calls", 0)) for a in all_audits),
        "total_intents": sum(a["generation_intents"] for a in all_audits),
        "input_files": {name: sha_file(ROOT / "analysis" / name) for name in inputs},
        "statistics": "Descriptive paired development results. No p-values or confidence intervals from correlated episode counts. Source macro weights four source families equally.",
        "protocol_failure": "Wave1 is retained separately; it is not included in main_model_table.",
        "error_taxonomy": "Mutually exclusive descriptive accounting in stated precedence; not causal attribution to hidden model mechanisms."}
    dump(ROOT / ("analysis/FINAL_RESULTS_02.json" if include_assistance else "analysis/FINAL_RESULTS.json"), result)
    if not include_assistance:
        csv_file(ROOT / "analysis/MODEL_RESULTS.csv", table)
        csv_file(ROOT / "analysis/PROGRAM_BUDGET_CURVES.csv", result["program_budget_curves"])
    print(json.dumps({"total_calls": result["total_captured_calls"], "main_trajectories": result["main_fixed_denominator_trajectories"],
                      "natural": natural_table}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-assistance", action="store_true")
    main(parser.parse_args().include_assistance)
