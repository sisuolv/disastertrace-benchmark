"""Acquire four preselected seasonal development weeks; confirmation stays closed."""

import argparse
import datetime as dt
import importlib.util
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from disastertrace.monitoring_v1.spool_backend import digest, publish, read

REGIONS = {
    "new_york": ["KJFK", "KLGA", "KEWR"],
    "chicago": ["KORD", "KMDW", "KRFD"],
    "denver": ["KDEN", "KBJC", "KAPA"],
}
WEEKS = ("2025-03-03", "2025-06-02", "2025-09-01", "2025-12-01")


def prepare(out, root):
    out.mkdir(exist_ok=False)
    source = out / "source"
    source.mkdir()
    previous = root / "plans/v7_adaptive_execution_20260913"
    template = read(previous / "DEVELOPMENT_CALENDAR.json")
    original = read(previous / "SOURCE_CATALOG_PLAN.json")
    units = []
    for week in WEEKS:
        start = dt.date.fromisoformat(week)
        end = start + dt.timedelta(days=7)
        lower, upper = start - dt.timedelta(days=2), end + dt.timedelta(days=1)
        for region, stations in REGIONS.items():
            name = region + "__" + week
            folder = out / name
            folder.mkdir()
            calendar = {
                **template,
                "stations": stations,
                "lead_hours": [1],
                "cutoff_start": week + "T00:00:00Z",
                "cutoff_end_exclusive": end.isoformat() + "T00:00:00Z",
                "opportunities_per_threshold": 504,
                "stage": "seasonal_development_only",
                "date_selection": "first complete Monday-Sunday weeks in March/June/September/December2025; no labels or performance used",
                "preregistered_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "baseline_mapping": "frozen December2024 banks; seasonal transfer is developmental",
                "image_admission": "none",
                "confirmation_opened": False,
            }
            publish(folder / "CALENDAR.json", calendar)
            requests = []
            for station in stations:
                for prior in original["requests"][:2]:
                    parts = urlsplit(prior["url"])
                    parameters = dict(parse_qsl(parts.query))
                    metar = prior["id"].startswith("metar")
                    parameters.update(
                        station=station[1:] if metar else station,
                        year1=str(lower.year),
                        month1=str(lower.month),
                        day1=str(lower.day),
                        year2=str(upper.year),
                        month2=str(upper.month),
                        day2=str(upper.day),
                    )
                    requests.append(
                        {
                            **prior,
                            "id": ("metar-routine-" if metar else "taf-catalog-")
                            + station,
                            "url": urlunsplit(
                                (
                                    parts.scheme,
                                    parts.netloc,
                                    parts.path,
                                    urlencode(parameters),
                                    "",
                                )
                            ),
                            "max_bytes": 8_000_000,
                            "timeout": 90,
                        }
                    )
            publish(
                folder / "SOURCE_CATALOG_PLAN.json",
                {
                    **original,
                    "requests": requests,
                    "registered_at": calendar["preregistered_at"],
                    "calendar_sha256": digest(folder / "CALENDAR.json"),
                    "limits": {"requests": 6, "bytes": 48_000_006},
                    "pause_seconds": 2,
                },
            )
            units.append(name)
    mapping = {
        "acquisition_helpers.py": root
        / "plans/v8_measurement_execution_20260913_01/scripts/extend_regional_calendars.py",
        "fetch_public.py": root / "plans/v7_review_execution_20260912/fetch_public.py",
        "prepare_native_fetch.py": root
        / "plans/v7_review_execution_20260912/prepare_native_fetch.py",
        "build_regional_stage_v1.py": previous / "build_regional.py",
        "build_native_v2.py": root
        / "plans/v8_measurement_execution_20260913_01/scripts/build_native_v2.py",
        "acquire_seasonal_development.py": Path(__file__),
    }
    for name, path in mapping.items():
        shutil.copyfile(path, source / name)
    for package in ("monitoring_v1", "monitoring_fixed_v1", "forecast_task"):
        shutil.copytree(
            root / "disastertrace-starter/src/disastertrace" / package,
            source / "disastertrace" / package,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (source / "disastertrace/__init__.py").write_text(
        '"""Frozen seasonal native data acquisition."""\n'
    )
    publish(
        out / "PLAN.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "units": units,
            "regions": REGIONS,
            "weeks": list(WEEKS),
            "opportunities": 12096,
            "parallel_fetchers": 6,
            "max_native_originals_per_unit": 500,
            "exact_retries": 1,
            "native_pause_seconds": 2,
            "global_calendar_blocks": 4,
            "independent_synoptic_processes_not_established": True,
            "retained_confirmation": "Bay2025-02-17..23 is unopened and not requested",
            "model_calls": 0,
            "new_model_training": False,
            "files": {
                str(p.relative_to(out)): digest(p)
                for p in out.rglob("*")
                if p.is_file()
            },
        },
    )


def acquire_unit(pair):
    out, root, name = pair
    folder = out / name
    spec = importlib.util.spec_from_file_location(
        "seasonal_io_" + name, out / "source/acquisition_helpers.py"
    )
    io = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(io)
    io.OUT, io.REPO = out, root
    io.PYTHON = str(root / "disastertrace-starter/.venv/bin/python")
    try:
        catalogs = io.acquire(folder, folder / "SOURCE_CATALOG_PLAN.json", "catalogs")
        native_plan = folder / "SOURCE_NATIVE_PLAN.json"
        io.run(
            folder,
            "prepare_native",
            [
                io.PYTHON,
                str(out / "source/prepare_native_fetch.py"),
                "--catalogs",
                str(catalogs),
                "--output",
                str(native_plan),
            ],
        )
        plan = read(native_plan)
        if len(plan["requests"]) > 500:
            raise ValueError("Registered source ceiling exceeded")
        bounded = folder / "SOURCE_NATIVE_BOUNDED_PLAN.json"
        publish(
            bounded,
            {**plan, "pause_seconds": 2, "parent_plan_sha256": digest(native_plan)},
        )
        native = io.acquire(folder, bounded, "native")
        stage = folder / "dataset_stage_v1"
        io.run(
            folder,
            "decode",
            [
                io.PYTHON,
                str(out / "source/build_regional_stage_v1.py"),
                "--contract",
                str(folder / "CALENDAR.json"),
                "--metar",
                str(catalogs),
                "--taf",
                str(native),
                "--source-root",
                str(folder),
                "--output",
                str(stage),
            ],
        )
        io.run(
            folder,
            "native_contract",
            [
                io.PYTHON,
                str(out / "source/build_native_v2.py"),
                "--dataset",
                str(stage),
                "--source-root",
                str(folder),
                "--output",
                str(folder / "dataset_v2"),
            ],
        )
        result = {
            "unit": name,
            "complete": True,
            "native_requests": len(plan["requests"]),
            "native_data_decoded": True,
            "model_calls": 0,
        }
    except Exception as exc:  # noqa: BLE001 - each failed source unit remains separate; other units continue.
        result = {
            "unit": name,
            "complete": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    publish(folder / "RESULT.json", result)
    print(result, flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    out, root = args.out.absolute(), args.repo.absolute()
    if not args.execute:
        prepare(out, root)
        return
    publish(
        out / "LAUNCH_CLAIM.json",
        {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "pid": os.getpid()},
    )
    plan = read(out / "PLAN.json")
    for path, sha in plan["files"].items():
        if digest(out / path) != sha:
            raise ValueError("Frozen seasonal source contract changed")
    for key in (
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
    ):
        os.environ.pop(key, None)
    with ThreadPoolExecutor(max_workers=plan["parallel_fetchers"]) as pool:
        results = list(
            pool.map(acquire_unit, [(out, root, name) for name in plan["units"]])
        )
    publish(
        out / "COMPLETE.json",
        {
            "all_complete": all(r["complete"] for r in results),
            "units": results,
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "confirmation_opened": False,
        },
    )
    if not all(r["complete"] for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
