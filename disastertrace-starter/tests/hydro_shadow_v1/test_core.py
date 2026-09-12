"""Time, datum, quality, and denominator regressions for prospective water targets."""

from copy import deepcopy

import pytest

from disastertrace.hydro_shadow_v1.core import (
    align_observations,
    content_hash,
    coops_points,
    number,
    nwps_points,
    predict,
    primary_contract,
    settle,
    threshold_contract,
    usgs_points,
)

NOW = "2026-09-12T06:00:00Z"


def target():
    return {
        "id": "h001",
        "lid": "TEST1",
        "valid_at": "2026-09-12T12:00:00Z",
        "deadline": "2026-09-12T10:00:00Z",
        "threshold": 10.0,
    }


def snapshot():
    return {
        "lid": "TEST1",
        "captured_at": NOW,
        "forecast": [
            {
                "valid_at": "2026-09-12T12:00:00Z",
                "issued_at": "2026-09-12T05:00:00Z",
                "generated_at": "2026-09-12T05:10:00Z",
                "value": 12.0,
            }
        ],
        "observations": [
            {"valid_at": "2026-09-12T05:45:00Z", "value": 8.0, "quality": "Provisional"}
        ],
    }


def test_negative_water_level_is_valid():
    assert number(-0.3) == -0.3


@pytest.mark.parametrize("value", [None, True, float("nan"), float("inf"), -999, -9999])
def test_invalid_numbers_rejected(value):
    with pytest.raises(ValueError):
        number(value)


def test_flow_threshold_cannot_replace_missing_stage_threshold():
    metadata = {
        "name": "fixture",
        "flood": {"stageUnits": "ft", "categories": {"minor": {"stage": -9999, "flow": 200}}},
    }
    with pytest.raises(ValueError):
        threshold_contract(metadata)


def test_exact_provider_alignment_rejects_datum_offset():
    first = [{"valid_at": NOW, "value": 10.0}]
    assert align_observations(first, [{"valid_at": NOW, "value": 10.01}])["compatible"]
    assert not align_observations(first, [{"valid_at": NOW, "value": 110.0}])["compatible"]


def usgs_body():
    return {
        "features": [
            {
                "properties": {
                    "monitoring_location_id": "USGS-12345678",
                    "parameter_code": "00065",
                    "unit_of_measure": "ft",
                    "statistic_id": "00011",
                    "time": NOW,
                    "value": "8.1",
                    "qualifier": None,
                    "approval_status": "Provisional",
                    "time_series_id": "series-1",
                }
            }
        ],
        "links": [],
    }


def test_usgs_provisional_preserved_and_uuid_irrelevant():
    body = usgs_body()
    first, _ = usgs_points(body, "12345678", "00065", NOW)
    body["features"][0]["properties"].update(id="changed-uuid", last_modified="2099-01-01")
    second, _ = usgs_points(body, "12345678", "00065", NOW)
    assert first == second
    assert first[0]["quality"] == "Provisional"


def test_multiple_usgs_series_at_same_time_rejected():
    body = usgs_body()
    other = deepcopy(body["features"][0])
    other["properties"]["time_series_id"] = "series-2"
    body["features"].append(other)
    with pytest.raises(ValueError):
        usgs_points(body, "12345678", "00065", NOW)


def test_usgs_pagination_not_silently_ignored():
    body = usgs_body()
    body["links"] = [{"rel": "next", "href": "more-data"}]
    with pytest.raises(ValueError):
        usgs_points(body, "12345678", "00065", NOW)


def test_future_or_qualified_usgs_observations_excluded():
    body = usgs_body()
    body["features"][0]["properties"]["time"] = "2026-09-12T07:00:00Z"
    points, reasons = usgs_points(body, "12345678", "00065", NOW)
    assert points == [] and reasons
    body["features"][0]["properties"].update(time=NOW, qualifier="ice")
    points, reasons = usgs_points(body, "12345678", "00065", NOW)
    assert points == [] and reasons


def test_coops_provisional_and_flags():
    body = {
        "metadata": {"id": "1234567"},
        "data": [{"t": "2026-09-12 05:54", "v": "-0.2", "q": "p", "f": "0,0,0,0"}],
    }
    points, _ = coops_points(body, "1234567", NOW)
    assert points[0]["quality"] == "Provisional" and points[0]["value"] == -0.2
    body["data"][0]["f"] = "0,1,0,0"
    points, reasons = coops_points(body, "1234567", NOW)
    assert points == [] and reasons


def test_nwps_observation_cannot_be_from_future():
    data = {
        "observed": {
            "primaryName": "Stage",
            "primaryUnits": "ft",
            "issuedTime": NOW,
            "data": [{"validTime": "2026-09-12T07:00:00Z", "generatedTime": NOW, "primary": 9}],
        }
    }
    points, reasons = nwps_points(data, "observed", NOW)
    assert points == [] and reasons


def test_prediction_uses_only_current_observations():
    data = snapshot()
    data["observations"].append(
        {"valid_at": "2026-09-12T12:00:00Z", "value": 50, "quality": "Approved"}
    )
    commits = {c["policy"]: c for c in predict(data, target(), NOW, 11)}
    assert commits["persistence"]["value"] == 8
    assert commits["latest_professional"]["value"] == 12
    assert commits["half_blend"]["value"] == 10


@pytest.mark.parametrize("mutation", ["late", "future_capture", "wrong_station"])
def test_illegal_prediction_rejected(mutation):
    data, time = snapshot(), NOW
    if mutation == "late":
        time = "2026-09-12T10:00:01Z"
    elif mutation == "future_capture":
        data["captured_at"] = "2026-09-12T06:00:01Z"
    else:
        data["lid"] = "OTHER"
    with pytest.raises(ValueError):
        predict(data, target(), time, 11)


def test_future_result_does_not_settle_early():
    observations = [{"valid_at": target()["valid_at"], "value": 10, "quality": "Approved"}]
    assert settle(target(), [], observations, NOW)["status"] == "pending_future"


def test_nearest_observation_is_not_exact_target_result():
    observations = [{"valid_at": "2026-09-12T11:45:00Z", "value": 10, "quality": "Approved"}]
    assert (
        settle(target(), [], observations, "2026-09-12T13:00:00Z")["status"]
        == "pending_exact_observation"
    )


def test_provisional_settlement_retains_missing_predictions():
    observations = [{"valid_at": target()["valid_at"], "value": 10, "quality": "Provisional"}]
    commits = predict(snapshot(), target(), NOW, 11)[:1]
    result = settle(target(), commits, observations, "2026-09-12T13:00:00Z")
    assert result["status"] == "settled_provisional"
    assert result["binary_outcome"] == 1
    assert len(result["policies"]) == 4
    assert result["policies"]["latest_professional"]["status"] == "missing_prediction"


def test_late_commit_is_never_scored():
    observations = [{"valid_at": target()["valid_at"], "value": 12, "quality": "Approved"}]
    commits = predict(snapshot(), target(), NOW, 11)
    for commit in commits:
        commit["committed_at"] = "2026-09-12T11:59:59Z"
    result = settle(target(), commits, observations, "2026-09-12T13:00:00Z")
    assert all(v["status"] == "missing_prediction" for v in result["policies"].values())


def test_content_identity_changes_with_values():
    data = snapshot()
    previous = content_hash(data)
    data["forecast"][0]["value"] = 13
    assert content_hash(data) != previous


def test_explicit_absolute_datum_conversion_is_metadata_bound():
    metadata = {
        "name": "River at example (NAVD88)",
        "usgsId": "12345678",
        "datums": {
            "vertical": {
                "value": [{"abbrev": "NAVD88", "value": 0}, {"abbrev": "STND", "value": 0.8}]
            }
        },
    }
    site = {"properties": {"id": "USGS-12345678", "vertical_datum": "NAVD88", "altitude": -0.8}}
    contract = primary_contract(metadata, site, "00065", "usgs")
    assert contract["offset_ft"] == -0.8
    assert contract["reference"] == "NAVD88"
    site["properties"]["altitude"] = -0.7
    with pytest.raises(ValueError, match="datum"):
        primary_contract(metadata, site, "00065", "usgs")


def test_tide_height_requires_explicit_variable_contract():
    data = {
        "observed": {
            "primaryName": "Tide Height",
            "primaryUnits": "ft",
            "issuedTime": NOW,
            "data": [{"validTime": NOW, "generatedTime": NOW, "primary": -0.2}],
        }
    }
    with pytest.raises(ValueError):
        nwps_points(data, "observed", NOW)
    points, _ = nwps_points(data, "observed", NOW, variable="Tide Height")
    assert points[0]["value"] == -0.2


def test_coops_four_quality_flags_are_required():
    body = {
        "metadata": {"id": "1234567"},
        "data": [{"t": "2026-09-12 05:54", "v": "1", "q": "p", "f": "0"}],
    }
    points, reasons = coops_points(body, "1234567", NOW)
    assert not points and reasons
