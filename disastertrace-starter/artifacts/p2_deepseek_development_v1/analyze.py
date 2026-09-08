"""Recompute a descriptive P2 error inventory from a verified captured report."""

import argparse
import json
from collections import Counter
from itertools import combinations
from pathlib import Path

import runner


def analyze(plan, report, audit):
    from disastertrace.controlled.compiler import reference_at
    from disastertrace.controlled.schema import parse_decision

    episodes = {episode["episode_id"]: episode for episode in plan["episodes"]}
    records = {
        (
            record["slot"]["method"],
            record["slot"]["episode_id"],
            record["slot"]["checkpoint_id"],
        ): record
        for record in audit["records"]
    }
    errors, checkpoints, actions, by_method = [], [], [], {}
    for method, score in report["methods"].items():
        reasons = Counter()
        for row in score["per_checkpoint"]:
            episode_id, checkpoint_id = row["episode_id"], row["checkpoint_id"]
            record = records.get((method, episode_id, checkpoint_id))
            gold = reference_at(episodes[episode_id], checkpoint_id)
            decision = None
            if record is not None:
                try:
                    decision = parse_decision(record["raw_response"])
                except (ValueError, TypeError, KeyError, RecursionError):
                    pass
            identity = {
                key: row[key]
                for key in ("episode_id", "group_id", "family", "branch", "checkpoint_id")
            }
            identity["method"] = method
            identity["slot_index"] = record["slot_index"] if record else None
            if row["status"] != "ok":
                checkpoints.append(
                    {
                        **identity,
                        "status": row["status"],
                        "finish_reason": record["completion"]["metadata"]["finish_reason"]
                        if record
                        else None,
                        "raw_response_bytes": len(record["raw_response"].encode())
                        if record
                        else None,
                    }
                )
            if not row["counts"]["action_correct"]:
                actions.append(
                    {
                        **identity,
                        "expected": gold["action"],
                        "submitted": decision["action"] if decision else None,
                        "checkpoint_status": row["status"],
                    }
                )
            for field, slot in row["slots"].items():
                if slot["grounded_correct"]:
                    continue
                reasons[slot["reason"]] += 1
                submitted = decision["state"][field] if decision else None
                cited_lines = []
                for citation in submitted["evidence"] if submitted else []:
                    text = None
                    for evidence in record["request"]["evidence"]:
                        if evidence["record_id"] == citation["record_id"]:
                            lines = evidence["text"].splitlines()
                            if 0 < citation["line"] <= len(lines):
                                text = lines[citation["line"] - 1]
                            break
                    cited_lines.append({**citation, "visible_line": text})
                errors.append(
                    {
                        **identity,
                        "field": field,
                        "reason": slot["reason"],
                        "expected": gold["state"][field],
                        "submitted": submitted,
                        "cited_visible_lines": cited_lines,
                    }
                )
        metric = score["metrics"]["overall_grounding"]
        if sum(reasons.values()) != metric["denominator"] - metric["numerator"]:
            raise ValueError("error inventory does not reconcile with frozen scores")
        by_method[method] = {
            "metrics": score["metrics"],
            "status_counts": score["status_counts"],
            "field_failure_reasons": dict(reasons),
            "by_family": score["by_family"],
            "by_source_group": score["by_group"],
            "matched_branches": score["matched_pairs"],
        }
    comparisons = []
    for left, right in combinations(report["methods"], 2):
        rows = {
            method: {
                (row["episode_id"], row["checkpoint_id"]): row
                for row in report["methods"][method]["per_checkpoint"]
            }
            for method in (left, right)
        }
        if rows[left].keys() != rows[right].keys() or len(rows[left]) != 90:
            raise ValueError("paired method denominators changed")
        for group in [None, *sorted({r["group_id"] for r in rows[left].values()})]:
            pairs = [
                (a, rows[right][key])
                for key, a in rows[left].items()
                if group is None or a["group_id"] == group
            ]
            outcomes = Counter(
                "left_only"
                if a["counts"]["all_correct"] > b["counts"]["all_correct"]
                else "right_only"
                if a["counts"]["all_correct"] < b["counts"]["all_correct"]
                else "both_correct"
                if a["counts"]["all_correct"]
                else "both_incorrect"
                for a, b in pairs
            )
            comparisons.append(
                {
                    "left": left,
                    "right": right,
                    "source_group": group,
                    "planned_checkpoints": len(pairs),
                    "all_correct_outcomes": {
                        key: outcomes[key]
                        for key in ("left_only", "right_only", "both_correct", "both_incorrect")
                    },
                    "grounded_field_difference_left_minus_right": sum(
                        a["counts"]["grounded_correct"] - b["counts"]["grounded_correct"]
                        for a, b in pairs
                    ),
                    "statistical_significance_tested": False,
                }
            )
    return {
        "schema_version": "p2_development_descriptive_analysis_v1",
        "execution_id": report["execution_id"],
        "audit_id": report["audit_id"],
        "mode": report["mode"],
        "complete": report["complete"],
        "model_calls": report["model_calls"],
        "additional_model_calls": 0,
        "reliability": report["reliability"],
        "methods": by_method,
        "checkpoint_failures": checkpoints,
        "field_errors": errors,
        "action_errors": actions,
        "paired_method_comparisons": comparisons,
        "all_methods_all_checkpoints_correct": report["complete"]
        and all(
            score["metrics"]["all_correct_checkpoints"]["value"] == 1
            for score in report["methods"].values()
        ),
        "interpretation": (
            "Descriptive development comparison with dependent branches and checkpoints. "
            "All methods receive cumulative evidence; no internal-memory claim, "
            "new human annotation, changed Gold, or LLM judge."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    _, plan = runner.verify()
    _, _, reporter, _ = runner.frozen_modules()
    verification = reporter.verify_report(runner.HERE / "execution", args.run, args.report)
    report = runner.read(args.report / "report.json")
    audit = runner.read(args.report / "audit.json")
    if (report["mode"] != "model_http") != args.diagnostic:
        raise ValueError("analysis origin must match explicit diagnostic/model mode")
    analysis = analyze(plan, report, audit)
    manifest = {
        "schema_version": "p2_descriptive_analysis_binding_v1",
        "analysis_script_sha256": runner.sha(Path(__file__)),
        "report_package_id": verification["package_id"],
        "execution_id": plan["execution_id"],
        "audit_id": audit["audit_id"],
        "additional_model_calls": 0,
    }
    if args.verify:
        if runner.read(args.output / "analysis.json") != analysis:
            raise ValueError("analysis differs from captured report reconstruction")
        if runner.read(args.output / "binding.json") != manifest:
            raise ValueError("analysis binding changed")
    else:
        args.output.mkdir(parents=True, exist_ok=False)
        for name, value in (("analysis.json", analysis), ("binding.json", manifest)):
            (args.output / name).write_text(json.dumps(value, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": "verified" if args.verify else "generated",
                "field_errors": len(analysis["field_errors"]),
                "checkpoint_failures": len(analysis["checkpoint_failures"]),
                "action_errors": len(analysis["action_errors"]),
                "report_package_id": verification["package_id"],
                "additional_model_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
