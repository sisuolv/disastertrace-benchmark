"""Keep cutoff snapshots exact while avoiding unused event-prefix reconstruction."""

import pytest
from test_monitoring_admission import bundle, complete, setup_engine

from disastertrace.monitoring_fixed_v1 import admission
from disastertrace.monitoring_fixed_v1.contracts import Target


def test_noncutoff_does_not_sort_or_hash_event_prefix(monkeypatch):
    engine, _bundle, events = setup_engine()
    engine.run(events, until=60)
    calls = []
    original = engine._event_key

    def key(event):
        calls.append(event.event_id)
        return original(event)

    monkeypatch.setattr(engine, "_event_key", key)
    engine._seal(61)
    assert engine.snapshots == {}
    assert calls == []


def test_one_shared_prefix_hash_preserves_every_cutoff_snapshot(monkeypatch):
    visible = bundle()
    target = Target(**visible.policy_view()["target"])
    extras = [admission.TypedOpportunity("other-" + str(i), target, 90) for i in range(3)]
    engine, visible, events = setup_engine(visible, extras)
    events.append(complete(visible, at=90))
    calls = []
    original = admission.fingerprint

    def fingerprint(value):
        if isinstance(value, dict) and set(value) == {"contract", "events"}:
            calls.append(value)
        return original(value)

    monkeypatch.setattr(admission, "fingerprint", fingerprint)
    engine.run(events, until=90)
    assert len(engine.snapshots) == 4
    expected = original({"contract": engine.contract_hash, "events": [e.to_dict() for e in events]})
    assert {s["prefix_sha256"] for s in engine.snapshots.values()} == {expected}
    assert {s["forecast"]["value"] for s in engine.snapshots.values()} == {-5}
    assert {s["override_call_id"] for s in engine.snapshots.values()} == {"c"}
    assert len(calls) == 1


def test_failed_transaction_does_not_modify_inherited_call_or_state():
    engine, visible, events = setup_engine()
    engine.run(events, until=60)
    before = engine.export()
    states_before = {key: value.to_dict() for key, value in engine.states.items()}
    with pytest.raises(ValueError, match="Unknown control target"):
        engine.run(
            [
                admission.AdmissionEvent("cancel", 61, "cancel", {"call_id": "c"}),
                admission.AdmissionEvent("clear", 62, "follow", {"target_id": "t"}),
                admission.AdmissionEvent("invalid", 63, "follow", {"target_id": "absent"}),
            ],
            until=90,
        )
    assert engine.export() == before
    assert not engine.calls["c"]["canceled"]
    assert {key: value.to_dict() for key, value in engine.states.items()} == states_before
    engine.run([complete(visible)], until=90)
    assert engine.snapshots["o"]["forecast"]["value"] == -5


def test_public_fork_keeps_independent_mutable_evidence_history():
    engine, _, events = setup_engine()
    engine.run(events, until=60)
    before = engine.export()
    branch = engine.fork()
    branch.calls["c"]["bundle"]["payload"]["baseline"]["content"]["value"] = 100
    branch._history[0]["events"][0]["payload"]["bundle"]["payload"]["baseline"]["content"][
        "value"
    ] = 100
    branch.states["t"].events[0]["forecast"]["value"] = 100
    assert engine.export() == before
    assert engine.states["t"].events[0]["forecast"]["value"] == -3.5
