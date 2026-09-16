"""Bound submissions; a request directory consumes the sole submission attempt."""

from datetime import datetime, timezone
from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.local_eval.storage import digest, read

from . import acp, package


def validate_acceptance(execution, value):
    plan, _, _ = package.verify(execution)
    if (
        value["acceptance_id"]
        != fingerprint({k: v for k, v in value.items() if k != "acceptance_id"})
        or value["status"] != "live_ready"
        or value["execution_id"] != plan["execution_id"]
        or value["implementation_files"] != plan["implementation_files"]
        or value["new_tests_passed"] is not True
        or value["model_generations"] != 0
        or set(value["diagnostics"]) != {"correct", "invalid-control"}
    ):
        raise ValueError("live acceptance differs")
    for mode, proof in value["diagnostics"].items():
        audit, score = proof["audit"], proof["score_counts"]
        if (
            audit["complete"] is not True
            or audit["model_result"] is not False
            or audit["execution_id"] != plan["execution_id"]
            or audit["mode"] != mode
            or audit["received"] != 2160
            or audit["additional_model_calls"] != 0
            or score["all_correct"] != (2160 if mode == "correct" else 1728)
            or proof["verified"] is not True
        ):
            raise ValueError("full live-source diagnostic acceptance required")


def submit(execution, directory, kind, *, acceptance=None, report=None):
    path, directory = Path(execution).resolve(), Path(directory).resolve()
    plan, _, _ = package.verify(path)
    if kind == "preflight":
        if plan["generation_authorized"] or plan["fixture"]:
            raise ValueError("preflight requires generation-disabled real resources")
        seconds = 1200
    elif kind == "model":
        if not plan["generation_authorized"] or acceptance is None or report is None:
            raise ValueError("live execution and full acceptance required")
        validate_acceptance(path, read(acceptance))
        if datetime.now(timezone.utc) >= datetime.fromisoformat(plan["deadline_utc"]):
            raise ValueError("deadline passed")
        if Path(plan["run_path"]).exists() or Path(report).exists():
            raise FileExistsError("model run or report already exists")
        claim = Path(plan["registry_path"]) / (plan["execution_id"] + "-model.json")
        if claim.exists():
            raise FileExistsError("model claim consumed")
        seconds = plan["max_worker_seconds"] + 1800
    else:
        raise ValueError("unsupported launch kind")
    # Canonical submission registry prevents bypassing a consumed directory with another path.
    from disastertrace.repeat_eval.storage import atomic_write

    atomic_write(
        Path(plan["registry_path"]) / (plan["execution_id"] + "-submit-" + kind + ".json"),
        {"execution_id": plan["execution_id"], "submission_directory": str(directory)},
    )
    request = {
        "kind": kind,
        "execution_path": str(path),
        "execution_id": plan["execution_id"],
        "project": str(package.PROJECT),
        "implementation_files": plan["implementation_files"],
        "max_model_attempts": 2160 if kind == "model" else 0,
        "display_name": "dt-p6-" + kind + "-" + plan["execution_id"][:12],
        "command": acp.command_for(
            directory / "request.json", path / "implementation_source/src", seconds
        ),
        "worker_seconds": seconds,
        "acceptance_path": str(Path(acceptance).resolve()) if acceptance else None,
        "acceptance_sha256": digest(acceptance) if acceptance else None,
        "report_path": str(Path(report).resolve()) if report else None,
    }
    return acp.submit(directory, request)
