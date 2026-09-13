"""Run four bounded one-H100 diagnostic batches after the existing calendar queue."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from gpu_worker import digest, save
from launch_gpu import TERMINAL, own_jobs, requested_gpus

BASE = Path(__file__).resolve().parent
OUT = BASE / "e_order_queue_01"
MODEL_PYTHON = "/mnt/afs/260010168/.venvs/disastertrace-mm-vlm-v1/bin/python"
PUBLICATION = BASE.parents[1] / "publication/v7_review_execution_20260912"


def now():
    return datetime.now(timezone.utc)


def main():
    names = ["gpu_e_order_" + model + "_" + order + "_01"
             for model in ("8b", "32b") for order in ("ab", "ba")]
    plans = {}
    for name in names:
        path = BASE / name / "PLAN.json"
        plan = json.loads(path.read_text())
        if plan["maximum_model_calls"] != 192 or len(plan["workers"]) != 1 or (path.parent / "submissions").exists():
            raise ValueError("Order audit includes an invalid or consumed batch")
        plans[name] = digest(path)
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(__file__, OUT / "run_e_order_queue.py")
    helpers = {name: digest(BASE / name) for name in ("launch_gpu.py", "verify_e_probe.py", "gpu_worker.py")}
    save(OUT / "CONTRACT.json", {"created_at": now().isoformat(), "plan_sha256": plans,
        "helpers": helpers, "maximum_model_calls": 768, "maximum_simultaneous_H100": 4,
        "launch_before": "2026-09-13T01:30:00+00:00", "stop_nonterminal_after": "2026-09-13T02:15:00+00:00",
        "scope": "Unchanged exposed-development E messages, counterbalanced case/condition orders. No old launch reuse, API, training or F gain claim."})
    state = {"phase": "waiting_for_calendar_queue", "launched": [], "completed": []}

    def status():
        state["updated_at"] = now().isoformat()
        temp = OUT / "STATUS.tmp"
        temp.write_text(json.dumps(state, indent=2) + "\n")
        temp.replace(OUT / "STATUS.json")

    while now() < datetime.fromisoformat("2026-09-13T01:30:00+00:00"):
        if (BASE / "gpu_queue_01/COMPLETE.json").exists():
            active = [j for j in own_jobs() if j["state"] not in TERMINAL]
            state["account_active_requested_gpus"] = sum(requested_gpus(j) for j in active)
            if state["account_active_requested_gpus"] == 0:
                break
        status()
        time.sleep(30)
    else:
        state["phase"] = "not_launched_before_cutoff"
        status()
        save(OUT / "STOPPED.json", state)
        return
    for name in names:
        for helper, expected in helpers.items():
            if digest(BASE / helper) != expected:
                raise ValueError("Diagnostic queue helper changed")
        batch = BASE / name
        if digest(batch / "PLAN.json") != plans[name]:
            raise ValueError("Diagnostic plan changed")
        save(OUT / (name + "-LAUNCH_INTENT.json"), {"batch": name, "at": now().isoformat(), "plan_sha256": plans[name]})
        with (BASE / (name + "_launch.log")).open("x") as stream:
            result = subprocess.run([sys.executable, str(BASE / "launch_gpu.py"), "--batch", str(batch)],
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=700, check=False)
        if result.returncode:
            raise ValueError("Diagnostic submission is not confirmed; never duplicate")
        ident = (batch / "submissions/0/job-id.txt").read_text().strip()
        state["launched"].append({"batch": name, "job_id": ident, "at": now().isoformat()})
        state["phase"] = "model_execution"
        status()
        print(json.dumps({"batch": name, "job_id": ident}), flush=True)
    while True:
        jobs = {j["name"]: j for j in own_jobs()}
        pending = [r for r in state["launched"] if r["job_id"] not in jobs or jobs[r["job_id"]]["state"] not in TERMINAL]
        if not pending:
            break
        if now() >= datetime.fromisoformat("2026-09-13T02:15:00+00:00"):
            for record in pending:
                result = subprocess.run(["/mnt/afs/260010168/bin/sco", "acp", "jobs", "stop",
                    "--workspace-name=share-space", record["job_id"]], capture_output=True, text=True, timeout=60, check=False)
                save(OUT / (record["job_id"] + "-STOP.json"), {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
            state["phase"] = "stopped_at_publication_reserve"
            status()
            save(OUT / "STOPPED.json", state)
            return
        status()
        time.sleep(30)
    state["phase"] = "independent_cpu_validation"
    status()
    for record in state["launched"]:
        name, ident = record["batch"], record["job_id"]
        if jobs[ident]["state"] != "SUCCEEDED":
            state["completed"].append({**record, "job_state": jobs[ident]["state"], "verified": False})
            continue
        batch = BASE / name
        validation = BASE / (name + "_validation_01")
        with (BASE / (name + "_validation_01.log")).open("x") as stream:
            result = subprocess.run([MODEL_PYTHON, str(BASE / "verify_e_probe.py"), "--batch", str(batch),
                "--labels", str(BASE / "E_DIAGNOSTIC_LABELS_01.json"), "--output", str(validation)],
                stdout=stream, stderr=subprocess.STDOUT, timeout=600, check=False)
        if result.returncode:
            raise ValueError("Diagnostic independent validation failed: " + name)
        with (OUT / (name + "-ARCHIVE.log")).open("x") as stream:
            result = subprocess.run([sys.executable, str(PUBLICATION / "build_evidence.py"),
                "--name", name.removeprefix("gpu_"), "--kind", "model", "--source", str(batch),
                "--verification", str(validation / "VERIFIED.json")], stdout=stream,
                stderr=subprocess.STDOUT, timeout=600, check=False)
        if result.returncode:
            raise ValueError("Diagnostic evidence archive failed: " + name)
        state["completed"].append({**record, "job_state": jobs[ident]["state"], "verified": True})
        status()
    state["phase"] = "completed"
    status()
    save(OUT / "COMPLETE.json", state)


if __name__ == "__main__":
    main()
