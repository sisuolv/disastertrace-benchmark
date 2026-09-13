"""Counterexamples for non-nested counts, repeated outcomes and sparse cells."""

import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "audit_saved_traces.py"
spec = importlib.util.spec_from_file_location("recorded_audit", MODULE)
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


def minimal_session():
    probability = 0.2
    raw = json.dumps({"probability": probability, "e_status": "undetermined", "decision": "override", "citations": []})
    bank = {"minimum_cell_n": 20, "mapping_version": "test", "cells": {'[1000,"pooled"]': {"n": 3, "positive": 0}}}
    snapshots = [{"opportunity_id": ident, "target_id": "t", "cutoff": cutoff, "probability": probability,
                  "base_probability": probability, "mode": "override", "override_call_id": "f0"}
                 for ident, cutoff in [("a", 10), ("b", 20)]]
    anchor = {r["opportunity_id"]: {"target_id": "t", "cutoff": r["cutoff"], "prediction": probability,
                                     "base": probability, "outcome": 0} for r in snapshots}
    request = {"opportunity_id": "a", "clock": 1, "cutoff": 10, "target": {"target_id": "t", "threshold": 1000},
               "common_baseline": {"context_hash": "hash", "product_revision_id": "frozen_fallback", "probability": probability},
               "read_evidence": [], "registered_query_ids": [], "current_state": {"probability": 0.5}}
    call = {"call_id": "f0", "opportunity_id": "a", "started_at": 1, "completed_at": 2,
            "details": {"ended_with_eos": True}, "raw": raw, "response_error": None,
            "proposed_probability": probability, "decision": "override", "reported_e": "undetermined",
            "citation_errors": [], "expected_e_from_disclosed_products": "undetermined"}
    attempt = {"call_id": "f0", "snapshot_context_hash": "hash", "current_context_hash": "hash", "target_id": "t", "status": "accepted"}
    trace = {"calls": [call], "attempts": [attempt], "selector_calls": [{"call_id": "s0", "response_error": None}],
             "actual_model_calls": 2, "snapshots": snapshots, "state_audit": [], "config": {"forecast_call_cap": 2}}
    return trace, {"f0": request}, anchor, bank, {}


def test_override_can_have_no_change_from_base_and_cover_uncalled_opportunity():
    counts, rows = audit.audit_session(*minimal_session())
    assert counts["actual_model_calls"] == 2
    assert counts["predictor_calls"] == counts["selector_calls"] == 1
    assert counts["accepted_candidates"] == 1
    assert counts["snapshots_in_override_mode"] == 2
    assert counts["snapshots_different_from_base"] == 0
    assert counts["candidate_changes_base_at_start"] == 0
    assert counts["candidate_changes_current_state_at_start"] == 1
    assert counts["opportunities_without_direct_call_but_adopted_override"] == 1
    assert rows[0]["adopted_snapshot_ids"] == ["a", "b"]


def test_unrecorded_candidate_is_never_synthesized():
    values = list(minimal_session())
    values[0]["snapshots"][1]["override_call_id"] = "missing"
    with pytest.raises(ValueError, match="unrecorded candidate"):
        audit.audit_session(*values)


def test_selector_count_must_reconcile():
    values = list(minimal_session())
    values[0]["actual_model_calls"] = 1
    with pytest.raises(ValueError, match="reconciliation"):
        audit.audit_session(*values)


def test_follow_with_probability_change_is_not_accepted():
    values = list(minimal_session())
    trace = values[0]
    call = trace["calls"][0]
    call.update(decision="follow", proposed_probability=0.7,
                raw=json.dumps({"probability": 0.7, "decision": "follow", "e_status": "undetermined", "citations": []}))
    trace["attempts"][0]["status"] = "declined_follow"
    for snap in trace["snapshots"]:
        snap.update(mode="follow", override_call_id=None)
    counts, _ = audit.audit_session(*values)
    assert counts["follow_or_nochange_with_nonbase_proposal"] == 1
    assert counts["candidate_changes_base_at_start"] == 1
    assert counts["accepted_candidates"] == 0


def test_one_unknown_outcome_per_target_tightens_bounds():
    rows = [{"opportunity_id": "a", "target_id": "t", "base": 0, "prediction": 1, "outcome": None},
            {"opportunity_id": "b", "target_id": "t", "base": 1, "prediction": 0, "outcome": None}]
    result = audit.independent_scores(rows)
    assert result["settled"] == 0
    assert result["base_brier"] is None
    assert result["full_population_gain_bounds"] == [0, 0]
    rows[1]["target_id"] = "different"
    assert audit.independent_scores(rows)["full_population_gain_bounds"] == [-1, 1]


def test_common_masks_cannot_silently_disagree():
    row = {"opportunity_id": "a", "target_id": "t", "base": 0.2, "prediction": 0.2, "outcome": 0, "cutoff": 10}
    other = deepcopy(row)
    other["outcome"] = None
    with pytest.raises(ValueError, match="Common"):
        audit.validate_common_rows({"a": [row], "b": [other]})
    with pytest.raises(ValueError, match="Duplicate"):
        audit.independent_scores([row, row])


def test_sparse_pool_allowed_but_sparse_taf_falls_back():
    bank = {"minimum_cell_n": 20, "mapping_version": "test", "cells": {
        '[1000,"no_taf"]': {"n": 2, "positive": 1}, '[1000,"pooled"]': {"n": 3, "positive": 0}}}
    result = audit.backoff(bank, {"threshold": 1000}, None)
    assert result["level"] == "threshold_pool"
    assert result["attempts"][0]["status"] == "below_minimum_n"
    assert result["probability"] == 0.2


def test_unparsed_native_taf_is_explicit_fallback():
    values = list(minimal_session())
    request = values[1]["f0"]
    request["common_baseline"].update(product_revision_id="unparsed", relevant_content={"status": "unparsed"})
    values[4]["unparsed"] = {"issued_at": 0}
    counts, rows = audit.audit_session(*values)
    assert counts["calls_with_unavailable_taf_projection"] == 1
    assert rows[0]["baseline_mapping"]["level"] == "threshold_pool"


def test_action_replay_changes_only_recorded_nonbase_actions():
    sys.path.insert(0, str(MODULE.parent))
    from fixed_candidate_diagnostics import mutate_actions

    replay = {"payload": {"events": [
        {"kind": "candidate", "time": 2, "payload": {"call_id": "f0", "probability": 0.7, "decision": "follow"}},
        {"kind": "candidate", "time": 4, "payload": {"call_id": "f1", "probability": 0.2, "decision": "no_change"}},
        {"kind": "baseline", "time": 3, "payload": {"baseline": "opaque"}},
    ]}, "sha256": "prior"}
    calls = {
        "f0": {"valid_response": True, "differs_from_base_at_start": True, "decision": "follow", "proposed_probability": 0.7},
        "f1": {"valid_response": True, "differs_from_base_at_start": False, "decision": "no_change", "proposed_probability": 0.2},
    }
    before = deepcopy(replay)
    changed, ids = mutate_actions(replay, calls)
    assert replay == before
    assert ids == ["f0"]
    expected = deepcopy(before["payload"])
    expected["events"][0]["payload"]["decision"] = "override"
    assert changed["payload"] == expected
    assert len(changed["payload"]["events"]) == 3
