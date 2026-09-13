"""Reconstruct this bundle's conservative requested-GPU overlap from ACP receipts."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from gpu_worker import digest, save

BASE = Path(__file__).resolve().parent


def main(args):
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "verify_gpu_occupancy.py")
    verifications = {}
    for path in BASE.glob("gpu*_validation_*/VERIFIED.json"):
        record = json.loads(path.read_text())
        key = record["plan_sha256"]
        if key not in verifications or record["verified_at"] > verifications[key][1]["verified_at"]:
            verifications[key] = (path, record)
    jobs, bindings = {}, {}
    for verification_path, record in verifications.values():
        batch = BASE / Path(record["batch"]).name
        if digest(batch / "PLAN.json") != record["plan_sha256"]:
            raise ValueError("Completed verification has a different frozen plan")
        bindings[str(verification_path.resolve())] = digest(verification_path)
        job_paths = sorted(verification_path.parent.glob("JOB*.json"))
        if len(job_paths) != record["verified_workers"]:
            raise ValueError("Verified worker count does not match saved ACP receipts")
        submission_ids = {p.read_text().strip() for p in batch.glob("submissions/*/job-id.txt")}
        for job_path in job_paths:
            job = json.loads(job_path.read_text())
            bindings[str(job_path.resolve())] = digest(job_path)
            name = job["name"]
            if job["state"] != "SUCCEEDED" or name not in submission_ids or name in jobs:
                raise ValueError("Invalid, duplicate or unmatched completed GPU job")
            count = sum(int(spec["requests"]["nvidia.com/gpu"]) * int(spec["replicas"])
                        for role in job["roles"] for spec in role["resource_spec"])
            if count != 1:
                raise ValueError("This execution only froze one-H100 workers")
            created, started, ended = (datetime.fromisoformat(job[k].replace("Z", "+00:00"))
                                       for k in ("create_time", "start_time", "complete_time"))
            if not created <= started < ended:
                raise ValueError("Invalid ACP job interval")
            jobs[name] = {"job_id": name, "batch": batch.name, "requested_gpus": count,
                          "created_at": created.isoformat(), "started_at": started.isoformat(),
                          "completed_at": ended.isoformat(),
                          "requested_gpu_seconds": (ended - created).total_seconds() * count,
                          "running_gpu_seconds": (ended - started).total_seconds() * count}
    events = defaultdict(lambda: {"begin": [], "end": []})
    for name, job in jobs.items():
        events[job["created_at"]]["begin"].append(name)
        events[job["completed_at"]]["end"].append(name)
    active, peak, timeline = set(), 0, []
    for moment, event in sorted(events.items()):
        active.difference_update(event["end"])
        active.update(event["begin"])
        total = sum(jobs[k]["requested_gpus"] for k in active)
        peak = max(peak, total)
        timeline.append({"at": moment, "requested_gpus": total, "jobs": sorted(active)})
    if active or peak > 4:
        raise ValueError("Completed bundle jobs violate the four-GPU overlap bound")
    all_submissions = {p.read_text().strip() for p in BASE.glob("gpu*/submissions/*/job-id.txt")}
    pending = sorted(all_submissions - set(jobs))
    report = {"verified_at": datetime.now(timezone.utc).isoformat(), "completed_jobs": len(jobs),
              "submitted_jobs": len(all_submissions), "unverified_submissions": pending,
              "maximum_completed_job_requested_GPU_overlap": peak,
              "completed_job_requested_GPU_hours": sum(j["requested_gpu_seconds"] for j in jobs.values()) / 3600,
              "completed_job_running_GPU_hours": sum(j["running_gpu_seconds"] for j in jobs.values()) / 3600,
              "jobs": sorted(jobs.values(), key=lambda row: row["created_at"]), "timeline": timeline,
              "input_bindings": bindings, "implementation_sha256": digest(args.output / "verify_gpu_occupancy.py"),
              "new_GPU_submissions": 0, "new_network_requests": 0,
              "scope": "This execution bundle's completed jobs only. Creation-to-completion intervals include queueing. Live launchers separately check account-wide pending/running GPU requests. Not GPU utilization or billing evidence."}
    save(args.output / "VERIFIED.json", report)
    print(json.dumps({k: report[k] for k in ("completed_jobs", "submitted_jobs", "unverified_submissions", "maximum_completed_job_requested_GPU_overlap")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
