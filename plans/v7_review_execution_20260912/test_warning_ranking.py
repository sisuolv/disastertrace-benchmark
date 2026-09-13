"""Known tie, ordering and missing-label counterexamples for ranking reports."""

import pytest
from analyze_warning_ranking import ranking


def rows(probabilities, outcomes):
    return [{"prediction": p, "outcome": y} for p, y in zip(probabilities, outcomes, strict=True)]


def test_constant_forecast_has_prevalence_ap_and_half_roc():
    result = ranking(rows([0.0] * 4, [1, 0, 0, 0]))
    assert result["average_precision"] == 0.25
    assert result["roc_auc"] == 0.5
    assert result["fixed_thresholds"][0]["recall"] == 0
    assert result["fixed_thresholds"][0]["precision"] is None


def test_tied_scores_do_not_gain_from_input_label_order():
    first = ranking(rows([0.5, 0.5], [1, 0]))
    second = ranking(rows([0.5, 0.5], [0, 1]))
    assert first == second
    assert first["average_precision"] == 0.5


def test_known_nonperfect_ordering_matches_exact_pair_counts():
    result = ranking(rows([0.9, 0.8, 0.7], [0, 1, 1]))
    assert result["average_precision"] == pytest.approx((1 / 2 + 2 / 3) / 2)
    assert result["roc_auc"] == 0


def test_missing_and_no_positive_labels_do_not_create_an_auc():
    result = ranking(rows([0.2, 0.1, 1.0], [0, 0, None]))
    assert result["missing"] == 1 and result["settled"] == 2
    assert result["average_precision"] is None
    assert result["roc_auc"] is None
    assert result["fixed_thresholds"][0]["recall"] is None
