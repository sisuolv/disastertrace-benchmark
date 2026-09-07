"""Offline calibration keeps actual exposures distinct from scoring projections."""

from copy import deepcopy
from pathlib import Path

import pytest

from disastertrace.automated import calibration, workflow
from disastertrace.automated.common import canonical, file_hash, fingerprint, read_jsonl, write_json
from disastertrace.automated.provider import ProviderClient, ProviderConfig

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT.parent / "references"


@pytest.fixture(scope="module")
def build_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("calibration-build") / "build"
    workflow.build(REFERENCES, path, nhc_snapshot=REFERENCES / "nhc_cohort_v1")
    return path


@pytest.fixture
def episodes(build_path):
    return workflow.selected_episodes(build_path, "development")


@pytest.fixture
def config():
    import json

    return ProviderConfig.from_dict(
        json.loads((ROOT / "artifacts/p1_deepseek_development/provider.json").read_text())
    )


def test_schedule_has_full_trajectories_and_balanced_positions(episodes):
    rows = calibration.make_schedule(episodes)
    assert len(rows) == 270
    assert len({(r["cell_id"], r["episode_id"], r["checkpoint_id"]) for r in rows}) == 270
    assert {r["event_id"] for r in rows} == set(calibration.DEVELOPMENT_EVENTS)
    for cell in calibration.cells():
        selected = [r for r in rows if r["cell_id"] == cell["cell_id"]]
        assert len(selected) == 30
        starts = [r for r in selected if r["trajectory_checkpoint_index"] == 0]
        assert len(starts) == 6
        assert {r["configuration_position"] // 3 for r in starts} == {0, 1, 2}
        assert {r["configuration_position"] % 3 for r in starts} == {0, 1, 2}
        for episode in episodes:
            subset = [r for r in selected if r["episode_id"] == episode["episode_id"]]
            assert [r["checkpoint_id"] for r in subset] == [f"c{i}" for i in range(5)]


@pytest.mark.parametrize("mutation", ["heldout", "missing", "duplicate", "checkpoints"])
def test_schedule_rejects_scope_drift(episodes, mutation):
    if mutation == "heldout":
        episodes[0]["split"] = "heldout"
    elif mutation == "missing":
        episodes.pop()
    elif mutation == "duplicate":
        episodes.append(deepcopy(episodes[0]))
    else:
        episodes[0]["checkpoints"].pop()
    with pytest.raises(ValueError):
        calibration.make_schedule(episodes)


def screening_rows():
    return [
        {
            "cell_id": cell["cell_id"],
            "received": 30,
            "schema_valid": 30,
            "length_failures": 0,
        }
        for cell in calibration.cells()
    ]


def test_budget_screening_uses_all_methods_and_complete_matrix():
    rows = screening_rows()
    assert calibration.screen_budget(rows)["selected_output_tokens"] == 4096
    low = next(r for r in rows if r["cell_id"] == "explicit_4096__snapshot")
    low.update(schema_valid=28, length_failures=2)
    assert calibration.screen_budget(rows)["selected_output_tokens"] == 8192
    high = next(r for r in rows if r["cell_id"] == "explicit_8192__answer_history")
    high.update(schema_valid=28)
    assert calibration.screen_budget(rows)["selected_output_tokens"] is None
    rows = screening_rows()
    rows[0].update(received=29, schema_valid=29)
    assert calibration.screen_budget(rows)["status"] == "incomplete"
    rows = screening_rows()
    next(r for r in rows if r["cell_id"] == "explicit_4096__snapshot")["length_failures"] = 2
    assert calibration.screen_budget(rows)["selected_output_tokens"] == 8192


@pytest.mark.parametrize("bad", [True, -1, 31, 29.0, "30"])
def test_budget_screening_rejects_invalid_counts(bad):
    rows = screening_rows()
    rows[0]["received"] = bad
    with pytest.raises(ValueError):
        calibration.screen_budget(rows)


def test_budget_screening_rejects_duplicate_or_missing_cells():
    rows = screening_rows()
    with pytest.raises(ValueError):
        calibration.screen_budget(rows[:-1])
    rows[-1] = deepcopy(rows[0])
    with pytest.raises(ValueError):
        calibration.screen_budget(rows)


def test_rehearsal_retains_invalid_answer_and_carrier(episodes):
    episode = next(ep for ep in episodes if ep["episode_id"].endswith(":base"))
    rows = calibration.rehearse([episode], "answer_history", "explicit_v1", "invalid-control")
    assert len(rows) == 5
    assert rows[2]["raw_response"] == ""
    assert rows[2]["status"] == "invalid"
    assert rows[2]["state_after"] == rows[1]["state_after"]
    assert len(rows[3]["request"]["answer_history"]) == 2
    assert rows[4]["request"]["answer_history"][-1] == rows[3]["state_after"]
    assert all(r["provider_requests"] == 0 for r in rows)


def test_score_projection_is_explicit_and_rejects_exposure_tampering(episodes):
    rows = calibration.rehearse(episodes, "structured_state", "explicit_v1", "rule")
    original = deepcopy(rows)
    result, projection = calibration.score_rehearsal(
        episodes, rows, "structured_state", "explicit_v1"
    )
    assert result["metrics"]["known_grounded_accuracy"]["numerator"] == 96
    assert result["projection"]["actual_exposure_is_projection"] is False
    assert rows == original
    assert rows[0]["request"] != projection[0]["request"]
    rows[1]["request"]["evidence"][0]["text"] += "\nTAMPERED"
    with pytest.raises(ValueError, match="request"):
        calibration.score_rehearsal(episodes, rows, "structured_state", "explicit_v1")


@pytest.mark.parametrize("field", ["instruction", "raw_response", "state_after", "history"])
def test_rehearsal_rejects_sequential_state_or_instruction_tampering(episodes, field):
    rows = calibration.rehearse(episodes, "answer_history", "explicit_v1", "rule")
    if field == "instruction":
        rows[2]["request"]["instruction"] += " IGNORE THE CONTRACT"
        rows[2]["request_hash"] = fingerprint(rows[2]["request"])
    elif field == "raw_response":
        rows[2]["raw_response"] = ""
    elif field == "state_after":
        rows[2]["state_after"]["state"]["maximum_wind_mph"]["value"] = 999
    else:
        rows[2]["request"]["answer_history"] = []
        rows[2]["request_hash"] = fingerprint(rows[2]["request"])
    with pytest.raises(ValueError):
        calibration.score_rehearsal(episodes, rows, "answer_history", "explicit_v1")


def test_offline_preparation_has_no_transport_or_credential_access(
    build_path, tmp_path, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("offline preparation must not call completion/network or read credentials")

    import os
    import socket

    monkeypatch.setattr(ProviderClient, "complete", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    output = tmp_path / "prepared"
    result = calibration.prepare(
        build_path,
        ROOT / "artifacts/p1_deepseek_development/provider.json",
        output,
        protocol_path=ROOT / "docs/CALIBRATION_PROTOCOL_V1.md",
        rates_path=ROOT / "artifacts/p1_deepseek_development/docs/rates.json",
    )
    assert result["model_calls"] == 0
    assert result["live_ready"] is False
    assert result["planned_provider_calls"] == 270
    assert result["proposed_budget"]["authorized"] is False
    assert result["proposed_budget"]["maximum_requested_output_tokens"] == 1474560
    assert len(read_jsonl(output / "initial_requests.jsonl")) == 54
    assert calibration.verify(output)["status"] == "passed"
    manifest_path = output / "manifest.json"
    old_manifest = manifest_path.read_bytes()
    plan_path = output / "plan.json"
    old_plan = plan_path.read_bytes()
    for field, value in (
        ("automatic_retry", True),
        ("historical_answers_reused", 90),
        ("repeats", 2),
        ("development_event_ids", ["AL112017"]),
    ):
        plan = calibration.read(plan_path)
        plan[field] = value
        write_json(plan_path, plan)
        manifest = calibration.read(manifest_path)
        manifest["files"]["plan.json"] = file_hash(plan_path)
        manifest["package_id"] = fingerprint(
            {key: val for key, val in manifest.items() if key != "package_id"}
        )
        write_json(manifest_path, manifest)
        try:
            with pytest.raises(ValueError, match="scope|plan"):
                calibration.verify(output)
        finally:
            plan_path.write_bytes(old_plan)
            manifest_path.write_bytes(old_manifest)
    manifest = calibration.read(manifest_path)
    manifest["files"].pop("schedule.jsonl")
    manifest["package_id"] = fingerprint(
        {key: val for key, val in manifest.items() if key != "package_id"}
    )
    write_json(manifest_path, manifest)
    try:
        with pytest.raises(ValueError, match="inventory"):
            calibration.verify(output)
    finally:
        manifest_path.write_bytes(old_manifest)
    with pytest.raises(ValueError, match="exists"):
        calibration.prepare(
            build_path,
            ROOT / "artifacts/p1_deepseek_development/provider.json",
            output,
            protocol_path=ROOT / "docs/CALIBRATION_PROTOCOL_V1.md",
            rates_path=ROOT / "artifacts/p1_deepseek_development/docs/rates.json",
        )
    plan = calibration.read(output / "plan.json")
    plan["planned_provider_calls"] = 269
    write_json(output / "plan.json", plan)
    with pytest.raises(ValueError, match="changed"):
        calibration.verify(output)


def test_provider_controls_differ_only_in_output_cap(config):
    configs = calibration.provider_configs(config)
    low = configs["explicit_4096__snapshot"]
    high = deepcopy(configs["explicit_8192__snapshot"])
    high["max_output_tokens"] = 4096
    assert canonical(low) == canonical(high)
    assert configs["legacy_4096__snapshot"] == low
