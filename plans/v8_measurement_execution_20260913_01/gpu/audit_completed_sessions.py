"""Audit only immutable completed controllers while the original batch runs."""

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def save(path, row):
    with path.open("x") as handle:
        json.dump(row, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stop-at", required=True)
    args = parser.parse_args()
    args.batch = args.batch.resolve()
    args.output = args.output.resolve()
    stop = dt.datetime.fromisoformat(args.stop_at)
    args.output.mkdir(parents=True, exist_ok=False)
    verifier = args.output / "verify_adaptive.py"
    shutil.copyfile(args.batch / "source/verify_adaptive.py", verifier)
    shutil.copyfile(Path(__file__), args.output / Path(__file__).name)
    plan = read(args.batch / "PLAN.json")
    save(
        args.output / "PLAN.json",
        {
            "stop_at": args.stop_at,
            "pid": os.getpid(),
            "registered_sessions": len(plan["cases"]),
            "mode": "read-only original captures; one CPU audit process; no GPU or model calls",
            "per_case_timeout_seconds": 300,
            "only_complete_sessions_before_worker_stop": True,
            "original_automatic_audit": "Preserved; this incremental audit is additional validation, not a replacement.",
        },
    )
    env = dict(
        os.environ,
        PYTHONPATH=str(args.batch / "source"),
        PYTHONDONTWRITEBYTECODE="1",
        CUDA_VISIBLE_DEVICES="",
        TOKENIZERS_PARALLELISM="false",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
    )
    attempted = {}
    while dt.datetime.now(dt.timezone.utc) < stop:
        for case in plan["cases"]:
            ident = case["id"]
            if (
                ident in attempted
                or not (args.batch / "runs" / ident / "COMPLETE.json").is_file()
            ):
                continue
            remaining = (stop - dt.datetime.now(dt.timezone.utc)).total_seconds()
            if remaining < 10:
                break
            command = [
                sys.executable,
                str(verifier),
                "case",
                "--batch",
                str(args.batch),
                "--output",
                str(args.output),
                "--case",
                ident,
            ]
            save(
                args.output / (ident + ".command.json"),
                {
                    "command": command,
                    "at": dt.datetime.now(dt.timezone.utc).isoformat(),
                },
            )
            with (args.output / (ident + ".log")).open("x") as log:
                try:
                    result = subprocess.run(
                        command,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        env=env,
                        timeout=min(300, remaining),
                        check=False,
                    )
                    code = result.returncode
                except subprocess.TimeoutExpired:
                    code = 124
            attempted[ident] = code
            save(
                args.output / (ident + ".exit.json"),
                {"exit_code": code, "at": dt.datetime.now(dt.timezone.utc).isoformat()},
            )
            print(
                json.dumps(
                    {
                        "case": ident,
                        "audit_exit": code,
                        "audited_sessions": len(attempted),
                    }
                ),
                flush=True,
            )
        if len(attempted) == len(plan["cases"]):
            break
        if (args.batch / "COMPLETE.json").exists() or (
            args.batch / "WORKER_FAILED.json"
        ).exists():
            break
        time.sleep(
            min(15, max(0, (stop - dt.datetime.now(dt.timezone.utc)).total_seconds()))
        )
    save(
        args.output / "COMPLETE.json",
        {
            "attempted": attempted,
            "registered_sessions": len(plan["cases"]),
            "remaining_sessions": [
                c["id"] for c in plan["cases"] if c["id"] not in attempted
            ],
            "full_batch_scores": "Use the original worker's audit_01 after termination.",
            "new_model_calls": 0,
        },
    )


if __name__ == "__main__":
    main()
