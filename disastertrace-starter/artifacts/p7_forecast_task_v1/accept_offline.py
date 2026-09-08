"""Bind the completed native-task milestone without any generation permission."""

import argparse
from pathlib import Path

from disastertrace.forecast_task.common import digest, fingerprint, read, verify, write

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
REQUIRED = (
    "unit_003",
    "gpu_preview_tests_001",
    "lint_final",
    "build_001",
    "cpu_relocation_002",
    "p6_live_preservation_001",
    "p6_offline_preservation_001",
)


def evidence():
    files = {}
    roots = (
        HERE,
        PROJECT / "src/disastertrace/forecast_task",
        PROJECT / "tests/p7_forecast_task",
        PROJECT / "work/p7-forecast-task-portable-v1",
    )
    for root in roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or any(p in ("__pycache__", ".pytest_cache") for p in path.parts):
                continue
            if path == HERE / "OFFLINE_ACCEPTANCE.json":
                continue
            if path.is_relative_to(HERE / "validation"):
                step = path.relative_to(HERE / "validation").parts[0]
                if (
                    step.startswith("acceptance_")
                    or not (HERE / "validation" / step / "result.json").exists()
                ):
                    continue
            files[path.relative_to(PROJECT).as_posix()] = digest(path)
    files["README_P7_FORECAST_TASK_V1.md"] = digest(PROJECT / "README_P7_FORECAST_TASK_V1.md")
    return files


def accept():
    for name in REQUIRED:
        if read(HERE / "validation" / name / "result.json")["exit_code"] != 0:
            raise ValueError("required check did not pass: " + name)
    execution_root = HERE / "execution_v1"
    package = verify(execution_root)
    source = verify(execution_root / "source")
    for name, expected in source["files"].items():
        if digest(PROJECT / name) != expected:
            raise ValueError("new source/tests differ from frozen execution")
    plan = read(execution_root / "execution.json")
    data = read(execution_root / "data/dataset.json")
    cpu = read(HERE / "CPU_RELOCATION.json")
    context = read(execution_root / "context.json")
    preservation = read(HERE / "PRESERVATION.json")
    tests = read(HERE / "VALIDATION_RESULTS.json")
    if (
        plan["generation_authorized"] is not False
        or plan["dispatch_compatible"] is not False
        or plan["model_generations"] != 0
        or plan["planned_slots_per_policy"] != 1542
        or cpu["status"] != "passed"
        or cpu["cli_exits"] != [0, 0]
        or cpu["execution_id"] != plan["execution_id"]
        or cpu["package_id"] != package["package_id"]
        or cpu["source_package_id"] != source["package_id"]
        or any(cpu["unexpected_blocked_attempts"].values())
        or cpu["torch_and_vllm_loaded"]
        or len(cpu["blocked_optional_import_probes"]) != 1
        or cpu["blocked_optional_import_probes"][0]["operation_permitted"] is not False
        or cpu["blocked_optional_import_probes"][0]["dependency_file_sha256"]
        != digest(HERE / "isolation_dependency/urllib3_util_connection.py")
        or preservation["status"] != "passed"
        or tests["unresolved_tests"] != 0
        or tests["new_tests"] != 64
        or tests["historical_source_tests"] != 26
        or context["status"] != "passed"
        or context["unique_requests"] != 2831
    ):
        raise ValueError("offline acceptance evidence does not reconcile")
    correct = read(execution_root / "diagnostics/latest_explicit/scores.json")
    if correct["counts"]["all_correct"] != plan["planned_slots_per_policy"]:
        raise ValueError("legal public resolver does not cover all slots")
    for policy in plan["diagnostic_policies"]:
        score = read(execution_root / "diagnostics" / policy / "scores.json")
        if score["counts"]["planned"] != 1542:
            raise ValueError("diagnostic denominator changed")
    record = {
        "schema_version": "forecast_task_offline_acceptance_v1",
        "status": "offline_verified_native_live_engineering_pending",
        "execution_id": plan["execution_id"],
        "package_id": package["package_id"],
        "dataset_id": data["dataset_id"],
        "source_package_id": source["package_id"],
        "counts": data["counts"],
        "new_tests": tests["new_tests"],
        "historical_source_tests": tests["historical_source_tests"],
        "diagnostic_policies": len(plan["diagnostic_policies"]),
        "diagnostic_answer_opportunities": 1542 * len(plan["diagnostic_policies"]),
        "unique_tokenizer_checks": context["unique_requests"],
        "maximum_prompt_plus_reserved_output": context["maximum_reserved_total"],
        "cpu_relocation": "passed_after_optional_import_probe_accounting_v2",
        "historical_acceptances_verified": preservation["historical_acceptances"],
        "future_model_candidate_answers": 1542,
        "future_gpu_ceiling": 4,
        "model_generations": 0,
        "gpu_jobs": 0,
        "paid_api_calls": 0,
        "upstream_acquisitions": 0,
        "heldout_inference": 0,
        "training_runs": 0,
        "human_gold_annotations": 0,
        "llm_judge_calls": 0,
        "evidence_sha256": evidence(),
    }
    record["acceptance_id"] = fingerprint(record)
    write(HERE / "OFFLINE_ACCEPTANCE.json", record)
    return record


def verify_acceptance():
    record = read(HERE / "OFFLINE_ACCEPTANCE.json")
    if record["acceptance_id"] != fingerprint(
        {k: v for k, v in record.items() if k != "acceptance_id"}
    ):
        raise ValueError("acceptance identity differs")
    for name, expected in record["evidence_sha256"].items():
        path = (PROJECT / name).resolve()
        if not path.is_relative_to(PROJECT) or digest(path) != expected:
            raise ValueError("accepted evidence differs: " + name)
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    record = verify_acceptance() if parser.parse_args().verify else accept()
    print(
        {
            "status": record["status"],
            "acceptance_id": record["acceptance_id"],
            "evidence_files": len(record["evidence_sha256"]),
            "model_generations": 0,
        }
    )
