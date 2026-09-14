"""Inspect published EUPP processed-surface metadata for native extrema forecasts."""

import datetime as dt
import hashlib
import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
OUT = HERE / "temperature_daily_forecast_01"
CATALOG = (
    REPO / "plans/v7_execution_20260913/sources_numerical/raw/eupp_germany_catalog.yml"
)
BASE = "https://object-store.os-api.cci1.ecmwf.int/eumetnet-postprocessing-benchmark-1st-phase-training-dataset/data/stations_data/"


def save(name, value):
    with (OUT / name).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), OUT / "EXECUTED_METADATA_SOURCE.py")
    requests = []
    for kind in ("ensemble_forecasts", "highres_forecasts"):
        store = f"stations_{kind}_surface_postprocessed_germany.zarr"
        assert store in CATALOG.read_text()
        requests.append({"name": kind, "url": BASE + store + "/.zmetadata"})
    save(
        "METADATA_PLAN.json",
        {
            "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "catalog_sha256": hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
            "requests": requests,
            "max_requests": 2,
            "retries": 0,
            "bytes_per_response_cap": 2_097_152,
            "timeout_seconds": 25,
            "selection": "Both published forecast processed-surface stores, no event/outcome selection.",
            "scope": "Metadata inspection only;no model calls,training or confirmation data.",
        },
    )
    receipts = []
    for request in requests:
        row = {**request, "started_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        try:
            req = urllib.request.Request(
                request["url"],
                headers={"User-Agent": "DisasterTrace-extreme-contract/1.0"},
            )
            with urllib.request.urlopen(req, timeout=25) as response:
                data = response.read(2_097_153)
                if len(data) > 2_097_152:
                    raise ValueError("Metadata exceeds frozen byte cap")
                with (OUT / (request["name"] + ".zmetadata")).open("xb") as handle:
                    handle.write(data)
                metadata = json.loads(data)["metadata"]
                row.update(
                    status="decoded_metadata",
                    http_status=response.status,
                    sha256=hashlib.sha256(data).hexdigest(),
                    bytes=len(data),
                    final_url=response.url,
                    etag=response.headers.get("ETag"),
                    variables={
                        name[:-8]: {
                            "array": value,
                            "attributes": metadata.get(name[:-8] + "/.zattrs"),
                        }
                        for name, value in metadata.items()
                        if name.endswith("/.zarray")
                    },
                )
        except (OSError, ValueError, KeyError, urllib.error.URLError) as exc:
            row.update(
                status="failed_preserved_no_retry",
                error_type=type(exc).__name__,
                error=str(exc),
            )
        row["completed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        save(request["name"] + ".receipt.json", row)
        receipts.append(row)
    save(
        "METADATA_COMPLETE.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "requests": len(receipts),
            "decoded": sum(row["status"] == "decoded_metadata" for row in receipts),
            "new_model_calls": 0,
            "daily_forecast_qualified": False,
        },
    )
    print(
        json.dumps(
            {
                row["name"]: {
                    "status": row["status"],
                    "variables": list(row.get("variables", {})),
                }
                for row in receipts
            }
        )
    )


if __name__ == "__main__":
    main()
