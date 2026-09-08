"""Seal or verify the complete first P6 offline milestone, with live gaps explicit."""

import argparse
from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.local_eval.storage import digest, inventory, read, verify_seal, write
from disastertrace.repeat_eval.package import verify

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]


def evidence_files():
    files = {}
    for path in ROOT.rglob("*"):
        if (
            not path.is_file()
            or "__pycache__" in path.parts
            or path.name == "OFFLINE_ACCEPTANCE.json"
        ):
            continue
        relative = path.relative_to(ROOT)
        if (
            relative.parts[0] == "validation"
            and len(relative.parts) > 1
            and not (ROOT / "validation" / relative.parts[1] / "result.json").exists()
        ):
            continue
        files[str(path.relative_to(PROJECT))] = digest(path)
    for root in (
        PROJECT / "src/disastertrace/post_p5",
        PROJECT / "src/disastertrace/repeat_eval",
        PROJECT / "tests/p6",
        PROJECT / "docs/p6",
        PROJECT / "work/p6-offline-v1",
        PROJECT.parent / "plans/plan_v3",
        PROJECT.parent / "plans/p6",
    ):
        for name, checksum in inventory(root).items():
            files[
                str((root / name).relative_to(PROJECT))
                if root.is_relative_to(PROJECT)
                else "../" + str((root / name).relative_to(PROJECT.parent))
            ] = checksum
    for name in (
        "README_P6_OFFLINE_V1.md",
        "AGENTS.md",
        "IMPLEMENTATION_STATUS.md",
        "DECISIONS.md",
        "BLOCKERS.md",
        "../README.md",
        "../plans/INTEGRATED_P6_PLAN_V1.md",
        "work/p6-portable-review-v1/verify_portable.py",
    ):
        files[name] = digest(PROJECT / name)
    return files


def accept():
    if (ROOT / "OFFLINE_ACCEPTANCE.json").exists():
        raise FileExistsError("acceptance already frozen")
    plan, _, _ = verify(ROOT / "execution")
    baseline = read(ROOT / "baseline/repo_baseline.json")
    matrix = read(ROOT / "FULL_MATRIX_VERIFICATION.json")
    portable = read(ROOT / "CPU_RELOCATION.json")
    preserved = read(ROOT / "PRESERVATION.json")
    tests = read(ROOT / "VALIDATION_RESULTS.json")
    if any(item["status"] != "passed" for item in (baseline, matrix, portable, preserved)):
        raise ValueError("required milestone evidence did not pass")
    if (
        tests["unresolved_tests"]
        or tests["distinct_legacy_tests"] != 1189
        or tests["distinct_new_tests"] != 69
    ):
        raise ValueError("test coverage incomplete")
    if matrix["execution_id"] != plan["execution_id"] or plan["generation_authorized"] is not False:
        raise ValueError("offline execution scope differs")
    for name in (
        "posthoc_final",
        "actual_examples",
        "source_binding_probe_v1",
        "context",
        "reports/correct",
        "reports/invalid-control",
    ):
        verify_seal(ROOT / name)
    for mode in ("correct", "invalid-control"):
        if (
            portable["reports"][mode]["audit_id"]
            != read(ROOT / "reports" / mode / "audit.json")["audit_id"]
        ):
            raise ValueError("portable report identity differs")
    required = (
        "04_unit_final",
        "05_lint",
        "07_posthoc_final",
        "08_prepare",
        "09_context",
        "10_correct_collection",
        "11_invalid_collection",
        "12_legacy_tokenizer_grammar",
        "13_correct_report",
        "14_invalid_report",
        "15_portable_copy",
        "16_full_matrix_assertions",
        "17_portable_reconstruction",
        "18_supplemental_properties",
        "19_source_binding_probes",
        "20_actual_examples",
        "21_test_inventory",
        "22_final_lint_fixed",
        "23_preservation",
    )
    for name in required:
        if read(ROOT / "validation" / name / "result.json")["exit_code"] != 0:
            raise ValueError("required step did not complete: " + name)
    result = {
        "schema_version": "p6_offline_acceptance_v1",
        "status": "offline_verified_live_pending",
        "offline_verified": True,
        "live_ready": False,
        "execution_id": plan["execution_id"],
        "initial_git_head": baseline["head"],
        "plan_input_index": "plan_inputs_v2.json",
        "program_responses_in_full_rehearsals": 4320,
        "proposed_model_responses": 2160,
        "planned_trajectories": 432,
        "context_program_opportunities": 10800,
        "new_tests": 69,
        "legacy_tests_reconciled": 1189,
        "legacy_first_command_exit": 1,
        "legacy_environment_subset_exit": 0,
        "model_generations": 0,
        "gpu_jobs": 0,
        "paid_api_calls": 0,
        "new_source_acquisitions": 0,
        "per_item_human_labels": 0,
        "llm_judge_calls": 0,
        "heldout_inference": 0,
        "training_runs": 0,
        "p6_published": False,
        "remaining_live_prerequisites": [
            "model_backend_adapter",
            "one_use_acp_phase_launcher",
            "generation_disabled_actual_h100_preflight",
            "fresh_bounded_live_freeze",
        ],
        "protected_tracked_files": preserved["protected_tracked_files"],
        "evidence_sha256": evidence_files(),
    }
    result["acceptance_id"] = fingerprint(result)
    write(ROOT / "OFFLINE_ACCEPTANCE.json", result)
    return result


def verify_acceptance():
    result = read(ROOT / "OFFLINE_ACCEPTANCE.json")
    if result["acceptance_id"] != fingerprint(
        {k: v for k, v in result.items() if k != "acceptance_id"}
    ):
        raise ValueError("acceptance identity differs")
    for name, expected in result["evidence_sha256"].items():
        path = (PROJECT / name).resolve()
        if not path.is_relative_to(PROJECT.parent) or digest(path) != expected:
            raise ValueError("accepted evidence differs: " + name)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    result = verify_acceptance() if parser.parse_args().verify else accept()
    print(
        {
            "status": result["status"],
            "acceptance_id": result["acceptance_id"],
            "evidence_files": len(result["evidence_sha256"]),
            "model_generations": 0,
        },
        flush=True,
    )
