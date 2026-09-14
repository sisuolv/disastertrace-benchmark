"""Compare native daily extremes with complete hourly and six-hour samples."""

import csv
import hashlib
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]


def read(path):
    return json.loads(path.read_text())


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def main():
    root = HERE / "temperature_daily_reference_01"
    output = root / "sample_support_comparison_01"
    output.mkdir(exist_ok=False)
    source = REPO / "plans/v7_execution_20260913/sources_numerical"
    receipts = [
        json.loads(line)
        for line in (source / "REQUESTS.jsonl").read_text().splitlines()
    ]
    receipt = [
        r
        for r in receipts
        if r["name"] == "dwd_berus_hourly_temperature.zip" and r.get("status") == 200
    ]
    if len(receipt) != 1:
        raise ValueError("Original successful hourly acquisition must be unique")
    payload = (source / "raw/dwd_berus_hourly_temperature.zip").read_bytes()
    if digest(payload) != receipt[0]["sha256"]:
        raise ValueError("Changed native hourly archive")
    daily_path = root / "qualification_01/DAILY_REFERENCES.json"
    days = read(daily_path)
    hourly = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if archive.testzip() is not None:
            raise ValueError("Hourly ZIP CRC failure")
        name = next(n for n in archive.namelist() if n.startswith("produkt_tu_stunde"))
        for row in csv.DictReader(
            io.TextIOWrapper(archive.open(name), encoding="utf-8-sig"), delimiter=";"
        ):
            row = {
                k.strip(): (v or "").strip() for k, v in row.items() if k is not None
            }
            stamp = row["MESS_DATUM"]
            if not "20170101" <= stamp[:8] <= "20181231":
                continue
            if int(row["STATIONS_ID"]) != 460 or stamp in hourly:
                raise ValueError("Wrong or duplicate native hourly station-time")
            number = float(row["TT_TU"])
            hourly[stamp] = None if number == -999 else number
    rows = []
    for day in days:
        prefix = day["date"].replace("-", "")
        row = {
            "date": day["date"],
            "TXK_C": day["values_C"]["TXK"],
            "TNK_C": day["values_C"]["TNK"],
        }
        for label, hours in (("hourly24", range(24)), ("sampled6h", (0, 6, 12, 18))):
            values = [hourly.get(prefix + f"{h:02d}") for h in hours]
            row[label + "_available_samples"] = sum(v is not None for v in values)
            complete = all(v is not None for v in values)
            row[label + "_max_C"] = max(values) if complete else None
            row[label + "_min_C"] = min(values) if complete else None
        rows.append(row)
    comparison = {}
    for label in ("hourly24", "sampled6h"):
        group = [
            r
            for r in rows
            if all(
                r[k] is not None
                for k in (label + "_max_C", label + "_min_C", "TXK_C", "TNK_C")
            )
        ]
        hot_native = sum(r["TXK_C"] >= 30 for r in group)
        frost_native = sum(r["TNK_C"] < 0 for r in group)
        comparison[label] = {
            "complete_comparison_days": len(group),
            "incomplete_days_retained": len(rows) - len(group),
            "native_hot_days_on_same_mask": hot_native,
            "sampled_hot_days_on_same_mask": sum(
                r[label + "_max_C"] >= 30 for r in group
            ),
            "native_hot_days_missed_by_samples": sum(
                r["TXK_C"] >= 30 and r[label + "_max_C"] < 30 for r in group
            ),
            "sampled_hot_but_native_not": sum(
                r["TXK_C"] < 30 and r[label + "_max_C"] >= 30 for r in group
            ),
            "native_frost_days_on_same_mask": frost_native,
            "sampled_frost_days_on_same_mask": sum(
                r[label + "_min_C"] < 0 for r in group
            ),
            "native_frost_days_missed_by_samples": sum(
                r["TNK_C"] < 0 and r[label + "_min_C"] >= 0 for r in group
            ),
            "sampled_frost_but_native_not": sum(
                r["TNK_C"] >= 0 and r[label + "_min_C"] < 0 for r in group
            ),
            "daily_max_minus_sample_max_mean_C": sum(
                r["TXK_C"] - r[label + "_max_C"] for r in group
            )
            / len(group),
            "sample_min_minus_daily_min_mean_C": sum(
                r[label + "_min_C"] - r["TNK_C"] for r in group
            )
            / len(group),
        }
    report = {
        "passed": True,
        "registered_days": len(rows),
        "hourly_product": name,
        "hourly_archive_sha256": digest(payload),
        "daily_references_sha256": digest(daily_path.read_bytes()),
        "hourly_native_slots_in_calendar": len(hourly),
        "hourly_sample_coverage": dict(
            Counter(r["hourly24_available_samples"] for r in rows)
        ),
        "comparison": comparison,
        "new_model_calls": 0,
        "new_source_requests": 0,
        "scope": "Actual native observations, not forecasts. Complete comparison masks are explicit; incomplete days remain in DAILY_COMPARISON.json.",
        "interpretation": "Hourly or00/06/12/18UTC observations need not equal a measured full-day extreme. Do not replace native daily-reference labels or advertise sampled maxima as matched daily professional forecasts.",
    }
    for name, value in (("DAILY_COMPARISON.json", rows), ("VALIDATION.json", report)):
        with (output / name).open("x") as handle:
            json.dump(value, handle, indent=2, allow_nan=False)
            handle.write("\n")
    (output / "EXECUTED_SOURCE.py").write_bytes(Path(__file__).read_bytes())
    print(json.dumps(report))


if __name__ == "__main__":
    main()
