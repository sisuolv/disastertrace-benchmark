"""Continue unconsumed shards within observed CPU quota, preserving failed submissions."""

import datetime as dt
import json
import os
import re
import time

import advance_02 as base

RUN, BATCH = base.RUN, base.BATCH


def status(state, **details):
    record = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "state": state, **details}
    temporary = RUN / "STATUS_03.writing"
    temporary.write_text(json.dumps(record, indent=2) + "\n")
    temporary.replace(RUN / "STATUS_03.json")
    print(json.dumps(record), flush=True)


def occupied_cpus():
    count = 0
    for path in (RUN / "runtime").glob("*/JOB.json"):
        if not (path.parent / "EXIT.json").exists():
            match = re.search(r"\.(\d+)c\d+g$", base.read(path)["spec"])
            if not match:
                raise ValueError("Unknown CPU allocation spelling")
            count += int(match[1])
    return count


def submit_after_capacity(name, command, deadline):
    for attempt in range(1, 4):
        while occupied_cpus() + 16 > 72:
            status("waiting_for_cpu_slot", observed_active_cpus=occupied_cpus(), next_job=name)
            if time.monotonic() >= deadline:
                raise TimeoutError("CPU slot did not become available within the coordinator bound")
            time.sleep(120)
        runtime = name + "_submission_" + str(attempt)
        try:
            job = base.submit(runtime, command)
            return runtime, job
        except RuntimeError:
            response = RUN / "runtime" / runtime / "CREATE_RESPONSE.json"
            # A definite server quota rejection consumed no worker; all other uncertainty stops.
            if not response.exists() or "MEMBER_QUOTA_EXCEEDED" not in base.read(response).get("stderr", ""):
                raise
            status("platform_quota_release_pending", rejected_runtime=runtime, attempt=attempt)
            time.sleep(120)
    raise RuntimeError("Three definite quota rejections; manual scheduler review required")


def main():
    base.write(RUN / "ADVANCE_CLAIM_03.json", {"pid": os.getpid(), "max_hours": 10})
    deadline = time.monotonic() + 36000
    try:
        if not all(base.read(RUN / p)["passed"] for p in ["real_pilot_02/RESULT.json", "profile_01/RESULT.json"]):
            raise ValueError("Preflight evidence did not pass")
        runtimes = ["fullweek02_shard_0", "fullweek02_shard_1", "fullweek02_shard_2_small"]
        jobs = [base.read(RUN / "runtime" / n / "JOB.json") for n in runtimes]
        if (BATCH / "CLAIM_3.json").exists():
            raise ValueError("Fourth shard already has an execution claim")
        runtime, job = submit_after_capacity("fullweek02_shard_3", ["env", "PYTHONDONTWRITEBYTECODE=1",
            "PYTHONPATH=" + str(BATCH / "source"), "python", str(BATCH / "source/fullweek.py"),
            "run", "--out", str(BATCH), "--shard", "3", "--workers", "12"], deadline)
        runtimes.append(runtime)
        jobs.append(job)
        status("running_full_calendar", jobs=jobs, workers_per_shard=[12, 12, 6, 12], expected_trajectories=840)
        complete = [BATCH / f"COMPLETE_{i}.json" for i in range(4)]
        base.wait_for(complete, runtimes, deadline)
        if not all(base.read(p)["passed"] for p in complete):
            raise ValueError("A registered trajectory failed; no automatic replacement")
        runtime, job = submit_after_capacity("fullweek02_audit", ["env", "PYTHONDONTWRITEBYTECODE=1",
            "PYTHONPATH=" + str(BATCH / "source"), "python", str(BATCH / "source/fullweek.py"),
            "audit", "--out", str(BATCH), "--workers", "12"], deadline)
        status("auditing_full_calendar", job=job)
        base.wait_for([BATCH / "RESULT.json"], [runtime], deadline)
        if not base.read(BATCH / "RESULT.json")["passed"]:
            raise ValueError("Complete calendar audit failed")
        status("completed_full_calendar_scope", result="fullweek_02/RESULT.json")
        base.write(RUN / "ADVANCE_RESULT_03.json", {"passed": True, "new_model_calls": 0})
    except Exception as exc:  # noqa: BLE001 - preserve the stopped continuation without relaunching workers.
        status("needs_review", error=type(exc).__name__, message=str(exc))
        base.write(RUN / "ADVANCE_RESULT_03.json", {"passed": False, "error": type(exc).__name__, "message": str(exc)})
        raise


if __name__ == "__main__":
    main()
