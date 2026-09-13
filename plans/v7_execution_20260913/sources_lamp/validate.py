"""Offline verification of captured LAMP scientific data and source semantics."""

import csv
import gzip
import hashlib
import io
import json
import tarfile
from collections import Counter
from pathlib import Path

from decode import LAV_HEADER, VISIBILITY_THRESHOLDS, parse_fltcat, parse_lav

ROOT = Path(__file__).resolve().parent
STATIONS = {"KSFO", "KDEN", "KAPA"}


def save(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def validate_receipts():
    receipts = []
    for path in sorted((ROOT / "raw").glob("*.receipt.json")):
        receipt = json.loads(path.read_text())
        body = (ROOT / receipt["path"]).read_bytes()
        assert hashlib.sha256(body).hexdigest() == receipt["sha256"], path
        assert len(body) == receipt["bytes"], path
        receipts.append(receipt)
    return receipts


def historical_lav():
    decoded = []
    captures = []
    for name in ("lav_ksfo_20240101_00.json", "lav_ksfo_20240101_06.json", "lav_front_stations_20240101_00.json"):
        data = json.loads((ROOT / "raw" / name).read_text())["data"]
        assert data
        for item in data:
            assert item["model"] == "LAV" and item["station"] in STATIONS
            assert 1 <= item["vis"] <= 7
            decoded.append({key: item[key] for key in ("station", "runtime_utc", "ftime_utc", "vis", "cig", "tmp", "dpt", "wdr", "wsp", "p01")})
        captures.append({
            "path": "raw/" + name,
            "records": len(data),
            "stations": sorted({item["station"] for item in data}),
            "runtimes": sorted({item["runtime_utc"] for item in data}),
            "first_valid": min(item["ftime_utc"] for item in data),
            "last_valid": max(item["ftime_utc"] for item in data),
        })
    csv_rows = list(csv.DictReader(io.StringIO((ROOT / "raw/lav_raw_request_20240101.txt").read_text())))
    keyed = {(row["runtime"], row["ftime"]): row for row in csv_rows}
    checked = 0
    for row in decoded:
        if row["station"] != "KSFO":
            continue
        key = (row["runtime_utc"].replace("T", " ")[:19], row["ftime_utc"].replace("T", " ")[:19])
        other = keyed[key]
        for field in ("vis", "cig", "tmp", "dpt", "wdr", "wsp", "p01"):
            assert float(other[field]) == row[field], (key, field)
        checked += 1
    save("HISTORICAL_IEM_DECODED.json", decoded)
    return decoded, {"captures": captures, "json_csv_checked_rows": checked, "json_csv_same_service_not_independent_reference": True}


def native_archive(iem_rows):
    summaries = []
    selected = []
    tar_headers = {}
    for suffix, header in (("0000", "lamp_2024_archive_header.bin"), ("0030", "lamp_2024_archive_header_3.bin")):
        member = tarfile.TarInfo.frombuf((ROOT / "raw" / header).read_bytes()[:512], "utf-8", "strict")
        tar_headers[suffix] = {"member": member.name, "compressed_bytes": member.size}
        path = ROOT / "raw" / f"lamp_2024_archive_member_jan_{suffix}.gz"
        assert path.stat().st_size == member.size
        header_receipt = json.loads((ROOT / "raw" / (header + ".receipt.json")).read_text())
        member_receipt = json.loads(path.with_name(path.name + ".receipt.json").read_text())
        assert header_receipt["status_code"] == member_receipt["status_code"] == 206
        assert header_receipt["headers"]["ETag"] == member_receipt["headers"]["ETag"]
        header_offset = int(header_receipt["requested_range"].split("=")[1].split("-")[0])
        expected_range = f"bytes={header_offset + 512}-{header_offset + 511 + member.size}"
        assert member_receipt["requested_range"] == expected_range
        with gzip.open(path, "rt", encoding="ascii") as source:
            text = source.read(500_000_001)
            assert len(text) <= 500_000_000, "decompression bound exceeded"
            assert source.read(1) == "", "must consume gzip through CRC verification"
        rows = parse_lav(text, STATIONS)
        headers = list(LAV_HEADER.finditer(text))
        summaries.append({
            **tar_headers[suffix],
            "gzip_crc_verified": True,
            "same_archive_etag_and_tar_range_verified": True,
            "full_annual_archive_downloaded_or_hashed": False,
            "decompressed_bytes": len(text.encode("ascii")),
            "decompressed_sha256": hashlib.sha256(text.encode("ascii")).hexdigest(),
            "native_bulletins": len(headers),
            "native_stations": len({match[1] for match in headers}),
            "selected_records": len(rows),
            "selected_cycles": sorted({row["native_cycle_at"] for row in rows}),
            "selected_fields": sorted({field for row in rows for field in row["guidance_values"]}),
            "selected_rows_with_missing_or_invalid_categories": sum(bool(row["missing_or_invalid_categorical_fields"]) for row in rows),
        })
        selected.extend(rows)
    direct_prefix = (ROOT / "raw/lamp_202401_0030_direct_prefix.bin").read_bytes()
    member_prefix = (ROOT / "raw/lamp_2024_archive_header_3.bin").read_bytes()[512:]
    assert member_prefix == direct_prefix[:len(member_prefix)]
    save("HISTORICAL_NATIVE_SELECTED.json", selected)
    iem = {(row["station"], row["ftime_utc"][:19]): row for row in iem_rows if row["runtime_utc"].startswith("2024-01-01T00")}
    comparison = {}
    for cycle in ("2024-01-01T00:00:00+00:00", "2024-01-01T00:30:00+00:00"):
        compared = Counter()
        examples = []
        for row in selected:
            if row["native_cycle_at"] != cycle:
                continue
            other = iem.get((row["station"], row["valid_at"][:19]))
            if other is None:
                continue
            compared["rows"] += 1
            for field, value in row["guidance_values"].items():
                if field.lower() not in other:
                    continue
                # IEM documents WDR as degrees; native LAV stores tens of degrees.
                native_value = value * 10 if field == "WDR" else value
                compared["field_comparisons"] += 1
                if native_value == other[field.lower()]:
                    compared["field_equal"] += 1
                elif len(examples) < 8:
                    examples.append({"station": row["station"], "valid_at": row["valid_at"], "field": field, "native": native_value, "iem": other[field.lower()]})
        comparison[cycle] = {**dict(compared), "mismatch_examples": examples}
    return {"members": summaries, "comparison_iem_runtime_00z_to_native_cycles": comparison,
            "direct_monthly_gzip_range_available_and_prefix_matches_tar_member": True,
            "historical_first_available_time_verified": False,
            "archive_http_last_modified_is_not_historical_issue_time": True}


def probabilities():
    source = ROOT / "raw/lmp_20260913_t0030z_fltcat_15min.txt"
    rows = parse_fltcat(source.read_text())
    selected = [row for row in rows if row["station"] in STATIONS]
    save("CURRENT_NATIVE_PROBABILITY_SELECTED.json", selected)
    complements = Counter(row["probability_percent"]["VPM"] + row["probability_percent"]["VPVFR"] for row in rows)
    return {
        "stations": len({row["station"] for row in rows}),
        "station_windows": len(rows),
        "selected_station_windows": len(selected),
        "probability_values": len(rows) * len(VISIBILITY_THRESHOLDS),
        "cycle": sorted({row["native_cycle_at"] for row in rows}),
        "probability_percent_range": [min(p for row in rows for p in row["probability_percent"].values()), max(p for row in rows for p in row["probability_percent"].values())],
        "all_cumulative_rows_monotone": True,
        "complement_native_sum_distribution": dict(complements),
        "complement_values_not_renormalized": True,
        "thresholds": VISIBILITY_THRESHOLDS,
        "statistic": "lowest_visibility_during_15_minute_period",
        "same_target_1000m_hourly_probability": False,
        "same_target_5000m_hourly_probability": False,
        "matching_15minute_minimum_observations_verified": False,
        "historical_probability_archive_verified": False,
    }


def main():
    receipts = validate_receipts()
    iem_rows, iem_report = historical_lav()
    current_lav = parse_lav((ROOT / "raw/lmp_20260913_t0030z_lav.txt").read_text(), STATIONS)
    save("CURRENT_NATIVE_LAV_SELECTED.json", current_lav)
    reference_paths = [
        ROOT.parents[1] / "v7_integrated_20260913/reference_checks_01/iem_mos.html",
        ROOT.parents[1] / "v7_integrated_20260913/reference_checks_01/lamp_bufr.html",
        ROOT.parents[1] / "v7_integrated_20260913/reference_checks_02/lamp_card.html",
    ]
    report = {
        "schema_version": "lamp_source_admission_probe_v1",
        "source_files_sha256_verified": len(receipts),
        "new_http_response_bytes": sum(row["bytes"] for row in receipts),
        "http_status_counts": dict(Counter(row.get("status_code", "exception") for row in receipts)),
        "http_incomplete_responses": [
            {"path": row["path"], "status_code": row.get("status_code"), "error": row.get("error")}
            for row in receipts if not row["body_complete"]
        ],
        "historical_iem_lav": iem_report,
        "historical_official_native_lav": native_archive(iem_rows),
        "current_official_native_lav": {
            "selected_records": len(current_lav),
            "cycles": sorted({row["native_cycle_at"] for row in current_lav}),
            "fields": sorted({field for row in current_lav for field in row["guidance_values"]}),
        },
        "current_native_probabilities": probabilities(),
        "bufr_decoder": json.loads((ROOT / "BUFR_DECODER_RESULT.json").read_text()),
        "qualification": {
            "real_scientific_data_downloaded_and_decoded": True,
            "authorization_needed": False,
            "historical_lav_product_fact_E_candidate": True,
            "historical_lav_category_to_weather_probability_R_mapping_fitted": False,
            "current_native_probability_source_readable": True,
            "existing_1000m_5000m_professional_baseline_P_admitted": False,
            "formal_A5_monitoring_admission": False,
            "native_probability_forecast_skill_evaluated": False,
        },
        "source_definition_bindings": [
            {"path": str(path.relative_to(ROOT.parents[2])), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in reference_paths
        ],
        "empty_response_preserved": {
            "path": "raw/lav_ksfo_20240101_native.txt",
            "http_status": 200,
            "semantic_result": "AFOS historical request returned no products; CSV/JSON and official archive are separate successful paths",
        },
        "historical_lav_field_units": {
            "VIS": "categorical_forecast_1_to_7",
            "CIG": "categorical_forecast_1_to_8",
            "TMP": "degree_Fahrenheit",
            "DPT": "degree_Fahrenheit",
            "P01": "percent_measurable_precipitation_during_preceding_hour",
            "WDR": "tens_of_degrees_in_native_bulletin; degrees_in_IEM_export",
            "WSP": "knots",
        },
        "non_claims": [
            "No model inference, forecast skill, LLM gain, E/F causal connection, or independent-process result was measured.",
            "Categorical guidance supports statements about the product; it is not observed physical truth.",
            "A current snapshot capture does not establish historical availability.",
            "Raw data being readable does not complete the benchmark task contract.",
        ],
    }
    save("REPORT.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
