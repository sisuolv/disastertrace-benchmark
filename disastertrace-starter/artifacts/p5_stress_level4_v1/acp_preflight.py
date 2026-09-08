"""Inspect the real ACP H100 runtime with generation disabled and no live claim."""

import argparse
import os
import platform
import socket
import subprocess
import sys
import traceback
from pathlib import Path

from acp_common import runtime_env

from disastertrace.local_eval.storage import digest, now, read, write
from disastertrace.stress_eval import execution, runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    request = read(args.request)
    directory = args.request.parent
    if (
        digest(__file__) != request["worker_sha256"]
        or digest(Path(__file__).with_name("acp_common.py")) != request["common_sha256"]
    ):
        raise ValueError("preflight worker differs from submitted source")
    write(
        directory / "worker_started.json",
        {
            "at": now(),
            "hostname": socket.gethostname(),
            "python": platform.python_version(),
            "executable": sys.executable,
            "request_sha256": digest(args.request),
            "worker_sha256": digest(__file__),
            "pid": os.getpid(),
        },
    )
    result = {"status": "failed", "model_calls": 0, "generate_disabled": True}
    try:
        path = Path(request["execution_path"])
        env = runtime_env(path / "implementation_source/src", directory / "cache")
        os.environ.clear()
        os.environ.update(env)
        os.chdir(request["project"])
        plan, _, _ = execution.verify(path, model_hashes=True)
        observed_env = runtime.environment()
        write(directory / "observed_environment.json", observed_env)
        if observed_env != read(path / "environment.json"):
            raise ValueError("ACP Python/package inventory differs from frozen runtime")
        import torch
        from vllm import LLM

        def forbidden(*args, **kwargs):
            raise RuntimeError("model generation is disabled during preflight")

        LLM.generate = forbidden
        if torch.cuda.device_count() != 1 or "H100" not in torch.cuda.get_device_name(0):
            raise ValueError("one visible H100 required")
        if socket.gethostname() == request["source_cci_hostname"]:
            raise ValueError("computation must run on the ACP worker")
        backend = runtime.VLLMBackend(path, plan["settings"])
        smi = subprocess.run(["nvidia-smi"], capture_output=True, text=True, check=False)
        result.update(
            status="passed",
            execution_id=plan["execution_id"],
            gpu_model_loaded=True,
            visible_gpu_count=torch.cuda.device_count(),
            hostname=socket.gethostname(),
            runtime_observation=backend.observation,
            nvidia_smi=smi.stdout,
            nvidia_smi_exit_code=smi.returncode,
        )
    except BaseException as exc:  # noqa: BLE001 - preserve a terminal preflight failure record
        result["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        result.update(
            finished_at=now(), request_sha256=digest(args.request), worker_sha256=digest(__file__)
        )
        write(directory / "worker_result.json", result)
    print({k: v for k, v in result.items() if k != "nvidia_smi"}, flush=True)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
