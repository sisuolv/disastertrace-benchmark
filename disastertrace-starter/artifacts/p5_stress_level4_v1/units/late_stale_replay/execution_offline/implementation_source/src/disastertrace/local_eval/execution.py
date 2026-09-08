"""Freeze all task/runtime inputs before observing new model responses."""

import shutil
from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.controlled.package import implementation

from . import adapter, data
from .storage import digest, now, read, seal, verify_seal, write

PROJECT = Path(__file__).resolve().parents[3]
RELIABILITY = {"planned_per_family_method": 60, "min_schema_valid": 58, "max_length": 2}


def source_inventory():
    files = dict(implementation()["files"])
    for p in sorted((PROJECT / "src/disastertrace/local_eval").glob("*.py")):
        files[str(p.relative_to(PROJECT))] = digest(p)
    files["docs/P3_LOCAL_BALANCED_V1.md"] = digest(PROJECT / "docs/P3_LOCAL_BALANCED_V1.md")
    return files


def verify_model(snapshot, *, hashes=True):
    root = Path(snapshot["local_path"])
    for entry in snapshot["files"]:
        from disastertrace.automated.common import safe_child

        path = safe_child(root, entry["path"])
        if not path.is_file() or path.stat().st_size != entry["bytes"]:
            raise ValueError("model snapshot size mismatch")
        if hashes and digest(path) != entry["sha256"]:
            raise ValueError("model snapshot digest mismatch")
    names = {f["path"] for f in snapshot["files"]}
    index = read(root / "model.safetensors.index.json")
    if not set(index["weight_map"].values()) <= names:
        raise ValueError("model snapshot lacks indexed weights")


def freeze(dataset, snapshot_path, environment_path, output, *, deadline_utc, run_path):
    output = Path(output)
    if output.exists():
        raise ValueError("preserve previous execution")
    plan, _, _ = data.verify(dataset)
    snapshot = read(snapshot_path)
    verify_model(snapshot)
    environment = read(environment_path)
    if environment["packages"]["vllm"] != adapter.SETTINGS["runtime_version"]:
        raise ValueError("runtime version mismatch")
    files = source_inventory()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(dataset, output / "dataset")
    for name in files:
        target = output / "implementation_source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / name, target)
    write(output / "model_snapshot.json", snapshot)
    for entry in snapshot["files"]:
        if not entry["path"].endswith(".safetensors"):
            target = output / "model_config" / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(snapshot["local_path"]) / entry["path"], target)
    write(output / "environment.json", environment)
    execution = {
        "schema_version": "local_balanced_execution_v1",
        "created_at": now(),
        "dataset_content_id": plan["dataset_content_id"],
        "dataset_package_id": read(Path(dataset) / "manifest.json")["package_id"],
        "implementation_files": files,
        "model_snapshot_sha256": fingerprint(snapshot),
        "environment_sha256": fingerprint(environment),
        "settings": adapter.SETTINGS,
        "planned_responses": 540,
        "max_attempts": 540,
        "repeats": 1,
        "retries": 0,
        "diagnostic_probes": 0,
        "heldout_calls": 0,
        "training": False,
        "deadline_utc": deadline_utc,
        "run_path": str(Path(run_path).resolve()),
        "reliability_rule": RELIABILITY,
        "authorization": {
            "scope": "one balanced local GPU development matrix",
            "user_instruction_summary": "Autonomous next-phase work; review in 4h; GPU permitted.",
            "paid_api_calls": 0,
            "basis": "current user instruction 2026-09-07",
        },
    }
    execution["execution_id"] = fingerprint(execution)
    write(output / "execution.json", execution)
    seal(output)
    return execution


def verify(output, *, full_data=False, model_hashes=False):
    output = Path(output)
    verify_seal(output)
    execution = read(output / "execution.json")
    if execution["execution_id"] != fingerprint(
        {k: v for k, v in execution.items() if k != "execution_id"}
    ):
        raise ValueError("execution identity mismatch")
    if (
        execution["settings"] != adapter.SETTINGS
        or execution["max_attempts"] != 540
        or execution["planned_responses"] != 540
        or execution["reliability_rule"] != RELIABILITY
        or execution["repeats"] != 1
        or execution["retries"] != 0
        or execution["heldout_calls"] != 0
        or execution["diagnostic_probes"] != 0
        or execution["training"] is not False
        or execution["authorization"]["paid_api_calls"] != 0
    ):
        raise ValueError("execution settings/scope mismatch")
    if source_inventory() != execution["implementation_files"]:
        raise ValueError("loaded source differs from frozen implementation")
    for name, value in execution["implementation_files"].items():
        if digest(output / "implementation_source" / name) != value:
            raise ValueError("frozen implementation mismatch")
    if fingerprint(read(output / "model_snapshot.json")) != execution["model_snapshot_sha256"]:
        raise ValueError("model identity mismatch")
    if fingerprint(read(output / "environment.json")) != execution["environment_sha256"]:
        raise ValueError("environment identity mismatch")
    plan, episodes, slots = data.verify(output / "dataset", full=full_data)
    if plan["dataset_content_id"] != execution["dataset_content_id"]:
        raise ValueError("dataset binding mismatch")
    if read(output / "dataset/manifest.json")["package_id"] != execution["dataset_package_id"]:
        raise ValueError("dataset package binding mismatch")
    if model_hashes:
        verify_model(read(output / "model_snapshot.json"))
    return execution, episodes, slots
