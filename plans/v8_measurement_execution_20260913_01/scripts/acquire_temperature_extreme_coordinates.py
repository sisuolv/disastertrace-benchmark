"""Complete native coordinates for the existing first-station extrema chunks."""

import concurrent.futures
import datetime as dt
import hashlib
import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "temperature_daily_forecast_01"
OUT = ROOT / "coordinates_01"
BASE = "https://object-store.os-api.cci1.ecmwf.int/eumetnet-postprocessing-benchmark-1st-phase-training-dataset/data/stations_data/stations_ensemble_forecasts_surface_postprocessed_germany.zarr/"
DEADLINE = dt.datetime(2026, 9, 14, 1, 0, tzinfo=dt.timezone.utc)


def now():
    return dt.datetime.now(dt.timezone.utc)


def save(name, value):
    with (OUT / name).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def fetch(row):
    result = {**row, "started_at": now().isoformat(), "issued": False}
    remaining = (DEADLINE - now()).total_seconds()
    if remaining < 1:
        return dict(result, status="not_issued_before_deadline")
    try:
        result["issued"] = True
        req = urllib.request.Request(
            row["url"], headers={"User-Agent": "DisasterTrace-extreme-coordinates/1.0"}
        )
        with urllib.request.urlopen(req, timeout=min(25, remaining)) as response:
            data = response.read(262145)
            if len(data) > 262144:
                raise ValueError("Coordinate exceeds frozen byte cap")
            if response.headers.get("Content-Length") is not None and int(
                response.headers["Content-Length"]
            ) != len(data):
                raise ValueError("Incomplete coordinate response")
            target = OUT / row["name"]
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(data)
            result.update(
                status="downloaded",
                http_status=response.status,
                bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                etag=response.headers.get("ETag"),
            )
    except (OSError, ValueError, urllib.error.URLError) as exc:
        result.update(
            status="failed_preserved_no_retry",
            error_type=type(exc).__name__,
            error=str(exc),
        )
    result["completed_at"] = now().isoformat()
    return result


def main():
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), OUT / "EXECUTED_SOURCE.py")
    existing = {
        row["name"]: row
        for row in json.loads((ROOT / "sample_01/RECEIPTS.json").read_text())
    }
    requests, reused = [], []
    for variable in ("time", "valid_time"):
        for index in range(730):
            name = f"{variable}/{index}" + (".0" if variable == "valid_time" else "")
            if name in existing and existing[name]["status"] == "downloaded":
                payload = (ROOT / "sample_01" / name).read_bytes()
                assert hashlib.sha256(payload).hexdigest() == existing[name]["sha256"]
                reused.append(existing[name])
            else:
                requests.append({"name": name, "url": BASE + name})
    save(
        "PLAN.json",
        {
            "frozen_at": now().isoformat(),
            "deadline": DEADLINE.isoformat(),
            "requests": requests,
            "reused": reused,
            "max_requests": len(requests),
            "max_workers": 4,
            "retries": 0,
            "bytes_per_response_cap": 262144,
            "new_model_calls": 0,
            "selection": "All native time/valid_time indices0..729 in already-downloaded first-station chunks;failures stay missing.",
        },
    )
    receipts = []
    with (
        (OUT / "RECEIPTS.jsonl").open("x") as handle,
        concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool,
    ):
        for result in pool.map(fetch, requests):
            receipts.append(result)
            handle.write(json.dumps(result) + "\n")
            handle.flush()
            if len(receipts) % 100 == 0:
                print(
                    json.dumps(
                        {
                            "completed": len(receipts),
                            "total": len(requests),
                            "failures": sum(
                                r["status"] != "downloaded" for r in receipts
                            ),
                        }
                    ),
                    flush=True,
                )
    summary = {
        "at": now().isoformat(),
        "registered_new_requests": len(requests),
        "issued": sum(row["issued"] for row in receipts),
        "reused": len(reused),
        "successful": sum(row["status"] == "downloaded" for row in receipts),
        "all_coordinates_downloaded": all(
            row["status"] == "downloaded" for row in receipts
        ),
        "new_model_calls": 0,
        "failed_or_unissued": [r for r in receipts if r["status"] != "downloaded"],
    }
    save("COMPLETE.json", summary)
    print(
        json.dumps({k: v for k, v in summary.items() if k != "failed_or_unissued"}),
        flush=True,
    )


if __name__ == "__main__":
    main()
