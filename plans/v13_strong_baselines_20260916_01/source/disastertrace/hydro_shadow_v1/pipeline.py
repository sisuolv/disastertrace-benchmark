"""Finite prospective capture with immutable registrations and actual disk receipts."""

import argparse
import os
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode

from .capture import capture_json, file_hash, stamp, strict_json, write_new
from .core import (
    POLICIES,
    content_hash,
    instant,
    nwps_points,
    predict,
    primary_contract,
    primary_points,
    settle,
    threshold_contract,
    utc,
)

MAX_BYTES = 4 * 1024 * 1024
REQUEST_SECONDS = 95


def make_registry(stations, snapshots, created_at):
    created = instant(created_at)
    if not 1 <= len(stations) <= 6 or len({s["lid"] for s in stations}) != len(stations):
        raise ValueError("one to six unique stations required")
    targets = []
    for station in stations:
        snapshot = snapshots[station["lid"]]
        if not station["admitted"] or instant(snapshot["captured_at"]) > created:
            raise ValueError("unqualified or unavailable initial station snapshot")
        used = set()
        for nominal in (6, 12, 24):
            candidates = [
                p
                for p in snapshot["forecast"]
                if p["valid_at"] not in used
                and abs((instant(p["valid_at"]) - created).total_seconds() / 3600 - nominal) <= 3
                and instant(p["valid_at"]) >= created + timedelta(hours=4)
                and instant(p["issued_at"]) <= instant(snapshot["captured_at"])
                and instant(p["generated_at"]) <= instant(snapshot["captured_at"])
                and created - instant(p["issued_at"]) <= timedelta(hours=36)
            ]
            if not candidates:
                raise ValueError(f"no lawful target in horizon bracket: {station['lid']} {nominal}")
            chosen = min(
                candidates,
                key=lambda p: (
                    abs((instant(p["valid_at"]) - created).total_seconds() / 3600 - nominal),
                    p["valid_at"],
                ),
            )
            used.add(chosen["valid_at"])
            targets.append(
                {
                    "id": f"h{len(targets) + 1:03d}",
                    "lid": station["lid"],
                    "valid_at": chosen["valid_at"],
                    "deadline": utc(instant(chosen["valid_at"]) - timedelta(hours=2)),
                    "threshold": station["threshold"],
                    "unit": "ft",
                    "reference": station["reference"],
                    "family": station["family"],
                    "spatial_group": station["spatial_group"],
                    "nominal_lead_hours": nominal,
                    "registration_lead_hours": (
                        instant(chosen["valid_at"]) - created
                    ).total_seconds()
                    / 3600,
                    "initial_value": chosen["value"],
                    "initial_snapshot_sha256": content_hash(snapshot),
                }
            )
    stop = max(instant(t["valid_at"]) for t in targets) + timedelta(hours=4)
    start = created + timedelta(seconds=10)
    schedule, at = [], start
    while at < stop:
        schedule.append(utc(at))
        at += timedelta(hours=2)
    schedule.append(utc(stop))
    requests = len(stations) * 4 * len(schedule)
    return {
        "schema": "disastertrace_hydro_shadow_v1",
        "created_at": utc(created),
        "origin": "prospective_program_shadow",
        "stations": stations,
        "targets": targets,
        "policies": list(POLICIES),
        "poll_at": schedule,
        "scheduled_stop_at": utc(stop),
        "hard_stop_at": utc(stop + timedelta(minutes=15)),
        "max_poll_lateness_seconds": 600,
        "max_request_seconds": REQUEST_SECONDS,
        "max_parallel_downloads": 4,
        "max_bytes_per_response": MAX_BYTES,
        "max_logical_downloads": requests,
        "max_body_bytes": requests * (MAX_BYTES + 1),
        "automatic_retries": 0,
        "model_calls": 0,
        "gpu_jobs": 0,
        "expected_target_policy_results": len(targets) * len(POLICIES),
        "outcome_policy": "exact instant; strict provider QC; provisional separately labelled",
        "submission_policy": "last on-disk receipt before target minus two hours; missing retained",
        "failed_poll_policy": "no retry or backdating; preserve missing slots and earlier commits",
        "outcome_revision_policy": "append each poll settlement; no best-outcome selection or silent overwrite",
        "sampling": "input-risk-stratified pilot, not representative incidence or independent events",
        "probabilities": False,
        "human_item_review": False,
        "gee": False,
    }


def provider_urls(station, now):
    begin = instant(now) - timedelta(hours=48)
    lid, source = station["lid"], station["source_station"]
    urls = {
        "metadata": f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}",
        "stageflow": f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}/stageflow",
    }
    if station["provider"] == "usgs":
        base = "https://api.waterdata.usgs.gov/ogcapi/v1/collections/"
        urls["site"] = base + f"monitoring-locations/items/USGS-{source}?f=json"
        urls["primary"] = (
            base
            + "continuous/items?"
            + urlencode(
                {
                    "f": "json",
                    "monitoring_location_id": "USGS-" + source,
                    "parameter_code": station["parameter"],
                    "datetime": utc(begin) + "/" + utc(now),
                    "limit": 1000,
                }
            )
        )
    else:
        urls["site"] = (
            "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/"
            + source
            + ".json?expand=details,datums&units=english"
        )
        urls["primary"] = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?" + urlencode(
            {
                "product": "water_level",
                "station": source,
                "datum": "MLLW",
                "units": "english",
                "time_zone": "gmt",
                "begin_date": begin.strftime("%Y%m%d %H:%M"),
                "end_date": instant(now).strftime("%Y%m%d %H:%M"),
                "format": "json",
            }
        )
    return urls


def supervised_capture(url, destination):
    """The parent bounds DNS/connect/read hangs as well as body size in the child."""
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError("capture opportunity already consumed: " + str(destination))
    started = stamp()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "disastertrace.hydro_shadow_v1.pipeline",
            "capture",
            "--url",
            url,
            "--out",
            str(destination),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    timed_out = False
    try:
        _, stderr = proc.communicate(timeout=REQUEST_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        _, stderr = proc.communicate()
    destination.mkdir(parents=True, exist_ok=True)
    raw, receipt_path = destination / "response.raw", destination / "RECEIPT.json"
    if not receipt_path.exists():
        write_new(
            receipt_path,
            {
                "url": url,
                "started_at": started,
                "finished_at": stamp(),
                "status": "failed",
                "complete": False,
                "http_status": None,
                "error": "parent_timeout" if timed_out else "capture_child_failed",
                "bytes": raw.stat().st_size if raw.exists() else 0,
                "sha256": file_hash(raw) if raw.exists() else None,
                "automatic_retries": 0,
            },
        )
    write_new(
        destination / "SUPERVISION.json",
        {
            "started_at": started,
            "finished_at": stamp(),
            "exit_code": proc.returncode,
            "timed_out": timed_out,
            "stderr": stderr.decode(errors="replace")[:4000],
        },
    )
    receipt = strict_json(receipt_path.read_bytes())
    if receipt["status"] != "received" or timed_out or proc.returncode != 0:
        return None, receipt
    if receipt["sha256"] != file_hash(raw) or receipt["bytes"] != raw.stat().st_size:
        raise ValueError("captured bytes fail receipt verification")
    return strict_json(raw.read_bytes()), receipt


def normalize_cycle(station, payloads, receipts):
    """A forecast failure need not prevent settling an eligible primary measurement."""
    problems = []
    if payloads.get("metadata") is None or payloads.get("site") is None:
        return None, ["missing metadata; datum and station identity cannot be checked"]
    metadata, site = payloads["metadata"], payloads["site"]
    if metadata["lid"] != station["lid"]:
        return None, ["NWPS station identity changed"]
    source = primary_contract(metadata, site, station["parameter"], station["provider"])
    if content_hash(source) != station["primary_contract_hash"]:
        return None, ["primary datum/identity contract changed"]
    if content_hash(threshold_contract(metadata)) != station["contract_hash"]:
        return None, ["threshold/reference contract changed"]
    forecasts, observations = [], []
    if payloads.get("stageflow") is not None:
        try:
            forecasts, excluded = nwps_points(
                payloads["stageflow"],
                "forecast",
                receipts["stageflow"]["finished_at"],
                station["variable"],
            )
            if excluded:
                problems.append({"excluded_forecast": excluded})
        except (ValueError, KeyError, TypeError) as exc:
            problems.append("forecast unavailable: " + str(exc))
    else:
        problems.append("forecast capture failed")
    if payloads.get("primary") is not None:
        observations, excluded = primary_points(
            payloads["primary"], source, receipts["primary"]["finished_at"]
        )
        if excluded:
            problems.append({"excluded_primary": excluded})
    else:
        problems.append("primary capture failed")
    times = {k: r["finished_at"] for k, r in receipts.items()}
    return {
        "lid": station["lid"],
        "captured_at": utc(max(times.values(), key=instant)),
        "source_received_at": times,
        "forecast": forecasts,
        "observations": observations,
    }, problems


def save_submissions(directory, submissions):
    path = directory / "SUBMISSIONS.json"
    write_new(path, submissions)
    write_new(
        directory / "SUBMISSION_RECEIPT.json",
        {
            "persisted_at": stamp(),
            "sha256": file_hash(path),
            "count": len(submissions),
        },
    )


def load_commits(run):
    commits = []
    for receipt_path in sorted(run.glob("*/SUBMISSION_RECEIPT.json")):
        receipt = strict_json(receipt_path.read_bytes())
        path = receipt_path.with_name("SUBMISSIONS.json")
        if file_hash(path) != receipt["sha256"]:
            raise ValueError("submission digest mismatch")
        for row in strict_json(path.read_bytes()):
            if instant(row["committed_at"]) > instant(receipt["persisted_at"]):
                raise ValueError("submission clock moved backwards")
            commits.append(
                {**row, "prepared_at": row["committed_at"], "committed_at": receipt["persisted_at"]}
            )
    return commits


def update_progress(run, value):
    temporary = run / f".progress-{os.getpid()}-{time.time_ns()}.json"
    write_new(temporary, value)
    os.replace(temporary, run / "PROGRESS.json")


def score_summary(registry, settlements):
    by_id = {s["target_id"]: s for s in settlements}
    rows = []
    for family in sorted({t["family"] for t in registry["targets"]}):
        results = [by_id[t["id"]] for t in registry["targets"] if t["family"] == family]
        settled = [r for r in results if r["status"].startswith("settled_")]
        for policy in POLICIES:
            scores = [
                r["policies"][policy]
                for r in settled
                if r["policies"][policy]["status"] == "scored"
            ]
            rows.append(
                {
                    "family": family,
                    "policy": policy,
                    "registered_targets": len(results),
                    "settled_targets": len(settled),
                    "scored_targets": len(scores),
                    "missing_predictions": len(settled) - len(scores),
                    "unresolved_targets": len(results) - len(settled),
                    "settled_positive_targets": sum(r["binary_outcome"] for r in settled),
                    "quality_counts": dict(Counter(r["status"] for r in settled)),
                    "mae_ft_on_scored_targets": sum(s["absolute_error"] for s in scores)
                    / len(scores)
                    if scores
                    else None,
                    "point_threshold_errors": sum(s["point_threshold_error"] for s in scores),
                }
            )
    return {
        "origin": registry["origin"],
        "registered_target_policy_results": registry["expected_target_policy_results"],
        "rows": rows,
        "interpretation": "descriptive program baseline diagnostics; no calibrated probabilities or model results",
    }


def verify_freeze(root):
    manifest = strict_json((root / "FREEZE.json").read_bytes())
    for name, digest in manifest["files"].items():
        if file_hash(root / name) != digest:
            raise ValueError("frozen file changed: " + name)
    return manifest


def worker(root):
    root = Path(root).resolve()
    verify_freeze(root)
    registry = strict_json((root / "REGISTRY.json").read_bytes())
    run = root / "run"
    run.mkdir(exist_ok=False)
    write_new(
        run / "CLAIM.json",
        {
            "started_at": stamp(),
            "pid": os.getpid(),
            "registry_sha256": file_hash(root / "REGISTRY.json"),
        },
    )
    if (
        not instant(registry["created_at"])
        <= instant(stamp())
        < instant(registry["poll_at"][0]) + timedelta(minutes=10)
    ):
        raise ValueError("initial launch outside registered start window; claim remains consumed")
    initial = run / "initial"
    initial.mkdir()
    snapshots = {
        s["lid"]: strict_json((root / "initial" / f"{s['lid']}.json").read_bytes())
        for s in registry["stations"]
    }
    submissions = []
    for target in registry["targets"]:
        submissions.extend(
            predict(snapshots[target["lid"]], target, stamp(), target["initial_value"])
        )
    save_submissions(initial, submissions)
    count_requests, count_bytes, completed_polls, missed_polls = 0, 0, 0, 0
    initial_state = {
        "state": "started",
        "updated_at": stamp(),
        "pid": os.getpid(),
        "initial_predictions": len(submissions),
        "completed_polls": 0,
        "logical_downloads": 0,
        "body_bytes": 0,
        "pending_targets": len(registry["targets"]),
    }
    update_progress(run, initial_state)
    for index, scheduled in enumerate(registry["poll_at"]):
        while instant(stamp()) < instant(scheduled):
            time.sleep(max(0, min(30, (instant(scheduled) - instant(stamp())).total_seconds())))
        verify_freeze(root)
        cycle = run / f"cycle_{index:03d}"
        cycle.mkdir()
        now = stamp()
        if (instant(now) - instant(scheduled)).total_seconds() > registry[
            "max_poll_lateness_seconds"
        ]:
            write_new(
                cycle / "MISSED.json",
                {
                    "scheduled_at": scheduled,
                    "checked_at": now,
                    "reason": "missed fixed poll; no replay or retry",
                },
            )
            missed_polls += 1
            continue
        if instant(now) >= instant(registry["hard_stop_at"]):
            break
        jobs = [
            (s["lid"], role, url)
            for s in registry["stations"]
            for role, url in provider_urls(s, now).items()
        ]
        count_requests += len(jobs)
        if count_requests > registry["max_logical_downloads"]:
            raise ValueError("registered download cap exceeded")
        write_new(
            cycle / "OPPORTUNITIES.json",
            {"scheduled_at": scheduled, "started_at": now, "requests": jobs},
        )

        def fetch(job, cycle=cycle):
            lid, role, url = job
            return supervised_capture(url, cycle / "captures" / lid / role)

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(fetch, jobs))
        payloads, receipts = {}, {}
        for (lid, role, _), (body, receipt) in zip(jobs, results):
            payloads.setdefault(lid, {})[role] = body
            receipts.setdefault(lid, {})[role] = receipt
            count_bytes += receipt["bytes"]
        if count_bytes > registry["max_body_bytes"] or instant(stamp()) > instant(
            registry["hard_stop_at"]
        ):
            raise ValueError("registered body/time cap exceeded")
        (cycle / "snapshots").mkdir()
        submissions, diagnostics, cycle_snapshots = [], [], {}
        for station in registry["stations"]:
            lid = station["lid"]
            try:
                snapshot, problems = normalize_cycle(station, payloads[lid], receipts[lid])
            except (ValueError, KeyError, TypeError) as exc:
                snapshot, problems = None, [type(exc).__name__ + ": " + str(exc)]
            diagnostics.append({"lid": lid, "quarantined": snapshot is None, "problems": problems})
            if snapshot is None:
                continue
            cycle_snapshots[lid] = snapshot
            write_new(cycle / "snapshots" / f"{lid}.json", snapshot)
            for target in registry["targets"]:
                if target["lid"] == lid and instant(stamp()) <= instant(target["deadline"]):
                    submissions.extend(predict(snapshot, target, stamp(), target["initial_value"]))
        write_new(cycle / "DIAGNOSTICS.json", diagnostics)
        save_submissions(cycle, submissions)
        commits, checked = load_commits(run), stamp()
        settlements = [
            settle(t, commits, cycle_snapshots.get(t["lid"], {}).get("observations", []), checked)
            for t in registry["targets"]
        ]
        write_new(cycle / "SETTLEMENTS.json", settlements)
        write_new(cycle / "SUMMARY.json", score_summary(registry, settlements))
        completed_polls += 1
        completed = {
            "state": "running",
            "updated_at": stamp(),
            "pid": os.getpid(),
            "completed_polls": completed_polls,
            "missed_polls": missed_polls,
            "last_cycle": cycle.name,
            "logical_downloads": count_requests,
            "body_bytes": count_bytes,
            "initial_predictions": initial_state["initial_predictions"],
            "latest_target_status_counts": dict(Counter(s["status"] for s in settlements)),
            "latest_quarantined_stations": sum(d["quarantined"] for d in diagnostics),
            "next_poll_at": registry["poll_at"][index + 1]
            if index + 1 < len(registry["poll_at"])
            else None,
            "scheduled_stop_at": registry["scheduled_stop_at"],
        }
        write_new(cycle / "COMPLETE.json", completed)
        update_progress(run, completed)
        print(
            f"{stamp()} completed {cycle.name} requests={count_requests} predictions={len(submissions)}",
            flush=True,
        )
    final = strict_json((run / "PROGRESS.json").read_bytes())
    final.update(
        state="finished_bounded_collection",
        updated_at=stamp(),
        next_poll_at=None,
        missed_polls=missed_polls,
        completed_polls=completed_polls,
    )
    write_new(run / "FINISHED.json", final)
    update_progress(run, final)


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("capture")
    fetch.add_argument("--url", required=True)
    fetch.add_argument("--out", type=Path, required=True)
    run = commands.add_parser("worker")
    run.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "capture":
        capture_json(args.url, args.out, MAX_BYTES)
    else:
        try:
            worker(args.root)
            with (args.root / "run/FINAL_AUDIT.log").open("xb") as log:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(args.root / "verify_shadow.py"),
                        "--root",
                        str(args.root),
                        "--out",
                        str(args.root / "run/FINAL_AUDIT.json"),
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=180,
                    check=False,
                )
            if result.returncode:
                raise ValueError("final independent audit failed; inspect FINAL_AUDIT.log")
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
            path = args.root / "run" / "FAILED.json"
            if path.parent.exists() and not path.exists():
                write_new(path, {"at": stamp(), "error": type(exc).__name__ + ": " + str(exc)})
            raise


if __name__ == "__main__":
    main()
