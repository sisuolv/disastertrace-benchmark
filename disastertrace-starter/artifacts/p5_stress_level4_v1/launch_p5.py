"""Validate and consume one phase launch for three independent one-H100 jobs."""

from datetime import datetime, timezone
from pathlib import Path

from acp_common import FACTORS, HERE, PROJECT, command_for, submit

from disastertrace.local_eval.storage import digest, fingerprint, now, read, write
from disastertrace.stress_eval import execution

PAIR_KEYS = (
    "settings",
    "implementation_files",
    "backend_files",
    "dataset_content_id",
    "dataset_package_id",
    "model_snapshot_sha256",
    "environment_sha256",
    "stress_profile",
    "base_dataset_content_id",
    "base_dataset_package_id",
    "model_config_files",
)


def validate_pair(live, offline, factor):
    if any(live[key] != offline[key] for key in PAIR_KEYS):
        raise ValueError("live factor differs from accepted offline implementation/data")
    if live["stress_profile"]["factor"] != factor or live["stress_profile"]["level"] != 4:
        raise ValueError("wrong factor or intensity")
    if live["scope"] != execution.LIVE_SCOPE or offline["scope"] != execution.SCOPE:
        raise ValueError("distinct live/offline scopes required")


def validate_budget(plans, project=PROJECT, *, check_deadline=True):
    if set(plans) != set(FACTORS):
        raise ValueError("exactly the three predeclared factors required")
    paths, deadlines = set(), set()
    for factor, plan in plans.items():
        if (
            plan["max_attempts"] != 540
            or plan["planned_responses"] != 540
            or plan["repeats"] != 1
            or plan["retries"] != 0
            or plan["diagnostic_probes"] != 0
        ):
            raise ValueError("phase exceeds frozen attempt/repeat/probe scope")
        expected = project / "work" / ("p5-qwen3-" + factor.replace("_", "-") + "-v1")
        if plan["run_path"] != str(expected.resolve()):
            raise ValueError("wrong canonical factor run")
        paths.add(plan["run_path"])
        deadline = datetime.fromisoformat(plan["deadline_utc"])
        if deadline.tzinfo is None or check_deadline and deadline <= datetime.now(timezone.utc):
            raise ValueError("future aware execution deadline required")
        deadlines.add(deadline)
    if len(paths) != 3 or len(deadlines) != 1:
        raise ValueError("distinct runs and one phase deadline required")


def verify_bound_files(acceptance, here=HERE):
    expected = fingerprint({k: v for k, v in acceptance.items() if k != "acceptance_id"})
    if acceptance["acceptance_id"] != expected or acceptance["status"] != "passed":
        raise ValueError("phase acceptance identity mismatch")
    for name, expected_hash in acceptance["evidence_sha256"].items():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or digest(here / name) != expected_hash:
            raise ValueError("phase acceptance evidence changed: " + name)


def validate(*, fresh=True):
    accepted = read(HERE / "LIVE_ACCEPTANCE.json")
    verify_bound_files(accepted)
    plans = {}
    for factor in FACTORS:
        unit = HERE / "units" / factor
        live, _, slots = execution.verify(unit / "execution_live")
        offline, _, _ = execution.verify(unit / "execution_offline")
        validate_pair(live, offline, factor)
        report = read(unit / "live_diagnostic_report/report.json")
        if (
            report["execution_id"] != live["execution_id"]
            or not report["complete"]
            or report["received"] != 540
            or report["local_model_calls"] != 0
            or report["origin"] != "diagnostic_stress_fixture"
            or len(slots) != 540
            or report["errors"] != {"fields": [], "actions": []}
            or accepted["units"][factor]["execution_id"] != live["execution_id"]
        ):
            raise ValueError("full matching live-freeze diagnostic required")
        if fresh and Path(live["run_path"]).exists():
            raise ValueError("factor production claim already consumed")
        plans[factor] = live
    validate_budget(plans)
    if (
        accepted["max_model_responses"] != 1620
        or accepted["parallel_gpus"] != 3
        or accepted["user_gpu_cap"] != 4
    ):
        raise ValueError("phase resource/response scope mismatch")
    return plans, accepted


def launch():
    plans, accepted = validate()
    phase = HERE / "acp/phase_001"
    phase.mkdir(exist_ok=False)
    write(
        phase / "launch.json",
        {
            "at": now(),
            "acceptance_id": accepted["acceptance_id"],
            "acceptance_sha256": digest(HERE / "LIVE_ACCEPTANCE.json"),
            "units": {factor: p["execution_id"] for factor, p in plans.items()},
            "max_model_responses": 1620,
            "parallel_gpus": 3,
            "user_gpu_cap": 4,
            "one_use": True,
            "no_retries": True,
        },
    )
    worker = HERE / "acp_worker.py"
    outcomes = {}
    for factor in FACTORS:
        directory = phase / factor
        path = HERE / "units" / factor / "execution_live"
        command = command_for(
            worker, directory / "request.json", path / "implementation_source/src", 7200
        )
        outcomes[factor] = submit(
            directory,
            {
                "kind": "p5_factor_model_evaluation",
                "factor": factor,
                "display_name": "dt-p5-" + factor.replace("_", "-") + "-20260908-v1",
                "project": str(PROJECT),
                "execution_path": str(path),
                "execution_id": plans[factor]["execution_id"],
                "run_path": plans[factor]["run_path"],
                "worker_sha256": digest(worker),
                "common_sha256": digest(HERE / "acp_common.py"),
                "phase_launch_sha256": digest(phase / "launch.json"),
                "acceptance_sha256": digest(HERE / "LIVE_ACCEPTANCE.json"),
                "command": command,
                "max_model_responses": 540,
                "maximum_gpus": 1,
            },
        )
    write(
        phase / "submission_completion.json",
        {
            "at": now(),
            "submissions": outcomes,
            "all_three_submitted": True,
            "model_completion_not_yet_established": True,
        },
    )


if __name__ == "__main__":
    launch()
