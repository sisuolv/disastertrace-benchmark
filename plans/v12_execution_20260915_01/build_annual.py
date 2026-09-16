"""Strict annual native joins reuse verified bytes and retain every monthly unit."""
import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from disastertrace.monitoring_v1.spool_backend import digest, publish, read

RUN = Path(__file__).resolve().parent
OUT = RUN / "annual_stage_B"
REPO = RUN.parents[1]
OLD = REPO / "plans/v11_execution_20260915_01"


def prepare():
    folder = OUT / "joins"
    folder.mkdir(exist_ok=False)
    source = folder / "source"; source.mkdir()
    for name, path in {
        "build_regional.py": REPO / "plans/v7_adaptive_execution_20260913/build_regional.py",
        "build_native_v2.py": REPO / "plans/v8_measurement_execution_20260913_01/scripts/build_native_v2.py",
    }.items():
        shutil.copy2(path, source / name)
    shutil.copytree(RUN / "branch_source/disastertrace", source / "disastertrace")
    units = []
    keys_by_unit = {}
    for record in read(OUT / "OBJECTS.json"):
        for ref in record["references"]:
            keys_by_unit.setdefault(ref["unit"], []).append(record["request_key"])
    previous = read(OLD / "annual_catalog_01/RESULT.json")
    for row in previous["results"]:
        name = row["unit"]
        if row["complete"]:
            origin, captures = OLD / "annual_catalog_01" / name, Path(row["captures"])
        else:
            origin = OUT / name; captures = origin / "catalogs_verified"
        units.append({"unit": name, "origin": str(origin), "captures": str(captures),
            "calendar_sha256": digest(origin / "CALENDAR.json"),
            "native_plan_sha256": digest(origin / "SOURCE_NATIVE_PLAN.json"),
            "source_request_keys": sorted(set(keys_by_unit[name]))})
    publish(folder / "REGISTRATION.json", {"units": units, "expected_units": 72,
        "source_files": {str(p): digest(p) for p in source.rglob("*.py")},
        "worker_script_sha256": digest(Path(__file__)), "source_objects_sha256": digest(OUT / "OBJECTS.json"),
        "at": dt.datetime.now(dt.timezone.utc).isoformat(), "confirmation_opened": False,
        "incomplete_month_policy": "retain as unqualified; no omitted-version native join or annual fit",
        "new_HTTP_requests": 0, "new_model_calls": 0})


def build(task):
    row, verified = task
    folder = OUT / "joins" / row["unit"]
    folder.mkdir(exist_ok=False)
    start = time.monotonic()
    result = {"unit": row["unit"], "complete": False}
    try:
        origin = Path(row["origin"])
        if digest(origin / "CALENDAR.json") != row["calendar_sha256"] or digest(origin / "SOURCE_NATIVE_PLAN.json") != row["native_plan_sha256"]:
            raise ValueError("Registered source/calendar changed")
        missing = sorted(set(row["source_request_keys"]) - set(verified))
        if missing:
            result.update(status="unqualified_missing_native_bytes", missing_keys=missing)
            publish(folder / "RESULT.json", result)
            return result
        for name in ("CALENDAR.json", "SOURCE_NATIVE_PLAN.json"):
            shutil.copy2(origin / name, folder / name)
        calendar = read(folder / "CALENDAR.json")
        catalogs = folder / "catalogs"; catalogs.mkdir()
        for p in Path(row["captures"]).iterdir():
            if p.is_file():
                os.symlink(str(p.resolve()), catalogs / p.name)
        native = folder / "native_verified"; native.mkdir()
        receipts, provenance = [], []
        for key in row["source_request_keys"]:
            bound = verified[key]
            body, receipt = Path(bound["body_path"]), Path(bound["receipt_path"])
            r = read(receipt)
            if digest(body) != bound["sha256"] or digest(receipt) != bound["receipt_sha256"] or not r["complete"] or r["http_status"] != 200 or r.get("curl_exit") != 0:
                raise ValueError("Unverified annual bytes")
            for p, name in ((body, r["id"] + ".body"), (receipt, r["id"] + ".json")):
                os.symlink(str(p.resolve()), native / name)
            receipts.append(r)
            provenance.append({"key": key, **bound})
        publish(native / "MANIFEST.json", {"planned": len(receipts), "attempted": len(receipts), "rows": receipts, "all_bytes_reused": True})
        publish(folder / "REUSED_BYTES.json", provenance)
        stage, dataset = folder / "dataset_stage_v1", folder / "dataset_v2"
        source = OUT / "joins/source"
        commands = [
            [sys.executable, str(source / "build_regional.py"), "--contract", str(folder / "CALENDAR.json"), "--metar", str(catalogs), "--taf", str(native), "--source-root", str(folder), "--output", str(stage)],
            [sys.executable, str(source / "build_native_v2.py"), "--dataset", str(stage), "--source-root", str(folder), "--output", str(dataset)],
        ]
        for index, command in enumerate(commands):
            publish(folder / f"COMMAND_{index}.json", {"argv": command, "timeout_seconds": 2400})
            env = {**os.environ, "PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
            with (folder / f"build_{index}.log").open("x") as log:
                completed = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=2400)
            publish(folder / f"EXIT_{index}.json", {"exit_code": completed.returncode})
            if completed.returncode:
                raise ValueError("Native annual join failed; original log retained")
        opportunities = read(dataset / "public/OPPORTUNITIES.json")
        lower = dt.datetime.fromisoformat(calendar["cutoff_start"].replace("Z", "+00:00"))
        upper = dt.datetime.fromisoformat(calendar["cutoff_end_exclusive"].replace("Z", "+00:00"))
        expected = int((upper-lower).total_seconds()/3600)*len(calendar["stations"])*len(calendar["thresholds_m"])*len(calendar["lead_hours"])
        if len(opportunities) != expected or len({o["opportunity_id"] for o in opportunities}) != expected:
            raise ValueError("Annual opportunity calendar differs")
        result.update(complete=True, status="native_join_qualified", dataset=str(dataset), opportunities=expected,
            dataset_files={str(p.relative_to(dataset)): digest(p) for p in dataset.rglob("*.json")},
            report=read(dataset / "NATIVE_UPGRADE_REPORT.json") if (dataset / "NATIVE_UPGRADE_REPORT.json").exists() else None)
    except Exception as exc:
        result.update(status="failed", error=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
    result["seconds"] = time.monotonic() - start
    publish(folder / "RESULT.json", result)
    print(json.dumps({k:v for k,v in result.items() if k not in {"dataset_files", "report", "traceback"}}), flush=True)
    return result


def execute(workers):
    folder = OUT / "joins"
    reg = read(folder / "REGISTRATION.json")
    for p, sha in reg["source_files"].items():
        if digest(Path(p)) != sha:
            raise ValueError("Native join source freeze changed")
    if digest(Path(__file__)) != reg["worker_script_sha256"] or digest(OUT / "OBJECTS.json") != reg["source_objects_sha256"]:
        raise ValueError("Annual join registration changed")
    publish(folder / "CLAIM.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "workers": workers})
    deadline = dt.datetime.fromisoformat("2026-09-16T00:24:27+00:00").timestamp()
    while not (OUT / "DOWNLOAD_RESULTS.json").exists():
        if time.time() > deadline or (RUN / "BATCH_CLOSED.json").exists():
            publish(folder / "RESULT.json", {"passed": False, "status": "source_download_not_finished_before_join_deadline", "expected_units": 72})
            return
        time.sleep(60)
    verified = {}
    for row in read(OUT / "OBJECTS.json"):
        if row["state"] == "verified_cached":
            verified[row["request_key"]] = row["verified_variants"][0]
    conflicts = set()
    for r in read(OUT / "DOWNLOAD_RESULTS.json"):
        if not r.get("complete"):
            continue
        key = r["key"]
        if key in verified and verified[key]["sha256"] != r["sha256"]:
            conflicts.add(key)
        verified[key] = r
    for key in conflicts:
        verified.pop(key, None)
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(build, (row, {k: verified[k] for k in row["source_request_keys"] if k in verified})) for row in reg["units"]]
        for future in as_completed(futures):
            results.append(future.result())
    publish(folder / "RESULT.json", {"passed": len(results)==72 and all(r["complete"] for r in results), "results": results,
        "expected_units": 72, "completed_units": sum(r["complete"] for r in results), "conflicting_keys": sorted(conflicts),
        "new_HTTP_requests": 0, "new_model_calls": 0, "annual_fit_complete": False, "confirmation_opened": False})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("mode", choices=["prepare", "execute"])
    parser.add_argument("--workers", type=int, default=12); args=parser.parse_args()
    prepare() if args.mode=="prepare" else execute(args.workers)
