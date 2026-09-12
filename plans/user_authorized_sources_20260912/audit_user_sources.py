"""Decode user-supplied event and track data without changing historical results."""

import argparse
import hashlib
import json
import re
import zlib
from collections import Counter
from datetime import datetime, timedelta
from itertools import pairwise
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent
EMDAT = (
    ROOT
    / "inputs/public_emdat_custom_request_2026-09-12_0a227307-4f08-41f6-8766-2a19b092e9c5.xlsx"
)
CORE_TYPES = {"Flood", "Storm", "Extreme temperature", "Drought", "Wildfire"}
SUBTYPE_HAZARDS = {
    "Tropical cyclone": ["H01"],
    "Extra-tropical storm": ["H02"],
    "Derecho": ["H03"],
    "Tornado": ["H04"],
    "Hail": ["H05"],
    "Lightning/Thunderstorms": ["H03", "H06"],
    "Riverine flood": ["H08"],
    "Flash flood": ["H08"],
    "Flood (General)": ["H08"],
    "Coastal flood": ["H09"],
    "Storm surge": ["H09"],
    "Heat wave": ["H10"],
    "Cold wave": ["H11"],
    "Blizzard/Winter storm": ["H12"],
    "Severe winter conditions": ["H12"],
    "Drought": ["H13"],
    "Sand/Dust storm": ["H14"],
    "Forest fire": ["H16"],
    "Land fire (Brush, Bush, Pasture)": ["H16"],
    "Wildfire (General)": ["H16"],
}


def bind(path):
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def dump(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str, allow_nan=False)
        + "\n"
    )


def read_emdat(path):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook["EM-DAT Data"]
        declared_dimension = sheet.calculate_dimension()
        # This real export declares A1 even though it contains thousands of rows.
        sheet.reset_dimensions()
        rows = sheet.iter_rows(values_only=True)
        headers = list(next(rows))
        if len(set(headers)) != len(headers) or "DisNo." not in headers:
            raise ValueError("Unexpected EM-DAT columns")
        records = []
        for row in rows:
            # This export writes absent dates and coordinates as empty strings.
            row = tuple(
                None if isinstance(v, str) and not v.strip() else v for v in row
            )
            if not any(v is not None for v in row):
                continue
            if len(row) != len(headers):
                raise ValueError("EM-DAT row width mismatch")
            records.append(dict(zip(headers, row)))
        return declared_dimension, headers, records
    finally:
        workbook.close()


def emdat(output):
    import zipfile

    with zipfile.ZipFile(EMDAT) as archive:
        if archive.testzip() is not None:
            raise ValueError("XLSX CRC mismatch")
    dimension, columns, rows = read_emdat(EMDAT)
    index, ambiguous = [], Counter()
    for row in rows:
        if row["Disaster Group"] != "Natural" or row["Disaster Type"] not in CORE_TYPES:
            continue
        hazards = SUBTYPE_HAZARDS.get(row["Disaster Subtype"], [])
        if len(hazards) != 1:
            ambiguous[row["Disaster Subtype"]] += 1
        ident = row["DisNo."]
        match = re.fullmatch(r"(\d{4}-\d+)-([A-Z]{3})", ident)
        if not match:
            raise ValueError("Unexpected disaster-country identifier")
        indexed = {
            key: row[key]
            for key in [
                "DisNo.",
                "Disaster Type",
                "Disaster Subtype",
                "Event Name",
                "ISO",
                "Country",
                "Start Year",
                "Start Month",
                "Start Day",
                "End Year",
                "End Month",
                "End Day",
                "Latitude",
                "Longitude",
                "Last Update",
            ]
        }
        indexed.update(
            event_group_key=match.group(1),
            candidate_hazards=hazards,
            label_is_event_index_only=True,
            start_precision="day"
            if row["Start Day"] is not None
            else "month"
            if row["Start Month"] is not None
            else "year",
        )
        index.append(indexed)
    with (output / "local_data/emdat_weather_index.jsonl").open("w") as stream:
        for row in index:
            stream.write(
                json.dumps(row, ensure_ascii=False, default=str, allow_nan=False) + "\n"
            )
    counts = Counter(r["Disaster Subtype"] for r in index)
    country_ids = [r["DisNo."] for r in rows]
    examples = []
    for subtype in sorted(counts):
        examples.append(next(r for r in index if r["Disaster Subtype"] == subtype))
    return {
        "source_id": "D39",
        "state": "catalog_records_only",
        "file": bind(EMDAT),
        "xlsx_crc_passed": True,
        "declared_dimension": dimension,
        "actual_columns": len(columns),
        "actual_rows": len(rows),
        "columns": columns,
        "duplicate_disaster_country_ids": len(country_ids) - len(set(country_ids)),
        "year_range": [
            min(r["Start Year"] for r in rows),
            max(r["Start Year"] for r in rows),
        ],
        "groups": dict(Counter(r["Disaster Group"] for r in rows)),
        "subgroups": dict(Counter(r["Disaster Subgroup"] for r in rows)),
        "core_weather_country_records": len(index),
        "core_weather_event_groups": len({r["event_group_key"] for r in index}),
        "core_weather_subtypes": dict(counts),
        "ambiguous_or_unspecified_subtypes": dict(ambiguous),
        "start_date_precision": dict(Counter(r["start_precision"] for r in index)),
        "missing_coordinates": sum(
            r["Latitude"] is None or r["Longitude"] is None for r in index
        ),
        "valid_coordinate_pairs": sum(
            isinstance(r["Latitude"], (int, float))
            and isinstance(r["Longitude"], (int, float))
            and -90 <= r["Latitude"] <= 90
            and -180 <= r["Longitude"] <= 180
            for r in index
        ),
        "conditional_wet_mass_movements": sum(
            r["Disaster Type"] == "Mass movement (wet)" for r in rows
        ),
        "conditional_glacial_lake_outbursts": sum(
            r["Disaster Type"] == "Glacial lake outburst flood" for r in rows
        ),
        "examples": examples,
        "limits": "User-authorized event-country export. Not a complete census of meteorological events, per-pixel truth or precise warning/arrival times. Missing events are not negative labels. Mixed lightning/thunderstorm and general storm labels stay ambiguous. Raw export is kept local; no blanket redistribution permission inferred.",
    }


def parse_cma(path):
    storms, current = [], None
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        fields = line.split()
        if not fields:
            continue
        if fields[0] == "66666":
            if current is not None:
                if len(current["points"]) != current["declared_points"]:
                    raise ValueError("CMA header count disagrees with body")
                storms.append(current)
            if len(fields) not in [8, 9]:
                raise ValueError("Unexpected CMA header width")
            current = {
                "storm_key": path.stem + ":" + str(len(storms) + 1),
                "member": path.name,
                "header_line": line_number,
                "header_raw": line,
                "declared_points": int(fields[2]),
                "name": " ".join(fields[7:-1]) or None,
                "header_stamp_raw": fields[-1],
                "points": [],
            }
        else:
            if current is None or len(fields) not in [6, 7]:
                raise ValueError("Unexpected CMA observation row")
            # The source clock has no explicit timezone marker; retain it verbatim.
            datetime.strptime(fields[0], "%Y%m%d%H")  # noqa: DTZ007
            if not re.fullmatch(r"\d{10}", fields[0]):
                raise ValueError("Unexpected CMA timestamp")
            numeric = list(map(int, fields[1:]))
            current["points"].append(
                {
                    "storm_key": current["storm_key"],
                    "source_line": line_number,
                    "time_raw": fields[0],
                    "intensity_code": numeric[0],
                    "latitude_raw": numeric[1],
                    "longitude_raw": numeric[2],
                    "pressure_raw": numeric[3],
                    "wind_raw": numeric[4],
                    "optional_wind_raw": numeric[5] if len(numeric) == 6 else None,
                }
            )
    if current is not None:
        if len(current["points"]) != current["declared_points"]:
            raise ValueError("CMA final header count disagrees with body")
        storms.append(current)
    return storms


def cma(output):
    archive = ROOT / "inputs/CMABSTdata.rar"
    index = json.loads((ROOT / "validation/CMA_ARCHIVE_INDEX.json").read_text())
    members = {r["Path"]: r for r in index}
    all_storms, files = [], [bind(archive)]
    for name in sorted(members):
        path = ROOT / "extracted/cma" / name
        raw = path.read_bytes()
        if (
            len(raw) != int(members[name]["Size"])
            or f"{zlib.crc32(raw):08X}" != members[name]["CRC"]
        ):
            raise ValueError("CMA member CRC mismatch")
        files.append(bind(path))
        all_storms.extend(parse_cma(path))
    intervals, anomalies, horizons = Counter(), [], Counter()
    samples, points = [], []
    for storm in all_storms:
        rows = storm["points"]
        clocks = [datetime.strptime(r["time_raw"], "%Y%m%d%H") for r in rows]  # noqa: DTZ007
        for first, second in pairwise(clocks):
            hours = (second - first).total_seconds() / 3600
            intervals[str(hours)] += 1
            if hours <= 0:
                anomalies.append(
                    {"storm_key": storm["storm_key"], "interval_hours": hours}
                )
        by_time = {t: r for t, r in zip(clocks, rows)}
        for t, row in zip(clocks, rows):
            for horizon in [6, 12, 24]:
                future = by_time.get(t + timedelta(hours=horizon))
                if future is not None:
                    horizons[str(horizon)] += 1
                    if len(samples) < 9 and storm["member"] == "CH2025BST.txt":
                        samples.append(
                            {
                                "storm_key": storm["storm_key"],
                                "name": storm["name"],
                                "input_time_raw": row["time_raw"],
                                "target_time_raw": future["time_raw"],
                                "horizon_hours": horizon,
                                "input_wind_raw": row["wind_raw"],
                                "target_wind_raw": future["wind_raw"],
                                "units_bound_for_scoring": False,
                            }
                        )
        points.extend(rows)
    for name, rows in [
        ("cma_points.jsonl", points),
        (
            "cma_storms.jsonl",
            [{k: v for k, v in s.items() if k != "points"} for s in all_storms],
        ),
    ]:
        with (output / "local_data" / name).open("w") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {
        "source_id": "D73",
        "state": "decoded_sample",
        "files": files,
        "year_range": [int(min(members)[2:6]), int(max(members)[2:6])],
        "annual_files": len(members),
        "storm_segments": len(all_storms),
        "point_records": len(points),
        "intensity_codes": dict(Counter(str(p["intensity_code"]) for p in points)),
        "optional_column_records": sum(
            p["optional_wind_raw"] is not None for p in points
        ),
        "zero_wind_records": sum(p["wind_raw"] == 0 for p in points),
        "interval_hours": dict(intervals),
        "nonincreasing_time_anomalies": anomalies,
        "exact_future_pairs_by_hours": dict(horizons),
        "future_pair_examples": samples,
        "missing_names": sum(s["name"] is None for s in all_storms),
        "limits": "All archive members CRC-checked and record counts parsed. This is retrospective CMA analysis, not a historical issued forecast. Keep raw coordinate/pressure/wind columns until the official field, averaging-time, timezone and missing-code contract is bound; the official format endpoint currently returns468. Segments and future pairs are not independent extreme events or admitted forecast tasks.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "local_data").mkdir()
    reports = [emdat(args.output), cma(args.output)]
    dump(
        args.output / "AUDIT.json",
        {"reports": reports, "new_formal_tasks": 0, "new_model_calls": 0},
    )
    for r in reports:
        print(
            json.dumps(
                {
                    k: r[k]
                    for k in [
                        "source_id",
                        "state",
                        "actual_rows",
                        "core_weather_country_records",
                        "core_weather_event_groups",
                        "annual_files",
                        "storm_segments",
                        "point_records",
                    ]
                    if k in r
                }
            )
        )


if __name__ == "__main__":
    main()
