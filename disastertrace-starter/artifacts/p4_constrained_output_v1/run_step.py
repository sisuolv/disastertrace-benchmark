"""Observe exact subprocess commands, exits and logs without recording credentials."""

import argparse
import os
import subprocess
from pathlib import Path

from disastertrace.local_eval.storage import digest, now, write

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--source", type=Path, default=PROJECT / "src")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("command required")
    directory = HERE / "validation" / args.name
    directory.mkdir(parents=True, exist_ok=False)
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(part in k.upper() for part in ("TOKEN", "SECRET", "API_KEY", "PASSWORD"))
    }
    env.update(
        PYTHONPATH=str(args.source.resolve()),
        PYTHONDONTWRITEBYTECODE="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        TOKENIZERS_PARALLELISM="false",
        VLLM_NO_USAGE_STATS="1",
        VLLM_WORKER_MULTIPROC_METHOD="spawn",
        VLLM_USE_V1="1",
        OMP_NUM_THREADS="8",
    )
    started = now()
    write(
        directory / "intent.json",
        {
            "command": command,
            "started_at": started,
            "source": str(args.source.resolve()),
            "cwd": str(PROJECT),
            "credential_environment_removed": True,
        },
    )
    with (directory / "stdout.log").open("xb") as stream:
        result = subprocess.run(
            command, cwd=PROJECT, env=env, stdout=stream, stderr=subprocess.STDOUT
        )
    observation = {
        "command": command,
        "started_at": started,
        "finished_at": now(),
        "exit_code": result.returncode,
        "log_sha256": digest(directory / "stdout.log"),
    }
    write(directory / "result.json", observation)
    print(observation, flush=True)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
