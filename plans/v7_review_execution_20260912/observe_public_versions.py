"""Bounded live first-observation receipts, separate from historical forecast scoring."""

import argparse
import csv
import hashlib
import io
import json
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from fetch_public import fetch_batch


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def now():
    return datetime.now(timezone.utc)


def main(args):
    output = args.output.resolve()
    output.mkdir(exist_ok=False)
    source = output / "source"
    source.mkdir()
    for path in (Path(__file__), Path(fetch_batch.__code__.co_filename)):
        shutil.copyfile(path, source / path.name)
    start = now()
    contract = {"started_at": start.isoformat(), "stations": ["KDEN", "KCOS", "KPUB"],
        "polls": 12, "interval_seconds": 600, "maximum_requests": 72,
        "latest_native_bulletins_per_poll_per_station": 1,
        "stop_after_utc": (start + timedelta(hours=2)).isoformat(),
        "interpretation": "Earliest observation by this monitor only. Initial sightings are left-censored; a later polling bracket is a service-snapshot observation bracket under freshness assumptions, not proven global publication/first-seen time. No F outcomes, model calls or changes to historical availability assumptions.",
        "implementation_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()}}
    write(output / "CONTRACT.json", contract)
    first_seen, last_good, fetched, receipts = {}, {}, set(), []
    for tick in range(contract["polls"]):
        due = start + timedelta(seconds=tick * contract["interval_seconds"])
        while now() < due:
            time.sleep(min(30, (due - now()).total_seconds()))
        if now() >= datetime.fromisoformat(contract["stop_after_utc"]):
            break
        requests = []
        for station in contract["stations"]:
            day = now().date()
            end = day + timedelta(days=1)
            params = {"station": station, "year1": day.year, "month1": day.month, "day1": day.day,
                "hour1": 0, "year2": end.year, "month2": end.month, "day2": end.day,
                "hour2": 0, "tz": "Etc/UTC", "fmt": "comma"}
            requests.append({"id": "taf-catalog-" + station, "station": station,
                "url": "https://mesonet.agron.iastate.edu/cgi-bin/request/taf.py?" + urlencode(params),
                "max_bytes": 1048576, "timeout": 45, "purpose": "bounded live native-product version observation"})
        plan = {"transport": "curl", "allowed_hosts": ["mesonet.agron.iastate.edu"],
            "limits": {"requests": 3, "bytes": 3 * 1048577}, "pause_seconds": 3, "requests": requests}
        plan_path, captures = output / f"catalog-plan-{tick:02d}.json", output / f"catalog-{tick:02d}"
        write(plan_path, plan)
        fetch_batch(plan_path, captures)
        manifest = json.loads((captures / "MANIFEST.json").read_text())
        native_requests = []
        for receipt in manifest["rows"]:
            receipts.append({"path": str(captures / (receipt["id"] + ".json")),
                             "http_status": receipt["http_status"], "complete": receipt["complete"]})
            if not receipt["complete"]:
                continue
            station = receipt["station"]
            rows = list(csv.DictReader(io.StringIO((captures / receipt["body_file"]).read_text())))
            versions = {r["product_id"]: r for r in rows if r["station"] == station}
            for ident, row in versions.items():
                key = station + "/" + ident
                if key not in first_seen:
                    first_seen[key] = {"station": station, "product_id": ident, "nominal_issue": row["valid"],
                        "first_observed_at": receipt["finished_at"], "poll": tick,
                        "previous_successful_poll_started_at": last_good.get(station),
                        "initial_or_unbracketed_sighting": station not in last_good,
                        "catalog_receipt": str(captures / (receipt["id"] + ".json"))}
            last_good[station] = receipt["started_at"]
            if versions:
                ident, row = max(versions.items(), key=lambda item: (item[1]["valid"], item[0]))
                if ident not in fetched:
                    if not ident.replace("-", "").isalnum():
                        raise ValueError("Unexpected native product identifier")
                    native_requests.append({"id": "taf-" + ident,
                        "url": "https://mesonet.agron.iastate.edu/api/1/nwstext/" + ident,
                        "max_bytes": 131072, "timeout": 45,
                        "catalog_metadata": {"station": station, "issued_at": row["valid"]},
                        "purpose": "latest observed native product body"})
                    fetched.add(ident)
        if native_requests:
            native_plan = {"transport": "curl", "allowed_hosts": plan["allowed_hosts"],
                "limits": {"requests": len(native_requests), "bytes": len(native_requests) * 131073},
                "pause_seconds": 3, "requests": native_requests}
            path = output / f"native-plan-{tick:02d}.json"
            write(path, native_plan)
            fetch_batch(path, output / f"native-{tick:02d}")
        status = {"updated_at": now().isoformat(), "completed_polls": tick + 1,
            "first_observations": list(first_seen.values()), "catalog_receipts": receipts,
            "native_body_attempts": len(fetched), "model_calls": 0,
            "historical_first_seen_proved": False}
        temp = output / "STATUS.tmp"
        temp.write_text(json.dumps(status, indent=2) + "\n")
        temp.replace(output / "STATUS.json")
        print(json.dumps({"poll": tick, "unique_versions_observed": len(first_seen), "native_bodies_attempted": len(fetched)}), flush=True)
    write(output / "COMPLETE.json", {"completed_at": now().isoformat(), "completed_polls": status["completed_polls"],
        "historical_first_seen_proved": False, "model_calls": 0})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
