"""Observe one factor's full offline pipeline; never request model generation."""

import argparse
import subprocess
import sys
from pathlib import Path

from disastertrace.local_eval.storage import digest, now, read, write
from disastertrace.stress_eval.data import FACTORS

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factor", required=True, choices=FACTORS)
    args = parser.parse_args()
    unit = HERE / "units" / args.factor
    unit.mkdir(parents=True, exist_ok=False)
    base = HERE.parent / "p3_local_balanced_v1"
    parent = HERE.parent / "p4_constrained_output_v1/execution_live"
    cli = [sys.executable, "-m", "disastertrace.stress_eval.cli"]
    report = [
        "--execution",
        str(unit / "execution_offline"),
        "--run",
        str(unit / "diagnostic"),
        "--output",
        str(unit / "diagnostic_report"),
    ]
    commands = [
        (
            "data",
            cli
            + [
                "prepare-data",
                "--base-dataset",
                str(base / "execution/dataset"),
                "--candidates",
                str(base / "stress_offline"),
                "--factor",
                args.factor,
                "--output",
                str(unit / "dataset"),
            ],
        ),
        (
            "freeze",
            cli
            + [
                "freeze",
                "--parent",
                str(parent),
                "--dataset",
                str(unit / "dataset"),
                "--output",
                str(unit / "execution_offline"),
            ],
        ),
        (
            "diagnostic",
            cli
            + [
                "collect",
                "--execution",
                str(unit / "execution_offline"),
                "--output",
                str(unit / "diagnostic"),
                "--diagnostic",
            ],
        ),
        ("report", cli + ["report"] + report),
        ("verify_report", cli + ["report"] + report + ["--verify"]),
    ]
    outcomes = []
    for name, command in commands:
        started = now()
        write(unit / (name + "_intent.json"), {"command": command, "started_at": started})
        log = unit / (name + ".log")
        with log.open("xb") as stream:
            result = subprocess.run(
                command, cwd=PROJECT, stdout=stream, stderr=subprocess.STDOUT, check=False
            )
        outcome = {
            "command": command,
            "started_at": started,
            "finished_at": now(),
            "exit_code": result.returncode,
            "log_sha256": digest(log),
        }
        write(unit / (name + "_result.json"), outcome)
        outcomes.append(outcome)
        print({"factor": args.factor, "step": name, **outcome}, flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
    report = read(unit / "diagnostic_report/report.json")
    if not report["complete"] or report["received"] != 540 or report["local_model_calls"] != 0:
        raise ValueError("full diagnostic required")
    if report["errors"] != {"fields": [], "actions": []}:
        raise ValueError("diagnostic oracle does not achieve complete correctness")
    write(
        unit / "offline_completion.json",
        {
            "status": "passed",
            "factor": args.factor,
            "finished_at": now(),
            "execution_id": report["execution_id"],
            "audit_id": report["audit_id"],
            "diagnostic_responses": 540,
            "model_calls": 0,
            "all_commands_exit_zero": all(x["exit_code"] == 0 for x in outcomes),
        },
    )


if __name__ == "__main__":
    main()
