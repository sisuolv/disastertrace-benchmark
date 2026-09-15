"""Native extraction is typed; temperature durations use whole member paths."""

import json

import pytest

from disastertrace.monitoring_v1.feature_tasks import (
    parse_features,
    parse_temperature,
    temperature_ensemble_probability,
)


def test_whole_fence_is_a_predeclared_representation_but_prose_is_rejected():
    value = '{"probability":0.2}'
    assert parse_temperature(value)[0] == parse_temperature("```json\n" + value + "\n```")[0]
    assert parse_temperature("```json\n" + value + "\n```")[1]["whole_json_fence"]
    with pytest.raises(ValueError):
        parse_temperature("Answer: " + value)
    with pytest.raises(ValueError):
        parse_temperature('{"probability":0.2,"probability":0.8}')


def test_claims_cannot_turn_an_unread_slot_or_boolean_bound_into_evidence():
    slot = {
        "visibility": {"lower": True, "upper": 5000, "lower_closed": True, "upper_closed": True},
        "temperature_c": None,
        "dewpoint_c": None,
    }
    with pytest.raises(ValueError):
        parse_features(json.dumps({"slots": {"q": slot}}), ["q"])
    slot["visibility"]["lower"] = 0
    with pytest.raises(ValueError):
        parse_features(json.dumps({"slots": {"q": slot}}), [])


def test_same_member_three_day_event_is_not_a_product_of_marginals():
    day = 86400_000_000
    row = {
        "cutoff": 0,
        "target": {
            "units": "C",
            "physical_start": day,
            "physical_end": 4 * day,
            "variable": "min_of_3_daily_max_2m_temperature",
            "event_operator": "ge",
            "threshold": 30,
        },
        "common": {
            "daily_products": [
                {
                    "target_date": f"1970-01-0{i + 1}",
                    "day_index": i,
                    "forecast_max_members_C": values,
                }
                for i, values in enumerate(([31, 20], [20, 31], [31, 20]), 1)
            ]
        },
    }
    assert temperature_ensemble_probability(row) == 0
    row["common"]["daily_products"][1]["forecast_max_members_C"] = [31, 20]
    assert temperature_ensemble_probability(row) == 0.5
