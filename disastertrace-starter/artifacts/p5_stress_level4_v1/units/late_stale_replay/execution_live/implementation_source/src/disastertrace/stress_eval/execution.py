"""Bind each stress factor to fresh data, source, settings and a one-use scope."""

import shutil
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.constrained_eval import adapter, contract
from disastertrace.constrained_eval import execution as parent_execution
from disastertrace.local_eval.execution import RELIABILITY, verify_model
from disastertrace.local_eval.storage import digest, now, read, seal, verify_seal, write

from . import data

PROJECT = Path(__file__).resolve().parents[3]
BACKEND_FILES = parent_execution.BACKEND_FILES
backend_inventory = parent_execution.backend_inventory
SCOPE = {
    "kind": "offline_stress_level4_candidate",
    "model_calls": 0,
    "paid_api_calls": 0,
    "heldout_calls": 0,
    "training": False,
    "new_human_annotations": 0,
    "llm_judge": False,
    "production_authorized": False,
}
LIVE_SCOPE = {
    **SCOPE,
    "kind": "one_stress_level4_factor_matrix",
    "model_calls": 540,
    "production_authorized": True,
}
LIVE_AUTHORIZATION = {
    "basis_date": "2026-09-08",
    "basis": "User asks to proceed with the next phase; automatic GPU permission persists.",
    "bounded_scope": "One factor, 540 local responses, three methods, one repeat, no retries",
    "phase_total_response_cap": 1620,
    "paid_api_calls": 0,
}


def source_inventory():
    files = dict(parent_execution.source_inventory())
    for path in sorted((PROJECT / "src/disastertrace/stress_eval").glob("*.py")):
        files[str(path.relative_to(PROJECT))] = digest(path)
    for name in ("docs/P5_STRESS_LEVEL4_V1.md", "tests/test_stress_level4.py"):
        files[name] = digest(PROJECT / name)
    return files


def freeze(parent, dataset, output, *, live=False, run_path=None, deadline_utc=None):
    parent, dataset, output = map(Path, (parent, dataset, output))
    if output.exists():
        raise ValueError("preserve previous stress execution")
    if live:
        if run_path is None or deadline_utc is None:
            raise ValueError("fresh canonical path and deadline required")
        deadline = datetime.fromisoformat(deadline_utc)
        if deadline.tzinfo is None or deadline <= datetime.now(timezone.utc):
            raise ValueError("future aware deadline required")
        if Path(run_path).exists():
            raise ValueError("canonical stress claim already exists")
    elif run_path is not None or deadline_utc is not None:
        raise ValueError("offline candidate has no production path or deadline")
    original, _, _ = parent_execution.verify(parent)
    profile, _, _ = data.verify(dataset)
    if profile["base_dataset_content_id"] != original["dataset_content_id"]:
        raise ValueError("stress profile has a different balanced parent")
    if read(dataset / "base_dataset/manifest.json")["package_id"] != original["dataset_package_id"]:
        raise ValueError("stress base dataset package differs from P4")
    if live and str(Path(run_path).resolve()) == original["run_path"]:
        raise ValueError("historical run cannot be reused")
    files = source_inventory()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(dataset, output / "dataset")
    for directory in ("model_config", "backend_source"):
        shutil.copytree(parent / directory, output / directory)
    for name in ("model_snapshot.json", "environment.json", "constraint.json"):
        shutil.copyfile(parent / name, output / name)
    shutil.copyfile(parent / "execution.json", output / "parent_execution.json")
    for name in files:
        target = output / "implementation_source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / name, target)
    plan = {
        "schema_version": "stress_level4_execution_v1",
        "created_at": now(),
        "parent_execution_id": original["execution_id"],
        "base_dataset_content_id": original["dataset_content_id"],
        "base_dataset_package_id": original["dataset_package_id"],
        "dataset_content_id": profile["dataset_content_id"],
        "dataset_package_id": read(dataset / "manifest.json")["package_id"],
        "stress_profile": {
            key: profile[key]
            for key in (
                "profile",
                "factor",
                "level",
                "candidate_package_id",
                "zero_effect_episodes",
            )
        },
        "implementation_files": files,
        **{
            key: original[key]
            for key in (
                "model_snapshot_sha256",
                "model_config_files",
                "environment_sha256",
                "backend_files",
            )
        },
        "settings": adapter.SETTINGS,
        "scope": LIVE_SCOPE if live else SCOPE,
        "authorization": LIVE_AUTHORIZATION if live else None,
        "run_path": str(Path(run_path).resolve()) if live else None,
        "deadline_utc": deadline_utc,
        "max_attempts": 540 if live else 0,
        "planned_responses": 540,
        "repeats": 1,
        "retries": 0,
        "diagnostic_probes": 0,
        "reliability_rule": RELIABILITY,
    }
    plan["execution_id"] = fingerprint(plan)
    write(output / "execution.json", plan)
    seal(output)
    return plan


def verify(output, *, model_hashes=False):
    output = Path(output)
    verify_seal(output)
    plan = read(output / "execution.json")
    if plan["execution_id"] != fingerprint({k: v for k, v in plan.items() if k != "execution_id"}):
        raise ValueError("stress execution identity mismatch")
    if (
        plan["schema_version"] != "stress_level4_execution_v1"
        or plan["settings"] != adapter.SETTINGS
        or plan["scope"] not in (SCOPE, LIVE_SCOPE)
        or plan["planned_responses"] != 540
        or plan["repeats"] != 1
        or plan["retries"] != 0
        or plan["diagnostic_probes"] != 0
        or plan["reliability_rule"] != RELIABILITY
    ):
        raise ValueError("stress settings or scope mismatch")
    live = plan["scope"] == LIVE_SCOPE
    if plan["authorization"] != (LIVE_AUTHORIZATION if live else None) or plan["max_attempts"] != (
        540 if live else 0
    ):
        raise ValueError("stress authorization mismatch")
    if live:
        if (
            not isinstance(plan["run_path"], str)
            or not Path(plan["run_path"]).is_absolute()
            or datetime.fromisoformat(plan["deadline_utc"]).tzinfo is None
        ):
            raise ValueError("canonical stress path or aware deadline missing")
    elif plan["run_path"] is not None or plan["deadline_utc"] is not None:
        raise ValueError("offline stress candidate has live metadata")
    if source_inventory() != plan["implementation_files"]:
        raise ValueError("loaded stress source differs from frozen implementation")
    for name, expected in plan["implementation_files"].items():
        if digest(output / "implementation_source" / name) != expected:
            raise ValueError("stress source digest mismatch")
    original = read(output / "parent_execution.json")
    if (
        fingerprint({k: v for k, v in original.items() if k != "execution_id"})
        != original["execution_id"]
        or original["execution_id"] != plan["parent_execution_id"]
    ):
        raise ValueError("stress parent execution mismatch")
    if (
        original["schema_version"] != "constrained_offline_execution_v1"
        or original["settings"] != adapter.SETTINGS
    ):
        raise ValueError("P4 constrained parent required")
    if (
        plan["base_dataset_content_id"] != original["dataset_content_id"]
        or plan["base_dataset_package_id"] != original["dataset_package_id"]
    ):
        raise ValueError("balanced parent identity changed")
    if live and plan["run_path"] == original["run_path"]:
        raise ValueError("historical run cannot be reused")
    for key in (
        "model_snapshot_sha256",
        "model_config_files",
        "environment_sha256",
        "backend_files",
    ):
        if plan[key] != original[key]:
            raise ValueError("P4 model, tokenizer or backend changed")
    if (
        fingerprint(read(output / "model_snapshot.json")) != plan["model_snapshot_sha256"]
        or fingerprint(read(output / "environment.json")) != plan["environment_sha256"]
    ):
        raise ValueError("model or environment binding changed")
    if set(plan["backend_files"]) != set(BACKEND_FILES):
        raise ValueError("backend source inventory changed")
    for name, expected in plan["backend_files"].items():
        if digest(output / "backend_source" / name) != expected:
            raise ValueError("backend source changed")
    snapshot_files = {
        "model_config/" + entry["path"]: entry["sha256"]
        for entry in read(output / "model_snapshot.json")["files"]
        if not entry["path"].endswith(".safetensors")
    }
    if snapshot_files != plan["model_config_files"]:
        raise ValueError("tokenizer/config not bound to the model snapshot")
    for name, expected in snapshot_files.items():
        if digest(output / name) != expected:
            raise ValueError("tokenizer/config digest mismatch")
    if read(output / "constraint.json") != {
        "identity": contract.identity(),
        "json": contract.schema_text(),
    }:
        raise ValueError("P4 structural grammar changed")
    profile, episodes, slots = data.verify(output / "dataset", full=False)
    if (
        profile["dataset_content_id"] != plan["dataset_content_id"]
        or read(output / "dataset/manifest.json")["package_id"] != plan["dataset_package_id"]
    ):
        raise ValueError("stress dataset identity mismatch")
    if {
        key: profile[key]
        for key in ("profile", "factor", "level", "candidate_package_id", "zero_effect_episodes")
    } != plan["stress_profile"]:
        raise ValueError("stress factor metadata mismatch")
    if (
        profile["base_dataset_content_id"] != plan["base_dataset_content_id"]
        or read(output / "dataset/base_dataset/manifest.json")["package_id"]
        != plan["base_dataset_package_id"]
    ):
        raise ValueError("stress dataset has a different parent")
    if model_hashes:
        verify_model(read(output / "model_snapshot.json"))
    return plan, episodes, slots
