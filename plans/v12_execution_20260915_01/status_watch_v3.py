"""Observe explicit platform termination of the replaced serial score tail."""
import datetime as dt
import json
import subprocess
import sys
import time

from status_watch_v2 import ROOT, read, snapshot as previous_snapshot


def main():
    deadline = dt.datetime.fromisoformat(read(ROOT / "EXECUTION_AUTHORIZATION.json")["deadline_at"]).timestamp()
    prior = None
    while True:
        status = previous_snapshot()
        handoff = read(ROOT / "stage_C_audit_handoff_01/ORIGINAL_JOB_TERMINAL.json", {})
        for job in status["jobs"]:
            controlled = job["job_id"] == handoff.get("job_id") and handoff.get("state") in {"STOPPED", "FAILED", "SUCCEEDED"}
            job["known_terminal"] = job["worker_exit"] is not None or controlled
            if controlled:
                job["controlled_audit_handoff_terminal"] = handoff
        status["parallel_scoring_handoff"] = {
            "result": read(ROOT / "stage_C_audit_handoff_01/RESULT.json"),
            "completed_new_groups": len(list((ROOT / "stage_C_audit_handoff_01/scores").glob("*/*_RESULT.json"))),
        }
        temp = ROOT / "STATUS.tmp"
        temp.write_text(json.dumps(status, indent=2))
        temp.replace(ROOT / "STATUS.json")
        key = {k: v for k, v in status.items() if k not in {"at", "watcher_pid", "download"}}
        if key != prior:
            with (ROOT / "logs/status_events_v3.jsonl").open("a") as stream:
                stream.write(json.dumps(status) + "\n")
            prior = key
        if (ROOT / "BATCH_CLOSED.json").exists():
            return
        if time.time() >= deadline - 1800:
            for job in status["jobs"]:
                receipt = ROOT / "runtime" / job["runtime"].split("/")[-1] / "DEADLINE_STOP.json"
                if not job["known_terminal"] and not receipt.exists():
                    result = subprocess.run(["/mnt/afs/260010168/bin/sco", "acp", "jobs", "stop", "--workspace-name=share-space", job["job_id"]], capture_output=True, text=True, timeout=60)
                    receipt.write_text(json.dumps({"at": status["at"], "job_id": job["job_id"], "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}))
        complete = all(j["known_terminal"] for j in status["jobs"])
        stage = read(ROOT / "stage_C/RESULT.json", {})
        if (complete and (stage.get("passed") or (ROOT / "CLOSEOUT_REQUEST.json").exists())) or time.time() >= deadline:
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
