"""Account for requested and running GPUs from saved ACP metadata, without dispatch."""

import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from disastertrace.forecast_task.common import digest, fingerprint, read, strict_json, write

TERMINAL = {"SUCCEEDED", "FAILED", "DELETED", "SUSPENDED"}


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def timeline(intervals, beginning, ending):
    changes = defaultdict(int)
    changes[beginning] = changes[ending] = 0
    for start, stop, count in intervals:
        start, stop = max(beginning, start), min(ending, stop)
        if stop <= start:
            continue
        changes[start] += count
        changes[stop] -= count
    current, maximum, seconds, rows = 0, 0, 0.0, []
    times = sorted(changes)
    for left, right in zip(times, times[1:]):
        current += changes[left]
        if current < 0:
            raise ValueError("negative GPU occupancy")
        elapsed = (right - left).total_seconds()
        maximum = max(maximum, current)
        seconds += current * elapsed
        rows.append({"start": left.isoformat(), "end": right.isoformat(), "gpus": current, "seconds": elapsed})
    return {"maximum_concurrent_gpus": maximum, "gpu_hours": seconds / 3600, "intervals": rows}


def account(window, snapshot):
    if snapshot["exit_code"] != 0:
        raise ValueError("ACP snapshot query failed")
    jobs = [] if snapshot["stdout"].strip() == "No jobs found" else strict_json(snapshot["stdout"])
    if len(jobs) >= 100 or len({j["name"] for j in jobs}) != len(jobs):
        raise ValueError("paginated or duplicate job snapshot")
    beginning, deadline = stamp(window["received_at"]), stamp(window["autonomous_work_deadline"])
    observed = stamp(snapshot["at"])
    if observed < beginning:
        raise ValueError("snapshot precedes the authorized window")
    ending = min(deadline, observed)
    reserved, running, records, excluded, unfinished = [], [], [], [], []
    for job in jobs:
        created = stamp(job["create_time"])
        complete = stamp(job["complete_time"]) if job.get("complete_time") else None
        terminal = job["state"] in TERMINAL
        if created > observed or complete is not None and complete < created:
            raise ValueError("inconsistent ACP lifecycle timestamps")
        if created >= deadline or complete is not None and complete <= beginning:
            continue
        if terminal and complete is None:
            # Some old smoke-job metadata lacks complete_time; only exclude it if its
            # last terminal metadata update demonstrably predates this entire window.
            if stamp(job["update_time"]) < beginning:
                excluded.append({"job_id": job["name"], "reason": "terminal_metadata_predates_window_without_complete_time"})
                continue
            raise ValueError("terminal in-window job lacks a completion time")
        count = 0
        for role in job["roles"]:
            if len(role["resource_spec"]) != 1:
                raise ValueError("heterogeneous allocation requires explicit accounting")
            spec = role["resource_spec"][0]
            replicas = max(1, role["total_replicas"], spec["replicas"])
            count += replicas * max(int(spec["requests"].get("nvidia.com/gpu", "0")),
                                    int(spec["limits"].get("nvidia.com/gpu", "0")))
        if count <= 0:
            raise ValueError("in-window job is missing GPU allocation metadata")
        end = complete or observed
        reserved.append((created, end, count))
        start = stamp(job["start_time"]) if job.get("start_time") else None
        if start is not None:
            if start < created or start > end:
                raise ValueError("inconsistent ACP start time")
            running.append((start, end, count))
        if not terminal:
            unfinished.append(job["name"])
        records.append({"job_id": job["name"], "display_name": job["display_name"], "state": job["state"],
                        "gpus": count, "create_time": job["create_time"], "start_time": job.get("start_time"),
                        "complete_time": job.get("complete_time"), "terminal": terminal,
                        "completion_after_window": complete is not None and complete > deadline})
    reservation, allocation = timeline(reserved, beginning, ending), timeline(running, beginning, ending)
    result = {
        "schema_version": "autonomy_gpu_window_accounting_v1",
        "window_start": beginning.isoformat(), "window_deadline": deadline.isoformat(),
        "observed_at": observed.isoformat(), "accounted_through": ending.isoformat(),
        "reserved_including_pending": reservation, "running_allocation": allocation,
        "within_four_gpu_cap": reservation["maximum_concurrent_gpus"] <= window["max_parallel_h100"],
        "all_observed_jobs_released": not unfinished, "unfinished_job_ids": unfinished,
        "jobs": sorted(records, key=lambda r: (r["create_time"], r["job_id"])),
        "excluded_old_terminal_metadata": excluded,
        "snapshot_is_current_at_observation_only": True,
        "running_time_is_allocation_not_device_utilization": True,
        "reservation_time_is_not_a_billing_claim": True, "model_calls": 0,
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = account(read(args.window), read(args.snapshot))
    result.update(window_sha256=digest(args.window), snapshot_sha256=digest(args.snapshot), script_sha256=digest(__file__))
    result["analysis_id"] = fingerprint(result)
    if args.verify:
        if result != read(args.output):
            raise ValueError("saved resource accounting differs")
    else:
        write(args.output, result)
    print({k: v for k, v in result.items() if k not in {"jobs", "reserved_including_pending", "running_allocation"}}, flush=True)
    if not result["within_four_gpu_cap"]:
        raise SystemExit(1)
