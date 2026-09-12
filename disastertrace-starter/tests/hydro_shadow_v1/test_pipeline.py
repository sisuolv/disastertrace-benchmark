"""Registry, revision, and disk-time submission contracts."""

from copy import deepcopy

import pytest

from disastertrace.hydro_shadow_v1.capture import file_hash, strict_json, write_new
from disastertrace.hydro_shadow_v1.core import content_hash, primary_contract, threshold_contract
from disastertrace.hydro_shadow_v1.pipeline import (
    load_commits,
    make_registry,
    normalize_cycle,
    provider_urls,
    save_submissions,
    verify_freeze,
    worker,
)

NOW = "2026-09-12T06:00:00Z"


def station_fixture():
    metadata = {
        "lid": "TEST1",
        "usgsId": "12345678",
        "name": "Fixture River",
        "datums": {"vertical": {"value": [{"abbrev": "NAVD88", "value": 50}]}},
        "flood": {"stageUnits": "ft", "categories": {"minor": {"stage": 10}}},
    }
    site = {"properties": {"id": "USGS-12345678", "vertical_datum": "NAVD88", "altitude": 50}}
    source = primary_contract(metadata, site, "00065", "usgs")
    station = {
        **source,
        "lid": "TEST1",
        "admitted": True,
        "threshold": 10,
        "primary_contract": source,
        "primary_contract_hash": content_hash(source),
        "contract_hash": content_hash(threshold_contract(metadata)),
        "family": "river_water_level",
    }
    snapshot = {
        "lid": "TEST1",
        "captured_at": NOW,
        "observations": [],
        "forecast": [
            {
                "valid_at": time,
                "issued_at": "2026-09-12T05:00:00Z",
                "generated_at": "2026-09-12T05:30:00Z",
                "value": value,
            }
            for time, value in [
                ("2026-09-12T12:00:00Z", 9),
                ("2026-09-12T18:00:00Z", 10),
                ("2026-09-13T06:00:00Z", 11),
            ]
        ],
    }
    return station, snapshot, metadata, site


def test_registry_fixes_denominators_and_stop():
    station, snapshot, _, _ = station_fixture()
    registry = make_registry([station], {"TEST1": snapshot}, NOW)
    assert len(registry["targets"]) == 3
    assert registry["expected_target_policy_results"] == 12
    assert registry["targets"][0]["deadline"] == "2026-09-12T10:00:00Z"
    assert registry["scheduled_stop_at"] == "2026-09-13T10:00:00Z"
    assert registry["max_logical_downloads"] == 4 * len(registry["poll_at"])


@pytest.mark.parametrize(
    "mutation", ["unqualified", "future_receipt", "past_issue_missing", "duplicate_station"]
)
def test_registry_rejects_unavailable_initial_support(mutation):
    station, snapshot, _, _ = station_fixture()
    stations = [station]
    if mutation == "unqualified":
        station["admitted"] = False
    elif mutation == "future_receipt":
        snapshot["captured_at"] = "2026-09-12T07:00:00Z"
    elif mutation == "past_issue_missing":
        snapshot["forecast"][0]["issued_at"] = "2026-09-12T07:00:00Z"
    else:
        stations.append(station)
    with pytest.raises(ValueError):
        make_registry(stations, {"TEST1": snapshot}, NOW)


def test_same_time_observation_does_not_require_forecast_capture():
    station, _, metadata, site = station_fixture()
    payloads = {
        "metadata": metadata,
        "site": site,
        "stageflow": None,
        "primary": {
            "features": [
                {
                    "properties": {
                        "monitoring_location_id": "USGS-12345678",
                        "parameter_code": "00065",
                        "unit_of_measure": "ft",
                        "statistic_id": "00011",
                        "time": NOW,
                        "value": "8",
                        "approval_status": "Provisional",
                        "time_series_id": "abc",
                        "qualifier": None,
                    }
                }
            ],
            "links": [],
        },
    }
    receipts = {k: {"finished_at": NOW} for k in payloads}
    snapshot, problems = normalize_cycle(station, payloads, receipts)
    assert snapshot["observations"][0]["value"] == 8
    assert snapshot["forecast"] == [] and problems
    metadata["flood"]["categories"]["minor"]["stage"] = 9
    snapshot, problems = normalize_cycle(station, payloads, receipts)
    assert snapshot is None and "contract changed" in problems[0]


def test_datum_revision_quarantined():
    station, _, metadata, site = station_fixture()
    original = deepcopy(station["primary_contract"])
    metadata["datums"]["vertical"]["value"][0]["value"] = 51
    site["properties"]["altitude"] = 51
    snapshot, problems = normalize_cycle(station, {"metadata": metadata, "site": site}, {})
    assert snapshot is None and problems
    assert station["primary_contract"] == original


def test_effective_commit_time_is_disk_receipt_not_preparation(tmp_path, monkeypatch):
    directory = tmp_path / "initial"
    directory.mkdir()
    monkeypatch.setattr(
        "disastertrace.hydro_shadow_v1.pipeline.stamp", lambda: "2026-09-12T10:00:01Z"
    )
    save_submissions(directory, [{"target_id": "h001", "committed_at": "2026-09-12T09:59:59Z"}])
    commits = load_commits(tmp_path)
    assert commits[0]["committed_at"] == "2026-09-12T10:00:01Z"
    assert commits[0]["prepared_at"] == "2026-09-12T09:59:59Z"
    with pytest.raises(FileExistsError):
        save_submissions(directory, [])


def test_request_urls_bind_identity_variable_and_time_support():
    station, _, _, _ = station_fixture()
    urls = provider_urls(station, NOW)
    assert "00065" in urls["primary"] and "USGS-12345678" in urls["primary"]
    assert "00060" not in urls["primary"]
    assert set(urls) == {"metadata", "stageflow", "site", "primary"}


def test_modified_frozen_source_is_rejected(tmp_path):
    write_new(tmp_path / "FREEZE.json", {"files": {"source.py": "wrong-digest"}})
    (tmp_path / "source.py").write_text("x=1\n")
    with pytest.raises(ValueError, match="frozen file changed"):
        verify_freeze(tmp_path)
    assert strict_json((tmp_path / "FREEZE.json").read_bytes())["files"]


def test_bounded_worker_entire_lifecycle_without_network(tmp_path, monkeypatch):
    station, initial, metadata, site = station_fixture()
    registry = make_registry([station], {"TEST1": initial}, NOW)
    schedule = [NOW, "2026-09-12T13:00:00Z", "2026-09-13T10:00:00Z"]
    registry["poll_at"] = schedule
    registry["max_logical_downloads"] = 12
    write_new(tmp_path / "REGISTRY.json", registry)
    (tmp_path / "initial").mkdir()
    write_new(tmp_path / "initial/TEST1.json", initial)
    write_new(
        tmp_path / "FREEZE.json",
        {"files": {"REGISTRY.json": file_hash(tmp_path / "REGISTRY.json")}},
    )
    current = [NOW]
    monkeypatch.setattr("disastertrace.hydro_shadow_v1.pipeline.stamp", lambda: current[0])

    def advance(_):
        current[0] = next(at for at in schedule if at > current[0])

    monkeypatch.setattr("disastertrace.hydro_shadow_v1.pipeline.time.sleep", advance)
    calls = []

    def capture(url, path):
        calls.append(url)
        role = path.name
        if role == "metadata":
            body = metadata
        elif role == "site":
            body = site
        elif role == "stageflow":
            body = {
                "forecast": {
                    "primaryName": "Stage",
                    "primaryUnits": "ft",
                    "issuedTime": NOW,
                    "data": [
                        {"validTime": p["valid_at"], "generatedTime": NOW, "primary": p["value"]}
                        for p in initial["forecast"]
                    ],
                }
            }
        else:
            body = {
                "features": [
                    {
                        "properties": {
                            "monitoring_location_id": "USGS-12345678",
                            "parameter_code": "00065",
                            "unit_of_measure": "ft",
                            "statistic_id": "00011",
                            "time": at,
                            "value": "9",
                            "approval_status": "Provisional",
                            "time_series_id": "fixture",
                            "qualifier": None,
                        }
                    }
                    for at in [NOW] + [p["valid_at"] for p in initial["forecast"]]
                    if at <= current[0]
                ],
                "links": [],
            }
        return body, {"finished_at": current[0], "bytes": 1}

    monkeypatch.setattr("disastertrace.hydro_shadow_v1.pipeline.supervised_capture", capture)
    worker(tmp_path)
    final = strict_json((tmp_path / "run/FINISHED.json").read_bytes())
    assert final["state"] == "finished_bounded_collection" and len(calls) == 12
    results = strict_json((tmp_path / "run/cycle_002/SETTLEMENTS.json").read_bytes())
    assert all(r["status"] == "settled_provisional" for r in results)
    assert all(len(r["policies"]) == 4 for r in results)
    with pytest.raises(FileExistsError):
        worker(tmp_path)
    assert len(calls) == 12
