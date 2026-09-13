"""Verify bounded CNRFC archives without treating a current retrieval as first-seen."""
import csv
import datetime as dt
import io
import json
import math
import zipfile
from collections import Counter
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read_archive(name, interval_hours):
    with zipfile.ZipFile(ROOT / "raw" / name) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != 1:
            raise ValueError("ZIP CRC/member validation failed")
        member = archive.namelist()[0]
        rows = list(csv.reader(io.StringIO(archive.read(member).decode())))
    ids, parameters = rows[0], rows[1]
    if ids[0] != "GMT":
        raise ValueError("Time basis is not the expected GMT")
    times, values = [], []
    for row in rows[2:]:
        if len(row) != len(ids):
            raise ValueError("CSV column count mismatch")
        times.append(dt.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc))
        vals = [float(v) for v in row[1:]]
        if any(not math.isfinite(v) or v < 0 for v in vals):
            raise ValueError("Nonfinite or negative forecast")
        values.append(vals)
    if any((b - a).total_seconds() != interval_hours * 3600 for a, b in pairwise(times)):
        raise ValueError("Nonuniform archive time support")
    nominal_init = dt.datetime.strptime(member[:10], "%Y%m%d%H").replace(tzinfo=dt.timezone.utc)
    if nominal_init != times[0]:
        raise ValueError("Filename cycle and first forecast timestamp differ")
    selected_indices = [i for i, v in enumerate(ids[1:]) if v == "SCOC1"]
    expected_parameter = "QINE" if interval_hours == 1 else "SQME"
    if {parameters[i + 1] for i in selected_indices} != {expected_parameter}:
        raise ValueError("Native parameter mismatch")
    target = {time: [row[i] for i in selected_indices] for time, row in zip(times, values)}
    report = {"archive": name, "zip_member": member, "zip_crc_pass": True,
              "row_count": len(times), "trace_columns_by_exact_identifier": dict(Counter(ids[1:])),
              "target_trace_count": len(selected_indices), "target_identifier": "SCOC1",
              "native_parameter": expected_parameter, "declared_unit_from_official_ui": "kcfs",
              "time_basis": "GMT", "step_hours": interval_hours,
              "nominal_cycle": nominal_init.isoformat(), "first_valid": times[0].isoformat(), "last_valid": times[-1].isoformat(),
              "exact_target_values_checked": len(times) * len(selected_indices),
              "all_finite_nonnegative_values_checked": sum(len(v) for v in values),
              "has_distinct_SCOC1F_identifier": "SCOC1F" in ids,
              "historical_first_seen_verified": False, "historical_rating_curve_verified": False}
    return report, target


def main():
    reports, hourly = [], []
    for resolution, hours in [("daily", 24), ("hourly", 1)]:
        for date in ["20240101", "20240102"]:
            report, target = read_archive(f"cnrfc_{resolution}_{date}.zip", hours)
            reports.append(report)
            if hours == 1:
                hourly.append((report, target))
    rows = json.loads((ROOT / "raw/usgs_scoc1_flow_20240102_04.json").read_text())
    if any(link.get("rel") == "next" for link in rows.get("links", [])):
        raise ValueError("Observation response is paginated")
    observed = {}
    quality = Counter()
    for feature in rows["features"]:
        row = feature["properties"]
        if not (row["monitoring_location_id"] == "USGS-11477000" and row["parameter_code"] == "00060"
                and row["unit_of_measure"] == "ft^3/s" and row["statistic_id"] == "00011"):
            raise ValueError("USGS identity, unit, or support mismatch")
        value = float(row["value"])
        if not math.isfinite(value) or value < 0:
            raise ValueError("Invalid observation value")
        t = dt.datetime.fromisoformat(row["time"].replace("Z", "+00:00"))
        if t in observed:
            raise ValueError("Duplicate observed target time")
        observed[t] = row
        quality[row["approval_status"]] += 1
    records = []
    target_times = [dt.datetime(2024, 1, d, 12, tzinfo=dt.timezone.utc) for d in [2, 3, 4]]
    for report, forecasts in hourly:
        init = dt.datetime.fromisoformat(report["nominal_cycle"])
        for t in target_times:
            obs = observed.get(t)
            records.append({
                "record_id": f"SCOC1_{init.strftime('%Y%m%d%H')}_{t.strftime('%Y%m%d%H')}",
                "gauge_id": "SCOC1", "usgs_id": "11477000", "variable": "native_QINE_discharge_candidate",
                "native_forecast_parameter": "QINE",
                "unit": "ft^3/s", "native_unit": "kcfs", "unit_multiplier": 1000,
                "forecast_reference_time_nominal": init.isoformat(), "valid_time": t.isoformat(),
                "lead_hours": (t - init).total_seconds() / 3600,
                "model_visible": {"member_values_cfs": [v * 1000 for v in forecasts[t]], "member_identity_kind": "CSV_column_position_no_explicit_id"},
                "evaluator_only": {"observation_cfs": float(obs["value"]) if obs else None,
                    "approval_status": obs["approval_status"] if obs else None, "qualifier": obs.get("qualifier") if obs else None},
                "historical_public_available_at": None,
                "same_target_history_technical_pair": obs is not None,
                "forecast_vs_usgs_quantity_equivalence_verified": False,
                "forecast_regulation_mode_verified": False,
                "continuous_numeric_scoring_qualified": False,
                "flood_threshold_contract_ready": False, "formal_monitoring_eligible": False,
            })
    common = set(hourly[0][1]) & set(hourly[1][1])
    changed = sum(hourly[0][1][t] != hourly[1][1][t] for t in common)
    result = {"archives": reports, "same_target_hourly_cycle_overlap": len(common),
              "changed_forecast_vectors_at_common_times": changed,
              "observation_count": len(observed), "observation_quality": dict(quality),
              "exact_timestamp_joins_by_cycle": {r["nominal_cycle"]: len(set(f) & set(observed)) for r, f in hourly},
              "small_sample_pair_count": sum(r["same_target_history_technical_pair"] for r in records),
              "hefs_api_2024_exact_queries_empty": all(json.loads((ROOT / "raw" / f"hefs_scoc1_2024-01-0{d}.json").read_text()) == [] for d in [1, 2]),
              "formal_monitoring_admissions": 0, "fresh_model_calls": 0,
              "physical_shared_archive_asset_verified": True,
              "natural_supplemental_shared_evidence_value_verified": False,
              "historical_first_seen_verified": False,
              "forecast_vs_usgs_quantity_equivalence_verified": False,
              "forecast_regulation_mode_verified": False,
              "continuous_numeric_scoring_qualified": False,
              "warning": "Daily SQME/aliases are not interchangeable with hourly QINE. Exact timestamp joins do not establish physical target equivalence. kcfs converts to CFS; stage thresholds do not."}
    (ROOT / "ARCHIVE_VALIDATION.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (ROOT / "archive_flow_pairs.json").write_text(json.dumps({"schema_version": "hydro_archive_pairs_v1", "records": records}, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "archives"}, indent=2))


if __name__ == "__main__":
    main()
