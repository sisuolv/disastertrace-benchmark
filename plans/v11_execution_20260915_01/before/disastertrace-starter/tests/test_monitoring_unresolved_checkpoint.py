"""Stopped local calls retain unresolved remote costs across process boundaries."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from test_monitoring_typed_session import typed_fixture

from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator


def failed_transport(*args):
    raise ConnectionError("synthetic dispatched transport became unknown")


def test_unknown_predictor_checkpoint_restores_in_another_process(tmp_path):
    data, bank, config = typed_fixture()
    session = SessionCoordinator(data, bank, config, backend=failed_transport)
    session.step()
    checkpoint = session.snapshot()
    assert checkpoint["payload"]["schema"] == "disastertrace.session_unresolved.v2"
    assert checkpoint["payload"]["ledger"]["reserved"]["tokens"] > 0
    spec = tmp_path / "spec.json"
    output = tmp_path / "result.json"
    spec.write_text(json.dumps({"checkpoint": checkpoint, "data": data, "bank": bank}))
    code = """
import json,sys
from pathlib import Path
from test_monitoring_unresolved_checkpoint import failed_transport
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
s=json.loads(Path(sys.argv[1]).read_text())
session=SessionCoordinator.restore(s['checkpoint'],s['data'],s['bank'],backend=failed_transport)
report=session.finish()
Path(sys.argv[2]).write_text(json.dumps({'report':report,'checkpoint':session.snapshot()}))
"""
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join(
            [str(Path(__file__).parent), str(Path(__file__).parents[1] / "src")]
        ),
        PYTHONDONTWRITEBYTECODE="1",
    )
    subprocess.run([sys.executable, "-c", code, str(spec), str(output)], env=env, check=True)
    resumed = json.loads(output.read_text())
    report = resumed["report"]
    assert len(report["calls"]) == 1
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert report["resource_reserved"] == checkpoint["payload"]["ledger"]["reserved"]
    assert report["calls"][0]["admission_status"] == "unknown_execution"
    assert checkpoint == session.snapshot()


def test_unknown_selector_restores_without_redispatch():
    data, bank, config = typed_fixture(
        selector_kind="llm",
        allocation_mode="global_budget",
        authorization_mode="session_shared",
        isolation_mode="actual_cost_clock",
    )
    session = SessionCoordinator(data, bank, config, backend=failed_transport)
    session.step()
    checkpoint = session.snapshot()
    restored = SessionCoordinator.restore(checkpoint, data, bank, backend=failed_transport)
    report = restored.finish()
    assert len(report["selector_calls"]) == 1
    assert report["resource_reserved"]["tokens"] > 0
    assert not report["calls"]


def test_original_receipt_reconciles_cost_without_reopening_old_decision():
    data, bank, config = typed_fixture()
    session = SessionCoordinator(data, bank, config, backend=failed_transport)
    session.step()
    checkpoint = session.snapshot()
    events = checkpoint["payload"]["ledger"]["events"]
    binding = next(
        e["binding"]
        for e in events
        if e["event"] == "bind_request" and e["receipt_id"] == "forecast-0"
    )
    proof = dict(binding, response_sha256="a" * 64, observed_at=checkpoint["payload"]["clock"])
    receipt = {
        "receipt_id": "forecast-0",
        "actual": {"tokens": 31, "compute_ms": 10},
        "proof": proof,
    }
    wrong = dict(receipt, proof=dict(proof, request_sha256="b" * 64))
    with pytest.raises(ValueError, match="original request"):
        session.reconcile_costs([wrong])
    assert session.snapshot() == checkpoint
    resolved = session.reconcile_costs([receipt])
    assert resolved["payload"]["schema"] == "disastertrace.session_quiescent.v1"
    assert resolved["payload"]["ledger"]["spent"]["tokens"] == 31
    assert session.reconcile_costs([receipt])["sha256"] == resolved["sha256"]
    report = session.finish()
    assert report["calls"][0]["admission_status"] == "unknown_execution"
    assert len(report["calls"]) == 1
    assert report["resource_reserved"]["tokens"] == 0
    assert len(report["snapshots"]) == len(data["opportunities"])


def test_reconciled_overrun_is_measured_and_durable(tmp_path):
    from disastertrace.monitoring_v1.journal import EventJournal
    from disastertrace.monitoring_v1.resources import BudgetLedger, Cost

    path = tmp_path / "ledger.jsonl"
    with EventJournal(path) as journal:
        ledger = BudgetLedger({"tokens": 10}, journal=journal)
        ledger.reserve("call", Cost(tokens=10), "target")
        binding = {"request_sha256": "a" * 64, "execution_sha256": "b" * 64}
        ledger.bind_request("call", binding)
        ledger.mark_unknown("call", {"reason": "transport_lost"})
        proof = dict(binding, response_sha256="c" * 64, observed_at=30)
        ledger.reconcile_unknown("call", Cost(tokens=15), proof)
        assert ledger.spent.tokens == 15 and ledger.reserved.tokens == 0
    with EventJournal(path) as journal:
        restored = BudgetLedger.restore(journal)
        assert restored.spent.tokens == 15
        assert restored.entries["call"]["overrun"]
        assert restored.reconcile_unknown("call", Cost(tokens=15), proof) is False


def test_unknown_source_is_not_downloaded_again_after_restore():
    data, bank, config = typed_fixture(predict=False)
    data["query_results"] = []
    session = SessionCoordinator(data, bank, config)
    session.step()
    first = session.snapshot()
    restored = SessionCoordinator.restore(first, data, bank)
    report = restored.finish()
    ids = [r["receipt_id"] for r in report["source_receipts"]]
    assert len(ids) == len(set(ids))
    assert report["resource_reserved"]["requests"] > 0
    assert not report["calls"]
