"""Bounded repeat capture of unchanged USGS windows to inspect provisional revisions."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from gpu_worker import digest, save

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
PARENT = REPO / "plans/task_chain_feasibility_20260912"
CAPTURE = REPO / "plans/all_candidate_data_validation_20260912/fetch_samples.py"


def main(args):
    specs = [s for s in json.loads((PARENT / "SPEC_02.json").read_text()) if s["id"].startswith("usgs-flow-")]
    if len(specs) != 3 or any(s.get("earthdata") or s["max_bytes"] > 4 * 1024**2 for s in specs):
        raise ValueError("Unexpected repeat-capture scope")
    args.output.mkdir(exist_ok=False)
    (args.output / "before").mkdir()
    (args.output / "after").mkdir()
    shutil.copyfile(__file__, args.output / "capture_hydro_revisions.py")
    shutil.copyfile(CAPTURE, args.output / "fetch_samples.py")
    before_bindings = {}
    for spec in specs:
        receipt_path = PARENT / "captures_02" / (spec["id"] + ".json")
        body_path = receipt_path.with_suffix(".body")
        receipt = json.loads(receipt_path.read_text())
        if receipt["http_status"] != 200 or receipt["curl_exit"] != 0 or receipt["sha256"] != digest(body_path):
            raise ValueError("Original USGS capture is incomplete or changed")
        if receipt["url"] != spec["url"]:
            raise ValueError("Repeat query would not have the same requested window")
        for path in (receipt_path, body_path):
            copied = args.output / "before" / path.name
            shutil.copyfile(path, copied)
            before_bindings[str(copied.relative_to(args.output))] = digest(copied)
    plan = {"frozen_at": datetime.now(timezone.utc).isoformat(), "specs": specs,
            "before_bindings": before_bindings, "capture_helper_sha256": digest(args.output / "fetch_samples.py"),
            "scope": "Post-hoc H08 source-maturity preflight. Re-fetch the same three 2026-09-10 00Z to 2026-09-12 09Z discharge windows once each; compare all rows, including failures and metadata-only changes.",
            "maximum_logical_requests": 3, "maximum_response_bytes": 12 * 1024**2,
            "per_host_parallelism": 1, "retry_count": 0,
            "new_model_calls": 0, "new_H08_warning_admission": False,
            "future_first_seen_claim": False,
            "interpretation": "New retrieval times are local observations, not historical first-seen. Do not overwrite the earlier provisional labels or derive flood thresholds from these values."}
    save(args.output / "PLAN.json", plan)
    module_spec = importlib.util.spec_from_file_location("bounded_hydro_capture", args.output / "fetch_samples.py")
    capture = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(capture)
    receipts = []
    for spec in specs:
        receipt = capture.fetch(spec, args.output / "after")
        receipts.append(receipt)
        print(json.dumps({k: receipt[k] for k in ("id", "http_status", "curl_exit", "bytes")}), flush=True)
    save(args.output / "CAPTURE_COMPLETE.json", {"finished_at": datetime.now(timezone.utc).isoformat(),
        "plan_sha256": digest(args.output / "PLAN.json"), "requests": len(receipts),
        "bytes": sum(r["bytes"] for r in receipts), "receipts": receipts,
        "scientific_validation": False, "new_model_calls": 0})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
