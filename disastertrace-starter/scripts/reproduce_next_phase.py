"""Run current tests and fresh offline T0-T5 packages; never dispatch a model request."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-tests", action="store_true", help="Record tests as not run")
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    for key in list(env):
        if any(part in key.upper() for part in ("TOKEN", "SECRET", "API_KEY", "PASSWORD")):
            env.pop(key)
    env["DISASTERTRACE_OFFLINE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        (str(project / "scripts/offline_guard"), str(project / "src"))
    )
    py = sys.executable
    commands = []
    if not args.skip_tests:
        commands.append(
            (
                "tests",
                [py, "-m", "pytest", "tests", "-o", "addopts=", "-q", "-p", "no:cacheprovider"],
            )
        )
    commands += [
        (
            "build",
            [
                py,
                "-c",
                "from disastertrace.automated.cli import main; main()",
                "build",
                "--references",
                str(project.parent / "references"),
                "--nhc-snapshot",
                str(project.parent / "references/nhc_cohort_v1"),
                "--output",
                str(output / "build"),
            ],
        ),
        (
            "calibration_prepare",
            [
                py,
                "-m",
                "disastertrace.automated.calibration",
                "prepare",
                "--build",
                str(output / "build"),
                "--provider-config",
                str(project / "artifacts/p1_deepseek_development/provider.json"),
                "--output",
                str(output / "calibration"),
            ],
        ),
        (
            "calibration_verify",
            [
                py,
                "-m",
                "disastertrace.automated.calibration",
                "verify",
                "--output",
                str(output / "calibration"),
            ],
        ),
        (
            "execution_prepare",
            [
                py,
                "-m",
                "disastertrace.automated.live_calibration",
                "prepare",
                "--preparation",
                str(output / "calibration"),
                "--output",
                str(output / "execution"),
                "--registry",
                str(output / "live_registry"),
            ],
        ),
        (
            "execution_verify",
            [
                py,
                "-m",
                "disastertrace.automated.live_calibration",
                "verify",
                "--execution",
                str(output / "execution"),
            ],
        ),
        (
            "execution_rehearse",
            [
                py,
                "-m",
                "disastertrace.automated.live_calibration",
                "rehearse",
                "--execution",
                str(output / "execution"),
                "--output",
                str(output / "rehearsal"),
                "--registry",
                str(output / "diagnostic_registry"),
            ],
        ),
        (
            "execution_audit",
            [
                py,
                "-m",
                "disastertrace.automated.live_calibration_audit",
                "--execution",
                str(output / "execution"),
                "--run",
                str(output / "rehearsal"),
                "--output",
                str(output / "execution_audit.json"),
            ],
        ),
        (
            "execution_report",
            [
                py,
                "-m",
                "disastertrace.automated.calibration_report",
                "--execution",
                str(output / "execution"),
                "--run",
                str(output / "rehearsal"),
                "--output",
                str(output / "report"),
            ],
        ),
        (
            "p2_prepare",
            [
                py,
                "-m",
                "disastertrace.controlled.cli",
                "prepare",
                "--source-build",
                str(output / "build"),
                "--output",
                str(output / "p2"),
            ],
        ),
        (
            "p2_verify",
            [py, "-m", "disastertrace.controlled.cli", "verify", "--dataset", str(output / "p2")],
        ),
    ]
    records = []
    for name, command in commands:
        start = time.monotonic()
        with (output / (name + ".log")).open("w") as stream:
            process = subprocess.run(
                command, cwd=project, env=env, stdout=stream, stderr=subprocess.STDOUT
            )
        records.append(
            {
                "name": name,
                "command": command,
                "cwd": str(project),
                "exit_code": process.returncode,
                "elapsed_seconds": round(time.monotonic() - start, 3),
                "log_sha256": hashlib.sha256((output / (name + ".log")).read_bytes()).hexdigest(),
            }
        )
        (output / "commands.json").write_text(
            json.dumps(
                {
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "records": records,
                    "tests_requested": not args.skip_tests,
                    "model_calls": 0,
                    "external_network_blocked": True,
                    "loopback_fixtures_allowed": True,
                },
                indent=2,
            )
            + "\n"
        )
        print(name, "exit", process.returncode, flush=True)
        if process.returncode:
            raise SystemExit(process.returncode)


if __name__ == "__main__":
    main()
