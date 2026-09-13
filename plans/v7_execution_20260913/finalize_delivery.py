"""Bind the completed bounded execution without modifying historical artifacts."""

import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def save(name, value):
    with (HERE / name).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    start = read("EXECUTION_START.json")
    preserved = start["preserved_files"]
    for name, expected in preserved.items():
        assert sha(ROOT / name) == expected, name
    index = Path(
        "/mnt/afs/260010168/extreme_weather_benchmark/github_review/"
        "disastertrace-benchmark/.git/worktrees/disastertrace-next/index"
    )
    assert sha(index) == start["real_index_sha256"]

    suites = ET.parse(HERE / "tests/CORE_AND_FIXED_04.xml").getroot().findall("testsuite")
    test_counts = {
        k: sum(int(s.attrib[k]) for s in suites)
        for k in ("tests", "failures", "errors", "skipped")
    }
    assert test_counts == {"tests": 250, "failures": 0, "errors": 0, "skipped": 0}
    assert (HERE / "tests/FINAL_TARGETED_RUFF.log").read_text().strip() == "All checks passed!"

    gpu = read("gpu/combined_analysis_01/REPORT.json")
    assert gpu["totals"] == {
        "actual_calls": 720, "input_tokens": 1916920, "output_tokens": 13295
    }
    assert gpu["total_tokens"] == 1930215 and gpu["max_requested_gpu_overlap"] == 4
    expected_correct = {
        "original_filled_example": 93,
        "alternate_filled_example": 42,
        "no_filled_example": 57,
        "explicit_truth_E_only": 127,
        "explicit_truth_joint_EF": 114,
    }
    for name, expected in expected_correct.items():
        assert gpu["variants"][name]["calls"] == 144
        assert gpu["variants"][name]["E_correct"] == expected
    account = read("FINAL_ACCOUNT_CHECK.json")
    assert account["active_requested_gpus"] == 0 and not account["active_job_ids"]

    archive = read("replay/ZIP_MANIFEST.json")
    zip_path = HERE / "replay" / archive["archive"]
    assert sha(zip_path) == archive["sha256"]
    assert zip_path.stat().st_size == archive["bytes"] == 11352884
    assert archive["crc_and_all_member_hashes_verified"]
    assert archive["relocated_zip_replay_verified"]
    assert archive["replayed_original_calls"] == 720 and archive["new_model_calls"] == 0
    for name, count in (("local_calibration_precheck", 636), ("local_calibration_2025", 660)):
        result = read("audit/" + name + "/FULL_VALIDATION.json")
        assert result["source_bodies_and_receipts_verified"] == count
        assert result["static_arms_recomputed"] == 6 and result["all_static_arms_common_mask"]
        assert result["january_targets_disjoint_from_training_dataset"]
    numerical = read("evidence_bundle/numerical_01/REPORT.json")
    assert numerical["scored_positive_lead_pairs"] == 60
    assert numerical["typed_state_roundtrips"] == 120
    assert not numerical["active_monitoring_qualified"]
    assert read("sources_lamp/VALIDATION.json")["all_checks_passed"]
    repair = read("tests/final_integration_review/REPAIRED_BOUNDARY_RESULTS.json")
    current = ROOT / "disastertrace-starter/src/disastertrace/monitoring_fixed_v1"
    assert repair["source_sha256"] == sha(current / "contracts.py")

    now = datetime.now(timezone.utc).isoformat()
    work = {
        "schema": "disastertrace.bounded_work_packages.v1",
        "at": now,
        "W0": {"status": "complete", "evidence": "audit/VALIDATION.json"},
        "W1A": {
            "status": "bounded_sources_and_two_year_controls_complete",
            "remaining": ["rare_event_check_support", "native_probability_outcomes", "historical_availability"],
        },
        "W1B": {"status": "historical_archive_precheck_complete_not_scored"},
        "W1C": {"status": "samples_decoded_temperature_interface_complete_rain_not_scored"},
        "W2": {
            "status": "fixed_lane_and_heads_cpu_verified_partial_engine_integration",
            "remaining": ["generic_C2_provider_bridge", "cutoff_effective_forecast_manifest", "adaptive_typed_engine"],
        },
        "W3": {
            "status": "720_actual_fixed_input_diagnostic_calls_complete",
            "remaining": ["independent_F_only_calls", "new_process_confirmation", "timed_action_response"],
        },
        "W4": {"status": "not_run_this_execution"},
        "W5": {"status": "cpu_replay_delivered_independent_confirmation_not_run"},
        "formal_v7_hazard_admissions": 0,
        "hazards_in_roadmap": 16,
        "positive_llm_gain_is_not_a_task_admission_requirement": True,
    }
    status = {
        "schema": "disastertrace.bounded_execution_status.v1",
        "status": "bounded_execution_complete",
        "started_at": start["started_at"],
        "completed_at": now,
        "authorized_window_target_end": start["target_end"],
        "new_model_calls": 720,
        "audited_old_calls": 31104,
        "new_gpu_jobs": 12,
        "successful_gpu_jobs": 12,
        "max_concurrent_h100": 4,
        "last_account_check_at": account["at"],
        "active_requested_gpus_at_check": 0,
        "new_tokens": gpu["totals"]["input_tokens"] + gpu["totals"]["output_tokens"],
        "new_paid_llm_api_calls": 0,
        "training_runs": 0,
        "new_github_publications": 0,
        "model_F_only_calls": 0,
        "head_interface_cpu_ready": True,
        "core_and_fixed_tests": test_counts,
        "formal_monitoring_admissions": 0,
        "independent_weather_confirmation": False,
        "LLM_F_gain_demonstrated": False,
        "replay_archive": "replay/" + archive["archive"],
        "report": "FINAL_REPORT_CN.md",
        "next_plan": "NEXT_PLAN_CN.md",
        "all_old_launches_preserved": True,
    }
    save("WORK_PACKAGE_STATUS.json", work)
    save("EXECUTION_STATUS.json", status)

    link_count = 0
    for name in ("README_CN.md", "FINAL_REPORT_CN.md", "NEXT_PLAN_CN.md"):
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", (HERE / name).read_text()):
            if "://" not in target and not target.startswith("#"):
                path = HERE / target.split("#", 1)[0]
                assert path.exists(), (name, target)
                link_count += 1
    snapshot = HERE / "source_current_01"
    snapshot.mkdir(exist_ok=False)
    sources = []
    for package in ("monitoring_fixed_v1", "monitoring_v1"):
        origin = current.parent / package
        for source in sorted(origin.rglob("*.py")):
            relative = source.relative_to(current.parent)
            destination = snapshot / "disastertrace" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            assert sha(source) == sha(destination)
            sources.append(str(source.relative_to(ROOT)))
    snapshot_files = {
        str(p.relative_to(snapshot)): sha(p) for p in sorted(snapshot.rglob("*.py"))
    }
    save("source_current_01/MANIFEST.json", {
        "at": now, "files": snapshot_files,
        "purpose": "current CPU-verified source, distinct from historical GPU batch copies",
        "new_model_calls": 0,
    })

    validation = {
        "schema": "disastertrace.final_delivery_validation.v1",
        "verified_at": now,
        "old_preserved_files_checked": len(preserved),
        "old_preserved_files_unchanged": True,
        "real_git_index_unchanged": True,
        "real_git_index_sha256": start["real_index_sha256"],
        "tests": test_counts,
        "targeted_ruff_passed": True,
        "whole_repository_lint_claimed": False,
        "gpu_summary_and_semantic_counts_reconciled": True,
        "replay_zip_bytes_and_sha256_recomputed": True,
        "component_validations_bound_not_all_upstream_downloads_rerun": True,
        "local_markdown_links_checked": link_count,
        "current_python_source_files_snapshotted": len(sources),
        "additional_recorded_checks": {
            "audit_tests": 9, "lamp_tests": 7, "replay_negative_checks": 4,
            "baseline_boundary_protocol_combinations": 6,
            "actual_frozen_bundles_compatible_with_repairs": 144,
        },
        "finalizer_sha256": sha(Path(__file__)),
        "no_new_inference_during_finalization": True,
    }
    save("FINAL_VALIDATION.json", validation)

    selected = [HERE / n for n in (
        "README_CN.md", "FINAL_REPORT_CN.md", "NEXT_PLAN_CN.md", "EXECUTION_START.json",
        "EXECUTION_STATUS.json", "WORK_PACKAGE_STATUS.json", "FINAL_VALIDATION.json",
        "FINAL_ACCOUNT_CHECK.json", "finalize_delivery.py", "source_current_01/MANIFEST.json",
        "tests/CORE_AND_FIXED_04.xml", "tests/FINAL_TARGETED_RUFF.log", "tests/heads_01/REPORT.json",
        "tests/heads_01/INPUT_MANIFEST.json", "tests/heads_01/PREPARED_MESSAGE_BINDINGS.json",
        "tests/final_integration_review/REVIEW_CN.md",
        "tests/final_integration_review/REPAIRED_BOUNDARY_RESULTS.json",
        "audit/VALIDATION.json", "audit/REPORT_CN.md", "audit/two_year_summary/SUMMARY.json",
        "audit/local_calibration_precheck/FULL_VALIDATION.json",
        "audit/local_calibration_2025/FULL_VALIDATION.json", "sources_lamp/VALIDATION.json",
        "sources_lamp/MANIFEST.json", "sources_numerical/DECODE_VALIDATION.json",
        "sources_numerical/QUALIFICATION.json", "sources_numerical/FILES.sha256.json",
        "hydrology/ARCHIVE_VALIDATION.json", "hydrology/SOURCE_SEMANTICS.json",
        "hydrology/FILES.sha256.json", "evidence_bundle/numerical_01/REPORT.json",
        "evidence_bundle/matrix_01/MANIFEST.json", "gpu/combined_analysis_01/REPORT.json",
        "replay/ZIP_MANIFEST.json", "replay/RELOCATION_VALIDATION.json",
        "replay/ORIGINAL_VERIFIER_CROSSCHECK.json", "replay/negative_checks_01/REPORT.json",
    )]
    selected += [ROOT / name for name in sources]
    selected += [ROOT / "disastertrace-starter" / name for name in (
        "IMPLEMENTATION_STATUS.md", "DECISIONS.md", "BLOCKERS.md",
    )]
    selected.append(zip_path)
    save("DELIVERY_MANIFEST.json", {
        "created_at": now,
        "scope": "selected final evidence and source; component manifests bind deeper data",
        "files": {str(p.relative_to(ROOT)): sha(p) for p in selected},
    })
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()
