"""Offline provider fixtures exercise frozen-build collection, resume and score binding."""

from __future__ import annotations

import json

import pytest
from test_automated_cohort_workflow import cohort_build as cohort_build

from disastertrace.automated import collection, provider
from disastertrace.automated.common import (
    file_hash,
    fingerprint,
    read_jsonl,
    write_json,
    write_jsonl,
)
from disastertrace.automated.dynamic import diagnostic_response
from disastertrace.automated.model_workflow import _match_collection_trace, collect_from_build
from disastertrace.automated.provider import ProviderClient
from disastertrace.automated.workflow import score


@pytest.fixture
def offline_transport(tmp_path, monkeypatch):
    calls = []
    controls = {"invalid_at": set(), "empty_at": set(), "failure_at": None}

    def forbidden_network(*args, **kwargs):
        pytest.fail("integration fixture attempted real network access")

    def transport(url, body, headers, timeout, max_response_bytes):
        public = json.loads(json.loads(body)["messages"][1]["content"])
        calls.append(public)
        if len(calls) == controls["failure_at"]:
            return 429, b""
        raw = (
            "invalid fixture response"
            if len(calls) in controls["invalid_at"]
            else diagnostic_response(public, "rule")
        )
        if len(calls) in controls["empty_at"]:
            raw = ""
        return 200, json.dumps(
            {
                "model": "OFFLINE-FIXTURE-NOT-LLM",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": raw},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            }
        ).encode()

    monkeypatch.setattr(provider, "urllib_transport", forbidden_network)
    monkeypatch.setattr(
        collection, "ProviderClient", lambda config: ProviderClient(config, transport=transport)
    )
    config = tmp_path / "provider.json"
    write_json(
        config,
        {
            "model": "OFFLINE-FIXTURE-NOT-LLM",
            "base_url": "http://127.0.0.1:9999/v1",
            "key_env": None,
            "max_output_tokens": 1024,
            "token_parameter": "max_tokens",
            "temperature": 0,
            "timeout": 5,
            "max_response_bytes": 1048576,
        },
    )
    return config, calls, controls


@pytest.mark.parametrize("method", ["snapshot", "answer_history", "structured_state"])
def test_workflow_resumes_actual_method_into_new_output(
    cohort_build, offline_transport, tmp_path, method
):
    config, calls, controls = offline_transport
    controls["invalid_at"] = {2}
    original = tmp_path / "original"
    first = collect_from_build(
        cohort_build[0], config, original, max_queries=3, method=method, group_ids=["AL092021"]
    )
    old_hashes = {
        str(path.relative_to(original)): file_hash(path)
        for path in original.rglob("*")
        if path.is_file()
    }
    resumed = tmp_path / "resumed"
    second = collect_from_build(
        cohort_build[0],
        config,
        resumed,
        max_queries=6,
        method=method,
        group_ids=["AL092021"],
        resume_from=original / "collection",
    )
    assert len(calls) == second["collection"]["attempts_started"] == 6
    assert second["collection"]["invalid_decisions"] == 1
    assert (
        first["metrics"]["schema_success"]["denominator"]
        == second["metrics"]["schema_success"]["denominator"]
        == 10
    )
    assert second["metrics"]["schema_success"]["numerator"] == 5
    assert second["collection"]["reported_prompt_tokens"] == 66
    assert second["collection"]["reported_completion_tokens"] == 42
    assert second["eligible_for_llm_leaderboard"] is False
    assert second["collection"]["transport_kind"] == "injected_transport_unverified"
    assert read_jsonl(resumed / "collection/responses.jsonl")[:3] == read_jsonl(
        original / "collection/responses.jsonl"
    )
    assert old_hashes == {
        str(path.relative_to(original)): file_hash(path)
        for path in original.rglob("*")
        if path.is_file()
    }
    traces = read_jsonl(resumed / "imported_run/trace.jsonl")
    assert [row["request"] for row in traces[:6]] == calls
    assert all(row["provider_requests"] == 0 for row in traces)
    if method == "answer_history":
        assert len(calls[3]["answer_history"]) == 2
        assert calls[5]["answer_history"] == []
    elif method == "structured_state":
        assert calls[2]["previous_state"] == calls[1]["previous_state"]
        assert calls[5]["previous_state"] is None
    else:
        assert all("previous_state" not in call and "answer_history" not in call for call in calls)
    rescored = score(cohort_build[0], resumed / "imported_run", tmp_path / "rescored.json")
    assert rescored["metrics"] == second["metrics"]


@pytest.mark.parametrize(
    "artifact", ["collection_response", "collection_usage", "trace_response", "trace_carrier"]
)
def test_score_rejects_collection_or_trace_tampering(
    cohort_build, offline_transport, tmp_path, artifact
):
    config, _, _ = offline_transport
    output = tmp_path / "collected"
    collect_from_build(cohort_build[0], config, output, max_queries=3, group_ids=["AL092021"])
    run_config = json.loads((output / "imported_run/run.json").read_text())
    if artifact.startswith("collection"):
        if artifact == "collection_response":
            path = output / "collection/responses.jsonl"
            rows = read_jsonl(path)
            rows[0]["raw_response"] = "forged"
        else:
            path = output / "collection/outcomes.jsonl"
            rows = read_jsonl(path)
            rows[0]["metadata"]["usage"]["completion_tokens"] += 1
            rows[0]["metadata_sha256"] = fingerprint(rows[0]["metadata"])
        write_jsonl(path, rows)
        # Rehash outer manifests so semantic audit, rather than a stale checksum,
        # must detect the mismatch between body, response, metadata and exposure.
        summary = json.loads((output / "collection/summary.json").read_text())
        summary["artifact_sha256"][path.name] = file_hash(path)
        write_json(output / "collection/summary.json", summary)
        run_config["collection_binding"]["artifact_sha256"] = {
            path.name: file_hash(path)
            for path in (output / "collection").iterdir()
            if path.is_file()
        }
    else:
        path = output / "imported_run/trace.jsonl"
        rows = read_jsonl(path)
        if artifact == "trace_response":
            rows[0]["raw_response"] = "forged"
        else:
            rows[2]["request"]["previous_state"] = None
            rows[2]["request_sha256"] = fingerprint(rows[2]["request"])
        write_jsonl(path, rows)
        run_config["trace_sha256"] = file_hash(path)
    write_json(output / "imported_run/run.json", run_config)
    with pytest.raises(ValueError, match="collection|response|metadata|request"):
        score(cohort_build[0], output / "imported_run", tmp_path / "rejected.json")


@pytest.mark.parametrize("guard", [{"max_request_bytes": 0}, {"max_reserved_output_tokens": 1024}])
def test_workflow_guard_stop_retains_all_selected_checkpoints(
    cohort_build, offline_transport, tmp_path, guard
):
    config, calls, _ = offline_transport
    output = tmp_path / "guarded"
    result = collect_from_build(
        cohort_build[0], config, output, max_queries=10, group_ids=["AL092021"], **guard
    )
    expected = 1 if "max_reserved_output_tokens" in guard else 0
    assert len(calls) == result["collection"]["completions_received"] == expected
    assert result["metrics"]["schema_success"]["numerator"] == expected
    assert result["metrics"]["schema_success"]["denominator"] == 10
    assert result["collection"]["unsubmitted_checkpoints"] == 10 - expected


def test_workflow_provider_error_keeps_denominator_and_refuses_resume(
    cohort_build, offline_transport, tmp_path
):
    config, calls, controls = offline_transport
    controls["failure_at"] = 2
    output = tmp_path / "failed"
    result = collect_from_build(
        cohort_build[0], config, output, max_queries=10, group_ids=["AL092021"]
    )
    assert result["collection"]["status"] == "provider_error"
    assert result["metrics"]["schema_success"]["numerator"] == 1
    assert result["metrics"]["schema_success"]["denominator"] == 10
    with pytest.raises(ValueError, match="resume"):
        collect_from_build(
            cohort_build[0],
            config,
            tmp_path / "retry",
            max_queries=10,
            group_ids=["AL092021"],
            resume_from=output / "collection",
        )
    assert len(calls) == 2


@pytest.mark.parametrize("mutation", ["uncollected_response", "trace_method"])
def test_binding_rejects_unaudited_response_or_method(
    cohort_build, offline_transport, tmp_path, mutation
):
    config, _, _ = offline_transport
    output = tmp_path / "partial"
    collect_from_build(cohort_build[0], config, output, max_queries=3, group_ids=["AL092021"])
    audit = json.loads((output / "collection_audit.json").read_text())
    traces = read_jsonl(output / "imported_run/trace.jsonl")
    if mutation == "uncollected_response":
        traces[3]["raw_response"] = diagnostic_response(traces[3]["request"], "rule")
        traces[3]["status"] = "accepted"
    else:
        traces[0]["method"] = "snapshot"
    with pytest.raises(ValueError, match="collection|response|method"):
        _match_collection_trace(audit, traces)


def test_collected_empty_response_remains_invalid_not_missing(
    cohort_build, offline_transport, tmp_path
):
    config, calls, controls = offline_transport
    controls["empty_at"] = {2}
    output = tmp_path / "empty-response"
    result = collect_from_build(
        cohort_build[0], config, output, max_queries=3, group_ids=["AL092021"]
    )
    assert len(calls) == result["collection"]["completions_received"] == 3
    assert result["collection"]["invalid_decisions"] == 1
    traces = read_jsonl(output / "imported_run/trace.jsonl")
    assert traces[1]["raw_response"] == "" and traces[1]["status"] == "invalid"
    assert result["metrics"]["schema_success"]["numerator"] == 2
    assert result["metrics"]["schema_success"]["denominator"] == 10
