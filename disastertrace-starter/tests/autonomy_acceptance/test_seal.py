import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

from disastertrace.forecast_task.common import digest, fingerprint, write

SCRIPT = Path(__file__).resolve().parents[2] / "artifacts/autonomy_10h_v1/seal_cohort_evidence.py"
SPEC = importlib.util.spec_from_file_location("cohort_acceptance", SCRIPT)
seal = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(seal)


def signed(value, field):
    result = deepcopy(value)
    result.pop(field, None)
    result[field] = fingerprint(result)
    return result


@pytest.fixture
def stopped():
    report = signed({
        "execution_id": "execution", "counts": {"raw_returned": 2},
        "scores": {"counts": {"planned": 6, "received": 2, "all_correct": 1}},
        "platform_jobs": [
            {"worker_id": 0, "state": "FAILED", "released": True},
            {"worker_id": 1, "state": "SUCCEEDED", "released": True},
        ],
    }, "report_id")
    status = signed({
        "status": "passed", "execution_id": report["execution_id"],
        "report_id": report["report_id"], "counts": report["counts"],
        "score_counts": report["scores"]["counts"], "platform_jobs": report["platform_jobs"],
    }, "status_id")
    analysis = signed({
        "execution_id": report["execution_id"], "report_id": report["report_id"],
        "counts": report["counts"], "score_counts": report["scores"]["counts"],
        "single_repeat_only": True, "planned_denominator_is_primary": True,
        "population_inference": False, "unit_normalization": False, "new_model_calls": 0,
    }, "analysis_id")
    return status, report, analysis


def test_auditable_stopped_collection_is_not_labeled_complete(stopped):
    result = seal.validate_result(*stopped, planned=6)
    assert result["model_matrix_complete"] is False
    assert result["all_gpu_jobs_succeeded"] is False
    assert result["unreturned_in_primary_denominator"] == 4
    assert result["platform_jobs"][0]["state"] == "FAILED"


def test_received_denominator_cannot_replace_planned_slots(stopped):
    with pytest.raises(ValueError, match="denominator"):
        seal.validate_result(*stopped, planned=2)


@pytest.mark.parametrize("field,value", [("released", False), ("state", "RUNNING"), ("worker_id", 0)])
def test_terminal_resource_claim_must_cover_two_released_workers(stopped, field, value):
    status, report, analysis = stopped
    report["platform_jobs"][1][field] = value
    report = signed(report, "report_id")
    status.update(platform_jobs=report["platform_jobs"], report_id=report["report_id"])
    analysis["report_id"] = report["report_id"]
    with pytest.raises(ValueError, match="terminal and released"):
        seal.validate_result(signed(status, "status_id"), report, signed(analysis, "analysis_id"), 6)


@pytest.mark.parametrize("field,value", [("unit_normalization", True), ("single_repeat_only", False),
                                         ("planned_denominator_is_primary", False)])
def test_posthoc_interpretation_cannot_silently_change(stopped, field, value):
    status, report, analysis = stopped
    analysis[field] = value
    with pytest.raises(ValueError, match="interpretation"):
        seal.validate_result(status, report, signed(analysis, "analysis_id"), 6)


def test_edited_score_summary_rejected_even_with_new_analysis_hash(stopped):
    status, report, analysis = stopped
    analysis["score_counts"] = {**analysis["score_counts"], "all_correct": 2}
    with pytest.raises(ValueError, match="score counts"):
        seal.validate_result(status, report, signed(analysis, "analysis_id"), 6)


def test_success_exit_code_without_matching_log_rejected(tmp_path):
    log = tmp_path / "check.log"
    log.write_text("passed\n")
    write(tmp_path / "check_result.json", {"exit_code": 0, "log_sha256": digest(log)})
    write(tmp_path / "check_intent.json", {"argv": ["check"]})
    seal.successful_command(tmp_path, "check")
    log.write_text("different content\n")
    with pytest.raises(ValueError, match="command or log"):
        seal.successful_command(tmp_path, "check")


def test_changed_accepted_bytes_rejected(tmp_path):
    project = tmp_path / "repo/project"
    project.mkdir(parents=True)
    evidence = project / "raw.json"
    evidence.write_text("original")
    path = project / "accepted.json"
    write(path, signed({"evidence_sha256": {"raw.json": digest(evidence)}}, "acceptance_id"))
    assert seal.verify_record(path, project)["verified_files"] == 1
    evidence.write_text("edited")
    with pytest.raises(ValueError, match="accepted evidence"):
        seal.verify_record(path, project)


def test_inventory_cannot_reach_outside_repository(tmp_path):
    project = tmp_path / "repo/project"
    project.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.write_text("outside")
    path = project / "accepted.json"
    write(path, signed({"evidence_sha256": {"../../outside": digest(outside)}}, "acceptance_id"))
    with pytest.raises(ValueError, match="accepted evidence"):
        seal.verify_record(path, project)
