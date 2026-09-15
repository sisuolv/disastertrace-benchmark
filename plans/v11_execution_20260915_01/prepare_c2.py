"""Bind a development C2 roster and real native E references, keeping F closed."""

import argparse
import datetime as dt
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.aviation import typed_target
from disastertrace.monitoring_fixed_v1.taf_tasks import (
    TafEvidenceTask,
    evaluate,
    messages,
)
from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def main(batch, out):
    out.mkdir(exist_ok=False)
    plan = read(batch / "PLAN.json")
    roster, bindings = [], {}
    # Calendar and public target identities select prefixes before any E reference is computed.
    selected = [c for c in plan["cases"] if c["date"] == c["week"]]
    payloads = {}
    for card in selected:
        path = batch / card["case"] / "DATA.json"
        if digest(path) != plan["files"][str(path.relative_to(batch))]:
            raise ValueError("Frozen development input changed")
        data = read(path)
        bindings[str(path)] = digest(path)
        payloads[card["case"]] = data
        for row in data["opportunities"]:
            if dt.datetime.fromtimestamp(row["cutoff"] / 1_000_000, dt.timezone.utc).hour == 12:
                roster.append({**row, "case": card["case"], "region": card["region"],
                    "week": card["week"], "prefix_rule": "immediately before the12UTC decision tick",
                    "parent_policy": "B11_COVERAGE", "checkpoint_materialized": False})
    if len(roster) != 72 or len({r["opportunity_id"] for r in roster}) != 72:
        raise ValueError("Expected all72 registered noon target prefixes")
    publish(out / "ROSTER.json", roster)
    tasks, references = [], []
    for row in roster:
        data = payloads[row["case"]]
        target = next(t for t in data["targets"] if t["target_id"] == row["target_id"])
        candidates = [c for c in data["baseline_candidates"] if c["target_id"] == row["target_id"]
                      and c["available_at"] <= row["cutoff"] and c["issued_at"] <= row["cutoff"]]
        products = {}
        for candidate in candidates:
            product = {"source_id": candidate["source_id"], "station": target["entity"],
                "raw": candidate["raw"], "issued_at": candidate["issued_at"],
                "available_at": candidate["available_at"], "completed_at": candidate["available_at"]}
            previous = products.setdefault(product["source_id"], product)
            if previous != product:
                raise ValueError("Conflicting versions of the same native source")
        for kind in ("coverage", "revision"):
            task = TafEvidenceTask.freeze({"schema": "disastertrace.taf_E_task.v1",
                "task_id": row["opportunity_id"] + "__" + kind, "kind": kind,
                "target": asdict(typed_target(target)), "as_of": row["cutoff"],
                "availability_basis": "declared_archive_scenario", "products": list(products.values())})
            tasks.append({"task": task.view(), "task_hash": task.task_hash, "messages": messages(task)})
            references.append(evaluate(task))
    (out / "public").mkdir()
    (out / "evaluator_only").mkdir()
    publish(out / "public/TASKS.json", tasks)
    publish(out / "evaluator_only/REFERENCES.json", references)
    publish(out / "DESIGN.json", {
        "schema": "disastertrace.v11.c2_development_design.v1",
        "scope": "registered design and native E reference sanity; no live branching or F attribution yet",
        "prefixes": 72, "parent_sessions": 24, "nominal_branches_per_prefix": 4,
        "roster_sha256": digest(out / "ROSTER.json"), "source_bindings": bindings,
        "branch_rules": ["no_further_paid_query", "first_sorted_eligible_registered_neighbor_query",
            "second_sorted_eligible_registered_neighbor_query", "all_remaining_registered_neighbor_queries"],
        "branch_budget": "inherit actual spent/reserved/shared quotas; do not grant additional credit",
        "same_state_fields": ["clock", "ledger", "authorization", "cache", "pending", "current_baseline",
            "current_override", "baseline_binding", "source_versions", "failure_continuation_policy"],
        "pending_rule": "finish the original serial in-flight invocation before a residual branch; never duplicate it",
        "infeasible_rule": "retain infeasible, missing-native, exhausted, late and failed branches; no replacement",
        "program_parser_access": "identical lawful parsing available to every policy",
        "causal_chain": ["native_field_change", "feature_change", "probability_change", "timely_adoption", "F_loss_change"],
        "aggregate_E_warning": "E status alone is not an input to the current native-feature F predictor",
        "oracle_scope": "finite evaluator E reachability; not a bound on future forecast skill",
        "confirmatory_gates": ["complete_week_scores_audited", "annual_source_roles_purged",
            "fixed_backend_qualified_on_development", "actual_checkpoint_restore_equal",
            "independent_source_process_groups_and_precision_design", "final_methods_code_and_hypotheses_frozen"],
        "confirmation_calendar": "Bay2025-02-17..23 remains unopened and at most a limited one-week confirmation",
        "statistics": {"primary": "paired natural-calendar Brier", "thresholds_m": [1000, 5000],
            "multiple_primary_claims": "Holm across the two threshold hypotheses",
            "sensitivity_blocks": ["region_week", "global_week", "72h", "7d"],
            "independent_process_count": None, "no_positive_stopping": True,
            "missing_result_bounds": "separate from sampling uncertainty",
            "insufficient_support": "report insufficient precision; no result-driven extension"},
        "model_calls": 0, "branch_runs": 0, "confirmation_opened": False,
    })
    publish(out / "RESULT.json", {"passed": True, "registered_prefixes": len(roster),
        "native_E_tasks": len(tasks), "reference_statuses": dict(Counter(r["answer"]["status"] for r in references)),
        "coverage": dict(Counter(r["answer"].get("coverage") for r in references if "coverage" in r["answer"])),
        "source_script_sha256": digest(Path(__file__)), "model_calls": 0, "F_scored": False,
        "current_scope": "native E construction sanity and development protocol registration only"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    main(args.batch.absolute(), args.out.absolute())
