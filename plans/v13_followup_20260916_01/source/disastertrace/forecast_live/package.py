"""Fresh phase identity and fixed whole-target ownership over the accepted task."""

import hashlib
import importlib.metadata
import platform
import shutil
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from disastertrace.forecast_task.common import digest, fingerprint, inventory, read, seal
from disastertrace.forecast_task.common import verify as verify_seal
from disastertrace.forecast_task.protocol import schedule

from .adapter import SETTINGS
from .storage import now, write

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
    "vllm/entrypoints/llm.py",
    "vllm/v1/engine/llm_engine.py",
    "vllm/v1/engine/processor.py",
    "vllm/v1/engine/output_processor.py",
)
BOUNDS = {
    "planned_answers": 1542,
    "max_requested_output_tokens": 12632064,
    "worker_count": 4,
    "gpus_per_worker": 1,
    "max_parallel_h100": 4,
    "max_phase_seconds": 14400,
    "max_live_h100_hours": 16,
    "retries": 0,
    "paid_api_calls": 0,
    "heldout_calls": 0,
    "training": False,
    "llm_judge": False,
    "new_human_annotations": 0,
    "methods": ["snapshot", "structured_state", "answer_history"],
    "repeats": 2,
    "condition": "native_natural_issue_order_complete_advisory_text",
}


def environment():
    return {
        "python": platform.python_version(),
        "packages": {
            d.metadata["Name"].lower().replace("_", "-"): d.version
            for d in importlib.metadata.distributions()
        },
    }


def backend_inventory():
    return {
        name: digest(importlib.metadata.distribution(name.split("/")[0]).locate_file(name))
        for name in BACKEND_FILES
    }


def verify_model(snapshot):
    root = Path(snapshot["local_path"]).resolve()
    for item in snapshot["files"]:
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or path.stat().st_size != item["bytes"]:
            raise ValueError("model path/size mismatch")
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                hasher.update(block)
        if hasher.hexdigest() != item["sha256"]:
            raise ValueError("pinned model hash mismatch")
    if not set(read(root / "model.safetensors.index.json")["weight_map"].values()) <= {
        item["path"] for item in snapshot["files"]
    }:
        raise ValueError("incomplete model weight inventory")


def assign(public, slots, phase_id):
    groups, loads, totals, owners = defaultdict(list), [Counter() for _ in range(4)], [0] * 4, {}
    for slot in slots:
        groups[slot["episode_id"]].append(slot)
    for storm in sorted({e["query"]["storm_id"] for e in public["episodes"].values()}):
        episodes = sorted(
            (e for e in groups if public["episodes"][e]["query"]["storm_id"] == storm),
            key=lambda e: (-len(groups[e]), public["episodes"][e]["query"]["valid_at"], e),
        )
        for episode in episodes:
            worker = min(range(4), key=lambda w: (loads[w][storm], totals[w], w))
            owners[episode] = worker
            loads[worker][storm] += len(groups[episode])
            totals[worker] += len(groups[episode])
    return [
        {
            **s,
            "worker_id": owners[s["episode_id"]],
            "attempt_id": fingerprint(
                {
                    "phase_id": phase_id,
                    "source_slot_id": s["slot_id"],
                    "worker_id": owners[s["episode_id"]],
                }
            ),
            "live_trajectory_id": fingerprint(
                {"phase_id": phase_id, "trajectory_id": s["trajectory_id"]}
            ),
        }
        for s in slots
    ]


def batches(slots, public, worker):
    selected = [s for s in slots if s["worker_id"] == worker]
    # Each round exposes at most one next checkpoint from each independent trajectory.
    # Hash ordering interleaves methods/repeats without using outcomes or private data.
    rounds = defaultdict(list)
    for slot in selected:
        step = len(public["opportunities"][slot["opportunity_id"]]["previous_checkpoint_ids"])
        rounds[step].append(slot)
    result = []
    for step in sorted(rounds):
        ordered = sorted(
            rounds[step],
            key=lambda s: fingerprint(
                {"order": "forecast_live_v1", "trajectory": s["trajectory_id"]}
            ),
        )
        for index in range(0, len(ordered), SETTINGS["batch_size"]):
            result.append(ordered[index : index + SETTINGS["batch_size"]])
    return result


def freeze(
    task, resources, output, *, kind="diagnostic", run_root=None, preflight=None, validation=None
):
    task, resources, output = Path(task), Path(resources), Path(output)
    task_manifest = verify_seal(task)
    task_plan = read(task / "execution.json")
    if task_plan["generation_authorized"] is not False:
        raise ValueError("native parent must remain offline")
    if kind not in ("diagnostic", "preflight", "model"):
        raise ValueError("unknown phase kind")
    if kind == "model":
        if preflight is None or validation is None or run_root is None:
            raise ValueError("model freeze requires preflight, CPU validation and canonical root")
        from .launch import validate_preflight

        validate_preflight(preflight)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(task, output / "task", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(
        task / "source/src", output / "source", ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copytree(
        PROJECT / "src/disastertrace/forecast_live",
        output / "source/disastertrace/forecast_live",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    if (PROJECT / "tests/p7_forecast_live").is_dir():
        shutil.copytree(
            PROJECT / "tests/p7_forecast_live",
            output / "tests",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    source_manifest = seal(output / "source")
    for name in ("model_snapshot.json", "environment.json"):
        shutil.copyfile(resources / "parent" / name, output / name)
    resource_plan = read(resources / "parent/execution.json")
    expected = {
        k.removeprefix("backend_source/"): v
        for k, v in resource_plan["resource_files"].items()
        if k.startswith("backend_source/")
    }
    expected.update(read(resources / "execution.json")["engine_files"])
    if set(expected) != set(BACKEND_FILES):
        raise ValueError("backend evidence closure differs")
    phase_id = fingerprint(
        {
            "task": task_manifest["package_id"],
            "nonce": uuid.uuid4().hex,
            "kind": kind,
            "schema": "forecast_live_v1",
        }
    )
    public = read(task / "data/public.json")
    slots = assign(public, schedule(public), phase_id)
    if len(slots) != BOUNDS["planned_answers"]:
        raise ValueError("unexpected native matrix size")
    write(output / "schedule.json", slots)
    write(output / "preflight.json", preflight)
    write(output / "validation.json", validation)
    at = now()
    plan = {
        "schema_version": "forecast_live_execution_v1",
        "phase_id": phase_id,
        "kind": kind,
        "generation_authorized": kind == "model",
        "settings": SETTINGS,
        "bounds": BOUNDS,
        "created_at": at,
        "deadline_utc": (datetime.fromisoformat(at) + timedelta(seconds=14400)).isoformat()
        if kind == "model"
        else None,
        "run_root": str(Path(run_root).resolve()) if run_root else None,
        "launch_registry": str(output.resolve().with_name(output.name + "_launch_claims")),
        "task_package_id": task_manifest["package_id"],
        "task_execution_id": task_plan["execution_id"],
        "source_files": source_manifest["files"],
        "backend_files": expected,
        "model_identity": fingerprint(read(output / "model_snapshot.json")),
        "environment_sha256": fingerprint(read(output / "environment.json")),
        "schedule_sha256": fingerprint(slots),
        "preflight_sha256": fingerprint(preflight),
        "validation_sha256": fingerprint(validation),
        "authorization_basis": "User authorizes continued native evaluation and automatic maximum four H100s.",
    }
    plan["execution_id"] = fingerprint(plan)
    write(output / "execution.json", plan)
    seal(output)
    verify(output)
    return plan


def verify(root, *, code=False):
    root = Path(root)
    verify_seal(root)
    task_manifest = verify_seal(root / "task")
    source_manifest = verify_seal(root / "source")
    plan, slots = read(root / "execution.json"), read(root / "schedule.json")
    public = read(root / "task/data/public.json")
    if plan["execution_id"] != fingerprint({k: v for k, v in plan.items() if k != "execution_id"}):
        raise ValueError("execution identity differs")
    if (
        plan["settings"] != SETTINGS
        or plan["bounds"] != BOUNDS
        or plan["generation_authorized"] != (plan["kind"] == "model")
        or plan["source_files"] != source_manifest["files"]
        or plan["task_package_id"] != task_manifest["package_id"]
        or slots != assign(public, schedule(public), plan["phase_id"])
        or plan["schedule_sha256"] != fingerprint(slots)
    ):
        raise ValueError("task/settings/ownership binding differs")
    for name, key in (
        ("model_snapshot", "model_identity"),
        ("environment", "environment_sha256"),
        ("preflight", "preflight_sha256"),
        ("validation", "validation_sha256"),
    ):
        if fingerprint(read(root / (name + ".json"))) != plan[key]:
            raise ValueError("resource or validation binding differs")
    parent_source = inventory(root / "task/source/src")
    if any(source_manifest["files"].get(name) != sha for name, sha in parent_source.items()):
        raise ValueError("accepted task implementation changed")
    model_files = {f["path"]: f["sha256"] for f in read(root / "model_snapshot.json")["files"]}
    if any(
        model_files.get(name) != sha for name, sha in inventory(root / "task/tokenizer").items()
    ):
        raise ValueError("public tokenizer differs from pinned model snapshot")
    if code:
        loaded = Path(__file__).resolve().parents[2]
        if any(
            not (loaded / name).is_file() or digest(loaded / name) != sha
            for name, sha in source_manifest["files"].items()
        ):
            raise ValueError("executing source differs from frozen closure")
    if plan["kind"] == "model":
        from .launch import validate_cpu, validate_preflight

        validate_preflight(read(root / "preflight.json"), plan)
        validate_cpu(read(root / "validation.json"), plan)
        if datetime.fromisoformat(plan["deadline_utc"]) - datetime.fromisoformat(
            plan["created_at"]
        ) != timedelta(seconds=14400):
            raise ValueError("phase deadline changed")
    return plan, public, slots


def tokenizer_for(root):
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(
        Path(root) / "task/tokenizer", local_files_only=True, trust_remote_code=False
    )


def past_deadline(plan):
    return bool(
        plan["deadline_utc"]
        and datetime.now(timezone.utc) >= datetime.fromisoformat(plan["deadline_utc"])
    )
