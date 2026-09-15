"""Transport tests use explicit engineering receipts, never pretend model answers."""

import hashlib
import json

import pytest

from disastertrace.monitoring_v1.execution import PendingExecution
from disastertrace.monitoring_v1.spool_backend import SpoolBackend, digest, publish
from disastertrace.monitoring_v1.targets import canonical_hash


@pytest.fixture
def dispatched(tmp_path):
    spec = {
        "model": "engineering_fixture",
        "weights": "none",
        "tokenizer": "none",
        "adapter": "test",
        "generation": {},
        "runtime": {},
    }
    backend = SpoolBackend(tmp_path, spec, run_id="fixture-run")
    with pytest.raises(PendingExecution) as error:
        backend("fixture system", {"fixture": True}, "call-0")
    return backend, error.value.ticket


def respond(backend, ticket):
    raw = '{"fixture":true}'
    payload = {
        "call_id": "call-0",
        "request_sha256": ticket["request_sha256"],
        "execution_sha256": canonical_hash(backend.execution_contract),
        "raw": raw,
        "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "input_tokens": 3,
        "output_tokens": 4,
        "compute_seconds": 0.0,
        "ended_with_eos": True,
    }
    worker = backend.directory / (ticket["remote_id"] + ".worker.json")
    publish(worker, {**payload, "origin": "synthetic transport test"})
    response = backend.directory / (ticket["remote_id"] + ".response.json")
    publish(
        response,
        {
            **payload,
            "schema": "disastertrace.spool_response.v1",
            "worker_receipt_sha256": digest(worker),
        },
    )
    return response


def test_original_dispatch_and_resolution_are_idempotent(dispatched):
    backend, ticket = dispatched
    with pytest.raises(PendingExecution) as error:
        backend("fixture system", {"fixture": True}, "call-0")
    assert error.value.ticket == ticket
    with pytest.raises(PendingExecution) as error:
        backend.resolve(ticket, "call-0")
    assert error.value.ticket == ticket
    respond(backend, ticket)
    first = backend.resolve(ticket, "call-0")
    assert first == backend.resolve(ticket, "call-0")
    assert first[1]["input_tokens"] == 3 and first[1]["output_tokens"] == 4
    assert len(list(backend.directory.glob("*.request.json"))) == 1


def test_call_id_cannot_be_rebound_to_new_input(dispatched):
    backend, _ = dispatched
    with pytest.raises(ValueError, match="different request"):
        backend("different system", {"fixture": True}, "call-0")


def test_other_request_response_rejected(dispatched):
    backend, ticket = dispatched
    path = respond(backend, ticket)
    response = json.loads(path.read_text())
    response["call_id"] = "other"
    path.write_text(json.dumps(response))
    with pytest.raises(ValueError, match="original dispatched request"):
        backend.resolve(ticket, "call-0")


def test_changed_worker_receipt_cannot_be_delivered(dispatched):
    backend, ticket = dispatched
    respond(backend, ticket)
    path = backend.directory / (ticket["remote_id"] + ".worker.json")
    path.write_text("{}")
    with pytest.raises(ValueError, match="Worker receipt hash"):
        backend.resolve(ticket, "call-0")


def test_atomic_publication_does_not_replace_an_existing_response(tmp_path):
    path = tmp_path / "receipt.json"
    publish(path, {"identity": 1})
    with pytest.raises(FileExistsError):
        publish(path, {"identity": 2})
    assert json.loads(path.read_text()) == {"identity": 1}
