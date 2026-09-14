"""Close the registered v10 work only after audits and resource termination."""

import argparse
import datetime as dt
import hashlib
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_workers(run):
    ancestors, pid = set(), os.getpid()
    while pid and pid not in ancestors:
        ancestors.add(pid)
        try:
            pid = int(
                (Path("/proc") / str(pid) / "stat")
                .read_text()
                .split(") ", 1)[1]
                .split()[1]
            )
        except (FileNotFoundError, ProcessLookupError):
            break
    active = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) in ancestors:
            continue
        try:
            argv = (proc / "cmdline").read_bytes().split(b"\0")
            state = (proc / "stat").read_text().split(") ", 1)[1].split()[0]
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if state != "Z" and any(str(run).encode() in arg for arg in argv):
            active.append({"pid": int(proc.name), "state": state})
    return active


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    run = args.run.absolute()
    paths = [
        "reports/calibration_review_01/RESULT.json",
        "reports/capsule_relocation_01/RESULT.json",
        "reports/closure_inputs_01/RESULT.json",
        "reports/existing_audit_01/RESULT.json",
        "reports/feature_temperature_final_02/RESULT.json",
        "reports/formal_real_01/RESULT.json",
        "reports/ledger_afs_stress_02/RESULT.json",
        "reports/model_capsule_relocation_01/RESULT.json",
        "reports/model_components_01/RESULT.json",
        "reports/multicutoff_analysis_01/RESULT.json",
        "reports/native_feature_audit_01/RESULT.json",
        "reports/native_feature_sessions_audit_01/RESULT.json",
        "reports/query_controls_analysis_01/RESULT.json",
        "reports/seasonal_independent_audit_01/RESULT.json",
        "reports/temperature_postprocess_audit_01/RESULT.json",
        "reports/selector_audit_01/RESULT.json",
        "reports/selector_timing_02/RESULT.json",
        "reports/seasonal_controls_audit_01/RESULT.json",
        "reports/seasonal_budget_interpretation_01/RESULT.json",
        "reports/clarified_feature_comparison_01/RESULT.json",
        "reports/resources_final_01/RESULT.json",
        "large_feature_trial_01/final_audit_01/RESULT.json",
        "clarified_feature_trial_01/final_audit_01/RESULT.json",
        "formal_recovery_01/RESULT.json",
        "native_residual_02/RESULT.json",
        "seasonal_evaluation_01/RESULT.json",
        "calendar_feature_ablation_01/RESULT.json",
        "calendar_feature_ablation_01/independent_audit_01/RESULT.json",
    ]
    audits = {}
    for name in paths:
        result = read(run / name)
        if result.get("passed") is not True or result.get("confirmation_opened", False):
            raise ValueError("Required audit is not qualified: " + name)
        audits[name] = digest(run / name)
    resources = read(run / "reports/resources_final_01/RESULT.json")
    if not resources["all_terminal"] or resources["peak_reserved_h100"] > 4:
        raise ValueError("Owned cloud jobs have not closed within the GPU bound")
    active = local_workers(run)
    if active:
        raise ValueError("Owned local work is still running: " + json.dumps(active))
    tests = {}
    for name in ["full_monitoring_final_01", "final_changed_tests_01"]:
        result = read(run / "validation" / name / "RESULT.json")
        suites = ET.parse(run / "validation" / name / "junit.xml").getroot()
        totals = {
            key: sum(int(s.attrib[key]) for s in suites.iter("testsuite"))
            for key in ("tests", "errors", "failures", "skipped")
        }
        if result["exit_code"] or any(
            totals[k] for k in ("errors", "failures", "skipped")
        ):
            raise ValueError("Final test gate did not pass")
        tests[name] = totals
    if read(run / "validation/current_source_ruff_final_06/RESULT.json")["exit_code"]:
        raise ValueError("Final current-source lint did not pass")

    gpu = {}
    for name, workers in [
        ("fixed_packet_01", 4),
        ("feature_temperature_trial_02", 4),
        ("large_feature_trial_01", 1),
        ("clarified_feature_trial_01", 1),
    ]:
        receipts = [
            read(run / name / "gpu" / ("worker_" + str(i)) / "COMPLETE.json")
            for i in range(workers)
        ]
        ids = [key for r in receipts for key in r["completed_call_ids"]]
        count = sum(r["benchmark_calls"] for r in receipts)
        if len(ids) != count or len(set(ids)) != count:
            raise ValueError("Duplicate or missing local benchmark call identity")
        gpu[name] = {
            "benchmark_answers": count,
            "compatibility_calls": sum(r["compatibility_calls"] for r in receipts),
        }
    selector = read(run / "selector_trial_01/COMPLETE.json")
    selector_audit = read(run / "reports/selector_audit_01/RESULT.json")
    captured = len(list((run / "selector_trial_01").glob("*/spool/*.response.json")))
    if captured != selector_audit["captured_selector_calls"]:
        raise ValueError("Selector capture and audit counts differ")
    gpu["selector_trial_01"] = {
        "benchmark_answers": captured,
        "compatibility_calls": read(run / "selector_trial_01/PLAN.json")[
            "compatibility_calls"
        ],
        "completion_sha256": digest(run / "selector_trial_01/COMPLETE.json"),
        "cases": len(selector["cases"]),
    }
    apis = {
        name: read(run / name / "api/COMPLETE.json")
        for name in ("fixed_packet_01", "feature_temperature_trial_02")
    }
    api_calls = sum(r["ledger"]["dispatch_intents"] for r in apis.values())
    api_answers = sum(r["states"].get("RECEIVED", 0) for r in apis.values())
    not_attempted = sum(r["states"].get("NOT_ATTEMPTED", 0) for r in apis.values())
    fees = read(run / "reports/original_fee_reconciliation_01/RESULT.json")
    original = next(s for s in fees["scopes"] if s["scope"] == "api_evidence_01")
    old_run = run.parent / "v9_followup_execution_20260914_01"
    if (
        digest(old_run / "api_evidence_01/BUDGET.json")
        != original["original_budget_sha256"]
    ):
        raise ValueError("The original unresolved API ledger changed")
    if original["unresolved_reservations"] != 62 or not_attempted != 424:
        raise ValueError(
            "Expected retained unresolved or unattempted denominator changed"
        )
    gpu_answers = sum(r["benchmark_answers"] for r in gpu.values())
    gpu_compat = sum(r["compatibility_calls"] for r in gpu.values())
    final = {
        "schema": "disastertrace.v10.closed_execution.v1",
        "phase": "EXPERIMENTS_CLOSED",
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "authorized_window": ["2026-09-14T15:56:00Z", "2026-09-15T01:56:00Z"],
        "all_registered_work_closed": True,
        "closure_includes_explicit_not_attempted_API_tasks": True,
        "confirmation_opened": False,
        "all_scientific_gates_passed": False,
        "all_resources_terminal": True,
        "cloud_jobs": resources["jobs"],
        "peak_reserved_h100": resources["peak_reserved_h100"],
        "registered_local_watchers_active": active,
        "tests": tests,
        "tests_are_overlapping_regression_checks_not_weather_cases": True,
        "audits": audits,
        "gpu_studies": gpu,
        "new_gpu_benchmark_answers": gpu_answers,
        "new_gpu_compatibility_calls": gpu_compat,
        "new_gpu_calls": gpu_answers + gpu_compat,
        "new_api_calls_including_compatibility": api_calls,
        "new_api_benchmark_answers": api_answers,
        "new_api_benchmark_not_attempted": not_attempted,
        "new_benchmark_answers_total": gpu_answers + api_answers,
        "new_model_calls_total_including_compatibility": gpu_answers
        + gpu_compat
        + api_calls,
        "new_API_settled_upper_usd": sum(
            r["ledger"]["actual_upper_nanodollars"] for r in apis.values()
        )
        / 1e9,
        "new_API_unresolved_calls": sum(
            r["ledger"]["unresolved_reservations"] for r in apis.values()
        ),
        "new_API_unresolved_upper_usd": sum(
            r["ledger"]["unresolved_nanodollars"] for r in apis.values()
        )
        / 1e9,
        "original_E01_unresolved_calls_retained": original["unresolved_reservations"],
        "original_E01_unresolved_upper_usd_retained": original["unresolved_nanodollars"]
        / 1e9,
        "costs_are_upper_estimates_not_provider_invoices": True,
        "seasonal_registered_opportunities": 12096,
        "seasonal_region_weeks": 12,
        "seasonal_global_calendar_blocks": 4,
        "seasonal_budget_trajectories": read(
            run / "seasonal_controls_01/COMPLETE.json"
        )["completed"],
        "scope": "Completed real-data development, component diagnostics, program/model comparisons and bounded replay; no independent-confirmation claim",
        "remaining_gates": [
            "complete-season pre-evaluation fitting and externally specified natural-process groups",
            "frozen independent confirmation with sufficient severe-positive support",
            "LLM value beyond strong same-information program and batch controls",
            "qualified temperature historical supplementary evidence",
            "matched physical MRMS/HEFS forecast and outcome contracts",
            "native multimodal, action feedback and complete16hazard task admission",
            "prospective first-seen capture and online model evaluation",
        ],
    }
    with (run / "FINAL_RESULT.json").open("x") as handle:
        json.dump(final, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in final.items()
                if k not in {"audits", "gpu_studies", "tests", "remaining_gates"}
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
