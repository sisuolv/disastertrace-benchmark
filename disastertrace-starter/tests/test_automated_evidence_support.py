"""Development excerpts plus explicitly synthetic adversarial evidence probes."""

import copy
import json
from pathlib import Path

import pytest

from disastertrace.automated.common import fingerprint
from disastertrace.automated.dynamic import build_episodes
from disastertrace.automated.evidence_support import (
    EVIDENCE_POLICY_VERSION,
    build_evidence_index,
    validate_citation,
)


def synthetic_episode(body="Maximum sustained winds are near 75 mph with higher gusts."):
    records = []
    for number, hour in enumerate((6, 12, 18), 1):
        lines = [
            "SYNTHETIC TEST FIXTURE; NOT AN OFFICIAL OBSERVATION",
            "LOCATION...12.3N 45.6W",
            "MAXIMUM SUSTAINED WINDS...75 MPH...120 KM/H",
            "MINIMUM CENTRAL PRESSURE...990 MB...29.24 INCHES",
            "",
            "DISCUSSION AND OUTLOOK",
            "----------------------",
            *body.splitlines(),
            "",
            "HAZARDS AFFECTING LAND",
            "----------------------",
        ]
        locators = {
            "latitude_deg": 2,
            "longitude_deg": 2,
            "maximum_wind_mph": 3,
            "minimum_pressure_mb": 4,
        }
        records.append(
            {
                "record_id": f"synthetic:{number}",
                "storm_id": "SYNTHETIC_TEST_STORM",
                "storm_name": "Teststorm",
                "issued_at": f"2040-08-01T{hour:02d}:00:00Z",
                "raw_text": "\n".join(lines),
                "fields": {
                    "latitude_deg": 12.3,
                    "longitude_deg": -45.6,
                    "maximum_wind_mph": 75,
                    "minimum_pressure_mb": 990,
                },
                "field_evidence": {
                    field: {"line_start": line, "line_end": line, "text": lines[line - 1]}
                    for field, line in locators.items()
                },
                "provenance": {"source_origin": "synthetic_record", "historical_claim": False},
            }
        )
    return build_episodes(records)[0]


def check(body, field="maximum_wind_mph", value=75, line=8):
    episode = synthetic_episode(body)
    return validate_citation(
        episode, "c4", field, value, {"record_id": "synthetic:3", "line": line}
    )


@pytest.mark.parametrize(
    "body,field,value,line",
    [
        ("Maximum sustained winds are near 75 mph with higher gusts.", "maximum_wind_mph", 75, 8),
        (
            "Maximum sustained winds have increased to near 75 mph (120 km/h) with higher gusts.",
            "maximum_wind_mph",
            75,
            8,
        ),
        (
            "Satellite imagery indicates that maximum sustained winds have\nincreased to near 75 mph (120 km/h) with higher gusts.",
            "maximum_wind_mph",
            75,
            9,
        ),
        (
            "Maximum sustained winds are near\n75 mph (120 km/h) with higher gusts.",
            "maximum_wind_mph",
            75,
            8,
        ),
        (
            "The estimated minimum central pressure is 990 mb (29.24 inches).",
            "minimum_pressure_mb",
            990,
            8,
        ),
        (
            "The latest minimum central pressure estimated from Air Force\nReserve reconnaissance aircraft data is 990 mb (29.24 inches).",
            "minimum_pressure_mb",
            990,
            9,
        ),
        (
            "The estimated minimum central pressure based on data from the NOAA\nHurricane Hunter aircraft is 990 mb (29.24 inches).",
            "minimum_pressure_mb",
            990,
            9,
        ),
        (
            "At 200 PM AST (1800 UTC), the center of Tropical Storm Teststorm was\nlocated near latitude 12.3 North, longitude 45.6 West.",
            "latitude_deg",
            12.3,
            9,
        ),
        (
            "At 200 PM AST (1800 UTC), the eye of Hurricane Teststorm was located\nnear latitude 12.3 North, longitude 45.6 West.",
            "longitude_deg",
            -45.6,
            9,
        ),
        (
            "At 200 PM AST (1800 UTC), the center of Tropical Storm Teststorm was\nlocated by satellite and Martinique radar near latitude 12.3 North,\nlongitude 45.6 West.",
            "longitude_deg",
            -45.6,
            10,
        ),
    ],
)
def test_restricted_current_body_forms_and_wrapped_lines(body, field, value, line):
    result = check(body, field, value, line)
    assert result["valid"], result
    assert result["reason"] == "supported_body_observation"
    assert result["support_spans"][0]["field"] == field


@pytest.mark.parametrize(
    "body",
    [
        "Wind gusts are near 75 mph.",
        "Present movement is near 75 mph.",
        "Maximum sustained winds will be near 75 mph tomorrow.",
        "Maximum sustained winds were near 75 mph yesterday.",
        "Maximum sustained winds are not near 75 mph.",
        "It is false that maximum sustained winds are near 75 mph.",
        "Maximum sustained winds are near 75 mph tomorrow.",
        "Maximum sustained winds are near 75 mph if strengthening occurs.",
        "Maximum sustained winds are near 75 mph at the previous observation.",
        "Maximum sustained winds are near 75 knots.",
        "Maximum sustained winds are near 120 km/h.",
        "Maximum sustained winds are between 70 and 80 mph.",
        "Maximum sustained winds are near 75 mph with a 50 percent probability.",
        "Maximum sustained winds of Hurricane Other are near 75 mph.",
        "For Hurricane Other, maximum sustained winds are near 75 mph.",
        "Yesterday's report follows. Maximum sustained winds are near 75 mph.",
        "Example: Maximum sustained winds are near 75 mph.",
        '"Maximum sustained winds are near 75 mph."',
        "Maximum sustained winds are near 75 mph. These are forecast values.",
        "Maximum sustained winds are near 75 mph. This estimate is for Hurricane Other.",
        "Maximum sustained winds are near 75 mph. The estimate is for hurricane other.",
        "Maximum sustained winds are near 75 mph. This statement is false.",
        "Maximum sustained winds are near 75 mph. Maximum sustained winds are near 70 mph.",
        "Maximum sustained winds are near 75 mph. The observation is from 0600 UTC.",
        "Maximum sustained winds are near 75 mph. Conditions refer to Hurricane Other at 0600 UTC.",
        "Maximum sustained winds are near 75 mph. According to the forecast, that value will occur tomorrow.",
        "Maximum sustained winds are near 75 mph. The estimate describes a future observation.",
    ],
)
def test_unsafe_or_unsupported_body_constructions_fail_closed(body):
    result = check(body)
    assert not result["valid"], result
    assert result["reason"] == "evaluator_unverifiable"


@pytest.mark.parametrize(
    "before,after",
    [
        ("Teststorm", "Other"),
        ("1800 UTC", "1200 UTC"),
        ("200 PM AST", "800 AM AST"),
        ("North", "South"),
        ("West", "East"),
        ("was located", "will be located"),
    ],
)
def test_coordinates_require_entity_time_polarity_and_direction(before, after):
    body = "At 200 PM AST (1800 UTC), the center of Tropical Storm Teststorm was located near latitude 12.3 North, longitude 45.6 West."
    field = "longitude_deg" if before == "West" else "latitude_deg"
    value = -45.6 if field == "longitude_deg" else 12.3
    assert not check(body.replace(before, after), field, value)["valid"]


@pytest.mark.parametrize(
    "field,value,line",
    [
        ("maximum_wind_mph", 75, 3),
        ("latitude_deg", 12.3, 2),
        ("longitude_deg", -45.6, 2),
        ("minimum_pressure_mb", 990, 4),
    ],
)
def test_existing_canonical_summary_citations_remain_supported(field, value, line):
    episode = synthetic_episode()
    result = validate_citation(
        episode, "c4", field, value, {"record_id": "synthetic:3", "line": line}
    )
    assert result["valid"] and result["reason"] == "supported_summary"


@pytest.mark.parametrize(
    "checkpoint,record,reason",
    [
        ("c4", "synthetic:1", "stale_report"),
        ("c3", "synthetic:1", "stale_report"),
        ("c1", "synthetic:3", "future_report"),
        ("c0", "synthetic:1", "future_report"),
        ("c4", "other:3", "unknown_report"),
    ],
)
def test_record_gate_follows_delivered_issue_order(checkpoint, record, reason):
    result = validate_citation(
        synthetic_episode(), checkpoint, "maximum_wind_mph", 75, {"record_id": record, "line": 3}
    )
    assert not result["valid"] and result["reason"] == reason


def test_delayed_arrival_unavailable_even_after_issue_time():
    episode = synthetic_episode()
    episode["checkpoints"][2]["arrivals"] = []
    result = validate_citation(
        episode, "c2", "maximum_wind_mph", 75, {"record_id": "synthetic:2", "line": 3}
    )
    assert result["reason"] == "undelivered_report"
    assert validate_citation(
        episode, "c2", "maximum_wind_mph", 75, {"record_id": "synthetic:1", "line": 3}
    )["valid"]


@pytest.mark.parametrize("line", [0, -1, 1000])
def test_out_of_bounds_citations_rejected(line):
    assert (
        check("Maximum sustained winds are near 75 mph.", line=line)["reason"]
        == "locator_out_of_bounds"
    )


@pytest.mark.parametrize("line", [True, 3.0, "3", None])
def test_non_integer_line_rejected(line):
    assert (
        check("Maximum sustained winds are near 75 mph.", line=line)["reason"] == "invalid_citation"
    )


def test_wrapped_gust_only_line_does_not_support_sustained_wind():
    assert not check("Maximum sustained winds are near 75 mph with higher\ngusts.", line=9)["valid"]


def test_wrong_field_and_source_value_are_not_equivalent_support():
    assert not check("Maximum sustained winds are near 75 mph.", "minimum_pressure_mb", 990)[
        "valid"
    ]
    assert check("Maximum sustained winds are near 75 mph.", value=74)["reason"] == "value_mismatch"
    assert not check("Maximum sustained winds are near 74 mph.")["valid"]


def test_unit_conversion_is_not_an_answer_tolerance():
    assert (
        check("Maximum sustained winds are near 75 mph (120 km/h).", value=120 / 1.609344)["reason"]
        == "value_mismatch"
    )


@pytest.mark.parametrize("value", [True, None, "75", float("nan"), float("inf")])
def test_only_finite_numbers_are_values(value):
    assert (
        check("Maximum sustained winds are near 75 mph.", value=value)["reason"] == "invalid_value"
    )


def test_wrong_entity_unknown_checkpoint_and_unsupported_field_are_explicit():
    episode = synthetic_episode()
    citation = {"record_id": "synthetic:3", "line": 3}
    assert (
        validate_citation(episode, "bad", "maximum_wind_mph", 75, citation)["reason"]
        == "unknown_checkpoint"
    )
    assert (
        validate_citation(episode, "c4", "movement_speed_mph", 75, citation)["reason"]
        == "unsupported_field"
    )
    episode["records"][2]["storm_id"] = "OTHER_SYNTHETIC_STORM"
    assert (
        validate_citation(episode, "c4", "maximum_wind_mph", 75, citation)["reason"]
        == "wrong_entity"
    )


def test_body_sentence_bound_and_wrapped_wrong_field_line():
    body = "Maximum\nsustained\nwinds\nare near\n75 mph."
    assert not check(body)["valid"]
    body = "At 200 PM AST (1800 UTC), the center of Tropical Storm Teststorm was\nlocated near latitude 12.3 North,\nlongitude 45.6 West."
    assert not check(body, "latitude_deg", 12.3, line=10)["valid"]
    assert check(body, "longitude_deg", -45.6, line=10)["valid"]


@pytest.mark.parametrize(
    "before,after,field,value,line",
    [
        ("75 MPH", "75 KT", "maximum_wind_mph", 75, 3),
        ("990 MB", "990 INCHES", "minimum_pressure_mb", 990, 4),
        ("12.3N", "12.3S", "latitude_deg", 12.3, 2),
    ],
)
def test_summary_locator_does_not_bypass_unit_or_direction_checks(
    before, after, field, value, line
):
    episode = synthetic_episode()
    record = episode["records"][2]
    record["raw_text"] = record["raw_text"].replace(before, after)
    for locator in record["field_evidence"].values():
        locator["text"] = locator["text"].replace(before, after)
    assert not validate_citation(
        episode, "c4", field, value, {"record_id": "synthetic:3", "line": line}
    )["valid"]


def test_hazard_section_cannot_supply_observation_support():
    body = (
        "HAZARDS AFFECTING LAND\n----------------------\nMaximum sustained winds are near 75 mph."
    )
    assert not check(body, line=10)["valid"]


def test_same_text_and_locator_move_preserves_body_support():
    episode = synthetic_episode()
    original = validate_citation(
        episode, "c4", "maximum_wind_mph", 75, {"record_id": "synthetic:3", "line": 8}
    )
    episode["records"][2]["raw_text"] = episode["records"][2]["raw_text"].replace(
        "DISCUSSION AND OUTLOOK", "\n\nDISCUSSION AND OUTLOOK"
    )
    moved = validate_citation(
        episode, "c4", "maximum_wind_mph", 75, {"record_id": "synthetic:3", "line": 10}
    )
    assert original["valid"] and moved["valid"]


def test_index_is_json_serializable_deterministic_and_binds_source_schedule_policy():
    episode = synthetic_episode()
    original = copy.deepcopy(episode)
    index = build_evidence_index([episode])
    assert episode == original
    assert json.loads(json.dumps(index)) == index
    assert index == build_evidence_index([episode])
    assert index["policy_version"] == EVIDENCE_POLICY_VERSION
    assert index["episodes"][episode["episode_id"]]["episode_sha256"] == fingerprint(episode)
    citation = {"record_id": "synthetic:3", "line": 8}
    assert validate_citation(episode, "c4", "maximum_wind_mph", 75, citation, index=index)["valid"]
    changed = copy.deepcopy(episode)
    changed["records"][2]["raw_text"] += "\nchanged source"
    assert (
        validate_citation(changed, "c4", "maximum_wind_mph", 75, citation, index=index)["reason"]
        == "index_mismatch"
    )
    changed = copy.deepcopy(index)
    changed["policy_version"] = "unrecognized-policy"
    assert (
        validate_citation(episode, "c4", "maximum_wind_mph", 75, citation, index=changed)["reason"]
        == "index_mismatch"
    )
    changed = copy.deepcopy(episode)
    changed["checkpoints"][2]["arrivals"] = []
    assert (
        validate_citation(changed, "c4", "maximum_wind_mph", 75, citation, index=index)["reason"]
        == "index_mismatch"
    )


def test_duplicate_episode_index_rejected():
    episode = synthetic_episode()
    with pytest.raises(ValueError, match="duplicate episode"):
        build_evidence_index([episode, episode])


def test_index_cannot_inject_an_unsupported_span():
    episode = synthetic_episode("Maximum sustained winds are not near 75 mph.")
    index = build_evidence_index([episode])
    entry = index["episodes"][episode["episode_id"]]["records"]["synthetic:3"]
    fake = copy.deepcopy(
        next(s for s in entry["support_spans"] if s["field"] == "maximum_wind_mph")
    )
    fake.update(line_start=8, line_end=8, citation_lines=[8])
    entry["support_spans"].append(fake)
    assert (
        validate_citation(
            episode,
            "c4",
            "maximum_wind_mph",
            75,
            {"record_id": "synthetic:3", "line": 8},
            index=index,
        )["reason"]
        == "index_mismatch"
    )


def test_actual_development_summary_and_body_excerpts_across_three_storms():
    path = Path(__file__).parents[1] / "work/build-deepseek-v1/episodes/dynamic_episodes.jsonl"
    episodes = [json.loads(line) for line in path.read_text().splitlines()]
    episodes = [
        e for e in episodes if e["split"] == "development" and e["episode_id"].endswith(":base")
    ]
    assert len(episodes) == 3
    records_tested = 0
    for episode in episodes:
        for checkpoint, record in zip(("c1", "c2", "c4"), episode["records"]):
            for field in (
                "maximum_wind_mph",
                "latitude_deg",
                "longitude_deg",
                "minimum_pressure_mb",
            ):
                summary = record["field_evidence"][field]["line_start"]
                result = validate_citation(
                    episode,
                    checkpoint,
                    field,
                    record["fields"][field],
                    {"record_id": record["record_id"], "line": summary},
                )
                assert result["valid"], (record["record_id"], field, result)
                index = build_evidence_index([episode])
                spans = index["episodes"][episode["episode_id"]]["records"][record["record_id"]][
                    "support_spans"
                ]
                bodies = [
                    s for s in spans if s["field"] == field and s["kind"] == "body_observation"
                ]
                assert bodies, (record["record_id"], field)
                for span in bodies:
                    result = validate_citation(
                        episode,
                        checkpoint,
                        field,
                        record["fields"][field],
                        {"record_id": record["record_id"], "line": span["citation_lines"][0]},
                        index=index,
                    )
                    assert result["valid"], result
            records_tested += 1
    assert records_tested == 9
    ida = next(e for e in episodes if e["group_id"] == "AL092021")
    assert validate_citation(
        ida, "c4", "maximum_wind_mph", 105, {"record_id": "nhc-al092021-public-011", "line": 88}
    )["valid"]
