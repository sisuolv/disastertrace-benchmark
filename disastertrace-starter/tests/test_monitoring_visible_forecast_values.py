"""A retained visible probability must not be counted as a new numeric forecast."""

import copy
import importlib.util
from pathlib import Path

import pytest

EXEC = Path(__file__).resolve().parents[2] / "plans/v8_measurement_execution_20260913_01"
spec = importlib.util.spec_from_file_location(
    "visible_forecast_values", EXEC / "scripts/analyze_visible_forecast_values.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def retained():
    report = {
        "calls": [
            {
                "call_id": "c1",
                "opportunity_id": "o1",
                "head": "joint",
                "admission_status": "accepted",
                "proposed_probability": 0.2,
                "bundle": {
                    "payload": {
                        "baseline": {"forecast": {"value": 0.8}},
                        "state": {"forecast": {"value": 0.2}, "mode": "OVERRIDE"},
                    }
                },
            }
        ],
        "snapshots": [
            {
                "opportunity_id": "o1",
                "forecast": {"value": 0.2},
                "base_forecast": {"value": 0.8},
                "override_call_id": "c1",
                "mode": "OVERRIDE",
            }
        ],
    }
    scored = [
        {
            "opportunity_id": "o1",
            "prediction": 0.2,
            "base": 0.8,
            "gain_vs_common_base": -0.6,
        }
    ]
    return report, scored


def test_retained_value_can_differ_from_baseline_without_new_numeric_proposal(retained):
    report, scored = retained
    original = copy.deepcopy(report)
    summary, calls, positions = module.describe(report, scored, -0.6)
    assert summary["model_proposals_differ_from_dispatch_baseline"] == 1
    assert summary["model_proposals_differ_from_both_visible_probabilities"] == 0
    assert summary["model_proposals_equal_visible_state"] == 1
    assert calls[0]["value_match"] == "matches_visible_state_only"
    assert positions[0]["category"] == "model_matches_visible_state_only"
    assert summary["gain_contributions_to_full_mature_mean"] == {
        "model_matches_visible_state_only": -0.6
    }
    assert report == original


def test_current_baseline_choice_remains_distinct_from_retaining_state():
    assert module.value_match(0.8, 0.8, 0.2) == "matches_dispatch_baseline_only"
    assert module.value_match(0.3, 0.8, 0.2) == "differs_from_both"


def test_same_value_override_is_not_relabelled_follow(retained):
    report, scored = retained
    report["calls"][0]["bundle"]["payload"]["baseline"]["forecast"]["value"] = 0.2
    report["snapshots"][0]["base_forecast"]["value"] = 0.2
    scored[0].update(base=0.2, gain_vs_common_base=0)
    summary, _, positions = module.describe(report, scored, 0)
    assert summary["call_value_matches"]["model"] == {"matches_both": 1}
    assert positions[0]["category"] == "model_matches_both"


def test_unparsed_answer_is_retained_but_cannot_be_effective_override(retained):
    report, scored = retained
    report["calls"][0]["proposed_probability"] = None
    report["calls"][0]["admission_status"] = "invalid"
    with pytest.raises(ValueError, match="accepted proposal"):
        module.describe(report, scored, -0.6)
    report["snapshots"][0].update(mode="FOLLOW", override_call_id=None)
    report["snapshots"][0]["forecast"]["value"] = 0.8
    scored[0].update(prediction=0.8, gain_vs_common_base=0)
    summary, _, _ = module.describe(report, scored, 0)
    assert summary["model_forecast_calls"] == 1
    assert summary["call_value_matches"]["model"] == {"no_parsed_probability": 1}


def test_cutoff_denominator_and_independent_score_cannot_be_changed(retained):
    report, scored = retained
    with pytest.raises(ValueError, match="full-denominator score"):
        module.describe(report, scored, 0.1)
    with pytest.raises(ValueError, match="Duplicate scored opportunity"):
        module.describe(report, scored * 2, -0.6)
    report["snapshots"] = []
    with pytest.raises(ValueError, match="Lost cutoff denominator"):
        module.describe(report, scored, -0.6)


def test_nonprobabilities_are_rejected():
    for invalid in (True, float("nan"), float("inf"), -0.1, 1.1):
        with pytest.raises(ValueError, match="finite probability"):
            module.value_match(invalid, 0.2, 0.3)
