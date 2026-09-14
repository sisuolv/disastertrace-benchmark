"""Freeze three regional natural calendars before bounded native data acquisition."""

import concurrent.futures
import datetime
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
OUT = HERE / "regional_calendar_extension_01"
REGIONS = {"new_york": ["KJFK", "KLGA", "KEWR"], "chicago": ["KORD", "KMDW", "KRFD"],
           "denver": ["KDEN", "KBJC", "KAPA"]}
PYTHON = str(REPO / "disastertrace-starter/.venv/bin/python")


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    with path.open("x") as handle:
        json.dump(data, handle, indent=2, allow_nan=False)
        handle.write("\n")


def run(directory, name, command):
    save(directory / (name + ".command.json"), {"command": command})
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(OUT / "source"))
    with (directory / (name + ".log")).open("x") as handle:
        result = subprocess.run(command, env=env, cwd=REPO, stdout=handle, stderr=subprocess.STDOUT, check=False)
    save(directory / (name + ".exit.json"), {"exit_code": result.returncode})
    if result.returncode:
        raise RuntimeError("Failed recorded stage: " + name)


def acquire(directory, plan_path, name):
    plan = load(plan_path)
    destination = directory / name
    command = [PYTHON, str(OUT / "source/fetch_public.py"), str(plan_path), str(destination)]
    run(directory, name + "_01", command)
    first = load(destination / "MANIFEST.json")
    expected = {r["id"]: r for r in plan["requests"]}
    assert first["planned"] == first["attempted"] == len(expected)
    assert {r["id"] for r in first["rows"]} == set(expected)
    failed = [r for r in first["rows"] if not r["complete"] or r.get("curl_exit") != 0]
    if not failed:
        return destination
    ids = {r["id"] for r in failed}
    retry = {**plan, "requests": [expected[i] for i in sorted(ids)],
             "limits": {"requests": len(ids), "bytes": sum(expected[i]["max_bytes"] + 1 for i in ids)},
             "continuation": "One exact retry of failed native retrievals; originals remain consumed and preserved."}
    retry_plan = directory / (name + "_EXACT_RETRY_PLAN.json")
    retry_out = directory / (name + "_retry_01")
    save(retry_plan, retry)
    run(directory, name + "_retry_01", [PYTHON, str(OUT / "source/fetch_public.py"),
                                       str(retry_plan), str(retry_out)])
    repaired = load(retry_out / "MANIFEST.json")
    assert repaired["planned"] == repaired["attempted"] == len(ids)
    assert {r["id"] for r in repaired["rows"]} == ids
    assert all(r["complete"] and r.get("curl_exit") == 0 for r in repaired["rows"]), "Failed exact retry retained"
    merged = directory / (name + "_complete_02")
    merged.mkdir(exist_ok=False)
    choices = {r["id"]: r for r in repaired["rows"]}
    rows, provenance = [], []
    for ident in sorted(expected):
        origin = retry_out if ident in choices else destination
        row = load(origin / (ident + ".json"))
        assert row["complete"] and row["sha256"] == sha(origin / row["body_file"])
        for suffix in (".body", ".json"):
            shutil.copyfile(origin / (ident + suffix), merged / (ident + suffix))
        rows.append(row)
        provenance.append({"id": ident, "original_receipt": str(destination / (ident + ".json")),
                           "chosen_receipt": str(origin / (ident + ".json")),
                           "chosen_receipt_sha256": sha(origin / (ident + ".json"))})
    save(merged / "MANIFEST.json", {"planned": len(expected), "attempted": len(expected), "rows": rows,
        "merged_verified_sources": True, "total_physical_attempts": len(expected) + len(ids)})
    save(merged / "PROVENANCE.json", provenance)
    return merged


def region(name):
    directory = OUT / name
    try:
        catalogs = acquire(directory, directory / "SOURCE_CATALOG_PLAN.json", "catalogs")
        native_plan = directory / "SOURCE_NATIVE_PLAN.json"
        run(directory, "native_plan", [PYTHON, str(OUT / "source/prepare_native_fetch.py"),
                                      "--catalogs", str(catalogs), "--output", str(native_plan)])
        assert len(load(native_plan)["requests"]) <= 500, "Frozen per-region native request ceiling exceeded"
        native = acquire(directory, native_plan, "native")
        stage = directory / "dataset_stage_v1"
        run(directory, "build_stage", [PYTHON, str(OUT / "source/build_regional_stage_v1.py"),
            "--contract", str(directory / "CALENDAR.json"), "--metar", str(catalogs), "--taf", str(native),
            "--source-root", str(directory), "--output", str(stage)])
        run(directory, "build_native_v2", [PYTHON, str(OUT / "source/build_native_v2.py"),
            "--dataset", str(stage), "--source-root", str(directory), "--output", str(directory / "dataset_v2")])
        report = load(stage / "REGIONAL_JOIN_AUDIT.json")
        save(directory / "COMPLETE.json", {"completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source_objects": len(load(native_plan)["requests"]) + 3, "report": report,
            "model_calls": 0, "forecast_performance_scored": False, "confirmation": False})
        return {"region": name, "complete": True}
    except Exception as exc:  # noqa: BLE001 - preserve one regional failure, let independent cohorts finish.
        row = {"region": name, "complete": False, "error_type": type(exc).__name__, "error": str(exc)}
        save(directory / "FAILED.json", row)
        return row


def main():
    OUT.mkdir(exist_ok=False)
    source = OUT / "source"
    source.mkdir()
    prior = REPO / "plans/v7_adaptive_execution_20260913"
    template = load(prior / "DEVELOPMENT_CALENDAR.json")
    original = load(prior / "SOURCE_CATALOG_PLAN.json")
    for name, stations in REGIONS.items():
        directory = OUT / name
        directory.mkdir()
        calendar = {**template, "preregistered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "stations": stations, "cutoff_start": "2025-01-06T00:00:00Z", "cutoff_end_exclusive": "2025-01-13T00:00:00Z",
            "opportunities_per_threshold": 1512, "stage": "new_regional_data_admission_only",
            "date_selection": "First complete Monday-Sunday week of January2025; no observed-value or model-gain filtering.",
            "region_selection": "Three geographically proximate airports per coastal, continental and High Plains region.",
            "image_admission": "none", "baseline_mapping": "No regional calibration has been fitted or qualified.",
            "forecast_baseline": "Native full TAF source and version selection only; probability projection awaits separate regional training calendar.",
            "secondary_threshold_reason": "5km adverse visibility includes snow/rain/BR; not necessarily fog or an independent hazard.",
            "reserved_confirmation": "Existing Bay2025-02-17..24 confirmation remains unopened."}
        save(directory / "CALENDAR.json", calendar)
        requests = []
        for station in stations:
            for old in original["requests"][:2]:
                parsed = urlsplit(old["url"])
                query = dict(parse_qsl(parsed.query))
                is_metar = old["id"].startswith("metar-")
                query.update(station=station[1:] if is_metar else station, year1="2025", month1="1", day1="4",
                             year2="2025", month2="1", day2="14")
                requests.append({**old, "id": ("metar-routine-" if is_metar else "taf-catalog-") + station,
                    "url": urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))})
        save(directory / "SOURCE_CATALOG_PLAN.json", {**original, "requests": requests,
            "registered_at": calendar["preregistered_at"], "calendar_sha256": sha(directory / "CALENDAR.json")})
    old = REPO / "plans/v7_review_execution_20260912"
    for name in ("fetch_public.py", "prepare_native_fetch.py"):
        shutil.copyfile(old / name, source / name)
    shutil.copyfile(prior / "build_regional.py", source / "build_regional_stage_v1.py")
    shutil.copyfile(HERE / "scripts/build_native_v2.py", source / "build_native_v2.py")
    for module in ("monitoring_v1", "monitoring_fixed_v1"):
        shutil.copytree(REPO / "disastertrace-starter/src/disastertrace" / module,
                        source / "disastertrace" / module, ignore=shutil.ignore_patterns("__pycache__"))
    (source / "disastertrace/__init__.py").write_text('"""Frozen regional acquisition package."""\n')
    shutil.copyfile(Path(__file__), source / "extend_regional_calendars.py")
    save(OUT / "PREREGISTRATION.json", {"regions": REGIONS, "selected_before_requests": True,
        "selection_basis": "calendar and airport geography, not severity or model response",
        "cutoff_days_per_region": 7, "opportunities_total_both_thresholds": 9072,
        "max_catalog_attempts": 36, "max_native_originals": 1500, "max_native_attempts_including_one_exact_retry": 3000,
        "parallel_regional_fetchers": 3, "native_pause_seconds_per_fetcher": 3,
        "model_calls": 0, "forecast_scores": False, "bank_fit": False, "confirmation_opened": False,
        "source": {str(p.relative_to(OUT)): sha(p) for p in source.rglob("*.py")}})
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(region, REGIONS))
    save(OUT / "BATCH_COMPLETE.json", {"results": results, "all_regions_complete": all(r["complete"] for r in results)})
    print(json.dumps(results), flush=True)


if __name__ == "__main__":
    main()
