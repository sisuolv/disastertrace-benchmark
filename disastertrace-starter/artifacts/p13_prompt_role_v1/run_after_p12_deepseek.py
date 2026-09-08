"""One two-H100 prompt-role matrix after its matched DeepSeek predecessor releases."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import time
import traceback

from disastertrace.compact_live import package as previous_package
from disastertrace.prompt_role_live import acp, capacity, launch, package
from disastertrace.prompt_role_live.storage import now, write
from disastertrace.forecast_task.common import digest, fingerprint, read, strict_json

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
PREVIOUS = PROJECT / "artifacts/p12_compact_grammar_v1"
PROFILE = "deepseek_r1"


def readiness(jobs, ids):
    count = capacity.occupied(jobs)
    mapping = {job["name"]: job for job in jobs}
    if len(set(ids)) != 3 or not set(ids) <= set(mapping):
        raise ValueError("three unique prerequisite allocations must be visible")
    return count <= 2 and all(mapping[job]["state"] in capacity.TERMINAL for job in ids), count


def validate_comparison(baseline, candidate, old_slots, new_slots):
    for key in ("task_package_id", "resource_package_id", "model_identity", "model_profile", "backend_files"):
        if baseline[key] != candidate[key]:
            raise ValueError("matched role comparison differs: " + key)
    old_settings = baseline["settings"]
    new_settings = {k: v for k, v in candidate["settings"].items() if k != "prompt_role_policy"}
    if new_settings != old_settings or candidate["settings"]["prompt_role_policy"] != "system_contract_prepended_to_user_v1":
        raise ValueError("role study changed other model settings")
    keys = ("slot_id", "seed", "method", "repeat", "episode_id", "opportunity_id", "worker_id")
    old = [{k: s[k] for k in keys} for s in old_slots]
    new = [{k: s[k] for k in keys} for s in new_slots]
    if old != new or {s["attempt_id"] for s in old_slots} & {s["attempt_id"] for s in new_slots}:
        raise ValueError("role study schedule mismatch or reused attempt")
    return fingerprint(new)


def main():
    output = ROOT / "chain_after_p12_01"
    output.mkdir(exist_ok=False)
    write(output / "CLAIM.json", {"at": now(), "pid": os.getpid(), "script_sha256": digest(__file__),
          "planned_answers": 2412, "new_gpu_workers": 2, "max_parallel_h100": 4, "model_retries": 0})
    final = {"status": "failed", "started_at": now()}
    try:
        deadline = read(ROOT / "PREREGISTRATION.json")["autonomous_work_deadline"]
        predecessor_status = PREVIOUS / "chain_after_p11_01/FINAL_STATUS.json"
        round_no = 0
        while True:
            if (datetime.fromisoformat(deadline) - datetime.now(timezone.utc)).total_seconds() < 1800:
                final.update(status="window_ended_without_dispatch", model_calls=0)
                return 0
            gates = predecessor_status.exists() and all((ROOT / (kind + "_ACCEPTANCE_" + PROFILE + ".json")).exists() for kind in ("CPU", "PREFLIGHT"))
            if not gates:
                print({"at": now(), "ready": False, "reason": "waiting_for_predecessor_and_current_gates"}, flush=True)
                time.sleep(30)
                continue
            if read(predecessor_status)["status"] != "submitted_registered_matrices":
                raise ValueError("P12 submission controller did not complete")
            ids = [read(PREVIOUS / "acp_deepseek_r1_live_01" / f"worker-{i}/submission.json")["job_id"] for i in range(2)]
            ids.append(read(ROOT / ("PREFLIGHT_ACCEPTANCE_" + PROFILE + ".json"))["job"]["job_id"])
            argv = [acp.SCO, "acp", "jobs", "list", "--workspace-name=share-space", "--user-name=260010168", "--format=json", "--page-size=100"]
            try:
                result = subprocess.run(argv, capture_output=True, text=True, timeout=45, check=False)
                write(output / "occupancy" / f"{round_no:05d}.json", {"at": now(), "argv": argv,
                      "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
                if result.returncode:
                    raise RuntimeError("capacity query failed")
                jobs = [] if result.stdout.strip() == "No jobs found" else strict_json(result.stdout)
                ready, count = readiness(jobs, ids)
                print({"at": now(), "ready": ready, "reserved_gpus": count}, flush=True)
                if ready:
                    break
            except (subprocess.TimeoutExpired, RuntimeError) as exc:
                write(output / "query_errors" / f"{round_no:05d}.json", {"at": now(), "error": str(exc)})
            round_no += 1
            time.sleep(30)
        cpu = read(ROOT / ("CPU_ACCEPTANCE_" + PROFILE + ".json"))
        preflight = read(ROOT / ("PREFLIGHT_ACCEPTANCE_" + PROFILE + ".json"))
        diagnostic = package.verify(ROOT / ("execution_" + PROFILE + "_diagnostic_01"), code=True)[0]
        launch.validate_cpu(cpu, diagnostic)
        launch.validate_preflight(preflight, diagnostic)
        baseline, _, old_slots = previous_package.verify(PREVIOUS / "execution_deepseek_r1_live_01", code=True)
        execution = ROOT / ("execution_" + PROFILE + "_live_01")
        shared_deadline = min(datetime.now(timezone.utc) + timedelta(hours=4, seconds=-30), datetime.fromisoformat(deadline)).isoformat()
        plan = package.freeze(PROJECT / "artifacts/p10_forecast_cohort_v1/execution_01",
                ROOT / ("resources_" + PROFILE + "_01"), execution, model_profile=PROFILE, kind="model",
                run_root=PROJECT / "work/p13-role-deepseek_r1-model-v1", preflight=preflight,
                validation=cpu, autonomy_deadline=deadline, phase_deadline=shared_deadline)
        matched = validate_comparison(baseline, plan, old_slots, read(execution / "schedule.json"))
        write(ROOT / "MATCHED_LIVE_FREEZE.json", {"at": now(), "execution": plan,
              "baseline_execution_id": baseline["execution_id"], "matched_schedule_sha256": matched,
              "released_prerequisite_jobs": ids, "source_model_scores_used_for_dispatch": False})
        submissions = ROOT / ("acp_" + PROFILE + "_live_01")
        submitted = launch.submit_phase(execution, submissions)
        argv = [str(PROJECT / ".venv/bin/python"), "-u", str(ROOT / "watch_live.py"),
                "--execution", str(execution), "--submissions", str(submissions),
                "--output", str(ROOT / "finalization_deepseek_r1_01")]
        write(ROOT / "OBSERVER_INTENT.json", {"at": now(), "argv": argv,
              "script_hashes": {n: digest(ROOT / n) for n in ("watch_live.py", "portable_review.py", "replay_model_tokens.py")}})
        env = dict(os.environ, PYTHONPATH=str(PROJECT / "src"), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
        with (ROOT / "observer_deepseek_r1_01.log").open("x") as stream:
            process = subprocess.Popen(argv, cwd=PROJECT, env=env, stdin=subprocess.DEVNULL,
                                       stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        write(ROOT / "OBSERVER_LAUNCH.json", {"at": now(), "pid": process.pid, "argv": argv})
        final.update(status="submitted_registered_matrix", submissions=submitted, observer_pid=process.pid,
                     deadline=shared_deadline, inference_audit="pending")
    except BaseException as exc:
        final["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        final["finished_at"] = now()
        final["status_id"] = fingerprint(final)
        write(output / "FINAL_STATUS.json", final)
        print(final, flush=True)
    return 0 if final["status"] == "submitted_registered_matrix" else 1


if __name__ == "__main__":
    raise SystemExit(main())
