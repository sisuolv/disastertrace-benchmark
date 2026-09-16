"""One phase claim, one submission per worker, including uncertain submission outcomes."""

from pathlib import Path

from disastertrace.forecast_task.common import fingerprint, read

from . import acp, package
from .storage import now, write


def validate_preflight(proof, plan=None):
    from .backend import validate_observation

    request, result, job, preplan = (proof[k] for k in ("request", "result", "job", "execution"))
    if (
        result["status"] != "passed"
        or result["generate_disabled"] is not True
        or type(result["model_calls"]) is not int
        or result["model_calls"] != 0
        or result["request_sha256"] != fingerprint(request)
        or request["kind"] != "preflight"
        or request["execution_id"] != preplan["execution_id"]
        or result["hostname"] == request["source_cci_hostname"]
        or job["state"] != "SUCCEEDED"
        or job["cluster"] != acp.CLUSTER
        or type(job["gpu_count"]) is not int
        or job["gpu_count"] != 1
        or not job["job_id"].startswith("pt-")
        or job["released"] is not True
        or job["display_name"] != request["display_name"]
        or preplan["kind"] != "preflight"
        or preplan["generation_authorized"] is not False
        or request["source_files"] != preplan["source_files"]
    ):
        raise ValueError("preflight does not establish a released no-generation H100 load")
    validate_observation(result["runtime_observation"], preplan)
    if plan is not None:
        if any(
            plan[k] != preplan[k]
            for k in (
                "settings",
                "source_files",
                "model_identity",
                "backend_files",
                "environment_sha256",
                "task_package_id",
            )
        ):
            raise ValueError("live implementation/resources differ from actual preflight")
        validation = proof.get("validation")
        if not validation or validation["status"] != "passed":
            raise ValueError("preflight lacks saved validation evidence")


def validate_cpu(proof, plan):
    if (
        proof["status"] != "passed"
        or proof["model_calls"] != 0
        or proof["source_files"] != plan["source_files"]
        or proof["settings"] != plan["settings"]
        or proof["task_package_id"] != plan["task_package_id"]
        or proof["core_tests_exit_code"] != 0
        or proof["backend_tests_exit_code"] != 0
        or proof["portable_review_exit_code"] != 0
    ):
        raise ValueError("live freeze lacks current offline validation")
    expected = {
        "latest_explicit": (1542, 1542),
        "invalid_even": (1542, 780),
        "missing_even": (1542, 780),
    }
    for policy, (planned, correct) in expected.items():
        record = proof["diagnostics"][policy]
        if (
            record["planned"] != planned
            or record["all_correct"] != correct
            or record["verified"] is not True
            or record["attempted"] != 1542
        ):
            raise ValueError("full four-worker diagnostic validation differs")


def submit_phase(root, directory):
    root, directory = Path(root).resolve(), Path(directory).resolve()
    plan, _, slots = package.verify(root, code=True)
    if plan["kind"] not in ("preflight", "model"):
        raise ValueError("diagnostic package has no ACP dispatch path")
    live = plan["kind"] == "model"
    if live:
        validate_cpu(read(root / "validation.json"), plan)
        if package.past_deadline(plan) or Path(plan["run_root"]).exists():
            raise ValueError("deadline or existing run consumes launch")
    phase = {
        "execution_id": plan["execution_id"],
        "phase_id": plan["phase_id"],
        "kind": plan["kind"],
        "source_files": plan["source_files"],
        "submission_directory": str(directory),
        "at": now(),
        "workers": 4 if live else 1,
    }
    claim_path = Path(plan["launch_registry"]) / "phase_submit.json"
    write(claim_path, phase)
    directory.mkdir(parents=True, exist_ok=False)
    write(directory / "phase.json", phase)
    results = []
    for worker in range(phase["workers"]):
        target = directory / f"worker-{worker}"
        request = {
            "kind": plan["kind"],
            "execution_id": plan["execution_id"],
            "phase_id": plan["phase_id"],
            "execution_path": str(root),
            "source_files": plan["source_files"],
            "worker_id": worker,
            "phase_claim": str(claim_path),
            "phase_claim_sha256": fingerprint(phase),
            "max_model_attempts": sum(s["worker_id"] == worker for s in slots) if live else 0,
            "display_name": f"dt-p7-{plan['kind']}-{plan['phase_id'][:10]}-w{worker}",
            "command": acp.command_for(
                target / "request.json", root / "source", 14400 if live else 1800
            ),
        }
        try:
            submission = acp.submit(target, request)
            results.append({"worker_id": worker, "status": "submitted", **submission})
        except Exception as exc:  # noqa: BLE001 - durable uncertain submission, never retry
            # This worker is consumed. Independent remaining workers retain their own claims.
            failure = {
                "worker_id": worker,
                "status": "submission_failed_or_unknown",
                "error": type(exc).__name__ + ": " + str(exc),
                "at": now(),
            }
            write(directory / f"worker-{worker}-submission-failure.json", failure)
            results.append(failure)
    write(directory / "submission_summary.json", results)
    return results
