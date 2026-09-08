"""Detached observer for the single frozen local matrix and its offline reports."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from disastertrace.local_eval import execution
from disastertrace.local_eval.storage import digest, fingerprint, now, read, write

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
PYTHON = "/mnt/afs/260010168/.venvs/disastertrace-qwen3-v1/bin/python"


def validate():
    plan, _, _ = execution.verify(HERE / "execution")
    preflight = read(HERE / "gpu_preflight.json")
    if not preflight["gpu_model_loaded"] or preflight["model_calls"] != 0:
        raise ValueError("GPU load preflight required")
    acceptance = read(HERE / "frozen_acceptance.json")
    if acceptance["execution_id"] != plan["execution_id"] or acceptance["status"] != "passed":
        raise ValueError("matching frozen offline acceptance required")
    for name, expected in acceptance["evidence_files"].items():
        if digest(HERE / name) != expected:
            raise ValueError("acceptance evidence changed")
    diagnostic = read(HERE / "diagnostic_report/report.json")
    if (
        diagnostic["origin"] != "diagnostic_fixture"
        or diagnostic["received"] != 540
        or not diagnostic["complete"]
        or diagnostic["local_model_calls"] != 0
    ):
        raise ValueError("complete separate diagnostic required")
    return plan


def worker():
    plan = validate()
    directory = HERE / "runtime"
    launch = read(directory / "launch.json")
    if launch["execution_id"] != plan["execution_id"] or launch["worker_sha256"] != digest(
        __file__
    ):
        raise ValueError("worker/launch binding mismatch")
    source = HERE / "execution/implementation_source/src"
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(part in k.upper() for part in ("TOKEN", "SECRET", "API_KEY", "PASSWORD"))
    }
    env.update(
        PYTHONPATH=str(source),
        PYTHONDONTWRITEBYTECODE="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        TOKENIZERS_PARALLELISM="false",
        OMP_NUM_THREADS="8",
        VLLM_NO_USAGE_STATS="1",
        VLLM_WORKER_MULTIPROC_METHOD="spawn",
    )
    base = [PYTHON, "-m", "disastertrace.local_eval.cli"]
    common = ["--execution", str(HERE / "execution"), "--run", plan["run_path"]]
    report = ["--output", str(HERE / "model_report"), "--require-model"]
    commands = [
        ("collect", base + ["collect"] + common),
        ("report", base + ["report"] + common + report),
        ("verify_report", base + ["verify-report"] + common + report),
    ]
    outcomes = []
    for name, command in commands:
        started = now()
        write(directory / (name + "_intent.json"), {"command": command, "started_at": started})
        with (directory / (name + ".log")).open("xb") as stream:
            result = subprocess.run(
                command, cwd=PROJECT, env=env, stdout=stream, stderr=subprocess.STDOUT
            )
        outcome = {
            "step": name,
            "command": command,
            "started_at": started,
            "finished_at": now(),
            "exit_code": result.returncode,
            "log_sha256": digest(directory / (name + ".log")),
        }
        write(directory / (name + "_result.json"), outcome)
        outcomes.append(outcome)
        # A stopped collector still gets an independent prefix report.
        if result.returncode and name != "collect":
            break
    write(
        directory / "observer_completion.json",
        {
            "execution_id": plan["execution_id"],
            "finished_at": now(),
            "outcomes": outcomes,
            "observer_pid": os.getpid(),
            "all_commands_exit_zero": len(outcomes) == 3
            and all(r["exit_code"] == 0 for r in outcomes),
        },
    )
    return 0 if len(outcomes) == 3 and all(r["exit_code"] == 0 for r in outcomes) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    if args.worker:
        raise SystemExit(worker())
    plan = validate()
    if Path(plan["run_path"]).exists():
        raise ValueError("production claim consumed; never relaunch")
    directory = HERE / "runtime"
    directory.mkdir(exist_ok=False)
    write(
        directory / "launch.json",
        {
            "execution_id": plan["execution_id"],
            "at": now(),
            "worker_sha256": digest(__file__),
            "acceptance_sha256": fingerprint(read(HERE / "frozen_acceptance.json")),
        },
    )
    with (directory / "observer.log").open("xb") as stream:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--worker"],
            cwd=PROJECT,
            stdout=stream,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    write(directory / "observer_process.json", {"pid": process.pid, "started_at": now()})
    print(
        {"observer_pid": process.pid, "execution_id": plan["execution_id"], "run": plan["run_path"]}
    )


if __name__ == "__main__":
    main()
