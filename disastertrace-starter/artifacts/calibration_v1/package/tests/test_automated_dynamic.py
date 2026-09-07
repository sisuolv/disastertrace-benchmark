"""Independent controlled fixtures; no fixture represents a historical NHC report."""

import json
from copy import deepcopy

import pytest

from disastertrace.automated.common import fingerprint
from disastertrace.automated.dynamic import (
    FIELDS,
    build_episodes,
    diagnostic_response,
    parse_decision,
    reference_at,
    render_request,
    run_episode,
    score_dynamic,
    validate_episode,
)


@pytest.fixture
def records():
    result = []
    examples = [
        ("2040-08-01T06:00:00Z", 85, 23.5, -83.2, 985),
        ("2040-08-01T12:00:00Z", 105, 24.1, -84.3, 972),
        ("2040-08-01T18:00:00Z", 115, 25.2, -85.1, 963),
    ]
    for number, (issued_at, wind, latitude, longitude, pressure) in enumerate(examples, 1):
        lines = [
            "SYNTHETIC UNIT-TEST REPORT; NOT AN OFFICIAL ADVISORY",
            f"LOCATION...{latitude}N {abs(longitude)}W",
            f"MAXIMUM SUSTAINED WINDS...{wind} MPH",
            f"MINIMUM CENTRAL PRESSURE...{pressure} MB",
        ]
        locators = {
            "maximum_wind_mph": 3,
            "latitude_deg": 2,
            "longitude_deg": 2,
            "minimum_pressure_mb": 4,
        }
        result.append(
            {
                "record_id": f"synthetic:report:{number}",
                "storm_id": "SYNTHETIC_TEST_STORM",
                "issued_at": issued_at,
                "raw_text": "\n".join(lines),
                "fields": {
                    "maximum_wind_mph": wind,
                    "latitude_deg": latitude,
                    "longitude_deg": longitude,
                    "minimum_pressure_mb": pressure,
                },
                "field_evidence": {
                    field: {"line_start": line, "line_end": line, "text": lines[line - 1]}
                    for field, line in locators.items()
                },
                "provenance": {"source_origin": "synthetic_record", "historical_claim": False},
            }
        )
    return result


@pytest.fixture
def episodes(records):
    return build_episodes(records)


def expected_decision(report_number=None):
    """Hand-specified expectations do not invoke either scorer or text parser."""
    state = {name: {"status": "unknown", "value": None, "evidence": []} for name in FIELDS}
    if report_number is None:
        return {"state": state, "action": "request_evidence"}
    values = {
        1: (85, 23.5, -83.2, 985),
        2: (105, 24.1, -84.3, 972),
        3: (115, 25.2, -85.1, 963),
    }
    for field, value, line in zip(FIELDS[:-1], values[report_number], (3, 2, 2, 4)):
        state[field] = {
            "status": "known",
            "value": value,
            "evidence": [{"record_id": f"synthetic:report:{report_number}", "line": line}],
        }
    return {"state": state, "action": "prepare" if report_number in (2, 3) else "monitor"}


def submitted(episode, decisions):
    return {
        (episode["episode_id"], f"c{index}"): {
            "raw_response": json.dumps(decision) if isinstance(decision, dict) else decision,
        }
        for index, decision in enumerate(decisions)
    }


def test_build_sorts_records_and_only_changes_declared_delivery_schedule(records):
    original = deepcopy(records)
    base, delay = build_episodes(list(reversed(records)))
    assert records == original
    assert [row["record_id"] for row in base["records"]] == [
        "synthetic:report:1",
        "synthetic:report:2",
        "synthetic:report:3",
    ]
    assert base["records"] == delay["records"] == original
    assert base["content_edits"] is False
    assert base["schedule_origin"] == "controlled_release"
    assert base["task_semantics"] == "latest_available_report_not_same_valid_time_forecast_revision"
    assert base["policy"]["threshold"] == 100
    assert base["source_origin"] == delay["source_origin"] == "synthetic_record"
    assert base["gold_origin"] == delay["gold_origin"] == "generated_by_spec"
    assert base["checkpoints"][2]["arrivals"] == ["synthetic:report:2"]
    assert delay["checkpoints"][2]["arrivals"] == []
    assert delay["checkpoints"][3]["arrivals"] == ["synthetic:report:2", "synthetic:report:1"]
    assert base["group_id"] == delay["group_id"]
    assert base["episode_id"] != delay["episode_id"]


@pytest.mark.parametrize(
    "arm,expected_reports",
    [
        (0, (None, 1, 2, 2, 3)),
        (1, (None, 1, 1, 2, 3)),
    ],
)
def test_references_follow_branch_visible_latest_issue(episodes, arm, expected_reports):
    for index, report in enumerate(expected_reports):
        assert reference_at(episodes[arm], f"c{index}") == expected_decision(report)


@pytest.mark.parametrize("mutation", ["mixed", "missing", "unrecognized"])
def test_builder_rejects_ambiguous_source_provenance(records, mutation):
    if mutation == "mixed":
        records[1]["provenance"]["source_origin"] = "official_record"
    elif mutation == "missing":
        del records[1]["provenance"]["source_origin"]
    else:
        records[1]["provenance"]["source_origin"] = "unverified_claim"
    with pytest.raises(ValueError):
        build_episodes(records)


def test_same_value_in_new_report_preserves_semantics_but_updates_grounding(records):
    third = records[2]
    third["fields"]["maximum_wind_mph"] = 105
    third["raw_text"] = third["raw_text"].replace("115 MPH", "105 MPH")
    third["field_evidence"]["maximum_wind_mph"]["text"] = "MAXIMUM SUSTAINED WINDS...105 MPH"
    episode = build_episodes(records)[0]
    traces = run_episode(episode, "rule", max_queries=5)
    wind_before = traces[3]["state_after"]["state"]["maximum_wind_mph"]
    wind_after = traces[4]["state_after"]["state"]["maximum_wind_mph"]
    assert wind_before["value"] == wind_after["value"] == 105
    assert wind_before["evidence"] != wind_after["evidence"]
    assert wind_after["evidence"] == [{"record_id": "synthetic:report:3", "line": 3}]
    result = score_dynamic([episode], traces)
    assert result["metrics"]["preservation"] == {"numerator": 9, "denominator": 9, "value": 1.0}
    assert result["per_checkpoint"][4]["all_correct"] is True


def test_rule_parser_reads_public_text_independently_of_private_fields(episodes):
    episode = episodes[0]
    episode["records"][0]["fields"]["maximum_wind_mph"] = 999
    request = render_request(episode, "c1", None)
    assert parse_decision(diagnostic_response(request, "rule")) == expected_decision(1)


def test_public_request_excludes_private_labels_and_future_evidence(episodes):
    previous = expected_decision(None)
    request = render_request(episodes[0], "c1", previous)
    assert set(request) == {
        "protocol",
        "instruction",
        "checkpoint_time",
        "required_fields",
        "policy",
        "evidence",
        "previous_state",
    }
    assert set(request["evidence"][0]) == {"delivery_index", "record_id", "issued_at", "text"}
    serialized = json.dumps(request)
    for forbidden in (
        "field_evidence",
        '"fields"',
        "provenance",
        "Gold",
        "gold_origin",
        "synthetic:report:2",
        "synthetic:report:3",
        "2040-08-01T18:00:00Z",
    ):
        assert forbidden not in serialized
    assert request["previous_state"] == previous
    request["previous_state"]["action"] = "prepare"
    assert previous["action"] == "request_evidence"
    assert render_request(episodes[0], "c0", None)["evidence"] == []


def test_rule_backend_is_perfect_diagnostic_and_not_an_llm_result(episodes):
    traces = [row for episode in episodes for row in run_episode(episode, "rule", max_queries=5)]
    result = score_dynamic(episodes, traces)
    assert result["independent_event_groups"] == 1
    assert result["eligible_for_llm_leaderboard"] is False
    assert result["gold_origins"] == ["generated_by_spec"]
    assert result["source_origins"] == ["synthetic_record"]
    assert result["model_kinds"] == ["diagnostic_program"]
    assert result["status_counts"] == {"ok": 10}
    assert all(metric["value"] == 1.0 for metric in result["metrics"].values())
    assert result["metrics"]["grounded_state"]["denominator"] == 50
    assert all(row["all_correct"] for row in result["per_checkpoint"])
    assert sum(row["logical_queries"] for row in traces) == 10
    assert sum(row["provider_requests"] for row in traces) == 0
    assert all(row["eligible_for_llm_leaderboard"] is False for row in traces)


def test_last_arrival_control_exposes_stale_overwrite(episodes):
    episode = episodes[0]
    traces = run_episode(episode, "last-arrival", max_queries=5)
    assert traces[3]["state_after"] == expected_decision(1)
    result = score_dynamic([episode], traces)
    assert [row["all_correct"] for row in result["per_checkpoint"]] == [
        True,
        True,
        True,
        False,
        True,
    ]
    assert result["metrics"]["state_accuracy"] == {
        "numerator": 21,
        "denominator": 25,
        "value": 21 / 25,
    }
    assert result["metrics"]["preservation"] == {"numerator": 4, "denominator": 8, "value": 0.5}


def test_no_update_control_does_not_win_by_always_abstaining(episodes):
    episode = episodes[0]
    result = score_dynamic([episode], run_episode(episode, "no-update", max_queries=5))
    assert result["metrics"]["unknown_accuracy"]["value"] == 1.0
    assert result["metrics"]["known_answer_coverage"] == {
        "numerator": 0,
        "denominator": 16,
        "value": 0.0,
    }
    assert result["metrics"]["state_accuracy"]["value"] == 9 / 25
    assert result["metrics"]["action_accuracy"]["value"] == 1 / 5
    assert result["metrics"]["required_change_success"]["value"] == 0.0


def test_invalid_and_missing_submissions_preserve_exact_previous_model_state(episodes):
    episode = episodes[0]
    own_wrong_state = expected_decision(1)
    own_wrong_state["state"]["maximum_wind_mph"]["value"] = 84
    predictions = submitted(episode, [expected_decision(None), own_wrong_state, "not JSON"])
    traces = run_episode(episode, "submissions", max_queries=5, predictions=predictions)
    assert [row["status"] for row in traces] == ["ok", "ok", "invalid", "missing", "missing"]
    for index in (2, 3, 4):
        assert traces[index]["request"]["previous_state"] == own_wrong_state
        assert traces[index]["state_after"] == own_wrong_state
    assert traces[2]["request"] is not traces[3]["request"]
    result = score_dynamic([episode], traces)
    assert result["status_counts"] == {"ok": 2, "invalid": 1, "missing": 2}
    assert result["metrics"]["schema_success"]["denominator"] == 5
    assert result["metrics"]["state_accuracy"] == {
        "numerator": 9,
        "denominator": 25,
        "value": 9 / 25,
    }
    assert result["metrics"]["action_accuracy"]["denominator"] == 5


def test_absent_trace_rows_count_as_missing_without_shrinking_denominators(episodes):
    episode = episodes[0]
    traces = run_episode(episode, "rule", max_queries=5)
    result = score_dynamic([episode], traces[:2])
    assert result["status_counts"] == {"ok": 2, "missing": 3}
    assert result["metrics"]["schema_success"]["value"] == 2 / 5
    assert result["metrics"]["state_accuracy"]["value"] == 10 / 25
    assert result["metrics"]["grounded_state"]["denominator"] == 25
    empty = score_dynamic([episode], [])
    assert empty["status_counts"] == {"missing": 5}
    assert empty["metrics"]["state_accuracy"]["value"] == 0.0


@pytest.mark.parametrize("budget", [0, 2])
def test_budget_exhaustion_counts_every_checkpoint_and_preserves_state(episodes, budget):
    episode = episodes[0]
    traces = run_episode(episode, "rule", max_queries=budget)
    assert len(traces) == 5
    assert sum(row["logical_queries"] for row in traces) == budget
    assert [row["status"] for row in traces] == ["ok"] * budget + ["budget_exhausted"] * (
        5 - budget
    )
    expected = None if budget == 0 else expected_decision(1)
    assert all(row["state_after"] == expected for row in traces[budget:])
    result = score_dynamic([episode], traces)
    assert result["metrics"]["schema_success"]["value"] == budget / 5
    assert result["metrics"]["state_accuracy"]["denominator"] == 25


def test_invalid_run_configuration_is_rejected(episodes):
    with pytest.raises(ValueError):
        run_episode(episodes[0], "rule", max_queries=-1)
    with pytest.raises(ValueError):
        run_episode(episodes[0], "submissions", max_queries=5)
    with pytest.raises(ValueError):
        run_episode(episodes[0], "nonexistent", max_queries=5)


@pytest.mark.parametrize(
    "mutation",
    [
        "future_arrival",
        "duplicate_record",
        "duplicate_checkpoint",
        "unknown_arrival",
        "naive_issue",
        "naive_checkpoint",
        "mixed_storm",
        "nonincreasing_clock",
        "ambiguous_issue",
        "bad_locator",
        "bad_locator_text",
        "bool_numeric",
        "nan_numeric",
        "policy_change",
        "extra_required_field",
    ],
)
def test_malformed_episodes_fail_admission(episodes, mutation):
    episode = deepcopy(episodes[0])
    if mutation == "future_arrival":
        episode["checkpoints"][0]["arrivals"] = ["synthetic:report:1"]
    elif mutation == "duplicate_record":
        episode["records"][1]["record_id"] = episode["records"][0]["record_id"]
    elif mutation == "duplicate_checkpoint":
        episode["checkpoints"][1]["checkpoint_id"] = "c0"
    elif mutation == "unknown_arrival":
        episode["checkpoints"][1]["arrivals"] = ["missing"]
    elif mutation == "naive_issue":
        episode["records"][0]["issued_at"] = "2040-08-01T06:00:00"
    elif mutation == "naive_checkpoint":
        episode["checkpoints"][0]["at"] = "2040-08-01T05:59:00"
    elif mutation == "mixed_storm":
        episode["records"][1]["storm_id"] = "OTHER_SYNTHETIC_STORM"
    elif mutation == "nonincreasing_clock":
        episode["checkpoints"][1]["at"] = episode["checkpoints"][0]["at"]
    elif mutation == "ambiguous_issue":
        episode["records"][1]["issued_at"] = "2040-08-01T07:00:00+01:00"
    elif mutation == "bad_locator":
        episode["records"][0]["field_evidence"]["maximum_wind_mph"]["line_start"] = 99
    elif mutation == "bad_locator_text":
        episode["records"][0]["field_evidence"]["maximum_wind_mph"]["text"] = "invented support"
    elif mutation == "bool_numeric":
        episode["records"][0]["fields"]["maximum_wind_mph"] = True
    elif mutation == "nan_numeric":
        episode["records"][0]["fields"]["maximum_wind_mph"] = float("nan")
    elif mutation == "policy_change":
        episode["policy"]["threshold"] = 111
    elif mutation == "extra_required_field":
        episode["required_fields"].append("unknown_new_field")
    with pytest.raises(ValueError):
        validate_episode(episode)


@pytest.mark.parametrize("bad_value", [True, float("nan"), float("inf"), "85"])
def test_decision_rejects_boolean_nonfinite_and_string_numbers(bad_value):
    decision = expected_decision(1)
    decision["state"]["maximum_wind_mph"]["value"] = bad_value
    with pytest.raises(ValueError):
        parse_decision(json.dumps(decision))


@pytest.mark.parametrize(
    "mutation",
    [
        "top_extra",
        "state_extra",
        "slot_extra",
        "citation_extra",
        "bool_line",
        "unknown_value",
        "unknown_evidence",
        "duplicate_key",
        "wrong_action",
    ],
)
def test_strict_submission_schema_rejects_ambiguous_or_extra_data(mutation):
    decision = expected_decision(1)
    slot = decision["state"]["maximum_wind_mph"]
    if mutation == "top_extra":
        decision["explanation"] = "uncontracted"
    elif mutation == "state_extra":
        decision["state"]["new_field"] = deepcopy(slot)
    elif mutation == "slot_extra":
        slot["confidence"] = 1
    elif mutation == "citation_extra":
        slot["evidence"][0]["source"] = "extra"
    elif mutation == "bool_line":
        slot["evidence"][0]["line"] = True
    elif mutation == "unknown_value":
        decision["state"]["port_reopening_time"]["value"] = 42
    elif mutation == "unknown_evidence":
        decision["state"]["port_reopening_time"]["evidence"] = deepcopy(slot["evidence"])
    elif mutation == "wrong_action":
        decision["action"] = "close_the_port"
    raw = json.dumps(decision)
    if mutation == "duplicate_key":
        raw = raw.replace('"action": "monitor"', '"action": "prepare", "action": "monitor"')
    with pytest.raises(ValueError):
        parse_decision(raw)


@pytest.mark.parametrize(
    "mutation", ["request", "rehash_request", "hash", "state_after", "gold_repair"]
)
def test_scorer_rejects_request_or_model_state_tampering(episodes, mutation):
    episode = episodes[0]
    traces = run_episode(episode, "rule", max_queries=5)
    if mutation in {"request", "rehash_request"}:
        traces[2]["request"]["evidence"] = []
        if mutation == "rehash_request":
            traces[2]["request_hash"] = fingerprint(traces[2]["request"])
    elif mutation == "hash":
        traces[2]["request_hash"] = "0" * 64
    elif mutation == "state_after":
        traces[2]["state_after"] = expected_decision(1)
    elif mutation == "gold_repair":
        predictions = submitted(episode, [expected_decision(None), expected_decision(1), "invalid"])
        traces = run_episode(episode, "submissions", max_queries=5, predictions=predictions)
        traces[2]["state_after"] = expected_decision(2)
    with pytest.raises(ValueError):
        score_dynamic([episode], traces)


def test_scorer_rejects_duplicate_or_unknown_checkpoints(episodes):
    episode = episodes[0]
    traces = run_episode(episode, "rule", max_queries=5)
    with pytest.raises(ValueError):
        score_dynamic([episode], traces + traces[:1])
    traces[0]["checkpoint_id"] = "outside_episode"
    with pytest.raises(ValueError):
        score_dynamic([episode], traces)


def test_scorer_rejects_duplicate_episode_ids_instead_of_recounting_traces(episodes):
    episode = episodes[0]
    traces = run_episode(episode, "rule", max_queries=5)
    with pytest.raises(ValueError):
        score_dynamic([episode, deepcopy(episode)], traces)


def test_scorer_rejects_empty_evaluation_set():
    with pytest.raises(ValueError):
        score_dynamic([], [])


@pytest.mark.parametrize("entrypoint", ["validate", "score"])
def test_episode_without_checkpoints_cannot_produce_zero_denominator_result(episodes, entrypoint):
    episode = deepcopy(episodes[0])
    episode["checkpoints"] = []
    with pytest.raises(ValueError):
        if entrypoint == "validate":
            validate_episode(episode)
        else:
            score_dynamic([episode], [])


@pytest.mark.parametrize("logical_queries", [0, -1, True, 1.0, 2])
def test_successful_response_requires_exactly_one_integer_logical_query(episodes, logical_queries):
    episode = episodes[0]
    traces = run_episode(episode, "rule", max_queries=5)
    for row in traces:
        row["logical_queries"] = logical_queries
    with pytest.raises(ValueError):
        score_dynamic([episode], traces)


@pytest.mark.parametrize("provider_requests", [-1, 1])
def test_offline_diagnostic_cannot_claim_impossible_provider_accounting(
    episodes, provider_requests
):
    episode = episodes[0]
    traces = run_episode(episode, "rule", max_queries=5)
    traces[1]["provider_requests"] = provider_requests
    with pytest.raises(ValueError):
        score_dynamic([episode], traces)


def test_unknown_trace_status_cannot_silently_become_an_unscored_response(episodes):
    episode = episodes[0]
    traces = run_episode(episode, "no-update", max_queries=5)
    traces[1]["status"] = "unrecognized_status"
    with pytest.raises(ValueError):
        score_dynamic([episode], traces)


def test_budget_exhausted_trace_cannot_include_a_submitted_response(episodes):
    episode = episodes[0]
    traces = run_episode(episode, "no-update", max_queries=5)
    traces[1]["status"] = "budget_exhausted"
    traces[1]["logical_queries"] = 0
    with pytest.raises(ValueError):
        score_dynamic([episode], traces)


@pytest.mark.parametrize(
    "citation",
    [
        [],
        [{"record_id": "synthetic:report:1", "line": 3}],
        [{"record_id": "synthetic:report:2", "line": 4}],
        [{"record_id": "synthetic:report:3", "line": 3}],
    ],
)
def test_correct_value_requires_correct_visible_source_and_line(episodes, citation):
    episode = episodes[0]
    decisions = [expected_decision(n) for n in (None, 1, 2, 2, 3)]
    decisions[2]["state"]["maximum_wind_mph"]["evidence"] = citation
    traces = run_episode(
        episode, "submissions", max_queries=5, predictions=submitted(episode, decisions)
    )
    result = score_dynamic([episode], traces)
    slot = result["per_checkpoint"][2]["slots"]["maximum_wind_mph"]
    assert slot == {"value_correct": True, "grounded_correct": False}
    assert result["metrics"]["state_accuracy"]["value"] == 1.0
    assert result["metrics"]["grounded_state"]["value"] == 24 / 25
