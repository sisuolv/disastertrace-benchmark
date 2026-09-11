"""Audit captured hydrology joins without promoting provisional values to final Gold."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TARGETS = ("2026-09-10T18:00:00Z", "2026-09-11T00:00:00Z")


def at(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def encode(value):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(type(value).__name__)


def capture(batch, name, checked):
    directory = ROOT / batch
    record = json.loads((directory / (name + ".json")).read_text())
    if record.get("status") != "received" or record.get("complete") is not True:
        raise ValueError(f"required capture incomplete: {name}")
    path = directory / record["raw"]
    raw = path.read_bytes()
    if len(raw) != record["bytes"] or hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError(f"capture bytes changed: {name}")
    checked[name] = {"path": str(path.relative_to(ROOT)), "url": record["url"],
                     "sha256": record["sha256"], "captured_at": record["finished_at"]}
    return json.loads(raw, parse_float=Decimal)


def observations(body, site_id, parameter):
    if any(link.get("rel") == "next" for link in body.get("links", [])):
        raise ValueError("observation sample paginated")
    result = {}
    for feature in body["features"]:
        row = feature["properties"]
        if row["monitoring_location_id"] != "USGS-" + site_id or row["parameter_code"] != parameter:
            raise ValueError("observation identity mismatch")
        time = at(row["time"])
        if time in result:
            raise ValueError("ambiguous observation time")
        value = Decimal(row["value"])
        if not value.is_finite():
            raise ValueError("nonfinite observation")
        result[time] = {**row, "value": value}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory must be new")
    checked, stations, points = {}, [], []
    for lid, metadata_batch, data_batch, basin in [
        ("SCOC1", "captures_02", "captures_03", "Eel River"),
        ("GUEC1", "captures_03", "captures_04", "Russian River"),
    ]:
        key = lid.lower()
        metadata = capture(metadata_batch, "nwps-" + key + "-metadata", checked)
        site = capture(data_batch, "usgs-" + key + "-site", checked)["properties"]
        stageflow = capture(data_batch, "nwps-" + key + "-stageflow", checked)
        series = capture(data_batch, "usgs-" + key + "-00065", checked)
        if metadata["usgsId"] != site["monitoring_location_number"] or metadata["lid"] != lid:
            raise ValueError("official gauge mapping mismatch")
        if site["id"] != "USGS-" + metadata["usgsId"]:
            raise ValueError("USGS site identity mismatch")
        datums = metadata["datums"]["vertical"]["value"]
        datum_matches = [d for d in datums if d["abbrev"] == site["vertical_datum"]
                         and Decimal(str(d["value"])) == Decimal(str(site["altitude"]))]
        if len(datum_matches) != 1:
            raise ValueError("current datum metadata not aligned")
        stage = observations(series, metadata["usgsId"], "00065")
        ordered = sorted(stage)
        gaps = Counter(int((b - a).total_seconds()) for a, b in zip(ordered, ordered[1:]))
        threshold = Decimal(str(metadata["flood"]["categories"]["minor"]["stage"]))
        if threshold in (Decimal("-999"), Decimal("-9999")):
            raise ValueError("missing stage threshold")
        if metadata["flood"]["stageUnits"] != "ft":
            raise ValueError("threshold unit mismatch")
        for role in ("observed", "forecast"):
            if stageflow[role]["primaryName"] != "Stage" or stageflow[role]["primaryUnits"] != "ft":
                raise ValueError("stageflow variable or unit mismatch")
        observed_nwps = {at(r["validTime"]): r for r in stageflow["observed"]["data"]}
        forecasts = {at(r["validTime"]): r for r in stageflow["forecast"]["data"]}
        if len(observed_nwps) != len(stageflow["observed"]["data"]):
            raise ValueError("duplicate provider observation times")
        if len(forecasts) != len(stageflow["forecast"]["data"]):
            raise ValueError("duplicate forecast times")
        differences = []
        for time, row in stage.items():
            if row["unit_of_measure"] != "ft" or time not in observed_nwps:
                raise ValueError("no matching NWPS stage observation")
            differences.append(row["value"] - Decimal(str(observed_nwps[time]["primary"])))
        if any(d != 0 for d in differences):
            raise ValueError("current provider observations disagree; quarantine required")
        for target in TARGETS:
            time = at(target)
            observation = stage[time]
            forecast = forecasts[time]
            issued = stageflow["forecast"]["issuedTime"]
            if at(issued) >= time or at(forecast["generatedTime"]) >= time:
                raise ValueError("forecast created after target")
            value = Decimal(str(forecast["primary"]))
            provisional = observation["approval_status"] != "Approved"
            points.append({
                "station_lid": lid, "usgs_id": metadata["usgsId"], "basin": basin,
                "target_time": target, "variable": "gage_height", "unit": "ft",
                "threshold": threshold, "threshold_kind": "current_minor_flood_stage_snapshot",
                "forecast_issue_time": issued, "forecast_row_generated_time": forecast["generatedTime"],
                "forecast_value": value, "observed_value": observation["value"],
                "preview_y": int(observation["value"] >= threshold),
                "confirmed_y": None if provisional else int(observation["value"] >= threshold),
                "outcome_approval": observation["approval_status"],
                "outcome_time_series_id": observation["time_series_id"],
                "observation_qualifier": observation["qualifier"],
                "historical_available_at": None,
                "time_mode": "controlled_replay_candidate_only",
                "formal_eligible": False,
                "blocking_reasons": ["no_historical_availability_proof", "threshold_vintage_not_proven_for_target"]
                                    + (["provisional_outcome"] if provisional else []),
            })
        stations.append({
            "station_lid": lid, "usgs_id": metadata["usgsId"], "basin": basin,
            "name": metadata["name"], "official_mapping_verified": True,
            "current_datum_name": site["vertical_datum"],
            "current_datum_numeric_value": site["altitude"],
            "datum_limit": "Current metadata agreement; no historical datum validity or general altitude conversion inferred.",
            "stage_unit": "ft", "minor_flood_stage": threshold,
            "observations_sampled": len(stage), "same_time_provider_pairs": len(differences),
            "same_time_values_equal": True, "observed_interval_seconds": dict(gaps),
            "outcome_approval_counts": dict(Counter(r["approval_status"] for r in stage.values())),
            "nwps_forecast_rows": len(forecasts), "nwps_forecast_issue_time": stageflow["forecast"]["issuedTime"],
            "hydronotes": metadata["hydronotes"],
            "admission": "selected_source_chain; controlled_preview_only_pending_outcomes_time_and_threshold_vintage",
        })

    flow = observations(capture("captures_03", "usgs-scoc1-00060", checked), "11477000", "00060")
    if any(r["unit_of_measure"] != "ft^3/s" for r in flow.values()):
        raise ValueError("unexpected discharge unit")
    ensemble_reports, ensemble_points = [], []
    for batch, name in [("captures_03", "hefs-scoc1-ensemble"),
                        ("captures_04", "hefs-scoc1-ensemble-earlier")]:
        groups = capture(batch, name, checked)
        if len(groups) != 1 or not groups[0]:
            raise ValueError("ambiguous or empty ensemble group")
        members = groups[0]
        if len({m["ensemble_member_index"] for m in members}) != len(members):
            raise ValueError("duplicate ensemble members")
        common = members[0]
        grids, indexed = [], []
        for member in members:
            if member["location_id"] != "SCOC1" or member["parameter_id"] != "QINE" or member["units"] != "CFS":
                raise ValueError("ensemble variable/identity mismatch")
            for field in ("forecast_datetime", "creation_datetime", "start_datetime", "end_datetime", "type"):
                if member[field] != common[field]:
                    raise ValueError("mixed ensemble product metadata")
            events = member["events"]
            grid = [at(e["valid_datetime"]) for e in events]
            if len(set(grid)) != len(grid) or grid != sorted(grid):
                raise ValueError("invalid ensemble time grid")
            for event in events:
                if event["value"] is None or not Decimal(str(event["value"])).is_finite():
                    raise ValueError("missing or nonfinite ensemble value")
            grids.append(grid)
            indexed.append({at(e["valid_datetime"]): Decimal(str(e["value"])) for e in events})
        if any(g != grids[0] for g in grids):
            raise ValueError("ensemble grids differ")
        step = int(common["time_step_multiplier"])
        if common["time_step_unit"] != "second" or any(int((b-a).total_seconds()) != step for a,b in zip(grids[0],grids[0][1:])):
            raise ValueError("ensemble cadence mismatch")
        ensemble_reports.append({
            "capture_id": name, "station_lid": "SCOC1", "usgs_id": "11477000",
            "forecast_datetime": common["forecast_datetime"], "creation_datetime": common["creation_datetime"],
            "members": len(members), "times_per_member": len(grids[0]),
            "member_time_values": sum(len(m["events"]) for m in members),
            "start": common["start_datetime"], "end": common["end_datetime"],
            "parameter": "QINE", "type": common["type"], "unit": "CFS",
            "cadence_seconds": step,
            "observed_flags": sorted({str(e.get("flag")) for m in members for e in m["events"]}),
            "flag_semantics": "Preserved; numeric/grid audit is not independent scientific QC certification.",
            "probability_status": "No operational flow threshold admitted; no flood probability assigned.",
        })
        for target in TARGETS:
            time = at(target)
            if at(common["creation_datetime"]) >= time:
                raise ValueError("ensemble not produced before target")
            values = [m[time] for m in indexed]
            ensemble_points.append({
                "station_lid": "SCOC1", "target_time": target,
                "forecast_datetime": common["forecast_datetime"],
                "creation_datetime": common["creation_datetime"],
                "member_count": len(values), "ensemble_min_cfs": min(values), "ensemble_max_cfs": max(values),
                "ensemble_mean_cfs_decimal_precision_28": sum(values) / len(values),
                "observed_discharge_cfs": flow[time]["value"],
                "outcome_approval": flow[time]["approval_status"],
                "source_unit_equivalence": "CFS equals ft^3/s; no stage conversion performed",
                "preview_only": True,
            })

    report = {
        "status": "data_join_audit_complete_not_formal_admission",
        "station_chains": stations, "stations": len(stations), "basins": len({s["basin"] for s in stations}),
        "stage_observations_sampled": sum(s["observations_sampled"] for s in stations),
        "point_target_previews": len(points), "point_preview_labels": dict(Counter(str(r["preview_y"]) for r in points)),
        "confirmed_point_outcomes": sum(r["confirmed_y"] is not None for r in points),
        "same_station_discharge_observations": len(flow), "ensemble_products": ensemble_reports,
        "source_bindings": checked, "formal_warning_episodes_created": 0,
        "limitations": ["Provisional observations; no historical availability proof; current threshold snapshots.",
                        "Convenience samples from two basins, not independent flood event groups or representative monitoring.",
                        "No observed flood-positive in the sampled target points; no NIMS camera returned for these sites.",
                        "NWPS observations duplicate USGS measurements here; they are alignment checks, not independent evidence.",
                        "HEFS discharge has no admitted stage conversion or flow threshold in this audit."],
    }
    args.output_dir.mkdir(parents=True)
    for name, rows in [("stage_point_pairs_private.jsonl", points), ("flow_point_pairs_private.jsonl", ensemble_points)]:
        with (args.output_dir / name).open("x") as stream:
            for row in rows:
                stream.write(json.dumps(row, default=encode, sort_keys=True) + "\n")
    fields = ["station_lid", "usgs_id", "basin", "current_datum_name", "current_datum_numeric_value",
              "minor_flood_stage", "observations_sampled", "nwps_forecast_rows", "admission"]
    with (args.output_dir / "JOIN_TABLE.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(stations)
    (args.output_dir / "AUDIT.json").write_text(json.dumps(report, default=encode, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("source_bindings", "station_chains")},
                     default=encode, indent=2))


if __name__ == "__main__":
    main()
