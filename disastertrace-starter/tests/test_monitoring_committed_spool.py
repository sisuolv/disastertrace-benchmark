"""Workers cannot consume staged model requests before controller durability."""

import hashlib

import pytest
from test_monitoring_typed_session import typed_fixture

from disastertrace.monitoring_v1.execution import PendingExecution
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.spool_backend import CommittedSpoolBackend, digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash


@pytest.fixture
def staged(tmp_path):
    spec = {
        "model": "engineering_fixture",
        "weights": "none",
        "tokenizer": "none",
        "adapter": "test",
        "generation": {},
        "runtime": {},
    }
    spool = tmp_path / "spool"
    spool.mkdir()
    backend = CommittedSpoolBackend(spool, spec, run_id="committed-fixture")
    data, bank, config = typed_fixture(forecast_call_cap=1, model_call_budget=1)
    session = SessionCoordinator(data, bank, config, backend=backend)
    session.step()
    checkpoint = session.snapshot()
    pending = checkpoint["payload"]["pending_predictor"]
    return session, backend, pending, data, bank


def response(backend, pending, raw='{"fact_truth":"unknown","probability":0.2}'):
    key, call = pending["ticket"]["remote_id"], pending["call_id"]
    payload = {
        "call_id": call,
        "request_sha256": pending["ticket"]["request_sha256"],
        "execution_sha256": canonical_hash(backend.execution_contract),
        "raw": raw,
        "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "input_tokens": 10,
        "output_tokens": 10,
        "compute_seconds": 0.001,
        "ended_with_eos": True,
    }
    worker = backend.directory / (key + ".worker.json")
    publish(worker, {**payload, "origin": "synthetic transport test"})
    publish(
        backend.directory / (key + ".response.json"),
        {
            **payload,
            "schema": "disastertrace.spool_response.v1",
            "worker_receipt_sha256": digest(worker),
        },
    )


def test_worker_cannot_claim_before_checkpoint_is_durable(staged, tmp_path):
    session, backend, pending, _, _ = staged
    with pytest.raises(PendingExecution):
        backend.claim_ready(pending["call_id"], worker_id="worker")
    assert not list(backend.directory.glob("*.claim.json"))
    original = session.snapshot()
    session.step()
    assert session.snapshot() == original
    path = tmp_path / "checkpoint.json"
    session.persist(path)
    assert read(path) == original
    claimed = backend.claim_ready(pending["call_id"], worker_id="worker")
    assert claimed["call_id"] == pending["call_id"]
    ready = read(next(backend.directory.glob("*.ready.json")))
    assert ready["checkpoint_file_sha256"] == digest(path)


def test_repeated_commit_is_idempotent_but_worker_claim_is_once(staged, tmp_path):
    session, backend, pending, _, _ = staged
    session.persist(tmp_path / "checkpoint.json")
    session.persist(tmp_path / "checkpoint.json")
    backend.claim_ready(pending["call_id"], worker_id="worker-1")
    with pytest.raises(FileExistsError):
        backend.claim_ready(pending["call_id"], worker_id="worker-2")
    claim = read(next(backend.directory.glob("*.claim.json")))
    assert claim["worker_id"] == "worker-1"
    assert len(list(backend.directory.glob("*.request.json"))) == 1


def test_wrong_request_binding_cannot_release_worker(staged, tmp_path):
    session, backend, _, _, _ = staged
    record = session.snapshot()
    record["payload"]["pending_predictor"]["binding"]["request_sha256"] = "a" * 64
    record["sha256"] = canonical_hash(record["payload"])
    path = tmp_path / "wrong.json"
    publish(path, record)
    with pytest.raises(ValueError, match="bind the staged"):
        backend.commit_checkpoint(path)
    assert not list(backend.directory.glob("*.ready.json"))


def test_changed_checkpoint_after_ready_blocks_worker(staged, tmp_path):
    session, backend, pending, _, _ = staged
    path = tmp_path / "checkpoint.json"
    session.persist(path)
    path.write_text("{}")
    with pytest.raises(ValueError, match="changed before worker"):
        backend.claim_ready(pending["call_id"], worker_id="worker")
    assert not list(backend.directory.glob("*.claim.json"))


def test_committed_response_resumes_same_original_call(staged, tmp_path):
    session, backend, pending, data, bank = staged
    record = session.persist(tmp_path / "checkpoint.json")
    backend.claim_ready(pending["call_id"], worker_id="worker")
    response(backend, pending)
    expected = session.finish()
    restored = SessionCoordinator.restore(record, data, bank, backend=backend)
    actual = restored.finish()
    assert restored.done and actual == expected
    assert actual["resource_reserved"]["tokens"] == 0
    assert actual["resource_spent"]["tokens"] == 20
    assert len(actual["calls"]) == 1


def test_response_without_committed_worker_remains_pending(staged):
    _, backend, pending, _, _ = staged
    response(backend, pending)
    with pytest.raises(PendingExecution):
        backend.resolve(pending["ticket"], pending["call_id"])


def test_altered_pending_ticket_rejected_before_any_worker_claim(staged):
    _, backend, pending, _, _ = staged
    with pytest.raises(ValueError, match="original request"):
        backend.resolve({**pending["ticket"], "request_sha256": "0" * 64}, pending["call_id"])


def test_pending_selector_requires_its_original_durable_checkpoint(tmp_path):
    spec = {
        "model": "selector_fixture",
        "weights": "none",
        "tokenizer": "none",
        "adapter": "test",
        "generation": {},
        "runtime": {},
    }
    spool = tmp_path / "spool"
    spool.mkdir()
    backend = CommittedSpoolBackend(spool, spec, run_id="selector-commit")
    data, bank, config = typed_fixture(
        selector_kind="llm",
        authorization_mode="session_shared",
        isolation_mode="actual_cost_clock",
        model_call_budget=1,
    )
    session = SessionCoordinator(data, bank, config, backend=backend)
    session.step()
    pending = session.snapshot()["payload"]["pending_selector"]
    with pytest.raises(PendingExecution):
        backend.claim_ready(pending["call_id"], worker_id="must-not-start")
    record = session.persist(tmp_path / "checkpoint.json")
    backend.claim_ready(pending["call_id"], worker_id="original-worker")
    response(backend, pending, '{"query_order":[],"forecast_handles":[]}')
    expected = session.finish()
    restored = SessionCoordinator.restore(record, data, bank, backend=backend)
    assert restored.finish() == expected
    assert len(expected["selector_calls"]) == 1
    assert expected["selector_calls"][0]["response_error"] is None
    assert expected["resource_spent"]["tokens"] == 20
    assert expected["resource_reserved"]["tokens"] == 0
