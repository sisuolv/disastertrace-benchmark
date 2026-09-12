"""Separate GEE network reachability, authentication, and real numeric sampling."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import ee
import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--project", default="disastertrace-gee")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    urls = [
        "https://earthengine.googleapis.com/$discovery/rest?version=v1",
        "https://accounts.google.com/",
        "https://oauth2.googleapis.com/token",
        "https://earthengine.googleapis.com/v1/projects/" + args.project + "/assets?pageSize=1",
    ]

    def check(url):
        try:
            response = requests.get(url, timeout=20)
            return dict(url=url, status=response.status_code, bytes=len(response.content))
        except requests.RequestException as error:
            return dict(url=url, error_type=type(error).__name__)

    with ThreadPoolExecutor(max_workers=4) as pool:
        checks = list(pool.map(check, urls))
    report = dict(checked_at=datetime.now(timezone.utc).isoformat(), project=args.project,
                  network=checks, authenticated=False, numeric_sample=False)
    try:
        ee.Initialize(project=args.project)
        ee.data.setDeadline(30000)
        report["server_check"] = ee.Number(1).getInfo()
        report["authenticated"] = report["server_check"] == 1
        region = ee.Geometry.Rectangle([116.3, 39.8, 116.4, 39.9])
        collection = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").filterDate("2024-01-01", "2024-01-02")
        item = ee.Image(collection.first())
        values = item.select("temperature_2m").sample(region=region, scale=11132, numPixels=3,
                                                     geometries=True).getInfo()
        body = json.dumps(values, indent=2).encode()
        (args.output / "era5_land_sample.json").write_bytes(body)
        report.update(collection="ECMWF/ERA5_LAND/DAILY_AGGR", image_id=item.id().getInfo(),
                      sample_sha256=hashlib.sha256(body).hexdigest(),
                      numeric_sample=any(isinstance(f["properties"].get("temperature_2m"), (int, float))
                                         for f in values.get("features", [])), units="K")
    except Exception as error:
        report["error_type"] = type(error).__name__
        # Only allowlisted diagnostic strings; arbitrary auth exceptions may embed secrets.
        message = str(error).lower()
        report["failure_category"] = ("local_login_required" if "authorize access" in message else
                                      "project_or_request_error_requires_local_inspection")
    report["limits"] = ["HTTP responses do not establish project permission.",
                        "One historical ERA5-Land sample does not validate all GEE collections or live latency."]
    (args.output / "GEE_CHECK.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
