"""Qualify three registered full-month native joins after catalog acquisition."""

import argparse
import datetime as dt
import importlib.util
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def prepare(catalogs, out, repo):
    sample = read(catalogs / "SAMPLE_RESULT.json")
    if not sample["passed"] or len(sample["results"]) != 3:
        raise ValueError("All three original leap-month catalog samples must pass")
    out.mkdir(exist_ok=False)
    (out / "source").mkdir()
    units = []
    for row in sample["results"]:
        folder = out / row["unit"]
        folder.mkdir()
        original = catalogs / row["unit"]
        captures = Path(row["captures"])
        shutil.copytree(captures, folder / "catalogs")
        for name in ("CALENDAR.json", "SOURCE_NATIVE_PLAN.json"):
            shutil.copyfile(original / name, folder / name)
        plan = read(folder / "SOURCE_NATIVE_PLAN.json")
        if len(plan["requests"]) > 2500:
            raise ValueError("Frozen monthly request cap exceeded")
        publish(folder / "SOURCE_NATIVE_BOUNDED_PLAN.json", {**plan, "pause_seconds": 2,
            "parent_plan_sha256": digest(original / "SOURCE_NATIVE_PLAN.json")})
        publish(folder / "REUSED_CATALOG_PROVENANCE.json", {"directory": str(captures),
            "files": {p.name: digest(p) for p in captures.iterdir() if p.is_file()}})
        units.append(row["unit"])
    mapping = {"annual_native_sample.py": Path(__file__),
        "acquisition_helpers.py": catalogs / "source/acquisition_helpers.py",
        "fetch_public.py": catalogs / "source/fetch_public.py",
        "build_regional_stage_v1.py": repo / "plans/v7_adaptive_execution_20260913/build_regional.py",
        "build_native_v2.py": repo / "plans/v8_measurement_execution_20260913_01/scripts/build_native_v2.py"}
    for name, path in mapping.items():
        shutil.copyfile(path, out / "source" / name)
    for package in ("monitoring_v1", "monitoring_fixed_v1", "forecast_task"):
        shutil.copytree(repo / "disastertrace-starter/src/disastertrace" / package,
            out / "source/disastertrace" / package, ignore=shutil.ignore_patterns("__pycache__"))
    (out / "source/disastertrace/__init__.py").write_text('"""Frozen monthly data qualification."""\n')
    publish(out / "PLAN.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "units": units,
        "catalog_sample_sha256": digest(catalogs / "SAMPLE_RESULT.json"),
        "native_originals": sum(r["native_originals"] for r in sample["results"]),
        "exact_retries": 1, "parallel_fetchers": 3, "pause_seconds": 2,
        "expected_opportunities_per_threshold_per_region": 2088,
        "role": "2024 final-calibration source preparation only; no fitting or performance evaluation",
        "native_parser_failures": "retain as unavailable with original text, never silently drop native IDs",
        "model_calls": 0, "confirmation_opened": False,
        "files": {str(p.relative_to(out)): digest(p) for p in out.rglob("*") if p.is_file()}})


def run_unit(task):
    out, repo, name = task
    folder = out / name
    spec = importlib.util.spec_from_file_location("monthly_" + name, out / "source/acquisition_helpers.py")
    io = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(io)
    io.OUT, io.REPO, io.PYTHON = out, repo, sys.executable
    try:
        native = io.acquire(folder, folder / "SOURCE_NATIVE_BOUNDED_PLAN.json", "native")
        stage = folder / "dataset_stage_v1"
        io.run(folder, "decode", [sys.executable, str(out / "source/build_regional_stage_v1.py"),
            "--contract", str(folder / "CALENDAR.json"), "--metar", str(folder / "catalogs"),
            "--taf", str(native), "--source-root", str(folder), "--output", str(stage)])
        dataset = folder / "dataset_v2"
        io.run(folder, "native_contract", [sys.executable, str(out / "source/build_native_v2.py"),
            "--dataset", str(stage), "--source-root", str(folder), "--output", str(dataset)])
        opportunities = read(dataset / "public/OPPORTUNITIES.json")
        if len(opportunities) != 4176 or len({r["opportunity_id"] for r in opportunities}) != 4176:
            raise ValueError("Monthly UTC calendar opportunities incomplete")
        result = {"unit": name, "complete": True, "opportunities": len(opportunities),
            "dataset": str(dataset), "dataset_files": {str(p.relative_to(dataset)): digest(p)
                for p in dataset.rglob("*") if p.is_file()}, "fit_completed": False}
    except Exception as exc:  # noqa: BLE001 - preserve failed monthly units and continue independent regions.
        result = {"unit": name, "complete": False, "error": type(exc).__name__, "message": str(exc)}
    publish(folder / "RESULT.json", result)
    print({k: v for k, v in result.items() if k != "dataset_files"}, flush=True)
    return result


def execute(out, repo):
    publish(out / "LAUNCH_CLAIM.json", {"pid": os.getpid(), "model_calls": 0})
    plan = read(out / "PLAN.json")
    for name, sha in plan["files"].items():
        if digest(out / name) != sha:
            raise ValueError("Monthly native freeze changed")
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(key, None)
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(run_unit, [(out, repo, n) for n in plan["units"]]))
    passed = all(r["complete"] for r in rows)
    publish(out / "RESULT.json", {"passed": passed, "results": rows, "full_years_complete": False,
        "model_calls": 0, "fit_completed": False, "confirmation_opened": False})
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "execute"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--catalogs", type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args.catalogs.absolute(), args.out.absolute(), args.repo.absolute())
    else:
        execute(args.out.absolute(), args.repo.absolute())
