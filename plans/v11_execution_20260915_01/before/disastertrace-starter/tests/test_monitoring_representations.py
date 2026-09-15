"""Narrow native views must preserve bounds, missing slots and E/F separation."""

import json
from pathlib import Path

import pytest

from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle
from disastertrace.monitoring_fixed_v1.representations import VERSION, focused_view, model_messages


def fixture():
    root = (
        Path(__file__).resolve().parents[2]
        / "plans/v7_execution_20260913/evidence_bundle/matrix_01"
    )
    rows = json.loads((root / "MANIFEST.json").read_text())
    row = next(r for r in rows if r["condition"] == "fixed_one")
    return EvidenceBundle.restore(
        json.loads((root / "policy" / (row["call_id"] + ".json")).read_text())
    )


def test_focused_E_keeps_native_censoring_and_all_registered_unread_slots():
    bundle = fixture()
    original = bundle.policy_view()
    focus = focused_view(bundle, "e_only")
    assert len(focus["registered_native_slots"]) == len(
        original["baseline"]["content"]["E_question"]["query_ids"]
    )
    source = original["assets"][0]
    slot = next(s for s in focus["registered_native_slots"] if s["disclosure"] == "acquired")
    assert slot["native_sources"][0]["content"] == source["content"]
    assert slot["native_sources"][0]["raw"] == source["raw"]
    assert any(s["disclosure"] == "not_acquired" for s in focus["registered_native_slots"])
    assert "baseline" not in focus and "target" not in focus
    assert "fact_truth" not in json.dumps(focus)


@pytest.mark.parametrize("head", ["joint", "f_only"])
def test_F_views_keep_whole_native_baseline_and_current_state(head):
    bundle = fixture()
    row = bundle.policy_view()
    focused = focused_view(bundle, head)
    assert focused["baseline"] == row["baseline"]
    assert focused["target"] == row["target"]
    assert focused["state"] == row["state"]
    assert json.loads(model_messages(bundle, head, VERSION)[1]["content"]) == focused
