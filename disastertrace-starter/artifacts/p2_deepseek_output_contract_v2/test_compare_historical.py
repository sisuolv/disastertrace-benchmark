import json
from copy import deepcopy
from pathlib import Path

import pytest
from compare_historical import compare_reports


@pytest.fixture
def reports():
    path = (
        Path(__file__).resolve().parents[1]
        / "p2_deepseek_development_v1/runtime/report/report.json"
    )
    before = json.loads(path.read_text())
    return before, deepcopy(before)


def test_unchanged_report_has_zero_metric_changes(reports):
    result = compare_reports(*reports)
    assert result["metric_denominators_checked"] == 321
    assert result["checkpoint_opportunities_checked"] == 270
    assert result["causal_effect_estimated"] is False
    for method in result["methods"].values():
        assert sum(method["matched_checkpoint_outcomes"].values()) == 90
        assert method["matched_checkpoint_outcomes"]["v2_only_correct"] == 0
        assert method["matched_checkpoint_outcomes"]["v1_only_correct"] == 0
        assert all(row["numerator_change_v2_minus_v1"] == 0 for row in method["metrics"].values())


def test_diagnostic_origin_is_rejected(reports):
    reports[1]["mode"] = "injected_transport_unverified"
    with pytest.raises(ValueError, match="actual model captures"):
        compare_reports(*reports)


def test_list_nested_denominator_drift_is_rejected(reports):
    for report in reports:
        report["methods"]["snapshot"]["fixture_nested"] = [
            {"metric": {"numerator": 1, "denominator": 2, "value": 0.5}}
        ]
    reports[1]["methods"]["snapshot"]["fixture_nested"][0]["metric"]["denominator"] = 3
    with pytest.raises(ValueError, match="metric opportunity denominators"):
        compare_reports(*reports)


@pytest.mark.parametrize("drift", ["identity", "opportunity", "duplicate"])
def test_checkpoint_alignment_is_required(reports, drift):
    rows = reports[1]["methods"]["snapshot"]["per_checkpoint"]
    if drift == "identity":
        rows[0]["checkpoint_id"] = "different-checkpoint"
        message = "checkpoint identities"
    elif drift == "opportunity":
        rows[0]["counts"]["known"] += 1
        message = "checkpoint opportunities"
    else:
        rows[1] = deepcopy(rows[0])
        message = "90 distinct"
    with pytest.raises(ValueError, match=message):
        compare_reports(*reports)
