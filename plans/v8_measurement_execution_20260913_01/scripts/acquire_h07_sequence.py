"""Bounded native MRMS continuity and documentation checks, with no label selection."""

import concurrent.futures
import datetime as dt
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "h07_extension_01"


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")


def fetch(row):
    receipt = {**row, "started_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    try:
        request = urllib.request.Request(
            row["url"], headers={"User-Agent": "DisasterTrace-source-audit/1.0"}
        )
        with urllib.request.urlopen(request, timeout=40) as response:
            data = response.read(row["cap"] + 1)
            if response.status != 200 or len(data) > row["cap"]:
                raise ValueError("Incomplete or oversized source response")
            length = response.headers.get("Content-Length")
            if length and int(length) != len(data):
                raise ValueError("Truncated source")
            etag = response.headers.get("ETag", "").strip('"')
            if (
                row["kind"] == "native_grid"
                and len(etag) == 32
                and hashlib.md5(data).hexdigest() != etag
            ):
                raise ValueError("Single-part S3 ETag differs")
            path = ROOT / "raw" / row["name"]
            with path.open("xb") as handle:
                handle.write(data)
            receipt.update(
                status="verified",
                http_status=response.status,
                bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                last_modified=response.headers.get("Last-Modified"),
                content_type=response.headers.get("Content-Type"),
                final_url=response.url,
                etag=etag,
            )
    except Exception as exc:  # noqa: BLE001 - record every failed acquisition in the denominator
        receipt.update(status="failed", error_type=type(exc).__name__, error=str(exc))
    receipt["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    return receipt


def main():
    ROOT.mkdir(exist_ok=False)
    (ROOT / "raw").mkdir()
    requests = [
        {
            "name": "mrms_tables.html",
            "kind": "documentation",
            "cap": 4_194_304,
            "url": "https://www.nssl.noaa.gov/projects/mrms/operational/tables.php",
        },
        {
            "name": "mrms_grib.pdf",
            "kind": "documentation",
            "cap": 4_194_304,
            "url": "https://www.nssl.noaa.gov/projects/mrms/operational/tables/MRMS_GRIB2_Description.pdf",
        },
        {
            "name": "mrms_qpe.html",
            "kind": "documentation",
            "cap": 4_194_304,
            "url": "https://www.nssl.noaa.gov/projects/mrms/operational/qpe.php",
        },
    ]
    for hour in range(12):
        name = f"MRMS_MultiSensor_QPE_01H_Pass2_00.00_20260910-{hour:02d}0000.grib2.gz"
        requests.append(
            {
                "name": name,
                "kind": "native_grid",
                "cap": 4_194_304,
                "nominal_time": f"2026-09-10T{hour:02d}:00:00Z",
                "url": "https://noaa-mrms-pds.s3.amazonaws.com/CONUS/MultiSensor_QPE_01H_Pass2_00.00/20260910/"
                + name,
            }
        )
    save(
        ROOT / "PLAN.json",
        {
            "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "hazard": "H07",
            "selection": "First twelve consecutive hourly objects on the same day as the inherited 00Z MRMS sample.",
            "requests": requests,
            "max_workers": 4,
            "attempts_per_object": 1,
            "primary_scope": "Native grid, product-code, unit, temporal-support and continuity qualification.",
            "regional_diagnostic_bounds": {
                "lat_min": 34.0,
                "lat_max": 36.0,
                "lon_min": -99.0,
                "lon_max": -96.0,
            },
            "region_selection": "Fixed Oklahoma box, before opening additional grids; no positive-event selection.",
            "source_product": "MultiSensor_QPE_01H_Pass2",
            "not_rain_rate_or_VIL": True,
            "QPE_is_product_estimate_not_error_free_physical_rain": True,
            "historical_first_seen_proved": False,
            "S3_last_modified_is_delivery_metadata_only": True,
            "no_LLM_calls": True,
            "independent_confirmation": False,
        },
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(fetch, requests))
    with (ROOT / "RECEIPTS.jsonl").open("x") as handle:
        for row in receipts:
            handle.write(json.dumps(row) + "\n")
    save(
        ROOT / "ACQUISITION.json",
        {
            "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "results": [{k: row[k] for k in ("name", "kind", "status")} for row in receipts],
            "native_objects_verified": sum(
                r["kind"] == "native_grid" and r["status"] == "verified" for r in receipts
            ),
            "document_objects_verified": sum(
                r["kind"] == "documentation" and r["status"] == "verified" for r in receipts
            ),
            "failed": sum(r["status"] != "verified" for r in receipts),
        },
    )
    print((ROOT / "ACQUISITION.json").read_text())


if __name__ == "__main__":
    main()
