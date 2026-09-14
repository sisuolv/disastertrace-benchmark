"""Bind local GRIB parameters and negative codes to pinned official NOAA tables."""

import csv
import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "h07_extension_01"
OUT = HERE / "semantic_contract_01"


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=False)
    directory = HERE / "nssl_native_contract_01"
    source = directory / "UserTable_MRMS_v12.2.csv"
    receipt = next(r for r in load(directory / "RECEIPTS.json") if r["path"] == "GRIB2_TABLES/" + source.name)
    assert receipt["status"] == 200 and receipt["sha256"] == sha(source)
    tree = load(HERE / "nssl_support_discovery_01/source_0.txt")
    assert tree["sha"] == receipt["revision"]
    item = next(r for r in tree["tree"] if r["path"] == receipt["path"])
    data = source.read_bytes()
    assert hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == item["sha"]
    with source.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    selected = [r for r in rows if (r["Discipline"], r["Category"], r["Parameter"]) == ("209", "6", "37")]
    assert len(selected) == 1
    row = selected[0]
    assert row["Name"] == "MultiSensor_QPE_01H_Pass2" and row["Unit"] == "mm"
    assert row["Missing"] == "-1" and row["No Coverage"] == "-3"
    wgrib = HERE / "official_mrms_table_01/MRMS_gribtable"
    lines = [line.split(":") for line in wgrib.read_text().splitlines()]
    matches = [r for r in lines if r[:8] == ["209", "10", "0", "255", "161", "1", "6", "37"]]
    assert len(matches) == 1 and matches[0][-1] == row["Unit"]
    report = load(HERE / "decoded_01/REPORT.json")
    mapping, time_checks = [], []
    for grid in report["grids"]:
        metadata = grid["metadata"]
        assert (metadata["discipline"], metadata["parameterCategory"], metadata["parameterNumber"],
                str(metadata["centre"]), metadata["localTablesVersion"]) == (209, 6, 37, "161", 1)
        assert 0 <= metadata["tablesVersion"] <= 255
        assert set(map(float, grid["negative_raw_codes"])) <= {-1.0, -3.0}
        mapping.append({"name": grid["name"], "source_sha256": grid["source_sha256"],
            "unit": "mm", "negative_counts": {"missing": grid["negative_raw_codes"].get("-1.0", 0),
                                               "no_coverage": grid["negative_raw_codes"].get("-3.0", 0)},
            "nonnegative_product_pixels": grid["positive_raw_values"] + grid["zero_raw_values"]})
        nominal = datetime.datetime.strptime(str(metadata["dataDate"]) + f"{metadata['dataTime']:04d}", "%Y%m%d%H%M")
        stored = datetime.datetime.strptime(grid["S3_last_modified"], "%a, %d %b %Y %H:%M:%S GMT")
        time_checks.append({"name": grid["name"], "nominal_GRIB_reference_time": nominal.isoformat() + "Z",
            "archive_object_last_modified": stored.isoformat() + "Z",
            "object_timestamp_offset_seconds": (stored - nominal).total_seconds(),
            "documented_product_description": row["Description"],
            "physical_window_end_inferred": False})
    result = {"qualified": {"official_local_parameter_mapping": True, "units": True,
                            "negative_code_meanings": True, "nominal_accumulation_duration_hours": 1},
        "still_unqualified": {"physical_window_start_end": True, "proved_historical_first_seen": True,
                              "matched_future_forecast_target": True, "independent_extreme_process": True},
        "official_source": receipt, "official_git_blob_sha1": item["sha"], "official_row": row,
        "wgrib2_corroborating_table_sha256": sha(wgrib),
        "raw_decoder_report_sha256": sha(HERE / "decoded_01/REPORT.json"), "native_grid_mappings": mapping,
        "time_checks": time_checks, "new_model_calls": 0, "formal_F_score": False, "native_MM_comparison": False,
        "interpretation": "Exact metadata under the native product definition, not error-free physical precipitation.",
        "timing_warning": "Official description says2-hour latency; object timestamps are about57min after the GRIB reference. These fields do not by themselves identify the physical accumulation endpoint or first publication."}
    (OUT / "QUALIFICATION.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUT / "EXECUTED_SOURCE.py").write_bytes(Path(__file__).read_bytes())
    print(json.dumps({"native_grids": len(mapping), "qualified": result["qualified"],
                      "remaining": result["still_unqualified"]}))


if __name__ == "__main__":
    main()
