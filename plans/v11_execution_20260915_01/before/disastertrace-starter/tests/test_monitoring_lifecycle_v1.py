"""Repeated transport waits must survive restoration and affect admission."""

import pytest
from test_monitoring_pending_predictor import PendingFixtureBackend, reply
from test_monitoring_pending_selector import SelectorFixtureBackend
from test_monitoring_pending_selector import reply as selector_reply
from test_monitoring_pending_source import PendingSource
from test_monitoring_pending_source import reply as source_reply
from test_monitoring_typed_session import typed_fixture

from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator


@pytest.fixture
def wall(monkeypatch):
    from disastertrace.monitoring_v1 import lifecycle

    clock = [1_000_000_000_000]
    monkeypatch.setattr(lifecycle.time, "time_ns", lambda: clock[0])
    return clock


def make_session(tmp_path, role):
    data, bank, config = typed_fixture(
        isolation_mode="actual_cost_clock",
        forecast_call_cap=1,
        model_call_budget=2,
        pending_timing_policy="lifecycle_wall_v1",
        execution_mode="test_callback_v1",
    )
    if role == "source":
        config.update(predict=False, request_budget=1)
        cutoff = min(o["cutoff"] for o in data["opportunities"])
        data["opportunities"] = [o for o in data["opportunities"] if o["cutoff"] == cutoff]
        tids = {o["target_id"] for o in data["opportunities"]}
        oids = {o["opportunity_id"] for o in data["opportunities"]}
        data["targets"] = [r for r in data["targets"] if r["target_id"] in tids]
        data["baseline_candidates"] = [
            r for r in data["baseline_candidates"] if r["target_id"] in tids
        ]
        data["e_f_pairs"] = [r for r in data["e_f_pairs"] if r["opportunity_id"] in oids]
        source = PendingSource(tmp_path, data["query_results"])
        backend = None
    else:
        source = None
        backend = (SelectorFixtureBackend if role == "selector" else PendingFixtureBackend)(
            tmp_path
        )
        if role == "selector":
            config.update(selector_kind="llm", authorization_mode="session_shared")
    session = SessionCoordinator(data, bank, config, backend=backend, source_backend=source)
    session.step()
    return data, bank, session, backend, source


@pytest.mark.parametrize("role", ["predictor", "selector", "source"])
def test_pending_cumulative_delay_includes_poll_gaps_and_restore(tmp_path, wall, role):
    data, bank, session, backend, source = make_session(tmp_path, role)
    wall[0] += 2_000_000_000
    session.step()
    checkpoint = session.snapshot()
    waits = [
        r for r in checkpoint["payload"]["ledger"]["events"] if r["event"] == "execution_timing"
    ]
    assert waits[-1]["timing"]["elapsed_us"] >= 2_000_000
    restored = SessionCoordinator.restore(
        checkpoint, data, bank, backend=backend, source_backend=source
    )
    wall[0] += 3_000_000_000
    if role == "predictor":
        reply(tmp_path)
    elif role == "selector":
        selector_reply(tmp_path)
    else:
        source_reply(tmp_path, data, restored)
    report = restored.finish()
    rows = report[
        {"predictor": "calls", "selector": "selector_calls", "source": "source_receipts"}[role]
    ]
    assert rows[0]["completed_at"] - rows[0]["started_at"] >= 5_000_000
    assert len(list(tmp_path.glob("*request.json"))) == 1
    # Delivery waiting is not a fabricated five seconds of model compute.
    assert report["resource_spent"]["compute_ms"] < 5000


def test_late_pending_answer_cannot_enter_old_cutoff(tmp_path, wall):
    _, _, session, _, _ = make_session(tmp_path, "predictor")
    wall[0] += 4_000_000_000_000
    reply(tmp_path)
    report = session.finish()
    call = report["calls"][0]
    assert call["completed_at"] - call["started_at"] >= 4_000_000_000
    assert call["admission_status"] != "accepted"
    assert report["resource_spent"]["tokens"] == 31
    assert report["resource_reserved"]["tokens"] == 0


def test_failed_poll_retains_elapsed_time_and_unknown_reserve(tmp_path, wall):
    _, _, session, _, _ = make_session(tmp_path, "predictor")
    wall[0] += 7_000_000_000
    (tmp_path / "forecast-0-reply.json").write_text("{invalid")
    report = session.finish()
    assert report["calls"][0]["persisted_at"] - report["calls"][0]["started_at"] >= 7_000_000
    assert report["resource_reserved"]["tokens"] > 0


def test_production_rejects_arbitrary_callback_and_unknown_mode():
    def callback(*args):
        return "{}", {}

    with pytest.raises(ValueError, match="production"):
        bind_execution({"execution_mode": "production_bound_v1"}, callback)
    with pytest.raises(ValueError, match="execution mode"):
        bind_execution({"execution_mode": "typo"}, callback)


def test_checkpoint_timing_cannot_move_backwards(tmp_path, wall):
    _, _, session, _, _ = make_session(tmp_path, "predictor")
    wall[0] += 2_000_000_000
    session.step()
    wall[0] -= 1_000_000_000
    session.step()
    report = session.finish()
    assert report["resource_reserved"]["tokens"] > 0
    assert report["calls"][0]["admission_status"] != "accepted"
