from __future__ import annotations

import copy
import json

import pytest

from disastertrace.automated.collection import collect_model
from disastertrace.automated.common import canonical, file_hash, read_jsonl
from disastertrace.automated.dynamic import FIELDS, build_episodes, diagnostic_response
from disastertrace.automated.provider import ProviderClient, ProviderConfig


@pytest.fixture
def config():
    return ProviderConfig(
        model="MOCK-NO-MODEL-CALLS",
        base_url="http://127.0.0.1:8000/v1",
        key_env=None,
        max_output_tokens=1024,
        token_parameter="max_tokens",
        temperature=0,
        timeout=5,
        max_response_bytes=65536,
    )


@pytest.fixture
def episodes():
    records = []
    for index, wind in enumerate([85, 105, 115], 1):
        text = f"SYNTHETIC TEST REPORT\nLOCATION...24.5N 85.3W\nMAXIMUM SUSTAINED WINDS...{wind} MPH\nMINIMUM CENTRAL PRESSURE...970 MB"
        lines = text.splitlines()
        locators = {
            "maximum_wind_mph": 3,
            "latitude_deg": 2,
            "longitude_deg": 2,
            "minimum_pressure_mb": 4,
        }
        records.append(
            {
                "record_id": f"synthetic-collection-{index}",
                "storm_id": "SYNTHETIC_COLLECTION",
                "issued_at": f"2040-08-01T{index * 6:02d}:00:00Z",
                "raw_text": text,
                "fields": {
                    "maximum_wind_mph": wind,
                    "latitude_deg": 24.5,
                    "longitude_deg": -85.3,
                    "minimum_pressure_mb": 970,
                },
                "field_evidence": {
                    field: {"line_start": line, "line_end": line, "text": lines[line - 1]}
                    for field, line in locators.items()
                },
                "provenance": {"source_origin": "synthetic_record", "historical_claim": False},
            }
        )
    return build_episodes(records)


def mock_client(config, raw_responses=None, failure_at=None, output=None):
    calls = []

    def transport(url, body, headers, timeout, maximum):
        public = json.loads(json.loads(body)["messages"][1]["content"])
        calls.append(public)
        if output is not None:
            requests = read_jsonl(output / "requests.jsonl")
            assert len(requests) == len(calls)
            assert requests[-1]["public_request"] == public
        if failure_at == len(calls):
            return 429, b"SECRET FROM SERVER MUST NOT BE LOGGED"
        raw = (
            raw_responses[len(calls) - 1]
            if raw_responses is not None
            else diagnostic_response(public, "rule")
        )
        return 200, canonical(
            {
                "model": "MOCK-NO-MODEL-CALLS",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": raw},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        ).encode()

    client = ProviderClient(config, transport=transport)
    return client, calls


def test_collection_full_fresh_requests_and_submission_format(config, episodes, tmp_path):
    output = tmp_path / "collection"
    client, calls = mock_client(config, output=output)
    summary = collect_model(episodes, config, output, max_queries=10, client=client)
    assert summary["status"] == "completed"
    assert summary["attempts_started"] == summary["completions_received"] == 10
    assert summary["accepted_decisions"] == 10 and summary["invalid_decisions"] == 0
    assert summary["transport_kind"] == "injected_transport_unverified"
    assert summary["reported_prompt_tokens"] == 100
    assert summary["reported_completion_tokens"] == 50
    assert calls[0]["previous_state"] is None and calls[5]["previous_state"] is None
    assert calls[1]["previous_state"]["action"] == "request_evidence"
    responses = read_jsonl(output / "responses.jsonl")
    assert all(set(row) == {"episode_id", "checkpoint_id", "raw_response"} for row in responses)
    assert all(
        "private_references" not in canonical(call) and "checkpoints" not in call for call in calls
    )
    assert "synthetic-collection-3" not in canonical(calls[1])
    for name, digest in summary["artifact_sha256"].items():
        assert file_hash(output / name) == digest
    plan = json.loads((output / "plan.json").read_text())
    assert len(plan["episodes"]) == 2 and len(plan["checkpoints"]) == 10


def test_wrong_but_valid_state_is_carried_and_invalid_state_preserves_it(
    config, episodes, tmp_path
):
    wrong = {
        "state": {field: {"status": "unknown", "value": None, "evidence": []} for field in FIELDS},
        "action": "prepare",
    }
    client, calls = mock_client(
        config, raw_responses=[canonical(wrong), "invalid JSON", canonical(wrong)]
    )
    summary = collect_model(episodes, config, tmp_path / "carrier", max_queries=3, client=client)
    assert summary["status"] == "budget_exhausted"
    assert summary["accepted_decisions"] == 2 and summary["invalid_decisions"] == 1
    assert calls[1]["previous_state"] == wrong
    assert calls[2]["previous_state"] == wrong
    outcomes = read_jsonl(tmp_path / "carrier" / "outcomes.jsonl")
    assert outcomes[1]["status"] == "invalid" and outcomes[1]["state_after"] == wrong


def test_failure_stops_and_preserves_partial_records(config, episodes, tmp_path):
    client, calls = mock_client(config, failure_at=3)
    output = tmp_path / "partial"
    summary = collect_model(episodes, config, output, max_queries=10, client=client)
    assert len(calls) == summary["attempts_started"] == 3
    assert summary["completions_received"] == 2
    assert summary["unsubmitted_checkpoints"] == 8
    assert summary["status"] == "provider_error"
    assert summary["stop_error"]["code"] == "rate_limited"
    assert len(read_jsonl(output / "requests.jsonl")) == 3
    assert len(read_jsonl(output / "responses.jsonl")) == 2
    assert read_jsonl(output / "outcomes.jsonl")[-1]["status"] == "provider_error"
    assert "SECRET" not in "".join(path.read_text() for path in output.iterdir())


@pytest.mark.parametrize(
    "budget,expected_status,attempts",
    [
        (0, "budget_exhausted", 0),
        (1, "budget_exhausted", 1),
        (6, "budget_exhausted", 6),
        (10, "completed", 10),
        (11, "completed", 10),
    ],
)
def test_budget_is_global_and_no_extra_attempt(
    config, episodes, tmp_path, budget, expected_status, attempts
):
    client, calls = mock_client(config)
    summary = collect_model(
        episodes, config, tmp_path / "budget", max_queries=budget, client=client
    )
    assert len(calls) == summary["attempts_started"] == attempts
    assert summary["status"] == expected_status


def test_outputs_are_not_overwritten(config, episodes, tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    (output / "sentinel").write_text("preserve")
    client, calls = mock_client(config)
    with pytest.raises(FileExistsError):
        collect_model(episodes, config, output, max_queries=10, client=client)
    assert calls == [] and (output / "sentinel").read_text() == "preserve"


@pytest.mark.parametrize("budget", [-1, True, 1.5])
def test_bad_budget_rejected_before_artifacts(config, episodes, tmp_path, budget):
    with pytest.raises(ValueError):
        collect_model(episodes, config, tmp_path / "invalid", max_queries=budget)
    assert not (tmp_path / "invalid").exists()


def test_empty_or_duplicate_episodes_rejected(config, episodes, tmp_path):
    for sample in ([], [episodes[0], copy.deepcopy(episodes[0])]):
        with pytest.raises(ValueError):
            collect_model(sample, config, tmp_path / "invalid", max_queries=1)
    assert not (tmp_path / "invalid").exists()


def test_missing_credential_is_a_recorded_attempt_without_transport(
    config, episodes, tmp_path, monkeypatch
):
    hosted = ProviderConfig(
        model=config.model,
        base_url="https://example.invalid/v1",
        key_env="ABSENT_COLLECTION_KEY",
        max_output_tokens=128,
        token_parameter="max_tokens",
        temperature=None,
        timeout=5,
        max_response_bytes=65536,
    )
    monkeypatch.delenv("ABSENT_COLLECTION_KEY", raising=False)
    client, calls = mock_client(hosted)
    summary = collect_model(
        episodes, hosted, tmp_path / "missing-key", max_queries=10, client=client
    )
    assert calls == [] and summary["attempts_started"] == 1
    assert summary["stop_error"]["code"] == "missing_credential"
    assert summary["stop_error"]["request_may_have_reached_provider"] is False


def test_mutated_metadata_is_not_silently_accepted(config, episodes, tmp_path):
    class TamperedClient(ProviderClient):
        def complete(self, public_request):
            return {"raw_response": "{}", "metadata": {"request_sha256": "wrong"}}

    client = TamperedClient(config, transport=lambda *args: None)
    summary = collect_model(episodes, config, tmp_path / "tamper", max_queries=2, client=client)
    assert summary["stop_error"]["code"] == "collection_metadata_mismatch"
    assert summary["completions_received"] == 0
