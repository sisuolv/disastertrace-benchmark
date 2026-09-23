import json

import pytest
from test_monitoring_policies import fixture

from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.selection import parse_selection


def test_selector_rejects_unregistered_repeated_and_over_capacity_handles():
    for raw in (
        '{"query_order":["future"],"forecast_handles":[]}',
        '{"query_order":["q0","q0"],"forecast_handles":[]}',
        '{"query_order":[],"forecast_handles":["t0","t1"]}',
    ):
        with pytest.raises(ValueError):
            parse_selection(raw, query_handles=["q0"], target_handles=["t0", "t1"], forecast_cap=1)
    assert parse_selection(
        '{"query_order":[],"forecast_handles":[]}',
        query_handles=[],
        target_handles=[],
        forecast_cap=1,
    ) == {"query_order": [], "forecast_handles": []}


def test_selector_and_forecaster_consume_the_same_model_call_and_token_budget():
    data, bank, config = fixture()
    config.update(
        selector_kind="llm",
        authorization_mode="session_shared",
        isolation_mode="actual_cost_clock",
        model_call_budget=3,
        per_tick_forecast_cap=1,
    )
    calls = []

    def backend(system, request, call_id):
        calls.append(call_id)
        if call_id.startswith("select-"):
            assert "outcomes" not in request and "private" not in request
            raw = {
                "query_order": list(request["queries"]),
                "forecast_handles": [next(iter(request["targets"]))],
            }
        else:
            raw = {
                "probability": 0.2,
                "e_status": "undetermined",
                "decision": "override",
                "citations": [],
            }
        return json.dumps(raw), {
            "input_tokens": 13,
            "output_tokens": 7,
            "seconds": 1,
            "ended_with_eos": True,
        }

    trace = run_session(data, bank, config, backend=backend)
    assert len(calls) == len(trace["calls"]) + len(trace["selector_calls"]) == 3
    assert trace["resource_spent"]["tokens"] == 60
    assert len(trace["snapshots"]) == len(data["opportunities"])


def test_invalid_selector_is_charged_and_keeps_all_opportunities():
    data, bank, config = fixture()
    config.update(
        selector_kind="llm",
        authorization_mode="session_shared",
        isolation_mode="actual_cost_clock",
        model_call_budget=2,
    )
    trace = run_session(
        data,
        bank,
        config,
        backend=lambda *_: (
            "bad selector",
            {"input_tokens": 10, "output_tokens": 1, "seconds": 1, "ended_with_eos": True},
        ),
    )
    assert len(trace["selector_calls"]) == 2 and not trace["calls"]
    assert trace["resource_spent"]["tokens"] == 22
    assert all(c["response_error"] for c in trace["selector_calls"])
    assert all(s["mode"] == "follow" for s in trace["snapshots"])


def test_llm_selector_cannot_silently_open_private_global_model_state():
    data, bank, config = fixture()
    with pytest.raises(ValueError, match="global/shared"):
        run_session(data, bank, dict(config, selector_kind="llm"), backend=lambda *_: None)


def test_shared_selector_sees_current_explicit_states_and_remaining_hard_resources():
    data, bank, config = fixture()
    config.update(
        selector_kind="llm",
        authorization_mode="session_shared",
        isolation_mode="actual_cost_clock",
        model_call_budget=4,
        per_tick_forecast_cap=1,
    )
    selections = []

    def backend(system, request, call_id):
        if call_id.startswith("select-"):
            selections.append(request)
            assert request["protocol"] == config["protocol"]
            remaining = request["remaining_resources_after_selection_reserve"]
            assert remaining["tokens"] >= 0 and remaining["compute_ms"] >= 0
            assert request["forecast_call_upper"]["tokens"] == 8192 + 384
            for row in request["targets"].values():
                state = row["current_state"]
                assert state["target_id"] == row["target"]["target_id"]
                assert state["protocol"] == config["protocol"]
                assert state["mode"] in {"follow", "override"}
            raw = {"query_order": [], "forecast_handles": [next(iter(request["targets"]))]}
        else:
            raw = {
                "probability": 0.3,
                "e_status": "undetermined",
                "decision": "override",
                "citations": [],
            }
        return json.dumps(raw), {
            "input_tokens": 13,
            "output_tokens": 7,
            "seconds": 1,
            "ended_with_eos": True,
        }

    run_session(data, bank, config, backend=backend)
    assert len(selections) == 2
    assert (
        selections[1]["remaining_resources_after_selection_reserve"]["tokens"]
        < selections[0]["remaining_resources_after_selection_reserve"]["tokens"]
    )
