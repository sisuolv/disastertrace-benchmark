from __future__ import annotations

import copy
import json

import pytest
from test_automated_collection import config as config
from test_automated_collection import episodes as episodes
from test_automated_collection import mock_client

from disastertrace.automated.collection import collect_model
from disastertrace.automated.collection_audit import audit_collection
from disastertrace.automated.common import (
    file_hash,
    fingerprint,
    read_jsonl,
    write_json,
    write_jsonl,
)


def refresh_hashes(output):
    summary = json.loads((output / "summary.json").read_text())
    summary["artifact_sha256"] = {
        name: file_hash(output / name) for name in summary["artifact_sha256"]
    }
    summary["plan_sha256"] = fingerprint(json.loads((output / "plan.json").read_text()))
    write_json(output / "summary.json", summary)


def test_audit_reconstructs_actual_carrier_without_network(config, episodes, tmp_path):
    client, calls = mock_client(config)
    output = tmp_path / "original"
    collect_model(episodes, config, output, max_queries=4, client=client)
    audit = audit_collection(episodes, output)
    assert audit["valid"] and audit["safe_to_resume"]
    assert audit["completed_checkpoints"] == 4
    assert len(calls) == 4
    assert [row["public_request"] for row in audit["verified_requests"]] == calls
    assert audit["counters"]["attempts_started"] == 4


@pytest.mark.parametrize(
    "mutation",
    [
        "wire",
        "carrier",
        "response",
        "usage",
        "model",
        "state",
        "status",
        "count",
        "episode",
        "config",
    ],
)
def test_rehashed_tampering_rejected(config, episodes, tmp_path, mutation):
    client, _ = mock_client(config)
    output = tmp_path / mutation
    collect_model(episodes, config, output, max_queries=4, client=client)
    requests = read_jsonl(output / "requests.jsonl")
    outcomes = read_jsonl(output / "outcomes.jsonl")
    responses = read_jsonl(output / "responses.jsonl")
    plan = json.loads((output / "plan.json").read_text())
    if mutation == "wire":
        requests[0]["prepared"]["payload"]["model"] = "forged"
    elif mutation == "carrier":
        requests[2]["public_request"]["previous_state"] = None
        requests[2]["public_request_sha256"] = fingerprint(requests[2]["public_request"])
    elif mutation == "response":
        responses[0]["raw_response"] = "forged"
        outcomes[0]["raw_response_sha256"] = fingerprint("forged")
    elif mutation == "usage":
        outcomes[0]["metadata"]["usage"]["prompt_tokens"] += 1
        outcomes[0]["metadata_sha256"] = fingerprint(outcomes[0]["metadata"])
    elif mutation == "model":
        outcomes[0]["metadata"]["response_model"] = "forged"
        outcomes[0]["metadata_sha256"] = fingerprint(outcomes[0]["metadata"])
    elif mutation == "state":
        outcomes[1]["state_after"] = None
    elif mutation == "status":
        outcomes[0]["status"] = "invalid"
    elif mutation == "episode":
        plan["episodes"][0]["episode_id"] = "forged"
    elif mutation == "config":
        plan["config"]["model"] = "forged"
        plan["config_sha256"] = fingerprint(plan["config"])
    write_jsonl(output / "requests.jsonl", requests)
    write_jsonl(output / "outcomes.jsonl", outcomes)
    write_jsonl(output / "responses.jsonl", responses)
    write_json(output / "plan.json", plan)
    refresh_hashes(output)
    if mutation == "count":
        summary = json.loads((output / "summary.json").read_text())
        summary["accepted_decisions"] -= 1
        write_json(output / "summary.json", summary)
    with pytest.raises(ValueError):
        audit_collection(episodes, output)


def test_resume_uses_total_budget_and_preserves_invalid_completed_slot(config, episodes, tmp_path):
    first, first_calls = mock_client(config, raw_responses=["not JSON", "still invalid"])
    original = tmp_path / "original"
    collect_model(episodes, config, original, max_queries=2, client=first)
    original_hashes = {path.name: file_hash(path) for path in original.iterdir()}
    second, second_calls = mock_client(config)
    resumed = tmp_path / "resumed"
    summary = collect_model(
        episodes, config, resumed, max_queries=4, client=second, resume_from=original
    )
    assert len(first_calls) == len(second_calls) == 2
    assert summary["attempts_started"] == 4 and summary["invalid_decisions"] == 2
    assert read_jsonl(resumed / "responses.jsonl")[:2] == read_jsonl(original / "responses.jsonl")
    assert second_calls[0]["previous_state"] is None
    assert audit_collection(episodes, resumed)["completed_checkpoints"] == 4
    assert {path.name: file_hash(path) for path in original.iterdir()} == original_hashes


def test_resume_after_clean_crash_but_reject_inflight(config, episodes, tmp_path):
    client, _ = mock_client(config)
    output = tmp_path / "clean"
    collect_model(episodes, config, output, max_queries=2, client=client)
    summary = json.loads((output / "summary.json").read_text())
    summary["status"] = "running"
    summary.pop("artifact_sha256")
    write_json(output / "summary.json", summary)
    with pytest.raises(ValueError):
        audit_collection(episodes, output)
    assert audit_collection(episodes, output, allow_incomplete=True)["safe_to_resume"]
    continuation, calls = mock_client(config)
    collect_model(
        episodes,
        config,
        tmp_path / "continued",
        max_queries=3,
        client=continuation,
        resume_from=output,
    )
    assert len(calls) == 1
    outcomes = read_jsonl(output / "outcomes.jsonl")
    write_jsonl(output / "outcomes.jsonl", outcomes[:-1])
    summary["completions_received"] = summary["accepted_decisions"] = 1
    summary["unsubmitted_checkpoints"] = 9
    summary["reported_prompt_tokens"] = 10
    summary["reported_completion_tokens"] = 5
    write_json(output / "summary.json", summary)
    uncertain = audit_collection(episodes, output, allow_incomplete=True)
    assert not uncertain["safe_to_resume"]
    with pytest.raises(ValueError, match="uncertain|in.flight|resume"):
        collect_model(
            episodes,
            config,
            tmp_path / "unsafe",
            max_queries=3,
            client=continuation,
            resume_from=output,
        )
    assert not (tmp_path / "unsafe").exists()


def test_provider_error_is_auditable_but_not_resumed(config, episodes, tmp_path):
    client, _ = mock_client(config, failure_at=2)
    output = tmp_path / "failed"
    collect_model(episodes, config, output, max_queries=10, client=client)
    audit = audit_collection(episodes, output)
    assert audit["valid"] and not audit["safe_to_resume"]
    assert audit["counters"]["attempts_started"] == 2
    with pytest.raises(ValueError, match="resume"):
        collect_model(
            episodes, config, tmp_path / "retry", max_queries=10, client=client, resume_from=output
        )


@pytest.mark.parametrize(
    "name,value,status",
    [
        ("max_request_bytes", 1, "request_bytes_exceeded"),
        ("max_reserved_output_tokens", 0, "output_reservation_exhausted"),
        ("max_reserved_output_tokens", 2048, "output_reservation_exhausted"),
    ],
)
def test_presend_guards_keep_full_denominator(config, episodes, tmp_path, name, value, status):
    client, calls = mock_client(config)
    output = tmp_path / name
    summary = collect_model(
        episodes, config, output, max_queries=10, client=client, **{name: value}
    )
    expected = 2 if value == 2048 else 0
    assert len(calls) == summary["attempts_started"] == expected
    assert summary["status"] == status
    assert summary["unsubmitted_checkpoints"] == 10 - expected
    assert audit_collection(episodes, output)["safe_to_resume"]


@pytest.mark.parametrize("value", [-1, True, 1.5])
@pytest.mark.parametrize("name", ["max_request_bytes", "max_reserved_output_tokens"])
def test_guard_bad_config_rejected_before_output(config, episodes, tmp_path, value, name):
    with pytest.raises(ValueError):
        collect_model(episodes, config, tmp_path / "bad", max_queries=10, **{name: value})
    assert not (tmp_path / "bad").exists()


@pytest.mark.parametrize("method", ["snapshot", "answer_history", "structured_state"])
def test_resume_reconstructs_selected_method(config, episodes, tmp_path, method):
    client, calls = mock_client(config)
    original = tmp_path / "original"
    collect_model(episodes, config, original, max_queries=2, client=client, method=method)
    next_client, next_calls = mock_client(config)
    resumed = tmp_path / "resumed"
    collect_model(
        episodes,
        config,
        resumed,
        max_queries=3,
        client=next_client,
        method=method,
        resume_from=original,
    )
    audit = audit_collection(episodes, resumed)
    assert audit["method"] == method
    assert len(next_calls) == 1
    if method == "answer_history":
        assert len(next_calls[0]["answer_history"]) == 2
    elif method == "snapshot":
        assert "previous_state" not in next_calls[0]
    else:
        assert (
            next_calls[0]["previous_state"]
            == read_jsonl(original / "outcomes.jsonl")[-1]["state_after"]
        )


def test_changed_episode_contents_rejected(config, episodes, tmp_path):
    client, _ = mock_client(config)
    original = tmp_path / "original"
    collect_model(episodes, config, original, max_queries=2, client=client)
    changed = copy.deepcopy(episodes)
    changed.reverse()
    with pytest.raises(ValueError):
        audit_collection(changed, original)


def test_crash_during_attempt_is_never_reissued(config, episodes, tmp_path):
    from disastertrace.automated.provider import ProviderClient

    calls = []

    def interrupted_transport(*args):
        calls.append(1)
        raise KeyboardInterrupt()

    client = ProviderClient(config, transport=interrupted_transport)
    original = tmp_path / "crashed"
    with pytest.raises(KeyboardInterrupt):
        collect_model(episodes, config, original, max_queries=10, client=client)
    audit = audit_collection(episodes, original, allow_incomplete=True)
    assert audit["inflight_request"] and not audit["safe_to_resume"]
    assert audit["counters"]["attempts_started"] == 1
    with pytest.raises(ValueError, match="resume"):
        collect_model(
            episodes,
            config,
            tmp_path / "unsafe",
            max_queries=10,
            client=client,
            resume_from=original,
        )
    assert calls == [1]


def test_resume_rejects_shrunk_total_budget(config, episodes, tmp_path):
    client, calls = mock_client(config)
    original = tmp_path / "original"
    collect_model(episodes, config, original, max_queries=3, client=client)
    for kwargs in (
        {"max_queries": 2},
        {"max_queries": 5, "max_reserved_output_tokens": 2048},
        {"max_queries": 5, "max_request_bytes": 1},
    ):
        with pytest.raises(ValueError):
            collect_model(
                episodes, config, tmp_path / "unsafe", client=client, resume_from=original, **kwargs
            )
    assert len(calls) == 3


def test_audit_body_mutation_cannot_hide_behind_metadata_hash(config, episodes, tmp_path):
    client, _ = mock_client(config)
    original = tmp_path / "original"
    collect_model(episodes, config, original, max_queries=1, client=client)
    outcomes = read_jsonl(original / "outcomes.jsonl")
    body = json.loads(outcomes[0]["metadata"]["raw_response_body"])
    body["choices"][0]["message"]["content"] = "forged"
    outcomes[0]["metadata"]["raw_response_body"] = json.dumps(body)
    outcomes[0]["metadata_sha256"] = fingerprint(outcomes[0]["metadata"])
    write_jsonl(original / "outcomes.jsonl", outcomes)
    refresh_hashes(original)
    with pytest.raises(ValueError, match="body"):
        audit_collection(episodes, original)


def test_legacy_v1_collection_still_audits(config, episodes, tmp_path):
    client, _ = mock_client(config)
    original = tmp_path / "legacy"
    collect_model(episodes, config, original, max_queries=2, client=client)
    plan = json.loads((original / "plan.json").read_text())
    summary = json.loads((original / "summary.json").read_text())
    plan["schema_version"] = summary["schema_version"] = "provider_collection_v1"
    for name in ("method", "max_request_bytes", "max_reserved_output_tokens", "resume_from"):
        plan.pop(name)
    for row in plan["episodes"]:
        row.pop("episode_sha256")
    for name in ("reserved_output_tokens", "request_bytes_sent", "stop_guard"):
        summary.pop(name)
    write_json(original / "plan.json", plan)
    write_json(original / "summary.json", summary)
    refresh_hashes(original)
    assert audit_collection(episodes, original)["valid"]


def test_resume_copies_verified_rows_instead_of_rereading_mutated_source(
    config, episodes, tmp_path, monkeypatch
):
    from disastertrace.automated import collection

    client, _ = mock_client(config)
    original = tmp_path / "original"
    collect_model(episodes, config, original, max_queries=2, client=client)
    expected = read_jsonl(original / "responses.jsonl")

    def mutate_after_audit(*args, **kwargs):
        audit = audit_collection(*args, **kwargs)
        write_jsonl(
            original / "responses.jsonl",
            [{**row, "raw_response": "unverified mutation"} for row in expected],
        )
        return audit

    monkeypatch.setattr(collection, "audit_collection", mutate_after_audit)
    output = tmp_path / "resumed"
    collect_model(episodes, config, output, max_queries=3, client=client, resume_from=original)
    assert read_jsonl(output / "responses.jsonl")[:2] == expected
    assert audit_collection(episodes, output)["valid"]
