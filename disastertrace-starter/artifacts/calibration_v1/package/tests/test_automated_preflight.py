"""Offline readiness must be supported by successful controls and immutable evidence."""

import copy
import json
from pathlib import Path

import pytest

from disastertrace.automated import preflight, workflow
from disastertrace.automated.common import file_hash, fingerprint, write_json
from disastertrace.automated.methods import METHODS

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT.parent / "references"
SPEC = ROOT / "configs/pre_api_pilot_v1.json"


@pytest.fixture(scope="module")
def build_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("preflight-build") / "build"
    workflow.build(REFERENCES, path, nhc_snapshot=REFERENCES / "nhc_cohort_v1")
    return path


def test_matrix_has_exact_event_grouped_smoke_dev_and_heldout_counts(build_path):
    matrix = preflight.experiment_matrix(build_path, json.loads(SPEC.read_text()))
    assert matrix["requests_by_phase"] == {"smoke": 60, "development": 180, "heldout": 420}
    assert len(matrix["cells"]) == 18
    assert {cell["method"] for cell in matrix["cells"]} == set(METHODS)
    for cell in matrix["cells"]:
        if cell["phase"] == "smoke":
            assert cell["split"] == "development"
            assert cell["group_ids"] == ["AL092021"]
            assert len(cell["episode_ids"]) == 2
    assert matrix["pending_live_configuration"]


@pytest.mark.parametrize("groups", [[], ["AL112017"], ["AL092021", "AL092021"], ["missing"]])
def test_smoke_cannot_select_empty_duplicate_or_heldout_group(build_path, groups):
    specification = json.loads(SPEC.read_text())
    specification["smoke_event_ids"] = groups
    with pytest.raises(ValueError):
        preflight.experiment_matrix(build_path, specification)


@pytest.mark.parametrize("method", METHODS)
def test_group_selected_run_freezes_method_and_full_branch_denominators(
    build_path, tmp_path, method
):
    output = tmp_path / "run"
    workflow.run(
        build_path,
        output,
        track="dynamic",
        backend="rule",
        split="development",
        group_ids=["AL092021"],
        method=method,
        max_queries=10,
    )
    result = workflow.score(build_path, output, tmp_path / "score.json")
    assert result["metrics"]["grounded_state"]["denominator"] == 50
    assert result["metrics"]["grounded_state"]["value"] == 1
    assert result["event_summary"]["n_events"] == 1
    config = json.loads((output / "run.json").read_text())
    config["method"] = "snapshot" if method != "snapshot" else "answer_history"
    write_json(output / "run.json", config)
    with pytest.raises(ValueError, match="method"):
        workflow.score(build_path, output, tmp_path / "reinterpreted.json")


@pytest.mark.parametrize("attach_record", [False, True])
def test_preflight_runs_offline_and_keeps_missing_suite_evidence_explicit(
    build_path, tmp_path, attach_record
):
    output = tmp_path / "preflight"
    record_path = None
    if attach_record:
        log = tmp_path / "original-unit-fixture.log"
        log.write_text("unit fixture for verification attachment; not actual suite evidence\n")
        record_path = tmp_path / "record.json"
        write_json(
            record_path,
            {
                "schema_version": "offline_verification_v1",
                "implementation_id": workflow.implementation_snapshot()["implementation_id"],
                "pytest_passed": 1,
                "pytest_skipped": 0,
                "checks": [
                    {
                        "command": "unit-test fixture",
                        "log": log.name,
                        "exit_code": 0,
                        "log_sha256": file_hash(log),
                    }
                ],
            },
        )
    result = preflight.prepare_experiment(build_path, SPEC, output, verification_path=record_path)
    assert result["live_ready"] is False
    assert result["offline_ready"] is attach_record
    assert result["offline_suite_evidence_attached"] is attach_record
    if attach_record:
        saved = json.loads((output / "verification/record.json").read_text())
        check = saved["checks"][0]
        assert check["original_log"] == "original-unit-fixture.log"
        assert file_hash(output / "verification" / check["log"]) == check["log_sha256"]
    assert result["diagnostic_runs"] == 18
    assert result["live_model_calls"] == 0
    readiness = json.loads((output / "readiness.json").read_text())
    for rehearsal in readiness["collection_rehearsals"]:
        assert rehearsal["fixture_transport_calls"] == 10
        assert rehearsal["completed_checkpoints"] == 10
        assert rehearsal["partial_status"] == "budget_exhausted"
        assert rehearsal["resumed_status"] == "completed"
    assert preflight.verify_preflight(build_path, output)["valid"] is True
    with pytest.raises(ValueError, match="exists"):
        preflight.prepare_experiment(build_path, SPEC, output)
    (output / "REPORT.md").write_text("altered")
    with pytest.raises(ValueError, match="artifact changed"):
        preflight.verify_preflight(build_path, output)


@pytest.mark.parametrize("control", ["rule", "reference-fixture", "empty-control"])
def test_failed_controls_prevent_readiness(build_path, tmp_path, monkeypatch, control):
    original = preflight.score

    def faulty_score(*args, **kwargs):
        result = copy.deepcopy(original(*args, **kwargs))
        if result["run"]["backend"] == control:
            if control == "rule":
                result["metrics"]["grounded_state"]["value"] = 0
            else:
                result["aggregate"]["correct_tasks"] = 1
        return result

    monkeypatch.setattr(preflight, "score", faulty_score)
    with pytest.raises(ValueError, match="control"):
        preflight.prepare_experiment(build_path, SPEC, tmp_path / "rejected")


def test_verification_for_different_implementation_cannot_attest_readiness(build_path, tmp_path):
    record = tmp_path / "verification.json"
    write_json(
        record,
        {
            "schema_version": "offline_verification_v1",
            "implementation_id": fingerprint({}),
            "checks": [{}],
            "pytest_passed": 1,
            "pytest_skipped": 0,
        },
    )
    with pytest.raises(ValueError, match="verification"):
        preflight.prepare_experiment(
            build_path, SPEC, tmp_path / "rejected", verification_path=record
        )


def test_preflight_verifier_rejects_empty_rehashed_manifest(build_path, tmp_path):
    lock = {
        "schema_version": "pre_api_artifact_manifest_v1",
        "files": {},
        "build_id": workflow.verify_build(build_path)["build_id"],
        "implementation_id": workflow.implementation_snapshot()["implementation_id"],
    }
    lock["package_id"] = fingerprint(lock)
    write_json(tmp_path / "manifest.json", lock)
    with pytest.raises(ValueError, match="required"):
        preflight.verify_preflight(build_path, tmp_path)


@pytest.mark.parametrize("mutation", ["schema", "empty_checks", "zero_passes", "skipped"])
def test_ready_package_revalidates_verification_record(build_path, tmp_path, mutation):
    build_id = workflow.verify_build(build_path)["build_id"]
    implementation_id = workflow.implementation_snapshot()["implementation_id"]
    write_json(
        tmp_path / "readiness.json",
        {"build_id": build_id, "implementation_id": implementation_id, "offline_ready": True},
    )
    write_json(tmp_path / "dataset_audit.json", preflight.audit_dataset(build_path))
    write_json(
        tmp_path / "experiment_matrix.json",
        preflight.experiment_matrix(build_path, json.loads(SPEC.read_text())),
    )
    (tmp_path / "REPORT.md").write_text("Unit fixture; not actual experiment evidence")
    log = tmp_path / "verification/check.log"
    log.parent.mkdir()
    log.write_text("unit fixture")
    record = {
        "schema_version": "offline_verification_v1",
        "implementation_id": implementation_id,
        "pytest_passed": 1,
        "pytest_skipped": 0,
        "checks": [{"exit_code": 0, "log": log.name, "log_sha256": file_hash(log)}],
    }
    if mutation == "schema":
        record["schema_version"] = "unsupported"
    elif mutation == "empty_checks":
        record["checks"] = []
    elif mutation == "zero_passes":
        record["pytest_passed"] = 0
    else:
        record["pytest_skipped"] = 1
    write_json(tmp_path / "verification/record.json", record)
    lock = {
        "schema_version": "pre_api_artifact_manifest_v1",
        "build_id": build_id,
        "implementation_id": implementation_id,
        "files": {
            str(path.relative_to(tmp_path)): file_hash(path)
            for path in tmp_path.rglob("*")
            if path.is_file()
        },
    }
    lock["package_id"] = fingerprint(lock)
    write_json(tmp_path / "manifest.json", lock)
    with pytest.raises(ValueError, match="verification"):
        preflight.verify_preflight(build_path, tmp_path)
