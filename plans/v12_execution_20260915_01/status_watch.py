"""Small durable status receipts; no dataset scans or model polling."""
import argparse
import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def snapshot():
    jobs = []
    for f in ROOT.glob("runtime/*/JOB.json"):
        job = read(f)
        job.update(runtime=str(f.parent), worker_exit=read(f.parent / "EXIT.json"))
        jobs.append(job)
    branch = read(ROOT / "C2_BRANCH_EXECUTION_RESULT.json")
    source = read(ROOT / "annual_stage_B/PREPARATION_RESULT.json")
    api = read(ROOT / "api_compatibility_01/RESULT.json", {})
    download = read(ROOT / "annual_stage_B/DOWNLOAD_STATUS.json")
    final = read(ROOT / "RESULT_SUMMARY.json")
    return {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "watcher_pid": os.getpid(),
        "state": "closed" if (ROOT / "BATCH_CLOSED.json").exists() else "executing",
        "deadline_at": read(ROOT / "EXECUTION_AUTHORIZATION.json")["deadline_at"],
        "jobs": jobs, "confirmed_h100_submissions": sum(j.get("gpus", 0) for j in jobs),
        "parent_reconstructions": 6, "original_policy_continuations": 6,
        "branch_claims": len(list((ROOT / "branches").glob("*/*_CLAIM.json"))),
        "branch_results": len(list((ROOT / "branches").glob("*/*_RESULT.json"))),
        "branch_aggregate_passed": None if branch is None else branch["passed"],
        "annual_preparation": source, "download": download,
        "model_compatibility_attempts": api.get("attempts", 0), "benchmark_model_requests": 0,
        "compatibility_http_status": api.get("http_status"), "synthetic_instruction_passed": api.get("passed"),
        "confirmation_opened": False, "final_summary": final}


def main(watch):
    deadline = dt.datetime.fromisoformat(read(ROOT / "EXECUTION_AUTHORIZATION.json")["deadline_at"]).timestamp()
    prior = None
    while True:
        status = snapshot()
        temp = ROOT / "STATUS.tmp"; temp.write_text(json.dumps(status, indent=2)); temp.replace(ROOT / "STATUS.json")
        key = {k: v for k, v in status.items() if k not in {"at", "watcher_pid", "download"}}
        if key != prior:
            with (ROOT / "logs/status_events.jsonl").open("a") as f:
                f.write(json.dumps(status) + "\n")
            prior = key
        if not watch or (ROOT / "BATCH_CLOSED.json").exists():
            return
        if time.time() >= deadline - 1800:
            stop = ROOT / "annual_stage_B/STOP_REQUEST.json"
            if not stop.exists():
                stop.write_text(json.dumps({"reason": "registered 9.5 hour resource closeout", "at": status["at"]}))
            for job in status["jobs"]:
                receipt = Path(job["runtime"]) / "DEADLINE_STOP.json"
                if job["worker_exit"] is None and not receipt.exists():
                    result = subprocess.run(["/mnt/afs/260010168/bin/sco", "acp", "jobs", "stop", "--workspace-name=share-space", job["job_id"]], capture_output=True, text=True, timeout=60)
                    receipt.write_text(json.dumps({"at": status["at"], "job_id": job["job_id"], "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}))
        if time.time() >= deadline:
            (ROOT / "DEADLINE_REACHED.json").write_text(json.dumps(status, indent=2))
            return
        time.sleep(60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--watch", action="store_true")
    main(parser.parse_args().watch)
