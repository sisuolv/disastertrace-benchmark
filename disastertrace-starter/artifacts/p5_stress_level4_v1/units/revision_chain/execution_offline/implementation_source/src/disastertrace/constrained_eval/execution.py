"""Freeze an offline candidate independently of all consumed production claims."""

import importlib.metadata
import shutil
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.local_eval import data
from disastertrace.local_eval import execution as parent_execution
from disastertrace.local_eval.runtime import environment
from disastertrace.local_eval.storage import digest, now, read, seal, verify_seal, write

from . import adapter, contract

PROJECT = Path(__file__).resolve().parents[3]
BACKEND_FILES = (
    "vllm/sampling_params.py",
    "vllm/config/__init__.py",
    "vllm/engine/arg_utils.py",
    "vllm/v1/core/sched/scheduler.py",
    "vllm/v1/structured_output/__init__.py",
    "vllm/v1/structured_output/backend_xgrammar.py",
    "vllm/reasoning/qwen3_reasoning_parser.py",
    "xgrammar/compiler.py",
    "xgrammar/grammar.py",
    "xgrammar/matcher.py",
    "xgrammar/tokenizer_info.py",
)
SCOPE = {
    "kind": "offline_candidate_only",
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
    "kind": "one_constrained_local_development_matrix",
    "model_calls": 540,
    "production_authorized": True,
}
LIVE_AUTHORIZATION = {
    "basis_date": "2026-09-08",
    "basis": "User requests continued optimization and explicitly permits automatic GPU use.",
    "bounded_scope": "540 local responses, three methods, one repeat, no retries or extra probes",
    "paid_api_calls": 0,
}


def source_inventory():
    files = dict(parent_execution.source_inventory())
    for path in sorted((PROJECT / "src/disastertrace/constrained_eval").glob("*.py")):
        files[str(path.relative_to(PROJECT))] = digest(path)
    for name in ("docs/P4_CONSTRAINED_OUTPUT_V1.md", "tests/test_constrained_eval.py"):
        files[name] = digest(PROJECT / name)
    return files


def backend_inventory():
    result = {}
    for name in BACKEND_FILES:
        distribution = importlib.metadata.distribution(name.split("/")[0])
        result[name] = digest(distribution.locate_file(name))
    return result


def freeze(parent, output, *, live=False, run_path=None, deadline_utc=None):
    parent, output = Path(parent), Path(output)
    if output.exists():
        raise ValueError("preserve previous constrained candidate")
    if live:
        if run_path is None or deadline_utc is None:
            raise ValueError("fresh canonical path and deadline required")
        deadline = datetime.fromisoformat(deadline_utc)
        if deadline.tzinfo is None or deadline <= datetime.now(timezone.utc):
            raise ValueError("future aware deadline required")
        if Path(run_path).exists():
            raise ValueError("canonical local claim already exists")
    elif run_path is not None or deadline_utc is not None:
        raise ValueError("offline candidates have no production path/deadline")
    original, _, _ = parent_execution.verify(parent)
    observed = environment()
    if observed != read(parent / "environment.json"):
        raise ValueError("historical runtime environment changed")
    if observed["packages"]["xgrammar"] != adapter.SETTINGS["xgrammar_version"]:
        raise ValueError("XGrammar version mismatch")
    files, backend_files = source_inventory(), backend_inventory()
    output.mkdir(parents=True, exist_ok=False)
    for directory in ("dataset", "model_config"):
        shutil.copytree(parent / directory, output / directory)
    for name in ("model_snapshot.json", "environment.json"):
        shutil.copyfile(parent / name, output / name)
    shutil.copyfile(parent / "execution.json", output / "parent_execution.json")
    for name in files:
        target = output / "implementation_source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / name, target)
    for name in backend_files:
        target = output / "backend_source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        distribution = importlib.metadata.distribution(name.split("/")[0])
        shutil.copyfile(distribution.locate_file(name), target)
    write(
        output / "constraint.json",
        {"identity": contract.identity(), "json": contract.schema_text()},
    )
    plan = {
        "schema_version": "constrained_offline_execution_v1",
        "created_at": now(),
        "parent_execution_id": original["execution_id"],
        "dataset_content_id": original["dataset_content_id"],
        "dataset_package_id": original["dataset_package_id"],
        "model_snapshot_sha256": original["model_snapshot_sha256"],
        "environment_sha256": fingerprint(observed),
        "model_config_files": read(parent / "manifest.json")["files"],
        "implementation_files": files,
        "backend_files": backend_files,
        "settings": adapter.SETTINGS,
        "scope": LIVE_SCOPE if live else SCOPE,
        "authorization": LIVE_AUTHORIZATION if live else None,
        "run_path": str(Path(run_path).resolve()) if live else None,
        "deadline_utc": deadline_utc,
        "max_attempts": 540 if live else 0,
        "repeats": 1,
        "retries": 0,
        "diagnostic_probes": 0,
        "planned_responses": 540,
        "reliability_rule": parent_execution.RELIABILITY,
    }
    plan["model_config_files"] = {
        k: v for k, v in plan["model_config_files"].items() if k.startswith("model_config/")
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
        raise ValueError("constrained execution identity mismatch")
    if (
        plan["schema_version"] != "constrained_offline_execution_v1"
        or plan["settings"] != adapter.SETTINGS
        or plan["scope"] not in (SCOPE, LIVE_SCOPE)
        or plan["planned_responses"] != 540
        or plan["repeats"] != 1
        or plan["retries"] != 0
        or plan["diagnostic_probes"] != 0
        or plan["reliability_rule"] != parent_execution.RELIABILITY
    ):
        raise ValueError("constrained settings/scope mismatch")
    live = plan["scope"] == LIVE_SCOPE
    if plan["authorization"] != (LIVE_AUTHORIZATION if live else None) or plan["max_attempts"] != (
        540 if live else 0
    ):
        raise ValueError("constrained authorization mismatch")
    if live:
        if (
            not isinstance(plan["run_path"], str)
            or not Path(plan["run_path"]).is_absolute()
            or datetime.fromisoformat(plan["deadline_utc"]).tzinfo is None
        ):
            raise ValueError("canonical path/deadline missing")
    elif plan["run_path"] is not None or plan["deadline_utc"] is not None:
        raise ValueError("offline candidate has production metadata")
    if source_inventory() != plan["implementation_files"]:
        raise ValueError("loaded source differs from constrained freeze")
    for name, expected in plan["implementation_files"].items():
        if digest(output / "implementation_source" / name) != expected:
            raise ValueError("constrained source digest mismatch")
    if set(plan["backend_files"]) != set(BACKEND_FILES):
        raise ValueError("backend evidence inventory mismatch")
    for name, expected in plan["backend_files"].items():
        if digest(output / "backend_source" / name) != expected:
            raise ValueError("backend evidence digest mismatch")
    if read(output / "constraint.json") != {
        "identity": contract.identity(),
        "json": contract.schema_text(),
    }:
        raise ValueError("constraint byte/order binding mismatch")
    original = read(output / "parent_execution.json")
    original_id = fingerprint({k: v for k, v in original.items() if k != "execution_id"})
    if original_id != original["execution_id"] or original_id != plan["parent_execution_id"]:
        raise ValueError("parent execution mismatch")
    if live and plan["run_path"] == original["run_path"]:
        raise ValueError("historical production claim cannot be reused")
    for key in (
        "dataset_content_id",
        "dataset_package_id",
        "model_snapshot_sha256",
        "environment_sha256",
    ):
        if plan[key] != original[key]:
            raise ValueError("parent semantic/model binding mismatch")
    if fingerprint(read(output / "model_snapshot.json")) != plan["model_snapshot_sha256"]:
        raise ValueError("model snapshot mismatch")
    if fingerprint(read(output / "environment.json")) != plan["environment_sha256"]:
        raise ValueError("environment mismatch")
    snapshot_files = {
        "model_config/" + entry["path"]: entry["sha256"]
        for entry in read(output / "model_snapshot.json")["files"]
        if not entry["path"].endswith(".safetensors")
    }
    if snapshot_files != plan["model_config_files"]:
        raise ValueError("tokenizer/config not bound to model snapshot")
    for name, expected in snapshot_files.items():
        if digest(output / name) != expected:
            raise ValueError("tokenizer/config digest mismatch")
    metadata, episodes, slots = data.verify(output / "dataset", full=False)
    if (
        metadata["dataset_content_id"] != plan["dataset_content_id"]
        or read(output / "dataset/manifest.json")["package_id"] != plan["dataset_package_id"]
    ):
        raise ValueError("balanced dataset identity mismatch")
    if model_hashes:
        parent_execution.verify_model(read(output / "model_snapshot.json"))
    return plan, episodes, slots
