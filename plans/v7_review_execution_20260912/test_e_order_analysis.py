"""Regression checks for pairing reordered E diagnostic outputs by identity."""

import pytest
from analyze_e_order import compare_calls, index_cases


def call(case, status, raw=None, error=None):
    return {"case_id": case, "reported_e": status, "raw": raw or str(status), "error": error}


def test_permuting_case_order_does_not_create_prediction_changes():
    labels = {"a": "supported", "b": "refuted"}
    original = index_cases([call("a", "supported"), call("b", "refuted")])
    reordered = index_cases([call("b", "refuted"), call("a", "supported")])
    result = compare_calls(reordered, original, labels)
    assert result["both_correct"] == 2
    assert result["status_changed"] == result["raw_changed"] == 0
    assert result["net_correct_change"] == 0


def test_unchanged_accuracy_retains_opposing_case_changes_and_raw_differences():
    labels = {"a": "supported", "b": "refuted", "c": "undetermined"}
    original = index_cases([call("a", "refuted"), call("b", "refuted"), call("c", "undetermined", "first")])
    reordered = index_cases([call("c", "undetermined", "second"), call("a", "supported"), call("b", "supported")])
    result = compare_calls(reordered, original, labels)
    assert result["net_correct_change"] == 0
    assert result["candidate_only_correct"] == result["reference_only_correct"] == 1
    assert result["status_changed"] == 2
    assert result["raw_changed"] == 3


def test_lost_or_duplicate_cases_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        index_cases([call("a", "supported"), call("a", "refuted")])
    with pytest.raises(ValueError, match="Paired cases differ"):
        compare_calls({"a": call("a", "supported")}, {}, {"a": "supported"})
