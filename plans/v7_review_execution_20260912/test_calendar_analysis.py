"""Regression cases for paired denominators and correlated forecast opportunities."""

import pytest
from analyze_calendar import calendar_sensitivity, paired_gain, reliability

HOUR = 3_600_000_000


def row(ident, target, time, p, y):
    return {"opportunity_id": ident, "target_id": target, "physical_start": time,
            "prediction": p, "outcome": y}


def test_paired_gain_rejects_different_masks_and_opportunity_sets():
    a = [row("a", "one", 0, 0.2, 0)]
    with pytest.raises(ValueError, match="opportunity"):
        paired_gain(a, [row("b", "one", 0, 0.2, 0)])
    with pytest.raises(ValueError, match="outcome"):
        paired_gain(a, [row("a", "one", 0, 0.2, None)])


def test_missing_result_bounds_use_the_same_unobserved_binary_outcome():
    a = [row("a", "one", 0, 0.2, None)]
    b = [row("a", "one", 0, 0.8, None)]
    result = paired_gain(a, b)
    assert result["mean_gain"] is None
    assert result["full_population_gain_bounds"] == pytest.approx([-0.6, 0.6])


def test_missing_bounds_keep_the_shared_outcome_across_repeated_leads():
    a = [row("lead1", "one", 0, 0.2, None), row("lead3", "one", 0, 0.8, None)]
    b = [row("lead1", "one", 0, 0.8, None), row("lead3", "one", 0, 0.2, None)]
    assert paired_gain(a, b)["full_population_gain_bounds"] == pytest.approx([0.0, 0.0])


def test_repeated_leads_stay_in_same_target_time_block():
    rows = [row("lead1", "one", HOUR, 0.1, 1),
            row("lead3", "one", HOUR, 0.1, 1),
            row("later", "two", 25 * HOUR, 0.1, 0)]
    for r, gain in zip(rows, [0.2, 0.2, -0.1]):
        r["gain"] = gain
    result = calendar_sensitivity(rows, block_hours=24, draws=32)
    assert result["calendar_blocks"] == 2
    assert result["unique_targets"] == 2
    assert sorted(r["opportunities"] for r in result["blocks"]) == [1, 2]
    assert result["mean_gain"] == pytest.approx(0.1)
    assert result["independent_process_claim"] is False


def test_reliability_includes_one_boundary_and_omits_missing_labels():
    rows = [row("a", "one", 0, 1.0, 1), row("b", "two", 0, 0.0, 0),
            row("c", "three", 0, 0.5, None)]
    result = reliability(rows)
    assert result["settled"] == 2
    assert result["missing"] == 1
    assert result["binned_ece"] == 0
    assert len(result["bins"]) == 2
