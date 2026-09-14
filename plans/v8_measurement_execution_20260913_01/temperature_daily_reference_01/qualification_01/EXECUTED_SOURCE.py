"""Qualify daily native temperature references, without inventing daily forecasts."""

import csv
import datetime as dt
import hashlib
import io
import json
import math
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
ROOT = HERE / "temperature_daily_reference_01"


def read(path):
    return json.loads(path.read_text())


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def tri_all(values):
    if any(value is False for value in values):
        return "refuted"
    if any(value is None for value in values):
        return "undetermined"
    return "supported"


def parse_rows(payload):
    text = payload.decode("latin1")
    rows = []
    for row in csv.DictReader(io.StringIO(text), delimiter=";"):
        normalized = {k.strip(): v.strip() for k, v in row.items()}
        if normalized["STATIONS_ID"] != "460":
            raise ValueError("Unexpected station in native daily reference")
        if "20170101" <= normalized["MESS_DATUM"] <= "20181231":
            rows.append(normalized)
    return rows


def main():
    out = ROOT / "qualification_01"
    out.mkdir(exist_ok=False)
    # Freeze simple inherited absolute thresholds before reading the daily values.
    spec = {
        "schema": "disastertrace.daily_temperature_reference_contract.v1",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "station_id": "00460",
        "dates": ["2017-01-01", "2018-12-31"],
        "daily_predicates": {
            "hot_day": {"field": "TXK", "operator": ">=", "threshold_C": 30},
            "frost_day": {"field": "TNK", "operator": "<", "threshold_C": 0},
            "ice_day": {"field": "TXK", "operator": "<", "threshold_C": 0},
        },
        "duration_candidates": {
            "fixed_threshold_hot_spell_3d": {
                "daily_predicate": "hot_day",
                "consecutive_days": 3,
            },
            "fixed_threshold_ice_spell_3d": {
                "daily_predicate": "ice_day",
                "consecutive_days": 3,
            },
        },
        "scope": "Native daily outcome/reference qualification and explicit candidate duration predicates; no forecast or model score.",
        "support_assumption": "exact_native_product_values_not_error_free_physical_truth",
        "quality_rule": "Retain native QN_4; -999/absent/invalid temperature remains missing, never replaced by an hourly extremum.",
        "heatwave_definition_note": "Three absolute-threshold days are an explicit diagnostic definition, not a universal/official heatwave or cold-wave definition.",
        "confirmation": False,
    }
    save(out / "TASK_SPEC.json", spec)
    archive_name = read(ROOT / "SELECTED.json")["archive"]
    archive = ROOT / archive_name
    payload = archive.read_bytes()
    if sha(payload) != read(ROOT / (archive_name + ".receipt.json"))["sha256"]:
        raise ValueError("Changed native daily archive")
    with zipfile.ZipFile(io.BytesIO(payload)) as handle:
        if handle.testzip() is not None:
            raise ValueError("Native ZIP integrity failure")
        product = [n for n in handle.namelist() if n.startswith("produkt_klima_tag_")]
        if len(product) != 1:
            raise ValueError("Ambiguous daily product")
        data = handle.read(product[0])
        meta_name = "Metadaten_Parameter_klima_tag_00460.txt"
        metadata = handle.read(meta_name)
    meta_rows = list(
        csv.DictReader(io.StringIO(metadata.decode("latin1")), delimiter=";")
    )
    evidence = {}
    for field in ("TXK", "TNK"):
        eligible = [
            r
            for r in meta_rows
            if r.get("Parameter") == field
            and r["Von_Datum"] <= "20170101"
            and r["Bis_Datum"] >= "20181231"
        ]
        if len(eligible) != 1:
            raise ValueError("Unique native daily parameter definition required")
        row = eligible[0]
        if (
            row["Einheit"].encode("latin1") != b"\xb0C"
            or row["Zusatz-Info"] != "00:00 - 24:00 UTC gemessen"
        ):
            raise ValueError("Unqualified native daily units/time support")
        evidence[field] = {k: v for k, v in row.items() if k and v}
    native = parse_rows(data)
    # A second delimiter-based decode checks the exported CSV values against source rows.
    lines = data.decode("latin1").splitlines()
    fields = [s.strip() for s in lines[0].split(";")]
    second = [
        dict(zip(fields, [s.strip() for s in line.split(";")]))
        for line in lines[1:]
        if line.strip()
    ]
    second = [r for r in second if "20170101" <= r["MESS_DATUM"] <= "20181231"]
    if second != native:
        raise ValueError("Independent native row decode differs")
    first_day = dt.date(2017, 1, 1)
    expected = [
        (first_day + dt.timedelta(days=i)).strftime("%Y%m%d") for i in range(730)
    ]
    if [r["MESS_DATUM"] for r in native] != expected:
        raise ValueError("Daily reference contains duplicate/missing/reordered dates")
    records = []
    for row in native:
        day = dt.datetime.strptime(row["MESS_DATUM"], "%Y%m%d").replace(
            tzinfo=dt.timezone.utc
        )
        values = {}
        for field in ("TXK", "TNK"):
            number = float(row[field])
            values[field] = number if math.isfinite(number) and number != -999 else None
        if (
            all(v is not None for v in values.values())
            and values["TXK"] < values["TNK"]
        ):
            raise ValueError("Native maximum below native minimum")
        predicates = {}
        for name, rule in spec["daily_predicates"].items():
            number = values[rule["field"]]
            predicates[name] = (
                None
                if number is None
                else number >= rule["threshold_C"]
                if rule["operator"] == ">="
                else number < rule["threshold_C"]
            )
        records.append(
            {
                "date": day.date().isoformat(),
                "station_id": "00460",
                "physical_start": day.isoformat(),
                "physical_end_exclusive": (day + dt.timedelta(days=1)).isoformat(),
                "values_C": values,
                "native_QN_4": row["QN_4"],
                "daily_predicates": predicates,
                "source_product": product[0],
                "row_sha256": sha(json.dumps(row, sort_keys=True).encode()),
                "historical_available_at": None,
            }
        )
    windows = []
    for start in range(len(records) - 2):
        selected = records[start : start + 3]
        for name, rule in spec["duration_candidates"].items():
            values = [r["daily_predicates"][rule["daily_predicate"]] for r in selected]
            windows.append(
                {
                    "candidate": name,
                    "physical_start": selected[0]["physical_start"],
                    "physical_end_exclusive": selected[-1]["physical_end_exclusive"],
                    "product_reference_state": tri_all(values),
                    "daily_row_sha256": [r["row_sha256"] for r in selected],
                    "native_QN_4": [r["native_QN_4"] for r in selected],
                }
            )
    eupp_path = (
        REPO
        / "plans/v7_execution_20260913/sources_numerical/raw/eupp_ensemble_forecasts_surface_metadata.json"
    )
    eupp = read(eupp_path)["metadata"]
    eupp_fields = sorted(
        k.removesuffix("/.zarray") for k in eupp if k.endswith("/.zarray")
    )
    summary = {
        "passed": True,
        "station_id": "00460",
        "native_daily_records": len(records),
        "calendar_days": 730,
        "daily_temperature_missing": {
            f: sum(r["values_C"][f] is None for r in records) for f in ("TXK", "TNK")
        },
        "native_quality_counts": dict(Counter(r["native_QN_4"] for r in records)),
        "daily_positive_counts": {
            k: sum(r["daily_predicates"][k] is True for r in records)
            for k in spec["daily_predicates"]
        },
        "duration_window_counts": {
            k: dict(
                Counter(
                    r["product_reference_state"] for r in windows if r["candidate"] == k
                )
            )
            for k in spec["duration_candidates"]
        },
        "native_definition": evidence,
        "independent_delimiter_decode_matches": True,
        "archive_sha256": sha(payload),
        "product_member": product[0],
        "product_member_sha256": sha(data),
        "metadata_member": meta_name,
        "metadata_member_sha256": sha(metadata),
        "task_spec_sha256": sha((out / "TASK_SPEC.json").read_bytes()),
        "eupp_metadata_sha256": sha(eupp_path.read_bytes()),
        "eupp_available_variables": eupp_fields,
        "eupp_t2m_attributes": eupp["t2m/.zattrs"],
        "matched_daily_forecast": False,
        "historical_first_seen_proved": False,
        "new_model_calls": 0,
        "forecast_scores": None,
        "independent_confirmation": False,
        "limits": [
            "Native daily TXK/TNK units and00-24UTC physical support are proved for this station and2017-2018, not all stations or historical years.",
            "All date windows are retained; overlapping positive windows are not independent weather processes.",
            "Quality codes are retained as native metadata; exact product support does not claim error-free physical temperature.",
            "Existing EUPP t2m is a point-temperature field; max/min of six-hour samples is not the native daily extreme or a matched professional daily forecast.",
            "These are exposed reference-development data, with no live or historical model forecast submission.",
        ],
    }
    save(out / "DAILY_REFERENCES.json", records)
    save(out / "DURATION_CANDIDATES.json", windows)
    save(out / "VALIDATION.json", summary)
    (out / "EXECUTED_SOURCE.py").write_bytes(Path(__file__).read_bytes())
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "passed",
                    "native_daily_records",
                    "daily_temperature_missing",
                    "daily_positive_counts",
                    "duration_window_counts",
                    "matched_daily_forecast",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
