"""Bounded public AWC capture: collector first-seen, never historical publication."""

import argparse
import datetime as dt
import hashlib
import json
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc


def now():
    return dt.datetime.now(UTC)


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(out):
    out.mkdir(exist_ok=False)
    start = now().replace(microsecond=0) + dt.timedelta(seconds=15)
    last = min(
        start + dt.timedelta(hours=4), dt.datetime(2026, 9, 14, 2, 15, tzinfo=UTC)
    )
    assert start < last
    slots = []
    cursor = start
    while cursor <= last:
        slots.append(cursor.isoformat())
        cursor += dt.timedelta(minutes=15)
    copied = out / "capture_shadow_sources.py"
    shutil.copyfile(Path(__file__), copied)
    save(
        out / "PLAN.json",
        {
            "schema": "disastertrace.bounded_awc_shadow_capture.v1",
            "frozen_at": now().isoformat(),
            "stations": ["KSFO", "KOAK", "KSJC"],
            "poll_times": slots,
            "end_at": (last + dt.timedelta(minutes=2)).isoformat(),
            "request_deadline_seconds": 30,
            "max_response_bytes": 4 * 1024 * 1024,
            "max_requests": 2 * len(slots),
            "retries": 0,
            "endpoints": {
                "taf": "https://aviationweather.gov/api/data/taf?ids=KSFO,KOAK,KSJC&format=json",
                "metar": "https://aviationweather.gov/api/data/metar?ids=KSFO,KOAK,KSJC&format=json&hours=2",
            },
            "source_sha256": sha(copied),
            "scope": "Source-only prospective capture. No submitted forecasts, model calls, or forecast score. AWC-issued/observation times and this collector's completed receipt time remain distinct.",
            "reference_maturity": "Snapshots preserve actual versions; collection-end references are provisional, not certified mature official outcomes.",
            "first_seen_rule": "Earliest completed successful receipt of identical source product bytes within this collector; not global first public release. No product may be exposed before that receipt.",
            "stop_rule": "One bounded attempt per registered endpoint/poll; stop after3 consecutive all-endpoint failed polls or absolute end. Preserve every failed or missed poll; no catch-up burst.",
            "date_selection": "Current clock and fixed four-hour duration, before source response inspection; no severity or model-score selection.",
        },
    )
    print(
        json.dumps(
            {"out": str(out), "polls": len(slots), "max_requests": 2 * len(slots)}
        ),
        flush=True,
    )


def run(out):
    plan = json.loads((out / "PLAN.json").read_text())
    assert sha(Path(__file__)) == plan["source_sha256"]
    save(
        out / "STARTED.json",
        {"at": now().isoformat(), "plan_sha256": sha(out / "PLAN.json")},
    )
    end = dt.datetime.fromisoformat(plan["end_at"])
    rows, failures = [], 0
    for index, slot in enumerate(plan["poll_times"]):
        when = dt.datetime.fromisoformat(slot)
        while now() < min(when, end):
            time.sleep(max(0, min(20, (min(when, end) - now()).total_seconds())))
        if now() >= end or failures >= 3:
            break
        folder = out / f"poll_{index:02d}"
        folder.mkdir()
        if now() > when + dt.timedelta(minutes=2):
            row = {"poll": index, "scheduled_at": slot, "status": "missed_no_catchup"}
            save(folder / "MISSED.json", row)
            rows.append(row)
            continue
        good = 0
        for kind, url in plan["endpoints"].items():
            receipt = {
                "poll": index,
                "kind": kind,
                "url": url,
                "scheduled_at": slot,
                "started_at": now().isoformat(),
            }
            tic = time.monotonic()
            try:
                request = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "DisasterTrace-research-source-validation/0.1",
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(
                    request, timeout=plan["request_deadline_seconds"]
                ) as response:
                    payload = response.read(plan["max_response_bytes"] + 1)
                    receipt.update(
                        http_status=response.status,
                        content_type=response.headers.get("Content-Type"),
                        server_date=response.headers.get("Date"),
                    )
                receipt["completed_at"] = now().isoformat()
                if len(payload) > plan["max_response_bytes"]:
                    raise ValueError("Bounded response too large")
                path = folder / (kind + ".raw.json")
                with path.open("xb") as handle:
                    handle.write(payload)
                receipt.update(bytes=len(payload), payload_sha256=sha(path))
                products = json.loads(payload)
                if not isinstance(products, list) or not all(
                    isinstance(p, dict) for p in products
                ):
                    raise ValueError("Unexpected native AWC response shape")
                receipt.update(status="received_json", product_rows=len(products))
                good += 1
            except (OSError, ValueError) as error:
                receipt.update(status="failed", error_type=type(error).__name__)
                if isinstance(error, urllib.error.HTTPError):
                    receipt["http_status"] = error.code
                    payload = error.read(plan["max_response_bytes"])
                    path = folder / (kind + ".http_error.bin")
                    with path.open("xb") as handle:
                        handle.write(payload)
                    receipt.update(bytes=len(payload), payload_sha256=sha(path))
            receipt.setdefault("completed_at", now().isoformat())
            receipt["elapsed_seconds"] = time.monotonic() - tic
            save(folder / (kind + ".receipt.json"), receipt)
            rows.append(receipt)
        failures = 0 if good else failures + 1
        print(
            json.dumps(
                {"poll": index, "received_endpoints": good, "at": now().isoformat()}
            ),
            flush=True,
        )
    save(
        out / "COMPLETE.json",
        {
            "at": now().isoformat(),
            "plan_sha256": sha(out / "PLAN.json"),
            "receipts": rows,
            "actual_requests": sum("kind" in r for r in rows),
            "successful_requests": sum(r["status"] == "received_json" for r in rows),
            "registered_polls": len(plan["poll_times"]),
            "attempted_poll_count": len({r["poll"] for r in rows if "kind" in r}),
            "actual_model_calls": 0,
            "new_forecast_scores": 0,
            "unattempted_polls": sorted(
                set(range(len(plan["poll_times"]))) - {r["poll"] for r in rows}
            ),
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["freeze", "run"])
    parser.add_argument("--out", type=Path, default=HERE / "shadow_capture_01")
    args = parser.parse_args()
    (freeze if args.mode == "freeze" else run)(args.out)
