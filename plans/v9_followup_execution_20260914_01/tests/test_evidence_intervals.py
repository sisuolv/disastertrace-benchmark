"""Independent E reference handles native unbounded and censored reports."""

import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/evidence_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("followup_evidence", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def view(visibility):
    return {
        "cutoff": 2,
        "baseline": {"content": {"E_question": {"query_ids": ["a", "b"], "threshold_m": 1000}}},
        "assets": [{
            "available_at": 1,
            "completed_at": 1,
            "content": {"query_id": "a", "status": "disclosed_product_fact",
                        "reports": [{"visibility": visibility}]},
        }],
    }


@pytest.mark.parametrize("upper", [None, "+inf"])
def test_unbounded_upper_is_not_an_empirical_maximum(upper):
    result = MODULE.independent_reference(view({"lower": 900, "upper": upper,
                                               "lower_closed": True, "upper_closed": False}))
    assert result == {"slots": {"a": "unknown", "b": "unknown"}, "fact_truth": "unknown"}


@pytest.mark.parametrize("closed,expected", [(True, "unknown"), (False, "true")])
def test_censoring_endpoint_changes_strict_threshold_support(closed, expected):
    result = MODULE.independent_reference(view({"lower": 0, "upper": 1000,
                                               "lower_closed": True, "upper_closed": closed}))
    assert result["fact_truth"] == expected


def test_conflicting_interval_is_neither_true_nor_false():
    result = MODULE.independent_reference(view({"lower": 1000, "upper": 1000,
                                               "lower_closed": False, "upper_closed": False}))
    assert result["fact_truth"] == "conflict"
