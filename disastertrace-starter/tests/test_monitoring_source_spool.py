"""Only checkpoint-committed source receipts may grant registered native data."""

import hashlib
import json

import pytest
from test_monitoring_pending_source import pending_source

from disastertrace.monitoring_v1.execution import PendingExecution
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.source_spool import ArchiveSpoolSource
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash


def staged(tmp_path):
    fixture_path = tmp_path / "fixture"
    fixture_path.mkdir()
    data, bank, fixture = pending_source(fixture_path)
    config = dict(fixture.config)
    config.pop("source_execution_contract")
    spool = tmp_path / "source"
    spool.mkdir()
    backend = ArchiveSpoolSource(
        spool,
        {
            "provider": "registered_native_archive",
            "products_sha256": canonical_hash(data["query_results"]),
        },
        run_id="native-source-test",
    )
    session = SessionCoordinator(data, bank, config, source_backend=backend)
    session.step()
    return data, bank, backend, session


def deliver(data, backend, pending):
    key = pending["ticket"]["remote_id"]
    request_path = backend.directory / (key + ".request.json")
    request = read(request_path)
    product = next(r for r in data["query_results"] if r["query_id"] == pending["query_id"])
    raw = json.dumps(product, sort_keys=True, separators=(",", ":"))
    value = {
        "call_id": pending["receipt_id"],
        "request_sha256": digest(request_path),
        "execution_sha256": request["execution_sha256"],
        "raw": raw,
        "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "input_tokens": 0,
        "output_tokens": 0,
        "compute_seconds": 0.001,
        "ended_with_eos": True,
    }
    path = backend.directory / (key + ".worker.json")
    publish(path, value)
    publish(
        backend.directory / (key + ".response.json"),
        {
            **value,
            "schema": "disastertrace.spool_response.v1",
            "worker_receipt_sha256": digest(path),
        },
    )


def test_original_source_worker_requires_checkpoint_then_settles_once(tmp_path):
    data, bank, backend, session = staged(tmp_path)
    pending = session.snapshot()["payload"]["pending_source"]
    with pytest.raises(PendingExecution):
        backend.claim_ready(pending["receipt_id"], worker_id="before-checkpoint")
    record = session.persist(tmp_path / "checkpoint.json")
    request = backend.claim_ready(pending["receipt_id"], worker_id="native-worker")
    assert request["request"] == pending["request"]
    with pytest.raises(FileExistsError):
        backend.claim_ready(pending["receipt_id"], worker_id="duplicate-worker")
    deliver(data, backend, pending)
    expected = session.finish()
    restored = SessionCoordinator.restore(record, data, bank, source_backend=backend)
    assert restored.finish() == expected
    assert expected["actual_model_calls"] == 0
    assert expected["resource_spent"]["requests"] == 1
    assert expected["resource_reserved"]["requests"] == 0
    assert len(restored.snapshot()["payload"]["store"]["assets"]) == 1


def test_unclaimed_source_response_cannot_grant_an_asset(tmp_path):
    data, _, backend, session = staged(tmp_path)
    pending = session.snapshot()["payload"]["pending_source"]
    deliver(data, backend, pending)
    original = session.snapshot()
    session.step()
    assert session.snapshot() == original
    assert not list(backend.directory.glob("*.claim.json"))
