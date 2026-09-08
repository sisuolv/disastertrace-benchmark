"""Submit one no-generation preflight per profile only when shared capacity is free."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import time
import traceback

from disastertrace.compact_live import acp, capacity, launch, package, provenance
from disastertrace.compact_live.storage import now, write
from disastertrace.forecast_task.common import digest, fingerprint, inventory, read, strict_json

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]


def main():
    output = ROOT / "preflight_controller_01"
    output.mkdir(exist_ok=False)
    write(output / "CLAIM.json", {"at": now(), "pid": os.getpid(), "script_sha256": digest(__file__),
          "model_calls": 0, "profiles": ["qwen3", "deepseek_r1"], "maximum_parallel_gpu": 4})
    final = {"status": "failed", "started_at": now(), "model_calls": 0}
    active, passed, stopped = {}, {}, set()
    round_no = 0
    try:
        gates = read(ROOT / "TEST_GATES.json")
        if (gates["core_tests_exit_code"] != 0 or any(gates["backend_tests_exit_codes"].values())
                or gates["source_files"] != inventory(PROJECT / "src/disastertrace/compact_live")):
            raise ValueError("current core/installed gates differ")
        deadline = datetime.fromisoformat(read(ROOT / "PREREGISTRATION.json")["autonomous_work_deadline"])
        predecessor = PROJECT / "artifacts/p11_cohort_live_v1/chain_after_p9_01/FINAL_STATUS.json"
        # The earlier controller does not share a lock. Wait until all its submissions end.
        while not predecessor.exists():
            if (deadline - datetime.now(timezone.utc)).total_seconds() < 1800:
                raise RuntimeError("window ended while waiting for predecessor dispatch")
            print({"at": now(), "waiting_for": "P11 submission controller completion"}, flush=True)
            time.sleep(30)
        if read(predecessor)["status"] != "submitted_registered_matrices":
            raise RuntimeError("P11 dispatch did not finish successfully; inspect retained claims")
        while len(passed) < 2:
            for profile in ("qwen3", "deepseek_r1"):
                if profile in passed:
                    continue
                if profile not in active:
                    if (deadline - datetime.now(timezone.utc)).total_seconds() < 1800:
                        raise RuntimeError("insufficient autonomous time for fresh hardware preflight")
                    try:
                        reservation = capacity.ensure(1)
                    except (ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
                        write(output / f"capacity_wait_{round_no:05d}_{profile}.json", {"at": now(), "error": str(exc)})
                        continue
                    write(output / f"capacity_before_{profile}.json", reservation)
                    execution = ROOT / ("execution_" + profile + "_preflight_01")
                    plan = package.freeze(PROJECT / "artifacts/p10_forecast_cohort_v1/execution_01",
                              ROOT / ("resources_" + profile + "_01"), execution, model_profile=profile, kind="preflight")
                    directory = ROOT / ("acp_" + profile + "_preflight_01")
                    submissions = launch.submit_phase(execution, directory)
                    if len(submissions) != 1 or submissions[0]["status"] != "submitted":
                        raise RuntimeError("preflight submission failed or uncertain; claim remains consumed")
                    active[profile] = {"job_id": submissions[0]["job_id"], "directory": directory,
                                       "plan": plan, "submitted_at": datetime.now(timezone.utc)}
                item = active[profile]
                argv = [acp.SCO, "acp", "jobs", "describe", "--workspace-name=share-space", "--format=json", item["job_id"]]
                try:
                    reply = subprocess.run(argv, capture_output=True, text=True, timeout=45, check=False)
                except subprocess.TimeoutExpired as exc:
                    write(output / "status" / f"{round_no:05d}_{profile}_timeout.json", {"at": now(), "error": str(exc)})
                    continue
                write(output / "status" / f"{round_no:05d}_{profile}.json", {"at": now(), "argv": argv,
                      "exit_code": reply.returncode, "stdout": reply.stdout, "stderr": reply.stderr})
                if reply.returncode:
                    continue
                details = strict_json(reply.stdout)
                print({"at": now(), "profile": profile, "job_id": item["job_id"], "state": details["state"]}, flush=True)
                if details["state"] not in provenance.TERMINAL:
                    if datetime.now(timezone.utc) > min(item["submitted_at"] + timedelta(minutes=35), deadline):
                        if profile not in stopped:
                            stopped.add(profile)
                            stop = [acp.SCO, "acp", "jobs", "stop", "--workspace-name=share-space", item["job_id"]]
                            write(output / (profile + "_stop_intent.json"), {"at": now(), "argv": stop})
                            result = subprocess.run(stop, capture_output=True, text=True, timeout=45, check=False)
                            write(output / (profile + "_stop_result.json"), {"at": now(), "exit_code": result.returncode,
                                  "stdout": result.stdout, "stderr": result.stderr})
                    continue
                directory = item["directory"] / "worker-0"
                request, result = read(directory / "request.json"), read(directory / "worker_result.json")
                job = provenance.job_record(details, request)
                proof = {"at": now(), "request": request, "result": result, "job": job,
                         "execution": item["plan"], "validation": {"status": "passed", "model_calls": 0,
                         "job_details_sha256": fingerprint(details)}}
                launch.validate_preflight(proof, item["plan"])
                proof["acceptance_id"] = fingerprint(proof)
                write(ROOT / ("PREFLIGHT_ACCEPTANCE_" + profile + ".json"), proof)
                passed[profile] = {"job_id": item["job_id"], "acceptance_id": proof["acceptance_id"]}
            round_no += 1
            if len(passed) < 2:
                time.sleep(30)
        final.update(status="passed", preflights=passed)
    except BaseException as exc:
        final["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        final.update(finished_at=now(), passed=passed,
                     submitted={name: item["job_id"] for name, item in active.items()})
        final["status_id"] = fingerprint(final)
        write(output / "FINAL_STATUS.json", final)
        print(final, flush=True)
    return 0 if final["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
