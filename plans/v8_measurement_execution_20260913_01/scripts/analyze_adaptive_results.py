"""Describe an independently audited adaptive batch without issuing model calls."""

import argparse
import csv
import hashlib
import json
import math
import shutil
from collections import Counter
from pathlib import Path

from disastertrace.monitoring_v1.scoring import brier_report


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def distribution(values):
    values = sorted(values)
    if not values:
        return {"n": 0, "sum": 0, "mean": None, "p50": None, "p95": None, "max": None}
    return {
        "n": len(values),
        "sum": sum(values),
        "mean": sum(values) / len(values),
        "p50": values[math.ceil(0.5 * len(values)) - 1],
        "p95": values[math.ceil(0.95 * len(values)) - 1],
        "max": values[-1],
    }


def describe_case(batch, audit, case, receipt, group_scores):
    common = {
        "case": case["id"],
        "group": case["data_case"],
        "arm": case["arm"],
        "threshold_m": case["threshold_m"],
        "protocol": case["protocol"],
        "status": receipt["status"],
        "registered_opportunities": case["opportunities"],
    }
    if receipt["status"] != "qualified":
        return dict(common, formal_score=None, original_audit=receipt), [], []
    report_path = batch / "runs" / case["id"] / "REPORT.json"
    assert sha(report_path) == receipt["source_report_sha256"]
    report = read(report_path)
    outcomes = {
        row["opportunity_id"]: row
        for row in read(batch / "cases" / case["data_case"] / "OUTCOMES.json")
    }
    metrics_rows, opportunity_rows, changes = [], [], Counter()
    positive_targets = set()
    for row in report["snapshots"]:
        oid = row["opportunity_id"]
        outcome = outcomes[oid]
        y = outcome["value"] if outcome["status"] == "mature" else None
        base, probability = row["base_forecast"]["value"], row["forecast"]["value"]
        if y == 1:
            positive_targets.add(outcome["target_contract_hash"])
        metrics_rows.append(
            {
                "opportunity_id": oid,
                "base": base,
                "prediction": probability,
                "outcome": y,
                "baseline_kind": row["baseline_kind"],
                "region": row["target"]["entity"],
                "period": "2025-02-03_development",
                "source": "native_routine_METAR",
                "quality": outcome["quality_status"],
                "maturity": outcome["status"],
            }
        )
        gain = None if y is None else (base - y) ** 2 - (probability - y) ** 2
        if gain is not None:
            changes[
                "help"
                if gain > 1e-15
                else "harm"
                if gain < -1e-15
                else "no_loss_change"
            ] += 1
        changes["effective_probability_changed"] += int(probability != base)
        changes["effective_override"] += int(row["mode"] == "OVERRIDE")
        changes["same_value_override"] += int(
            row["mode"] == "OVERRIDE" and probability == base
        )
        opportunity_rows.append(
            {
                "case": case["id"],
                "opportunity_id": oid,
                "target_id": row["target"]["target_id"],
                "cutoff": row["cutoff"],
                "outcome": y,
                "base": base,
                "prediction": probability,
                "gain_vs_common_base": gain,
                "mode": row["mode"],
                "override_call_id": row["override_call_id"],
            }
        )
    metrics = brier_report(metrics_rows)
    canonical = group_scores["scores"]["scores"]
    arm_score = canonical["arms"][case["arm"]]
    assert metrics["opportunities"] == canonical["registered"] == case["opportunities"]
    assert metrics["settled"] == arm_score["scored"] == canonical["settled"]
    assert metrics["missing"] == canonical["missing"]
    if metrics["system_brier"] is None:
        assert arm_score["mean_loss"] is None
    else:
        assert abs(metrics["system_brier"] - arm_score["mean_loss"]) < 1e-14
        assert (
            abs(metrics["g_plus"] - metrics["g_minus"] - metrics["net_realized_gain"])
            < 1e-14
        )
    if "A00_follow" in canonical["arms"]:
        assert (
            abs(metrics["base_brier"] - canonical["arms"]["A00_follow"]["mean_loss"])
            < 1e-14
        )
    e_calls = [row for row in report["calls"] if row["head"] != "program"]
    counts, confusion, call_rows = Counter(), Counter(), []
    for row in e_calls:
        expected, predicted = (
            row["expected_e_from_disclosed_products"],
            row["reported_e"],
        )
        parsed = row["response_error"] is None and predicted is not None
        accepted = row["admission_status"] == "accepted"
        correct = parsed and predicted == expected
        overclaim = (
            parsed
            and predicted in {"supported", "refuted"}
            and expected in {"undetermined", "inconsistent"}
        )
        contrary = (
            parsed
            and expected in {"supported", "refuted"}
            and predicted in {"supported", "refuted"}
            and predicted != expected
        )
        confusion[(expected, predicted if parsed else "invalid_or_unfinished")] += 1
        for key, condition in {
            "parsed_answers": parsed,
            "correct_parsed_answers": correct,
            "correct_accepted_answers": correct and accepted,
            "unsupported_determination": overclaim,
            "unsupported_determination_accepted": overclaim and accepted,
            "contrary_determination": contrary,
            "always_unknown_correct_on_same_dispatched_bundles": expected
            == "undetermined",
            "changed_F_from_dispatch_base": row["proposed_probability"] is not None
            and row["proposed_probability"]
            != row["bundle"]["payload"]["baseline"]["forecast"]["value"],
        }.items():
            counts[key] += int(condition)
        call_rows.append(
            {
                "case": case["id"],
                "call_id": row["call_id"],
                "opportunity_id": row["opportunity_id"],
                "started_at": row["started_at"],
                "expected_E_at_dispatch": expected,
                "reported_E": predicted,
                "response_error": row["response_error"],
                "admission_status": row["admission_status"],
                "unsupported_determination": bool(overclaim),
                "evidence_query_ids": row["evidence_query_ids"],
                "proposed_probability": row["proposed_probability"],
                "dispatch_baseline": row["bundle"]["payload"]["baseline"]["forecast"][
                    "value"
                ],
            }
        )
    assert (
        counts["correct_accepted_answers"] == receipt["E_correct_timely_model_answers"]
    )
    model_receipts = read(audit / case["id"] / "RECEIPTS.json")
    receipt_groups = {
        role: [
            r
            for r in model_receipts
            if r["call_id"].startswith("select-") == (role == "selector")
        ]
        for role in ("selector", "predictor")
    }
    role_costs = {
        role: {
            "callbacks": len(rows),
            "input_tokens": sum(r["input_tokens"] for r in rows),
            "output_tokens": sum(r["output_tokens"] for r in rows),
            "compute_seconds_charged_per_call": distribution(
                [r["compute_seconds"] for r in rows]
            ),
            "delivery_elapsed_seconds": distribution(
                [r["elapsed_seconds"] for r in rows]
            ),
            "elapsed_seconds_outside_measured_model_compute": distribution(
                [max(0, r["elapsed_seconds"] - r["compute_seconds"]) for r in rows]
            ),
            "unfinished": sum(not r["ended_with_eos"] for r in rows),
            "response_errors": sum(r["response_error"] is not None for r in rows),
        }
        for role, rows in receipt_groups.items()
    }
    called_ids = {r["opportunity_id"] for r in e_calls}
    registered_ids = set(outcomes)
    assert called_ids <= registered_ids
    common.update(
        config={
            k: report["config"][k]
            for k in (
                "allocation_mode",
                "authorization_mode",
                "selector_kind",
                "predictor_kind",
                "request_budget",
                "model_call_budget",
            )
        },
        formal_score=metrics["system_brier"],
        F_metrics=metrics,
        positive_opportunities=sum(r["outcome"] == 1 for r in metrics_rows),
        unique_positive_targets=len(positive_targets),
        F_change_counts=dict(changes),
        E_availability_at_cutoff=report["e_counts"],
        E_determined_at_cutoff=sum(
            report["e_counts"].get(k, 0) for k in ("supported", "refuted")
        ),
        E_model_calls=len(e_calls),
        E_opportunities_with_model_submission=len(called_ids),
        E_opportunities_without_model_submission=len(registered_ids - called_ids),
        E_call_counts=dict(counts),
        E_confusion=[
            {"expected_E_at_dispatch": a, "reported_E": b, "count": n}
            for (a, b), n in sorted(confusion.items())
        ],
        actual_model_calls=receipt["actual_model_calls"],
        program_forecasts=report["actual_program_forecast_calls"],
        source_queries=len(report["source_receipts"]),
        resource_spent=report["resource_spent"],
        resource_reserved=report["resource_reserved"],
        role_costs=role_costs,
        attempt_statuses=dict(Counter(r["status"] for r in report["attempts"])),
        forecast_admission_statuses=receipt["forecast_admission_statuses"],
        source_report_sha256=sha(report_path),
    )
    return common, call_rows, opportunity_rows


def contrasts(rows):
    result = []
    for group in sorted({r["group"] for r in rows}):
        arms = {
            r["arm"]: r
            for r in rows
            if r["group"] == group and r["status"] == "qualified"
        }
        for left, right, factor in (
            ("A01_base_program", "A07_base_llm", "predictor_base_only"),
            ("A02_one_program", "A08_one_llm", "predictor_one_read"),
            ("A03_batch_program", "A09_batch_llm", "predictor_batch"),
            ("A04_risk_program", "A10_risk_llm", "predictor_risk"),
            ("A05_coverage_program", "A11_coverage_llm", "predictor_coverage"),
            ("A06_llm_program", "A12_llm_llm", "predictor_llm_selector"),
            (
                "A04_risk_program",
                "A06_llm_program",
                "selector_vs_risk_program_predictor",
            ),
            (
                "A05_coverage_program",
                "A06_llm_program",
                "selector_vs_coverage_program_predictor",
            ),
            ("A10_risk_llm", "A12_llm_llm", "selector_vs_risk_llm_predictor"),
            ("A11_coverage_llm", "A12_llm_llm", "selector_vs_coverage_llm_predictor"),
        ):
            item = {
                "group": group,
                "comparison": factor,
                "reference_arm": left,
                "candidate_arm": right,
            }
            if left not in arms or right not in arms:
                item.update(status="not_both_qualified", metrics=None)
            else:
                a, b = arms[left], arms[right]
                item.update(
                    status="qualified_descriptive_pair",
                    brier_gain_reference_minus_candidate=a["formal_score"]
                    - b["formal_score"],
                    E_determined_difference=b["E_determined_at_cutoff"]
                    - a["E_determined_at_cutoff"],
                    source_query_difference=b["source_queries"] - a["source_queries"],
                    model_call_difference=b["actual_model_calls"]
                    - a["actual_model_calls"],
                )
            result.append(item)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-rehearsal", action="store_true")
    args = parser.parse_args()
    plan, validation = (
        read(args.batch / "PLAN.json"),
        read(args.audit / "VALIDATION.json"),
    )
    assert plan["engineering_rehearsal"] == args.allow_rehearsal
    assert validation["plan_sha256"] == sha(args.batch / "PLAN.json")
    assert (args.audit / "COMPLETE.json").is_file()
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(Path(__file__), args.output / Path(__file__).name)
    receipts = {r["case"]: r for r in validation["sessions"]}
    all_rows, calls, opportunities = [], [], []
    for case in plan["cases"]:
        row, case_calls, case_opportunities = describe_case(
            args.batch,
            args.audit,
            case,
            receipts[case["id"]],
            read(args.audit / (case["data_case"] + "_SCORES.json")),
        )
        all_rows.append(row)
        calls.extend(case_calls)
        opportunities.extend(case_opportunities)
    assert (
        sum(r.get("actual_model_calls", 0) for r in all_rows)
        == validation["audited_actual_model_calls"]
    )
    save(args.output / "ARMS.json", all_rows)
    save(args.output / "E_CALLS.json", calls)
    save(args.output / "OPPORTUNITIES.json", opportunities)
    save(args.output / "CONTRASTS.json", contrasts(all_rows))
    with (args.output / "ARMS.csv").open("x", newline="") as handle:
        fields = [
            "case",
            "status",
            "registered_opportunities",
            "formal_score",
            "positive_opportunities",
            "unique_positive_targets",
            "E_determined_at_cutoff",
            "E_model_calls",
            "E_opportunities_without_model_submission",
            "source_queries",
            "actual_model_calls",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)
    summary = {
        "passed": True,
        "registered_sessions": len(all_rows),
        "qualified_sessions": sum(r["status"] == "qualified" for r in all_rows),
        "registered_opportunity_rows": sum(
            r["registered_opportunities"] for r in all_rows
        ),
        "actual_model_calls_in_qualified_sessions": validation[
            "audited_actual_model_calls"
        ],
        "issued_model_calls_all_sessions": validation["issued_model_calls"],
        "unique_generation_batch_seconds": validation[
            "unique_generation_batch_seconds"
        ],
        "all_metrics_match_independent_scores": True,
        "original_audit_sha256": sha(args.audit / "VALIDATION.json"),
        "engineering_rehearsal": plan["engineering_rehearsal"],
        "new_model_calls": 0,
        "independent_confirmation": False,
        "interpretation": [
            "Posthoc exposed development descriptions; thresholds and protocols stay separate.",
            "Program time is a declared scenario and model delivery is measured; this is not deployment cost-effectiveness or a pure reasoning-only intervention.",
            "Changing selector or predictor can change subsequent evidence and timing. These are policy-level comparisons, not identical-input predictor effects.",
            "E availability is at cutoff; model E correctness is on its actual dispatch bundle, not evaluator-only later evidence.",
            "No-submission uses distinct registered opportunity IDs; repeated calls never enlarge the opportunity denominator.",
            "Per-call batch compute can count the same physical generation batch for multiple independent sessions; unique batch seconds are reported separately.",
            "Elapsed time outside measured model compute includes durable checkpoints, scheduling, transfer and controller observation; it is not an identified CPU-only or network-only bottleneck.",
            "Latency quantiles use nearest rank. No independent weather-process confidence interval is inferred from one day.",
            "Unknown is the benchmark undetermined status. Always-unknown is evaluated only on the same dispatched E bundles.",
        ],
    }
    save(args.output / "VALIDATION.json", summary)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
