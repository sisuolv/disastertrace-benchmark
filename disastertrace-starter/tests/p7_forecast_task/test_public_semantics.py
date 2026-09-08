import hashlib
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

import pytest
from conftest import at, messages_at, source
from hypothesis import given, settings
from hypothesis import strategies as st

from disastertrace.forecast_task.common import canonical, strict_json
from disastertrace.forecast_task.compiler import compile_sources
from disastertrace.forecast_task.public_resolver import parse_document, resolve


def test_fixed_answer_and_original_byte_citation(dataset, sources):
    expected = {
        "storm_id": "AL062024",
        "valid_at": "2025-01-01T06:00:00+00:00",
        "measurement_kind": "forecast",
        "status": "numeric",
        "latitude": {"value": 15.0, "unit": "deg"},
        "longitude": {"value": -50.0, "unit": "deg"},
        "max_sustained_wind": {"value": 65, "unit": "KT"},
        "citation": {"source_id": "al062024-fstadv-005", "forecast_line": 10, "wind_line": 11},
    }
    assert resolve(messages_at(dataset)) == expected
    oid, _ = at(dataset)
    assert dataset["private_reference"]["references"][oid]["answer"] == expected
    support = dataset["private_reference"]["claims"]["al062024-fstadv-005"][expected["valid_at"]][
        "support"
    ]
    for s in support:
        raw = sources[0]["raw"][s["raw_byte_start"] : s["raw_byte_end"]]
        assert hashlib.sha256(raw).hexdigest() == s["raw_line_sha256"]
        assert raw.decode().rstrip("\n") == s["canonical_text"]


def test_same_value_refresh_and_newest_noncovering_product(dataset):
    revised = resolve(messages_at(dataset, step=2))
    assert revised["max_sustained_wind"]["value"] == 65
    assert revised["citation"]["source_id"].endswith("006")
    missing_row = resolve(messages_at(dataset, "2025-01-01T18:00:00+00:00", 3))
    assert missing_row["citation"]["source_id"].endswith("005")
    assert missing_row["max_sustained_wind"]["value"] == 70


def test_explicit_terminal_is_not_zero_or_blanket_termination(dataset):
    terminal = resolve(messages_at(dataset, "2025-01-03T06:00:00+00:00", 2))
    assert terminal["status"] == "ABSORBED"
    assert terminal["max_sustained_wind"]["value"] is None
    assert terminal["citation"]["wind_line"] is None
    later = resolve(messages_at(dataset, "2025-01-02T18:00:00+00:00", 1))
    assert later["status"] == "not_stated" and later["citation"] is None
    qualifier = resolve(messages_at(dataset, "2025-01-02T06:00:00+00:00", 2))
    assert qualifier["status"] == "numeric" and "qualifier" not in qualifier


def test_late_old_delivery_uses_issue_authority(dataset):
    messages = messages_at(dataset, step=2)
    payload = strict_json(messages[1]["content"])
    payload["documents"].reverse()
    messages[1]["content"] = canonical(payload)
    assert resolve(messages)["citation"]["source_id"].endswith("006")


@pytest.mark.parametrize(
    "lat,lon,expected", [("15.0S", "150.0E", (-15.0, 150.0)), ("0.0N", "0.0W", (0.0, 0.0))]
)
def test_signed_coordinates(lat, lon, expected):
    data = compile_sources([source(lat=lat, lon=lon)], {})
    result = resolve(messages_at(data))
    assert (result["latitude"]["value"], result["longitude"]["value"]) == expected


@pytest.mark.parametrize(
    "before,after",
    [
        ("MAX WIND 65 KT", "MAX WIND 65 MPH"),
        ("KT...GUSTS 80 KT", "KT...GUSTS 80 MPH"),
        ("01/0600Z", "32/0600Z"),
        ("01/0600Z", "01/2460Z"),
        ("TUE DEC 31", "MON DEC 31"),
        ("15.0N", "95.0N"),
        ("50.0W", "190.0W"),
        ("L0010|", "L0011|"),
        ("MAX WIND 65 KT", "GUSTS 65 KT"),
    ],
)
def test_public_parser_rejects_invalid_dates_units_and_locators(dataset, before, after):
    messages = messages_at(dataset)
    payload = strict_json(messages[1]["content"])
    document = payload["documents"][0]
    document["numbered_text"] = document["numbered_text"].replace(before, after)
    with pytest.raises(ValueError):
        parse_document(document)


@settings(max_examples=100, derandomize=True, deadline=None)
@given(
    date=st.dates(min_value=date(2018, 1, 1), max_value=date(2026, 12, 31)),
    hour=st.sampled_from([0, 3, 9, 15, 21]),
    delay=st.integers(0, 6),
    lead=st.integers(7, 168),
)
def test_generated_calendar_cases_against_constructed_absolute_times(date, hour, delay, lead):
    center = datetime(date.year, date.month, date.day, hour, tzinfo=timezone.utc)
    issue, valid = center + timedelta(hours=delay), center + timedelta(hours=lead)
    item = source(
        issue=issue.strftime("%H%M UTC %a %b %d %Y").upper(),
        center=center.strftime("%d/%H%MZ"),
        rows=f"FORECAST VALID {valid:%d/%H%MZ} 15.0N 50.0W\nMAX WIND 65 KT...GUSTS 80 KT.\n",
    )
    data = compile_sources([item], {})
    answer = resolve(messages_at(data, valid.isoformat()))
    assert answer["valid_at"] == valid.isoformat()
    assert answer["max_sustained_wind"]["value"] == 65


@pytest.mark.parametrize(
    "center,valid",
    [
        ("2024-02-28T21:00:00+00:00", "2024-02-29T00:00:00+00:00"),
        ("2024-02-29T21:00:00+00:00", "2024-03-01T00:00:00+00:00"),
        ("2023-02-28T21:00:00+00:00", "2023-03-01T00:00:00+00:00"),
        ("2024-12-31T21:00:00+00:00", "2025-01-01T00:00:00+00:00"),
    ],
)
def test_explicit_leap_month_year_and_midnight(center, valid):
    c, v = datetime.fromisoformat(center), datetime.fromisoformat(valid)
    item = source(
        issue=c.strftime("%H%M UTC %a %b %d %Y").upper(),
        center=c.strftime("%d/%H%MZ"),
        rows=f"FORECAST VALID {v:%d/%H%MZ} 15.0N 50.0W\nMAX WIND 65 KT...GUSTS 80 KT.\n",
    )
    data = compile_sources([item], {})
    assert resolve(messages_at(data, valid))["valid_at"] == valid


def test_nonleap_february_29_not_silently_march(dataset):
    item = source(
        issue="2100 UTC TUE FEB 28 2023",
        center="28/2100Z",
        rows="FORECAST VALID 01/0600Z 15.0N 50.0W\nMAX WIND 65 KT...GUSTS 80 KT.\n",
    )
    data = compile_sources([item], {})
    messages = messages_at(data, "2023-03-01T06:00:00+00:00")
    payload = strict_json(messages[1]["content"])
    payload["documents"][0]["numbered_text"] = payload["documents"][0]["numbered_text"].replace(
        "01/0600Z", "29/0600Z"
    )
    with pytest.raises(ValueError):
        parse_document(payload["documents"][0])


def test_wrong_storm_is_not_a_matching_key(dataset):
    messages = messages_at(dataset)
    payload = strict_json(messages[1]["content"])
    payload["query"]["storm_id"] = "AL012025"
    messages[1]["content"] = canonical(payload)
    assert resolve(messages)["status"] == "not_stated"


def test_ties_and_duplicate_sources_fail_closed(sources):
    duplicate = deepcopy(sources[0])
    duplicate["source_id"] = "different-id"
    with pytest.raises(ValueError, match="tied"):
        compile_sources([sources[0], duplicate], {})
    with pytest.raises(ValueError, match="duplicate source"):
        compile_sources([sources[0], sources[0]], {})
