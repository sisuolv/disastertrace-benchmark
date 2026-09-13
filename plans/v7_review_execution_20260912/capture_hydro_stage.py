"""Capture bounded native stage samples without converting the existing flow task."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from gpu_worker import digest, save

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]


def main(args):
    args.output.mkdir(exist_ok=False)
    helper = REPO / "plans/all_candidate_data_validation_20260912/fetch_samples.py"
    shutil.copyfile(helper, args.output / "fetch_samples.py")
    shutil.copyfile(__file__, args.output / "capture_hydro_stage.py")
    specs = []
    for lid, site in (("NRWI4", "05486000"), ("CRHA2", "15493400"), ("SCOC1", "11477000")):
        specs.append({"id": "nwps-stageflow-" + lid.lower(),
                      "url": "https://api.water.noaa.gov/nwps/v1/gauges/" + lid + "/stageflow",
                      "source_id": "NOAA-NWPS-native-stageflow", "nws_lid": lid,
                      "usgs_site": site, "max_bytes": 2 * 1024**2, "timeout": 45})
        query = urlencode({"f": "json", "monitoring_location_id": "USGS-" + site,
                           "parameter_code": "00065", "datetime": "2026-09-12T00:00:00Z/2026-09-12T23:00:00Z", "limit": 1000})
        specs.append({"id": "usgs-stage-" + lid.lower(),
                      "url": "https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items?" + query,
                      "source_id": "USGS-continuous-gage-height", "nws_lid": lid,
                      "usgs_site": site, "max_bytes": 2 * 1024**2, "timeout": 45})
    metadata = BASE / "hydro_metadata_validation_01/REPORT.json"
    plan = {"frozen_at": datetime.now(timezone.utc).isoformat(), "specs": specs,
            "maximum_logical_requests": 6, "maximum_response_bytes": 12 * 1024**2,
            "retries": 0, "per_host_parallelism": 1, "metadata_binding": {str(metadata): digest(metadata)},
            "capture_helper_sha256": digest(args.output / "fetch_samples.py"),
            "scope": "H08 current native stage forecast/observation availability and unit/datum preflight; preserve all empty/error responses. No new model calls, historical availability or flood-task admission.",
            "reference_policy": "Exact timestamps only; raw unit/datum differences remain unresolved; never substitute missing flow thresholds or alter the prior QINE/CFS chain."}
    save(args.output / "PLAN.json", plan)
    spec = importlib.util.spec_from_file_location("stage_capture", args.output / "fetch_samples.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    receipts = []
    for request in specs:
        receipt = module.fetch(request, args.output)
        receipts.append(receipt)
        print(json.dumps({key: receipt[key] for key in ("id", "http_status", "curl_exit", "bytes")}), flush=True)
    save(args.output / "CAPTURE_COMPLETE.json", {"finished_at": datetime.now(timezone.utc).isoformat(),
         "plan_sha256": digest(args.output / "PLAN.json"), "logical_requests": len(receipts),
         "response_bytes": sum(r["bytes"] for r in receipts), "new_model_calls": 0,
         "scientific_validation": False})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
