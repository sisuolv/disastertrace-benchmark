"""ACP entrypoint: generation-disabled preflight or exactly one assigned native worker."""

import argparse
import math
import os
import socket
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.forecast_task.common import digest, fingerprint, read

from . import acp, package
from .storage import now, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    request, directory = read(args.request), args.request.resolve().parent
    write(
        directory / "worker_started.json",
        {
            "at": now(),
            "hostname": socket.gethostname(),
            "request_sha256": fingerprint(request),
            "pid": os.getpid(),
            "python": sys.executable,
        },
    )
    result = {
        "status": "failed",
        "generate_disabled": request["kind"] == "preflight",
        "request_sha256": fingerprint(request),
        "hostname": socket.gethostname(),
        "started_at": now(),
    }
    try:
        acp.check_mount()
        root = Path(request["execution_path"])
        env = acp.runtime_env(root / "source", directory / "cache")
        env["FORECAST_WORKER_REQUEST"] = str(args.request.resolve())
        os.environ.clear()
        os.environ.update(env)
        plan, _, slots = package.verify(root, code=True)
        phase = read(request["phase_claim"])
        if (
            request["execution_id"] != plan["execution_id"]
            or request["phase_id"] != plan["phase_id"]
            or request["source_files"] != plan["source_files"]
            or request["kind"] != plan["kind"]
            or fingerprint(phase) != request["phase_claim_sha256"]
            or phase["execution_id"] != plan["execution_id"]
            or str(directory.parent) != phase["submission_directory"]
            or directory.name != f"worker-{request['worker_id']}"
            or socket.gethostname() == request["source_cci_hostname"]
        ):
            raise ValueError("worker/request/phase/host binding differs")
        if request["kind"] == "preflight":
            if plan["generation_authorized"] or request["max_model_attempts"] != 0:
                raise ValueError("preflight cannot generate")
            import vllm
            from vllm.v1.engine.llm_engine import LLMEngine

            from .backend import VLLMBackend

            def forbidden(*args, **kwargs):
                raise RuntimeError("generation is disabled during native preflight")

            vllm.LLM.generate = forbidden
            LLMEngine.add_request = forbidden
            LLMEngine.step = forbidden
            backend = VLLMBackend(root)
            result.update(
                status="passed",
                model_calls=0,
                gpu_model_loaded=True,
                runtime_observation=backend.observation,
            )
            smi = subprocess.run(["nvidia-smi"], capture_output=True, text=True, check=False)
            result.update(nvidia_smi=smi.stdout, nvidia_smi_exit_code=smi.returncode)
            if smi.returncode:
                raise ValueError("nvidia-smi failed")
        elif request["kind"] == "model":
            from .launch import validate_cpu

            validate_cpu(read(root / "validation.json"), plan)
            planned = sum(s["worker_id"] == request["worker_id"] for s in slots)
            if request["max_model_attempts"] != planned or package.past_deadline(plan):
                raise ValueError("worker attempt cap or phase deadline differs")
            seconds = math.floor(
                (
                    datetime.fromisoformat(plan["deadline_utc"]) - datetime.now(timezone.utc)
                ).total_seconds()
            )
            command = [
                "timeout",
                "--signal=TERM",
                "--kill-after=15s",
                str(max(1, seconds - 15)) + "s",
                acp.GPU_PYTHON,
                "-u",
                "-m",
                "disastertrace.prompt_role_live",
                "collect",
                "--execution",
                str(root),
                "--run-root",
                plan["run_root"],
                "--worker",
                str(request["worker_id"]),
                "--mode",
                "model",
            ]
            write(directory / "collect_command.json", {"argv": command, "at": now()})
            with (directory / "collect.log").open("x") as stream:
                completed = subprocess.run(
                    command, stdout=stream, stderr=subprocess.STDOUT, env=env, check=False
                )
            result.update(
                status="passed" if completed.returncode == 0 else "failed",
                collector_exit_code=completed.returncode,
                planned_answers=planned,
                collect_log_sha256=digest(directory / "collect.log"),
            )
        else:
            raise ValueError("unsupported worker kind")
    except BaseException as exc:  # noqa: BLE001 - preserve worker failure evidence
        result["status"] = "failed"
        result["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        result["finished_at"] = now()
        write(directory / "worker_result.json", result)
    print(
        {k: v for k, v in result.items() if k not in ("nvidia_smi", "runtime_observation")},
        flush=True,
    )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
