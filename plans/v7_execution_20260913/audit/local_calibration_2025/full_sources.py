"""Bounded parallel raw TAF collection from a fixed prior-period catalogue."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from precheck import HERE, REPO, capture, dump, rows

sys.path.insert(0, str(REPO / "plans/v7_review_execution_20260912"))
from fetch_public import curl_fetch  # noqa: E402


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def prepare():
    plan = json.loads((HERE / "FULL_FETCH_01.json").read_text())
    requests, reused = [], {}
    catalogue_counts = {}
    for station in ["KDEN", "KCOS", "KPUB"]:
        raw, _ = capture(HERE / "full_captures_01", "taf-catalog-" + station)
        products = {}
        for row in rows(raw):
            if row["station"] != station:
                raise ValueError("Station mismatch")
            products[row["product_id"]] = row["valid"]
        catalogue_counts[station] = len(products)
        for product_id, issued in sorted(products.items()):
            identity = "taf-" + product_id
            spec = {"id": identity, "url": "https://mesonet.agron.iastate.edu/api/1/nwstext/" + product_id,
                    "max_bytes": 65536, "timeout": 60, "catalog_metadata": {"station": station, "issued_at": issued},
                    "purpose": "Complete frozen Front local calibration catalogue, native bulletin including applicable clauses"}
            if (HERE / "native_01" / (identity + ".json")).exists():
                _, receipt = capture(HERE / "native_01", identity)
                if receipt["catalog_metadata"] != spec["catalog_metadata"]:
                    raise ValueError("Native reuse metadata conflict")
                reused[identity] = str((HERE / "native_01").relative_to(REPO))
            else:
                requests.append(spec)
    if len(requests) + len(reused) > plan["native_product_request_cap"]:
        raise ValueError("Native product cap exceeded; preserve catalogue without fetching")
    worst_case = plan["limits"]["bytes"] + sum(r["max_bytes"] + 1 for r in requests)
    if worst_case > plan["total_cycle_safety_cap_bytes"]:
        raise ValueError("Aggregate transfer reservation exceeds100MiB")
    dump("FULL_NATIVE_PLAN.json", {"prepared_at": now(), "requests": requests, "reused": reused,
                                   "catalogue_distinct_products": catalogue_counts, "request_limit": plan["native_product_request_cap"],
                                   "parallelism": 4, "attempts_per_request": 1, "worst_case_reserved_bytes": worst_case,
                                   "all_products_selected_by_fixed_station_date_catalogue": True, "fitting_not_started": True})


def fetch_one(spec, directory):
    write(directory / (spec["id"] + ".intent.json"), dict(spec, started_at=now()))
    started = now()
    raw, result = curl_fetch(spec)
    (directory / (spec["id"] + ".body")).write_bytes(raw)
    result.update(spec, started_at=started, finished_at=now(), bytes=len(raw),
                  sha256=hashlib.sha256(raw).hexdigest(), body_file=spec["id"] + ".body",
                  first_seen_is_historical=False, as_of_admission=False)
    write(directory / (spec["id"] + ".json"), result)
    return result


def fetch():
    plan = json.loads((HERE / "FULL_NATIVE_PLAN.json").read_text())
    directory = HERE / "full_native_new_01"
    directory.mkdir(exist_ok=False)
    write(directory / "INTENT.json", {"started_at": now(), "plan_sha256": hashlib.sha256((HERE / "FULL_NATIVE_PLAN.json").read_bytes()).hexdigest(),
                                       "parallelism": 4, "requests": len(plan["requests"]), "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    completed = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch_one, spec, directory) for spec in plan["requests"]]
        for future in as_completed(futures):
            row = future.result()
            completed.append(row)
            if len(completed) % 25 == 0 or not row["complete"]:
                print(len(completed), "/", len(futures), row["http_status"], row["complete"], flush=True)
    write(directory / "MANIFEST.json", {"planned": len(plan["requests"]), "attempted": len(completed), "bytes": sum(r["bytes"] for r in completed),
                                         "rows": sorted(completed, key=lambda r: r["id"]), "completed_at": now()})
    if not all(r["complete"] for r in completed):
        raise ValueError("Incomplete native collection; no dataset assembly")
    output = HERE / "full_native_01"
    output.mkdir(exist_ok=False)
    origins, all_rows = {}, []
    for spec in plan["requests"]:
        origins[spec["id"]] = directory
    origins.update({k: REPO / v for k, v in plan["reused"].items()})
    for identity, origin in sorted(origins.items()):
        _, receipt = capture(origin, identity)
        for suffix in (".json", ".body"):
            shutil.copyfile(origin / (identity + suffix), output / (identity + suffix))
        all_rows.append(receipt)
    write(output / "MANIFEST.json", {"planned": len(all_rows), "attempted": len(all_rows), "rows": all_rows,
                                     "assembly_is_not_network": True, "bytes": sum(r["bytes"] for r in all_rows)})
    write(output / "ORIGINS.json", {k: str(p.relative_to(REPO)) for k, p in origins.items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["prepare", "fetch"])
    args = parser.parse_args()
    prepare() if args.stage == "prepare" else fetch()
