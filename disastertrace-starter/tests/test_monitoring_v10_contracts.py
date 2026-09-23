import copy

import pytest
from test_monitoring_admission import setup_engine
from test_monitoring_outcome_policies import fixture

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine, AdmissionEvent
from disastertrace.monitoring_fixed_v1.outcomes import OutcomeRegistry


def test_formal_registry_rejects_omitted_policy():
    target, record = fixture()
    del record["resolution_policy"]
    with pytest.raises(ValueError, match="policy"):
        OutcomeRegistry([target], mode="formal_provider_bound").register(record)


def test_formal_provider_binding_is_roundtrippable_and_not_legacy():
    target, record = fixture()
    record.update(provider="IEM", provider_version="native_h15_snapshot.v1")
    registry = OutcomeRegistry([target], mode="formal_provider_bound")
    registry.register(record)
    assert registry.export()["payload"]["mode"] == "formal_provider_bound"
    wrong = dict(record, provider="DWD")
    with pytest.raises(ValueError, match="provider"):
        OutcomeRegistry([target], mode="formal_provider_bound").register(wrong)


@pytest.mark.parametrize("identity", ["a-policy", "z-policy"])
def test_v3_intervention_precedes_same_time_begin_and_survives_replay(tmp_path, monkeypatch, identity):
    experiment = {"invariants": {"scope": "fixture"}, "interventions": {"predict": True}}
    engine, _bundle, events = setup_engine(semantics_version="measurement.v3", experiment=experiment)
    engine.run(events[:1], until=55)
    prefix = engine.export()
    restored = AdmissionEngine.restore(prefix)
    policy = AdmissionEvent(identity, 60, "policy_intervention", {
        "parent_checkpoint_sha256": prefix["sha256"], "changes": {"predict": False}})
    # Observe actual processing order without relying on IDs. The restored branch
    # must also retain the versioned order when written as an unmodified journal.
    order = []
    original = AdmissionEngine._process

    def observe(self, event):
        order.append(event.kind)
        original(self, event)

    monkeypatch.setattr(AdmissionEngine, "_process", observe)
    restored.run([events[1], policy], until=61)
    assert order == ["policy_intervention", "begin"]
    plain = AdmissionEngine.restore(prefix)
    plain.run([events[1], policy], until=90)
    plain.write_journal(tmp_path / "admission.jsonl")
    assert AdmissionEngine.from_journal(tmp_path / "admission.jsonl").export() == plain.export()


def test_v2_event_order_is_not_redefined_for_historical_replay():
    engine, _bundle, events = setup_engine()
    policy = AdmissionEvent("z-policy", 60, "policy_intervention", {})
    assert engine._event_key(events[1]) < engine._event_key(policy)


def test_exact_coverage_rejects_missing_extra_and_duplicate_ids():
    from disastertrace.monitoring_v1.audit_contracts import require_exact_ids

    assert require_exact_ids(["a", "b"], ["b", "a"], "fixtures") == 2
    for observed in [["a"], ["a", "b", "c"], ["a", "a", "b"]]:
        with pytest.raises(ValueError, match="coverage"):
            require_exact_ids(["a", "b"], observed, "fixtures")


def test_composition_only_uses_model_slots_and_rejects_invalid_output():
    from disastertrace.monitoring_v1.e_composition import compose

    answer = compose('{"slots":{"a":"false","b":"unknown"},"fact_truth":"false"}', ["a", "b"])
    assert answer["reported_aggregate"] == "false"
    assert answer["composed_aggregate"] == "unknown"
    assert answer["reference_kind"] == "model_estimate"
    for raw in ['{"slots":{"a":"false"},"fact_truth":"false"}',
                '{"slots":{"a":false,"b":"unknown"},"fact_truth":"unknown"}',
                '{"slots":{"a":"true","a":"false","b":"unknown"},"fact_truth":"false"}']:
        with pytest.raises(ValueError):
            compose(raw, ["a", "b"])


def test_calibration_trace_preserves_original_and_identifies_mapping_only_effect():
    from disastertrace.monitoring_v1.calibration_diagnostics import trace_prediction

    bank = {"minimum_cell_n": 1, "mapping_version": "fixture",
            "cells": {'[1000,"no_taf"]': {"n": 98, "positive": 19},
                      '[1000,"pooled"]': {"n": 98, "positive": 19}},
            "post_calibration": {"1000": {
                "base": [{"upper": 1, "value": .2}],
                "evidence": [{"upper": 1, "value": .6}]}}}
    before = copy.deepcopy(bank)
    result = trace_prediction(bank, {"threshold": 1000}, None, ["a"], {"a": {"status": "missing"}})
    assert result["raw_probability"] == .2
    assert result["post_probability"] == .6
    assert result["same_raw_cell_as_base"]
    assert result["mapping_only_numeric_change"]
    assert result["four_cells"] == {"base_raw_base_map": .2, "base_raw_evidence_map": .6,
                                    "evidence_raw_base_map": .2, "evidence_raw_evidence_map": .6}
    assert bank == before
