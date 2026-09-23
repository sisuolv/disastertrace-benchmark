"""Selector dispatch survives process loss without another selection or charge."""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from test_monitoring_pending_predictor import PendingFixtureBackend
from test_monitoring_typed_session import typed_fixture

from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.targets import canonical_hash


class SelectorFixtureBackend(PendingFixtureBackend):
    def __call__(self, system, request, call_id):
        if call_id.startswith("select-"):
            return super().__call__(system, request, call_id)
        return '{"fact_truth":"unknown","probability":0.3}', {
            "input_tokens": 4,
            "output_tokens": 5,
            "seconds": 0.01,
            "ended_with_eos": True,
        }


def pending_session(directory):
    data, bank, config = typed_fixture(
        selector_kind="llm",
        authorization_mode="session_shared",
        isolation_mode="actual_cost_clock",
        model_call_budget=2,
        forecast_call_cap=1,
        per_tick_forecast_cap=1,
    )
    session = SessionCoordinator(data, bank, config, backend=SelectorFixtureBackend(directory))
    report = session.step()
    checkpoint = session.snapshot()
    assert checkpoint["payload"]["schema"] == "disastertrace.session_inflight_selector.v4"
    assert checkpoint["payload"]["next_tick"] == 0
    assert not report["source_receipts"] and not report["calls"]
    assert report["pending_model_calls"] == report["dispatched_model_calls"] == 1
    assert checkpoint["payload"]["ledger"]["reserved"]["tokens"] > 0
    assert not session.done
    return data, bank, session


def reply(directory, **changes):
    request = json.loads((directory / "select-0-request.json").read_text())["request"]
    details = {"input_tokens": 11, "output_tokens": 7, "seconds": 0.02, "ended_with_eos": True}
    details.update(changes)
    payload = {
        "call_id": "select-0",
        "raw": json.dumps(
            {
                "query_order": list(request["queries"]),
                "forecast_handles": [next(iter(request["targets"]))],
            }
        ),
        "details": details,
    }
    (directory / "select-0-reply.json").write_text(json.dumps(payload))


def test_pending_selector_polls_original_request_without_advancing_or_charging(tmp_path):
    _, _, session = pending_session(tmp_path)
    before = session.snapshot()
    session.step()
    assert session.snapshot() == before
    assert session.finish() == session.report
    assert not session.done
    assert len(list(tmp_path.glob("*-request.json"))) == 1
    assert (
        session.policy_view()["public_selector_view"]
        == before["payload"]["pending_selector"]["public_selector_view"]
    )


def test_selector_then_predictor_has_one_shared_budget_after_process_restore(tmp_path):
    data, bank, session = pending_session(tmp_path)
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"data": data, "bank": bank, "checkpoint": session.snapshot()}))
    reply(tmp_path)
    expected = session.finish()
    result = tmp_path / "continued.json"
    code = """
import json,sys
from pathlib import Path
from test_monitoring_pending_selector import SelectorFixtureBackend
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
spec=json.loads(Path(sys.argv[1]).read_text())
session=SessionCoordinator.restore(spec['checkpoint'],spec['data'],spec['bank'],backend=SelectorFixtureBackend(sys.argv[3]))
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
    assert len(actual["selector_calls"]) == len(actual["calls"]) == 1
    assert actual["resource_spent"]["tokens"] == 27
    assert actual["resource_reserved"]["tokens"] == 0
    assert len(actual["snapshots"]) == len(data["opportunities"])
    assert len(list(tmp_path.glob("*-request.json"))) == 1


def test_selector_delivery_wait_is_not_charged_as_compute_and_cannot_backdate(tmp_path):
    data, _, session = pending_session(tmp_path)
    reply(tmp_path, elapsed_seconds=8000)
    report = session.finish()
    assert len(report["selector_calls"]) == 1
    call = report["selector_calls"][0]
    assert call["completed_at"] - call["started_at"] == 8_000_000_000
    assert report["resource_spent"]["tokens"] == 18
    assert report["resource_spent"]["compute_ms"] == 20
    assert not report["calls"] and not report["source_receipts"]
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert all(s["mode"] == "FOLLOW" for s in report["snapshots"])


def test_pending_selector_blocks_control_change_and_detects_rehashed_cursor(tmp_path):
    data, bank, session = pending_session(tmp_path)
    with pytest.raises(ValueError, match="pending"):
        session.step({"acquire": False})
    damaged = copy.deepcopy(session.snapshot())
    damaged["payload"]["pending_selector"]["clock"] += 1
    damaged["sha256"] = canonical_hash(damaged["payload"])
    with pytest.raises(ValueError, match="selector"):
        SessionCoordinator.restore(damaged, data, bank, backend=SelectorFixtureBackend(tmp_path))


def test_received_unfinished_selection_is_charged_without_executing_its_choices(tmp_path):
    _, _, session = pending_session(tmp_path)
    reply(tmp_path, ended_with_eos=False)
    session.step()
    report = session.report
    assert report["selector_calls"][0]["response_error"]
    assert report["resource_spent"]["tokens"] == 18
    assert not report["source_receipts"] and not report["calls"]
    assert len(report["snapshots"]) > 0


def test_late_selector_can_legally_start_a_new_tick_without_reissuing_the_old_one(tmp_path):
    _, _, session = pending_session(tmp_path)
    reply(tmp_path, elapsed_seconds=4000)
    session.finish()
    assert not session.done
    assert session.snapshot()["payload"]["pending_selector"]["call_id"] == "select-1"
    assert len(session.report["selector_calls"]) == 1
    assert len(list(tmp_path.glob("*-request.json"))) == 2
    assert session.report["resource_spent"]["tokens"] == 18
    assert session.report["resource_reserved"]["tokens"] > 0


def test_direct_resume_cannot_change_controls_of_a_pending_selector(tmp_path):
    from disastertrace.monitoring_v1.policies import run_session

    data, bank, session = pending_session(tmp_path)
    config = dict(session.config, acquire=False)
    with pytest.raises(ValueError, match="pending"):
        run_session(
            data, bank, config, backend=SelectorFixtureBackend(tmp_path), _resume=session.snapshot()
        )
