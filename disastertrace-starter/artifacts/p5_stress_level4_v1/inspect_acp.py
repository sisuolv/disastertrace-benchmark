"""Save ACP job observations and verify an actual completed preflight."""

import argparse
import json
import subprocess
from pathlib import Path

from acp_common import CLUSTER, HERE, IMAGE, SCO, SPEC

from disastertrace.local_eval.storage import digest, now, read, write


def observe(directory):
    submitted = read(directory / "submission.json")
    job_id = submitted["job_id"]
    command = [
        SCO,
        "acp",
        "jobs",
        "describe",
        "--workspace-name=share-space",
        "--format=json",
        job_id,
    ]
    reply = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
    target = directory / "observations"
    target.mkdir(exist_ok=True)
    record = {"at": now(), "command": command, "exit_code": reply.returncode}
    if reply.returncode:
        record.update(stdout=reply.stdout, stderr=reply.stderr)
    else:
        record["job"] = json.loads(reply.stdout)
    path = target / (str(len(list(target.glob("*.json")))).zfill(4) + ".json")
    write(path, record)
    if reply.returncode:
        raise RuntimeError("ACP describe failed; inspect saved observation")
    job = record["job"]
    request = read(directory / "request.json")
    if (
        job["name"] != job_id
        or job["display_name"] != request["display_name"]
        or job["resource_pool"]["name"] != CLUSTER
    ):
        raise ValueError("ACP job identity/cluster mismatch")
    roles = job["roles"]
    if len(roles) != 1 or roles[0]["total_replicas"] != 1:
        raise ValueError("one worker node required")
    role = roles[0]
    if role["image_path"] != IMAGE or role["startup_script"] != request["command"]:
        raise ValueError("ACP command or image mismatch")
    specs = role["resource_spec"]
    if (
        len(specs) != 1
        or specs[0]["name"] != SPEC
        or specs[0]["limits"].get("nvidia.com/gpu") != "1"
    ):
        raise ValueError("one frozen H100 resource spec required")
    if job["fault_tolerance"]["backoff_limit"] != 0 or job["lme"]["max_retries"] != 0:
        raise ValueError("platform retries must be disabled")
    return job, path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--verify-preflight", action="store_true")
    args = parser.parse_args()
    job, observation = observe(args.directory)
    print({"job_id": job["name"], "state": job["state"], "observation": str(observation)})
    if args.verify_preflight:
        request = read(args.directory / "request.json")
        result = read(args.directory / "worker_result.json")
        if (
            job["state"] != "SUCCEEDED"
            or result["status"] != "passed"
            or result["model_calls"] != 0
            or not result["generate_disabled"]
            or not result["gpu_model_loaded"]
            or result["visible_gpu_count"] != 1
            or result["hostname"] == request["source_cci_hostname"]
            or result["request_sha256"] != digest(args.directory / "request.json")
            or result["worker_sha256"] != digest(HERE / "acp_preflight.py")
            or request["common_sha256"] != digest(HERE / "acp_common.py")
        ):
            raise ValueError("completed matching ACP preflight required")
        write(
            args.directory / "verified_job.json",
            {
                "status": "passed",
                "at": now(),
                "job_id": job["name"],
                "gpu_count": 1,
                "execution_id": result["execution_id"],
                "model_calls": 0,
                "result_sha256": digest(args.directory / "worker_result.json"),
                "observation_sha256": digest(observation),
                "observation": str(observation),
                "request_sha256": digest(args.directory / "request.json"),
            },
        )


if __name__ == "__main__":
    main()
