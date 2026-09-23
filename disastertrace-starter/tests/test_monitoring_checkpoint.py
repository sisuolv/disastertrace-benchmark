"""Whole-controller recovery and counterfactual isolation at quiescent ticks."""

import copy
import json

import pytest
from test_monitoring_policies import fixture

from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator


def test_step_restore_matches_uninterrupted_calls_costs_and_events():
    data, bank, config = fixture()
    direct = run_session(data, bank, config)
    session = SessionCoordinator(data, bank, config)
    session.step()
    snapshot = json.loads(json.dumps(session.snapshot()))
    resumed = SessionCoordinator.restore(snapshot, data, bank)
    assert resumed.finish() == direct


def test_branches_do_not_mutate_prefix_or_repay_spent_cost():
    data, bank, config = fixture()
    session = SessionCoordinator(data, bank, config)
    session.step()
    snapshot = session.snapshot()
    before = copy.deepcopy(snapshot)
    first = SessionCoordinator.restore(snapshot, data, bank)
    first.step({"acquire": False, "predict": False})
    second = SessionCoordinator.restore(snapshot, data, bank)
    second.step()
    assert snapshot == before
    assert first.report["resource_spent"] == session.report["resource_spent"]
    assert second.report["resource_spent"]["requests"] >= first.report["resource_spent"]["requests"]
    with pytest.raises(ValueError, match="control"):
        second.step({"request_budget": 100})


def test_snapshot_integrity_and_environment_binding_are_strict():
    data, bank, config = fixture()
    session = SessionCoordinator(data, bank, config)
    session.step()
    snapshot = session.snapshot()
    snapshot["payload"]["next_tick"] += 1
    with pytest.raises(ValueError, match="integrity"):
        SessionCoordinator.restore(snapshot, data, bank)
    changed = copy.deepcopy(data)
    changed["query_results"][0]["status"] = "not_a_real_source_status"
    with pytest.raises(ValueError, match="binding"):
        SessionCoordinator.restore(session.snapshot(), changed, bank)


def test_no_step_reexecutes_a_captured_backend_call():
    data, bank, config = fixture()
    calls = []

    def backend(system, request, cid):
        assert cid not in calls
        calls.append(cid)
        return json.dumps(
            {
                "probability": 0.3,
                "e_status": "undetermined",
                "decision": "override",
                "citations": [],
            }
        ), {"seconds": 1, "input_tokens": 20, "output_tokens": 10, "ended_with_eos": True}

    session = SessionCoordinator(data, bank, config, backend=backend)
    session.step()
    old_calls = list(calls)
    restored = SessionCoordinator.restore(session.snapshot(), data, bank, backend=backend)
    restored.finish()
    assert calls[: len(old_calls)] == old_calls
    assert len(calls) == len(set(calls))


def test_future_archive_values_do_not_change_public_prefix_and_private_views():
    data, bank, config = fixture()
    first = SessionCoordinator(data, bank, config)
    first.step()
    future_ids = {
        q["query_id"]
        for q in data["query_catalog"]
        if q["available_at"] > first.policy_view()["clock"]
    }
    assert future_ids
    changed = copy.deepcopy(data)
    for r in changed["query_results"]:
        if r["query_id"] in future_ids:
            r["status"] = "future_value_should_be_hidden"
    second = SessionCoordinator(changed, bank, config)
    second.step()
    assert first.policy_view() == second.policy_view()
    assert "cache" not in first.policy_view()
    for target in data["targets"]:
        assert all(
            target["target_id"] in a["entitlement"]
            for a in first.policy_view(target["target_id"])["cache"]
        )
