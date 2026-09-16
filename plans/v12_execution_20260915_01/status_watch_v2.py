"""Low-volume stage receipts and deadline handling for only this batch's jobs."""
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from status_watch import ROOT, read, snapshot as original_snapshot


def snapshot():
    status = original_snapshot()
    compatibility = [read(p) for p in ROOT.glob("api_compatibility_*/RESULT.json")]
    status["model_compatibility_attempts"] = sum(r.get("attempts",0) for r in compatibility)
    status["structured_compatibility"] = read(ROOT / "api_compatibility_02/RESULT.json")
    stage = read(ROOT / "stage_C/RESULT.json", {})
    arms = [read(p) for p in (ROOT / "stage_C").glob("*/*_RESULT.json")]
    status["benchmark_model_requests"] = len(list((ROOT / "stage_C").glob("*/spool/*.api_intent.json")))
    status["model_count_semantics"] = "HTTP intents; provider processing may remain unknown for a failed transport"
    status["annual_joins"] = {k:v for k,v in read(ROOT / "annual_stage_B/joins/RESULT.json", {}).items() if k!="results"}
    status["annual_fit"] = read(ROOT / "annual_stage_B/fit/RESULT.json")
    status["stage_C"] = {"claim_present": (ROOT / "stage_C/CLAIM.json").exists(),
        "case_freeze_present": (ROOT / "stage_C/CASE_FREEZE.json").exists(),
        "completed_arms": len(arms), "successful_arms": sum(r.get("passed",False) for r in arms),
        "terminal_result": {k:v for k,v in stage.items() if k not in {"results","scored"}},
        "analysis_present": (ROOT / "stage_C/ANALYSIS.json").exists()}
    return status


def main():
    deadline = dt.datetime.fromisoformat(read(ROOT / "EXECUTION_AUTHORIZATION.json")["deadline_at"]).timestamp()
    prior = None
    while True:
        status = snapshot()
        temp = ROOT / "STATUS.tmp"
        temp.write_text(json.dumps(status, indent=2))
        temp.replace(ROOT / "STATUS.json")
        key = {k:v for k,v in status.items() if k not in {"at","watcher_pid","download"}}
        if key != prior:
            with (ROOT / "logs/status_events_v2.jsonl").open("a") as stream:
                stream.write(json.dumps(status)+"\n")
            prior = key
        if (ROOT / "BATCH_CLOSED.json").exists():
            return
        if time.time() >= deadline-1800:
            stop = ROOT / "annual_stage_B/STOP_REQUEST.json"
            if not stop.exists():
                stop.write_text(json.dumps({"reason": "registered 9.5 hour closeout", "at": status["at"]}))
            for job in status["jobs"]:
                receipt = Path(job["runtime"]) / "DEADLINE_STOP.json"
                if job["worker_exit"] is None and not receipt.exists():
                    result = subprocess.run(["/mnt/afs/260010168/bin/sco", "acp", "jobs", "stop", "--workspace-name=share-space", job["job_id"]], capture_output=True, text=True, timeout=60)
                    receipt.write_text(json.dumps({"at": status["at"], "job_id": job["job_id"], "returncode": result.returncode,
                        "stdout": result.stdout, "stderr": result.stderr}))
        completed = all(j["worker_exit"] is not None for j in status["jobs"])
        stage = read(ROOT / "stage_C/RESULT.json", {})
        ready = completed and (stage.get("passed") or (ROOT / "CLOSEOUT_REQUEST.json").exists())
        if ready or time.time() >= deadline:
            log = ROOT / "logs/automatic_closeout.log"
            if not log.exists():
                with log.open("x") as stream:
                    result = subprocess.run([sys.executable, str(ROOT / "closeout.py"), "--write"], stdout=stream, stderr=subprocess.STDOUT)
                (ROOT / "AUTOMATIC_CLOSEOUT_EXIT.json").write_text(json.dumps({"exit_code": result.returncode, "at": status["at"]}))
            if (ROOT / "BATCH_CLOSED.json").exists():
                continue
        if time.time() >= deadline:
            (ROOT / "DEADLINE_REACHED.json").write_text(json.dumps(status, indent=2))
            return
        time.sleep(60)


if __name__ == "__main__":
    main()
