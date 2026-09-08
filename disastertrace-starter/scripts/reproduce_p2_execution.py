"""Reproduce P2 captured-execution acceptance with external networking disabled."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from historical_artifacts import HistoricalFiles


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--output-contract",
        choices=("controlled_output_contract_v1", "controlled_output_contract_v2"),
        default="controlled_output_contract_v1",
    )
    parser.add_argument(
        "--skip-tests", action="store_true", help="Explicitly record tests as not run"
    )
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    for key in list(env):
        if any(part in key.upper() for part in ("TOKEN", "SECRET", "API_KEY", "PASSWORD")):
            env.pop(key)
    env.update(
        DISASTERTRACE_OFFLINE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=os.pathsep.join((str(project / "scripts/offline_guard"), str(project / "src"))),
    )
    py = sys.executable
    checks = [
        "src/disastertrace/controlled",
        "src/disastertrace/automated/provider_capture.py",
        "tests/test_controlled_capture.py",
        "tests/test_controlled_live.py",
        "tests/test_controlled_live_guards.py",
        "tests/test_controlled_output_contract.py",
        "scripts/reproduce_p2_execution.py",
        "scripts/historical_artifacts.py",
        "tests/test_p2_historical_artifacts.py",
        "scripts/verify_p2_output_contract.py",
        "scripts/reproduce_p2_output_contract.py",
    ]
    commands = []
    if not args.skip_tests:
        commands.append(
            (
                "tests",
                [py, "-m", "pytest", "tests", "-q", "-o", "addopts=", "-p", "no:cacheprovider"],
            )
        )
    commands += [
        ("lint", [py, "-m", "ruff", "check", "--select", "E,F,I", *checks]),
        ("format", [py, "-m", "ruff", "format", "--check", *checks]),
        ("dependencies", [py, "-m", "pip", "check"]),
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
        (
            "execution_prepare",
            [
                py,
                "-m",
                "disastertrace.controlled.live",
                "prepare",
                "--dataset",
                str(output / "p2"),
                "--rates",
                str(project / "artifacts/p1_deepseek_development/docs/rates.json"),
                "--registry",
                str(output / "live_registry"),
                "--output",
                str(output / "execution"),
                "--output-contract",
                args.output_contract,
            ],
        ),
        (
            "execution_verify",
            [
                py,
                "-m",
                "disastertrace.controlled.live",
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
                "disastertrace.controlled.live",
                "rehearse",
                "--execution",
                str(output / "execution"),
                "--output",
                str(output / "rehearsal"),
            ],
        ),
        (
            "execution_audit",
            [
                py,
                "-m",
                "disastertrace.controlled.live",
                "audit",
                "--execution",
                str(output / "execution"),
                "--run",
                str(output / "rehearsal"),
                "--output",
                str(output / "audit.json"),
            ],
        ),
        (
            "execution_report",
            [
                py,
                "-m",
                "disastertrace.controlled.live",
                "report",
                "--execution",
                str(output / "execution"),
                "--run",
                str(output / "rehearsal"),
                "--output",
                str(output / "report"),
            ],
        ),
        (
            "report_verify",
            [
                py,
                "-m",
                "disastertrace.controlled.live",
                "verify-report",
                "--execution",
                str(output / "execution"),
                "--run",
                str(output / "rehearsal"),
                "--output",
                str(output / "report"),
            ],
        ),
    ]
    records = []
    for name, command in commands:
        started = time.monotonic()
        with (output / (name + ".log")).open("w") as stream:
            result = subprocess.run(
                command, cwd=project, env=env, stdout=stream, stderr=subprocess.STDOUT
            )
        records.append(
            {
                "name": name,
                "command": command,
                "cwd": str(project),
                "exit_code": result.returncode,
                "seconds": round(time.monotonic() - started, 3),
                "log_sha256": digest(output / (name + ".log")),
            }
        )
        (output / "commands.json").write_text(
            json.dumps(
                {
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "records": records,
                    "tests_requested": not args.skip_tests,
                    "external_network_blocked": True,
                    "loopback_fixtures_allowed": True,
                    "model_calls": 0,
                },
                indent=2,
            )
            + "\n"
        )
        print(name, "exit", result.returncode, flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
    history = HistoricalFiles(project.parent)
    historical = "disastertrace-starter/work/next-phase-acceptance-003/p2/"
    semantic_files = (
        "episodes.jsonl",
        "micro_fixtures.jsonl",
        "schedule.jsonl",
        "private/gold.jsonl",
        "public/initial_requests.jsonl",
        "parent_sources.jsonl",
    )
    lineage = {
        name: {
            "old_sha256": history.digest(historical + name),
            "new_sha256": digest(output / "p2" / name),
        }
        for name in semantic_files
    }
    if any(row["old_sha256"] != row["new_sha256"] for row in lineage.values()):
        raise ValueError("P2 semantic content unexpectedly changed")
    reference_scores = 0
    for path in sorted((output / "p2/diagnostics").glob("*/*/score.json")):
        name = str(path.relative_to(output / "p2"))
        previous = json.loads(history.read(historical + name))
        if json.dumps(previous, sort_keys=True) != json.dumps(read(path), sort_keys=True):
            raise ValueError("historical diagnostic metrics changed: " + name)
        reference_scores += 1
    if reference_scores != 30:
        raise ValueError("expected all 30 historical program score configurations")
    protection = read(project / "artifacts/p2_execution_v1/baseline/protected_files.json")
    changed = [name for name, sha in protection.items() if history.digest(name) != sha]
    if changed:
        raise ValueError("historical files changed: " + ", ".join(changed))
    report = read(output / "report/report.json")
    plan = read(output / "execution/execution.json")
    if (
        not report["complete"]
        or report["model_calls"] != 0
        or report["eligible_for_llm_leaderboard"]
    ):
        raise ValueError("diagnostic acceptance scope mismatch")
    status = {
        "status": "P2_CAPTURED_EXECUTION_OFFLINE_READY",
        "output_contract_version": args.output_contract,
        "model_calls": 0,
        "heldout_model_calls": 0,
        "live_authorized": False,
        "live_launch_ready": False,
        "execution_id": plan["execution_id"],
        "dataset_content_id": plan["dataset_content_id"],
        "dataset_package_id": plan["dataset_package_id"],
        "audit_id": report["audit_id"],
        "diagnostic_attempts": report["attempted"],
        "diagnostic_responses": report["received"],
        "planned_output_cap": 8192,
        "historical_files_verified": len(protection),
        "historical_files_changed": [],
        "semantic_lineage": lineage,
        "historical_dataset_content_id": json.loads(history.read(historical + "plan.json"))[
            "dataset_content_id"
        ],
        "historical_program_score_configurations_equal": reference_scores,
        "tests_requested": not args.skip_tests,
        "remaining_launch_conditions": [
            "Actual P2 execution authorization",
            "Current matching price attestation",
        ],
    }
    (output / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    print(json.dumps(status))


if __name__ == "__main__":
    main()
