"""One-use local235 launch after the previous four-GPU task is terminal."""

import argparse
import datetime as dt
import json
import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    predecessor = parser.add_mutually_exclusive_group(required=True)
    predecessor.add_argument("--after-batch", type=Path)
    predecessor.add_argument("--after-submission", type=Path)
    args = parser.parse_args()
    batch = args.batch.absolute()
    previous_submission = (
        args.after_submission.absolute()
        if args.after_submission is not None
        else args.after_batch.absolute() / "gpu/submission_01"
    )
    plan = read(batch / "PLAN.json")
    qualification = read(batch / plan["scorer_preflight_required"])
    if (
        not qualification["passed"]
        or qualification["plan_sha256"] != digest(batch / "PLAN.json")
        or qualification["scorer_sha256"] != digest(batch / plan["scorer_source"])
    ):
        raise ValueError("Frozen scorer qualification required")
    publish(
        batch / "LAUNCH_INTENT.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "plan_sha256": digest(batch / "PLAN.json"),
            "predecessor": str(previous_submission),
            "max_simultaneous_h100": 4,
        },
    )
    latest = dt.datetime.fromisoformat(plan["late_start_cutoff"])
    previous_job = read(previous_submission / "JOB.json")["job_id"]
    while True:
        if dt.datetime.now(dt.timezone.utc) >= latest:
            publish(
                batch / "LATE_START_STOP.json",
                {"job_submitted": False, "model_calls": 0},
            )
            raise SystemExit(124)
        if (previous_submission / "EXIT.json").exists():
            query = [
                "/mnt/afs/260010168/bin/sco",
                "acp",
                "jobs",
                "describe",
                "--workspace-name=share-space",
                "--format=json",
                previous_job,
            ]
            observed = subprocess.run(
                query, capture_output=True, text=True, check=False, timeout=30
            )
            if observed.returncode == 0:
                state = json.loads(observed.stdout)
                if state.get("state") in {
                    "SUCCEEDED",
                    "FAILED",
                    "CANCELED",
                    "CANCELLED",
                    "STOPPED",
                } and state.get("complete_time"):
                    publish(batch / "PREVIOUS_GPU_TERMINAL.json", state)
                    break
        time.sleep(20)
    for rel, sha in plan["files"].items():
        if digest(batch / rel) != sha:
            raise ValueError("Local235 source/data changed while waiting")
    gpu = batch / "gpu"
    gpu.mkdir(exist_ok=False)
    shutil.copytree(batch / "policy", gpu / "policy")
    (gpu / "source").mkdir()
    shutil.copyfile(batch / plan["gpu_worker_source"], gpu / "source/worker.py")
    shutil.copyfile(batch / "MODEL_MANIFEST.json", gpu / "MODEL_MANIFEST.json")
    local_plan = {
        "model": plan["local_model"],
        "model_directory": read(batch / "MODEL_MANIFEST.json")["directory"],
        "tasks": [{**task, "worker": 0} for task in plan["tasks"]],
        "generation": {"seed": 20260914, "thinking": False, "temperature": 0},
        "input_token_cap": plan["input_token_cap"],
        "max_tokens": plan["max_tokens"],
        "batch_size": plan["batch_size"],
        "engine": plan["gpu_engine"],
        "last_worker_time": plan["last_worker_time"],
        "parent_plan_sha256": digest(batch / "PLAN.json"),
    }
    publish(gpu / "PLAN.json", local_plan)
    publish(
        gpu / "QUALIFICATION.json",
        {
            "runtime_versions": plan["gpu_runtime"],
            "frozen_files": {
                str(p.relative_to(gpu)): digest(p)
                for p in gpu.rglob("*")
                if p.is_file()
            },
        },
    )
    submission = gpu / "submission_01"
    submission.mkdir()
    epoch = int(dt.datetime.fromisoformat(plan["last_worker_time"]).timestamp())
    python = "/mnt/afs/260010168/.venvs/disastertrace-qwen3-v1/bin/python"
    worker = [
        "env",
        "HF_HUB_OFFLINE=1",
        "TRANSFORMERS_OFFLINE=1",
        "PYTHONDONTWRITEBYTECODE=1",
        "VLLM_WORKER_MULTIPROC_METHOD=spawn",
        "TOKENIZERS_PARALLELISM=false",
        "OMP_NUM_THREADS=4",
        python,
        str(gpu / "source/worker.py"),
        "--batch",
        str(gpu),
    ]
    script = (
        "#!/usr/bin/env bash\nset -uo pipefail\n"
        f"remaining_seconds=$(({epoch} - $(date -u +%s)))\n"
        'if [ "$remaining_seconds" -le 0 ]; then exit 124; fi\n'
        'timeout --signal=TERM --kill-after=30 "${remaining_seconds}s" '
        + shlex.join(worker)
        + " > "
        + shlex.quote(str(gpu / "worker.log"))
        + " 2>&1\n"
        'worker_exit=$?\nprintf \'{"exit_code":%s}\\n\' "$worker_exit" > '
        + shlex.quote(str(submission / "EXIT.json"))
        + '\nexit "$worker_exit"\n'
    )
    (submission / "bounded.sh").write_text(script)
    arguments = read(previous_submission / "CREATE_ARGUMENTS.json")
    name = "dt-v10-qwen235-features-" + dt.datetime.now(dt.timezone.utc).strftime(
        "%H%M%S"
    )
    arguments = [
        "--job-name=" + name
        if arg.startswith("--job-name=")
        else "--command=bash " + shlex.quote(str(submission / "bounded.sh"))
        if arg.startswith("--command=")
        else arg
        for arg in arguments
    ]
    publish(submission / "CREATE_ARGUMENTS.json", arguments)
    try:
        response = subprocess.run(
            arguments, capture_output=True, text=True, timeout=90, check=False
        )
    except subprocess.TimeoutExpired:
        publish(
            submission / "SUBMISSION_UNKNOWN.json", {"job_name": name, "retries": 0}
        )
        raise
    publish(
        submission / "CREATE_RESPONSE.json",
        {
            "returncode": response.returncode,
            "stdout": response.stdout,
            "stderr": response.stderr,
        },
    )
    match = re.search(r"job (pt-[a-z0-9]+) submitted successfully", response.stdout)
    if response.returncode or not match:
        raise RuntimeError("GPU submission not confirmed; do not automatically retry")
    publish(
        submission / "JOB.json", {"job_id": match.group(1), "job_name": name, "gpus": 4}
    )
    audit_command = [
        python,
        str(batch / "source/finalize_feature_temperature.py"),
        "--batch",
        str(batch),
        "--out",
        str(batch / "final_audit_01"),
        "--wait-seconds",
        str(max(1, epoch - int(time.time()))),
    ]
    with (batch / "finalizer.log").open("x") as log:
        audit = subprocess.Popen(
            audit_command,
            env=dict(
                os.environ,
                PYTHONPATH=str(batch / "source"),
                PYTHONDONTWRITEBYTECODE="1",
                HF_HUB_OFFLINE="1",
                TRANSFORMERS_OFFLINE="1",
                TOKENIZERS_PARALLELISM="false",
            ),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    publish(
        batch / "FINALIZER_LAUNCH.json",
        {"pid": audit.pid, "command": audit_command, "model_calls": 0},
    )
    print(
        json.dumps(
            {
                "gpu_job": match.group(1),
                "gpus": 4,
                "predecessor_terminal_verified": True,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
