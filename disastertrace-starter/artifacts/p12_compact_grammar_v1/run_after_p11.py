"""Dispatch the two registered two-replica matrices after CPU/hardware gates and release."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import time
import traceback

from disastertrace.compact_live import acp, capacity, launch, package
from disastertrace.compact_live.storage import now, write
from disastertrace.forecast_task.common import digest, fingerprint, read, strict_json

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
PROFILES = ("qwen3", "deepseek_r1")


def readiness(jobs, prerequisite_ids):
    count = capacity.occupied(jobs)
    lookup = {j["name"]: j for j in jobs}
    if not set(prerequisite_ids) <= set(lookup):
        raise ValueError("capacity listing omits prerequisite jobs")
    return count == 0 and all(lookup[j]["state"] in capacity.TERMINAL for j in prerequisite_ids), count


def predecessor_jobs(bundle):
    rows = [read(bundle / ("acp_" + p + "_live_01") / f"worker-{i}/submission.json")
            for p in PROFILES for i in range(2)]
    ids = [row["job_id"] for row in rows]
    if len(set(ids)) != 4 or any(not value.startswith("pt-") for value in ids):
        raise ValueError("predecessor jobs are not four unique actual ACP submissions")
    return ids


def main():
    output = ROOT / "chain_after_p11_01"
    output.mkdir(exist_ok=False)
    write(output / "CLAIM.json", {"at": now(), "pid": os.getpid(), "script_sha256": digest(__file__),
          "planned_answers": 4824, "max_parallel_gpu": 4, "model_retries": 0})
    final = {"status": "failed", "started_at": now()}
    try:
        deadline = read(ROOT / "PREREGISTRATION.json")["autonomous_work_deadline"]
        predecessor = PROJECT / "artifacts/p11_cohort_live_v1/chain_after_p9_01/FINAL_STATUS.json"
        while not predecessor.exists():
            if (datetime.fromisoformat(deadline) - datetime.now(timezone.utc)).total_seconds() < 1800:
                final.update(status="window_ended_without_dispatch", model_calls=0)
                return 0
            print({"at": now(), "waiting_for": "P11 dispatch completion"}, flush=True)
            time.sleep(30)
        if read(predecessor)["status"] != "submitted_registered_matrices":
            raise RuntimeError("P11 dispatch did not finish; no automatic P12 launch")
        ids = predecessor_jobs(PROJECT / "artifacts/p11_cohort_live_v1")
        round_no = 0
        while True:
            if (datetime.fromisoformat(deadline) - datetime.now(timezone.utc)).total_seconds() < 1800:
                final.update(status="window_ended_without_dispatch", model_calls=0)
                return 0
            gates = all((ROOT / (kind + "_ACCEPTANCE_" + profile + ".json")).exists()
                        for profile in PROFILES for kind in ("CPU", "PREFLIGHT"))
            if not gates:
                print({"at": now(), "ready": False, "reason": "waiting_for_both_cpu_and_preflight_acceptances"}, flush=True)
                time.sleep(30)
                continue
            prerequisite_ids = ids + [read(ROOT / ("PREFLIGHT_ACCEPTANCE_" + p + ".json"))["job"]["job_id"] for p in PROFILES]
            argv = [acp.SCO, "acp", "jobs", "list", "--workspace-name=share-space", "--user-name=260010168", "--format=json", "--page-size=100"]
            try:
                result = subprocess.run(argv, capture_output=True, text=True, timeout=45, check=False)
                write(output / "occupancy" / f"{round_no:05d}.json", {"at": now(), "argv": argv,
                      "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
                if result.returncode:
                    raise RuntimeError("capacity query failed")
                jobs = [] if result.stdout.strip() == "No jobs found" else strict_json(result.stdout)
                ready, count = readiness(jobs, prerequisite_ids)
                print({"at": now(), "ready": ready, "reserved_gpus": count}, flush=True)
                if ready:
                    break
            except (subprocess.TimeoutExpired, RuntimeError) as exc:
                write(output / "query_errors" / f"{round_no:05d}.json", {"at": now(), "error": str(exc)})
            round_no += 1
            time.sleep(30)
        shared_deadline = min(datetime.now(timezone.utc) + timedelta(hours=4) - timedelta(seconds=30),
                              datetime.fromisoformat(deadline)).isoformat()
        plans, schedules = {}, {}
        for profile in PROFILES:
            cpu = read(ROOT / ("CPU_ACCEPTANCE_" + profile + ".json"))
            preflight = read(ROOT / ("PREFLIGHT_ACCEPTANCE_" + profile + ".json"))
            baseline = package.verify(ROOT / ("execution_" + profile + "_diagnostic_01"), code=True)[0]
            launch.validate_cpu(cpu, baseline)
            launch.validate_preflight(preflight, baseline)
            execution = ROOT / ("execution_" + profile + "_live_01")
            plans[profile] = package.freeze(PROJECT / "artifacts/p10_forecast_cohort_v1/execution_01",
                ROOT / ("resources_" + profile + "_01"), execution, model_profile=profile, kind="model",
                run_root=PROJECT / ("work/p12-compact-" + profile + "-model-v1"), preflight=preflight,
                validation=cpu, autonomy_deadline=deadline, phase_deadline=shared_deadline)
            schedules[profile] = read(execution / "schedule.json")
        comparable = lambda slots: [{k: s[k] for k in ("slot_id", "seed", "method", "repeat", "episode_id", "opportunity_id", "worker_id")} for s in slots]
        if comparable(schedules["qwen3"]) != comparable(schedules["deepseek_r1"]):
            raise ValueError("models do not share the complete source schedule and worker assignment")
        if {s["attempt_id"] for s in schedules["qwen3"]} & {s["attempt_id"] for s in schedules["deepseek_r1"]}:
            raise ValueError("model attempt identities overlap")
        write(ROOT / "COMBINED_LIVE_FREEZE.json", {"at": now(), "executions": plans,
              "shared_deadline": shared_deadline, "planned_answers": 4824,
              "matched_schedule_sha256": fingerprint(comparable(schedules["qwen3"])),
              "prerequisite_jobs_released": prerequisite_ids, "source_model_scores_used_for_dispatch": False})
        submitted, observers = {}, {}
        for profile in PROFILES:
            execution = ROOT / ("execution_" + profile + "_live_01")
            submissions = ROOT / ("acp_" + profile + "_live_01")
            submitted[profile] = launch.submit_phase(execution, submissions)
            argv = [str(PROJECT / ".venv/bin/python"), "-u", str(ROOT / "watch_live.py"),
                    "--execution", str(execution), "--submissions", str(submissions),
                    "--output", str(ROOT / ("finalization_" + profile + "_01"))]
            write(ROOT / ("OBSERVER_" + profile + "_INTENT.json"), {"at": now(), "argv": argv,
                  "script_hashes": {n: digest(ROOT / n) for n in ("watch_live.py", "portable_review.py", "replay_model_tokens.py")}})
            env = dict(os.environ, PYTHONPATH=str(PROJECT / "src"), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
            with (ROOT / ("observer_" + profile + "_01.log")).open("x") as stream:
                process = subprocess.Popen(argv, cwd=PROJECT, env=env, stdin=subprocess.DEVNULL, stdout=stream,
                                           stderr=subprocess.STDOUT, start_new_session=True)
            observers[profile] = process.pid
            write(ROOT / ("OBSERVER_" + profile + "_LAUNCH.json"), {"at": now(), "pid": process.pid, "argv": argv})
        final.update(status="submitted_registered_matrices", submissions=submitted, observer_pids=observers,
                     shared_deadline=shared_deadline, inference_audits="pending")
    except BaseException as exc:
        final["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        final["finished_at"] = now()
        final["status_id"] = fingerprint(final)
        write(output / "FINAL_STATUS.json", final)
        print(final, flush=True)
    return 0 if final["status"] == "submitted_registered_matrices" else 1


if __name__ == "__main__":
    raise SystemExit(main())
