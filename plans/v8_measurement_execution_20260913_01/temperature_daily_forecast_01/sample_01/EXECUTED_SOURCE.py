"""Fetch bounded native extreme arrays and coordinates, retaining every receipt."""

import concurrent.futures
import datetime as dt
import hashlib
import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE / "temperature_daily_forecast_01"
OUT = ROOT / "sample_01"
BASE = "https://object-store.os-api.cci1.ecmwf.int/eumetnet-postprocessing-benchmark-1st-phase-training-dataset/data/stations_data/stations_ensemble_forecasts_surface_postprocessed_germany.zarr/"


def save(name, value):
    with (OUT / name).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def fetch(row):
    result = {**row, "started_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    try:
        req = urllib.request.Request(
            row["url"], headers={"User-Agent": "DisasterTrace-extreme-contract/1.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read(row["byte_cap"] + 1)
            if len(data) > row["byte_cap"]:
                raise ValueError("Response exceeds frozen cap")
            target = OUT / row["name"]
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(data)
            result.update(
                status="downloaded",
                http_status=response.status,
                bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                final_url=response.url,
                etag=response.headers.get("ETag"),
            )
    except (OSError, ValueError, urllib.error.URLError) as exc:
        result.update(
            status="failed_preserved_no_retry",
            error_type=type(exc).__name__,
            error=str(exc),
        )
    result["completed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    return result


def main():
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), OUT / "EXECUTED_SOURCE.py")
    requests = [
        {"name": name, "url": BASE + name, "byte_cap": 8_388_608}
        for name in (
            "mx2t6/0.0.0.0.0",
            "mn2t6/0.0.0.0.0",
            "station_id/0",
            "step/0",
            "number/0",
            "time/0",
            "time/1",
            "time/729",
            "valid_time/0.0",
            "valid_time/729.0",
            "station_latitude/0",
            "station_longitude/0",
        )
    ] + [
        {
            "name": "eupp_org_repositories.json",
            "url": "https://api.github.com/orgs/EUPP-benchmark/repos?per_page=100",
            "byte_cap": 2_097_152,
        }
    ]
    save(
        "PLAN.json",
        {
            "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "requests": requests,
            "requests_cap": len(requests),
            "max_workers": 4,
            "retries": 0,
            "metadata_sha256": hashlib.sha256(
                (ROOT / "ensemble_forecasts.zmetadata").read_bytes()
            ).hexdigest(),
            "selection": "First station chunk, all51members/730inits/20six-hour indices;coordinate endpoints and first two inits. No outcome-based selection.",
            "scope": "Actual byte/coordinate verification. Daily support,units,all-coordinate identity and formal F remain unqualified until checked.",
            "new_model_calls": 0,
        },
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(fetch, requests))
    save("RECEIPTS.json", receipts)
    save(
        "COMPLETE.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "requests": len(receipts),
            "successful": sum(r["status"] == "downloaded" for r in receipts),
            "bytes": sum(r.get("bytes", 0) for r in receipts),
            "new_model_calls": 0,
        },
    )
    print(
        json.dumps(
            {
                row["name"]: {"status": row["status"], "bytes": row.get("bytes")}
                for row in receipts
            }
        )
    )


if __name__ == "__main__":
    main()
