"""Offline restart regressions; actual HTTP and credential prompts are forbidden."""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from disastertrace.automated.collection_audit import audit_collection
from disastertrace.automated.common import canonical, file_hash, fingerprint, read_jsonl, write_json
from disastertrace.automated.dynamic import diagnostic_response
from disastertrace.automated.provider import ProviderClient, ProviderError

SPEC = importlib.util.spec_from_file_location(
    "background_resume_tests", Path(__file__).with_name("resume_background.py")
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ROOT = MODULE.ROOT
EXPERIMENT = ROOT / "artifacts/p1_deepseek_development/experiment.json"
SOURCE = ROOT / "work/p1-deepseek-development-v1"


@pytest.fixture(autouse=True)
def forbid_network_and_credentials(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "OFFLINE-TEST-CREDENTIAL")

    def forbidden(*args, **kwargs):
        raise AssertionError("offline tests must not use HTTP or credential prompts")

    monkeypatch.setattr("disastertrace.automated.provider.urllib_transport", forbidden)
    monkeypatch.setattr(MODULE.getpass, "getpass", forbidden)


@pytest.fixture
def frozen():
    return MODULE.FROZEN.validate_experiment(EXPERIMENT)


@pytest.fixture
def prepared(tmp_path):
    output = tmp_path / "prepared"
    amendment = MODULE.prepare(EXPERIMENT, SOURCE, output)
    return output / "amendment.json", amendment


def authorization(amendment):
    return {
        "authorized": True,
        "original_experiment_id": amendment["original_experiment_id"],
        "amendment_id": amendment["amendment_id"],
        "allowance_usd": "1.5",
        "max_additional_provider_attempts": 12,
        "max_cumulative_provider_attempts": 91,
        "explicit_retry_original_attempt": 79,
        "user_message": "OFFLINE TEST APPROVAL FIXTURE; no real execution",
    }


def transport_response(body, *, raw=None, usage="normal"):
    public = json.loads(json.loads(body)["messages"][1]["content"])
    envelope = {
        "model": "deepseek-v4-flash",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": raw if raw is not None else diagnostic_response(public, "rule"),
                },
                "finish_reason": "stop",
            }
        ],
    }
    if usage == "normal":
        usage = {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100}
    if usage is not None:
        envelope["usage"] = usage
    return 200, canonical(envelope).encode()


def test_prepare_is_offline_preserves_original_and_all_received_answers(
    tmp_path, frozen, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError("preparation must never invoke complete")

    monkeypatch.setattr(ProviderClient, "complete", forbidden)
    before = MODULE.inventory(SOURCE)
    amendment = MODULE.prepare(EXPERIMENT, SOURCE, tmp_path / "prepared")
    _, _, episodes = frozen
    prefix = audit_collection(episodes, tmp_path / "prepared/prefix", allow_incomplete=True)
    assert prefix["safe_to_resume"] and not prefix["inflight_request"]
    assert prefix["counters"]["attempts_started"] == 18
    assert prefix["counters"]["completions_received"] == 18
    assert prefix["counters"]["invalid_decisions"] == 4
    assert prefix["counters"]["unsubmitted_checkpoints"] == 12
    for name in ("plan.json", "responses.jsonl", "outcomes.jsonl"):
        assert (tmp_path / "prepared/prefix" / name).read_bytes() == (
            SOURCE / "runs/answer_history/collection" / name
        ).read_bytes()
    assert MODULE.inventory(SOURCE) == before
    proof = MODULE.read_object(tmp_path / "prepared/prefix_provenance.json")
    assert proof["original_counters"]["attempts_started"] == 19
    assert proof["retained_original_global_attempt"]["attempt_number"] == 79
    assert amendment["new_api_calls_during_preparation"] == 0
    assert amendment["budget"]["max_provider_requests"] == 91


@pytest.mark.parametrize(
    "name",
    [
        "prefix/requests.jsonl",
        "prefix/outcomes.jsonl",
        "prefix/responses.jsonl",
        "prefix_provenance.json",
    ],
)
def test_changed_prefix_or_provenance_rejected(prepared, name):
    path, _ = prepared
    with (path.parent / name).open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(ValueError, match="prefix or provenance"):
        MODULE.validate_amendment(path)


def test_forged_amendment_scope_rejected(prepared):
    path, amendment = prepared
    amendment["budget"]["allowance"] = 2
    amendment["amendment_id"] = fingerprint(
        {k: v for k, v in amendment.items() if k != "amendment_id"}
    )
    write_json(path, amendment)
    with pytest.raises(ValueError, match="scope"):
        MODULE.validate_amendment(path)


@pytest.mark.parametrize("mutation", ["released", "wrong_request", "wrong_cost", "orphan_response"])
def test_invalid_original_cannot_be_sanitized_into_prefix(tmp_path, frozen, mutation):
    source = tmp_path / "source"
    shutil.copytree(SOURCE, source)
    ledger = MODULE.read_object(source / "budget_ledger.json")
    if mutation == "released":
        ledger["attempts"][-1]["reservation_released"] = True
    elif mutation == "wrong_request":
        ledger["attempts"][-1]["request_sha256"] = "0" * 64
    elif mutation == "wrong_cost":
        ledger["conservative_reported_cost_usd"] = 0
    else:
        response_path = source / "runs/answer_history/collection/responses.jsonl"
        orphan = read_jsonl(response_path)[-1]
        orphan["checkpoint_id"] = "c3"
        with response_path.open("a", encoding="utf-8") as stream:
            stream.write(canonical(orphan) + "\n")
    write_json(source / "budget_ledger.json", ledger)
    with pytest.raises(ValueError):
        MODULE.derive_prefix(source, tmp_path / "derived", frozen[2])
    assert not (tmp_path / "derived").exists()


def test_old_pending_is_retained_after_new_completion_and_request_92_denied(
    tmp_path, frozen, monkeypatch
):
    _, config, episodes = frozen
    old, audit = MODULE.validate_original(SOURCE, episodes)
    amendment = {
        "amendment_id": "offline",
        "original_experiment_id": old["experiment_id"],
        "explicit_retry_request_sha256": old["attempts"][-1]["request_sha256"],
    }
    saved = []
    original_write = MODULE.FROZEN.write_json

    def observe_write(path, value):
        saved.append(copy.deepcopy(value))
        original_write(path, value)

    monkeypatch.setattr(MODULE.FROZEN, "write_json", observe_write)
    ledger = MODULE.ContinuationLedger(old, tmp_path / "ledger.json", amendment)
    assert len(saved) == 1
    assert saved[0]["provider_attempts_started"] == 79
    assert saved[0]["pending_reservation_usd"] == 0.46678016
    prepared = copy.deepcopy(audit["verified_requests"][-1]["prepared"])
    for index in range(12):
        if index:
            prepared["request_sha256"] = fingerprint({"offline_request": index})
        attempt = ledger.reserve(prepared, "answer_history", config)
        assert attempt == 80 + index
        assert ledger.pending == Decimal("0.93356032")
        ledger.record_completion(
            attempt,
            {
                "raw_response": "fixture",
                "metadata": {
                    "response_model": config.model,
                    "elapsed_seconds": 0.1,
                    "usage": {
                        "prompt_tokens": 1000,
                        "completion_tokens": 100,
                        "total_tokens": 1100,
                    },
                },
            },
            config,
        )
        assert ledger.pending == Decimal("0.46678016")
    assert len(ledger.rows) == 91
    assert ledger.reserved_output_total == 372736
    assert ledger.rows[:79] == old["attempts"]
    prepared["request_sha256"] = fingerprint("attempt92")
    with pytest.raises(ProviderError, match="external_budget_request_limit"):
        ledger.reserve(prepared, "answer_history", config)
    assert len(ledger.rows) == 91


def test_first_retry_must_match_uncertain_request_before_admission(tmp_path, frozen):
    old, audit = MODULE.validate_original(SOURCE, frozen[2])
    amendment = {
        "amendment_id": "offline",
        "original_experiment_id": old["experiment_id"],
        "explicit_retry_request_sha256": old["attempts"][-1]["request_sha256"],
    }
    ledger = MODULE.ContinuationLedger(old, tmp_path / "ledger.json", amendment)
    prepared = copy.deepcopy(audit["verified_requests"][-1]["prepared"])
    prepared["request_sha256"] = "0" * 64
    with pytest.raises(ProviderError, match="explicit_retry_request_mismatch"):
        ledger.reserve(prepared, "answer_history", frozen[1])
    assert len(ledger.rows) == 79
    assert ledger.pending == Decimal("0.46678016")


def test_full_offline_continuation_only_12_new_calls_and_30_scoring_slots(prepared, tmp_path):
    path, amendment = prepared
    calls = []

    def transport(url, body, headers, timeout, max_response_bytes):
        calls.append(body)
        return transport_response(body, raw="invalid benchmark answer" if len(calls) == 2 else None)

    output = tmp_path / "run"
    output.mkdir()
    result = MODULE.execute(path, output, transport=transport)
    assert result["status"] == "completed"
    assert result["injected_offline_transport"]
    assert result["new_provider_attempts"] == len(calls) == 12
    assert result["cumulative_provider_attempts"] == 91
    assert result["cumulative_completions_received"] == 90
    assert result["actual_total_cost_usd"] is None
    requests = read_jsonl(output / "runs/answer_history/collection/requests.jsonl")
    outcomes = read_jsonl(output / "runs/answer_history/collection/outcomes.jsonl")
    original_outcomes = read_jsonl(SOURCE / "runs/answer_history/collection/outcomes.jsonl")
    assert outcomes[:18] == original_outcomes
    assert requests[18]["prepared"]["request_sha256"] == amendment["explicit_retry_request_sha256"]
    assert len(outcomes) == len(requests) == 30
    assert result["collection"]["invalid_decisions"] == 5
    assert (
        MODULE.read_object(output / "runs/answer_history/score.json")["metrics"]["schema_success"][
            "denominator"
        ]
        == 30
    )
    ledger = MODULE.read_object(output / "budget_ledger.json")
    assert ledger["pending_reservation_usd"] == 0.46678016
    assert ledger["active_attempt"] is None
    assert ledger["attempts"][78]["status"] == "pending"
    assert ledger["attempts"][79]["request_sha256"] == ledger["attempts"][78]["request_sha256"]
    dorian_c0 = [
        row
        for row in requests
        if row["episode_id"].startswith("al052019") and row["checkpoint_id"] == "c0"
    ]
    assert len(dorian_c0) == 2
    assert dorian_c0[0]["prepared"]["request_sha256"] == dorian_c0[1]["prepared"]["request_sha256"]


def test_uncertain_new_failure_halts_without_retry(prepared, tmp_path):
    path, _ = prepared
    calls = []

    def transport(*args):
        calls.append(1)
        raise TimeoutError("offline injected timeout")

    output = tmp_path / "run"
    output.mkdir()
    result = MODULE.execute(path, output, transport=transport)
    assert result["status"] == "stopped"
    assert len(calls) == result["new_provider_attempts"] == 1
    ledger = MODULE.read_object(output / "budget_ledger.json")
    assert ledger["pending_reservation_usd"] == 0.93356032
    assert ledger["halted"]
    assert result["collection"]["completions_received"] == 18
    assert result["full_three_method_scoring_opportunities"] == 90


@pytest.mark.parametrize(
    "field,value",
    [
        ("authorized", False),
        ("allowance_usd", "1.0"),
        ("explicit_retry_original_attempt", 78),
        ("max_cumulative_provider_attempts", 90),
        ("user_message", ""),
    ],
)
def test_launch_requires_matching_explicit_authorization(prepared, tmp_path, field, value):
    path, amendment = prepared
    auth = authorization(amendment)
    auth[field] = value
    auth_path = tmp_path / "authorization.json"
    write_json(auth_path, auth)
    with pytest.raises(ValueError, match="authorization"):
        MODULE.launch(path, auth_path, tmp_path / "run")
    assert not (tmp_path / "run").exists()


def test_detached_launch_uses_memory_credential_and_durable_records(
    prepared, tmp_path, monkeypatch
):
    path, amendment = prepared
    auth_path = tmp_path / "authorization.json"
    write_json(auth_path, authorization(amendment))
    captured = {}

    def fake_popen(args, **kwargs):
        captured.update(args=args, kwargs={**kwargs, "env": dict(kwargs["env"])})
        return type("OfflineProcess", (), {"pid": 12345})()

    monkeypatch.setattr(MODULE.subprocess, "Popen", fake_popen)
    result = MODULE.launch(path, auth_path, tmp_path / "run")
    assert result["pid"] == 12345
    assert captured["kwargs"]["start_new_session"] is True
    assert captured["kwargs"]["stdin"] == MODULE.subprocess.DEVNULL
    assert captured["kwargs"]["env"]["DEEPSEEK_API_KEY"] == "OFFLINE-TEST-CREDENTIAL"
    assert "OFFLINE-TEST-CREDENTIAL" not in str(captured["args"])
    for child in (tmp_path / "run").iterdir():
        assert b"OFFLINE-TEST-CREDENTIAL" not in child.read_bytes()
    assert result["authorization_sha256"] == file_hash(auth_path)
    with pytest.raises(ValueError, match="automatic relaunch"):
        MODULE.launch(path, auth_path, tmp_path / "run")
    with pytest.raises(ValueError, match="amendment already claimed"):
        MODULE.launch(path, auth_path, tmp_path / "other-run")
    assert not (tmp_path / "other-run").exists()


def test_copied_amendment_cannot_obtain_second_claim(prepared, tmp_path):
    path, _ = prepared
    moved = tmp_path / "copied"
    shutil.copytree(path.parent, moved)
    with pytest.raises(ValueError, match="bound prepared package location"):
        MODULE.validate_amendment(moved / "amendment.json")


def test_worker_persists_sanitized_exit_status_even_on_error(prepared, tmp_path, monkeypatch):
    path, _ = prepared
    output = tmp_path / "run"
    output.mkdir()

    def fail(*args, **kwargs):
        raise RuntimeError("OFFLINE-TEST-CREDENTIAL must not reach durable logs")

    monkeypatch.setattr(MODULE, "validate_amendment", fail)
    assert MODULE.worker(path, output) == 1
    assert MODULE.read_object(output / "status.json")["error_type"] == "RuntimeError"
    assert MODULE.read_object(output / "exit.json")["exit_code"] == 1
    for child in output.iterdir():
        assert b"OFFLINE-TEST-CREDENTIAL" not in child.read_bytes()
    with pytest.raises(FileExistsError):
        MODULE.worker(path, output)
