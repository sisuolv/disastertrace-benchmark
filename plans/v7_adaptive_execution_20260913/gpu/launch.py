"""Submit fresh bounded one-H100 workers with persisted, non-retryable intents."""

import argparse
import fcntl
import json
import re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from gpu_worker import digest, save

BASE = Path(__file__).resolve().parent
SCO = "/mnt/afs/260010168/bin/sco"
PYTHON = "/mnt/afs/260010168/.venvs/disastertrace-mm-vlm-v1/bin/python"
CLUSTER = "computing-cluster-01g-02"
SPEC = "N6lS.Iu.I10.1.8c128g"
IMAGE = "registry.cn-sh-01g.sensecore.cn/lepton-trainingjob/nvidia24.04-ubuntu22.04-py3.10-cuda12.4-cudnn9.1-torch2.3.0-transformerengine1.5:v1.0.0-20241130-nvdia-base-image"
TERMINAL = {"SUCCEEDED", "FAILED", "DELETED"}


def own_jobs():
    result = subprocess.run(
        [
            SCO,
            "acp",
            "jobs",
            "list",
            "--workspace-name=share-space",
            "--user-name=260010168",
            "--page-size=500",
            "--format=json",
        ],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    if result.returncode:
        raise ValueError("account job listing failed")
    jobs = json.loads(result.stdout)
    if len(jobs) >= 500 or any(
        x["ownership"]["user_name"] != "260010168" for x in jobs
    ):
        raise ValueError("account pagination or ownership is ambiguous")
    return jobs


def requested_gpus(job):
    total = 0
    for role in job["roles"]:
        specs = role["resource_spec"]
        if len(specs) != 1:
            raise ValueError("heterogeneous worker resources")
        count = int(specs[0]["requests"]["nvidia.com/gpu"])
        if count < 0 or int(specs[0]["limits"]["nvidia.com/gpu"]) != count:
            raise ValueError("GPU requests and limits differ")
        replicas = int(role["total_replicas"])
        if replicas < 0:
            raise ValueError("negative worker replicas")
        total += replicas * count
    return total


def main(batch):
    plan = json.loads((batch / "PLAN.json").read_text())
    expected = digest(batch / "PLAN.json")
    if not 0 < len(plan["workers"]) <= 4 or plan["max_concurrent_gpus"] != 4:
        raise ValueError("invalid four-GPU scope")
    for name, sha in plan["files"].items():
        if digest(batch / name) != sha:
            raise ValueError("frozen input changed: " + name)
    mount = subprocess.check_output(
        ["findmnt", "-n", "-T", str(batch), "-o", "TARGET,FSTYPE"],
        text=True,
    ).split()
    if mount != ["/mnt/afs", "fuse.quarkfs_client"]:
        raise ValueError("AFS mapping changed")
    submissions = batch / "submissions"
    submissions.mkdir(exist_ok=False)
    with (BASE / "submission.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        confirmed = {}
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%Sz")
        for worker in plan["workers"]:
            jobs = own_jobs()
            observed = {j["name"]: j for j in jobs}
            # Include locally confirmed submissions if listing visibility lags.
            all_known = {**confirmed, **observed}
            active = [j for j in all_known.values() if j["state"] not in TERMINAL]
            count = sum(requested_gpus(j) for j in active)
            if count + 1 > 4:
                raise ValueError("four-GPU account cap would be exceeded")
            slot = submissions / worker
            slot.mkdir(exist_ok=False)
            save(
                slot / "ACCOUNT_BEFORE.json",
                {"active_requested_gpus": count, "jobs": active},
            )
            name = "dtv7-adaptive-dev-" + stamp + "-w" + worker
            command = [
                "timeout",
                "--signal=TERM",
                "--kill-after=60",
                str(plan["max_worker_seconds"]) + "s",
                "env",
                "HF_HUB_OFFLINE=1",
                "TRANSFORMERS_OFFLINE=1",
                "TOKENIZERS_PARALLELISM=false",
                "PYTHONDONTWRITEBYTECODE=1",
                "PYTHONHASHSEED=20260912",
                "OMP_NUM_THREADS=4",
                "PYTHONPATH=" + str(batch / "source"),
                PYTHON,
                "-u",
                str(batch / "source/gpu_worker.py"),
                "--batch",
                str(batch),
                "--plan-sha",
                expected,
                "--worker",
                worker,
            ]
            runner = slot / "run.sh"
            runner.write_text(
                "#!/usr/bin/env bash\nset -euo pipefail\n"
                + shlex.join(command)
                + " > "
                + shlex.quote(str(batch / ("worker-" + worker + ".log")))
                + " 2>&1\n"
            )
            argv = [
                SCO,
                "acp",
                "jobs",
                "create",
                "--workspace-name=share-space",
                "--aec2-name=" + CLUSTER,
                "--job-name=" + name,
                "--container-image-url=" + IMAGE,
                "--training-framework=pytorch",
                "--worker-nodes=1",
                "--worker-spec=" + SPEC,
                "--storage-mount=01a04263-91e5-7603-bc01-c67e503da6b5:/mnt/afs",
                "--quota-type=reserved",
                "--priority=NORMAL",
                "--retry-times=0",
                "--command=bash " + shlex.quote(str(runner)),
            ]
            save(
                slot / "INTENT.json",
                {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "worker": worker,
                    "display_name": name,
                    "requested_gpus": 1,
                    "argv": argv,
                    "plan_sha256": expected,
                    "runner_sha256": digest(runner),
                    "command": command,
                },
            )
            try:
                response = subprocess.run(
                    argv, capture_output=True, text=True, timeout=90, check=False
                )
            except subprocess.TimeoutExpired:
                save(
                    slot / "UNKNOWN.json",
                    {
                        "display_name": name,
                        "reason": "submission CLI timeout; reconcile by name; never duplicate",
                    },
                )
                raise
            save(
                slot / "RESPONSE.json",
                {
                    "returncode": response.returncode,
                    "stdout": response.stdout,
                    "stderr": response.stderr,
                },
            )
            match = re.search(
                r"job (pt-[a-z0-9]+) submitted successfully", response.stdout
            )
            if response.returncode or not match:
                raise ValueError(
                    "submission not confirmed; reconcile unique display name: " + name
                )
            job_id = match.group(1)
            (slot / "job-id.txt").write_text(job_id + "\n")
            result = subprocess.run(
                [
                    SCO,
                    "acp",
                    "jobs",
                    "describe",
                    "--workspace-name=share-space",
                    "--format=json",
                    job_id,
                ],
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            if result.returncode:
                raise ValueError("accepted job needs reconciliation: " + job_id)
            job = json.loads(result.stdout)
            save(slot / "ACCEPTED.json", job)
            if requested_gpus(job) != 1 or job["resource_pool"]["name"] != CLUSTER:
                raise ValueError(
                    "accepted resource request differs from one H100: " + job_id
                )
            confirmed[job["name"]] = job
            print(
                json.dumps(
                    {
                        "worker": worker,
                        "job_id": job_id,
                        "state": job["state"],
                        "requested_gpus": 1,
                        "cluster": CLUSTER,
                    }
                ),
                flush=True,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    main(parser.parse_args().batch.resolve())
