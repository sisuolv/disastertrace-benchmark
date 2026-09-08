"""Bind verified inherited data, ACP preflight, fresh diagnostics and launch code."""

import re

from acp_common import FACTORS, HERE
from launch_p5 import validate_budget, validate_pair

from disastertrace.local_eval.storage import digest, fingerprint, inventory, now, read, write
from disastertrace.stress_eval import execution


def main():
    old = read(HERE / "OFFLINE_ACCEPTANCE.json")
    files = dict(old["evidence_sha256"])
    names = [
        "OFFLINE_ACCEPTANCE.json",
        "inherited_acceptance_verified.json",
        "preservation_before_acp.json",
        "ACP_EXECUTION_PLAN.md",
        "verify_existing.py",
        "acp_common.py",
        "acp_preflight.py",
        "submit_preflight.py",
        "inspect_acp.py",
        "prepare_live.py",
        "launch_p5.py",
        "acp_worker.py",
        "test_acp_launcher.py",
        "freeze_live_acceptance.py",
    ]
    for name in ("inherited_acceptance_verified.json", "preservation_before_acp.json"):
        if read(HERE / name)["status"] != "passed":
            raise ValueError("fresh inherited acceptance verification required")
    preflight = HERE / "acp/preflight_001"
    verified = read(preflight / "verified_job.json")
    result = read(preflight / "worker_result.json")
    if (
        verified["status"] != "passed"
        or result["status"] != "passed"
        or verified["result_sha256"] != digest(preflight / "worker_result.json")
        or verified["model_calls"] != 0
    ):
        raise ValueError("verified actual ACP preflight required")
    for path in preflight.rglob("*"):
        if path.is_file() and "cache" not in path.relative_to(preflight).parts:
            names.append(str(path.relative_to(HERE)))
    plans, units = {}, {}
    for factor in FACTORS:
        unit = HERE / "units" / factor
        live, _, _ = execution.verify(unit / "execution_live")
        offline, _, _ = execution.verify(unit / "execution_offline")
        validate_pair(live, offline, factor)
        done = read(unit / "live_preparation/completion.json")
        report = read(unit / "live_diagnostic_report/report.json")
        if (
            done["status"] != "passed"
            or not done["same_method_scores_as_offline"]
            or done["model_calls"] != 0
            or report["received"] != 540
            or not report["complete"]
            or report["origin"] != "diagnostic_stress_fixture"
            or report["errors"] != {"fields": [], "actions": []}
            or report["execution_id"] != live["execution_id"]
        ):
            raise ValueError("full exact live diagnostic required")
        plans[factor] = live
        units[factor] = {
            "execution_id": live["execution_id"],
            "dataset_content_id": live["dataset_content_id"],
            "diagnostic_audit_id": report["audit_id"],
            "run_path": live["run_path"],
        }
        for directory in (
            "execution_live",
            "live_diagnostic",
            "live_diagnostic_report",
            "live_preparation",
        ):
            for name in inventory(unit / directory):
                if "cache" not in name.split("/"):
                    names.append(f"units/{factor}/{directory}/{name}")
    validate_budget(plans)
    for step in (
        "inherited_acceptance_check_revised",
        "preservation_before_acp",
        "lint_acp_preflight",
        "verify_acp_preflight",
        "tests_acp_launcher",
        "lint_acp_launcher",
        "prepare_live_revision_chain",
        "prepare_live_irrelevant_scope",
        "prepare_live_late_stale_replay",
    ):
        directory = HERE / "validation" / step
        outcome = read(directory / "result.json")
        if outcome["exit_code"] != 0 or outcome["log_sha256"] != digest(directory / "stdout.log"):
            raise ValueError("required validation failed or changed: " + step)
        for name in inventory(directory):
            names.append(f"validation/{step}/{name}")
    for name in names:
        files[name] = digest(HERE / name)
    for name, expected in files.items():
        if digest(HERE / name) != expected:
            raise ValueError("acceptance input changed: " + name)
    tests = re.findall(
        r"\b(\d+) passed\b", (HERE / "validation/tests_acp_launcher/stdout.log").read_text()
    )
    accepted = {
        "schema_version": "p5_acp_live_acceptance_v1",
        "status": "passed",
        "at": now(),
        "max_model_responses": 1620,
        "parallel_gpus": 3,
        "user_gpu_cap": 4,
        "deadline_utc": next(iter(plans.values()))["deadline_utc"],
        "model_calls_before_launch": 0,
        "paid_api_calls": 0,
        "heldout_calls": 0,
        "new_launcher_tests_passed": int(tests[-1]),
        "inherited_tests_verified": old["tests"],
        "units": units,
        "acp_preflight_job_id": verified["job_id"],
        "evidence_sha256": files,
        "hardware_note": "P4 used H100 MIG; P5 uses one full H100 per factor. Timing is descriptive.",
    }
    accepted["acceptance_id"] = fingerprint(accepted)
    write(HERE / "LIVE_ACCEPTANCE.json", accepted)
    print({k: v for k, v in accepted.items() if k != "evidence_sha256"})


if __name__ == "__main__":
    main()
