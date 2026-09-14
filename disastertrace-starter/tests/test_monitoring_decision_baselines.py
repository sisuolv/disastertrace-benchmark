"""Decision controls preserve common forecasts and cannot read future demands."""

import copy

import pytest
from test_monitoring_preparation import card, setup_engine

from disastertrace.monitoring_fixed_v1.decision_baselines import (
    act,
    choose_preparation,
    possible_actions,
    projected_cost,
)


def fixture():
    engine, _, events = setup_engine(preparation=card())
    engine.run(events, until=60)
    return engine


def test_planning_keeps_live_engine_and_forecasts_unchanged():
    engine = fixture()
    before = copy.deepcopy(engine.export())
    preparation = copy.deepcopy(engine.preparation.to_dict())
    choice = choose_preparation(
        engine,
        {"j1": 0.1, "j2": 0.9},
        method="rolling_two_step",
        at=60,
        next_at=65,
        miss_penalty=10,
    )
    assert choice in {("prepare", "j2"), ("wait", None)}
    assert engine.export() == before and engine.preparation.to_dict() == preparation


def test_threshold_boundary_and_capacity_are_enforced():
    engine = fixture()
    choice = choose_preparation(
        engine, {"j1": 0.3, "j2": 0.2}, method="threshold", at=60, next_at=65, miss_penalty=10
    )
    assert choice == ("wait", None)
    assert act(engine, ("prepare", "j1"), 61, event_id="actual")
    assert not act(engine, ("prepare", "j2"), 62, event_id="blocked")
    assert engine.preparation.spent == 3


def test_expired_protection_is_not_projected_as_coverage():
    scenario = card()
    scenario["jobs"][0]["expires_at"] = 80
    engine, _, events = setup_engine(preparation=scenario)
    engine.run(events, until=60)
    assert act(engine, ("prepare", "j1"), 61, event_id="early")
    assert projected_cost(engine, {"j1": 1, "j2": 0}, 10) == 13


def test_completed_demand_can_release_capacity_without_rewriting_past_readiness():
    engine = fixture()
    assert act(engine, ("prepare", "j1"), 85, event_id="on-time")
    engine.run([], until=96)
    assert engine.preparation.snapshots["j1"]["ready"]
    assert ("cancel_preparation", "j1") in possible_actions(engine)
    assert act(engine, ("cancel_preparation", "j1"), 97, event_id="release-later")
    assert engine.preparation.snapshots["j1"]["ready"]


@pytest.mark.parametrize("probability", [None, True, float("nan"), -0.1, 1.1])
def test_invalid_forecast_cannot_enter_decision_comparison(probability):
    with pytest.raises(ValueError):
        projected_cost(fixture(), {"j1": probability, "j2": 0.5}, 10)


def test_current_state_and_forward_time_are_required():
    with pytest.raises(ValueError):
        choose_preparation(
            fixture(), {"j1": 0.5, "j2": 0.5}, method="edf", at=61, next_at=60, miss_penalty=10
        )
