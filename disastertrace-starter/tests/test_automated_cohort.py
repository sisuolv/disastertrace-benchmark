"""Synthetic event fixtures test grouping without claiming archived observations."""

import hashlib
from copy import deepcopy

import pytest

from disastertrace.automated.cohort import build_cohort, summarize_events
from disastertrace.automated.dynamic import run_episode


@pytest.fixture
def cohort_input():
    events, records = [], []
    for event_number, split in enumerate(("development", "heldout", "heldout"), 1):
        storm_id = f"AL{event_number:02d}2040"
        source_ids = [f"synthetic:{storm_id}:{number}" for number in (9, 10, 11)]
        event = {
            "storm_id": storm_id,
            "storm_name": f"SYNTHETIC_{event_number}",
            "split": split,
            "advisory_numbers": ["9", "10", "11"],
            "source_ids": source_ids,
        }
        events.append(event)
        for index, (number, wind) in enumerate(zip((9, 10, 11), (85, 105, 115))):
            latitude, longitude, pressure = 20.0 + index, -80.0 - index, 980 - index * 10
            lines = [
                f"SYNTHETIC UNIT TEST: {storm_id} ADVISORY {number}; NOT OFFICIAL",
                f"LOCATION...{latitude}N {abs(longitude)}W",
                f"MAXIMUM SUSTAINED WINDS...{wind} MPH",
                f"MINIMUM CENTRAL PRESSURE...{pressure} MB",
            ]
            text = "\n".join(lines)
            fields = {
                "maximum_wind_mph": wind,
                "latitude_deg": latitude,
                "longitude_deg": longitude,
                "minimum_pressure_mb": pressure,
            }
            locators = {
                "maximum_wind_mph": 3,
                "latitude_deg": 2,
                "longitude_deg": 2,
                "minimum_pressure_mb": 4,
            }
            records.append(
                {
                    "record_id": source_ids[index],
                    "source_id": source_ids[index],
                    "storm_id": storm_id,
                    "storm_name": event["storm_name"],
                    "advisory_number": str(number),
                    "issued_at": f"2040-08-{event_number:02d}T{6 + 6 * index:02d}:00:00Z",
                    "raw_text": text,
                    "fields": fields,
                    "field_evidence": {
                        name: {"line_start": line, "line_end": line, "text": lines[line - 1]}
                        for name, line in locators.items()
                    },
                    "provenance": {
                        "source_origin": "synthetic_record",
                        "historical_claim": False,
                        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    },
                }
            )
    return records, {
        "schema_version": "nhc_cohort_catalogue_v1",
        "cohort_id": "synthetic-tests-v1",
        "planned_event_count": 3,
        "advisories_per_event": 3,
        "events": events,
        "selection_basis": "synthetic_test_only",
    }


def traces_for(episodes, backend="rule", max_queries=5):
    return [
        row
        for episode in episodes
        for row in run_episode(episode, backend, max_queries=max_queries)
    ]


def test_build_admits_whole_events_and_preserves_frozen_assignments(cohort_input):
    records, catalogue = cohort_input
    original = deepcopy(cohort_input)
    cohort = build_cohort(list(reversed(records)), catalogue)
    assert cohort_input == original
    assert cohort["profile"]["candidate_event_count"] == 3
    assert cohort["profile"]["admitted_event_count"] == 3
    assert cohort["profile"]["provided_record_count"] == 9
    assert cohort["profile"]["episode_count"] == 6
    assert cohort["profile"]["checkpoint_count"] == 30
    assert cohort["profile"]["new_human_reviews"] == 0
    assert cohort["profile"]["model_result_based_filtering"] is False
    assert cohort["split_manifest"]["splits"]["heldout"]["admitted_event_ids"] == [
        "AL022040",
        "AL032040",
    ]
    for event in catalogue["events"]:
        pair = [ep for ep in cohort["episodes"] if ep["group_id"] == event["storm_id"]]
        assert len(pair) == 2
        assert {ep["split"] for ep in pair} == {event["split"]}
        assert {ep["branch"] for ep in pair} == {"base", "delay"}
        assert all(ep["source_origin"] == "synthetic_record" for ep in pair)
        assert all(ep["schedule_origin"] == "controlled_release" for ep in pair)
        assert all(ep["content_edits"] is False for ep in pair)
    cohort["episodes"][0]["records"][0]["fields"]["maximum_wind_mph"] = -1
    assert cohort_input == original


def test_missing_sources_quarantine_whole_storm_without_reassignment(cohort_input):
    records, catalogue = cohort_input
    cohort = build_cohort(records[2:], catalogue)
    assert cohort["profile"]["candidate_event_count"] == 3
    assert cohort["profile"]["admitted_event_count"] == 2
    assert cohort["profile"]["quarantined_event_count"] == 1
    outcome = cohort["profile"]["event_outcomes"][0]
    assert outcome["status"] == "quarantined"
    assert outcome["split"] == "development"
    assert len(outcome["rejection_reasons"]) == 2
    assert {reason["code"] for reason in outcome["rejection_reasons"]} == {"PLANNED_SOURCE_MISSING"}
    assert cohort["split_manifest"]["splits"]["development"]["admitted_event_ids"] == []
    assert cohort["split_manifest"]["splits"]["heldout"]["admitted_event_count"] == 2


def test_archive_storm_name_casing_does_not_change_identity(cohort_input):
    records, catalogue = cohort_input
    records[0]["storm_name"] = records[0]["storm_name"].title()
    result = build_cohort(records, catalogue)
    assert result["profile"]["admitted_event_count"] == 3
    assert result["episodes"][0]["records"][0]["storm_name"] == "Synthetic_1"


@pytest.mark.parametrize(
    "field,value",
    [
        ("record_id", "wrong"),
        ("storm_id", "AL992040"),
        ("storm_name", "OTHER"),
        ("advisory_number", "12"),
    ],
)
def test_record_must_match_each_planned_identity_component(cohort_input, field, value):
    records, catalogue = cohort_input
    records[0][field] = value
    result = build_cohort(records, catalogue)
    assert result["profile"]["admitted_event_count"] == 2
    assert (
        result["profile"]["event_outcomes"][0]["rejection_reasons"][0]["code"]
        == "PLANNED_IDENTITY_MISMATCH"
    )


@pytest.mark.parametrize("kind", ["source", "record", "unplanned"])
def test_ambiguous_inventory_is_fatal(cohort_input, kind):
    records, catalogue = cohort_input
    if kind == "source":
        records.append(deepcopy(records[0]))
    elif kind == "record":
        records[1]["record_id"] = records[0]["record_id"]
    else:
        records[0]["source_id"] = "unplanned"
    with pytest.raises(ValueError, match="duplicate|unplanned"):
        build_cohort(records, catalogue)


@pytest.mark.parametrize(
    "mutation",
    [
        "count",
        "empty",
        "duplicate_event",
        "duplicate_source",
        "split",
        "nonconsecutive",
        "number_type",
    ],
)
def test_invalid_frozen_catalogue_is_fatal(cohort_input, mutation):
    records, catalogue = cohort_input
    if mutation == "count":
        catalogue["planned_event_count"] = 4
    elif mutation == "empty":
        catalogue["events"] = []
    elif mutation == "duplicate_event":
        catalogue["events"][1]["storm_id"] = catalogue["events"][0]["storm_id"]
    elif mutation == "duplicate_source":
        catalogue["events"][1]["source_ids"][0] = catalogue["events"][0]["source_ids"][0]
    elif mutation == "split":
        catalogue["events"][0]["split"] = "training"
    elif mutation == "nonconsecutive":
        catalogue["events"][0]["advisory_numbers"] = ["9", "11", "12"]
    else:
        catalogue["events"][0]["advisory_numbers"][0] = 9
    with pytest.raises(ValueError):
        build_cohort(records, catalogue)


def test_cross_split_identical_text_quarantines_both_events(cohort_input):
    records, catalogue = cohort_input
    records[3]["raw_text"] = records[0]["raw_text"]
    records[3]["provenance"]["source_sha256"] = records[0]["provenance"]["source_sha256"]
    result = build_cohort(records, catalogue)
    assert result["profile"]["admitted_event_count"] == 1
    assert result["profile"]["rejection_counts"]["CROSS_SPLIT_SOURCE_DUPLICATE"] == 2
    assert result["split_manifest"]["splits"]["development"]["admitted_event_count"] == 0
    assert result["split_manifest"]["splits"]["heldout"]["admitted_event_ids"] == ["AL032040"]


@pytest.mark.parametrize(
    "kind,code",
    [
        ("hash", "SOURCE_HASH_MISMATCH"),
        ("provenance", "SOURCE_PROVENANCE_MISSING"),
        ("origin", "SOURCE_ORIGIN_UNSUPPORTED"),
        ("naive", "ISSUE_TIME_INVALID"),
        ("backward", "NONINCREASING_ADVISORY_TIME"),
        ("same_instant", "NONINCREASING_ADVISORY_TIME"),
        ("year", "MIXED_YEAR_SCOPE"),
        ("locator", "EPISODE_CONTRACT_REJECTED"),
        ("too_close", "EPISODE_CONTRACT_REJECTED"),
    ],
)
def test_unsafe_record_or_timing_is_quarantined(cohort_input, kind, code):
    records, catalogue = cohort_input
    if kind == "hash":
        records[0]["raw_text"] += " edited"
    elif kind == "provenance":
        records[0].pop("provenance")
    elif kind == "origin":
        records[0]["provenance"]["source_origin"] = "unknown"
    elif kind == "naive":
        records[0]["issued_at"] = "2040-08-01T06:00:00"
    elif kind == "backward":
        records[0]["issued_at"] = "2040-08-01T13:00:00Z"
    elif kind == "same_instant":
        records[1]["issued_at"] = "2040-08-01T07:00:00+01:00"
    elif kind == "year":
        records[2]["issued_at"] = "2041-08-01T18:00:00Z"
    elif kind == "locator":
        records[0]["field_evidence"]["maximum_wind_mph"]["text"] = "wrong"
    else:
        records[2]["issued_at"] = "2040-08-01T12:00:30Z"
    result = build_cohort(records, catalogue)
    assert result["profile"]["admitted_event_count"] == 2
    assert code in result["profile"]["rejection_counts"]


def test_no_accepted_sources_preserves_all_candidates(cohort_input):
    _, catalogue = cohort_input
    result = build_cohort([], catalogue)
    assert result["episodes"] == []
    assert result["profile"]["candidate_event_count"] == 3
    assert result["profile"]["quarantined_event_count"] == 3
    assert result["profile"]["rejection_counts"] == {"PLANNED_SOURCE_MISSING": 9}


def test_event_macro_keeps_storm_as_independent_unit(cohort_input):
    episodes = build_cohort(*cohort_input)["episodes"]
    result = summarize_events(episodes, traces_for(episodes))
    assert result["n_events"] == 3
    assert result["n_episodes"] == 6
    assert result["n_checkpoints"] == 30
    assert result["overall"]["event_macro"]["grounded_state"] == {
        "value": 1.0,
        "n_events_defined": 3,
        "n_events_total": 3,
        "numerator_sum": 150,
        "denominator_sum": 150,
    }
    assert result["by_split"]["development"]["n_events"] == 1
    assert result["by_split"]["heldout"]["n_events"] == 2
    assert result["overall"]["paired_delay_minus_base"]["grounded_state"] == {
        "value": 0.0,
        "n_paired_events_defined": 3,
        "n_paired_events_total": 3,
    }
    assert result["confidence_intervals"] is None
    assert result["eligible_for_llm_leaderboard"] is False


def test_missing_event_traces_still_count_in_event_macro(cohort_input):
    episodes = build_cohort(*cohort_input)["episodes"]
    result = summarize_events(episodes, traces_for(episodes[:2]))
    metric = result["overall"]["event_macro"]["grounded_state"]
    assert metric["value"] == pytest.approx(1 / 3)
    assert metric["n_events_defined"] == 3
    assert metric["numerator_sum"] == 50
    assert metric["denominator_sum"] == 150
    conditional = result["overall"]["event_macro"]["required_change_success"]
    assert conditional["n_events_defined"] == 1
    assert conditional["n_events_total"] == 3
    assert conditional["value"] == 1.0
    assert result["overall"]["status_counts"] == {"ok": 10, "missing": 20}


def test_explicit_split_selection_enforced_and_extra_traces_not_dropped(cohort_input):
    episodes = build_cohort(*cohort_input)["episodes"]
    traces = traces_for(episodes)
    with pytest.raises(ValueError, match="outside"):
        summarize_events(episodes, traces, expected_split="heldout")
    with pytest.raises(ValueError, match="unknown or duplicate"):
        summarize_events(episodes[2:], traces, expected_split="heldout")
    result = summarize_events(episodes[2:], traces[10:], expected_split="heldout")
    assert result["n_events"] == 2
    assert result["selected_splits"] == ["heldout"]


def test_conditional_event_macro_does_not_weight_events_by_opportunities(cohort_input):
    episodes = build_cohort(*cohort_input)["episodes"]
    traces = traces_for(episodes[:2], "rule") + traces_for(episodes[2:4], "no-update")
    result = summarize_events(episodes, traces)
    macro = result["overall"]["event_macro"]["required_change_success"]
    assert macro["value"] == 0.5
    assert macro["n_events_defined"] == 2
    assert macro["n_events_total"] == 3
    assert macro["numerator_sum"] == 24
    assert macro["denominator_sum"] == 56
    assert result["overall"]["pooled_metrics"]["required_change_success"]["value"] == pytest.approx(
        24 / 56
    )


@pytest.mark.parametrize(
    "mutation", ["empty", "duplicate", "unpaired", "cross_split", "wrong_branch", "unknown_split"]
)
def test_scoring_rejects_ambiguous_event_population(cohort_input, mutation):
    episodes = build_cohort(*cohort_input)["episodes"]
    if mutation == "empty":
        episodes = []
    elif mutation == "duplicate":
        episodes.append(deepcopy(episodes[0]))
    elif mutation == "unpaired":
        episodes.pop()
    elif mutation == "cross_split":
        episodes[1]["split"] = "heldout"
    elif mutation == "wrong_branch":
        episodes[1]["branch"] = "base"
    else:
        episodes[0]["split"] = "unknown"
    with pytest.raises(ValueError):
        summarize_events(episodes, [])


def test_budget_exhaustion_keeps_all_event_and_attempt_denominators(cohort_input):
    episodes = build_cohort(*cohort_input)["episodes"]
    result = summarize_events(episodes, traces_for(episodes, max_queries=0))
    assert result["overall"]["event_macro"]["grounded_state"]["value"] == 0.0
    assert result["overall"]["pooled_metrics"]["action_accuracy"]["denominator"] == 30
    assert result["overall"]["status_counts"] == {"budget_exhausted": 30}
    assert result["overall"]["event_macro"]["preservation"]["value"] is None
    assert result["overall"]["event_macro"]["preservation"]["n_events_defined"] == 0


def test_bad_last_arrival_control_detected_per_event_and_paired(cohort_input):
    episodes = build_cohort(*cohort_input)["episodes"]
    result = summarize_events(episodes, traces_for(episodes, "last-arrival"))
    assert result["overall"]["event_macro"]["grounded_state"]["value"] == pytest.approx(42 / 50)
    assert result["overall"]["pooled_metrics"]["action_accuracy"]["numerator"] == 24
    for row in result["per_event"]:
        assert row["metrics"]["grounded_state"]["numerator"] == 42
        assert row["paired_branches"]["base"]["metrics"]["grounded_state"]["numerator"] == 21
        assert row["paired_branches"]["delay"]["metrics"]["grounded_state"]["numerator"] == 21
