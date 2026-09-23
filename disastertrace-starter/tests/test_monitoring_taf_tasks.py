"""Window/issuance counterexamples for E-only native TAF contracts."""

import copy
import json

import pytest

from disastertrace.monitoring_fixed_v1.contracts import Target
from disastertrace.monitoring_fixed_v1.taf_tasks import (
    TafEvidenceTask,
    evaluate,
    messages,
    parse_answer,
    score_answer,
)
from disastertrace.monitoring_v1.targets import utc_us


def task(kind="coverage", *, start="2024-01-05T20:00:00Z", end="2024-01-05T22:00:00Z", raw=None):
    product = {
        "source_id": "r1",
        "station": "KSFO",
        "raw": raw
        or "TAF KSFO 050000Z 0500/0600 20010KT P6SM SCT020 TEMPO 0518/0521 2SM BR BKN005=",
        "issued_at": utc_us("2024-01-05T00:00:00Z"),
        "available_at": utc_us("2024-01-05T00:02:00Z"),
        "completed_at": utc_us("2024-01-05T00:02:00Z"),
    }
    target = Target(
        "target",
        "station:KSFO",
        "visibility",
        "m",
        "event_probability",
        "interval",
        utc_us(start),
        utc_us(end),
        "future_physical",
        "iem_routine_unique_hour.v1",
        "lt",
        5000,
    )
    return TafEvidenceTask.freeze(
        {
            "schema": "disastertrace.taf_E_task.v1",
            "task_id": "task-" + kind,
            "kind": kind,
            "target": target.to_dict(),
            "as_of": utc_us("2024-01-05T01:00:00Z"),
            "availability_basis": "declared_archive_scenario",
            "products": [product],
        }
    )


@pytest.mark.parametrize(
    "start,end,coverage",
    [
        ("2024-01-05T20:00:00Z", "2024-01-05T22:00:00Z", "full"),
        ("2024-01-05T23:00:00Z", "2024-01-06T01:00:00Z", "partial"),
        ("2024-01-06T00:00:00Z", "2024-01-06T01:00:00Z", "none"),
    ],
)
def test_fixed_native_window_support_is_not_inferred_from_publication(start, end, coverage):
    t = task(start=start, end=end)
    answer = evaluate(t)["answer"]
    assert answer["status"] == "resolved" and answer["coverage"] == coverage
    assert score_answer(json.dumps(answer), t)["correct"]


def test_newest_source_may_remove_coverage_old_coverage_is_not_intersected():
    old = task(start="2024-01-05T20:00:00Z", end="2024-01-05T22:00:00Z").view()
    newer = copy.deepcopy(old["products"][0])
    newer.update(
        source_id="r2",
        raw="TAF AMD KSFO 050030Z 0500/0520 20010KT P6SM SCT020=",
        issued_at=utc_us("2024-01-05T00:30:00Z"),
        available_at=utc_us("2024-01-05T00:32:00Z"),
        completed_at=utc_us("2024-01-05T00:32:00Z"),
    )
    old["products"].append(newer)
    t = TafEvidenceTask.freeze(old)
    assert evaluate(t)["answer"]["coverage"] == "none"
    old["kind"] = "revision"
    answer = evaluate(TafEvidenceTask.freeze(old))["answer"]
    assert answer["current_source_ids"] == ["r2"]
    assert answer["superseded_source_ids"] == ["r1"]


def test_parse_failure_is_unsupported_not_negative_factual_evidence():
    answer = evaluate(task(raw="TAF KSFO 050000Z 0500/0600 UNKNOWN_TOKEN="))["answer"]
    assert answer["status"] == "unsupported" and answer["coverage"] is None


@pytest.mark.parametrize("body", ["NIL", "CNL"])
def test_native_nil_and_cancellation_are_resolved_noncoverage(body):
    answer = evaluate(task(raw="TAF KSFO 050000Z " + body + "="))["answer"]
    assert answer["status"] == "resolved" and answer["coverage"] == "none"


def test_missing_disclosure_is_unknown_and_no_hidden_versions_enter_the_head():
    row = task().view()
    row["products"] = []
    t = TafEvidenceTask.freeze(row)
    assert evaluate(t)["answer"]["status"] == "unknown"
    request = messages(t)
    assert json.loads(request[1]["content"]) == t.view()
    assert "gold" not in request[1]["content"] and "projection" not in request[1]["content"]


def test_equal_issuance_conflict_is_distinct_from_equivalent_source_mirrors():
    row = task().view()
    mirror = dict(row["products"][0], source_id="mirror")
    row["products"].append(mirror)
    assert evaluate(TafEvidenceTask.freeze(row))["answer"]["status"] == "resolved"
    mirror["raw"] = mirror["raw"].replace("P6SM", "1SM")
    answer = evaluate(TafEvidenceTask.freeze(row))["answer"]
    assert answer["status"] == "conflict" and answer["coverage"] is None


def test_future_or_wrong_station_records_cannot_be_supplied_as_disclosed():
    for field, value in (("completed_at", utc_us("2024-01-05T02:00:00Z")), ("station", "KOAK")):
        row = task().view()
        row["products"][0][field] = value
        with pytest.raises(ValueError):
            TafEvidenceTask.freeze(row)


def test_strict_answer_parser_has_no_gold_or_json_bool_shortcut():
    t = task()
    for raw in (
        '{"status":"resolved","status":"unknown","coverage":"full","current_source_ids":["r1"]}',
        '{"status":true,"coverage":"full","current_source_ids":["r1"]}',
        '{"status":"resolved","coverage":"full","current_source_ids":["unseen"]}',
    ):
        with pytest.raises(ValueError):
            parse_answer(raw, t)
    wrong = '{"status":"resolved","coverage":"none","current_source_ids":["r1"]}'
    assert parse_answer(wrong, t)["coverage"] == "none"
    assert score_answer(wrong, t)["correct"] is False
