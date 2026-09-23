"""Query choice must not silently choose forecast targets or invocation times."""

import copy

import pytest
from test_monitoring_typed_session import typed_fixture

from disastertrace.monitoring_v1.policies import run_session, stable_rank
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator


def scheduled(**changes):
    return typed_fixture(
        admission_semantics="measurement.v3",
        isolation_mode="actual_cost_clock",
        predictor_kind="program",
        forecast_schedule={"kind": "public_serial_slots.v1", "lead_seconds": 100,
                           "spacing_seconds": 20},
        **changes,
    )


def expected_schedule(data, config):
    result = []
    for cutoff in sorted({o["cutoff"] for o in data["opportunities"]}):
        active = sorted((o for o in data["opportunities"] if o["cutoff"] == cutoff),
                        key=lambda o: stable_rank(config["seed"], "forecast_slot", o["opportunity_id"]))
        result.extend((o["opportunity_id"], cutoff - 100_000_000 + i*20_000_000)
                      for i, o in enumerate(active[:config["per_tick_forecast_cap"]]))
    return result


def test_public_schedule_is_identical_under_distinct_query_policies():
    data, bank, config = scheduled(authorization_mode="session_shared")
    for selector in ("round_robin", "risk", "coverage", "batch_complete"):
        report = run_session(data, bank, dict(config, selector_kind=selector))
        assert [(c["opportunity_id"], c["started_at"]) for c in report["calls"]] == expected_schedule(data, config)
        assert all(f["forecast_schedule"]["kind"] == "public_serial_slots.v1" for f in report["frames"])


def test_acquisition_cannot_use_time_reserved_for_forecast_slots():
    data, bank, config = scheduled()
    for q in data["query_catalog"]:
        q["latency_ms"] = 550000
    report = run_session(data, bank, config)
    assert report["resource_spent"]["requests"] == 0
    assert [(c["opportunity_id"], c["started_at"]) for c in report["calls"]] == expected_schedule(data, config)


def test_overrunning_a_slot_keeps_costs_and_skips_the_next_without_backdating():
    data, bank, config = scheduled()
    config["predictor_kind"] = "llm"

    def slow(*args):
        return '{"fact_truth":"unknown","probability":0.3}', {
            "seconds": 30, "input_tokens": 10, "output_tokens": 10, "ended_with_eos": True}

    report = run_session(data, bank, config, backend=slow)
    assert len(report["calls"]) == 2
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert report["resource_spent"]["tokens"] == 40
    assert [(c["opportunity_id"], c["started_at"]) for c in report["calls"]] == expected_schedule(data, config)[::2]


def test_schedule_survives_actual_controller_restore():
    data, bank, config = scheduled()
    session = SessionCoordinator(data, bank, config)
    session.step()
    restored = SessionCoordinator.restore(session.snapshot(), data, bank).finish()
    assert restored == run_session(data, bank, config)


@pytest.mark.parametrize("change", [{"lead_seconds": True}, {"lead_seconds": 600},
                                    {"spacing_seconds": 100}, {"unexpected": 1}])
def test_invalid_slot_contract_is_not_silently_ignored(change):
    data, bank, config = scheduled()
    config = copy.deepcopy(config)
    config["forecast_schedule"].update(change)
    with pytest.raises(ValueError, match="schedule|slot"):
        run_session(data, bank, config)
