import math
from datetime import datetime, timezone

import pytest

from disastertrace.monitoring_v1.providers.aviation import (
    day_time,
    parse_metar,
    parse_taf,
    visibility,
)
from disastertrace.monitoring_v1.providers.taf_timeline import target_withdrawals
from disastertrace.monitoring_v1.support import Interval, classify
from disastertrace.monitoring_v1.targets import canonical_hash, utc_us


def test_native_withdrawal_is_bound_to_station_window_and_legal_release():
    targets = [
        {"target_id": "covered", "entity": "KSFO", "physical_start": 100, "physical_end": 110},
        {"target_id": "other-site", "entity": "KOAK", "physical_start": 100, "physical_end": 110},
        {
            "target_id": "different-window",
            "entity": "KSFO",
            "physical_start": 200,
            "physical_end": 210,
        },
    ]
    products = [
        {
            "source_id": "cancel-1",
            "station": "KSFO",
            "issued_at": 5,
            "valid_start": 90,
            "valid_end": 150,
            "status": "canceled",
        }
    ]
    assert target_withdrawals(products, targets, 6, declared_replay_lag_us=2) == []
    result = target_withdrawals(products, targets, 7, declared_replay_lag_us=2)
    assert [r["target_id"] for r in result] == ["covered"]
    assert result[0]["available_at"] == 7


def test_nil_without_a_window_does_not_crash_or_leave_an_old_product_live():
    product = {
        "source_id": "nil",
        "station": "KSFO",
        "issued_at": 5,
        "valid_start": None,
        "valid_end": None,
        "status": "nil",
    }
    targets = [
        {"target_id": "future", "entity": "KSFO", "physical_start": 10, "physical_end": 11},
        {"target_id": "other", "entity": "KOAK", "physical_start": 10, "physical_end": 11},
    ]
    result = target_withdrawals([product], targets, 6, declared_replay_lag_us=1)
    assert [r["target_id"] for r in result] == ["future"]


def test_unparsed_taf_keeps_verified_envelope_without_extending_native_validity():
    from disastertrace.monitoring_v1.providers.taf_timeline import unavailable_product

    raw = "TAF KDEN 061739Z 0618/0724 20007KT P6SM FEW060 FM080200 30007KT P6SM BKN120="
    with pytest.raises(ValueError, match="outside native validity"):
        parse_taf(raw, station="KDEN", archive_issue="2024-01-06T17:39:00Z")
    product = unavailable_product(
        raw,
        station="KDEN",
        archive_issue="2024-01-06T17:39:00Z",
        source_id="native",
        reason="unsupported_scope",
    )
    assert product["valid_end"] == utc_us("2024-01-08T00:00:00Z")
    assert product["status"] == "unparsed" and product["raw"] == raw
    assert product["projection_status"] == "unavailable"


ISSUE = "2024-01-05T05:20:00Z"


def test_native_fm_preserves_minutes_inside_a_fixed_hour_target():
    raw = (
        "TAF KOAK 041729Z 0418/0524 00000KT 1/4SM FG VV002 "
        "FM041930 28007KT 3SM BR SCT004 "
        "FM042000 30008KT P6SM SCT010="
    )
    product = parse_taf(raw, station="KOAK", archive_issue="2023-12-04T17:29:00Z")
    projection = product.project(
        utc_us("2023-12-04T19:00:00Z"), utc_us("2023-12-04T20:00:00Z")
    )
    first, second = projection["segments"]
    assert first["end"] == second["start"] == utc_us("2023-12-04T19:30:00Z")
    assert first["prevailing"][0]["visibility"]["upper"] < 1000
    assert second["prevailing"][0]["visibility"]["lower"] > 1000


def taf(body):
    return parse_taf("TAF KSFO 050520Z 0506/0612 " + body, station="KSFO", archive_issue=ISSUE)


@pytest.mark.parametrize(
    "token,lower,upper,lc,uc",
    [
        ("P6SM", 9656.064, math.inf, False, True),
        ("M1/4SM", 0, 402.336, True, False),
        ("1 1/4SM", 2011.68, 2011.68, True, True),
        ("9999", 10000, math.inf, True, True),
        ("0000", 0, 50, True, False),
        ("1000", 1000, 1000, True, True),
        ("CAVOK", 10000, math.inf, True, True),
    ],
)
def test_native_visibility_bounds(token, lower, upper, lc, uc):
    result = visibility("22005KT " + token + " BKN020")
    assert result == Interval(lower, upper, lc, uc)


def test_native_observation_excludes_trend_and_runway_range():
    result = parse_metar(
        "EGKK 270820Z VRB03KT 1000 R08R/1400U BR OVC002 05/05 Q1033 TEMPO 0800 FG",
        observation_time="2024-01-27T08:20:00Z",
        report_type="routine",
    )
    assert result.visibility == Interval(1000, 1000)
    assert classify(result.visibility, "lt", 1000) == "refuted"


def test_signed_native_temperature_and_explicit_archive_report_type():
    result = parse_metar(
        "KSFO 050556Z 01005KT 10SM CLR M05/M10 A3010 RMK AO2",
        observation_time="2024-01-05T05:56:00Z",
        report_type="routine",
    )
    assert result.temperature_c == -5
    assert result.report_type == "routine"
    with pytest.raises(ValueError):
        parse_metar(
            "SPECI KSFO 050556Z 01005KT 10SM CLR M05/M10 A3010",
            observation_time="2024-01-05T05:56:00Z",
            report_type="routine",
        )


def test_missing_visibility_is_unresolved_not_negative():
    result = parse_metar(
        "KSFO 050556Z AUTO 01005KT //// VV/// 05/03 A3010",
        observation_time="2024-01-05T05:56:00Z",
        report_type="routine",
    )
    assert result.visibility is None
    assert "visibility_missing" in result.quality_flags


def test_month_rollover_and_hour_24_are_explicit():
    reference = datetime(2024, 12, 31, 20, tzinfo=timezone.utc)
    assert day_time("3124", reference) == datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert day_time("010100", reference) == datetime(2025, 1, 1, 1, tzinfo=timezone.utc)


def test_tempo_inherits_unchanged_fields_without_inventing_probability():
    product = taf("22005KT P6SM BKN020 TEMPO 0508/0510 1/2SM FG")
    projected = product.project(utc_us("2024-01-05T08:00:00Z"), utc_us("2024-01-05T09:00:00Z"))
    segment = projected["segments"][0]
    conditional = segment["conditional"][0]
    assert conditional["operator"] == "TEMPO"
    assert conditional["native_probability"] is None
    assert conditional["states"][0]["sky"] == ["BKN020"]
    assert conditional["states"][0]["wind"] == "22005KT"


def test_prob_tempo_retains_probability_and_operator():
    product = taf("22005KT P6SM BKN020 PROB30 TEMPO 0508/0510 1/2SM FG")
    segment = product.project(utc_us("2024-01-05T08:00:00Z"), utc_us("2024-01-05T09:00:00Z"))[
        "segments"
    ][0]
    assert segment["conditional"][0]["native_probability"] == 0.3
    assert segment["conditional"][0]["operator"] == "PROB30 TEMPO"


def test_becmg_has_transition_uncertainty_then_inherited_changed_fields():
    product = taf("22005KT P6SM BKN020 BECMG 0508/0510 1/2SM FG")
    during = product.project(utc_us("2024-01-05T09:00:00Z"), utc_us("2024-01-05T10:00:00Z"))[
        "segments"
    ][0]
    after = product.project(utc_us("2024-01-05T10:00:00Z"), utc_us("2024-01-05T11:00:00Z"))[
        "segments"
    ][0]
    assert len(during["prevailing"]) == 2
    assert len(after["prevailing"]) == 1
    assert after["prevailing"][0]["sky"] == ["BKN020"]
    assert after["prevailing"][0]["visibility"]["lower"] == 804.672


def test_fm_is_complete_replacement_and_nsw_clears_weather():
    product = taf("22005KT 2SM RA BKN020 FM051000 25010KT P6SM SCT040 TEMPO 0511/0512 NSW")
    after = product.project(utc_us("2024-01-05T11:00:00Z"), utc_us("2024-01-05T12:00:00Z"))[
        "segments"
    ][0]
    assert after["prevailing"][0]["weather"] == []
    assert after["conditional"][0]["states"][0]["weather"] == []
    with pytest.raises(ValueError, match="complete"):
        taf("22005KT P6SM BKN020 FM051000 1SM FG")


def test_irrelevant_future_segment_does_not_change_target_projection():
    one = taf("22005KT P6SM BKN020 FM051200 25010KT P6SM SCT040")
    two = taf("22005KT P6SM BKN020 FM051200 35030KT 1SM SN OVC003")
    start, end = utc_us("2024-01-05T08:00:00Z"), utc_us("2024-01-05T09:00:00Z")
    assert canonical_hash(one.project(start, end)) == canonical_hash(two.project(start, end))


def test_projection_cannot_truncate_out_of_validity_target():
    product = taf("22005KT P6SM BKN020")
    with pytest.raises(ValueError):
        product.project(utc_us("2024-01-05T05:00:00Z"), utc_us("2024-01-05T07:00:00Z"))


def test_cor_amendment_and_cancel_keep_native_identity():
    corrected = parse_taf(
        "TAF COR KSFO 050520Z 0506/0612 22005KT P6SM BKN020", station="KSFO", archive_issue=ISSUE
    )
    assert corrected.amendment_kind == "COR"
    canceled = parse_taf("TAF AMD KSFO 050520Z 0506/0612 CNL", station="KSFO", archive_issue=ISSUE)
    assert canceled.status == "canceled"
    with pytest.raises(ValueError):
        canceled.project(utc_us("2024-01-05T08:00:00Z"), utc_us("2024-01-05T09:00:00Z"))


def test_unsupported_or_conflicting_taf_operator_fails_closed():
    with pytest.raises(ValueError):
        taf("22005KT P6SM BKN020 PROB50 0508/0510 1/2SM FG")


def test_later_fm_supersedes_an_earlier_tempo_group():
    product = taf("22005KT P6SM BKN020 TEMPO 0508/0512 1/2SM FG FM051000 25010KT P6SM SCT040")
    before = product.project(utc_us("2024-01-05T09:00:00Z"), utc_us("2024-01-05T10:00:00Z"))
    after = product.project(utc_us("2024-01-05T11:00:00Z"), utc_us("2024-01-05T12:00:00Z"))
    assert before["segments"][0]["conditional"]
    assert not after["segments"][0]["conditional"]


def test_nsw_cannot_replace_significant_weather_in_a_complete_fm_group():
    with pytest.raises(ValueError, match="NSW"):
        taf("22005KT P6SM BKN020 FM051000 25010KT P6SM NSW SCT040")


def test_amendment_service_notice_is_preserved_in_target_context():
    product = taf("22005KT P6SM BKN020 FM051000 25010KT P6SM SCT040 AMD NOT SKED")
    assert product.amendment_scheduling == "AMD NOT SKED"
    projected = product.project(utc_us("2024-01-05T11:00:00Z"), utc_us("2024-01-05T12:00:00Z"))
    assert projected["amendment_scheduling"] == "AMD NOT SKED"
    assert projected["segments"][0]["prevailing"][0]["visibility"]["lower"] == 9656.064
