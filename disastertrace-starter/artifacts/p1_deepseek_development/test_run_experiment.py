"""Offline regression checks for the bounded P1 runner; no real HTTP requests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from run_experiment import (
    METHODS,
    BudgetedClient,
    BudgetLedger,
    run_experiment,
    validate_experiment,
)

from disastertrace.automated.common import canonical, file_hash, fingerprint, read_jsonl, write_json
from disastertrace.automated.dynamic import FIELDS, POLICY, diagnostic_response
from disastertrace.automated.evidence_support import EVIDENCE_POLICY_VERSION
from disastertrace.automated.provider import ProviderConfig, ProviderError
from disastertrace.automated.scoring_v2 import SCORER_VERSION
from disastertrace.automated.workflow import build, implementation_snapshot, selected_episodes

ROOT = Path(__file__).resolve().parents[2]
BUDGET = {
    "currency": "USD",
    "allowance": 1.0,
    "prompt_reservation_tokens": 1048576,
    "peak_input_per_million": 0.44,
    "peak_output_per_million": 1.32,
    "max_provider_requests": 90,
    "max_reserved_output_tokens": 368640,
    "max_request_bytes": 262144,
}


def configuration(**updates):
    values = {
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
        "key_env": "DEEPSEEK_API_KEY",
        "max_output_tokens": 4096,
        "token_parameter": "max_tokens",
        "temperature": None,
        "timeout": 60,
        "max_response_bytes": 1048576,
        "reasoning_effort": "high",
        "thinking_type": "enabled",
    }
    values.update(updates)
    return ProviderConfig.from_dict(values)


@pytest.fixture(autouse=True)
def offline_credentials_and_network(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "OFFLINE-TEST-CREDENTIAL")

    def forbidden(*args, **kwargs):
        pytest.fail("runner tests attempted actual network access")

    monkeypatch.setattr("disastertrace.automated.provider.urllib_transport", forbidden)


@pytest.fixture
def public_request():
    return {
        "protocol": "disastertrace_text_v1",
        "instruction": "Return the requested state and action as JSON.",
        "checkpoint_time": "2021-08-28T15:00:00+00:00",
        "required_fields": list(FIELDS),
        "policy": dict(POLICY),
        "evidence": [],
        "previous_state": None,
    }


def wire_response(request_body, *, usage="normal", model="deepseek-v4-flash", raw=None):
    public = json.loads(json.loads(request_body)["messages"][1]["content"])
    if raw is None:
        raw = diagnostic_response(public, "rule")
    body = {
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": raw},
                "finish_reason": "stop",
            }
        ],
    }
    if usage == "normal":
        usage = {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100}
    if usage is not None:
        body["usage"] = usage
    return 200, canonical(body).encode()


def client_fixture(tmp_path, *, budget=None, usage="normal", model="deepseek-v4-flash"):
    calls = []

    def transport(url, body, headers, timeout, max_response_bytes):
        calls.append(body)
        return wire_response(body, usage=usage, model=model)

    ledger = BudgetLedger(budget or BUDGET, tmp_path / "ledger.json", experiment_id="fixture")
    client = BudgetedClient(configuration(), ledger, method="snapshot", transport=transport)
    return client, ledger, calls


def test_reserve_full_context_then_release_to_conservative_actual(tmp_path, public_request):
    client, ledger, calls = client_fixture(tmp_path)
    observed = []
    original = client._transport

    def inspect_pending(*args):
        observed.append(json.loads((tmp_path / "ledger.json").read_text()))
        return original(*args)

    client._transport = inspect_pending
    completion = client.complete(public_request)
    assert len(calls) == 1
    assert observed[0]["pending_reservation_usd"] == 0.46678016
    assert ledger.snapshot()["pending_reservation_usd"] == 0
    assert ledger.snapshot()["conservative_reported_cost_usd"] == 0.000572
    assert completion["metadata"]["monetary_cap_enforced"] is False
    assert client.transport_kind == "injected_transport_with_external_budget_guard_unverified"


def test_monetary_guard_is_before_http_and_shared_between_methods(tmp_path, public_request):
    client, ledger, calls = client_fixture(
        tmp_path,
        budget={**BUDGET, "allowance": 0.5},
        usage={"prompt_tokens": 100000, "completion_tokens": 100, "total_tokens": 100100},
    )
    client.complete(public_request)
    second = BudgetedClient(
        configuration(), ledger, method="answer_history", transport=client._transport
    )
    with pytest.raises(ProviderError) as failure:
        second.complete(public_request)
    assert failure.value.code == "external_budget_allowance_exhausted"
    assert failure.value.request_may_have_reached_provider is False
    assert len(calls) == ledger.snapshot()["provider_attempts_started"] == 1
    assert ledger.snapshot()["guard_denials_before_provider"] == 1


@pytest.mark.parametrize(
    "limit,expected",
    [
        ({"max_provider_requests": 1}, "external_budget_request_limit"),
        ({"max_reserved_output_tokens": 4096}, "external_budget_output_reservation_limit"),
    ],
)
def test_global_request_and_output_guards(tmp_path, public_request, limit, expected):
    client, ledger, calls = client_fixture(tmp_path, budget={**BUDGET, **limit})
    client.complete(public_request)
    with pytest.raises(ProviderError, match=expected):
        client.complete(public_request)
    assert len(calls) == 1
    assert ledger.snapshot()["requested_output_tokens_reserved_total"] == 4096


def test_request_byte_guard_before_http(tmp_path, public_request):
    client, ledger, calls = client_fixture(tmp_path, budget={**BUDGET, "max_request_bytes": 1})
    with pytest.raises(ProviderError, match="external_budget_request_bytes"):
        client.complete(public_request)
    assert calls == []
    assert ledger.snapshot()["provider_attempts_started"] == 0


def test_missing_usage_preserves_completion_and_halts_without_release(tmp_path, public_request):
    client, ledger, calls = client_fixture(tmp_path, usage=None)
    received = client.complete(public_request)
    assert received["metadata"]["usage"] is None
    assert ledger.halted
    assert ledger.snapshot()["pending_reservation_usd"] == 0.46678016
    with pytest.raises(ProviderError, match="external_budget_halted"):
        client.complete(public_request)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "usage",
    [
        {"prompt_tokens": True, "completion_tokens": 1, "total_tokens": 2},
        {"prompt_tokens": -1, "completion_tokens": 1, "total_tokens": 0},
        {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 9},
    ],
)
def test_invalid_usage_keeps_reservation_and_stops(tmp_path, public_request, usage):
    client, ledger, calls = client_fixture(tmp_path, usage=usage)
    with pytest.raises(ProviderError, match="invalid_response_schema"):
        client.complete(public_request)
    assert ledger.halted
    assert len(calls) == 1
    assert ledger.snapshot()["pending_reservation_usd"] == 0.46678016


@pytest.mark.parametrize(
    "usage,reason",
    [
        (
            {"prompt_tokens": 1048577, "completion_tokens": 1, "total_tokens": 1048578},
            "reported_prompt_cap_exceeded",
        ),
        (
            {"prompt_tokens": 1, "completion_tokens": 4097, "total_tokens": 4098},
            "reported_output_cap_exceeded",
        ),
    ],
)
def test_reported_cap_violation_preserves_answer_and_halts(tmp_path, public_request, usage, reason):
    client, ledger, calls = client_fixture(tmp_path, usage=usage)
    received = client.complete(public_request)
    assert received["metadata"]["usage"] == usage
    assert ledger.snapshot()["halt_reason"] == reason
    assert ledger.snapshot()["conditional_budget_assumptions_satisfied"] is False
    assert len(calls) == 1


@pytest.mark.parametrize("usage", ["normal", None])
def test_reported_model_drift_preserves_answer_and_halts(tmp_path, public_request, usage):
    client, ledger, calls = client_fixture(tmp_path, model="different-model", usage=usage)
    received = client.complete(public_request)
    assert received["metadata"]["response_model"] == "different-model"
    assert ledger.snapshot()["halt_reason"] == (
        "reported_model_mismatch" if usage is not None else "missing_usage"
    )
    assert ledger.snapshot()["conditional_budget_assumptions_satisfied"] is False
    assert ledger.snapshot()["pending_reservation_usd"] == 0.46678016
    assert ledger.snapshot()["conservative_reported_cost_usd"] == 0
    assert ledger.snapshot()["attempts"][0].get("conservative_reported_cost_usd") is None
    assert len(calls) == 1


@pytest.mark.parametrize("failure", ["timeout", "http_error"])
def test_uncertain_provider_failure_keeps_reservation(tmp_path, public_request, failure):
    client, ledger, calls = client_fixture(tmp_path)

    def transport(*args):
        calls.append("attempt")
        if failure == "timeout":
            raise TimeoutError("must not persist exception text")
        return 500, b""

    client._transport = transport
    with pytest.raises(ProviderError):
        client.complete(public_request)
    assert ledger.halted
    assert ledger.snapshot()["pending_reservation_usd"] == 0.46678016
    assert "must not persist" not in (tmp_path / "ledger.json").read_text()
    assert len(calls) == 1


def test_missing_credential_does_not_reserve_or_dispatch(tmp_path, public_request, monkeypatch):
    client, ledger, calls = client_fixture(tmp_path)
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    with pytest.raises(ProviderError, match="missing_credential"):
        client.complete(public_request)
    assert len(calls) == ledger.snapshot()["provider_attempts_started"] == 0
    assert ledger.snapshot()["pending_reservation_usd"] == 0


def test_reentrant_reservation_is_rejected(tmp_path, public_request):
    client, ledger, calls = client_fixture(tmp_path)
    ledger.reserve(client.prepare(public_request), "snapshot", client.config)
    with pytest.raises(ProviderError, match="external_budget_pending_attempt"):
        client.complete(public_request)
    assert calls == []


@pytest.fixture(scope="module")
def frozen_build(tmp_path_factory):
    output = tmp_path_factory.mktemp("p1-offline-build") / "build"
    references = ROOT.parent / "references"
    build(references, output, nhc_snapshot=references / "nhc_cohort_v1")
    return output


def manifest_fixture(tmp_path, frozen_build):
    from dataclasses import asdict

    config = tmp_path / "config.json"
    rates = tmp_path / "rates.json"
    write_json(config, asdict(configuration()))
    write_json(rates, {"fixture": "OFFLINE_ONLY", "budget": BUDGET})
    episodes = selected_episodes(frozen_build, "development")
    checkpoints = [
        {"episode_id": ep["episode_id"], "checkpoint_id": cp["checkpoint_id"]}
        for ep in episodes
        for cp in ep["checkpoints"]
    ]
    manifest = {
        "schema_version": "p1_deepseek_development_experiment_v1",
        "methods": list(METHODS),
        "development_event_ids": list(dict.fromkeys(ep["group_id"] for ep in episodes)),
        "expected_requests_per_method": 30,
        "repeats": 1,
        "total_requests": 90,
        "build_path": str(frozen_build),
        "build_id": json.loads((frozen_build / "manifest.json").read_text())["build_id"],
        "implementation_id": implementation_snapshot()["implementation_id"],
        "provider_config_path": str(config),
        "provider_config_sha256": file_hash(config),
        "rates_path": str(rates),
        "rates_sha256": file_hash(rates),
        "budget": copy.deepcopy(BUDGET),
        "runner_sha256": file_hash(Path(__file__).with_name("run_experiment.py")),
        "scorer_version": SCORER_VERSION,
        "evidence_policy_version": EVIDENCE_POLICY_VERSION,
        "expected_checkpointkeys_sha256": fingerprint(checkpoints),
    }
    manifest["experiment_id"] = fingerprint(manifest)
    path = tmp_path / "experiment.json"
    write_json(path, manifest)
    return path, manifest


def test_valid_manifest_and_existing_output_guard(tmp_path, frozen_build):
    path, manifest = manifest_fixture(tmp_path, frozen_build)
    checked, _, episodes = validate_experiment(path)
    assert checked == manifest
    assert len(episodes) == 6
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("preserve")
    with pytest.raises(ValueError, match="output exists"):
        run_experiment(path, output)
    assert list(output.iterdir()) == [marker]
    assert marker.read_text() == "preserve"


@pytest.mark.parametrize(
    "field,value",
    [
        ("methods", ["snapshot", "answer_history", "structured_state"]),
        ("repeats", 2),
        ("total_requests", 91),
        ("development_event_ids", ["AL092021"]),
        ("build_id", "wrong"),
        ("implementation_id", "wrong"),
        ("runner_sha256", "wrong"),
        ("provider_config_sha256", "wrong"),
        ("rates_sha256", "wrong"),
        ("scorer_version", "wrong"),
        ("evidence_policy_version", "wrong"),
        ("expected_checkpointkeys_sha256", "wrong"),
    ],
)
def test_rejects_changed_manifest_constraints(tmp_path, frozen_build, field, value):
    path, manifest = manifest_fixture(tmp_path, frozen_build)
    manifest[field] = value
    manifest["experiment_id"] = fingerprint(
        {k: v for k, v in manifest.items() if k != "experiment_id"}
    )
    write_json(path, manifest)
    with pytest.raises(ValueError):
        validate_experiment(path)


def test_rejects_manifest_fingerprint_tampering(tmp_path, frozen_build):
    path, manifest = manifest_fixture(tmp_path, frozen_build)
    manifest["comment"] = "unbound edit"
    write_json(path, manifest)
    with pytest.raises(ValueError, match="fingerprint"):
        validate_experiment(path)


def test_rejects_rehashed_manifest_edit_between_methods(tmp_path, frozen_build):
    path, manifest = manifest_fixture(tmp_path, frozen_build)
    calls = []

    def transport(url, body, headers, timeout, max_response_bytes):
        calls.append(body)
        if len(calls) == 1:
            changed = {key: value for key, value in manifest.items() if key != "experiment_id"}
            changed["comment"] = "Changed after execution started"
            changed["experiment_id"] = fingerprint(changed)
            write_json(path, changed)
        return wire_response(body)

    output = tmp_path / "changed-manifest-output"
    with pytest.raises(ValueError, match="experiment inputs changed"):
        run_experiment(path, output, transport=transport)
    assert len(calls) == 30
    assert not (output / "runs/structured_state").exists()
    assert json.loads((output / "execution.json").read_text())["status"] == "failed"


@pytest.mark.parametrize(
    "stop_mode", [None, "missing_usage", "model_drift", "output_cap", "missing_usage_at_30"]
)
def test_full_audited_matrix_or_scored_missing_remainder(tmp_path, frozen_build, stop_mode):
    path, manifest = manifest_fixture(tmp_path, frozen_build)
    calls = []

    def transport(url, body, headers, timeout, max_response_bytes):
        calls.append(json.loads(json.loads(body)["messages"][1]["content"]))
        updates = {}
        if len(calls) == 30 and stop_mode == "missing_usage_at_30":
            updates["usage"] = None
        if len(calls) == 1:
            if stop_mode == "missing_usage":
                updates["usage"] = None
            elif stop_mode == "model_drift":
                updates["model"] = "unexpected-model"
            elif stop_mode == "output_cap":
                updates["usage"] = {
                    "prompt_tokens": 1,
                    "completion_tokens": 4097,
                    "total_tokens": 4098,
                }
        # A malformed answer is preserved and not repaired or retried.
        if len(calls) == 2 and stop_mode is None:
            updates["raw"] = "INVALID OFFLINE FIXTURE"
        return wire_response(body, **updates)

    output = tmp_path / "experiment-output"
    execution = run_experiment(path, output, transport=transport)
    expected_calls = 90 if stop_mode is None else 30 if stop_mode == "missing_usage_at_30" else 1
    assert len(calls) == expected_calls
    assert execution["status"] == ("completed" if stop_mode is None else "stopped")
    assert execution["provider_attempts_started"] == len(calls)
    assert execution["planned_checkpoints_total"] == 90
    assert [item["method"] for item in execution["methods"]] == list(METHODS)
    for method in METHODS:
        score = json.loads((output / "rescores" / method / "score_v2.json").read_text())
        assert score["metrics"]["schema_success"]["denominator"] == 30
        assert score["metrics"]["known_grounded_accuracy"]["denominator"] == 96
        run = output / "runs" / method
        assert (run / "collection_audit.json").is_file()
        trace = read_jsonl(run / "imported_run/trace.jsonl")
        assert len(trace) == 30
        assert all(row["provider_requests"] == 0 for row in trace)
    if stop_mode:
        assert (
            len(read_jsonl(output / "runs/snapshot/collection/responses.jsonl")) == expected_calls
        )
        assert (
            json.loads((output / "runs/structured_state/collection/summary.json").read_text())[
                "attempts_started"
            ]
            == 0
        )
    else:
        assert (
            read_jsonl(output / "runs/snapshot/collection/responses.jsonl")[1]["raw_response"]
            == "INVALID OFFLINE FIXTURE"
        )
        assert "previous_state" not in calls[0]
        assert calls[30]["previous_state"] is None
        assert calls[60]["answer_history"] == []
    for file in output.rglob("*"):
        if file.is_file() and file.suffix in {".json", ".jsonl"}:
            assert "OFFLINE-TEST-CREDENTIAL" not in file.read_text()
