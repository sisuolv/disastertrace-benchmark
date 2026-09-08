"""Synthetic forecast products test semantics; no per-item human Gold is used."""

from copy import deepcopy

import pytest

from disastertrace.forecast_source import parser_a, parser_b
from disastertrace.forecast_source.consensus import agree, latest_covering, revision_pairs


def advisory(
    issue="2100 UTC TUE DEC 31 2024",
    center="31/2100Z",
    valid="01/0600Z",
    lat="15.0N",
    lon="50.0W",
    wind="65",
    gust="80",
    number=5,
):
    return (
        "<html><pre>\nHURRICANE EXAMPLE FORECAST/ADVISORY NUMBER " + str(number) + "\n"
        "NWS NATIONAL HURRICANE CENTER MIAMI FL AL062024\n" + issue + "\n\n"
        "CENTER LOCATED NEAR 14.0N 49.0W AT " + center + "\n"
        "PRESENT MOVEMENT TOWARD THE WEST OR 270 DEGREES AT 12 KT\n"
        "MAXIMUM SUSTAINED WINDS 50 KT WITH GUSTS TO 60 KT.\n"
        "ESTIMATED MINIMUM CENTRAL PRESSURE 980 MB\n\nFORECAST VALID "
        + valid
        + " "
        + lat
        + " "
        + lon
        + "\nMAX WIND "
        + wind
        + " KT...GUSTS "
        + gust
        + " KT.\n"
        "64 KT... 20NE 20SE 20SW 20NW.\n\n$$\nFORECASTER EXAMPLE\n</pre></html>"
    ).encode()


@pytest.mark.parametrize("parser", [parser_a.parse, parser_b.parse])
def test_forecast_not_observation_gust_movement_or_pressure(parser):
    result = parser(advisory())
    assert result["issued_at"] == "2024-12-31T21:00:00+00:00"
    row = result["forecasts"][0]
    assert row["valid_at"] == "2025-01-01T06:00:00+00:00"
    assert row["latitude"] == 15.0 and row["longitude"] == -50.0
    assert row["max_sustained_wind_kt"] == 65
    assert row["lead_hours_from_center"] == 9
    assert "pressure" not in row


@pytest.mark.parametrize(
    "lat,lon,expected", [("15.0S", "150.0E", (-15.0, 150.0)), ("0.0N", "0.0W", (0.0, 0.0))]
)
def test_hemispheres(lat, lon, expected):
    result = agree(advisory(lat=lat, lon=lon))
    row = result["forecasts"][0]
    assert (row["latitude"], row["longitude"]) == expected


@pytest.mark.parametrize(
    "mutation",
    [
        lambda x: x.replace(b"MAX WIND 65 KT", b"MAX WIND 65 MPH"),
        lambda x: x.replace(b"15.0N", b"95.0N"),
        lambda x: x.replace(b"50.0W", b"190.0W"),
        lambda x: x.replace(b"01/0600Z", b"31/0600Z"),
        lambda x: x.replace(b"TUE DEC 31", b"MON DEC 31"),
        lambda x: x.replace(b"01/0600Z", b"01/2560Z"),
        lambda x: x.replace(b"MAX WIND 65 KT", b"GUSTS 65 KT"),
    ],
)
def test_ambiguity_units_and_bounds_quarantined(mutation):
    for parser in (parser_a.parse, parser_b.parse):
        with pytest.raises(ValueError):
            parser(mutation(advisory()))


def test_month_rollover_and_same_valid_pairing():
    first = agree(advisory(issue="2100 UTC FRI JAN 31 2025", center="31/2100Z", valid="01/1200Z"))
    second = agree(
        advisory(
            issue="0300 UTC SAT FEB 01 2025",
            center="01/0300Z",
            valid="01/1200Z",
            wind="70",
            number=6,
        )
    )
    pairs = revision_pairs([first, second])
    assert len(pairs) == 1
    assert pairs[0]["wind_change_kt"] == 5
    assert first["forecasts"][0]["lead_hours_from_center"] == 15
    assert second["forecasts"][0]["lead_hours_from_center"] == 9
    third = agree(
        advisory(issue="0300 UTC SAT FEB 01 2025", center="01/0300Z", valid="01/1800Z", number=6)
    )
    assert third["forecasts"][0]["lead_hours_from_center"] == 15
    assert revision_pairs([first, third]) == []


def test_latest_document_does_not_replace_latest_covering_key():
    first = agree(advisory())
    second = agree(
        advisory(issue="0300 UTC WED JAN 01 2025", center="01/0300Z", valid="01/1800Z", number=6)
    )
    found = latest_covering(
        [first, second], "AL062024", first["forecasts"][0]["valid_at"], second["issued_at"]
    )
    assert found["advisory_number"] == 5


def test_parser_disagreement_is_not_resolved_by_preference(monkeypatch):
    original = parser_b.parse

    def wrong(raw):
        value = deepcopy(original(raw))
        value["forecasts"][0]["max_sustained_wind_kt"] = 80
        return value

    monkeypatch.setattr(parser_b, "parse", wrong)
    with pytest.raises(ValueError, match="disagreement"):
        agree(advisory())


@pytest.mark.parametrize(
    "prefix", [b"HURRICANE ", b"TROPICAL STORM ", b"POTENTIAL TROPICAL CYCLONE "]
)
def test_classified_center_and_repeat_line(prefix):
    body = advisory().replace(b"CENTER LOCATED NEAR", prefix + b"CENTER LOCATED NEAR")
    body = body.replace(b"$$", b"REPEAT...CENTER LOCATED NEAR 14.0N 49.0W AT 31/2100Z\n$$")
    result = agree(body)
    assert result["center_at"] == "2024-12-31T21:00:00+00:00"


def test_terminal_forecast_retained_without_invented_values():
    body = advisory().replace(b"$$", b"OUTLOOK VALID 02/0600Z...DISSIPATED\n\n$$")
    result = agree(body)
    assert len(result["forecasts"]) == 2
    assert result["forecasts"][1]["terminal_status"] == "DISSIPATED"
    assert result["forecasts"][1]["max_sustained_wind_kt"] is None
