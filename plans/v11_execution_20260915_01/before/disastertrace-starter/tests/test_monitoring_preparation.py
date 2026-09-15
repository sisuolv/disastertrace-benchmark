"""Preparation consumes resources independently of forecast revision/fallback."""

from dataclasses import replace

import pytest
from test_monitoring_admission import complete
from test_monitoring_admission import setup_engine as single_engine

from disastertrace.monitoring_fixed_v1.admission import (
    AdmissionEngine,
    AdmissionEvent,
    TypedOpportunity,
)
from disastertrace.monitoring_fixed_v1.contracts import Forecast, Target
from disastertrace.monitoring_v1.journal import EventJournal
from disastertrace.monitoring_v1.preparation import (
    PreparationReducer,
    one_step_prepare,
    score_preparation,
)


def setup_engine(*, preparation, journal=None):
    _, b, events = single_engine()
    t = Target(**b.policy_view()["target"])
    u = replace(t, target_id="u", entity="station:B")
    engine = AdmissionEngine(
        [TypedOpportunity("o", t, 90), TypedOpportunity("u", u, 90)],
        fallbacks={
            "t": b.policy_view()["baseline"]["forecast"],
            "u": Forecast(u.contract_hash, "scalar", "degC", -3.5).to_dict(),
        },
        preparation=preparation,
        journal=journal,
    )
    return engine, b, events


def card(capacity=1):
    return {
        "schema": "disastertrace.preparation_scenario.v1",
        "kind": "research_assumption",
        "capacity": capacity,
        "budget": 20,
        "units": "synthetic_cost_units",
        "jobs": [
            {
                "job_id": "j1",
                "target_id": "t",
                "deadline": 95,
                "duration": 10,
                "expires_at": 98,
                "cost": 3,
                "cleanup_duration": 5,
                "cleanup_cost": 1,
            },
            {
                "job_id": "j2",
                "target_id": "u",
                "deadline": 96,
                "duration": 8,
                "expires_at": 97,
                "cost": 2,
                "cleanup_duration": 3,
                "cleanup_cost": 1,
            },
        ],
    }


def test_inference_and_follow_do_not_stop_preparation_exact_deadline_counts():
    engine, b, events = setup_engine(preparation=card())
    events += [
        AdmissionEvent("prepare", 85, "prepare", {"job_id": "j1"}),
        complete(b, 90),
        AdmissionEvent("follow", 91, "follow", {"target_id": "t"}),
    ]
    engine.run(events, until=99)
    assert engine.preparation.snapshots["j1"]["ready"] is True
    assert engine.preparation.spent == 3
    assert len(engine.preparation.snapshots) == 2


def test_cancel_is_sunk_cost_and_cleanup_blocks_reallocation():
    engine, _, events = setup_engine(preparation=card())
    events += [
        AdmissionEvent("p1", 60, "prepare", {"job_id": "j1"}),
        AdmissionEvent("c1", 65, "cancel_preparation", {"job_id": "j1"}),
        AdmissionEvent("p2blocked", 66, "prepare", {"job_id": "j2"}),
        AdmissionEvent("p2", 70, "prepare", {"job_id": "j2"}),
    ]
    engine.run(events, until=98)
    assert engine.preparation.spent == 6
    assert any(r["status"] == "capacity_rejected" for r in engine.preparation.history)
    assert engine.preparation.snapshots["j1"]["ready"] is False
    assert engine.preparation.snapshots["j2"]["ready"] is True


def test_expired_coverage_is_not_ready_and_repeated_start_does_not_pay_twice():
    scenario = card()
    scenario["jobs"][0]["expires_at"] = 80
    engine, _, events = setup_engine(preparation=scenario)
    event = AdmissionEvent("p1", 60, "prepare", {"job_id": "j1"})
    engine.run(
        events + [event, event, AdmissionEvent("again", 65, "prepare", {"job_id": "j1"})], until=99
    )
    assert engine.preparation.spent == 3
    assert not engine.preparation.snapshots["j1"]["ready"]


def test_late_start_and_budget_rejection_preserve_cost():
    scenario = card()
    scenario["budget"] = 3
    engine, _, events = setup_engine(preparation=scenario)
    engine.run(
        events
        + [
            AdmissionEvent("early", 60, "prepare", {"job_id": "j1"}),
            AdmissionEvent("late", 94, "prepare", {"job_id": "j2"}),
        ],
        until=99,
    )
    assert engine.preparation.spent == 0
    assert {r["status"] for r in engine.preparation.history} >= {"budget_rejected", "too_late"}


def test_replay_restores_preparation_under_the_same_clock(tmp_path):
    path = tmp_path / "session.jsonl"
    with EventJournal(path) as journal:
        engine, _, events = setup_engine(preparation=card(), journal=journal)
        engine.run(events + [AdmissionEvent("p1", 85, "prepare", {"job_id": "j1"})], until=99)
    replay = AdmissionEngine.from_journal(path)
    assert replay.preparation.to_dict() == engine.preparation.to_dict()
    report = score_preparation(replay.preparation, {"j1": 1, "j2": 1}, miss_penalty=10)
    assert report["total_cost"] == 13
    assert report["unique_jobs"] == 2


def test_single_step_analytic_boundary_is_strict():
    assert one_step_prepare(0.6, 3, 5) is False
    assert one_step_prepare(0.61, 3, 5) is True


def test_one_job_per_target_prevents_repeated_D_settlement():
    scenario = card()
    scenario["jobs"][1]["target_id"] = "t"
    with pytest.raises(ValueError, match="one job"):
        PreparationReducer(scenario)
