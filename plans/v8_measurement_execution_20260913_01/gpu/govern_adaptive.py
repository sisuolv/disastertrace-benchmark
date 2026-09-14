"""Wait for the original program audit, then qualify and submit exactly once."""

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BATCH = HERE / "adaptive_large_02"
OUT = BATCH / "governor_01"


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")


def main():
    OUT.mkdir(exist_ok=False)
    save(
        OUT / "STARTED.json",
        {
            "pid": os.getpid(),
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "batch": str(BATCH),
            "maximum_submissions": 1,
            "maximum_gpus": 4,
        },
    )
    gate = (
        HERE.parent / "reports/program_calendar_optimized_audit_01/BATCH_COMPLETE.json"
    )
    last = dt.datetime(2026, 9, 13, 23, tzinfo=dt.timezone.utc)
    while not gate.exists():
        if dt.datetime.now(dt.timezone.utc) >= last:
            save(
                OUT / "NOT_SUBMITTED.json",
                {
                    "reason": "Original program audit not complete before launch window ended."
                },
            )
            return
        time.sleep(20)
    if not json.loads(gate.read_text())["all_passed"]:
        save(
            OUT / "NOT_SUBMITTED.json",
            {"reason": "Original program audit failed; no inference permitted."},
        )
        return
    for name in ("qualify_adaptive", "launch_adaptive"):
        argv = [sys.executable, str(HERE / (name + ".py"))]
        save(
            OUT / (name + ".command.json"),
            {"argv": argv, "at": dt.datetime.now(dt.timezone.utc).isoformat()},
        )
        with (OUT / (name + ".log")).open("x") as handle:
            result = subprocess.run(
                argv, stdout=handle, stderr=subprocess.STDOUT, check=False
            )
        save(OUT / (name + ".exit.json"), {"exit_code": result.returncode})
        print(name, result.returncode, flush=True)
        if result.returncode:
            return
    job = BATCH / "submission_01/job-id.txt"
    if job.exists():
        argv = [sys.executable, str(HERE / "observe_adaptive.py")]
        with (OUT / "observer.log").open("x") as handle:
            child = subprocess.Popen(
                argv, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True
            )
        save(
            OUT / "OBSERVING.json",
            {"pid": child.pid, "job_id": job.read_text().strip(), "argv": argv},
        )
        print(job.read_text().strip(), flush=True)
    save(
        OUT / "COMPLETE.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "job_id": job.read_text().strip() if job.exists() else None,
        },
    )


if __name__ == "__main__":
    main()
