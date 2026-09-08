"""Persistent, non-retrying ACP submission with explicit job identities."""

import os
import re
import shlex
import socket
import subprocess

from disastertrace.forecast_task.common import digest

from .storage import now, write

SCO = "/mnt/afs/260010168/bin/sco"
GPU_PYTHON = "/mnt/afs/260010168/.venvs/disastertrace-qwen3-v1/bin/python"
CPU_PYTHON = "/mnt/afs/260010168/.venvs/disastertrace-p4-review-cpu-v1/bin/python"
CLUSTER = "computing-cluster-01g-02"
SPEC = "N6lS.Iu.I10.1.8c128g"
IMAGE = (
    "registry.cn-sh-01g.sensecore.cn/lepton-trainingjob/"
    "nvidia24.04-ubuntu22.04-py3.10-cuda12.4-cudnn9.1-torch2.3.0-"
    "transformerengine1.5:v1.0.0-20241130-nvdia-base-image"
)


def check_mount():
    observed = subprocess.check_output(
        ["findmnt", "-n", "-T", "/mnt/afs/260010168", "-o", "TARGET,FSTYPE"], text=True
    ).split()
    if observed != ["/mnt/afs", "fuse.quarkfs_client"]:
        raise ValueError("AFS mount differs; do not create a local substitute")


def runtime_env(source, cache):
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(part in k.upper() for part in ("TOKEN", "SECRET", "API_KEY", "PASSWORD"))
    }
    env.update(
        PYTHONPATH=str(source),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONNOUSERSITE="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        TOKENIZERS_PARALLELISM="false",
        VLLM_NO_USAGE_STATS="1",
        VLLM_WORKER_MULTIPROC_METHOD="spawn",
        VLLM_USE_V1="1",
        VLLM_ENABLE_V1_MULTIPROCESSING="0",
        OMP_NUM_THREADS="8",
        XDG_CACHE_HOME=str(cache),
        VLLM_CACHE_ROOT=str(cache / "vllm"),
        TRITON_CACHE_DIR=str(cache / "triton"),
    )
    return env


def command_for(request_path, source, seconds):
    arguments = [
        "env",
        "PYTHONDONTWRITEBYTECODE=1",
        "PYTHONNOUSERSITE=1",
        "PYTHONPATH=" + str(source),
        "timeout",
        "--signal=TERM",
        "--kill-after=60s",
        str(seconds) + "s",
        GPU_PYTHON,
        "-u",
        "-m",
        "disastertrace.cohort_live.worker",
        "--request",
        str(request_path),
    ]
    return shlex.join(arguments)


def submit(directory, request):
    """A durable request consumes submission, including ambiguous CLI failures."""
    check_mount()
    directory.mkdir(parents=True, exist_ok=False)
    request = {**request, "source_cci_hostname": socket.gethostname(), "created_at": now()}
    write(directory / "request.json", request)
    args = [
        SCO,
        "acp",
        "jobs",
        "create",
        "--workspace-name=share-space",
        "--aec2-name=" + CLUSTER,
        "--job-name=" + request["display_name"],
        "--container-image-url=" + IMAGE,
        "--training-framework=pytorch",
        "--worker-nodes=1",
        "--worker-spec=" + SPEC,
        "--storage-mount=01a04263-91e5-7603-bc01-c67e503da6b5:/mnt/afs",
        "--quota-type=reserved",
        "--priority=NORMAL",
        "--retry-times=0",
        "--command=" + request["command"],
    ]
    write(directory / "create_argv.json", args)
    try:
        reply = subprocess.run(args, capture_output=True, text=True, timeout=90, check=False)
    except subprocess.TimeoutExpired:
        write(
            directory / "submission_unknown.json",
            {
                "at": now(),
                "display_name": request["display_name"],
                "reason": "CLI timeout; query this exact display name before any further action",
            },
        )
        raise
    write(
        directory / "submission_response.json",
        {
            "at": now(),
            "returncode": reply.returncode,
            "stdout": reply.stdout,
            "stderr": reply.stderr,
        },
    )
    match = re.search(r"job (pt-[a-z0-9]+) submitted successfully", reply.stdout)
    if reply.returncode or not match:
        raise RuntimeError("Inspect saved submission response; never automatically resubmit")
    result = {
        "job_id": match.group(1),
        "at": now(),
        "display_name": request["display_name"],
        "request_sha256": digest(directory / "request.json"),
        "cluster": CLUSTER,
        "gpu_count": 1,
    }
    write(directory / "submission.json", result)
    print(result, flush=True)
    return result
