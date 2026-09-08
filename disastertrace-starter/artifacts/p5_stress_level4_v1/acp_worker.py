"""Run one frozen factor once, then audit even a stopped collection prefix."""

import argparse
import os
import socket
import subprocess
import traceback
from pathlib import Path

from acp_common import CPU_PYTHON, GPU_PYTHON, HERE, PROJECT, runtime_env
from launch_p5 import validate

from disastertrace.local_eval.storage import digest, now, read, write


def run_commands(commands, directory, env, *, runner=subprocess.run):
    outcomes = []
    for name, command in commands:
        started = now()
        write(directory / (name + "_intent.json"), {"command": command, "started_at": started})
        log = directory / (name + ".log")
        with log.open("xb") as stream:
            result = runner(
                command, cwd=PROJECT, env=env, stdout=stream, stderr=subprocess.STDOUT, check=False
            )
        outcome = {
            "step": name,
            "command": command,
            "started_at": started,
            "finished_at": now(),
            "exit_code": result.returncode,
            "log_sha256": digest(log),
        }
        write(directory / (name + "_result.json"), outcome)
        outcomes.append(outcome)
        print(outcome, flush=True)
        if result.returncode and name != "collect":
            break
    return outcomes


def commands_for(path, run, output):
    report = [
        CPU_PYTHON,
        "-m",
        "disastertrace.stress_eval.cli",
        "report",
        "--execution",
        str(path),
        "--run",
        str(run),
        "--output",
        str(output),
        "--require-model",
    ]
    return [
        (
            "collect",
            [
                GPU_PYTHON,
                "-m",
                "disastertrace.stress_eval.cli",
                "collect",
                "--execution",
                str(path),
                "--output",
                str(run),
            ],
        ),
        ("report", report),
        ("verify_report", report + ["--verify"]),
    ]


def worker(request_path):
    request = read(request_path)
    directory = request_path.parent
    if (
        request["worker_sha256"] != digest(__file__)
        or request["common_sha256"] != digest(HERE / "acp_common.py")
        or request["acceptance_sha256"] != digest(HERE / "LIVE_ACCEPTANCE.json")
        or request["phase_launch_sha256"] != digest(directory.parent / "launch.json")
    ):
        raise ValueError("worker/request/phase binding mismatch")
    write(
        directory / "worker_claim.json",
        {
            "at": now(),
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "request_sha256": digest(request_path),
            "worker_sha256": digest(__file__),
            "execution_id": request["execution_id"],
            "one_use": True,
        },
    )
    outcomes = []
    result = {"status": "failed", "outcomes": outcomes}
    try:
        plans, accepted = validate(fresh=False)
        factor = request["factor"]
        plan = plans[factor]
        path = HERE / "units" / factor / "execution_live"
        if (
            request["execution_id"] != plan["execution_id"]
            or request["execution_path"] != str(path)
            or request["run_path"] != plan["run_path"]
            or request["max_model_responses"] != 540
            or request["maximum_gpus"] != 1
            or Path(plan["run_path"]).exists()
        ):
            raise ValueError("fresh canonical factor request required")
        env = runtime_env(path / "implementation_source/src", directory / "cache")
        os.environ.clear()
        os.environ.update(env)
        import torch

        if (
            torch.cuda.device_count() != 1
            or "H100" not in torch.cuda.get_device_name(0)
            or socket.gethostname() == request["source_cci_hostname"]
        ):
            raise ValueError("one H100 on an independent ACP worker required")
        write(
            directory / "hardware.json",
            {
                "at": now(),
                "hostname": socket.gethostname(),
                "visible_gpu_count": 1,
                "device_name": torch.cuda.get_device_name(0),
                "memory_bytes": torch.cuda.get_device_properties(0).total_memory,
                "capability": list(torch.cuda.get_device_capability(0)),
                "torch_version": torch.__version__,
                "cuda_version": torch.version.cuda,
                "acceptance_id": accepted["acceptance_id"],
            },
        )
        outputs = HERE / "units" / factor / "model_report"
        outcomes = run_commands(commands_for(path, plan["run_path"], outputs), directory, env)
        result["outcomes"] = outcomes
        passed = len(outcomes) == 3 and all(o["exit_code"] == 0 for o in outcomes)
        result.update(status="passed" if passed else "failed", all_commands_exit_zero=passed)
        if (outputs / "report.json").exists():
            report = read(outputs / "report.json")
            result.update(
                {
                    key: report[key]
                    for key in (
                        "complete",
                        "received",
                        "attempted",
                        "local_model_calls",
                        "audit_id",
                    )
                }
            )
    except BaseException as exc:  # noqa: BLE001 - record failed worker before exiting
        result["error"] = type(exc).__name__ + ": " + str(exc)
        traceback.print_exc()
    finally:
        result.update(
            finished_at=now(),
            request_sha256=digest(request_path),
            execution_id=request["execution_id"],
            worker_sha256=digest(__file__),
        )
        write(directory / "worker_result.json", result)
    return 0 if result["status"] == "passed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(worker(args.request))


if __name__ == "__main__":
    main()
