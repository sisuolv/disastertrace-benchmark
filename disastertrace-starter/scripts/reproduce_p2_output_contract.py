"""Complete the common-contract v2 offline acceptance; never launch model requests."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from historical_artifacts import HistoricalFiles


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def verify_completed_pipeline(pipeline):
    commands, status = read(pipeline / "commands.json"), read(pipeline / "status.json")
    expected = [
        "tests",
        "lint",
        "format",
        "dependencies",
        "build",
        "p2_prepare",
        "p2_verify",
        "execution_prepare",
        "execution_verify",
        "execution_rehearse",
        "execution_audit",
        "execution_report",
        "report_verify",
    ]
    if not commands["tests_requested"] or [r["name"] for r in commands["records"]] != expected:
        raise ValueError("complete full-suite pipeline required for reuse")
    for row in commands["records"]:
        actual = hashlib.sha256((pipeline / (row["name"] + ".log")).read_bytes()).hexdigest()
        if row["exit_code"] != 0 or actual != row["log_sha256"]:
            raise ValueError("prior pipeline command/log changed or failed")
    tests = (pipeline / "tests.log").read_text()
    if not re.search(r"\d+ passed in [\d.]+s", tests) or re.search(
        r"\d+ (failed|skipped|errors?)", tests
    ):
        raise ValueError("prior full-suite result is not a complete pass")
    from disastertrace.controlled.execution import verify_execution
    from disastertrace.controlled.live_report import verify_report

    plan = verify_execution(pipeline / "execution")
    if (
        status["execution_id"] != plan["execution_id"]
        or status["output_contract_version"] != "controlled_output_contract_v2"
        or status["model_calls"] != 0
    ):
        raise ValueError("completed pipeline scope changed")
    report = verify_report(pipeline / "execution", pipeline / "rehearsal", pipeline / "report")
    return {
        "status": "passed",
        "completed_pipeline": str(pipeline),
        "pipeline_commands_sha256": hashlib.sha256(
            (pipeline / "commands.json").read_bytes()
        ).hexdigest(),
        "tests_reexecuted": False,
        "source_and_environment_reverified": True,
        "report": report,
        "model_calls": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--verify-pipeline", type=Path)
    parser.add_argument("--completed-pipeline", type=Path)
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()
    if args.verify_pipeline is not None:
        print(json.dumps(verify_completed_pipeline(args.verify_pipeline.resolve())))
        return
    if args.completed_pipeline is not None and args.skip_tests:
        parser.error("completed pipeline reuse requires its full-suite record")
    project = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    pipeline = args.completed_pipeline.resolve() if args.completed_pipeline else output / "pipeline"
    old = project / "artifacts/p2_deepseek_development_v1"
    old_run = project / "work/p2-deepseek-development-v1"
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(part in k.upper() for part in ("TOKEN", "SECRET", "API_KEY", "PASSWORD"))
    }
    guard = str(project / "scripts/offline_guard")
    env.update(
        DISASTERTRACE_OFFLINE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=os.pathsep.join((guard, str(project / "src"))),
    )
    records = []

    def run(name, command, *, source=None):
        selected_env = dict(env)
        if source is not None:
            selected_env["PYTHONPATH"] = os.pathsep.join((guard, str(source)))
        start = time.monotonic()
        log = output / (name + ".log")
        with log.open("w") as stream:
            result = subprocess.run(
                command, cwd=project, env=selected_env, stdout=stream, stderr=subprocess.STDOUT
            )
        records.append(
            {
                "name": name,
                "command": command,
                "cwd": str(project),
                "pythonpath": selected_env["PYTHONPATH"],
                "exit_code": result.returncode,
                "seconds": round(time.monotonic() - start, 3),
                "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
            }
        )
        write(
            output / "commands.json",
            {
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "records": records,
                "model_calls": 0,
                "external_network_blocked": True,
                "loopback_fixtures_allowed": True,
                "tests_requested": not args.skip_tests,
                "completed_pipeline_reused": bool(args.completed_pipeline),
                "pipeline_path": str(pipeline),
            },
        )
        print(name, "exit", result.returncode, flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)

    py = sys.executable
    run(
        "pipeline",
        [py, "scripts/reproduce_p2_output_contract.py", "--verify-pipeline", str(pipeline)]
        if args.completed_pipeline
        else [
            py,
            "scripts/reproduce_p2_execution.py",
            "--output",
            str(pipeline),
            "--output-contract",
            "controlled_output_contract_v2",
            *(["--skip-tests"] if args.skip_tests else []),
        ],
    )
    for name, execution, run_dir, report_dir in (
        ("frozen_v1_report", old / "execution", old_run, old / "runtime/report"),
        ("frozen_v2_report", pipeline / "execution", pipeline / "rehearsal", pipeline / "report"),
    ):
        run(
            name,
            [
                py,
                "-m",
                "disastertrace.controlled.live",
                "verify-report",
                "--execution",
                str(execution),
                "--run",
                str(run_dir),
                "--output",
                str(report_dir),
            ],
            source=execution / "dataset/implementation_source/src",
        )
    comparison = [
        py,
        "scripts/verify_p2_output_contract.py",
        "--old-execution",
        str(old / "execution"),
        "--new-execution",
        str(pipeline / "execution"),
        "--old-run",
        str(old_run),
        "--old-report",
        str(old / "runtime/report"),
        "--new-report",
        str(pipeline / "report"),
        "--output",
        str(output / "equivalence"),
    ]
    run("semantic_equivalence", comparison)
    run("semantic_equivalence_verify", [*comparison, "--verify"])
    plan = read(pipeline / "execution/execution.json")
    registry = Path(plan["registry_path"])
    registry.mkdir(parents=True, exist_ok=True)
    if list(registry.iterdir()):
        raise ValueError("v2 production registry was consumed during offline preparation")
    history = HistoricalFiles(project.parent)
    protection = read(project / "artifacts/p2_output_contract_v2/baseline/protected_files.json")
    changed = [name for name, digest in protection.items() if history.digest(name) != digest]
    if changed:
        raise ValueError("historical files changed: " + ", ".join(changed))
    write(output / "history_verification.json", {"verified": len(protection), "changed": changed})

    from disastertrace.controlled.output_contract import V2, identity, system_message

    write(output / "output_contract.json", identity(V2))
    (output / "system_message.txt").write_text(system_message(V2))
    policy = plan["budget"]
    reserve = (
        Decimal(policy["input_per_million"]) * policy["prompt_bound"]
        + Decimal(policy["output_per_million"]) * plan["config"]["max_output_tokens"]
    ) / Decimal(1000000)
    proposal = {
        "schema_version": "p2_output_contract_v2_development_proposal_v1",
        "authorized": False,
        "launch_ready": False,
        "execution_id": plan["execution_id"],
        "dataset_content_id": plan["dataset_content_id"],
        "dataset_package_id": plan["dataset_package_id"],
        "implementation_id": plan["source_identity"]["implementation_id"],
        "output_contract": plan["output_contract"],
        "matrix": {"episodes": 18, "methods": 3, "checkpoints": 5, "repeats": 1, "calls": 270},
        "config": plan["config"],
        "conditional_allowance_usd": policy["allowance"],
        "max_requested_output_tokens": policy["max_requested_output_tokens"],
        "rates_sha256": plan["rates_sha256"],
        "reservation_prompt_tokens_per_request": policy["prompt_bound"],
        "reserved_usd_per_request": str(reserve),
        "all_slots_at_maximum_reservation_usd": str(reserve * 270),
        "budget_caveat": "USD 3 is a conditional guard, not a guarantee of all 270 responses.",
        "actual_new_prompt_tokens_and_cost": None,
        "registry_path": str(registry),
        "registry_consumed": False,
        "proposed_run": str(project / "work/p2-deepseek-output-contract-v2"),
        "automatic_retry": False,
        "extra_probes": 0,
        "heldout_calls": 0,
        "human_annotations": 0,
        "llm_judge": False,
        "reliability_rule": plan["reliability_rule"],
        "launch_conditions": [
            "New authorization bound to this exact 270-call execution and conditional budget",
            "Current matching official pricing/settings applicability and provider credential",
            "Verify frozen source/environment, fresh run and unconsumed production registry",
        ],
        "interpretation": (
            "Development format screen; historical v1 contrast is not a causal estimate."
        ),
    }
    write(output / "proposal.json", proposal)
    report = read(pipeline / "report/report.json")
    if (
        not report["complete"]
        or report["model_calls"] != 0
        or report["eligible_for_llm_leaderboard"]
    ):
        raise ValueError("candidate diagnostic must remain complete and non-model")
    status = {
        "status": "P2_OUTPUT_CONTRACT_V2_OFFLINE_READY",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "execution_id": plan["execution_id"],
        "dataset_content_id": plan["dataset_content_id"],
        "dataset_package_id": plan["dataset_package_id"],
        "implementation_id": plan["source_identity"]["implementation_id"],
        "output_contract": plan["output_contract"],
        "audit_id": report["audit_id"],
        "report_package_id": read(pipeline / "report/manifest.json")["package_id"],
        "diagnostic_attempts": report["attempted"],
        "diagnostic_responses": report["received"],
        "diagnostic_trajectories": 54,
        "measured_v2_model_reliability": False,
        "model_calls": 0,
        "heldout_model_calls": 0,
        "new_human_annotations": 0,
        "llm_judge": False,
        "live_authorized": False,
        "live_launch_ready": False,
        "production_registry_consumed": False,
        "historical_files_verified": len(protection),
        "historical_files_changed": [],
        "tests_requested": not args.skip_tests,
        "completed_pipeline_reused": bool(args.completed_pipeline),
        "pipeline_path": str(pipeline),
    }
    write(output / "status.json", status)
    print(json.dumps(status), flush=True)


if __name__ == "__main__":
    main()
