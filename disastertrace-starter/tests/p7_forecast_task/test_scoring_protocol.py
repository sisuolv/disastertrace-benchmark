from copy import deepcopy

import pytest
from conftest import at, messages_at

from disastertrace.forecast_task.common import canonical, fingerprint, strict_json
from disastertrace.forecast_task.contract import parse_answer
from disastertrace.forecast_task.diagnostics import collect_program, run_programs
from disastertrace.forecast_task.protocol import carrier, request, schedule
from disastertrace.forecast_task.public_resolver import resolve
from disastertrace.forecast_task.scoring import score_one, summarize


def score(dataset, answer, valid="2025-01-01T06:00:00+00:00", step=1):
    oid, op = at(dataset, valid, step)
    text = canonical(answer) if isinstance(answer, dict) else answer
    return score_one(
        text, op, dataset["private_reference"]["references"][oid], dataset["private_reference"]
    )


def test_stale_same_value_retains_literal_support_but_loses_authority(dataset):
    answer = resolve(messages_at(dataset))
    result = score(dataset, answer, step=2)
    assert all(result["fields"].values()) and all(result["literal_support"].values())
    assert result["locator_correct"] and not result["current_source"]
    assert not result["all_correct"] and result["error_category"] == "superseded_same_value"


@pytest.mark.parametrize(
    "field,value,unit",
    [
        ("max_sustained_wind", 80, "KT"),
        ("max_sustained_wind", 980, "MB"),
        ("max_sustained_wind", 50, "KT"),
        ("max_sustained_wind", 65, "MPH"),
        ("latitude", 14.0, "deg"),
        ("longitude", 50.0, "deg"),
    ],
)
def test_wind_gust_observation_pressure_units_and_signs_are_semantic_errors(
    dataset, field, value, unit
):
    answer = resolve(messages_at(dataset))
    answer[field] = {"value": value, "unit": unit}
    result = score(dataset, answer)
    assert result["shape_valid"] and not result["all_correct"]
    assert not result["fields"][field] and not result["literal_support"][field]
    assert result["current_source"] and result["locator_correct"]


@pytest.mark.parametrize(
    "key,value",
    [
        ("storm_id", "AL012025"),
        ("valid_at", "2025-01-01T18:00:00+00:00"),
        ("valid_at", "2025-02-30T18:00:00Z"),
        ("measurement_kind", "observation"),
    ],
)
def test_wrong_scope_or_time_cannot_get_key_or_literal_credit(dataset, key, value):
    answer = resolve(messages_at(dataset))
    answer[key] = value
    result = score(dataset, answer)
    assert result["shape_valid"] and not result["key_correct"]
    assert not any(result["literal_support"].values())


def test_equivalent_utc_spelling(dataset):
    answer = resolve(messages_at(dataset))
    answer["valid_at"] = "2025-01-01T06:00:00Z"
    assert score(dataset, answer)["all_correct"]


def test_future_source_and_wrong_line_cannot_support_same_number(dataset):
    future = resolve(messages_at(dataset, step=2))
    result = score(dataset, future)
    assert result["error_category"] == "unseen_source"
    assert not any(result["literal_support"].values())
    answer = resolve(messages_at(dataset))
    answer["citation"]["wind_line"] = 8
    result = score(dataset, answer)
    assert result["current_source"] and not result["locator_correct"]
    assert (
        result["literal_support"]["latitude"]
        and not result["literal_support"]["max_sustained_wind"]
    )


@pytest.mark.parametrize(
    "kind", ["extra", "duplicate", "boolean", "nan", "infinite", "fence", "missing", "line_bool"]
)
def test_invalid_shapes_and_missing_keep_the_denominator(dataset, kind):
    answer = resolve(messages_at(dataset))
    if kind == "extra":
        answer["forecast_pressure"] = 980
    if kind == "boolean":
        answer["latitude"]["value"] = True
    if kind == "line_bool":
        answer["citation"]["forecast_line"] = True
    text = canonical(answer)
    if kind == "duplicate":
        text = text.replace('"status":"numeric"', '"status":"numeric","status":"numeric"')
    if kind == "nan":
        text = text.replace('"value":15.0', '"value":NaN')
    if kind == "infinite":
        text = text.replace('"value":15.0', '"value":1e999')
    if kind == "fence":
        text = "```json\n" + text + "\n```"
    if kind == "missing":
        text = None
    result = score(dataset, text)
    assert not result["shape_valid"] and not result["all_correct"]
    assert not any(result["fields"].values())


def test_terminal_zero_and_missing_status_with_citation_are_wrong(dataset):
    valid = "2025-01-03T06:00:00+00:00"
    answer = resolve(messages_at(dataset, valid))
    answer["max_sustained_wind"]["value"] = 0
    assert not score(dataset, answer, valid)["fields"]["max_sustained_wind"]
    answer = resolve(messages_at(dataset))
    answer["status"] = "not_stated"
    assert not score(dataset, answer)["status_correct"]


def test_all_wrong_policies_rejected_on_informative_fixtures_and_agreements_retained(dataset):
    report = run_programs(
        dataset["public"], dataset["private_reference"], schedule(dataset["public"])
    )
    for policy, result in report["scores"].items():
        count = result["counts"]
        assert count["planned"] == len(schedule(dataset["public"]))
        if policy == "latest_explicit":
            assert count["all_correct"] == count["planned"]
        else:
            assert count["all_correct"] < count["planned"]
    assert report["scores"]["newest_document"]["counts"]["all_correct"] > 0
    assert report["scores"]["first_covering"]["counts"]["errors"]["superseded_same_value"] > 0


def test_same_relative_lead_is_different_absolute_time(dataset):
    messages = messages_at(dataset, step=2)
    wrong = resolve(messages, "same_relative_lead")
    assert wrong["max_sustained_wind"]["value"] == 70
    assert resolve(messages)["max_sustained_wind"]["value"] == 65
    assert not score(dataset, wrong, step=2)["all_correct"]


def test_public_requests_hide_future_and_reference_and_keep_exact_own_prefix(dataset):
    oid, _ = at(dataset)
    public = deepcopy(dataset["public"])
    expected = request(public, oid, "snapshot", [])
    public["documents"]["al062024-fstadv-006"]["numbered_text"] = "FUTURE_HIDDEN_MARKER"
    dataset["private_reference"]["references"][oid]["answer"] = {"SECRET_GOLD": "not_for_model"}
    assert request(public, oid, "snapshot", []) == expected
    assert "FUTURE_HIDDEN_MARKER" not in canonical(expected)
    payload = strict_json(expected[1]["content"])
    assert set(payload) == {"query", "checkpoint", "documents", "method", "carrier"}
    assert set(payload["documents"][0]) == {
        "source_id",
        "delivery_step",
        "delivery_elapsed_hours",
        "numbered_text",
    }
    with pytest.raises(ValueError, match="prefix"):
        request(
            public, oid, "structured_state", [{"checkpoint_id": "wrong-target", "final_text": "{}"}]
        )


def test_carrier_preserves_semantic_errors_and_invalid_history_without_gold(dataset):
    answer = resolve(messages_at(dataset))
    answer["max_sustained_wind"]["value"] = 980
    raw = canonical(answer)
    history = [
        {"checkpoint_id": "first", "final_text": raw},
        {"checkpoint_id": "second", "final_text": "bad"},
    ]
    assert carrier("structured_state", history[:1])["answer"]["max_sustained_wind"]["value"] == 980
    assert carrier("structured_state", history)["kind"] == "invalid"
    assert carrier("answer_history", history) == history
    assert carrier("snapshot", history) is None


def test_schedule_nonuniform_episodes_and_absent_captures(dataset):
    public, private = dataset["public"], dataset["private_reference"]
    slots = schedule(public)
    assert len(slots) == len(public["opportunities"]) * 6
    assert len({s["slot_id"] for s in slots}) == len(slots)
    assert len({len(e["opportunity_ids"]) for e in public["episodes"].values()}) > 1
    assert fingerprint(schedule(deepcopy(public))) == fingerprint(slots)
    captures, _ = collect_program(public, slots, "latest_explicit")
    truncated = summarize(slots, captures[:-1], public, private)
    assert truncated["counts"]["planned"] == len(slots)
    assert truncated["counts"]["received"] == len(slots) - 1
    assert truncated["counts"]["all_correct"] == len(slots) - 1
    assert truncated["absent_capture_records"] == 1
    assert (
        truncated["whole_trajectories"]["all_checkpoints_correct"]
        == truncated["whole_trajectories"]["planned"] - 1
    )
    with pytest.raises(ValueError, match="duplicate"):
        summarize(slots, [*captures, captures[0]], public, private)


def test_structure_validity_does_not_use_current_keys_units_or_gold(dataset):
    answer = resolve(messages_at(dataset))
    answer["max_sustained_wind"] = {"value": None, "unit": "MB"}
    answer["citation"]["source_id"] = "invented-source"
    assert parse_answer(canonical(answer)) == answer
    assert not score(dataset, answer)["all_correct"]


def test_large_finite_integer_is_a_semantic_error_without_crashing_scorer(dataset):
    answer = resolve(messages_at(dataset))
    answer["max_sustained_wind"]["value"] = 10**1000
    result = score(dataset, answer)
    assert result["shape_valid"]
    assert not result["fields"]["max_sustained_wind"] and not result["all_correct"]
