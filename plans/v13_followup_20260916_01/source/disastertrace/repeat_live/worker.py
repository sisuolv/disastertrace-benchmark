"""One ACP worker claim: generation-disabled load or one bounded matrix."""

import argparse
import os
import socket
import subprocess
import sys
import traceback
from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.local_eval.storage import digest, now, read
from disastertrace.repeat_eval.storage import atomic_write

from . import acp, package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    request, directory = read(args.request), args.request.resolve().parent
    atomic_write(
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
    }
    try:
        acp.check_mount()
        path = Path(request["execution_path"])
        env = acp.runtime_env(path / "implementation_source/src", directory / "cache")
        os.environ.clear()
        os.environ.update(env)
        os.chdir(request["project"])
        plan, _, _ = package.verify(path)
        if (
            plan["execution_id"] != request["execution_id"]
            or package.source_inventory() != request["implementation_files"]
            or socket.gethostname() == request["source_cci_hostname"]
        ):
            raise ValueError("worker/request binding or actual ACP host differs")
        if request["kind"] == "preflight":
            if plan["generation_authorized"] or request["max_model_attempts"] != 0:
                raise ValueError("preflight cannot generate")
            import vllm
            from vllm.v1.engine.llm_engine import LLMEngine

            from .backend import VLLMBackend

            def forbidden(*args, **kwargs):
                raise RuntimeError("generation is disabled during preflight")

            vllm.LLM.generate = forbidden
            LLMEngine.add_request = forbidden
            LLMEngine.step = forbidden
            backend = VLLMBackend(path, plan["settings"])
            result.update(
                status="passed",
                model_calls=0,
                gpu_model_loaded=True,
                runtime_observation=backend.observation,
            )
            smi = subprocess.run(["nvidia-smi"], capture_output=True, text=True, check=False)
            result.update(nvidia_smi=smi.stdout, nvidia_smi_exit_code=smi.returncode)
        elif request["kind"] == "model":
            from .launch import validate_acceptance

            acceptance_path = Path(request["acceptance_path"])
            if digest(acceptance_path) != request["acceptance_sha256"]:
                raise ValueError("launcher acceptance changed")
            validate_acceptance(path, read(acceptance_path))
            if not plan["generation_authorized"] or request["max_model_attempts"] != 2160:
                raise ValueError("model scope differs")
            run, report = Path(plan["run_path"]), Path(request["report_path"])
            steps = []
            commands = [
                (
                    "collect",
                    acp.GPU_PYTHON,
                    ["collect", "--execution", str(path), "--run", str(run), "--mode", "model"],
                ),
                (
                    "report",
                    acp.CPU_PYTHON,
                    [
                        "report",
                        "--execution",
                        str(path),
                        "--run",
                        str(run),
                        "--output",
                        str(report),
                    ],
                ),
                (
                    "verify",
                    acp.CPU_PYTHON,
                    [
                        "verify-report",
                        "--execution",
                        str(path),
                        "--run",
                        str(run),
                        "--output",
                        str(report),
                    ],
                ),
            ]
            for name, python, arguments in commands:
                command = [python, "-u", "-m", "disastertrace.repeat_live.cli", *arguments]
                if name == "collect":
                    command = [
                        "timeout",
                        "--signal=TERM",
                        "--kill-after=60s",
                        str(plan["max_worker_seconds"]) + "s",
                        *command,
                    ]
                atomic_write(directory / (name + "_command.json"), {"argv": command, "at": now()})
                log = directory / (name + ".log")
                with log.open("x") as stream:
                    completed = subprocess.run(
                        command, stdout=stream, stderr=subprocess.STDOUT, env=env, check=False
                    )
                row = {
                    "name": name,
                    "exit_code": completed.returncode,
                    "log_sha256": digest(log),
                    "at": now(),
                }
                atomic_write(directory / (name + "_result.json"), row)
                steps.append(row)
            result.update(
                status="passed" if all(s["exit_code"] == 0 for s in steps) else "failed",
                steps=steps,
                model_attempt_cap=2160,
            )
        else:
            raise ValueError("unknown worker kind")
    except BaseException as exc:  # noqa: BLE001 - preserve terminal worker failures
        result["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        result["finished_at"] = now()
        atomic_write(directory / "worker_result.json", result)
    print(
        {k: v for k, v in result.items() if k not in ("nvidia_smi", "runtime_observation")},
        flush=True,
    )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
