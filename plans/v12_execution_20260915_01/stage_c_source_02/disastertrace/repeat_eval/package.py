"""Freeze a CPU-verifiable candidate; no live authorization or consumed P5 claim is copied."""

import shutil
from copy import deepcopy
from pathlib import Path

from disastertrace.automated.common import canonical, fingerprint
from disastertrace.constrained_eval import adapter, contract
from disastertrace.constrained_eval.execution import BACKEND_FILES
from disastertrace.local_eval.adapter import FixtureTokenizer
from disastertrace.local_eval.storage import digest, read, seal, verify_seal, write
from disastertrace.stress_eval.execution import source_inventory as inherited_sources

from . import protocol

PROJECT = Path(__file__).resolve().parents[3]

RUNTIME_PROFILE = {
    "required_hardware": "full_H100_80GB_single_gpu",
    "hardware_verified": False,
    "engine_seed": adapter.SETTINGS["seed"],
    "vllm_use_v1": "1",
    "v1_multiprocessing": "0",
    "multiprocessing_policy_is_new_common_profile": True,
    "gpu_preflight_performed": False,
    "condition_order": "paired_adjacent_counterbalanced_by_base_method_index_and_repeat",
    "max_parallel_gpus": 4,
}
FIXED = {
    "schema_version": protocol.VERSION,
    "settings": adapter.SETTINGS,
    "conditions": list(protocol.CONDITIONS),
    "methods": list(protocol.METHODS),
    "generation_authorized": False,
    "max_model_attempts": 0,
    "response_cache": False,
    "retries": 0,
    "repair": False,
    "runtime_profile": RUNTIME_PROFILE,
    "sampling_scheme": "paired_sampling_v1",
    "analysis": "closed_loop_total_trajectory_comparison",
    "reliability": {"per_condition_repeat_method_family": 60, "minimum_valid": 58, "max_length": 2},
    "scope": "offline_preparation_and_program_diagnostics_only",
}


def source_inventory():
    files = inherited_sources()
    for directory in ("post_p5", "repeat_eval"):
        for path in sorted((PROJECT / "src/disastertrace" / directory).glob("*.py")):
            files[str(path.relative_to(PROJECT))] = digest(path)
    return files


def freeze(datasets, output, registry, *, repeats=2, resource=None, fixture=False):
    output = Path(output)
    if output.exists():
        raise FileExistsError("candidate output already exists")
    mapping = protocol.dataset_mapping(datasets)
    if type(fixture) is not bool:
        raise ValueError("explicit fixture boolean required")
    if not fixture and (
        len(mapping) != 36
        or {x["group_id"] for x in mapping} != {"AL092021", "AL062018", "AL052019"}
    ):
        raise ValueError("full balanced development cohort required")
    if not fixture and resource is None:
        raise ValueError("actual tokenizer/model resource binding required")
    sources = source_inventory()
    model_snapshot = None if fixture else read(Path(resource) / "model_snapshot.json")
    model_identity = (
        "synthetic_diagnostic_fixture"
        if fixture
        else fingerprint({"model_id": model_snapshot["model_id"], "files": model_snapshot["files"]})
    )
    plan = {
        **deepcopy(FIXED),
        "repeats": repeats,
        "mapping": mapping,
        "model_identity": model_identity,
        "data_sha256": fingerprint(datasets),
        "registry_path": str(Path(registry).resolve()),
        "implementation_files": sources,
        "fixture": fixture,
        "planned_responses": len(mapping) * 5 * 3 * 2 * repeats,
        "planned_trajectories": len(mapping) * 3 * 2 * repeats,
        "generation_token_reservation": len(mapping) * 5 * 3 * 2 * repeats * 8192,
    }
    plan["experiment_id"] = fingerprint(plan)
    slots = protocol.schedule(plan)
    plan["schedule_sha256"] = fingerprint(slots)
    output.mkdir(parents=True)
    write(output / "datasets.json", datasets)
    write(output / "schedule.json", slots)
    if not fixture:
        resource = Path(resource)
        for folder in ("model_config", "backend_source"):
            shutil.copytree(resource / folder, output / folder)
        for name in ("model_snapshot.json", "environment.json", "constraint.json"):
            shutil.copyfile(resource / name, output / name)
        plan["resource_files"] = {
            str(p.relative_to(output)): digest(p)
            for p in output.rglob("*")
            if p.is_file() and p.name not in ("datasets.json", "schedule.json")
        }
    else:
        plan["resource_files"] = {}
    plan["execution_id"] = fingerprint(plan)
    write(output / "execution.json", plan)
    for name in sources:
        target = output / "implementation_source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / name, target)
    seal(output)
    return plan


def verify(path):
    path = Path(path)
    verify_seal(path)
    plan, datasets, slots = (
        read(path / "execution.json"),
        read(path / "datasets.json"),
        read(path / "schedule.json"),
    )
    if plan["execution_id"] != fingerprint({k: v for k, v in plan.items() if k != "execution_id"}):
        raise ValueError("candidate identity changed")
    experiment_fields = {
        k: v
        for k, v in plan.items()
        if k not in ("experiment_id", "execution_id", "schedule_sha256", "resource_files")
    }
    if plan["experiment_id"] != fingerprint(experiment_fields):
        raise ValueError("experiment binding differs")
    if canonical({k: plan[k] for k in FIXED}) != canonical(FIXED):
        raise ValueError("offline scope or frozen settings changed")
    if type(plan["fixture"]) is not bool or not Path(plan["registry_path"]).is_absolute():
        raise ValueError("fixture type or canonical registry differs")
    if (
        plan["data_sha256"] != fingerprint(datasets)
        or protocol.dataset_mapping(datasets) != plan["mapping"]
    ):
        raise ValueError("task data or paired mapping differs")
    expected = protocol.schedule(plan)
    if (
        slots != expected
        or plan["schedule_sha256"] != fingerprint(expected)
        or len(slots) != plan["planned_responses"]
    ):
        raise ValueError("repeat schedule differs from independent reconstruction")
    if (
        type(plan["planned_responses"]) is not int
        or type(plan["planned_trajectories"]) is not int
        or type(plan["generation_token_reservation"]) is not int
        or plan["planned_trajectories"] != len(expected) // 5
        or plan["generation_token_reservation"] != len(expected) * 8192
    ):
        raise ValueError("matrix budget differs")
    if not plan["fixture"] and (
        len(plan["mapping"]) != 36
        or {m["group_id"] for m in plan["mapping"]} != {"AL092021", "AL062018", "AL052019"}
    ):
        raise ValueError("full development cohort required")
    if plan["implementation_files"] != source_inventory():
        raise ValueError("loaded implementation differs from frozen candidate")
    for name, expected_hash in plan["implementation_files"].items():
        if digest(path / "implementation_source" / name) != expected_hash:
            raise ValueError("frozen implementation changed")
    for name, expected_hash in plan["resource_files"].items():
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("resource path escapes candidate")
        if digest(path / name) != expected_hash:
            raise ValueError("resource binding changed")
    if plan["fixture"]:
        if plan["resource_files"] or plan["model_identity"] != "synthetic_diagnostic_fixture":
            raise ValueError("fixture cannot claim real model resources")
    else:
        snapshot = read(path / "model_snapshot.json")
        if snapshot["model_id"] != adapter.SETTINGS["model_id"] or plan[
            "model_identity"
        ] != fingerprint({"model_id": snapshot["model_id"], "files": snapshot["files"]}):
            raise ValueError("model identity differs from frozen snapshot")
        config_files = {
            "model_config/" + item["path"]: item["sha256"]
            for item in snapshot["files"]
            if not item["path"].endswith(".safetensors")
        }
        expected_names = (
            set(config_files)
            | {"backend_source/" + n for n in BACKEND_FILES}
            | {"model_snapshot.json", "environment.json", "constraint.json"}
        )
        if set(plan["resource_files"]) != expected_names or any(
            plan["resource_files"][name] != value for name, value in config_files.items()
        ):
            raise ValueError("tokenizer/backend resource coverage differs")
        if read(path / "constraint.json") != {
            "identity": contract.identity(),
            "json": contract.schema_text(),
        }:
            raise ValueError("structure grammar differs")
    return plan, datasets, slots


def tokenizer(path, plan):
    if plan["fixture"]:
        return FixtureTokenizer()
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(
        Path(path) / "model_config", local_files_only=True, trust_remote_code=False
    )


def prepare(project, output, registry, *, repeats=2):
    project = Path(project)
    from disastertrace.constrained_eval.execution import verify as verify_base
    from disastertrace.stress_eval.execution import verify as verify_stress

    base = project / "artifacts/p4_constrained_output_v1/execution_live"
    scope = project / "artifacts/p5_stress_level4_v1/units/irrelevant_scope/execution_live"
    parent, bases, _ = verify_base(base)
    stress, conditions, _ = verify_stress(scope)
    if parent["dataset_content_id"] != stress["base_dataset_content_id"]:
        raise ValueError("historical base mapping differs")
    return freeze(
        {"base": bases, "irrelevant_scope": conditions},
        output,
        registry,
        repeats=repeats,
        resource=scope,
    )
