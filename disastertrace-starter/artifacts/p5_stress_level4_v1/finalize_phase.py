"""Seal a completed P5 status only after actual jobs and independent checks pass."""

import re
from collections import Counter

from acp_common import FACTORS, HERE
from launch_p5 import verify_bound_files

from disastertrace.local_eval.storage import digest, now, read, write
from disastertrace.stress_eval import execution


def main():
    accepted = read(HERE / "LIVE_ACCEPTANCE.json")
    verify_bound_files(accepted)
    offline = read(HERE / "OFFLINE_ACCEPTANCE.json")
    for name, expected in offline["evidence_sha256"].items():
        if digest(HERE / name) != expected:
            raise ValueError("historical P5 offline evidence changed")
    jobs = read(HERE / "completed_jobs_verified.json")
    portable = read(HERE / "portable_model_verification.json")
    preservation = read(HERE / "preservation_final.json")
    analysis = read(HERE / "analysis/analysis.json")
    comparison = read(HERE / "stress_comparison/comparison.json")
    if any(value["status"] != "passed" for value in (jobs, portable, preservation)):
        raise ValueError("terminal jobs, portable review and preservation required")
    if (
        not analysis["complete"]
        or analysis["received_total"] != 1620
        or jobs["received_total"] != 1620
        or jobs["attempted_total"] != 1620
        or portable["analysis_id"] != analysis["analysis_id"]
        or portable["comparison_id"] != comparison["comparison_id"]
    ):
        raise ValueError("full matching phase results required")
    evidence = [
        "LIVE_ACCEPTANCE.json",
        "OFFLINE_ACCEPTANCE.json",
        "completed_jobs_verified.json",
        "portable_model_verification.json",
        "preservation_final.json",
        "analysis/analysis.json",
        "stress_comparison/comparison.json",
        "compare_stress.py",
        "analyze_p5.py",
        "validate_grammar.py",
        "verify_review.py",
        "prepare_review.py",
        "finalize_phase.py",
        "test_stress_comparison.py",
        "verify_completed_jobs.py",
        "package_review.py",
        "validation/portable_model_review/result.json",
        "validation/preservation_final/result.json",
        "validation/verify_completed_jobs/result.json",
        "validation/lint_postprocessing_final/result.json",
    ]
    grammar_counts, methods = Counter(), {}
    for factor in FACTORS:
        unit = HERE / "units" / factor
        plan = read(unit / "execution_live/execution.json")
        if execution.source_inventory() != plan["implementation_files"]:
            raise ValueError("current primary implementation differs from freeze")
        report = read(unit / "model_report/report.json")
        grammar = read(unit / "grammar_model/report.json")
        if (
            grammar["status"] != "passed"
            or grammar["counts"]["sequences"] != 540
            or grammar["audit_id"] != report["audit_id"]
            or report["audit_id"] != portable["units"][factor]["audit_id"]
        ):
            raise ValueError("actual grammar and CPU report binding required")
        grammar_counts.update(grammar["counts"])
        methods[factor] = {method: score["metrics"] for method, score in report["methods"].items()}
        evidence += [
            f"units/{factor}/model_report/report.json",
            f"units/{factor}/model_report/audit.json",
            f"units/{factor}/grammar_model/report.json",
            f"units/{factor}/grammar_model/manifest.json",
            f"validation/grammar_{factor}/result.json",
        ]
    tests = {}
    for name in ("tests_acp_launcher", "tests_stress_comparison"):
        directory = HERE / "validation" / name
        record = read(directory / "result.json")
        if record["exit_code"] or record["log_sha256"] != digest(directory / "stdout.log"):
            raise ValueError("test observation changed")
        passed = re.findall(r"\b(\d+) passed\b", (directory / "stdout.log").read_text())
        tests[name] = int(passed[-1])
        evidence += [f"validation/{name}/result.json", f"validation/{name}/stdout.log"]
    status = {
        "schema_version": "p5_acp_completed_status_v1",
        "complete": True,
        "recorded_at": now(),
        "status": "actual_phase_and_independent_verification_complete",
        "acceptance_id": accepted["acceptance_id"],
        "analysis_id": analysis["analysis_id"],
        "comparison_id": comparison["comparison_id"],
        "phase_launch_consumed": True,
        "planned_responses": 1620,
        "attempted_responses": 1620,
        "received_responses": 1620,
        "model_retries": 0,
        "platform_retries": 0,
        "extra_model_probes": 0,
        "preflight_model_calls": 0,
        "parallel_h100_gpus": 3,
        "user_gpu_cap": 4,
        "all_acp_jobs_succeeded": True,
        "gpu_resources_released_per_acp_terminal_state": True,
        "jobs": jobs["units"],
        "scores": methods,
        "usage": analysis["usage"],
        "gpu_cost_usd": None,
        "field_error_reasons": dict(
            sum((Counter(v["field_error_reasons"]) for v in analysis["units"].values()), Counter())
        ),
        "incorrect_checkpoints": sum(
            m["incorrect_checkpoints"]
            for u in analysis["units"].values()
            for m in u["methods"].values()
        ),
        "actual_grammar_replay": dict(grammar_counts),
        "tests_executed_this_extension": tests,
        "distinct_new_tests_passed": sum(tests.values()),
        "inherited_test_acceptance_verified_not_rerun": offline["tests"],
        "historical_preservation": preservation,
        "offline_acceptance_entries_unchanged": len(offline["evidence_sha256"]),
        "live_acceptance_entries_unchanged": len(accepted["evidence_sha256"]),
        "relocated_cpu_verification": portable,
        "paid_api_calls": 0,
        "heldout_calls": 0,
        "training": False,
        "new_human_annotations": 0,
        "llm_judge": False,
        "model_outputs_repaired": False,
        "fixed_denominators_preserved": True,
        "git_commit_or_publication_this_extension": False,
        "interpretation": comparison["interpretation"],
        "next_plan": "NEXT_PHASE_PLAN_ACP.md",
        "archive_verification_record": "archive_verification.json",
        "archive_note": "The archive is created after this status and independently verified in its separate record.",
        "evidence_sha256": {name: digest(HERE / name) for name in evidence},
    }
    write(HERE / "FINAL_STATUS.json", status)
    print(
        {
            "status": status["status"],
            "responses": 1620,
            "distinct_new_tests": status["distinct_new_tests_passed"],
            "grammar_tokens": grammar_counts["constrained_tokens_checked"],
            "final_status_sha256": digest(HERE / "FINAL_STATUS.json"),
        }
    )


if __name__ == "__main__":
    main()
