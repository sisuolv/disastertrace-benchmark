"""Whole member paths, physical min/max ordering and fixed future days survive calibration."""

import copy

import pytest

from disastertrace.monitoring_v1.temperature_postprocess import ecc_products, event_probability


def row():
    day = 86400_000_000
    return {
        "cutoff": 0,
        "target": {
            "physical_start": day,
            "physical_end": 4 * day,
            "units": "C",
            "variable": "min_of_3_daily_max_2m_temperature",
            "event_operator": "ge",
            "threshold": 30,
        },
        "common": {
            "daily_products": [
                {
                    "day_index": i,
                    "target_date": f"1970-01-0{i + 1}",
                    "forecast_max_members_C": maximum,
                    "forecast_min_members_C": [0, 1],
                }
                for i, maximum in enumerate(([31, 20], [20, 31], [31, 20]), 1)
            ]
        },
    }


def test_spells_are_same_member_predicates_before_and_after_transforms():
    original = row()
    assert event_probability(original) == 0
    original["common"]["daily_products"][1]["forecast_max_members_C"] = [31, 20]
    assert event_probability(original) == 0.5


def test_member_rank_coupling_and_minmax_projection_are_explicit():
    original = row()
    bank = {
        "max": {"a": 0, "b": 1, "log_c": 0, "log_d": 0},
        "min": {"a": 100, "b": 1, "log_c": 0, "log_d": 0},
    }
    converted, trace = ecc_products(original["common"]["daily_products"], bank)
    assert trace["minmax_projections"] > 0
    assert all(
        lo <= hi
        for p in converted
        for lo, hi in zip(p["forecast_min_members_C"], p["forecast_max_members_C"], strict=True)
    )
    assert original == row()


@pytest.mark.parametrize("failure", ["rolling_day", "day0", "duplicate_date", "missing_member"])
def test_invalid_temporal_or_member_support_is_rejected(failure):
    broken = copy.deepcopy(row())
    if failure == "rolling_day":
        broken["target"]["physical_start"] += 1
        broken["target"]["physical_end"] += 1
    elif failure == "day0":
        broken["common"]["daily_products"][0]["day_index"] = 0
    elif failure == "duplicate_date":
        broken["common"]["daily_products"].append(broken["common"]["daily_products"][0])
    else:
        broken["common"]["daily_products"][0]["forecast_max_members_C"].pop()
    with pytest.raises(ValueError):
        event_probability(broken)
