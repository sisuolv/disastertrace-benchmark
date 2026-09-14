"""Inventory only this run's submitted jobs and verify terminal/resource receipts."""

import argparse
import datetime as dt
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TERMINAL = {"SUCCEEDED", "FAILED", "CANCELED", "CANCELLED", "STOPPED"}


def seconds(stamp):
    return dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--require-terminal", action="store_true")
    args = parser.parse_args()
    run, out = args.run.absolute(), args.out.absolute()
    out.mkdir(exist_ok=False)
    paths = set((run / "runtime").glob("*/JOB.json"))
    paths.update(run.glob("*/gpu/submission_*/JOB.json"))
    paths.update(run.glob("*/submission_*/JOB.json"))
    jobs = {}
    for path in sorted(paths):
        record = json.loads(path.read_text())
        job = record["job_id"]
        if job in jobs:
            raise ValueError("Duplicate submitted job identity")
        jobs[job] = {
            "record": record,
            "job_receipt": str(path.relative_to(run)),
            "job_receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def describe(job):
        command = [
            "/mnt/afs/260010168/bin/sco",
            "acp",
            "jobs",
            "describe",
            "--workspace-name=share-space",
            "--format=json",
            job,
        ]
        response = subprocess.run(
            command, capture_output=True, text=True, timeout=45, check=False
        )
        if response.returncode:
            return job, {"lookup_passed": False, "returncode": response.returncode}
        state = json.loads(response.stdout)
        (out / (job + ".json")).write_text(json.dumps(state, indent=2) + "\n")
        return job, state

    with ThreadPoolExecutor(max_workers=4) as pool:
        observed = dict(pool.map(describe, jobs))
    now = dt.datetime.now(dt.timezone.utc)
    reservations, allocations, records = [], [], []
    for job, original in jobs.items():
        state, record = observed[job], original["record"]
        gpu = record.get("gpus", record.get("requested_gpu", 0))
        if type(gpu) is not int or not 0 <= gpu <= 4:
            raise ValueError("Invalid GPU submission accounting")
        terminal = state.get("state") in TERMINAL and bool(state.get("complete_time"))
        item = {
            **original,
            "job": job,
            "state": state.get("state", "LOOKUP_FAILED"),
            "terminal": terminal,
            "gpus": gpu,
            "create_time": state.get("create_time"),
            "start_time": state.get("start_time"),
            "complete_time": state.get("complete_time"),
        }
        if gpu and state.get("create_time"):
            end = seconds(state["complete_time"]) if terminal else now.timestamp()
            start = seconds(state["create_time"])
            reservations.extend([(start, gpu), (end, -gpu)])
            item["reserved_gpu_hours"] = gpu * (end - start) / 3600
            if state.get("start_time"):
                allocated = seconds(state["start_time"])
                allocations.extend([(allocated, gpu), (end, -gpu)])
                item["allocated_gpu_hours"] = gpu * (end - allocated) / 3600
        records.append(item)

    def peak(events):
        maximum, current = 0, 0
        for _, delta in sorted(events):
            current += delta
            maximum = max(maximum, current)
        return maximum

    maximum = peak(reservations)
    if maximum > 4:
        raise ValueError("Submitted GPU intervals exceed the authorized four H100s")
    result = {
        "at": now.isoformat(),
        "jobs": len(records),
        "records": records,
        "all_terminal": all(r["terminal"] for r in records),
        "all_lookup_passed": all("state" in s for s in observed.values()),
        "peak_reserved_h100": maximum,
        "peak_allocated_h100": peak(allocations),
        "reserved_gpu_hours": sum(r.get("reserved_gpu_hours", 0) for r in records),
        "allocated_gpu_hours": sum(r.get("allocated_gpu_hours", 0) for r in records),
        "resource_interpretation": "platform create/start/complete intervals; not GPU utilization or billing",
        "only_run_local_submission_receipts_queried": True,
        "all_workers_successful": all(r["state"] == "SUCCEEDED" for r in records),
    }
    result["passed"] = result["all_lookup_passed"] and (
        result["all_terminal"] or not args.require_terminal
    )
    (out / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "records"}), flush=True)
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
