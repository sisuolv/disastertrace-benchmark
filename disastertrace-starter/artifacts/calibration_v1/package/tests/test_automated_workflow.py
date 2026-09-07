"""Offline integration checks against the selected, hashed source snapshots.

All runs are diagnostics or explicitly submitted fixtures, never LLM results.
"""

import json
import shutil
from pathlib import Path

import pytest

from disastertrace.automated import workflow
from disastertrace.automated.common import read_jsonl
from disastertrace.automated.workflow import build, report, run, score, verify_build

REFERENCES = Path(__file__).resolve().parents[2] / "references"


def read_json(path):
    return json.loads(path.read_text())


def write_json(path, value):
    path.write_text(json.dumps(value) + "\n")


def write_predictions(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


@pytest.fixture(scope="session")
def real_build(tmp_path_factory):
    path = tmp_path_factory.mktemp("real-source-workflow") / "build"
    summary = build(REFERENCES, path)
    return path, summary


def test_actual_sources_build_with_quarantine_and_honest_scope(real_build):
    path, summary = real_build
    assert summary["disasterbench_source_tasks"] == 233
    assert summary["disasterbench_admitted"] == 230
    assert summary["disasterbench_quarantined"] == 3
    assert summary["cyportqa_templates"] == 48
    assert summary["nhc_admitted_records"] == 3
    assert summary["dynamic_episodes"] == 2
    assert summary["dynamic_checkpoints"] == 10
    assert summary["independent_weather_events"] == 1
    assert summary["schedule_origin"] == "controlled_release"
    assert summary["content_edits"] is False
    assert summary["new_human_reviews"] == summary["model_calls"] == 0
    assert verify_build(path)["build_id"] == summary["build_id"]
    assert len(read_json(path / "profiles/disasterbench.json")["quarantine"]) == 3
    records = read_jsonl(path / "records/nhc_records.jsonl")
    assert [item["fields"]["maximum_wind_mph"] for item in records] == [85, 105, 105]
    assert records[-1]["issued_at"] == "2021-08-29T03:00:00+00:00"
    for record in records:
        assert record["provenance"]["availability_proven"] is False


def test_source_checksum_change_stops_build_before_admission(tmp_path):
    relative = Path("no_manual_review_2026-09-06/weather_qa_sources")
    copied_references = tmp_path / "references"
    snapshot = copied_references / relative
    shutil.copytree(REFERENCES / relative, snapshot)
    manifest = read_json(snapshot / "MANIFEST.json")
    selected = next(
        row
        for row in manifest
        if row["repo"] == "TamuChen18/DisasterBench_Open" and row["path"] == "data/benchmark.jsonl"
    )
    source = snapshot / selected["local_path"]
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        build(copied_references, tmp_path / "rejected-build")


@pytest.mark.parametrize("artifact", ["summary.json", "manifest.json"])
def test_build_artifact_and_manifest_tampering_are_rejected(real_build, tmp_path, artifact):
    copied = tmp_path / "copied-build"
    shutil.copytree(real_build[0], copied)
    value = read_json(copied / artifact)
    value["unexpected_mutation"] = True
    write_json(copied / artifact, value)
    with pytest.raises(ValueError, match="(artifact changed|fingerprint mismatch)"):
        run(copied, tmp_path / "rejected-run", track="dynamic", backend="rule")
    assert not (tmp_path / "rejected-run").exists()


def test_build_run_score_and_report_refuse_overwrites(real_build, tmp_path):
    path, _ = real_build
    run_path, score_path, report_path = (
        tmp_path / "run",
        tmp_path / "score.json",
        tmp_path / "report.md",
    )
    with pytest.raises(ValueError, match="already exists"):
        build(REFERENCES, path)
    run(path, run_path, track="dynamic", backend="rule")
    original_trace = (run_path / "trace.jsonl").read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        run(path, run_path, track="dynamic", backend="no-update")
    assert (run_path / "trace.jsonl").read_bytes() == original_trace
    score(path, run_path, score_path)
    original_score = score_path.read_bytes()
    with pytest.raises(ValueError, match="output exists"):
        score(path, run_path, score_path)
    assert score_path.read_bytes() == original_score
    content = report(path, [score_path], report_path)
    assert "not LLM benchmark results" in content
    assert "230/233" in content
    with pytest.raises(ValueError, match="output exists"):
        report(path, [score_path], report_path)
    assert report_path.read_text() == content


@pytest.mark.parametrize(
    "backend,grounded,actions",
    [
        ("rule", 50, 10),
        ("last-arrival", 42, 8),
        ("no-update", 18, 2),
    ],
)
def test_dynamic_diagnostic_controls_expose_distinct_failure_modes(
    real_build, tmp_path, backend, grounded, actions
):
    path, _ = real_build
    run_path = tmp_path / "run"
    config = run(path, run_path, track="dynamic", backend=backend, max_queries=10)
    result = score(path, run_path, tmp_path / "score.json")
    assert config["logical_queries"] == config["checkpoint_attempts"] == 10
    assert config["live_model_calls"] == 0
    assert config["model_kind"] == "diagnostic_program"
    assert config["eligible_for_llm_leaderboard"] is False
    assert result["metrics"]["grounded_state"] == {
        "numerator": grounded,
        "denominator": 50,
        "value": grounded / 50,
    }
    assert result["metrics"]["action_accuracy"] == {
        "numerator": actions,
        "denominator": 10,
        "value": actions / 10,
    }
    assert result["independent_event_groups"] == 1
    if backend == "last-arrival":
        assert [
            row["checkpoint_id"] for row in result["per_checkpoint"] if not row["all_correct"]
        ] == ["c3", "c3"]
    if backend == "no-update":
        assert result["metrics"]["known_answer_coverage"]["value"] == 0.0
        assert result["metrics"]["unknown_accuracy"]["value"] == 1.0


@pytest.mark.parametrize("budget", [0, 3, 7])
def test_global_budget_keeps_all_ten_attempts_in_denominator(real_build, tmp_path, budget):
    path, _ = real_build
    run_path = tmp_path / "run"
    config = run(path, run_path, track="dynamic", backend="rule", max_queries=budget)
    traces = read_jsonl(run_path / "trace.jsonl")
    result = score(path, run_path, tmp_path / "score.json")
    assert len(traces) == config["checkpoint_attempts"] == 10
    assert sum(row["logical_queries"] for row in traces) == budget
    assert config["logical_queries"] == budget
    assert config["stop_reason"] == "budget_exhausted"
    assert [row["status"] for row in traces] == ["ok"] * budget + ["budget_exhausted"] * (
        10 - budget
    )
    assert result["metrics"]["schema_success"] == {
        "numerator": budget,
        "denominator": 10,
        "value": budget / 10,
    }
    assert result["metrics"]["grounded_state"]["denominator"] == 50
    assert result["metrics"]["action_accuracy"]["denominator"] == 10


def test_disasterbench_reference_copy_scores_230_and_is_explicitly_a_fixture(real_build, tmp_path):
    path, _ = real_build
    run_path = tmp_path / "run"
    config = run(
        path, run_path, track="disasterbench", backend="reference-fixture", max_queries=230
    )
    result = score(path, run_path, tmp_path / "score.json")
    assert result["aggregate"]["expected_tasks"] == result["aggregate"]["correct_tasks"] == 230
    assert result["aggregate"]["exact_match_accuracy"] == 1.0
    assert config["model_kind"] == "scorer_fixture"
    assert config["eligible_for_llm_leaderboard"] is False
    assert config["live_model_calls"] == 0
    assert config["logical_queries"] == 230
    traces = read_jsonl(run_path / "trace.jsonl")
    assert all(row["fixture_reads_private_reference"] is True for row in traces)
    assert all(row["eligible_for_llm_leaderboard"] is False for row in traces)


def test_disasterbench_missing_and_empty_controls_keep_every_admitted_task(real_build, tmp_path):
    path, _ = real_build
    empty_predictions = tmp_path / "empty.jsonl"
    empty_predictions.write_text("")
    for backend in ("empty-control", "submissions"):
        kwargs = {"predictions_path": empty_predictions} if backend == "submissions" else {}
        run_path = tmp_path / backend
        run(path, run_path, track="disasterbench", backend=backend, max_queries=230, **kwargs)
        result = score(path, run_path, tmp_path / f"{backend}.json")
        aggregate = result["aggregate"]
        assert aggregate["expected_tasks"] == 230
        assert aggregate["correct_tasks"] == 0
        assert aggregate["exact_match_accuracy"] == 0.0
        assert aggregate["invalid_predictions"] == (230 if backend == "empty-control" else 0)
        assert aggregate["missing_predictions"] == (230 if backend == "submissions" else 0)


def test_actual_model_requests_contain_only_public_inputs_and_released_evidence(
    real_build, tmp_path
):
    path, _ = real_build
    tasks = read_jsonl(path / "public/disasterbench_tasks.jsonl")
    references = read_jsonl(path / "private/disasterbench_references.jsonl")
    assert {row["task_id"] for row in tasks} == {row["task_id"] for row in references}
    assert all("structured_plan" not in task and "label_origin" not in task for task in tasks)
    assert all(task["tools"] == tasks[0]["tools"] for task in tasks)
    run_path = tmp_path / "run"
    run(path, run_path, track="dynamic", backend="rule", max_queries=10)
    traces = read_jsonl(run_path / "trace.jsonl")
    for trace in traces:
        request = trace["request"]
        assert set(request) == {
            "protocol",
            "instruction",
            "checkpoint_time",
            "required_fields",
            "policy",
            "evidence",
            "previous_state",
        }
        for evidence in request["evidence"]:
            assert set(evidence) == {"delivery_index", "record_id", "issued_at", "text"}
        if trace["checkpoint_id"] == "c0":
            assert request["evidence"] == []
            assert request["previous_state"] is None
        if trace["checkpoint_id"] != "c4":
            assert "nhc-al092021-public-011" not in json.dumps(request)
        if trace["checkpoint_id"] == "c2" and trace["episode_id"].endswith(":delay"):
            assert {row["record_id"] for row in request["evidence"]} == {"nhc-al092021-public-009"}


@pytest.mark.parametrize("mutation", ["raw_type", "unknown_id", "duplicate", "id_type"])
def test_dynamic_submission_contract_rejects_malformed_identifiers_and_types(
    real_build, tmp_path, mutation
):
    path, _ = real_build
    row = {
        "episode_id": "al092021:controlled:base",
        "checkpoint_id": "c0",
        "raw_response": "not JSON",
    }
    if mutation == "raw_type":
        row["raw_response"] = {}
    elif mutation == "unknown_id":
        row["episode_id"] = "unknown-event"
    elif mutation == "id_type":
        row["episode_id"] = []
    predictions = tmp_path / "predictions.jsonl"
    write_predictions(predictions, [row, row] if mutation == "duplicate" else [row])
    with pytest.raises(ValueError):
        run(
            path,
            tmp_path / "run",
            track="dynamic",
            backend="submissions",
            predictions_path=predictions,
        )


def test_invalid_dynamic_response_and_missing_submissions_are_counted(real_build, tmp_path):
    path, _ = real_build
    predictions, run_path = tmp_path / "predictions.jsonl", tmp_path / "run"
    write_predictions(
        predictions,
        [
            {
                "episode_id": "al092021:controlled:base",
                "checkpoint_id": "c0",
                "raw_response": "not JSON",
            }
        ],
    )
    config = run(
        path,
        run_path,
        track="dynamic",
        backend="submissions",
        predictions_path=predictions,
        max_queries=10,
    )
    result = score(path, run_path, tmp_path / "score.json")
    assert config["model_kind"] == "submitted_unverified"
    assert result["status_counts"] == {"invalid": 1, "missing": 9}
    assert result["metrics"]["schema_success"] == {"numerator": 0, "denominator": 10, "value": 0.0}
    assert result["metrics"]["grounded_state"]["denominator"] == 50


def test_saved_trace_checksum_is_verified_before_scoring(real_build, tmp_path):
    path, _ = real_build
    run_path = tmp_path / "run"
    run(path, run_path, track="dynamic", backend="rule")
    trace_path = run_path / "trace.jsonl"
    trace_path.write_bytes(trace_path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="trace checksum mismatch"):
        score(path, run_path, tmp_path / "rejected.json")


def test_score_and_report_refuse_mismatched_build_identity(real_build, tmp_path):
    path, _ = real_build
    run_path, score_path = tmp_path / "run", tmp_path / "score.json"
    run(path, run_path, track="dynamic", backend="rule")
    result = score(path, run_path, score_path)
    config = read_json(run_path / "run.json")
    config["build_id"] = "different-build"
    write_json(run_path / "run.json", config)
    with pytest.raises(ValueError, match="identity mismatch"):
        score(path, run_path, tmp_path / "rejected-score.json")
    result["build_id"] = "different-build"
    write_json(score_path, result)
    with pytest.raises(ValueError, match="different builds"):
        report(path, [score_path], tmp_path / "rejected-report.md")


def test_implementation_changes_require_a_new_build_and_cannot_rescore_old_traces(
    real_build, tmp_path, monkeypatch
):
    path, _ = real_build
    run_path = tmp_path / "run"
    config = run(path, run_path, track="dynamic", backend="rule")
    original = workflow.implementation_snapshot()
    assert config["implementation_id"] == original["implementation_id"]
    assert read_json(path / "implementation.json") == original
    changed = {
        **original,
        "files": {**original["files"], "workflow.py": "0" * 64},
        "implementation_id": "different-implementation",
    }
    with monkeypatch.context() as scoped:
        scoped.setattr(workflow, "implementation_snapshot", lambda: changed)
        with pytest.raises(ValueError, match="implementation changed"):
            run(path, tmp_path / "rejected-run", track="dynamic", backend="rule")
        with pytest.raises(ValueError, match="implementation changed"):
            score(path, run_path, tmp_path / "rejected-score.json")
    assert not (tmp_path / "rejected-run").exists()
    assert not (tmp_path / "rejected-score.json").exists()
    config["implementation_id"] = "different-implementation"
    write_json(run_path / "run.json", config)
    with pytest.raises(ValueError, match="implementation"):
        score(path, run_path, tmp_path / "rejected-run-version.json")


def test_query_budget_rejects_noninteger_or_negative_configuration(real_build, tmp_path):
    for index, budget in enumerate((True, 1.5, "10", -1)):
        with pytest.raises(ValueError, match="nonnegative integer"):
            run(
                real_build[0],
                tmp_path / f"invalid-{index}",
                track="dynamic",
                backend="rule",
                max_queries=budget,
            )


@pytest.mark.parametrize(
    "track,backend,field,value,budget",
    [
        ("dynamic", "rule", "max_queries", 0, 10),
        ("dynamic", "rule", "logical_queries", 0, 10),
        ("disasterbench", "reference-fixture", "max_queries", 1, 230),
    ],
)
def test_saved_run_budget_must_agree_with_actual_trace_and_prediction_count(
    real_build, tmp_path, track, backend, field, value, budget
):
    path, _ = real_build
    run_path = tmp_path / "run"
    config = run(path, run_path, track=track, backend=backend, max_queries=budget)
    assert config["logical_queries"] == budget
    config[field] = value
    write_json(run_path / "run.json", config)
    with pytest.raises(ValueError):
        score(path, run_path, tmp_path / "rejected-score.json")
