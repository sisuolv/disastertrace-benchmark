"""A dispatched, still-running predictor survives a fresh coordinator process."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from test_monitoring_typed_session import typed_fixture

from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator


class PendingFixtureBackend:
    def __init__(self, directory):
        self.directory = Path(directory)

    def __call__(self, system, request, call_id):
        from disastertrace.monitoring_v1.execution import PendingExecution

        with (self.directory / (call_id + "-request.json")).open("x") as handle:
            json.dump({"system": system, "request": request, "call_id": call_id}, handle)
        raise PendingExecution({"remote_id": call_id, "transport": "test_file_mailbox.v1"})

    def resolve(self, ticket, call_id):
        from disastertrace.monitoring_v1.execution import PendingExecution

        if ticket != {"remote_id": call_id, "transport": "test_file_mailbox.v1"}:
            raise ValueError("Original ticket mismatch")
        reply = self.directory / (call_id + "-reply.json")
        if not reply.exists():
            raise PendingExecution(ticket)
        row = json.loads(reply.read_text())
        if row["call_id"] != call_id:
            raise ValueError("Original reply mismatch")
        return row["raw"], row["details"]


class PendingSecondBackend(PendingFixtureBackend):
    def __call__(self, system, request, call_id):
        if call_id == "forecast-0":
            return '{"fact_truth":"unknown","probability":0.3}', {
                "input_tokens": 4,
                "output_tokens": 5,
                "seconds": 0.01,
                "ended_with_eos": True,
                "origin": "synthetic engineering transport",
            }
        return super().__call__(system, request, call_id)


def reply(directory):
    (directory / "forecast-0-reply.json").write_text(
        json.dumps(
            {
                "call_id": "forecast-0",
                "raw": '{"fact_truth":"unknown","probability":0.2}',
                "details": {
                    "input_tokens": 21,
                    "output_tokens": 10,
                    "seconds": 0.02,
                    "ended_with_eos": True,
                    "origin": "synthetic engineering transport",
                },
            }
        )
    )


def pending_session(directory):
    data, bank, config = typed_fixture(forecast_call_cap=1, model_call_budget=1)
    session = SessionCoordinator(data, bank, config, backend=PendingFixtureBackend(directory))
    session.step()
    checkpoint = session.snapshot()
    assert checkpoint["payload"]["schema"] == "disastertrace.session_inflight_predictor.v3"
    assert checkpoint["payload"]["ledger"]["reserved"]["tokens"] > 0
    assert checkpoint["payload"]["next_tick"] == 0
    assert not session.done
    return data, bank, session


def test_unresolved_poll_is_idempotent_and_never_redispatches(tmp_path):
    _, _, session = pending_session(tmp_path)
    before = session.snapshot()
    session.step()
    assert session.snapshot() == before
    assert len(list(tmp_path.glob("*-request.json"))) == 1
    assert session.finish() == session.report
    assert not session.done


def test_fresh_process_continues_original_pending_invocation(tmp_path):
    data, bank, session = pending_session(tmp_path)
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"data": data, "bank": bank, "checkpoint": session.snapshot()}))
    reply(tmp_path)
    expected = session.finish()
    result = tmp_path / "continued.json"
    code = """
import json,sys
from pathlib import Path
from test_monitoring_pending_predictor import PendingFixtureBackend
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
spec=json.loads(Path(sys.argv[1]).read_text())
backend=PendingFixtureBackend(sys.argv[3])
session=SessionCoordinator.restore(spec['checkpoint'],spec['data'],spec['bank'],backend=backend)
report=session.finish()
assert session.done
Path(sys.argv[2]).write_text(json.dumps(report))
"""
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=os.pathsep.join(
            [str(Path(__file__).parent), str(Path(__file__).parents[1] / "src")]
        ),
    )
    subprocess.run(
        [sys.executable, "-c", code, str(spec), str(result), str(tmp_path)], check=True, env=env
    )
    actual = json.loads(result.read_text())
    assert actual == expected
    assert len(actual["calls"]) == 1
    assert actual["resource_spent"]["tokens"] == 31
    assert actual["resource_reserved"]["tokens"] == 0
    assert len(actual["snapshots"]) == len(data["opportunities"])
    assert len(list(tmp_path.glob("*-request.json"))) == 1


def test_pending_frame_cannot_change_selection_after_dispatch(tmp_path):
    _, _, session = pending_session(tmp_path)
    with pytest.raises(ValueError, match="pending"):
        session.step({"selector_kind": "risk"})


def test_pending_second_call_preserves_completed_frame_prefix(tmp_path):
    data, bank, config = typed_fixture(forecast_call_cap=2, model_call_budget=2)
    session = SessionCoordinator(data, bank, config, backend=PendingSecondBackend(tmp_path))
    first = session.step()
    assert len(first["calls"]) == 1
    assert session.snapshot()["payload"]["pending_predictor"]["forecast_index"] == 1
    payload = {
        "call_id": "forecast-1",
        "raw": '{"fact_truth":"unknown","probability":0.2}',
        "details": {
            "input_tokens": 21,
            "output_tokens": 10,
            "seconds": 0.02,
            "ended_with_eos": True,
        },
    }
    (tmp_path / "forecast-1-reply.json").write_text(json.dumps(payload))
    report = session.finish()
    assert session.done
    assert [r["call_id"] for r in report["calls"]] == ["forecast-0", "forecast-1"]
    assert report["resource_spent"]["tokens"] == 40
    assert report["frames"][0]["call_ids"] == ["forecast-0", "forecast-1"]


def test_late_pending_response_keeps_actual_charge_and_cutoff_fallback(tmp_path):
    _, _, session = pending_session(tmp_path)
    reply(tmp_path)
    path = tmp_path / "forecast-0-reply.json"
    row = json.loads(path.read_text())
    row["details"]["seconds"] = 4000
    path.write_text(json.dumps(row))
    report = session.finish()
    assert session.done
    assert report["resource_spent"]["tokens"] == 31
    assert report["calls"][0]["receipt"]["cost"]["compute_ms"] == 4_000_000
    assert report["resource_spent"]["compute_ms"] >= 4_000_000
    assert report["resource_reserved"]["tokens"] == 0
    assert report["calls"][0]["admission_status"] in {"slot_overrun", "resource_overrun"}
    assert all(s["mode"] == "FOLLOW" for s in report["snapshots"])


def test_changing_resolver_implementation_is_a_new_executor(tmp_path):
    data, bank, session = pending_session(tmp_path)

    class OtherResolver(PendingFixtureBackend):
        def resolve(self, ticket, call_id):
            raise RuntimeError("not the original resolver")

    with pytest.raises(ValueError, match="execution contract"):
        SessionCoordinator.restore(session.snapshot(), data, bank, backend=OtherResolver(tmp_path))


def test_delivery_latency_is_not_billed_as_model_compute(tmp_path):
    _, _, session = pending_session(tmp_path)
    reply(tmp_path)
    path = tmp_path / "forecast-0-reply.json"
    row = json.loads(path.read_text())
    row["details"]["elapsed_seconds"] = 4000
    path.write_text(json.dumps(row))
    report = session.finish()
    call = report["calls"][0]
    assert call["receipt"]["cost"]["compute_ms"] == 20
    assert call["persisted_at"] - call["started_at"] >= 4_000_000_000
    assert call["admission_status"] == "slot_overrun"
