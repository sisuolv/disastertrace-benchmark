"""Bounded native DWD daily-reference acquisition for the existing Berus pilot."""

import datetime as dt
import hashlib
import io
import json
import re
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE / "temperature_daily_reference_01"
BASE = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/"


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def fetch(name, url, maximum=25 * 1024 * 1024):
    record = {"name": name, "url": url, "started_at": now(), "maximum_bytes": maximum}
    save(ROOT / (name + ".intent.json"), record)
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "DisasterTrace/0.1 research data qualification"}
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = response.read(maximum + 1)
            if len(payload) > maximum:
                raise ValueError("Bounded response size exceeded")
            record.update(
                http_status=response.status,
                final_url=response.url,
                response_headers={
                    k: response.headers.get(k)
                    for k in (
                        "Content-Type",
                        "Content-Length",
                        "Date",
                        "Last-Modified",
                        "ETag",
                    )
                },
                sha256=hashlib.sha256(payload).hexdigest(),
                bytes=len(payload),
                status="received",
            )
        with (ROOT / name).open("xb") as handle:
            handle.write(payload)
    except Exception as exc:
        record.update(status="failed", error_type=type(exc).__name__, reason=str(exc))
        payload = None
    record["completed_at"] = now()
    save(ROOT / (name + ".receipt.json"), record)
    return payload


def main():
    ROOT.mkdir(exist_ok=False)
    save(
        ROOT / "PLAN.json",
        {
            "schema": "disastertrace.daily_reference_acquisition.v1",
            "created_at": now(),
            "station": "00460",
            "station_name": "Berus",
            "evaluation_dates": ["2017-01-01", "2018-12-31"],
            "source": BASE,
            "maximum_requests": 4,
            "maximum_response_bytes": 25 * 1024 * 1024,
            "selection_rule": "Unique station00460 historical ZIP covering2017-2018, latest end then earliest start; no outcome-based selection.",
            "purpose": "Validate native daily TXK/TNK references for an already exposed station and identify daily forecast-support gaps.",
            "new_model_calls": 0,
            "reserved_confirmation_access": False,
            "heatwave_forecast_qualification": False,
        },
    )
    directory = fetch("historical_index.html", BASE + "historical/", 4 * 1024 * 1024)
    if directory is None:
        save(
            ROOT / "COMPLETE.json",
            {"data_received": False, "reason": "Historical directory unavailable"},
        )
        return
    names = sorted(
        set(
            re.findall(
                r"tageswerte_KL_00460_([0-9]{8})_([0-9]{8})_hist\.zip",
                directory.decode(),
            )
        )
    )
    eligible = [
        (start, end)
        for start, end in names
        if start <= "20170101" and end >= "20181231"
    ]
    if not eligible:
        save(
            ROOT / "COMPLETE.json",
            {
                "data_received": False,
                "reason": "No covering native station archive",
                "directory_candidates": names,
            },
        )
        return
    start, end = sorted(eligible, key=lambda pair: (-int(pair[1]), pair[0]))[0]
    archive = f"tageswerte_KL_00460_{start}_{end}_hist.zip"
    save(ROOT / "SELECTED.json", {"archive": archive, "all_candidates": names})
    payload = fetch(archive, urllib.parse.urljoin(BASE + "historical/", archive))
    if payload is not None:
        with zipfile.ZipFile(io.BytesIO(payload)) as handle:
            if handle.testzip() is not None:
                raise ValueError("Native ZIP CRC failure")
            save(
                ROOT / "ZIP_MEMBERS.json",
                [
                    {"name": m.filename, "bytes": m.file_size, "crc": m.CRC}
                    for m in handle.infolist()
                ],
            )
    # These official product descriptions are independently useful even if one language is absent.
    fetch(
        "DESCRIPTION_obsgermany_climate_daily_kl_en.pdf",
        BASE + "DESCRIPTION_obsgermany_climate_daily_kl_en.pdf",
        8 * 1024 * 1024,
    )
    fetch(
        "BESCHREIBUNG_obsgermany_climate_daily_kl_de.pdf",
        BASE + "BESCHREIBUNG_obsgermany_climate_daily_kl_de.pdf",
        8 * 1024 * 1024,
    )
    receipts = [json.loads(p.read_text()) for p in ROOT.glob("*.receipt.json")]
    if len(receipts) > 4:
        raise ValueError("Request envelope exceeded")
    save(
        ROOT / "COMPLETE.json",
        {
            "completed_at": now(),
            "data_received": payload is not None,
            "archive": archive,
            "requests": len(receipts),
            "request_statuses": {r["name"]: r["status"] for r in receipts},
            "new_model_calls": 0,
            "retries": 0,
        },
    )
    print((ROOT / "COMPLETE.json").read_text())


if __name__ == "__main__":
    main()
