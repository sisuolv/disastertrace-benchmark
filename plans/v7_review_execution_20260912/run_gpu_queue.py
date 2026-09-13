"""One-use queue of already frozen four-H100 batches and CPU validators."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gpu_worker import digest, save
from launch_gpu import TERMINAL, own_jobs, requested_gpus

BASE = Path(__file__).resolve().parent
MODEL_PYTHON = "/mnt/afs/260010168/.venvs/disastertrace-mm-vlm-v1/bin/python"


def now():
    return datetime.now(timezone.utc)


def main(args):
    jobs = [
        ("gpu_bay_secondary_persistent_01", "extension_bay_area_01", "bay_area"),
        ("gpu_front_primary_persistent_01", "extension_front_range_03", "front_range"),
        ("gpu_replication_primary_base_01", "replication_2026_01", "front_range_2026"),
        ("gpu_replication_primary_persistent_01", "replication_2026_01", "front_range_2026"),
    ]
    window = json.loads((BASE / "WINDOW.json").read_text())
    deadline = datetime.fromisoformat(window["deadline_at"])
    entries = []
    for name, data, region in jobs:
        batch = BASE / name
        plan = json.loads((batch / "PLAN.json").read_text())
        if (batch / "submissions").exists() or len(plan["workers"]) != 4:
            raise ValueError("Queue includes a consumed or non-four-worker batch")
        entries.append({"batch": name, "dataset": data, "region": region,
            "plan_sha256": digest(batch / "PLAN.json"), "maximum_calls": plan["maximum_model_calls"],
            "max_worker_seconds": plan["max_worker_seconds"]})
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "run_gpu_queue.py")
    helpers = {name: digest(BASE / name) for name in ("launch_gpu.py", "verify_gpu.py", "gpu_worker.py")}
    save(args.output / "CONTRACT.json", {"started_at": now().isoformat(), "deadline": deadline.isoformat(),
        "entries": entries, "helper_sha256": helpers, "max_concurrent_h100": 4,
        "launch_rule": "Wait for zero account-wide requested active GPUs before a four-worker launch; include queued jobs; original launcher rechecks each submission. Each queue/batch intent is single use.",
        "deadline_rule": "Do not start a batch if its entire worker timeout plus 15-minute validation margin would exceed the user window. CPU validation can overlap the following independent frozen batch.",
        "maximum_new_model_calls": sum(e["maximum_calls"] for e in entries)})
    state = {"completed_batches": [], "launched_batches": [], "validators": [], "phase": "waiting"}
    validators = []

    def status():
        state["updated_at"] = now().isoformat()
        state["validators"] = [{"batch": name, "pid": process.pid, "returncode": process.poll()} for name, process in validators]
        path = args.output / "STATUS.tmp"
        path.write_text(json.dumps(state, indent=2) + "\n")
        path.replace(args.output / "STATUS.json")

    for index, entry in enumerate(entries):
        state.update(phase="waiting_for_free_gpus", next_batch=entry["batch"])
        while True:
            if now() + timedelta(seconds=entry["max_worker_seconds"] + 900) > deadline:
                state["phase"] = "stopped_before_late_launch"
                status()
                save(args.output / "STOPPED.json", state)
                return
            account = own_jobs()
            active = [job for job in account if job["state"] not in TERMINAL]
            state["account_active_requested_gpus"] = sum(requested_gpus(j) for j in active)
            status()
            if state["account_active_requested_gpus"] == 0:
                break
            time.sleep(30)
        for name, expected in helpers.items():
            if digest(BASE / name) != expected:
                raise ValueError("Queued helper changed; no automatic reapproval of its bytes")
        batch = BASE / entry["batch"]
        if digest(batch / "PLAN.json") != entry["plan_sha256"]:
            raise ValueError("Queued frozen plan changed")
        save(args.output / f"LAUNCH_INTENT_{index:02d}.json", {**entry, "at": now().isoformat()})
        with (BASE / (entry["batch"] + "_launch.log")).open("x") as log:
            result = subprocess.run([sys.executable, str(BASE / "launch_gpu.py"), "--batch", str(batch)],
                                    stdout=log, stderr=subprocess.STDOUT, timeout=700, check=False)
        if result.returncode:
            raise ValueError("Submission was not confirmed; stop queue without retry")
        ids = [(batch / "submissions" / str(worker) / "job-id.txt").read_text().strip() for worker in range(4)]
        state["launched_batches"].append({"batch": entry["batch"], "job_ids": ids, "at": now().isoformat()})
        state["phase"] = "model_execution"
        status()
        print(json.dumps({"launched": entry["batch"], "job_ids": ids}), flush=True)
        while True:
            observed = {j["name"]: j for j in own_jobs()}
            if all(i in observed and observed[i]["state"] in TERMINAL for i in ids):
                break
            status()
            time.sleep(30)
        states = {i: observed[i]["state"] for i in ids}
        state["completed_batches"].append({"batch": entry["batch"], "job_states": states})
        if all(s == "SUCCEEDED" for s in states.values()):
            output = BASE / (entry["batch"] + "_validation_01")
            with (BASE / (entry["batch"] + "_validation_01.log")).open("x") as log:
                process = subprocess.Popen([MODEL_PYTHON, str(BASE / "verify_gpu.py"), "--batch", str(batch),
                    "--output", str(output), "--outcomes", str(BASE / entry["dataset"] / "private/OUTCOMES.json"),
                    "--region", entry["region"]], stdout=log, stderr=subprocess.STDOUT)
            validators.append((entry["batch"], process))
        status()
    state["phase"] = "waiting_for_cpu_validators"
    while any(process.poll() is None for _, process in validators):
        status()
        time.sleep(20)
    state["phase"] = "queue_completed"
    status()
    save(args.output / "COMPLETE.json", state)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
