"""One-use CPU continuation: verify the worker, reconstruct, then acquire the bounded sources."""

import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from disastertrace.automated.common import fingerprint, strict_json
from disastertrace.local_eval.storage import digest, now, read, write

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
CPU = "/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1/bin/python"
GPU_ENV_CPU_ONLY = "/mnt/afs/260010168/.venvs/disastertrace-qwen3-v1/bin/python"


def main():
    directory = HERE / "finalization_001"
    directory.mkdir(parents=True, exist_ok=False)
    write(
        directory / "claim.json",
        {
            "at": now(),
            "pid": os.getpid(),
            "script_sha256": digest(__file__),
            "no_model_dispatch": True,
            "no_gpu_submission": True,
        },
    )
    execution = HERE / "execution_live_02"
    plan = read(execution / "execution.json")
    worker = HERE / "acp/model"
    run = Path(plan["run_path"])
    report = HERE / "reports/model"
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(part in k.upper() for part in ("TOKEN", "SECRET", "API_KEY", "PASSWORD"))
    }
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONNOUSERSITE="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        CUDA_VISIBLE_DEVICES="",
        PYTHONPATH=str(execution / "implementation_source/src"),
        TOKENIZERS_PARALLELISM="false",
    )
    steps, result = [], {"status": "failed", "additional_model_calls": 0, "new_gpu_jobs": 0}

    def command(name, argv, child_env=env, timeout=1800):
        folder = directory / name
        folder.mkdir(exist_ok=False)
        write(folder / "intent.json", {"argv": argv, "at": now(), "timeout_seconds": timeout})
        start = time.monotonic()
        with (folder / "output.log").open("x") as stream:
            completed = subprocess.run(
                argv,
                cwd=PROJECT,
                env=child_env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
        value = {
            "name": name,
            "exit_code": completed.returncode,
            "wall_seconds": time.monotonic() - start,
            "log_sha256": digest(folder / "output.log"),
            "finished_at": now(),
        }
        write(folder / "result.json", value)
        steps.append(value)
        print(value, flush=True)
        if completed.returncode:
            raise RuntimeError("CPU continuation step failed: " + name)

    try:
        stop_wait = datetime.fromisoformat(plan["deadline_utc"]) + timedelta(hours=1)
        while not (worker / "worker_result.json").exists():
            if datetime.now(timezone.utc) > stop_wait:
                raise TimeoutError(
                    "worker did not publish completion by the bounded observation deadline"
                )
            time.sleep(15)
        worker_result, request, submitted = (
            read(worker / name)
            for name in ("worker_result.json", "request.json", "submission.json")
        )
        if (
            worker_result["request_sha256"] != fingerprint(request)
            or submitted["request_sha256"] != digest(worker / "request.json")
            or request["execution_id"] != plan["execution_id"]
        ):
            raise ValueError("worker/submission binding differs")
        query = [
            "/mnt/afs/260010168/bin/sco",
            "acp",
            "jobs",
            "describe",
            "--workspace-name=share-space",
            "--format=json",
            submitted["job_id"],
        ]
        for index in range(12):
            completed = subprocess.run(
                query, capture_output=True, text=True, timeout=45, check=False
            )
            write(
                directory / f"job_status_{index:02d}.json",
                {
                    "argv": query,
                    "at": now(),
                    "exit_code": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                },
            )
            if completed.returncode:
                raise RuntimeError("ACP final status query failed")
            job = strict_json(completed.stdout)
            if job["state"] not in ("RUNNING", "PENDING", "CREATING"):
                break
            time.sleep(15)
        role = job["roles"][0]
        spec = role["resource_spec"][0]
        if (
            job["name"] != submitted["job_id"]
            or job["display_name"] != request["display_name"]
            or job["resource_pool"]["name"] != "computing-cluster-01g-02"
            or len(job["roles"]) != 1
            or len(role["resource_spec"]) != 1
            or spec["name"] != "N6lS.Iu.I10.1.8c128g"
            or spec["replicas"] != 1
            or spec["limits"]["nvidia.com/gpu"] != "1"
            or role["total_replicas"] != 1
            or role["startup_script"] != request["command"]
            or job["fault_tolerance"]["backoff_limit"] != 0
        ):
            raise ValueError("actual model job differs from the frozen one-GPU request")
        write(
            HERE / "MODEL_JOB_OBSERVED.json",
            {
                "job": job,
                "worker": worker_result,
                "observed_at": now(),
                "all_worker_steps_passed": all(
                    s["exit_code"] == 0 for s in worker_result.get("steps", [])
                ),
            },
        )
        if not report.exists():
            command(
                "01_report_stopped_prefix",
                [
                    CPU,
                    "-m",
                    "disastertrace.repeat_live.cli",
                    "report",
                    "--execution",
                    str(execution),
                    "--run",
                    str(run),
                    "--output",
                    str(report),
                ],
            )
        command(
            "02_verify_model_report",
            [
                CPU,
                "-m",
                "disastertrace.repeat_live.cli",
                "verify-report",
                "--execution",
                str(execution),
                "--run",
                str(run),
                "--output",
                str(report),
            ],
        )
        command(
            "03_token_mask_replay",
            [
                GPU_ENV_CPU_ONLY,
                "-m",
                "disastertrace.repeat_live.grammar",
                "--execution",
                str(execution),
                "--run",
                str(run),
                "--output",
                str(HERE / "grammar_model"),
            ],
        )
        command("04_model_attribution", [CPU, str(HERE / "analyze_model.py")])
        copied = PROJECT / "work/p6-live-portable-review-v1"
        copied.mkdir(parents=True, exist_ok=False)
        for source, name in ((execution, "execution"), (run, "run"), (report, "report")):
            shutil.copytree(source, copied / name)
        portable_env = {**env, "PYTHONPATH": str(copied / "execution/implementation_source/src")}
        command(
            "05_cpu_relocation",
            [
                CPU,
                "-m",
                "disastertrace.repeat_live.portable",
                "--copy",
                str(copied),
                "--original-project",
                str(PROJECT),
                "--model-directory",
                "/mnt/afs/260010168/models/Qwen3-8B-modelscope-pinned-v1",
                "--output",
                str(copied / "CPU_RELOCATION.json"),
            ],
            portable_env,
        )
        shutil.copyfile(copied / "CPU_RELOCATION.json", HERE / "CPU_RELOCATION.json")
        project_env = {**env, "PYTHONPATH": str(PROJECT / "src")}
        command(
            "06_historical_acceptance",
            [
                str(PROJECT / ".venv/bin/python"),
                str(PROJECT / "artifacts/p6_offline_v1/accept_offline.py"),
                "--verify",
            ],
            project_env,
        )
        source_bundle = PROJECT / "artifacts/nhc_forecast_source_v1"
        source_env = {**env, "PYTHONPATH": str(source_bundle / "acquisition_source/src")}
        command(
            "07_nhc_acquisition",
            [
                CPU,
                "-m",
                "disastertrace.forecast_source.pipeline",
                "acquire",
                "--bundle",
                str(source_bundle),
            ],
            source_env,
            timeout=600,
        )
        source_report = source_bundle / "review_v1"
        command(
            "08_nhc_consensus",
            [
                CPU,
                "-m",
                "disastertrace.forecast_source.pipeline",
                "review",
                "--bundle",
                str(source_bundle),
                "--output",
                str(source_report),
            ],
            source_env,
        )
        command(
            "09_nhc_verify",
            [
                CPU,
                "-m",
                "disastertrace.forecast_source.pipeline",
                "verify",
                "--bundle",
                str(source_bundle),
                "--output",
                str(source_report),
            ],
            source_env,
        )
        result.update(
            status="passed",
            model_report=read(report / "audit.json")["audit_id"],
            model_complete=read(report / "audit.json")["complete"],
            nhc_admitted_bodies=read(source_report / "report.json")["admitted_bodies"],
        )
    except BaseException as exc:  # noqa: BLE001 - preserve partial CPU continuation evidence
        result["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        result.update(finished_at=now(), steps=steps)
        write(directory / "result.json", result)
    print(result, flush=True)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
