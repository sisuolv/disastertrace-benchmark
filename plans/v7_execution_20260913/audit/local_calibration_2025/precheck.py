"""Validate prior-period native samples; never fit on the January evaluation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "disastertrace-starter/src"))

from disastertrace.monitoring_v1.providers.aviation import parse_metar, parse_taf  # noqa: E402
from disastertrace.monitoring_v1.support import classify  # noqa: E402

HOUR = 3_600_000_000


def dump(name, value):
    with (HERE / name).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def capture(directory, identity):
    metadata = json.loads((directory / (identity + ".json")).read_text())
    raw = (directory / (identity + ".body")).read_bytes()
    if not metadata["complete"] or metadata["http_status"] != 200 or metadata["bytes"] != len(raw) or metadata["sha256"] != hashlib.sha256(raw).hexdigest():
        raise ValueError("Incomplete or corrupt source capture: " + identity)
    return raw, metadata


def rows(raw):
    reader = csv.reader(io.StringIO(raw.decode()), strict=True)
    header = next(reader)
    if len(set(header)) != len(header):
        raise ValueError("Nonunique CSV header")
    result = []
    for values in reader:
        if len(values) != len(header):
            raise ValueError("CSV field count")
        result.append(dict(zip(header, values)))
    return result


def prepare():
    native_requests, report = [], {}
    for station in ["KDEN", "KCOS", "KPUB"]:
        raw, receipt = capture(HERE / "captures_01", "metar-routine-" + station)
        parsed, failures, by_hour = [], [], defaultdict(dict)
        for row in rows(raw):
            try:
                product = parse_metar(row["metar"], observation_time=row["valid"].replace(" ", "T") + ":00Z", report_type="routine")
                if product.station != station or row["station"] not in (station, station[1:]):
                    raise ValueError("Station mismatch")
                value = {"station": station, "observation_time": product.observation_time,
                         "visibility": None if product.visibility is None else product.visibility.to_dict(),
                         "quality_flags": product.quality_flags, "raw": product.raw,
                         "below_1000m": "undetermined" if product.visibility is None else classify(product.visibility, "lt", 1000)}
                parsed.append(value)
                by_hour[product.observation_time // HOUR][(product.observation_time, product.raw)] = value
            except (ValueError, KeyError) as exc:
                failures.append({"row": row, "error": str(exc)})
        dump(station + "_METAR_PARSED.json", {"rows": parsed, "failures": failures, "source_sha256": receipt["sha256"]})
        usable = [next(iter(v.values())) for v in by_hour.values() if len(v) == 1 and not next(iter(v.values()))["quality_flags"] and next(iter(v.values()))["visibility"] is not None]
        catalogue_raw, catalogue_receipt = capture(HERE / "captures_01", "taf-catalog-" + station)
        catalogue = rows(catalogue_raw)
        products = {}
        for row in catalogue:
            if row["station"] != station:
                raise ValueError("Catalogue station mismatch")
            if row["product_id"] in products and products[row["product_id"]] != row["valid"]:
                raise ValueError("Conflicting catalogue issuance")
            products[row["product_id"]] = row["valid"]
        by_day = defaultdict(list)
        for identity, issued in products.items():
            by_day[issued[:10]].append((issued, identity))
        selected = []
        for day in ["2025-12-01", "2025-12-02", "2025-12-03"]:
            if by_day[day]:
                issued, identity = min(by_day[day])
                selected.append(identity)
                native_requests.append({"id": "taf-" + identity, "url": "https://mesonet.agron.iastate.edu/api/1/nwstext/" + identity,
                                        "max_bytes": 65536, "timeout": 60, "catalog_metadata": {"station": station, "issued_at": issued},
                                        "purpose": "First product by native catalogue issue on each fixed prior day; no event-label selection"})
        report[station] = {"native_reports": len(parsed), "parse_failures": len(failures), "distinct_report_hours": len(by_hour),
                           "unambiguous_quality_accepted_hours": len(usable), "requested_hours": 72,
                           "usable_hour_states_below_1000m": dict(Counter(r["below_1000m"] for r in usable)),
                           "metar_bytes": len(raw), "taf_catalogue_bytes": len(catalogue_raw),
                           "taf_catalogue_rows": len(catalogue), "distinct_taf_products": len(products),
                           "native_sample_product_ids": selected, "catalogue_sha256": catalogue_receipt["sha256"]}
    dump("STAGE1.json", {"stations": report, "source_window": "2025-12-01T00:00Z/2025-12-04T00:00Z", "new_model_calls": 0, "fitting_performed": False})
    dump("NATIVE_FETCH_01.json", {"schema": "disastertrace.monitoring.public_capture.v1", "transport": "curl",
                                "allowed_hosts": ["mesonet.agron.iastate.edu"], "pause_seconds": 0.2,
                                "limits": {"requests": len(native_requests), "bytes": sum(r["max_bytes"] + 1 for r in native_requests)},
                                "requests": native_requests})


def finish():
    stage1 = json.loads((HERE / "STAGE1.json").read_text())
    manifest = json.loads((HERE / "native_01/MANIFEST.json").read_text())
    results, joins, failures = [], [], []
    metar = {}
    for station in stage1["stations"]:
        metar[station] = defaultdict(list)
        for row in json.loads((HERE / (station + "_METAR_PARSED.json")).read_text())["rows"]:
            metar[station][row["observation_time"] // HOUR].append(row)
    for receipt in manifest["rows"]:
        try:
            raw, verified = capture(HERE / "native_01", receipt["id"])
            metadata = verified["catalog_metadata"]
            product = parse_taf(raw.decode(), station=metadata["station"], archive_issue=metadata["issued_at"].replace(" ", "T") + ":00Z")
            projections = []
            if product.status == "active":
                cutoff = ((product.issued_at + 120_000_000) // HOUR + 1) * HOUR
                for lead in (1, 3, 6):
                    start = cutoff + lead * HOUR
                    end = start + HOUR
                    if product.valid_start <= start < end <= product.valid_end:
                        projection = product.project(start, end)
                        projections.append(projection)
                        references = {(r["observation_time"], r["raw"]): r for r in metar[product.station][start // HOUR]}
                        settled = len(references) == 1 and not next(iter(references.values()))["quality_flags"] and next(iter(references.values()))["visibility"] is not None
                        joins.append({"source_id": receipt["id"], "station": product.station, "cutoff": cutoff,
                                      "lead_hours": lead, "target_start": start, "target_end": end,
                                      "unique_native_observation": settled,
                                      "reference": next(iter(references.values())) if settled else None,
                                      "projection": projection})
            results.append({"source_id": receipt["id"], "station": product.station, "issued_at": product.issued_at,
                            "valid_start": product.valid_start, "valid_end": product.valid_end,
                            "status": product.status, "clause_operators": [c.operator for c in product.clauses],
                            "projections": projections, "bytes": len(raw), "sha256": verified["sha256"]})
        except (ValueError, KeyError) as exc:
            failures.append({"source_id": receipt["id"], "failure": str(exc)})
    dump("NATIVE_PARSE.json", {"products": results, "failures": failures})
    dump("SAMPLE_JOINS.json", joins)
    estimates = {}
    for station, s in stage1["stations"].items():
        native = [p for p in results if p["station"] == station]
        mean_bytes = sum(p["bytes"] for p in native) / len(native) if native else None
        estimates[station] = {"assumption": "Linear 31/3 extrapolation from this three-day sample; not measured monthly coverage or reliability",
                             "metar_bytes_estimate_31days": math_ceil(s["metar_bytes"] * 31 / 3),
                             "taf_catalogue_bytes_estimate_31days": math_ceil(s["taf_catalogue_bytes"] * 31 / 3),
                             "taf_product_requests_estimate_31days": math_ceil(s["distinct_taf_products"] * 31 / 3),
                             "native_taf_body_bytes_estimate_31days": None if mean_bytes is None else math_ceil(s["distinct_taf_products"] * 31 / 3 * mean_bytes)}
    first_manifest = json.loads((HERE / "captures_01/MANIFEST.json").read_text())
    report = {"completed_at": datetime.now(timezone.utc).isoformat(), "scope": "Fresh three-day Front prior-Dec2025 scientific source feasibility, not full calibration training",
              "local_preexisting_dec2025_front_chain_found": False, "inventory_scope": "See LOCAL_INVENTORY.json; no claim that every external storage location was searched",
              "successful_http200_requests": sum(r["complete"] and r["http_status"] == 200 for m in (first_manifest, manifest) for r in m["rows"]),
              "fresh_bytes": first_manifest["bytes"] + manifest["bytes"], "stations": stage1["stations"],
              "parsed_native_taf_products": len(results), "native_taf_parse_failures": failures,
              "projected_fixed_hour_examples": len(joins), "examples_joined_to_native_hourly_reference": sum(r["unique_native_observation"] for r in joins),
              "fresh_native_forecast_observation_pairing_verified": bool(joins) and any(r["unique_native_observation"] for r in joins),
              "monthly_estimates": estimates,
              "remaining_inputs": ["Complete fixed prior-period native TAF bulletins for KDEN/KCOS/KPUB including revisions, cancellations, unparsed cases", "Complete same-period routine METAR with original duplicate/correction/quality rules", "Chronological fit/purge/check contract matching Bay comparator, frozen before rerun", "Local/source-pooled/shrunk mappings with no January evaluation fitting", "Separate Dec2025 Front chain before claiming local calibration for Jan2026", "Historical first-seen chronology if seeking stronger-than-declared-replay availability admission"],
              "no_fitting": True, "evaluation_january_outcomes_not_read": True, "new_model_calls": 0,
              "admission": "scientific_small_sample_verified; full_local_calibration_not_completed", "original_first_seen_proven": False,
              "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    dump("REPORT.json", report)
    print(json.dumps({k: v for k, v in report.items() if k not in {"stations", "monthly_estimates", "remaining_inputs"}}, indent=2))


def math_ceil(value):
    return int(-(-value // 1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["prepare", "finish"])
    options = parser.parse_args()
    prepare() if options.stage == "prepare" else finish()
