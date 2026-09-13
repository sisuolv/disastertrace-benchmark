"""Deadline and provenance counterexamples for the typed admission boundary."""

import copy
import hashlib
import json

import pytest

from disastertrace.monitoring_fixed_v1.admission import (
    AdmissionEngine,
    AdmissionEvent,
    TypedOpportunity,
    baseline_context,
    score_admitted,
)
from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, Forecast, Target
from disastertrace.monitoring_v1.journal import EventJournal


def bundle(cutoff=90, opportunity_id="o"):
    target = Target(
        "t",
        "station:A",
        "temperature",
        "degC",
        "scalar",
        "point",
        100,
        100,
        "future_physical",
        "native.v1",
    )
    forecast = Forecast(target.contract_hash, "scalar", "degC", -3.5).to_dict()
    return EvidenceBundle.freeze(
        {
            "schema": "disastertrace.frozen_evidence.v1",
            "opportunity_id": opportunity_id,
            "target": target.to_dict(),
            "cutoff": cutoff,
            "baseline": {
                "forecast": forecast,
                "source_revision": "r1",
                "issued_at": 40,
                "available_at": 50,
                "valid_until": 100,
                "kind": "research",
                "mapping_version": "fixture.v1",
                "content": {"value": -3.5},
            },
            "state": {"forecast": forecast, "mode": "FOLLOW", "protocol": "base_bound_override"},
            "assets": [],
            "receipts": [],
            "authorization_mode": "target_private",
            "representation": "native",
            "availability_basis": "declared_archive_scenario",
            "provider_version": "fixture.v1",
        }
    )


def setup_engine(b=None, extra=(), **kwargs):
    b = b or bundle()
    row = b.policy_view()
    row["state"]["protocol"] = kwargs.get("protocol", "base_bound_override")
    b = EvidenceBundle.freeze(row)
    target = Target(**row["target"])
    opportunities = [TypedOpportunity(row["opportunity_id"], target, row["cutoff"]), *extra]
    engine = AdmissionEngine(opportunities, fallbacks={"t": row["baseline"]["forecast"]}, **kwargs)
    baseline = AdmissionEvent("base", 50, "baseline", {"bundle": b.to_dict()})
    begin = AdmissionEvent(
        "begin",
        60,
        "begin",
        {
            "call_id": "c",
            "bundle": b.to_dict(),
            "head": "program",
            "executor": "deterministic_fixture.v1",
        },
    )
    return engine, b, [baseline, begin]


def complete(b, at=80, value=-5, **changes):
    raw = json.dumps(
        Forecast(
            Target(**b.policy_view()["target"]).contract_hash, "scalar", "degC", value
        ).to_dict()
    )
    receipt = {
        "call_id": "c",
        "bundle_hash": b.bundle_hash,
        "raw": raw,
        "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "started_at": 60,
        "completed_at": at - 1,
        "persisted_at": at,
        "expires_at": 99,
        "cost": {"requests": 0, "bytes": len(raw), "tokens": 0, "compute_ms": 1},
        "ended_with_eos": True,
        "head": "program",
        "executor": "deterministic_fixture.v1",
    }
    receipt.update(changes)
    return AdmissionEvent("complete", at, "completion", receipt)


def test_early_opportunity_closes_without_closing_later_one():
    b = bundle()
    t = Target(**b.policy_view()["target"])
    engine, b, events = setup_engine(b, [TypedOpportunity("early", t, 70)])
    engine.run(events + [complete(b)], until=90)
    assert engine.snapshots["early"]["forecast"]["value"] == -3.5
    assert engine.snapshots["o"]["forecast"]["value"] == -5
    assert engine.snapshots["o"]["mode"] == "OVERRIDE"


def test_exact_cutoff_completion_is_before_seal_follow_is_after():
    engine, b, events = setup_engine()
    follow = AdmissionEvent("follow", 90, "follow", {"target_id": "t"})
    engine.run(events + [complete(b, 90), follow], until=91)
    assert engine.snapshots["o"]["forecast"]["value"] == -5
    assert engine.attempts[-1]["status"] == "closed_target"


@pytest.mark.parametrize(
    "at,changes,status",
    [
        (91, {}, "late"),
        (80, {"persisted_at": 79}, "invalid_receipt"),
        (80, {"bundle_hash": "0" * 64}, "invalid_receipt"),
        (80, {"raw_sha256": "0" * 64}, "invalid_receipt"),
        (80, {"started_at": 59}, "invalid_receipt"),
        (80, {"completed_at": 81}, "invalid_receipt"),
        (80, {"ended_with_eos": False}, "invalid_response"),
    ],
)
def test_failures_keep_fallback_and_full_denominator(at, changes, status):
    engine, b, events = setup_engine()
    engine.run(events + [complete(b, at, **changes)], until=max(90, at))
    assert engine.snapshots["o"]["forecast"]["value"] == -3.5
    assert engine.attempts[-1]["status"] == status
    assert "raw" in engine.attempts[-1]


def test_source_input_must_exist_at_begin_not_just_eventual_cutoff():
    row = bundle().policy_view()
    row["baseline"]["available_at"] = 65
    b = EvidenceBundle.freeze(row)
    engine, _, events = setup_engine()
    events[1] = AdmissionEvent(
        "begin",
        60,
        "begin",
        {"call_id": "c", "bundle": b.to_dict(), "head": "program", "executor": "x"},
    )
    engine.run(events, until=90)
    assert engine.attempts[-1]["status"] == "invalid_begin"
    assert engine.snapshots["o"]["mode"] == "FOLLOW"


def test_no_backdated_injection_or_snapshot_mutation():
    engine, b, events = setup_engine()
    engine.run(events, until=90)
    before = copy.deepcopy(engine.snapshots)
    with pytest.raises(ValueError, match="backdated"):
        engine.run([complete(b, 80)], until=90)
    engine.run([complete(b, 92)], until=95)
    assert engine.snapshots == before


def test_missing_begin_cannot_be_scored_as_a_candidate():
    engine, b, events = setup_engine()
    engine.run(events[:1] + [complete(b)], until=90)
    assert engine.attempts[-1]["status"] == "missing_begin"
    assert engine.snapshots["o"]["forecast"]["value"] == -3.5


@pytest.mark.parametrize(
    "protocol,expected",
    [
        ("base_bound_override", -3.5),
        ("persistent_override", -5),
    ],
)
def test_inflight_identical_scalar_relevant_change_obeys_protocol(protocol, expected):
    engine, b, events = setup_engine(protocol=protocol)
    row = b.policy_view()
    row["baseline"]["content"]["new_condition"] = "different native forecast context"
    row["baseline"]["available_at"] = 70
    row["baseline"]["source_revision"] = "r2"
    revision = AdmissionEvent(
        "r2", 70, "baseline", {"bundle": EvidenceBundle.freeze(row).to_dict()}
    )
    engine.run(events + [revision, complete(b)], until=90)
    assert engine.snapshots["o"]["forecast"]["value"] == expected


def test_h15_identity_ignores_question_and_mirror_but_not_applicable_conditions():
    row = bundle().policy_view()
    row["provider_version"] = "native_h15_snapshot.v1"
    row["baseline"]["content"] = {
        "native_taf": {"projection": {"segments": [{"wind": "10KT"}]}, "raw": "x"},
        "calibration_bank_sha256": "bank",
        "mapping_details": {"p": 0.2},
        "E_question": {"predicate": "old"},
    }
    first = baseline_context(EvidenceBundle.freeze(row))
    row["baseline"]["source_revision"] = "mirror"
    row["baseline"]["content"]["E_question"] = {"predicate": "unrelated"}
    row["baseline"]["content"]["native_taf"]["raw"] = "different wrapping"
    assert baseline_context(EvidenceBundle.freeze(row)) == first
    row["baseline"]["content"]["native_taf"]["projection"]["segments"][0]["wind"] = "50KT"
    assert baseline_context(EvidenceBundle.freeze(row)) != first


def test_expired_baseline_and_override_fall_back():
    row = bundle().policy_view()
    row["cutoff"] = 75
    row["opportunity_id"] = "early"
    row["baseline"]["valid_until"] = 80
    b = EvidenceBundle.freeze(row)
    t = Target(**row["target"])
    engine, b, events = setup_engine(b, [TypedOpportunity("late", t, 90)])
    engine.run(events + [complete(b, 70, expires_at=78)], until=90)
    assert engine.snapshots["early"]["forecast"]["value"] == -5
    assert engine.snapshots["late"]["baseline_kind"] == "fallback"
    assert engine.snapshots["late"]["forecast"]["value"] == -3.5


def test_scoring_requires_journal_replay_and_mature_target_bound_outcomes(tmp_path):
    path = tmp_path / "events.jsonl"
    with EventJournal(path) as journal:
        engine, b, events = setup_engine(journal=journal)
        engine.run(events + [complete(b)], until=90)
    restored = AdmissionEngine.from_journal(path)
    assert restored.snapshots == engine.snapshots
    outcome = {
        "opportunity_id": "o",
        "target_contract_hash": Target(**b.policy_view()["target"]).contract_hash,
        "value": -6,
        "status": "mature",
        "source_revision": "obs-v1",
    }
    report = score_admitted([outcome], {"program": path})
    assert report["scores"]["arms"]["program"]["mean_loss"] == 1
    outcome["status"] = "provisional"
    assert score_admitted([outcome], {"program": path})["scores"]["settled"] == 0
    outcome["target_contract_hash"] = "0" * 64
    with pytest.raises(ValueError, match="target"):
        score_admitted([outcome], {"program": path})
    with pytest.raises((ValueError, TypeError)):
        score_admitted([outcome], {"fake": {"o": b.policy_view()["baseline"]["forecast"]}})


def test_begin_rejects_protocol_mismatch_and_receipt_requires_every_cost_dimension():
    engine, b, events = setup_engine()
    row = b.policy_view()
    row["state"]["protocol"] = "persistent_override"
    events[1] = AdmissionEvent(
        "begin", 60, "begin", {**events[1].payload, "bundle": EvidenceBundle.freeze(row).to_dict()}
    )
    engine.run(events, until=90)
    assert engine.attempts[-1]["status"] == "invalid_begin"
    engine, b, events = setup_engine()
    engine.run(events + [complete(b, cost={})], until=90)
    assert engine.attempts[-1]["status"] == "invalid_receipt"


def test_E_only_activity_cannot_be_passed_as_a_forecasting_arm(tmp_path):
    path = tmp_path / "e_only.jsonl"
    with EventJournal(path) as journal:
        engine, b, events = setup_engine(journal=journal)
        events[1] = AdmissionEvent("begin", 60, "begin", {**events[1].payload, "head": "e_only"})
        engine.run(events, until=90)
    outcome = {
        "opportunity_id": "o",
        "target_contract_hash": Target(**b.policy_view()["target"]).contract_hash,
        "value": -6,
        "status": "mature",
        "source_revision": "obs-v1",
    }
    with pytest.raises(ValueError, match="E-only"):
        score_admitted([outcome], {"e_only": path})
