"""Observe stage boundaries and ACP terminal status without duplicate submission."""

import datetime as dt
import json
from pathlib import Path
import subprocess
import time

from run_cpu_handoff import HANDOFF, ROOT, publish, read


def pipeline(phase, **details):
    row = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "phase": phase,
           "orchestration": "cpu_handoff_01", **details}
    with (ROOT / "runtime/PIPELINE_EVENTS.jsonl").open("a") as handle:
        handle.write(json.dumps(row) + "\n")
    tmp = ROOT / "runtime/PIPELINE_STATUS.acp"
    tmp.write_text(json.dumps(row, indent=2) + "\n")
    tmp.replace(ROOT / "runtime/PIPELINE_STATUS.json")


def main():
    publish(HANDOFF / "WATCHER_CLAIM.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat()})
    job = (HANDOFF / "job-id.txt").read_text().strip()
    last, next_platform = None, 0
    deadline = time.monotonic() + 7 * 3600
    while time.monotonic() < deadline:
        state_path = HANDOFF / "STATUS.json"
        state = read(state_path) if state_path.exists() else {}
        phase = state.get("phase")
        if phase and phase != last:
            pipeline("N4_" + phase, job_id=job)
            last = phase
        if time.monotonic() >= next_platform:
            result = subprocess.run([
                "/mnt/afs/260010168/bin/sco", "acp", "jobs", "describe",
                "--workspace-name=share-space", "--format=json", job,
            ], capture_output=True, text=True, timeout=45)
            if result.returncode == 0:
                raw = json.loads(result.stdout)
                keys = ["name", "display_name", "state", "create_time", "start_time", "finish_time", "resource_pool", "roles"]
                safe = {k: raw[k] for k in keys if k in raw}
                temp = HANDOFF / "PLATFORM_STATUS.next"
                temp.write_text(json.dumps(safe, indent=2) + "\n")
                temp.replace(HANDOFF / "PLATFORM_STATUS.json")
                final = safe.get("state")
                if final in ["SUCCEEDED", "FAILED", "STOPPED", "CANCELLED", "TERMINATED"]:
                    expected = HANDOFF / "COMPLETE.json"
                    passed = final == "SUCCEEDED" and expected.exists() and read(expected)["passed"]
                    publish(HANDOFF / "PLATFORM_VALIDATION.json", {
                        "passed": passed, "job_id": job, "state": final, "gpu_cards": 0,
                        "expected_worker_result": expected.exists(),
                    })
                    pipeline("REGISTERED_PIPELINE_COMPLETE" if passed else "STOPPED_AT_GATE",
                             job_id=job, platform_state=final)
                    if not passed and not (ROOT / "runtime/RARE_COMPLETE.json").exists() and not (ROOT / "runtime/RARE_STOPPED.json").exists():
                        publish(ROOT / "runtime/RARE_STOPPED.json", {"reason": "ACP job terminated", "state": final})
                    return
            next_platform = time.monotonic() + 180
        time.sleep(30)
    publish(HANDOFF / "WATCHER_TIMEOUT.json", {"job_id": job, "automatic_resubmission": False})


if __name__ == "__main__":
    main()
