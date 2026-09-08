"""Bind completed model/source evidence without regenerating any model answer."""

import argparse
from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.local_eval.storage import digest, inventory, read, verify_seal, write

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]


def evidence():
    selected = {}
    roots = [
        HERE,
        PROJECT / "artifacts/nhc_forecast_source_v1",
        PROJECT / "artifacts/p6_parallel_preparation_v1",
        PROJECT / "work/p6-live-v1",
        PROJECT / "src/disastertrace/repeat_live",
        PROJECT / "src/disastertrace/repeat_live_review",
        PROJECT / "src/disastertrace/forecast_source",
        PROJECT / "src/disastertrace/repeat_parallel",
        PROJECT / "tests/p6_live",
        PROJECT / "tests/p6_live_review",
        PROJECT / "tests/forecast_source",
        PROJECT / "tests/p6_parallel",
    ]
    for root in roots:
        for path in sorted(root.rglob("*")):
            if (
                path.is_file()
                and "cache" not in path.parts
                and "__pycache__" not in path.parts
                and path.name != "COMPLETED_ACCEPTANCE.json"
                and not path.name.endswith(".tmp")
            ):
                selected[str(path.relative_to(PROJECT))] = digest(path)
    for name in ("README_P6_LIVE_V1.md",):
        selected[name] = digest(PROJECT / name)
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    target = HERE / "COMPLETED_ACCEPTANCE.json"
    if args.verify:
        record = read(target)
        if record["acceptance_id"] != fingerprint(
            {k: v for k, v in record.items() if k != "acceptance_id"}
        ):
            raise ValueError("completed acceptance identity changed")
        for name, expected in record["files"].items():
            if digest(PROJECT / name) != expected:
                raise ValueError("accepted evidence changed: " + name)
        print(
            {
                "status": record["status"],
                "acceptance_id": record["acceptance_id"],
                "files_verified": len(record["files"]),
                "additional_model_calls": 0,
            },
            flush=True,
        )
        return
    finalization = read(HERE / "finalization_003/result.json")
    if finalization["status"] != "passed" or any(s["exit_code"] for s in finalization["steps"]):
        raise ValueError("CPU continuation is not complete")
    model_recovery = read(HERE / "finalization_002/result.json")
    if len(model_recovery["steps"]) != 7 or any(s["exit_code"] for s in model_recovery["steps"][:6]):
        raise ValueError("model CPU review steps are not complete")
    job = read(HERE / "MODEL_JOB_OBSERVED.json")
    report = HERE / "reports/model_review_v2"
    verify_seal(report)
    audited, scores = read(report / "audit.json"), read(report / "scores.json")
    plan = read(HERE / "execution_live_02/execution.json")
    review_binding = read(HERE / "token_text_review_v2/REVIEW_BINDING.json")
    review_manifest = verify_seal(HERE / "token_text_review_v2/review_source")
    if (
        review_binding["review_source_id"] != review_manifest["package_id"]
        or review_binding["execution_id"] != plan["execution_id"]
        or review_binding["run_files"] != audited["run_files"]
    ):
        raise ValueError("CPU-only review binding differs from preserved capture")
    if inventory(plan["run_path"]) != audited["run_files"]:
        raise ValueError("actual run differs from audited evidence")
    grammar = read(HERE / "grammar_model/report.json")
    relocated = read(HERE / "CPU_RELOCATION.json")
    supplement = HERE / "supplementary_relocation_001"
    supplement_result = read(supplement / "result.json")
    relocated_attribution = read(supplement / "attribution_receipt.json")
    relocated_source = read(supplement / "source_receipt.json")
    verify_seal(HERE / "analysis")
    attribution = read(HERE / "analysis/summary.json")
    source_bundle = PROJECT / "artifacts/nhc_forecast_source_v1"
    verify_seal(source_bundle / "acquisition")
    verify_seal(source_bundle / "review_v1")
    source = read(source_bundle / "review_v1/report.json")
    source_runtime = read(source_bundle / "SOURCE_RUNTIME_V2.json")
    source_runtime_manifest = verify_seal(source_bundle / "source_execution_v2")
    if (
        source_runtime["source_package_id"] != source_runtime_manifest["package_id"]
        or source_runtime["scope_id"] != source["scope_id"]
        or source_runtime["requests_before_fix"] != 0
    ):
        raise ValueError("source runtime closure does not bind the original acquisition scope")
    parallel_root = PROJECT / "artifacts/p6_parallel_preparation_v1/four_worker_layout"
    verify_seal(parallel_root)
    parallel = read(parallel_root / "layout.json")
    from disastertrace.repeat_parallel.layout import validate

    validate(parallel, read(HERE / "execution_live_02/schedule.json"))
    if parallel["source_execution_id"] != audited["execution_id"] or parallel["worker_count"] != 4:
        raise ValueError("future parallel preview is not bound to the current matrix shape")
    if (
        grammar["status"] != "passed"
        or grammar["audit_id"] != audited["audit_id"]
        or relocated["status"] != "passed"
        or relocated["verification"]["audit_id"] != audited["audit_id"]
        or source["planned_bodies"] != 12
        or source["model_generations"] != 0
        or supplement_result["status"] != "passed"
        or any(s["exit_code"] for s in supplement_result["steps"])
        or relocated_attribution["status"] != "passed"
        or relocated_attribution["audit_id"] != audited["audit_id"]
        or relocated_attribution["analysis_id"] != attribution["analysis_id"]
        or relocated_source["status"] != "passed"
        or relocated_source["scope_id"] != source["scope_id"]
        or relocated_source["admitted_bodies"] != source["admitted_bodies"]
        or relocated_source["quarantined_bodies"] != source["quarantined_bodies"]
    ):
        raise ValueError("verification evidence does not reconcile")
    complete = (
        audited["complete"] is True
        and audited["received"] == 2160
        and any(s["name"] == "collect" and s["exit_code"] == 0 for s in job["worker"]["steps"])
    )
    record = {
        "schema_version": "p6_live_and_source_acceptance_v1",
        "status": "model_matrix_verified_after_cpu_audit_fix_source_reviewed"
        if complete
        else "stopped_prefix_verified_source_reviewed",
        "execution_id": plan["execution_id"],
        "model_job_id": job["job"]["name"],
        "model_job_state": job["job"]["state"],
        "original_worker_all_steps_passed": job["all_worker_steps_passed"],
        "cpu_recovery_passed": True,
        "review_source_id": review_manifest["package_id"],
        "model_audit_id": audited["audit_id"],
        "model_planned": 2160,
        "model_received": audited["received"],
        "model_matrix_complete": complete,
        "all_correct": scores["counts"]["all_correct"],
        "format_screens_passed": sum(s["passed"] for s in scores["format_screens"]),
        "format_screens_planned": len(scores["format_screens"]),
        "nhc_scope_id": source["scope_id"],
        "nhc_source_runtime_id": source_runtime["source_package_id"],
        "nhc_planned_bodies": 12,
        "nhc_admitted_bodies": source["admitted_bodies"],
        "nhc_quarantined_bodies": source["quarantined_bodies"],
        "supplementary_relocation_verified": True,
        "model_attribution_id": attribution["analysis_id"],
        "future_four_worker_layout_id": parallel["layout_id"],
        "future_parallel_preview_dispatch_compatible": False,
        "historical_offline_acceptance_id": "1495dc5c3c31d5007ac3ca067a7660ddd6b0c14607c980d9c56cd87497b0147d",
        "cache_files_excluded": True,
        "mutable_current_phase_pointer_excluded": True,
        "files": evidence(),
        "additional_model_calls_during_acceptance": 0,
    }
    record["acceptance_id"] = fingerprint(record)
    write(target, record)
    print({k: v for k, v in record.items() if k != "files"}, flush=True)


if __name__ == "__main__":
    main()
