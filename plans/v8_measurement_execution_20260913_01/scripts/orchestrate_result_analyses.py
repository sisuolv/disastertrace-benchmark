"""Run CPU-only analyses once their original immutable completion receipts exist."""

import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
OUT = HERE / "finalization_pipeline_01"
DEADLINE = dt.datetime(2026, 9, 14, 2, 40, tzinfo=dt.timezone.utc)
PYTHON = REPO / "disastertrace-starter/.venv/bin/python"
PLOTLIBS = "/mnt/afs/260010168/.venvs/disastertrace-multihazard-libs-20260911"


def now():
    return dt.datetime.now(dt.timezone.utc)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    with (OUT / name).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    OUT.mkdir(exist_ok=False)
    scripts = {
        name: sha(HERE / "scripts" / name)
        for name in (
            "analyze_adaptive_results.py",
            "explain_forecast_changes.py",
            "plot_adaptive_results.py",
            "analyze_shadow_sources.py",
            "analyze_joint_results.py",
        )
    }
    save(
        "STARTED.json",
        {
            "at": now().isoformat(),
            "deadline": DEADLINE.isoformat(),
            "script_hashes": scripts,
            "pid": os.getpid(),
            "new_model_calls": 0,
            "scope": "Only postprocessing original captures;no new source,model or GPU calls.",
        },
    )
    states = {
        name: "pending"
        for name in ("adaptive", "attribution", "adaptive_plot", "shadow", "joint")
    }

    def run(name, script, arguments, *, paths=None, plot=False):
        remaining = (DEADLINE - now()).total_seconds()
        if remaining < 60:
            states[name] = "not_started_before_analysis_deadline"
            return
        path = HERE / "scripts" / script
        if sha(path) != scripts[script]:
            raise ValueError(
                "Analysis source changed after one-use orchestration claim"
            )
        command = [sys.executable if plot else str(PYTHON), str(path)] + [
            str(arg) for arg in arguments
        ]
        env = dict(
            os.environ,
            PYTHONDONTWRITEBYTECODE="1",
            CUDA_VISIBLE_DEVICES="",
            OMP_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
            PYTHONPATH=PLOTLIBS
            if plot
            else str(paths or REPO / "disastertrace-starter/src"),
        )
        save(
            name + ".command.json",
            {
                "at": now().isoformat(),
                "command": command,
                "cwd": str(REPO),
                "source_sha256": scripts[script],
                "pythonpath": env["PYTHONPATH"],
            },
        )
        code, error = None, None
        try:
            with (OUT / (name + ".log")).open("x") as log:
                result = subprocess.run(
                    command,
                    cwd=REPO,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=min(600, remaining),
                    check=False,
                )
            code = result.returncode
        except (OSError, subprocess.TimeoutExpired) as exc:
            error = type(exc).__name__
        states[name] = "complete" if code == 0 else "failed_preserved_no_retry"
        save(
            name + ".exit.json",
            {
                "at": now().isoformat(),
                "exit_code": code,
                "error": error,
                "state": states[name],
            },
        )
        print(json.dumps({"stage": name, "state": states[name]}), flush=True)

    while now() < DEADLINE and any(v == "pending" for v in states.values()):
        adaptive = HERE / "gpu/adaptive_large_02"
        analysis = HERE / "reports/adaptive_large_analysis_01"
        if states["adaptive"] == "pending" and all(
            (adaptive / "audit_01" / n).exists()
            for n in ("COMPLETE.json", "VALIDATION.json")
        ):
            run(
                "adaptive",
                "analyze_adaptive_results.py",
                [
                    "--batch",
                    adaptive,
                    "--audit",
                    adaptive / "audit_01",
                    "--output",
                    analysis,
                ],
                paths=adaptive / "source",
            )
        if states["adaptive"] == "complete":
            if states["attribution"] == "pending":
                run(
                    "attribution",
                    "explain_forecast_changes.py",
                    [
                        "--batch",
                        adaptive,
                        "--analysis",
                        analysis,
                        "--output",
                        HERE / "reports/forecast_attribution_01",
                    ],
                )
            if states["adaptive_plot"] == "pending":
                run(
                    "adaptive_plot",
                    "plot_adaptive_results.py",
                    ["--analysis", analysis, "--output", analysis / "figures_01"],
                    plot=True,
                )
        elif states["adaptive"] != "pending":
            for name in ("attribution", "adaptive_plot"):
                if states[name] == "pending":
                    states[name] = "dependency_not_qualified"
        if (
            states["shadow"] == "pending"
            and (HERE / "shadow_capture_01/COMPLETE.json").exists()
        ):
            run(
                "shadow",
                "analyze_shadow_sources.py",
                ["--output", HERE / "shadow_decode_complete_02"],
            )
        joint = HERE / "gpu/joint_targets_live_01"
        if states["joint"] == "pending":
            if (joint / "audit_01/VALIDATION.json").exists() and (
                joint / "audit.exit.txt"
            ).exists():
                run(
                    "joint",
                    "analyze_joint_results.py",
                    [
                        "--audit",
                        joint / "audit_01",
                        "--output",
                        HERE / "reports/joint_large_analysis_01",
                    ],
                )
            elif (joint / "submission_01/NOT_SUBMITTED.json").exists():
                states["joint"] = "not_launched_as_declared"
        if any(v == "pending" for v in states.values()):
            time.sleep(min(30, max(0, (DEADLINE - now()).total_seconds())))
    for name, state in states.items():
        if state == "pending":
            states[name] = "prerequisite_not_complete_before_deadline"
    save(
        "COMPLETE.json",
        {
            "at": now().isoformat(),
            "states": states,
            "new_model_calls": 0,
            "remaining_raw_results_preserved": True,
        },
    )
    print(json.dumps(states), flush=True)


if __name__ == "__main__":
    main()
