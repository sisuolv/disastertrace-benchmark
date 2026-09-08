"""Seal audited cohort evidence without changing scores or running a model."""

import argparse
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.forecast_task.common import digest, fingerprint, inventory, read, write

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
PHASES = {
    "p11": ("p11_cohort_live_v1", "cohort_live", "cohort", "p11_cohort_live", "cohort_reviews_01"),
    "p12": ("p12_compact_grammar_v1", "compact_live", "compact", "p12_compact_live", "cohort_reviews_01"),
    "p13": ("p13_prompt_role_v1", "prompt_role_live", "role", "p13_prompt_role", "role_reviews_01"),
    "p14": ("p14_qwen_prompt_role_v1", "qwen_role_live", "role", "p14_qwen_role", "role_reviews_01"),
}


def identity(value, key):
    if value[key] != fingerprint({k: v for k, v in value.items() if k != key}):
        raise ValueError("identity differs: " + key)


def successful_command(folder, name):
    folder = Path(folder)
    result = read(folder / (name + "_result.json"))
    if result["exit_code"] != 0 or result["log_sha256"] != digest(folder / (name + ".log")):
        raise ValueError("required command or log differs: " + name)
    if not (folder / (name + "_intent.json")).is_file():
        raise ValueError("required command intent missing: " + name)
    return result


def validate_result(status, report, analysis, planned):
    identity(status, "status_id")
    identity(report, "report_id")
    identity(analysis, "analysis_id")
    if status["status"] != "passed":
        raise ValueError("terminal audit did not pass")
    for key in ("execution_id", "report_id", "counts"):
        if status[key] != report[key] or analysis[key] != report[key]:
            raise ValueError("audit/analysis identity or counts differ: " + key)
    scores = report["scores"]["counts"]
    if status["score_counts"] != scores or analysis["score_counts"] != scores:
        raise ValueError("score counts differ")
    if scores["planned"] != planned or not 0 <= scores["all_correct"] <= scores["received"] <= planned:
        raise ValueError("fixed denominator or score coverage differs")
    jobs = report["platform_jobs"]
    if (len(jobs) != 2 or {j["worker_id"] for j in jobs} != {0, 1}
            or any(j["state"] not in {"SUCCEEDED", "FAILED", "SUSPENDED", "DELETED"}
                   or j["released"] is not True for j in jobs)
            or status["platform_jobs"] != jobs):
        raise ValueError("both exact GPU allocations must be terminal and released")
    if (analysis["single_repeat_only"] is not True or analysis["planned_denominator_is_primary"] is not True
            or analysis["population_inference"] is not False or analysis["unit_normalization"] is not False
            or analysis["new_model_calls"] != 0):
        raise ValueError("analysis interpretation contract differs")
    returned = report["counts"]["raw_returned"]
    if scores["received"] != returned:
        raise ValueError("returned and scored coverage differ")
    return {
        "execution_id": report["execution_id"], "report_id": report["report_id"],
        "analysis_id": analysis["analysis_id"], "counts": report["counts"],
        "score_counts": scores, "platform_jobs": jobs,
        "model_matrix_complete": returned == planned,
        "unreturned_in_primary_denominator": planned - returned,
        "all_gpu_jobs_succeeded": all(j["state"] == "SUCCEEDED" for j in jobs),
    }


def verify_record(path, project=PROJECT):
    record = read(path)
    identity(record, "acceptance_id")
    files = record.get("evidence_sha256", record.get("files"))
    if not files:
        raise ValueError("acceptance lacks an evidence inventory")
    for name, expected in files.items():
        target = (project / name).resolve()
        if not target.is_relative_to(project.parent) or digest(target) != expected:
            raise ValueError("accepted evidence differs: " + name)
    return {"acceptance_id": record["acceptance_id"], "verified_files": len(files)}


def accept(phase):
    bundle_name, namespace, run_label, test_label, review_label = PHASES[phase]
    bundle = PROJECT / "artifacts" / bundle_name
    destination = bundle / "COMPLETED_ACCEPTANCE.json"
    if destination.exists():
        raise FileExistsError("acceptance already exists; use --verify")
    registration = read(bundle / "PREREGISTRATION.json")
    identity(registration, "design_id")
    if digest(bundle / "DESIGN.md") != registration["design_sha256"]:
        raise ValueError("registered design bytes differ")
    planned = registration["planned_answers"]
    reviews, files, results = ROOT / review_label, {}, {}

    def add(path):
        path = Path(path)
        if path.is_symlink() or not path.resolve().is_relative_to(PROJECT):
            raise ValueError("evidence must be a regular file within the project")
        files[path.relative_to(PROJECT).as_posix()] = digest(path)

    def add_tree(path):
        if not path.is_dir():
            raise ValueError("required evidence directory is missing: " + str(path))
        for name in inventory(path):
            if ".pytest_cache" not in Path(name).parts:
                add(path / name)

    gates = read(bundle / "TEST_GATES.json")
    if gates["core_tests_exit_code"] != 0 or any(gates["backend_tests_exit_codes"].values()):
        raise ValueError("CPU/backend acceptance gates did not pass")
    if gates["source_files"] != inventory(PROJECT / "src/disastertrace" / namespace):
        raise ValueError("source differs from the tested phase")
    if gates["test_files"] != inventory(PROJECT / "tests" / test_label):
        raise ValueError("phase tests differ from their bound gate")
    for name, expected in gates["logs"].items():
        if digest(ROOT / "validation" / name) != expected:
            raise ValueError("registered test log changed: " + name)
    test_result = successful_command(ROOT / "validation", "autonomy_acceptance_02")
    if test_result["script_sha256"] != digest(__file__):
        raise ValueError("acceptance script changed after its tests")
    for profile in registration["model_profiles"]:
        cpu = read(bundle / ("CPU_ACCEPTANCE_" + profile + ".json"))
        hardware = read(bundle / ("PREFLIGHT_ACCEPTANCE_" + profile + ".json"))
        identity(hardware, "acceptance_id")
        if (cpu["status"] != "passed" or cpu["design_id"] != registration["design_id"]
                or cpu["portable_review_exit_code"] != 0 or hardware["validation"]["status"] != "passed"
                or hardware["validation"]["model_calls"] != 0):
            raise ValueError("offline or no-generation hardware gate differs")
        for name, expected in cpu["source_files"].items():
            if digest(PROJECT / "src" / name) != expected:
                raise ValueError("CPU-accepted source changed: " + name)
        final = bundle / ("finalization_" + profile + "_01")
        status = read(final / "FINAL_STATUS.json")
        report = read(final / "global_report.json")
        for label in ("report", "verify_report", "token_replay", "cpu_relocation"):
            successful_command(final, label)
        for field, path in (("report_sha256", final / "global_report.json"),
                            ("token_replay_sha256", final / "token_replay.json"),
                            ("cpu_relocation_sha256", final / "cpu_relocated/receipt.json")):
            if status[field] != digest(path):
                raise ValueError("final audit receipt differs: " + field)
        key = phase + "_" + profile
        for action in ("analyze", "verify"):
            successful_command(reviews, key + "_" + action)
        analysis = read(reviews / (key + ".json"))
        results[profile] = validate_result(status, report, analysis, planned)
        for path in reviews.glob(key + "*"):
            if path.is_file():
                add(path)
        for suffix in ("model-v1", "diagnostics-v1", "portable-v1"):
            add_tree(PROJECT / ("work/" + phase + "-" + run_label + "-" + profile + "-" + suffix))

    for path in (bundle, PROJECT / "src/disastertrace" / namespace,
                 PROJECT / "tests" / test_label, PROJECT / "tests" / (phase + "_chain"),
                 PROJECT / "tests/autonomy_acceptance"):
        add_tree(path)
    review_namespace = "cohort_review" if phase in {"p11", "p12"} else "role_review"
    for path in (PROJECT / "src/disastertrace" / review_namespace,
                 PROJECT / "tests" / review_namespace):
        add_tree(path)
    add(reviews / "CLAIM.json")
    add(ROOT / ("watch_" + review_namespace + "s.py"))
    add(Path(__file__))
    add(ROOT / "analyze_cohort_stop.py")
    for path in (ROOT / "cohort_stops_01").glob(phase + "_*.json"):
        add(path)
    for pattern in (phase + "_*", "autonomy_acceptance_*", review_namespace + "_*"):
        for path in (ROOT / "validation").glob(pattern):
            if path.is_file():
                add(path)
    readme = PROJECT / ("README_" + phase.upper() + "_COMPLETED_V1.md")
    add(readme)
    add(bundle / "FINDINGS.md")
    ancestors = {}
    predecessor = "p10_forecast_cohort_v1" if phase == "p11" else ("p11_cohort_live_v1" if phase == "p12" else "p12_compact_grammar_v1")
    for name in {"p10_forecast_cohort_v1", predecessor}:
        path = PROJECT / "artifacts" / name / "COMPLETED_ACCEPTANCE.json"
        if name == "p10_forecast_cohort_v1":
            path = path.with_name("OFFLINE_ACCEPTANCE.json")
        ancestors[path.relative_to(PROJECT).as_posix()] = verify_record(path)
        add(path)
    record = {
        "schema_version": "expanded_cohort_completed_acceptance_v1", "status": "passed",
        "at": datetime.now(timezone.utc).isoformat(), "phase": phase,
        "design_id": registration["design_id"], "model_results": results,
        "all_gpu_jobs_released": True, "model_matrix_complete": all(r["model_matrix_complete"] for r in results.values()),
        "audit_acceptance_is_not_collection_success": True, "unit_normalization": False,
        "new_model_calls": 0, "ancestors": ancestors, "evidence_sha256": files,
    }
    record["acceptance_id"] = fingerprint(record)
    write(destination, record)
    return {"acceptance_id": record["acceptance_id"], "files": len(files), "status": "passed"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=PHASES, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    path = PROJECT / "artifacts" / PHASES[args.phase][0] / "COMPLETED_ACCEPTANCE.json"
    print(verify_record(path) if args.verify else accept(args.phase), flush=True)
