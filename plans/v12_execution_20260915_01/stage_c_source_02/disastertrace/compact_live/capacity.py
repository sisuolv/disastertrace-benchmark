"""Count pending reservations as well as running GPUs before every new phase."""

import subprocess

from disastertrace.forecast_task.common import strict_json

from . import acp
from .storage import now

TERMINAL = {"SUCCEEDED", "FAILED", "DELETED", "SUSPENDED"}


def occupied(jobs):
    if len(jobs) >= 100 or len({j["name"] for j in jobs}) != len(jobs):
        raise ValueError("ambiguous or paginated capacity listing")
    count = 0
    for job in jobs:
        if job["state"] in TERMINAL:
            continue
        if not job["roles"]:
            raise ValueError("active job lacks a reservation description")
        for role in job["roles"]:
            if len(role["resource_spec"]) != 1:
                raise ValueError("heterogeneous active reservation requires explicit accounting")
            spec = role["resource_spec"][0]
            running, requested = spec["replicas"], role["total_replicas"]
            if any(type(v) is not int or v < 0 for v in (running, requested)):
                raise ValueError("invalid replica metadata")
            gpus = max(
                int(spec["requests"].get("nvidia.com/gpu", "0")),
                int(spec["limits"].get("nvidia.com/gpu", "0")),
            )
            if gpus < 0 or (spec["name"] == acp.SPEC and gpus != 1):
                raise ValueError("GPU resource metadata differs")
            # ACP reports running replicas as zero while a one-node reservation is STARTING.
            count += gpus * max(1, running, requested)
    return count


def ensure(additional):
    if type(additional) is not int or not 1 <= additional <= 4:
        raise ValueError("invalid additional GPU reservation")
    argv = [
        acp.SCO,
        "acp",
        "jobs",
        "list",
        "--workspace-name=share-space",
        "--user-name=260010168",
        "--format=json",
        "--page-size=100",
    ]
    result = subprocess.run(argv, capture_output=True, text=True, timeout=45, check=False)
    if result.returncode:
        raise RuntimeError("capacity query failed")
    jobs = [] if result.stdout.strip() == "No jobs found" else strict_json(result.stdout)
    count = occupied(jobs)
    if count + additional > 4:
        raise ValueError("new phase would exceed four active or pending GPU reservations")
    return {
        "at": now(),
        "argv": argv,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "reserved_gpu_before": count,
        "additional_gpu": additional,
    }
