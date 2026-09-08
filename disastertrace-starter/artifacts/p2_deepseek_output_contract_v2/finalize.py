"""Reconstruct completed or stopped v2 results offline, without new model requests."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import runner


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bundle = runner.HERE
    project = bundle.parents[1]
    manifest = runner.validate_files(bundle)
    completion = runner.read(bundle / "runtime/completion.json")
    if completion["execution_id"] != runner.EXECUTION_ID or not completion.get("report"):
        raise ValueError("matching worker report required before offline finalization")
    args.output.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    for key in list(env):
        if any(part in key.upper() for part in ("TOKEN", "SECRET", "API_KEY", "PASSWORD")):
            env.pop(key)
    env.update(
        DISASTERTRACE_OFFLINE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=os.pathsep.join(
            [
                str(project / "scripts/offline_guard"),
                str(bundle / "execution/dataset/implementation_source/src"),
            ]
        ),
    )
    run = manifest["run_output"]
    report_dir = str(bundle / "runtime/report")
    tasks = [
        (
            "frozen_report_verify",
            [
                sys.executable,
                "-m",
                "disastertrace.controlled.live",
                "verify-report",
                "--execution",
                str(bundle / "execution"),
                "--run",
                run,
                "--output",
                report_dir,
            ],
        )
    ]
    for script, name in (
        ("analyze.py", "analysis"),
        ("schema_inventory.py", "schema_inventory.json"),
        ("render_tables.py", "RESULT_TABLES.md"),
    ):
        command = [
            sys.executable,
            str(bundle / script),
            "--run",
            run,
            "--report",
            report_dir,
            "--output",
            str(bundle / "runtime" / name),
        ]
        if (bundle / "runtime" / name).exists():
            tasks.append((script + "_reuse_verify", [*command, "--verify"]))
        else:
            tasks.extend(
                [(script + "_generate", command), (script + "_verify", [*command, "--verify"])]
            )
    comparison = [
        sys.executable,
        str(bundle / "compare_historical.py"),
        "--old-bundle",
        str(bundle.parent / "p2_deepseek_development_v1"),
        "--output",
        str(bundle / "runtime/historical_comparison.json"),
    ]
    if (bundle / "runtime/historical_comparison.json").exists():
        tasks.append(("historical_comparison_reuse_verify", [*comparison, "--verify"]))
    else:
        tasks.extend(
            [
                ("historical_comparison_generate", comparison),
                ("historical_comparison_verify", [*comparison, "--verify"]),
            ]
        )
    records = []
    try:
        for name, command in tasks:
            start = datetime.now(timezone.utc).isoformat()
            with (args.output / (name + ".log")).open("xb") as stream:
                result = subprocess.run(
                    command, cwd=project, env=env, stdout=stream, stderr=subprocess.STDOUT
                )
            records.append(
                {
                    "step": name,
                    "command": command,
                    "started_at": start,
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                    "exit_code": result.returncode,
                    "external_network_blocked": True,
                    "additional_model_calls": 0,
                }
            )
            print(json.dumps(records[-1]), flush=True)
            if result.returncode:
                raise RuntimeError("offline finalization failed: " + name)
    finally:
        write(args.output / "commands.json", records)
    baseline = runner.read(bundle / "baseline/protected_files.json")["files"]
    changed = [
        name
        for name, expected in baseline.items()
        if not (project.parent / name).is_file() or digest(project.parent / name) != expected
    ]
    write(
        args.output / "historical_preservation.json",
        {"verified_entries": len(baseline), "changed": changed},
    )
    if changed:
        raise ValueError("historical preservation failed")
    write(
        args.output / "result.json",
        {
            "status": "passed",
            "execution_id": runner.EXECUTION_ID,
            "command_count": len(records),
            "historical_entries_verified": len(baseline),
            "additional_model_calls": 0,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
    )


if __name__ == "__main__":
    main()
