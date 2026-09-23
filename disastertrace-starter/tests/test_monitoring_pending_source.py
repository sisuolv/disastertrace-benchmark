"""Original native acquisitions retain identity, timing, payment and entitlements."""

import copy
import json
from pathlib import Path

import pytest
from test_monitoring_typed_session import typed_fixture

from disastertrace.monitoring_v1.execution import PendingExecution
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.targets import canonical_hash


class PendingSource:
    def __init__(self, directory, products):
        self.directory = Path(directory)
        self.source_contract = {
            "provider": "registered_native_archive",
            "products_sha256": canonical_hash(products),
        }

    def __call__(self, request, receipt_id):
        with (self.directory / (receipt_id + ".request.json")).open("x") as handle:
            json.dump(request, handle)
        raise PendingExecution({"remote_id": receipt_id})

    def resolve(self, ticket, receipt_id):
        if ticket != {"remote_id": receipt_id}:
            raise ValueError("Original source ticket mismatch")
        path = self.directory / (receipt_id + ".reply.json")
        if not path.exists():
            raise PendingExecution(ticket)
        row = json.loads(path.read_text())
        return row["product"], row["details"]


def pending_source(directory, **changes):
    data, bank, config = typed_fixture(
        authorization_mode="session_shared",
        isolation_mode="actual_cost_clock",
        predict=False,
        request_budget=1,
    )
    config.update(changes)
    cutoff = min(o["cutoff"] for o in data["opportunities"])
    data["opportunities"] = [o for o in data["opportunities"] if o["cutoff"] == cutoff]
    tids = {o["target_id"] for o in data["opportunities"]}
    oids = {o["opportunity_id"] for o in data["opportunities"]}
    data["targets"] = [t for t in data["targets"] if t["target_id"] in tids]
    data["baseline_candidates"] = [b for b in data["baseline_candidates"] if b["target_id"] in tids]
    data["e_f_pairs"] = [p for p in data["e_f_pairs"] if p["opportunity_id"] in oids]
    backend = PendingSource(directory, data["query_results"])
    session = SessionCoordinator(data, bank, config, source_backend=backend)
    report = session.step()
    state = session.snapshot()["payload"]
    assert state["schema"] == "disastertrace.session_inflight_source.v5"
    assert state["ledger"]["reserved"]["requests"] == 1
    assert state["ledger"]["spent"]["requests"] == 0
    assert not state["store"]["assets"] and not report["source_receipts"]
    assert not session.done
    return data, bank, session


def reply(directory, data, session, *, elapsed_seconds=0.2, corrupt=False):
    p = session.snapshot()["payload"]["pending_source"]
    product = copy.deepcopy(
        next(r for r in data["query_results"] if r["query_id"] == p["query_id"])
    )
    if corrupt:
        product["status"] = "not-the-registered-result"
    row = {"product": product, "details": {"seconds": 0.01, "elapsed_seconds": elapsed_seconds}}
    (directory / (p["receipt_id"] + ".reply.json")).write_text(json.dumps(row))


def test_source_pending_poll_has_no_free_evidence_or_repeated_request(tmp_path):
    _, _, session = pending_source(tmp_path)
    original = session.snapshot()
    session.step()
    assert session.snapshot() == original
    assert session.finish() == session.report and not session.done
    assert len(list(tmp_path.glob("*.request.json"))) == 1
    assert session.report["pending_source_requests"] == 1
    assert session.report["actual_model_calls"] == 0


def test_restored_source_settles_original_once_before_granting_evidence(tmp_path):
    data, bank, session = pending_source(tmp_path)
    original = session.snapshot()
    reply(tmp_path, data, session)
    expected = session.finish()
    restored = SessionCoordinator.restore(
        original, data, bank, source_backend=PendingSource(tmp_path, data["query_results"])
    )
    assert restored.finish() == expected and restored.done
    assert expected["resource_reserved"]["requests"] == 0
    assert expected["resource_spent"]["requests"] == 1
    assert expected["resource_spent"]["compute_ms"] == 10
    assert len(expected["source_receipts"]) == 1
    assert len(list(tmp_path.glob("*.request.json"))) == 1
    assert restored.snapshot()["payload"]["store"]["assets"]


def test_late_source_does_not_supply_evidence_or_forecasts_at_previous_cutoff(tmp_path):
    data, _, session = pending_source(tmp_path)
    reply(tmp_path, data, session, elapsed_seconds=2000)
    result = session.finish()
    (receipt,) = result["source_receipts"]
    assert receipt["completed_at"] > data["opportunities"][0]["cutoff"]
    assert result["resource_spent"]["compute_ms"] == 10
    assert len(result["snapshots"]) == len(data["opportunities"])
    assert all(s["mode"] == "FOLLOW" for s in result["snapshots"])
    assert all(v == "undetermined" for v in result["frames"][0]["e_statuses"].values())


def test_changed_native_response_is_charged_but_never_authorized(tmp_path):
    data, _, session = pending_source(tmp_path)
    reply(tmp_path, data, session, corrupt=True)
    report = session.finish()
    assert report["source_receipts"][0]["execution_status"] == "source_identity_mismatch"
    assert report["resource_spent"]["requests"] == 1
    assert report["resource_reserved"]["requests"] == 0
    assert not session.snapshot()["payload"]["store"]["assets"]


def test_pending_source_rejects_control_or_executor_changes(tmp_path):
    data, bank, session = pending_source(tmp_path)
    with pytest.raises(ValueError, match="pending"):
        session.step({"selector_kind": "coverage"})
    other = PendingSource(tmp_path, [])
    with pytest.raises(ValueError, match="source execution"):
        SessionCoordinator.restore(session.snapshot(), data, bank, source_backend=other)
    with pytest.raises(ValueError, match="source execution"):
        SessionCoordinator.restore(session.snapshot(), data, bank)


def test_second_pending_source_preserves_first_settled_asset_and_charge(tmp_path):
    data, bank, session = pending_source(tmp_path, request_budget=2)
    reply(tmp_path, data, session)
    session.step()
    record = session.snapshot()
    assert len(record["payload"]["pending_source"]["source_steps"]) == 1
    assert len(record["payload"]["store"]["assets"]) == 1
    assert record["payload"]["ledger"]["spent"]["requests"] == 1
    assert record["payload"]["ledger"]["reserved"]["requests"] == 1
    reply(tmp_path, data, session)
    expected = session.finish()
    restored = SessionCoordinator.restore(
        record, data, bank, source_backend=PendingSource(tmp_path, data["query_results"])
    )
    assert restored.finish() == expected
    assert expected["resource_spent"]["requests"] == 2
    assert len(expected["source_receipts"]) == 2
    assert len(list(tmp_path.glob("*.request.json"))) == 2


def test_untrustworthy_source_receipt_keeps_original_reservation(tmp_path):
    data, _, session = pending_source(tmp_path)
    reply(tmp_path, data, session)
    (path,) = tmp_path.glob("*.reply.json")
    row = json.loads(path.read_text())
    row["details"]["seconds"] = "unknown"
    path.write_text(json.dumps(row))
    report = session.finish()
    assert session.done
    assert report["source_receipts"][0]["execution_status"] == "unknown_execution"
    assert report["resource_spent"]["requests"] == 0
    assert report["resource_reserved"]["requests"] == 1
    assert not session.snapshot()["payload"]["store"]["assets"]
