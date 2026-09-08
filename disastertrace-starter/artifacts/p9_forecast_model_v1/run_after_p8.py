"""Launch the registered second-model matrix once P8 releases the shared four-GPU capacity."""

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import time
import traceback

from disastertrace.forecast_model import acp, launch, package
from disastertrace.forecast_task.common import digest, fingerprint, read, strict_json
from disastertrace.forecast_model.storage import now, write

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
TERMINAL = {"SUCCEEDED", "FAILED", "DELETED", "SUSPENDED"}


def available(jobs, prerequisite_ids):
    if len(jobs) >= 100:
        raise ValueError("capacity listing may be paginated; no launch")
    lookup = {job["name"]: job for job in jobs}
    if len(lookup) != len(jobs) or not set(prerequisite_ids) <= set(lookup):
        raise ValueError("capacity listing does not identify every prerequisite job")
    capacity = 0
    for job in jobs:
        if job["state"] in TERMINAL:
            continue
        if not job["roles"]:
            raise ValueError("active allocation has no resource description")
        for role in job["roles"]:
            if not role["resource_spec"]:
                raise ValueError("active allocation has no resource specification")
            for spec in role["resource_spec"]:
                replicas = spec["replicas"]
                if type(replicas) is not int or replicas < 0:
                    raise ValueError("invalid replica count")
                request = int(spec["requests"].get("nvidia.com/gpu", "0"))
                limit = int(spec["limits"].get("nvidia.com/gpu", "0"))
                if min(request, limit) < 0:
                    raise ValueError("invalid GPU count")
                capacity += max(request, limit) * replicas
    released = all(lookup[name]["state"] in TERMINAL for name in prerequisite_ids)
    return released and capacity == 0, capacity


def main():
    output = ROOT / "chain_after_p8_01"
    output.mkdir(exist_ok=False)
    write(output / "CONTROLLER_CLAIM.json", {"at": now(), "pid": os.getpid(), "script_sha256": digest(__file__),
          "purpose": "One new registered P9 matrix after P8 hardware release; independent CPU audit may continue.",
          "maximum_parallel_gpu": 4, "automatic_model_retries": 0})
    result = {"status": "failed", "started_at": now()}
    try:
        p8 = PROJECT / "artifacts/p8_carrier_representation_v1"
        native = PROJECT / "artifacts/p7_forecast_live_v1"
        if read(native / "finalization_01/FINAL_STATUS.json")["status"] != "passed":
            raise ValueError("first native audit did not pass")
        prerequisite_ids = [read(p8 / "acp_live_01" / f"worker-{i}" / "submission.json")["job_id"] for i in range(4)]
        cpu, preflight = read(ROOT / "CPU_ACCEPTANCE.json"), read(ROOT / "PREFLIGHT_ACCEPTANCE.json")
        baseline = package.verify(ROOT / "execution_diagnostic_01", code=True)[0]
        launch.validate_cpu(cpu, baseline)
        launch.validate_preflight(preflight, baseline)
        deadline = read(native / "AUTONOMY_WINDOW.json")["autonomous_work_deadline"]
        round_no = 0
        while True:
            seconds = (datetime.fromisoformat(deadline) - datetime.now(timezone.utc)).total_seconds()
            if seconds < 900:
                result.update(status="window_ended_without_dispatch", model_calls=0)
                return 0
            argv = [acp.SCO, "acp", "jobs", "list", "--workspace-name=share-space", "--user-name=260010168",
                    "--format=json", "--page-size=100"]
            try:
                reply = subprocess.run(argv, capture_output=True, text=True, timeout=45, check=False)
                write(output / "occupancy" / f"{round_no:05d}.json", {"at": now(), "argv": argv,
                      "exit_code": reply.returncode, "stdout": reply.stdout, "stderr": reply.stderr})
                if reply.returncode:
                    raise RuntimeError("capacity query failed")
                jobs = [] if reply.stdout.strip() == "No jobs found" else strict_json(reply.stdout)
                ready, capacity = available(jobs, prerequisite_ids)
                print({"at": now(), "prerequisite_jobs": prerequisite_ids, "active_gpu_count": capacity,
                       "all_four_slots_available": ready}, flush=True)
                if ready:
                    break
            except (subprocess.TimeoutExpired, RuntimeError) as exc:
                write(output / "query_errors" / f"{round_no:05d}.json", {"at": now(), "error": str(exc)})
            round_no += 1
            time.sleep(30)
        execution, submissions = ROOT / "execution_live_01", ROOT / "acp_live_01"
        plan = package.freeze(PROJECT / "artifacts/p7_forecast_task_v1/execution_v1", ROOT / "resources_01", execution,
                              kind="model", run_root=PROJECT / "work/p9-native-deepseek-r1-v1", preflight=preflight,
                              validation=cpu, autonomy_deadline=deadline)
        write(ROOT / "LIVE_FREEZE_RECEIPT.json", {"at": now(), "execution_id": plan["execution_id"],
              "phase_id": plan["phase_id"], "deadline": plan["deadline_utc"], "planned_answers": 1542,
              "worker_counts": [390, 390, 384, 378], "active_gpu_count_before": capacity,
              "prerequisite_jobs_released": prerequisite_ids})
        submitted = launch.submit_phase(execution, submissions)
        argv = [str(PROJECT / ".venv/bin/python"), "-u", str(ROOT / "watch_live.py"),
                "--execution", str(execution), "--submissions", str(submissions), "--output", str(ROOT / "finalization_01")]
        write(ROOT / "OBSERVER_LAUNCH_INTENT.json", {"at": now(), "argv": argv,
              "script_hashes": {name: digest(ROOT / name) for name in ("watch_live.py", "replay_model_tokens.py", "portable_review.py")}})
        env = dict(os.environ, PYTHONPATH=str(PROJECT / "src"), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
        with (ROOT / "observer_01.log").open("x") as log:
            process = subprocess.Popen(argv, cwd=PROJECT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
        write(ROOT / "OBSERVER_LAUNCH.json", {"at": now(), "pid": process.pid, "argv": argv})
        result.update(status="submitted_new_matrix", execution_id=plan["execution_id"], submissions=submitted,
                      observer_pid=process.pid, inference_results="pending_independent_observer")
    except BaseException as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        result["finished_at"] = now()
        result["status_id"] = fingerprint(result)
        write(output / "CONTROLLER_RESULT.json", result)
        print(result, flush=True)
    return 0 if result["status"] in ("submitted_new_matrix", "window_ended_without_dispatch") else 1


if __name__ == "__main__":
    raise SystemExit(main())
