"""Predetermined paired population, shared prefix and lossless request differences."""

from copy import deepcopy

import pytest

from disastertrace.carrier_repr import design
from disastertrace.forecast_task.common import canonical, strict_json
from disastertrace.forecast_task.public_resolver import resolve


def test_all_noninitial_structured_slots_selected_independent_of_answers(native_fixture):
    public, slots, _ = native_fixture
    rows = design.select("synthetic-native", public, slots)
    base = [
        s
        for s in slots
        if s["method"] == "structured_state"
        and public["opportunities"][s["opportunity_id"]]["previous_checkpoint_ids"]
    ]
    assert len(rows) == 2 * len(base)
    assert {r["source_slot_id"] for r in rows} == {s["slot_id"] for s in base}
    for first, second in zip(rows[::2], rows[1::2]):
        assert first["pair_id"] == second["pair_id"] and first["seed"] == second["seed"]
        assert first["encoding"] == "json" and second["encoding"] == "text"
        assert first["source_trajectory_id"] == second["source_trajectory_id"]


def test_paired_requests_restore_the_identical_native_evidence_and_carrier(native_fixture):
    public, slots, audit = native_fixture
    rows = design.select("synthetic-native", public, slots)
    bound = design.bind("synthetic-native", public, slots, audit, rows)
    for first, second in zip(rows[::2], rows[1::2]):
        a, b = bound[first["slot_id"]], bound[second["slot_id"]]
        assert a["eligible"] and b["eligible"]
        assert a["source_prefix_sha256"] == b["source_prefix_sha256"]
        assert a["messages"] != b["messages"]
        assert design.restore(a["messages"]) == design.restore(b["messages"])
        assert resolve(design.restore(a["messages"])) == resolve(design.restore(b["messages"]))


def test_wrong_source_answer_remains_wrong_in_both_representations(native_fixture):
    public, slots, audit = native_fixture
    rows = design.select("synthetic-native", public, slots)
    for capture in audit["workers"][0]["captures"]:
        answer = strict_json(capture["final_text"])
        answer["max_sustained_wind"] = {"value": -12345, "unit": "wrong-unit"}
        answer["citation"] = {
            "source_id": "superseded-source",
            "forecast_line": 999,
            "wind_line": 1,
        }
        capture["final_text"] = canonical(answer)
    bound = design.bind("synthetic-native", public, slots, audit, rows)
    assert len(bound) == len(rows)
    for data in bound.values():
        carrier = strict_json(design.restore(data["messages"])[1]["content"])["carrier"]
        assert carrier["answer"]["max_sustained_wind"] == {"value": -12345, "unit": "wrong-unit"}
        assert carrier["answer"]["citation"]["source_id"] == "superseded-source"


def test_missing_prefix_is_ineligible_without_removing_planned_branches(native_fixture):
    public, slots, audit = native_fixture
    rows = design.select("synthetic-native", public, slots)
    removed = next(s["slot_id"] for s in slots if s["method"] == "structured_state")
    audit["workers"][0]["captures"] = [
        c for c in audit["workers"][0]["captures"] if c["slot_id"] != removed
    ]
    bound = design.bind("synthetic-native", public, slots, audit, rows)
    missing = [v for v in bound.values() if not v["eligible"]]
    assert missing and len(bound) == len(rows)
    assert all(v["messages"] is None and removed in v["missing_source_slot_ids"] for v in missing)
    assert sum(not v["eligible"] for v in bound.values()) % 2 == 0


def test_invalid_prefix_preserves_the_declared_marker(native_fixture):
    public, slots, audit = native_fixture
    rows = design.select("synthetic-native", public, slots)
    for c in audit["workers"][0]["captures"]:
        c["final_text"] = "not JSON"
    bound = design.bind("synthetic-native", public, slots, audit, rows)
    assert all(v["eligible"] for v in bound.values())
    for v in bound.values():
        carrier = strict_json(design.restore(v["messages"])[1]["content"])["carrier"]
        assert carrier["kind"] == "invalid" and carrier["answer"] is None


@pytest.mark.parametrize(
    "mutation", ["source", "diagnostic", "selection", "capture_origin", "duplicate"]
)
def test_prefix_origin_and_outcome_independent_selection_are_bound(native_fixture, mutation):
    public, slots, original = native_fixture
    audit = deepcopy(original)
    rows = design.select("synthetic-native", public, slots)
    if mutation == "source":
        audit["execution_id"] = "another-experiment"
    elif mutation == "diagnostic":
        audit["kind"] = "diagnostic"
    elif mutation == "selection":
        rows.pop()
    elif mutation == "capture_origin":
        audit["workers"][0]["captures"][0]["origin"] = "public_program_diagnostic"
    else:
        audit["workers"][0]["captures"].append(audit["workers"][0]["captures"][0])
    with pytest.raises(ValueError):
        design.bind("synthetic-native", public, slots, audit, rows)
