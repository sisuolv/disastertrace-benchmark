"""D policies consume the admitted forecast at the current shared clock only."""

import copy
import hashlib
import json

import pytest
from test_monitoring_preparation import card, setup_engine

from disastertrace.monitoring_fixed_v1.admission import (
    AdmissionEngine,
    AdmissionEvent,
    TypedOpportunity,
)
from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, Forecast, Target
from disastertrace.monitoring_fixed_v1.decision_inputs import choose_admitted_preparation


def probability_engine(protocol="base_bound_override"):
    target = Target(
        "t",
        "station:A",
        "visibility",
        "m",
        "event_probability",
        "point",
        100,
        100,
        "future_physical",
        "native.v1",
        event_operator="lt",
        threshold=5000,
    )
    scenario = card()
    scenario["jobs"] = scenario["jobs"][:1]
    engine = AdmissionEngine(
        [TypedOpportunity("o", target, 90)],
        fallbacks={
            "t": Forecast(target.contract_hash, "event_probability", "probability", 0.1).to_dict()
        },
        protocol=protocol,
        preparation=scenario,
    )
    return engine, target


def baseline(target, value, at, revision, protocol="base_bound_override"):
    forecast = Forecast(target.contract_hash, "event_probability", "probability", value).to_dict()
    bundle = EvidenceBundle.freeze(
        {
            "schema": "disastertrace.frozen_evidence.v1",
            "opportunity_id": "o",
            "target": target.to_dict(),
            "cutoff": 90,
            "baseline": {
                "forecast": forecast,
                "source_revision": revision,
                "issued_at": at - 1,
                "available_at": at,
                "valid_until": 100,
                "kind": "research",
                "mapping_version": "fixture.v1",
                "content": {"value": value},
            },
            "state": {"forecast": forecast, "mode": "FOLLOW", "protocol": protocol},
            "assets": [],
            "receipts": [],
            "authorization_mode": "target_private",
            "representation": "native",
            "availability_basis": "declared_archive_scenario",
            "provider_version": "fixture.v1",
        }
    )
    return bundle, AdmissionEvent("base-" + revision, at, "baseline", {"bundle": bundle.to_dict()})


def choose(engine, at, method="threshold"):
    return choose_admitted_preparation(
        engine, method=method, at=at, next_at=at + 5, miss_penalty=10
    )


def test_future_registered_update_cannot_enter_current_decision():
    engine, target = probability_engine()
    _, early = baseline(target, 0.1, 10, "r1")
    _, future = baseline(target, 0.9, 20, "r2")
    engine.run([early, future], until=15)
    first = choose(engine, 15)
    assert first["probabilities"] == {"j1": 0.1}
    assert first["action"] == ["wait", None]
    engine.run([], until=25)
    second = choose(engine, 25)
    assert second["probabilities"] == {"j1": 0.9}
    assert second["action"] == ["prepare", "j1"]
    assert first["forecast_bindings"]["j1"] != second["forecast_bindings"]["j1"]


def completion(target, bundle, expires_at):
    raw = json.dumps(
        Forecast(target.contract_hash, "event_probability", "probability", 0.8).to_dict()
    )
    return AdmissionEvent(
        "complete",
        15,
        "completion",
        {
            "call_id": "c",
            "bundle_hash": bundle.bundle_hash,
            "raw": raw,
            "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "started_at": 12,
            "completed_at": 14,
            "persisted_at": 15,
            "expires_at": expires_at,
            "cost": {"requests": 0, "bytes": len(raw), "tokens": 0, "compute_ms": 1},
            "ended_with_eos": True,
            "head": "program",
            "executor": "fixture.v1",
        },
    )


@pytest.mark.parametrize(
    "protocol,expected", [("base_bound_override", 0.2), ("persistent_override", 0.8)]
)
def test_revision_protocol_controls_the_probability_used_by_D(protocol, expected):
    engine, target = probability_engine(protocol)
    bundle, early = baseline(target, 0.1, 10, "r1", protocol)
    _, later = baseline(target, 0.2, 20, "r2", protocol)
    begin = AdmissionEvent(
        "begin",
        12,
        "begin",
        {
            "call_id": "c",
            "bundle": bundle.to_dict(),
            "head": "program",
            "executor": "fixture.v1",
        },
    )
    engine.run([early, begin, completion(target, bundle, 40), later], until=25)
    assert engine.attempts[-1]["status"] == "accepted"
    assert choose(engine, 25)["probabilities"] == {"j1": expected}


def test_expired_proposal_is_not_a_decision_input():
    engine, target = probability_engine()
    bundle, early = baseline(target, 0.1, 10, "r1")
    begin = AdmissionEvent(
        "begin",
        12,
        "begin",
        {
            "call_id": "c",
            "bundle": bundle.to_dict(),
            "head": "program",
            "executor": "fixture.v1",
        },
    )
    engine.run([early, begin, completion(target, bundle, 18)], until=25)
    assert choose(engine, 25)["probabilities"] == {"j1": 0.1}


@pytest.mark.parametrize("method", ["no_preparation", "threshold", "edf", "rolling_two_step"])
def test_decision_keeps_source_engine_unchanged_and_reproduces_after_restore(method):
    engine, target = probability_engine()
    _, event = baseline(target, 0.8, 10, "r1")
    engine.run([event], until=15)
    checkpoint = copy.deepcopy(engine.export())
    preparation = copy.deepcopy(engine.preparation.to_dict())
    decision = choose(engine, 15, method)
    assert engine.export() == checkpoint
    assert engine.preparation.to_dict() == preparation
    restored = AdmissionEngine.restore(checkpoint)
    assert choose(restored, 15, method) == decision


@pytest.mark.parametrize("at", [14, 16])
def test_decision_cannot_query_past_or_unprocessed_future_clock(at):
    engine, _ = probability_engine()
    engine.run([], until=15)
    with pytest.raises(ValueError, match="current"):
        choose(engine, at)


def test_scalar_forecast_cannot_be_used_as_demand_probability():
    engine, _, events = setup_engine(preparation=card())
    engine.run(events, until=60)
    with pytest.raises(ValueError, match="probability"):
        choose(engine, 60)


def test_uninitialized_clock_or_missing_D_scenario_rejected():
    engine, _ = probability_engine()
    with pytest.raises(ValueError, match="current"):
        choose(engine, 0)
    engine.run([], until=15)
    engine.preparation = None
    with pytest.raises(ValueError, match="preparation"):
        choose(engine, 15)
