"""Observe the four exact ACP jobs, then audit once; never submit or retry inference."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import time
import traceback

from disastertrace.carrier_repr import acp, package, provenance
from disastertrace.carrier_repr.storage import now, write
from disastertrace.forecast_task.common import digest, fingerprint, read, strict_json


def command(argv, logroot, name, env=None):
    write(logroot / (name + "_intent.json"), {"argv": argv, "at": now()})
    path = logroot / (name + ".log")
    with path.open("x") as stream:
        result = subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT, env=env, check=False)
    value = {"exit_code": result.returncode, "log_sha256": digest(path), "at": now()}
    write(logroot / (name + "_result.json"), value)
    if result.returncode:
        raise RuntimeError("finalization failed: " + name)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution", required=True, type=Path)
    parser.add_argument("--submissions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root, submissions, output = args.execution.resolve(), args.submissions.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    write(output / "observer_claim.json", {"pid": os.getpid(), "at": now(), "execution": str(root),
                                           "submissions": str(submissions), "script_sha256": digest(__file__)})
    plan, _, _ = package.verify(root, code=True)
    if plan["kind"] != "model":
        raise ValueError("live observer requires live execution")
    final = {"status": "failed", "execution_id": plan["execution_id"], "started_at": now()}
    try:
        phase = read(submissions / "phase.json")
        workers, stop_claims = {}, set()
        round_no = 0
        while True:
            complete, states = True, []
            for wid in range(4):
                directory = submissions / f"worker-{wid}"
                row = {"worker_id": wid}
                for name in ("request", "submission", "worker_started", "worker_result"):
                    if (directory / (name + ".json")).exists():
                        row[name] = read(directory / (name + ".json"))
                if "request" not in row:
                    workers[wid] = row
                    states.append({"worker": wid, "state": "unsubmitted"})
                    continue
                job_id = row.get("submission", {}).get("job_id")
                if job_id:
                    argv = [acp.SCO, "acp", "jobs", "describe", "--workspace-name=share-space", "--format=json", job_id]
                else:
                    argv = [acp.SCO, "acp", "jobs", "list", "--workspace-name=share-space", "--format=json",
                            "--display-name=" + row["request"]["display_name"], "--page-size=100"]
                record_path = output / "status" / f"{round_no:05d}-{wid}.json"
                try:
                    result = subprocess.run(argv, capture_output=True, text=True, timeout=45, check=False)
                    write(record_path, {"argv": argv, "at": now(), "exit_code": result.returncode,
                                        "stdout": result.stdout, "stderr": result.stderr})
                    if result.returncode:
                        raise RuntimeError("status query failed")
                    details = [] if not job_id and result.stdout.strip() == "No jobs found" else strict_json(result.stdout)
                    if not job_id:
                        exact = [j for j in details if j["display_name"] == row["request"]["display_name"]]
                        if len(exact) > 1:
                            raise ValueError("duplicate actual ACP display name")
                        if not exact:
                            complete = False
                            states.append({"worker": wid, "state": "submission_unknown_no_job_found"})
                            continue
                        details = exact[0]
                        job_id = details["name"]
                    observed = provenance.job_record(details, row["request"])
                    row["job_details"] = details
                    workers[wid] = row
                    states.append({"worker": wid, "job_id": job_id, "state": observed["state"]})
                    if not observed["released"]:
                        complete = False
                        if package.past_deadline(plan) and job_id not in stop_claims:
                            stop_claims.add(job_id)
                            stop_argv = [acp.SCO, "acp", "jobs", "stop", "--workspace-name=share-space", job_id]
                            write(output / (job_id + "_stop_intent.json"), {"argv": stop_argv, "at": now()})
                            stopped = subprocess.run(stop_argv, capture_output=True, text=True, timeout=45, check=False)
                            write(output / (job_id + "_stop_result.json"), {"exit_code": stopped.returncode,
                                  "stdout": stopped.stdout, "stderr": stopped.stderr, "at": now()})
                except (subprocess.TimeoutExpired, RuntimeError) as exc:
                    complete = False
                    states.append({"worker": wid, "state": "status_query_error", "error": str(exc)})
            print({"at": now(), "round": round_no, "workers": states}, flush=True)
            if complete:
                break
            # Status failures consume no inference claims. Never duplicate a worker to recover them.
            round_no += 1
            if datetime.now(timezone.utc).timestamp() > datetime.fromisoformat(plan["deadline_utc"]).timestamp() + 1800:
                raise RuntimeError("terminal-state observation incomplete after deadline and 30-minute status grace")
            time.sleep(30)
        run = Path(plan["run_root"])
        proof = {"execution_id": plan["execution_id"], "phase_id": plan["phase_id"],
                 "phase_claim": phase, "workers": [workers[i] for i in range(4)], "at": now()}
        write(run / "provenance.json", proof)
        env = acp.runtime_env(root / "source", output / "cpu_cache")
        env["CUDA_VISIBLE_DEVICES"] = ""
        report = output / "global_report.json"
        argv = [acp.CPU_PYTHON, "-u", "-m", "disastertrace.carrier_repr", "report", "--execution", str(root),
                "--run-root", str(run), "--output", str(report)]
        command(argv, output, "report", env)
        argv[4] = "verify-report"
        command(argv, output, "verify_report", env)
        command([acp.GPU_PYTHON, "-u", str(Path(__file__).with_name("replay_model_tokens.py")),
                 "--execution", str(root), "--run-root", str(run), "--output", str(output / "token_replay.json")],
                output, "token_replay", env)
        copied = output / "cpu_relocated"
        copied.mkdir()
        shutil.copytree(root, copied / "execution")
        shutil.copytree(run, copied / "run")
        shutil.copyfile(report, copied / "report.json")
        wrapper = Path(__file__).with_name("portable_review.py")
        shutil.copyfile(wrapper, copied / "portable_review.py")
        write(copied / "review_spec.json", [{"run": "run", "report": "report.json"}])
        command([acp.CPU_PYTHON, str(copied / "portable_review.py"), "--execution", str(copied / "execution"),
                 "--isolation-root", str(copied), "--blocked-root", str(Path(__file__).resolve().parents[2]),
                 "--blocked-root", "/mnt/afs/260010168/models", "--review-spec", str(copied / "review_spec.json"),
                 "--output", str(copied / "receipt.json")], output, "cpu_relocation", env)
        actual = read(report)
        final.update(status="passed", report_id=actual["report_id"], report_sha256=digest(report),
                     counts=actual["counts"], score_counts=actual["scores"]["counts"],
                     platform_jobs=actual["platform_jobs"],
                     token_replay_sha256=digest(output / "token_replay.json"),
                     cpu_relocation_sha256=digest(copied / "receipt.json"))
    except BaseException as exc:
        final["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        final["finished_at"] = now()
        final["status_id"] = fingerprint(final)
        write(output / "FINAL_STATUS.json", final)
    print(final, flush=True)
    return 0 if final["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
