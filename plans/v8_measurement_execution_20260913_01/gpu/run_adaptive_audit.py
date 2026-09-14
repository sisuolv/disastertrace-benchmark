"""Run a separate, full-denominator audit after the original worker terminates."""

import argparse
import concurrent.futures
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def save(path, data):
    with path.open("x") as handle:
        json.dump(data, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    verifier = args.output / "verify_adaptive.py"
    shutil.copyfile(Path(__file__).with_name("verify_adaptive.py"), verifier)
    shutil.copyfile(Path(__file__), args.output / "run_adaptive_audit.py")
    plan = json.loads((args.batch / "PLAN.json").read_text())
    env = dict(
        os.environ,
        PYTHONPATH=str(args.batch / "source"),
        PYTHONDONTWRITEBYTECODE="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
    )

    def run(name, command):
        save(
            args.output / (name + ".command.json"),
            {
                "command": command,
                "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        )
        with (args.output / (name + ".log")).open("x") as log:
            result = subprocess.run(
                command, stdout=log, stderr=subprocess.STDOUT, env=env, check=False
            )
        save(
            args.output / (name + ".exit.json"),
            {
                "exit_code": result.returncode,
                "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        )
        print(json.dumps({"stage": name, "exit_code": result.returncode}), flush=True)
        return result.returncode

    def one(case):
        return run(
            case["id"],
            [
                sys.executable,
                str(verifier),
                "case",
                "--batch",
                str(args.batch),
                "--output",
                str(args.output),
                "--case",
                case["id"],
            ],
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        exits = list(pool.map(one, plan["cases"]))
    code = run(
        "finalize",
        [
            sys.executable,
            str(verifier),
            "finalize",
            "--batch",
            str(args.batch),
            "--output",
            str(args.output),
        ],
    )
    save(
        args.output / "COMPLETE.json",
        {"case_exit_codes": exits, "finalizer_exit_code": code},
    )
    raise SystemExit(int(any(exits) or code != 0))


if __name__ == "__main__":
    main()
