"""Acquire the fixed 2023/2024 station-month inventory before native expansion."""

import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REGIONS = {"new_york": ["KJFK", "KLGA", "KEWR"],
           "chicago": ["KORD", "KMDW", "KRFD"], "denver": ["KDEN", "KBJC", "KAPA"]}


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def month_bounds(year, month):
    start = dt.date(year, month, 1)
    end = dt.date(year + (month == 12), month % 12 + 1, 1)
    return start, end


def prepare(out, repo):
    out.mkdir(exist_ok=False)
    (out / "source").mkdir()
    prior = repo / "plans/v7_adaptive_execution_20260913"
    template = read(prior / "SOURCE_CATALOG_PLAN.json")
    calendar = read(prior / "DEVELOPMENT_CALENDAR.json")
    units, logical = [], []
    for year in (2023, 2024):
        for month in range(1, 13):
            start, end = month_bounds(year, month)
            lower, upper = start - dt.timedelta(days=2), end + dt.timedelta(days=1)
            for region, stations in REGIONS.items():
                name = f"{region}__{year}-{month:02d}"
                folder = out / name
                folder.mkdir()
                role = "fit_internal_selection" if year == 2023 else "final_calibration"
                card = {**calendar, "stations": stations, "lead_hours": [1],
                    "cutoff_start": str(start) + "T00:00:00Z",
                    "cutoff_end_exclusive": str(end) + "T00:00:00Z",
                    "opportunities_per_threshold": (end-start).days * 24 * 3,
                    "stage": "annual_source_acquisition_only", "role": role,
                    "baseline_mapping": "not fitted; separate purged role admission required",
                    "confirmation_opened": False, "image_admission": "none",
                    "date_selection": "complete preselected 2023/2024 months; no outcome filtering",
                    "padding_role": "capture only; full source/reference footprints must be purged at role boundaries"}
                write(folder / "CALENDAR.json", card)
                requests = []
                for station in stations:
                    for old in template["requests"][:2]:
                        metar = old["id"].startswith("metar")
                        parts = urlsplit(old["url"])
                        query = dict(parse_qsl(parts.query))
                        query.update(station=station[1:] if metar else station,
                            year1=str(lower.year), month1=str(lower.month), day1=str(lower.day),
                            year2=str(upper.year), month2=str(upper.month), day2=str(upper.day))
                        ident = ("metar-routine-" if metar else "taf-catalog-") + station
                        requests.append({**old, "id": ident,
                            "url": urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), "")),
                            "max_bytes": 8_000_000, "timeout": 90})
                        logical.append({"unit": name, "station": station,
                            "product": "METAR" if metar else "TAF_catalog", "role": role,
                            "request_id": ident, "cache_status": "no_exact_monthly_capture_verified"})
                write(folder / "SOURCE_CATALOG_PLAN.json", {**template, "requests": requests,
                    "registered_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "calendar_sha256": digest(folder / "CALENDAR.json"),
                    "limits": {"requests": 6, "bytes": 48_000_006}, "pause_seconds": 2})
                units.append(name)
    mapping = {"annual_catalogs.py": Path(__file__),
        "acquisition_helpers.py": repo / "plans/v8_measurement_execution_20260913_01/scripts/extend_regional_calendars.py",
        "fetch_public.py": repo / "plans/v7_review_execution_20260912/fetch_public.py",
        "prepare_native_fetch.py": repo / "plans/v7_review_execution_20260912/prepare_native_fetch.py"}
    for name, path in mapping.items():
        shutil.copyfile(path, out / "source" / name)
    write(out / "LOGICAL_SLICES.json", logical)
    write(out / "PLAN.json", {"units": units, "logical_slices": len(logical),
        "sample_units": [r + "__2024-02" for r in REGIONS],
        "sample_basis": "all three registered regions in the leap month; fixed before HTTP",
        "parallel_fetchers": 3, "exact_retries": 1, "max_catalog_attempts": 864,
        "max_body_bytes_all_attempts": 864 * 8_000_001,
        "native_expansion": "enumerate only; no full TAF body acquisition in this scope",
        "native_originals_ceiling_per_region_month": 2500,
        "model_calls": 0, "fit_completed": False, "confirmation_opened": False,
        "cache_scope": "existing weekly captures are not proof of complete monthly coverage",
        "files": {str(p.relative_to(out)): digest(p) for p in out.rglob("*") if p.is_file()}})


def acquire_unit(task):
    out, repo, name = task
    folder = out / name
    spec = importlib.util.spec_from_file_location("acquire_" + name, out / "source/acquisition_helpers.py")
    io = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(io)
    io.OUT, io.REPO, io.PYTHON = out, repo, sys.executable

    def bounded_run(directory, label, command):
        write(directory / (label + ".command.json"), {"command": command, "timeout_seconds": 900})
        with (directory / (label + ".log")).open("x") as log:
            try:
                result = subprocess.run(command, cwd=repo, stdout=log, stderr=subprocess.STDOUT,
                                        timeout=900, check=False)
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = 124
        write(directory / (label + ".exit.json"), {"exit_code": code})
        if code:
            raise RuntimeError("Bounded stage failed: " + label)

    io.run = bounded_run
    try:
        captures = io.acquire(folder, folder / "SOURCE_CATALOG_PLAN.json", "catalogs")
        manifest = read(captures / "MANIFEST.json")
        inventory = []
        for receipt in manifest["rows"]:
            body = captures / receipt["body_file"]
            if digest(body) != receipt["sha256"] or receipt["http_status"] != 200:
                raise ValueError("Catalog body identity/HTTP mismatch")
            table = csv.DictReader(body.read_text().splitlines())
            metar = receipt["id"].startswith("metar")
            required = {"station", "valid", "metar"} if metar else {"station", "valid", "product_id"}
            if not required <= set(table.fieldnames or []):
                raise ValueError("Missing native catalog columns: " + receipt["id"])
            rows = list(table)
            if not rows:
                raise ValueError("Empty station month: " + receipt["id"])
            inventory.append({"id": receipt["id"], "rows": len(rows), "bytes": body.stat().st_size,
                "body_sha256": digest(body), "min_time": min(r["valid"] for r in rows),
                "max_time": max(r["valid"] for r in rows)})
        native = folder / "SOURCE_NATIVE_PLAN.json"
        bounded_run(folder, "native_inventory", [sys.executable, str(out / "source/prepare_native_fetch.py"),
            "--catalogs", str(captures), "--output", str(native)])
        count = len(read(native)["requests"])
        if count > 2500:
            raise ValueError("Registered monthly native ceiling exceeded")
        result = {"unit": name, "complete": True, "logical_slices": len(inventory),
            "captures": str(captures), "inventory": inventory, "native_originals": count,
            "native_bodies_downloaded": False, "task_join_validated": False, "fit_completed": False}
    except Exception as exc:  # noqa: BLE001 - keep all failures without replacing monthly units.
        result = {"unit": name, "complete": False, "error": type(exc).__name__, "message": str(exc)}
    write(folder / "RESULT.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "inventory"}), flush=True)
    return result


def execute(out, repo):
    write(out / "LAUNCH_CLAIM.json", {"pid": os.getpid(), "at": dt.datetime.now(dt.timezone.utc).isoformat()})
    plan = read(out / "PLAN.json")
    for name, expected in plan["files"].items():
        if digest(out / name) != expected:
            raise ValueError("Frozen annual source or scope changed")
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(key, None)
    with ThreadPoolExecutor(max_workers=3) as pool:
        sample = list(pool.map(acquire_unit, [(out, repo, n) for n in plan["sample_units"]]))
        sample_ok = all(r["complete"] for r in sample)
        write(out / "SAMPLE_RESULT.json", {"passed": sample_ok, "results": sample})
        rest = [n for n in plan["units"] if n not in plan["sample_units"]]
        results = sample + (list(pool.map(acquire_unit, [(out, repo, n) for n in rest])) if sample_ok else sample)
    passed = len(results) == len(plan["units"]) and all(r["complete"] for r in results)
    write(out / "RESULT.json", {"passed": passed, "expected_units": 72,
        "completed_units": sum(r["complete"] for r in results), "results": results,
        "not_attempted": sorted(set(plan["units"]) - {r["unit"] for r in results}),
        "full_native_download_complete": False, "annual_fit_complete": False,
        "confirmation_opened": False, "model_calls": 0})
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "execute"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    (prepare if args.mode == "prepare" else execute)(args.out.absolute(), args.repo.absolute())
