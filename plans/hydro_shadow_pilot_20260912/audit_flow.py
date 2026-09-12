"""Verify real ensemble members and matched instantaneous flow observations."""

import argparse
from collections import Counter
from pathlib import Path

from audit_inputs import BUNDLE, read_source
from disastertrace.hydro_shadow_v1.capture import stamp, write_new
from disastertrace.hydro_shadow_v1.core import instant, number, utc


def audit(output):
    records = []
    for lid, site in (("NRWI4", "05486000"), ("CRHA2", "15493400")):
        key = lid.lower()
        ensembles, ensemble_receipt = read_source(
            BUNDLE / "hefs_01" / f"{key}-hefs-ensemble.raw"
        )
        flow, flow_receipt = read_source(BUNDLE / "flow_01" / f"{key}-usgs-flow.raw")
        metadata, metadata_receipt = read_source(
            BUNDLE / "stations_01" / f"{key}-metadata.raw"
        )
        if len(ensembles) != 1 or not ensembles[0]:
            raise ValueError("one nonempty HEFS forecast product required")
        members = ensembles[0]
        member_ids = {m["ensemble_member_index"] for m in members}
        if len(member_ids) != len(members):
            raise ValueError("ensemble member identity is duplicated")
        series = {}
        for member in members:
            if not (
                member["location_id"] == lid
                and member["parameter_id"] == "QINE"
                and member["units"] == "CFS"
                and member["type"] == "instantaneous"
                and instant(member["forecast_datetime"])
                <= instant(member["creation_datetime"])
                <= instant(ensemble_receipt["finished_at"])
            ):
                raise ValueError("HEFS variable, support, identity or time mismatch")
            identity = (
                member["forecast_datetime"],
                member["creation_datetime"],
                member["start_datetime"],
            )
            if identity != (
                members[0]["forecast_datetime"],
                members[0]["creation_datetime"],
                members[0]["start_datetime"],
            ):
                raise ValueError("mixed HEFS versions in one sample")
            points = {}
            for event in member["events"]:
                if event["flag"] != "0":
                    raise ValueError("HEFS quality flag is not admitted")
                valid, value = utc(event["valid_datetime"]), number(event["value"])
                if valid in points or value < 0:
                    raise ValueError("duplicate time or negative discharge")
                points[valid] = value
            series[member["ensemble_member_index"]] = points
        common = set.intersection(*(set(points) for points in series.values()))
        if any(set(points) != common for points in series.values()):
            raise ValueError("ensemble members have different valid-time support")
        if any(link.get("rel") == "next" for link in flow.get("links", [])):
            raise ValueError("USGS flow sample is paginated")
        observations, excluded = {}, Counter()
        for feature in flow["features"]:
            row = feature["properties"]
            if not (
                row["monitoring_location_id"] == "USGS-" + site
                and row["parameter_code"] == "00060"
                and row["statistic_id"] == "00011"
                and row["unit_of_measure"] == "ft^3/s"
            ):
                raise ValueError(
                    "USGS flow identity, unit or instantaneous support mismatch"
                )
            try:
                val, valid = number(row["value"]), utc(row["time"])
                if val < 0 or instant(valid) > instant(flow_receipt["finished_at"]):
                    raise ValueError("invalid/future discharge measurement")
                if row.get("qualifier") not in (None, "") or row[
                    "approval_status"
                ] not in ("Provisional", "Approved"):
                    raise ValueError("ineligible observation quality")
            except (ValueError, TypeError) as exc:
                excluded[str(exc)] += 1
                continue
            item = {
                "value": val,
                "quality": row["approval_status"],
                "series": row["time_series_id"],
            }
            if valid in observations and observations[valid] != item:
                raise ValueError("ambiguous discharge observation")
            observations[valid] = item
        threshold = metadata["flood"]["categories"]["minor"]["flow"]
        flow_threshold = None
        if threshold not in (-999, -9999):
            flow_threshold = number(threshold)
        records.append(
            {
                "lid": lid,
                "usgs_id": site,
                "member_count": len(members),
                "valid_times_per_member": len(common),
                "ensemble_values_verified": sum(len(v) for v in series.values()),
                "issue_at": members[0]["forecast_datetime"],
                "creation_at": members[0]["creation_datetime"],
                "valid_start": min(common),
                "valid_end": max(common),
                "observations_verified": len(observations),
                "observation_quality": dict(
                    Counter(p["quality"] for p in observations.values())
                ),
                "exact_forecast_observation_time_overlap": len(
                    common & set(observations)
                ),
                "flow_threshold_cfs": flow_threshold,
                "continuous_flow_chain_verified": True,
                "minor_flood_warning_chain_verified": flow_threshold is not None,
                "historical_public_availability_proven": False,
                "historical_forecast_skill_scored": False,
                "excluded_observations": dict(excluded),
                "sources": {
                    "ensemble": ensemble_receipt,
                    "observations": flow_receipt,
                    "metadata": metadata_receipt,
                },
            }
        )
    report = {
        "created_at": stamp(),
        "records": records,
        "interpretation": "real flow data admission; stage thresholds cannot score CFS forecasts; no model or online result",
    }
    write_new(output, report)
    for record in records:
        print({k: v for k, v in record.items() if k != "sources"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    audit(parser.parse_args().out)
