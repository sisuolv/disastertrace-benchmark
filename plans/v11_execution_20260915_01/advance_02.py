"""Bounded background handoff: preflight, four shards, complete-roster audit."""

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

RUN = Path(__file__).resolve().parent
REPO = RUN.parents[1]
BATCH = RUN / "fullweek_02"


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def status(state, **details):
    value = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "state": state, **details}
    temporary = RUN / "STATUS_02.writing"
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(RUN / "STATUS_02.json")
    print(json.dumps(value), flush=True)


def submit(name, command, seconds=21600):
    folder = RUN / "runtime" / name
    if folder.exists():
        if not (folder / "JOB.json").exists():
            raise RuntimeError("Submission identity exists without a confirmed job: " + name)
        return read(folder / "JOB.json")
    cmd = [sys.executable, str(REPO / "plans/v10_execution_20260914_01/scripts/submit_cpu.py"),
           "--out", str(folder), "--name", "dt-v11-" + name.replace("_", "-"),
           "--seconds", str(seconds), "--spec", "n6ls.iu.i40.16c64g", "--", *command]
    result = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=120)
    write(RUN / (name + ".SUBMISSION.json"), {"exit_code": result.returncode,
          "stdout": result.stdout, "stderr": result.stderr, "command": cmd})
    if result.returncode:
        raise RuntimeError("Original cloud submission not confirmed: " + name)
    return read(folder / "JOB.json")


def wait_for(paths, runtime_names, deadline):
    while not all(p.exists() for p in paths):
        for name in runtime_names:
            p = RUN / "runtime" / name / "EXIT.json"
            if p.exists() and read(p)["exit_code"] != 0:
                raise RuntimeError("Worker exited unsuccessfully: " + name)
        if time.monotonic() >= deadline:
            raise TimeoutError("Bounded coordinator deadline; existing jobs are not relaunched")
        time.sleep(120)


def main():
    write(RUN / "ADVANCE_CLAIM_02.json", {"pid": os.getpid(), "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "max_hours": 10, "model_calls": 0, "max_gpu": 0, "cpu_shards": 4})
    deadline = time.monotonic() + 36000
    try:
        status("waiting_for_real_preflight_and_replay_equivalence")
        proofs = [RUN / "real_pilot_02/RESULT.json", RUN / "profile_01/RESULT.json"]
        wait_for(proofs, ["pilot_02", "profile_01"], deadline)
        if not all(read(p)["passed"] for p in proofs):
            raise ValueError("Real preflight or exact legacy-score equivalence failed")
        regression = read(RUN / "REGRESSION_RESULT_02.json")
        if regression["failures"] or regression["skips"]:
            raise ValueError("Regression gate failed")
        jobs = []
        for shard in range(4):
            jobs.append(submit("fullweek02_shard_" + str(shard), ["env", "PYTHONDONTWRITEBYTECODE=1",
                "PYTHONPATH=" + str(BATCH / "source"), "python", str(BATCH / "source/fullweek.py"),
                "run", "--out", str(BATCH), "--shard", str(shard), "--workers", "12"]))
        status("running_full_calendar", jobs=jobs, expected_trajectories=840, registered_opportunities=12096)
        wait_for([BATCH / ("COMPLETE_" + str(i) + ".json") for i in range(4)],
                 ["fullweek02_shard_" + str(i) for i in range(4)], deadline)
        if not all(read(BATCH / ("COMPLETE_" + str(i) + ".json"))["passed"] for i in range(4)):
            raise ValueError("Registered trajectory failure; no automatic replacement")
        audit = submit("fullweek02_audit_01", ["env", "PYTHONDONTWRITEBYTECODE=1",
            "PYTHONPATH=" + str(BATCH / "source"), "python", str(BATCH / "source/fullweek.py"),
            "audit", "--out", str(BATCH), "--workers", "12"], seconds=14400)
        status("auditing_full_calendar", job=audit, expected_method_rows=60480)
        wait_for([BATCH / "RESULT.json"], ["fullweek02_audit_01"], deadline)
        result = read(BATCH / "RESULT.json")
        if not result["passed"]:
            raise ValueError("Full calendar audit failed")
        status("completed_full_calendar_scope", result="fullweek_02/RESULT.json",
               independent_confirmation=False, annual_fit_completed=False)
        write(RUN / "ADVANCE_RESULT_02.json", {"passed": True, "result": str(BATCH / "RESULT.json"),
              "independent_confirmation": False, "new_model_calls": 0})
    except Exception as exc:  # noqa: BLE001 - surface a bounded stage failure without hiding or retrying it.
        status("needs_review", error=type(exc).__name__, message=str(exc))
        write(RUN / "ADVANCE_RESULT_02.json", {"passed": False, "error": type(exc).__name__, "message": str(exc)})
        raise


if __name__ == "__main__":
    main()
