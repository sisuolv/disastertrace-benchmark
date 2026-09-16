"""Keep the accepted offline parent intact; bind a new live identity and runtime."""

import importlib.metadata
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.automated.common import canonical, fingerprint
from disastertrace.local_eval.storage import digest, read, seal, verify_seal, write
from disastertrace.repeat_eval import package as parent
from disastertrace.repeat_eval import protocol

PROJECT = Path(__file__).resolve().parents[3]
ENGINE_FILES = (
    "vllm/entrypoints/llm.py",
    "vllm/v1/engine/llm_engine.py",
    "vllm/v1/engine/processor.py",
    "vllm/v1/engine/output_processor.py",
)
FIXED = {
    "schema_version": "p6_paired_live_v1",
    "repeats": 2,
    "retries": 0,
    "response_cache": False,
    "repair": False,
    "max_worker_seconds": 14400,
    "max_parallel_gpus": 1,
    "paid_api_calls": 0,
    "heldout_calls": 0,
    "training": False,
    "llm_judge": False,
    "new_human_annotations": 0,
    "analysis": "closed_loop_total_trajectory_comparison",
    "authorization_basis": "User approved sequential execution and automatic GPU use; one paired 2160-opportunity matrix.",
}


def source_inventory():
    files = parent.source_inventory()
    for path in sorted((PROJECT / "src/disastertrace/repeat_live").glob("*.py")):
        files[str(path.relative_to(PROJECT))] = digest(path)
    return files


def engine_inventory():
    dist = importlib.metadata.distribution("vllm")
    return {name: digest(dist.locate_file(name)) for name in ENGINE_FILES}


def validate_preflight(proof, implementation_files):
    request, result, job = (proof[k] for k in ("request", "result", "job"))
    from .backend import validate_observation

    if (
        result["status"] != "passed"
        or result["generate_disabled"] is not True
        or type(result["model_calls"]) is not int
        or result["model_calls"] != 0
        or result["request_sha256"] != fingerprint(request)
        or request["kind"] != "preflight"
        or request["implementation_files"] != implementation_files
        or job["state"] != "SUCCEEDED"
        or job["cluster"] != "computing-cluster-01g-02"
        or type(job["gpu_count"]) is not int
        or job["gpu_count"] != 1
        or not job["job_id"].startswith("pt-")
        or result["hostname"] == request["source_cci_hostname"]
    ):
        raise ValueError("preflight proof does not establish a generation-disabled ACP H100 load")
    validate_observation(result["runtime_observation"])


def freeze(
    parent_path,
    output,
    registry,
    *,
    live=False,
    run_path=None,
    deadline_utc=None,
    preflight=None,
    engine_source=None,
):
    old, _, _ = parent.verify(parent_path)
    if type(live) is not bool or old["repeats"] != 2:
        raise ValueError("fixed two-repeat boolean scope required")
    if live:
        if old["fixture"] or preflight is None or run_path is None or deadline_utc is None:
            raise ValueError("model resources, actual preflight, run and deadline required")
        deadline = datetime.fromisoformat(deadline_utc)
        if deadline.tzinfo is None or deadline <= datetime.now(timezone.utc):
            raise ValueError("future aware deadline required")
        if Path(run_path).exists():
            raise FileExistsError("production directory consumes launch")
    elif any(value is not None for value in (run_path, deadline_utc, preflight)):
        raise ValueError("offline preflight candidate cannot contain a live scope")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(parent_path, output / "parent")
    plan = {
        **deepcopy(FIXED),
        **{
            k: deepcopy(old[k])
            for k in (
                "settings",
                "conditions",
                "methods",
                "mapping",
                "model_identity",
                "data_sha256",
                "fixture",
                "planned_responses",
                "planned_trajectories",
                "generation_token_reservation",
                "runtime_profile",
                "sampling_scheme",
                "reliability",
            )
        },
        "parent_execution_id": old["execution_id"],
        "implementation_files": source_inventory(),
        "registry_path": str(Path(registry).resolve()),
        "generation_authorized": live,
        "max_model_attempts": old["planned_responses"] if live else 0,
        "run_path": str(Path(run_path).resolve()) if live else None,
        "deadline_utc": deadline_utc,
        "preflight": preflight,
        "engine_files": {},
    }
    if not old["fixture"]:
        if engine_source is None:
            raise ValueError("explicit installed engine source root required")
        for name in ENGINE_FILES:
            target = output / "engine_source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(engine_source) / name, target)
            plan["engine_files"][name] = digest(target)
    if live:
        validate_preflight(preflight, plan["implementation_files"])
        plan["runtime_profile"].update(hardware_verified=True, gpu_preflight_performed=True)
    plan["experiment_id"] = fingerprint(plan)
    slots = protocol.schedule(plan)
    plan["schedule_sha256"] = fingerprint(slots)
    plan["execution_id"] = fingerprint(plan)
    write(output / "execution.json", plan)
    write(output / "schedule.json", slots)
    for name in plan["implementation_files"]:
        target = output / "implementation_source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / name, target)
    seal(output)
    verify(output)
    return plan


def verify(path):
    path = Path(path)
    verify_seal(path)
    plan, slots = read(path / "execution.json"), read(path / "schedule.json")
    old, datasets, _ = parent.verify(path / "parent")
    if plan["execution_id"] != fingerprint({k: v for k, v in plan.items() if k != "execution_id"}):
        raise ValueError("execution binding changed")
    if plan["experiment_id"] != fingerprint(
        {
            k: v
            for k, v in plan.items()
            if k not in ("experiment_id", "execution_id", "schedule_sha256")
        }
    ):
        raise ValueError("experiment binding changed")
    if canonical({k: plan[k] for k in FIXED}) != canonical(FIXED):
        raise ValueError("fixed scope differs")
    for key in (
        "settings",
        "conditions",
        "methods",
        "mapping",
        "model_identity",
        "data_sha256",
        "fixture",
        "planned_responses",
        "planned_trajectories",
        "generation_token_reservation",
        "sampling_scheme",
        "reliability",
    ):
        if canonical(plan[key]) != canonical(old[key]):
            raise ValueError("paired parent metadata differs: " + key)
    if (
        old["repeats"] != 2
        or plan["parent_execution_id"] != old["execution_id"]
        or type(plan["generation_authorized"]) is not bool
        or type(plan["max_model_attempts"]) is not int
        or not Path(plan["registry_path"]).is_absolute()
    ):
        raise ValueError("scope/parent identity differs")
    profile = deepcopy(old["runtime_profile"])
    if plan["generation_authorized"]:
        if (
            plan["fixture"]
            or plan["max_model_attempts"] != 2160
            or not Path(plan["run_path"]).is_absolute()
        ):
            raise ValueError("only the full real-resource 2160 model matrix is authorized")
        if datetime.fromisoformat(plan["deadline_utc"]).tzinfo is None:
            raise ValueError("aware deadline required")
        validate_preflight(plan["preflight"], plan["implementation_files"])
        profile.update(hardware_verified=True, gpu_preflight_performed=True)
        observed = plan["preflight"]["result"]["runtime_observation"]
        if observed["model_identity"] != plan["model_identity"]:
            raise ValueError("preflight model identity differs")
        if observed["engine_files"] != plan["engine_files"] or observed[
            "environment_sha256"
        ] != fingerprint(read(path / "parent/environment.json")):
            raise ValueError("preflight environment differs from live resources")
    elif plan["max_model_attempts"] != 0 or any(
        plan[k] is not None for k in ("run_path", "deadline_utc", "preflight")
    ):
        raise ValueError("offline candidate has no model authorization")
    if canonical(plan["runtime_profile"]) != canonical(profile):
        raise ValueError("runtime profile changed")
    if slots != protocol.schedule(plan) or plan["schedule_sha256"] != fingerprint(slots):
        raise ValueError("schedule differs from independent reconstruction")
    if plan["implementation_files"] != source_inventory():
        raise ValueError("loaded source differs from frozen implementation")
    for name, expected in plan["implementation_files"].items():
        if digest(path / "implementation_source" / name) != expected:
            raise ValueError("copied source differs")
    expected_engine = () if plan["fixture"] else ENGINE_FILES
    if set(plan["engine_files"]) != set(expected_engine):
        raise ValueError("engine source coverage differs")
    for name, expected in plan["engine_files"].items():
        if digest(path / "engine_source" / name) != expected:
            raise ValueError("engine source differs")
    return plan, datasets, slots


def tokenizer(path, plan):
    return parent.tokenizer(Path(path) / "parent", plan)
