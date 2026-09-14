"""Inspect bounded native GRIB prefixes; a prefix is never a full-archive check."""

import datetime as dt
import hashlib
import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path

import eccodes

ROOT = Path(__file__).resolve().parents[1] / "temperature_daily_forecast_01"
OUT = ROOT / "grib_prefix_01"


def save(name, value):
    with (OUT / name).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), OUT / "EXECUTED_SOURCE.py")
    requests = [
        {
            "name": name,
            "url": "https://object-store.os-api.cci1.ecmwf.int/"
            + bucket
            + "/data/fcs/surf/EU_forecast_ens_surf_params_2017-01-01_0.grb",
        }
        for name, bucket in (
            ("original_gridded", "eumetnet-postprocessing-benchmark-training-dataset"),
            (
                "first_phase_gridded",
                "eumetnet-postprocessing-benchmark-1st-phase-training-dataset",
            ),
        )
    ]
    save(
        "PLAN.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "requests": requests,
            "range": "bytes=0-262143",
            "read_cap_bytes": 262144,
            "retries": 0,
            "scope": "Two bounded prefixes at published original-GRIB filename and same first-phase path;not full files or a new forecast sample selection.",
        },
    )
    results = []
    for row in requests:
        result = {**row, "started_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        try:
            req = urllib.request.Request(
                row["url"],
                headers={
                    "Range": "bytes=0-262143",
                    "User-Agent": "DisasterTrace-native-cycle/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=25) as response:
                data = response.read(262144)
                with (OUT / (row["name"] + ".prefix")).open("xb") as handle:
                    handle.write(data)
                result.update(
                    status="prefix_downloaded",
                    http_status=response.status,
                    content_range=response.headers.get("Content-Range"),
                    bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                )
            messages, offset = [], 0
            while data[offset : offset + 4] == b"GRIB" and len(data) - offset >= 16:
                edition = data[offset + 7]
                length = int.from_bytes(
                    data[offset + 4 : offset + 7]
                    if edition == 1
                    else data[offset + 8 : offset + 16],
                    "big",
                )
                if length < 16 or offset + length > len(data):
                    break
                native = data[offset : offset + length]
                if native[-4:] != b"7777":
                    raise ValueError("Complete native message lacks GRIB terminator")
                gid = eccodes.codes_new_from_message(native)
                try:
                    meta = {
                        key: eccodes.codes_get(gid, key)
                        for key in (
                            "edition",
                            "dataDate",
                            "dataTime",
                            "paramId",
                            "shortName",
                            "units",
                            "stepType",
                            "startStep",
                            "endStep",
                            "validityDate",
                            "validityTime",
                            "numberOfDataPoints",
                            "gridType",
                        )
                    }
                    meta.update(
                        offset=offset,
                        length=length,
                        sha256=hashlib.sha256(native).hexdigest(),
                    )
                    messages.append(meta)
                finally:
                    eccodes.codes_release(gid)
                offset += length
            result.update(
                complete_messages=messages,
                uninterpreted_prefix_tail_bytes=len(data) - offset,
            )
        except (
            OSError,
            ValueError,
            urllib.error.URLError,
            eccodes.CodesInternalError,
        ) as exc:
            result.update(
                status="failed_preserved_no_retry",
                error_type=type(exc).__name__,
                error=str(exc),
            )
        result["completed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        results.append(result)
    save(
        "REPORT.json",
        {
            "requests": results,
            "new_model_calls": 0,
            "all_cycle_unit_equivalence_qualified": False,
            "scope": "Native header samples only. Coordinate alignment of the complete station store needs its own verification.",
        },
    )
    print(
        json.dumps(
            [
                {
                    k: row.get(k)
                    for k in ("name", "status", "http_status", "complete_messages")
                }
                for row in results
            ]
        )
    )


if __name__ == "__main__":
    main()
