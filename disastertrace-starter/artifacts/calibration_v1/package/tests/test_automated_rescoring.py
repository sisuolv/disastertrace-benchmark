"""Offline migration validates archived code and never rewrites historical artifacts."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from disastertrace.automated.common import (
    canonical,
    file_hash,
    fingerprint,
    read_jsonl,
    write_json,
    write_jsonl,
)
from disastertrace.automated.dynamic import build_episodes, diagnostic_response, run_episode
from disastertrace.automated.rescoring import rescore, verify_rescore


def tree_hashes(root):
    return {
        str(path.relative_to(root)): file_hash(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture
def historical(tmp_path):
    build = tmp_path / "historical_build"
    source = build / "implementation_source/automated"
    source.mkdir(parents=True)
    package = Path(__file__).parents[1] / "src/disastertrace/automated"
    for item in package.glob("*.py"):
        (source / item.name).write_bytes(item.read_bytes())
    (source / "archived_only_marker.py").write_text("ARCHIVED = True\n", encoding="ascii")
    implementation = {"schema_version": "automated_implementation_v1", "files": tree_hashes(source)}
    implementation["implementation_id"] = fingerprint(implementation)
    write_json(build / "implementation.json", implementation)
    records = []
    for index, wind in enumerate((85, 105, 115), 1):
        lines = [
            "SYNTHETIC MIGRATION TEST RECORD",
            "LOCATION...23.5N 83.2W",
            f"MAXIMUM SUSTAINED WINDS...{wind} MPH",
            "MINIMUM CENTRAL PRESSURE...985 MB",
            "DISCUSSION AND OUTLOOK",
            "----------------------",
            f"Maximum sustained winds are near {wind} mph with higher gusts.",
        ]
        records.append(
            {
                "record_id": f"synthetic:migration:{index}",
                "storm_id": "SYNTHETIC_MIGRATION",
                "issued_at": f"2040-08-01T{6 * index:02d}:00:00Z",
                "raw_text": "\n".join(lines),
                "fields": {
                    "maximum_wind_mph": wind,
                    "latitude_deg": 23.5,
                    "longitude_deg": -83.2,
                    "minimum_pressure_mb": 985,
                },
                "field_evidence": {
                    field: {"line_start": line, "line_end": line, "text": lines[line - 1]}
                    for field, line in (
                        ("maximum_wind_mph", 3),
                        ("latitude_deg", 2),
                        ("longitude_deg", 2),
                        ("minimum_pressure_mb", 4),
                    )
                },
                "provenance": {"source_origin": "synthetic_record"},
            }
        )
    episodes = build_episodes(records)
    for episode in episodes:
        episode["split"] = "development"
    write_jsonl(build / "episodes/dynamic_episodes.jsonl", episodes)
    manifest = {"schema_version": "automated_build_v1", "files": tree_hashes(build)}
    manifest["build_id"] = fingerprint(manifest)
    write_json(build / "manifest.json", manifest)
    run = tmp_path / "historical_run"
    traces = [row for episode in episodes for row in run_episode(episode, "rule", max_queries=5)]
    write_jsonl(run / "trace.jsonl", traces)
    write_json(
        run / "run.json",
        {
            "schema_version": "automated_run_v1",
            "build_id": manifest["build_id"],
            "implementation_id": implementation["implementation_id"],
            "track": "dynamic",
            "backend": "rule",
            "split": "development",
            "method": "structured_state",
            "group_ids": None,
            "max_queries": 10,
            "logical_queries": 10,
            "checkpoint_attempts": 10,
            "selected_episode_ids": [ep["episode_id"] for ep in episodes],
            "trace_sha256": file_hash(run / "trace.jsonl"),
            "model_kind": "diagnostic_program",
            "live_model_calls": 0,
            "eligible_for_llm_leaderboard": False,
        },
    )
    return build, run


def test_rescore_replays_distinct_archived_implementation_and_preserves_old_bytes(
    historical, tmp_path
):
    build, run = historical
    before = tree_hashes(build), tree_hashes(run)
    output = tmp_path / "derived"
    manifest = rescore(build, run, output)
    assert manifest["new_provider_requests"] == 0
    assert manifest["schema_version"] == "offline_rescore_v1"
    assert verify_rescore(output)["verified"] is True
    assert before == (tree_hashes(build), tree_hashes(run))
    assert not list(build.rglob("__pycache__"))
    assert not list(output.rglob("__pycache__"))
    assert (output / "baseline_v1.json").exists()
    assert (output / "score_v2.json").exists()
    assert (output / "evidence_index_v2.json").exists()
    assert (output / "comparison.json").exists()


def test_supplied_original_score_must_equal_archived_replay(historical, tmp_path):
    build, run = historical
    first = tmp_path / "first"
    rescore(build, run, first)
    baseline = first / "baseline_v1.json"
    second = rescore(build, run, tmp_path / "second", historical_score=baseline)
    assert second["original_inputs"]["historical_score"]["sha256"] == file_hash(baseline)
    write_json(tmp_path / "false_score.json", {"fabricated": True})
    with pytest.raises(ValueError, match="historical score"):
        rescore(build, run, tmp_path / "third", historical_score=tmp_path / "false_score.json")


@pytest.mark.parametrize("target", ["build", "run", "existing", "symlink_parent"])
def test_output_cannot_overwrite_or_enter_historical_directories(historical, tmp_path, target):
    build, run = historical
    if target == "build":
        output = build / "new_scores"
    elif target == "run":
        output = run / "new_scores"
    elif target == "symlink_parent":
        (tmp_path / "alias").symlink_to(build, target_is_directory=True)
        output = tmp_path / "alias/new_scores"
    else:
        output = tmp_path / "already_present"
        output.mkdir()
    before = tree_hashes(build), tree_hashes(run)
    with pytest.raises(ValueError):
        rescore(build, run, output)
    assert before == (tree_hashes(build), tree_hashes(run))


@pytest.mark.parametrize(
    "artifact",
    [
        "implementation_source/automated/dynamic.py",
        "episodes/dynamic_episodes.jsonl",
        "implementation.json",
    ],
)
def test_rejects_modified_historical_build_before_executing_archived_code(
    historical, tmp_path, artifact
):
    build, run = historical
    path = build / artifact
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="(hash|changed|fingerprint)"):
        rescore(build, run, tmp_path / "derived")


def test_rejects_modified_historical_trace(historical, tmp_path):
    build, run = historical
    with (run / "trace.jsonl").open("a") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="checksum"):
        rescore(build, run, tmp_path / "derived")


@pytest.mark.parametrize(
    "artifact",
    [
        "baseline_v1.json",
        "score_v2.json",
        "evidence_index_v2.json",
        "comparison.json",
        "implementation_source/automated/scoring_v2.py",
    ],
)
def test_verification_detects_derived_artifact_tampering(historical, tmp_path, artifact):
    output = tmp_path / "derived"
    rescore(*historical, output)
    path = output / artifact
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="(hash|changed)"):
        verify_rescore(output)


def test_verification_recomputes_scores_even_if_artifact_hash_and_manifest_are_rewritten(
    historical, tmp_path
):
    from disastertrace.automated.common import strict_json

    output = tmp_path / "derived"
    rescore(*historical, output)
    score_path = output / "score_v2.json"
    score = strict_json(score_path.read_text())
    score["metrics"]["state_accuracy"]["numerator"] = 0
    write_json(score_path, score)
    manifest_path = output / "manifest.json"
    manifest = strict_json(manifest_path.read_text())
    manifest["files"]["score_v2.json"] = file_hash(score_path)
    manifest["rescore_id"] = fingerprint(
        {key: value for key, value in manifest.items() if key != "rescore_id"}
    )
    write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="recomputed"):
        verify_rescore(output)


def test_verification_binds_original_response_artifacts(historical, tmp_path):
    build, run = historical
    output = tmp_path / "derived"
    rescore(build, run, output)
    rows = read_jsonl(run / "trace.jsonl")
    rows[0]["raw_response"] = "tampered"
    write_jsonl(run / "trace.jsonl", rows)
    with pytest.raises(ValueError, match="original"):
        verify_rescore(output)


def test_no_unknown_executable_source_may_hide_outside_saved_implementation_manifest(
    historical, tmp_path
):
    build, run = historical
    (build / "implementation_source/automated/unlisted.py").write_text("UNLISTED = True\n")
    with pytest.raises(ValueError, match="implementation"):
        rescore(build, run, tmp_path / "derived")


def test_equivalent_body_citation_has_exactly_one_reasoned_difference(historical, tmp_path):
    build, run = historical
    traces = read_jsonl(run / "trace.jsonl")
    decision = json.loads(traces[4]["raw_response"])
    decision["state"]["maximum_wind_mph"]["evidence"][0]["line"] = 7
    traces[4]["raw_response"] = canonical(decision)
    traces[4]["state_after"] = decision
    write_jsonl(run / "trace.jsonl", traces)
    config = json.loads((run / "run.json").read_text())
    config["trace_sha256"] = file_hash(run / "trace.jsonl")
    write_json(run / "run.json", config)
    output = tmp_path / "derived"
    rescore(build, run, output)
    old, new = [
        json.loads((output / filename).read_text())
        for filename in ("baseline_v1.json", "score_v2.json")
    ]
    assert old["metrics"]["grounded_state"]["numerator"] == 49
    assert new["metrics"]["grounded_state"]["numerator"] == 50
    comparison = json.loads((output / "comparison.json").read_text())
    assert len(comparison["per_field"]) == 50
    assert len(comparison["changed_fields"]) == 1
    change = comparison["changed_fields"][0]
    assert change["field"] == "maximum_wind_mph"
    assert change["reason"] == "supported"
    assert change["citation_checks"][0]["valid"] is True


def test_verification_uses_saved_functions_after_current_functions_change(
    historical, tmp_path, monkeypatch
):
    from disastertrace.automated import evidence_support, scoring_v2, workflow

    output = tmp_path / "derived"
    rescore(*historical, output)

    def changed_current_implementation(*args, **kwargs):
        raise AssertionError("Current implementation must not replace archived code")

    monkeypatch.setattr(scoring_v2, "score_dynamic_v2", changed_current_implementation)
    monkeypatch.setattr(evidence_support, "build_evidence_index", changed_current_implementation)
    monkeypatch.setattr(workflow, "score", changed_current_implementation)
    assert verify_rescore(output)["verified"] is True


def test_rescore_rechecks_input_inventory_after_computation(historical, tmp_path, monkeypatch):
    from disastertrace.automated import rescoring

    build, run = historical
    original_compute = rescoring._compute_v2

    def mutate_after_compute(*args):
        result = original_compute(*args)
        with (run / "trace.jsonl").open("a") as stream:
            stream.write("\n")
        return result

    monkeypatch.setattr(rescoring, "_compute_v2", mutate_after_compute)
    with pytest.raises(ValueError, match="original"):
        rescore(build, run, tmp_path / "derived")
    assert not (tmp_path / "derived/manifest.json").exists()


def test_module_cli_rescores_and_verifies_without_provider_calls(historical, tmp_path):
    build, run = historical
    output = tmp_path / "derived"
    command = [sys.executable, "-m", "disastertrace.automated.rescoring"]
    migrated = subprocess.run(
        command + ["rescore", "--build", str(build), "--run", str(run), "--output", str(output)],
        capture_output=True,
        text=True,
    )
    assert migrated.returncode == 0, migrated.stderr
    assert "new provider requests: 0" in migrated.stdout
    verified = subprocess.run(
        command + ["verify", "--output", str(output)], capture_output=True, text=True
    )
    assert verified.returncode == 0, verified.stderr
    assert "Verified offline rescore" in verified.stdout


@pytest.fixture
def collected(historical, tmp_path):
    from disastertrace.automated.collection import collect_model
    from disastertrace.automated.collection_audit import audit_collection
    from disastertrace.automated.provider import ProviderClient, ProviderConfig

    build, original_run = historical
    run = tmp_path / "historical_trial/imported_run"
    shutil.copytree(original_run, run)
    episodes = read_jsonl(build / "episodes/dynamic_episodes.jsonl")
    calls = []

    def transport(url, body, headers, timeout, max_response_bytes):
        public = json.loads(json.loads(body)["messages"][1]["content"])
        calls.append(public)
        return 200, canonical(
            {
                "model": "OFFLINE-MIGRATION-FIXTURE-NOT-LLM",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": diagnostic_response(public, "rule"),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        ).encode()

    config = ProviderConfig(
        model="OFFLINE-MIGRATION-FIXTURE-NOT-LLM",
        base_url="http://localhost:9999/v1",
        key_env=None,
        max_output_tokens=256,
        token_parameter="max_tokens",
        temperature=0,
        timeout=5,
        max_response_bytes=65536,
    )
    collection = run.parent / "collection"
    collect_model(
        episodes,
        config,
        collection,
        max_queries=10,
        client=ProviderClient(config, transport=transport),
    )
    assert len(calls) == 10
    audit = audit_collection(episodes, collection)
    run_config = json.loads((run / "run.json").read_text())
    run_config["collection_binding"] = {
        "relative_path": "../collection",
        "audit_sha256": fingerprint(audit),
        "artifact_sha256": tree_hashes(collection),
    }
    write_json(run / "run.json", run_config)
    return build, run, collection, calls


def test_migration_reaudits_bound_collection_without_reissuing_requests(collected, tmp_path):
    build, run, collection, calls = collected
    original = tree_hashes(run.parent)
    output = tmp_path / "derived"
    manifest = rescore(build, run, output)
    assert manifest["original_inputs"]["collection"]["files"] == tree_hashes(collection)
    assert verify_rescore(output)["historical_collection_reaudited"] is True
    assert tree_hashes(run.parent) == original
    assert len(calls) == 10


@pytest.mark.parametrize("location", ["collection", "trial_parent"])
def test_derived_output_cannot_enter_historical_collection_package(collected, location):
    build, run, collection, _ = collected
    root = collection if location == "collection" else run.parent
    with pytest.raises(ValueError, match="outside historical"):
        rescore(build, run, root / "derived")


def test_rehashed_inconsistent_collection_is_rejected_by_archived_audit(collected, tmp_path):
    build, run, collection, _ = collected
    responses = read_jsonl(collection / "responses.jsonl")
    responses[0]["raw_response"] = "FORGED"
    write_jsonl(collection / "responses.jsonl", responses)
    summary = json.loads((collection / "summary.json").read_text())
    summary["artifact_sha256"]["responses.jsonl"] = file_hash(collection / "responses.jsonl")
    write_json(collection / "summary.json", summary)
    config = json.loads((run / "run.json").read_text())
    config["collection_binding"]["artifact_sha256"] = tree_hashes(collection)
    write_json(run / "run.json", config)
    with pytest.raises(ValueError, match="(audit|response)"):
        rescore(build, run, tmp_path / "derived")


def test_original_collection_requests_and_responses_remain_bound_after_migration(
    collected, tmp_path
):
    build, run, collection, _ = collected
    output = tmp_path / "derived"
    rescore(build, run, output)
    with (collection / "requests.jsonl").open("a") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="original"):
        verify_rescore(output)
