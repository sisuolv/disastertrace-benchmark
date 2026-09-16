"""Freeze shared audited native prefixes, paired branches and fresh resource/attempt claims."""

import shutil
import tarfile
import tempfile
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

from disastertrace.forecast_live import audit as native_audit
from disastertrace.forecast_live import package as native_package
from disastertrace.forecast_task.common import digest, fingerprint, inventory, read, seal
from disastertrace.forecast_task.common import verify as verify_seal

from . import design
from .adapter import SETTINGS
from .storage import now, write

PROJECT = Path(__file__).resolve().parents[3]
BOUNDS = {
    "planned_answers": 844,
    "planned_pairs": 422,
    "max_requested_output_tokens": 6914048,
    "worker_count": 4,
    "gpus_per_worker": 1,
    "max_parallel_h100": 4,
    "max_phase_seconds": 7200,
    "max_live_h100_hours": 8,
    "retries": 0,
    "paid_api_calls": 0,
    "heldout_calls": 0,
    "training": False,
    "llm_judge": False,
    "new_human_annotations": 0,
    "methods": ["json", "text"],
    "source_repeats": 2,
    "condition": design.VERSION,
    "generated_steps_per_branch": 1,
}
environment = native_package.environment
backend_inventory = native_package.backend_inventory
verify_model = native_package.verify_model
tokenizer_for = native_package.tokenizer_for
past_deadline = native_package.past_deadline


def registration(root, source_execution_id):
    root = Path(root)
    prereg = read(root / "PREREGISTRATION.json")
    declared = read(root / "PREDECLARED_SLOTS.json")
    if (
        prereg["design_id"] != fingerprint({k: v for k, v in prereg.items() if k != "design_id"})
        or prereg["source_execution_id"] != source_execution_id
        or prereg["design_sha256"] != digest(root / "DESIGN_BEFORE_NATIVE_RESULTS.md")
        or prereg["slots_sha256"] != digest(root / "PREDECLARED_SLOTS.json")
        or prereg["source_model_scores_read"] is not False
        or prereg["has_dispatch_path"] is not False
        or prereg["planned_answers"] != BOUNDS["planned_answers"]
        or prereg["planned_pairs"] != BOUNDS["planned_pairs"]
        or prereg["planned_output_reservation"] != BOUNDS["max_requested_output_tokens"]
        or len(declared) != BOUNDS["planned_answers"]
        or len({r["pair_id"] for r in declared}) != BOUNDS["planned_pairs"]
    ):
        raise ValueError("pre-result design registration or complete population differs")
    return prereg, declared


def prepare_source(native_execution, native_run, native_report, preregistration, output):
    execution, run, output, preregistration = map(
        Path, (native_execution, native_run, output, preregistration)
    )
    plan, public, slots = native_package.verify(execution, code=True)
    audited = native_audit.aggregate(execution, run)
    if read(native_report) != audited or plan["kind"] != "model":
        raise ValueError("prefix source must reconstruct as an actual native model report")
    prereg, declared = registration(preregistration, plan["execution_id"])
    bound = design.bind(plan["execution_id"], public, slots, audited, declared)
    if len(declared) != 844 or len({r["pair_id"] for r in declared}) != 422:
        raise ValueError("representation population changed")
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(execution / "task", output / "task")
    for name in ("model_snapshot.json", "environment.json"):
        shutil.copyfile(execution / name, output / name)
    write(output / "native_execution.json", plan)
    write(output / "native_schedule.json", slots)
    write(output / "native_report.json", audited)
    write(output / "declared_slots.json", declared)
    write(output / "representation_requests.json", bound)
    for name in (
        "DESIGN_BEFORE_NATIVE_RESULTS.md",
        "PREREGISTRATION.json",
        "PREDECLARED_SLOTS.json",
    ):
        shutil.copyfile(preregistration / name, output / name)
    with tarfile.open(output / "native_evidence.tar.gz", "x:gz") as archive:
        for folder, prefix in ((execution, "execution"), (run, "run")):
            for path in sorted(folder.rglob("*")):
                if path.is_symlink():
                    raise ValueError("symlink in native input archive")
                if path.is_file() and "__pycache__" not in path.parts:
                    archive.add(
                        path,
                        arcname=prefix + "/" + path.relative_to(folder).as_posix(),
                        recursive=False,
                    )
    eligible = sum(b["eligible"] for b in bound.values())
    odd = sum(
        bound[s["slot_id"]]["eligible"]
        and public["opportunities"][s["opportunity_id"]]["delivery_step"] % 2 == 1
        for s in declared
    )
    record = {
        "schema_version": "carrier_representation_source_v1",
        "native_execution_id": plan["execution_id"],
        "native_report_id": audited["report_id"],
        "design_id": prereg["design_id"],
        "eligible": eligible,
        "ineligible": 844 - eligible,
        "diagnostic_expectations": {
            "latest_explicit": eligible,
            "invalid_even": odd,
            "missing_even": odd,
        },
        "source_native_model_answers": audited["counts"]["raw_returned"],
        "new_model_calls": 0,
        "created_at": now(),
    }
    record["source_id"] = fingerprint(record)
    write(output / "source.json", record)
    seal(output)
    return record


def reconstruct_source(root):
    root = Path(root)
    public = read(root / "task/data/public.json")
    native = read(root / "native_execution.json")
    audit, slots, declared = (
        read(root / name)
        for name in ("native_report.json", "native_schedule.json", "declared_slots.json")
    )
    prereg, original_declared = registration(root, native["execution_id"])
    if (
        native["execution_id"]
        != fingerprint({k: v for k, v in native.items() if k != "execution_id"})
        or native["kind"] != "model"
        or native["generation_authorized"] is not True
        or fingerprint(slots) != native["schedule_sha256"]
        or declared != original_declared
        or audit["report_id"] != fingerprint({k: v for k, v in audit.items() if k != "report_id"})
        or audit["phase_id"] != native["phase_id"]
        or fingerprint(read(root / "model_snapshot.json")) != native["model_identity"]
        or fingerprint(read(root / "environment.json")) != native["environment_sha256"]
        or verify_seal(root / "task")["package_id"] != native["task_package_id"]
    ):
        raise ValueError("native execution/report/schedule/resources differ from audited source")
    bound = design.bind(native["execution_id"], public, slots, audit, declared)
    if bound != read(root / "representation_requests.json"):
        raise ValueError("shared-prefix request reconstruction differs")
    source = read(root / "source.json")
    if source["source_id"] != fingerprint({k: v for k, v in source.items() if k != "source_id"}):
        raise ValueError("source identity differs")
    eligible = sum(v["eligible"] for v in bound.values())
    odd = sum(
        bound[s["slot_id"]]["eligible"]
        and public["opportunities"][s["opportunity_id"]]["delivery_step"] % 2 == 1
        for s in declared
    )
    if (
        source["native_report_id"] != audit["report_id"]
        or source["eligible"] != eligible
        or source["ineligible"] != len(declared) - eligible
        or source["native_execution_id"] != native["execution_id"]
        or source["design_id"] != prereg["design_id"]
        or source["source_native_model_answers"] != audit["counts"]["raw_returned"]
        or source["new_model_calls"] != 0
        or source["diagnostic_expectations"]
        != {"latest_explicit": eligible, "invalid_even": odd, "missing_even": odd}
    ):
        raise ValueError("source report/eligibility binding differs")
    public["representation_requests"] = bound
    return source, public, declared


def replay_native_archive(root, temporary_parent):
    root = Path(root)
    with tempfile.TemporaryDirectory(
        prefix="native-prefix-review-", dir=temporary_parent
    ) as temporary:
        copied = Path(temporary)
        with tarfile.open(root / "native_evidence.tar.gz", "r:gz") as archive:
            names = set()
            for member in archive:
                name = PurePosixPath(member.name)
                if (
                    not member.isfile()
                    or name.is_absolute()
                    or ".." in name.parts
                    or name.parts[0] not in ("execution", "run")
                    or member.name in names
                ):
                    raise ValueError("unsafe or duplicate native archive member")
                names.add(member.name)
                target = copied / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open("xb") as destination:
                    shutil.copyfileobj(source, destination)
        reconstructed = native_audit.aggregate(copied / "execution", copied / "run")
        if reconstructed != read(root / "native_report.json"):
            raise ValueError("archived source prefix cannot reproduce its native report")
    return {"status": "passed", "native_report_id": reconstructed["report_id"], "model_calls": 0}


def assign(public, declared, phase_id):
    rows = [
        {
            **r,
            "method": r["encoding"],
            "trajectory_id": fingerprint({"pair_id": r["pair_id"], "branch": r["encoding"]}),
            "eligible": public["representation_requests"][r["slot_id"]]["eligible"],
        }
        for r in declared
    ]
    return native_package.assign(public, rows, phase_id)


def batches(slots, public, worker):
    pairs = defaultdict(list)
    for slot in slots:
        if slot["worker_id"] == worker and slot["eligible"]:
            pairs[slot["pair_id"]].append(slot)
    ready = []
    for pair_id, pair in sorted(
        pairs.items(), key=lambda item: fingerprint({"order": "repr_v1", "pair": item[0]})
    ):
        if len(pair) != 2 or {s["encoding"] for s in pair} != {"json", "text"}:
            raise ValueError("pair is split, missing an arm or inconsistently eligible")
        order = ("json", "text") if int(pair_id[:2], 16) % 2 == 0 else ("text", "json")
        ready.extend(sorted(pair, key=lambda s: order.index(s["encoding"])))
    return [
        ready[i : i + SETTINGS["batch_size"]] for i in range(0, len(ready), SETTINGS["batch_size"])
    ]


def freeze(
    source,
    output,
    *,
    kind="diagnostic",
    run_root=None,
    preflight=None,
    validation=None,
    autonomy_deadline=None,
):
    source, output = Path(source), Path(output)
    input_manifest = verify_seal(source)
    inputs, public, declared = reconstruct_source(source)
    if kind not in ("diagnostic", "preflight", "model"):
        raise ValueError("unsupported representation phase")
    if kind == "model" and (
        preflight is None or validation is None or run_root is None or autonomy_deadline is None
    ):
        raise ValueError("live prefix comparison requires complete gates and autonomous deadline")
    output.mkdir(parents=True, exist_ok=False)
    for child in source.iterdir():
        if child.name == "manifest.json":
            shutil.copyfile(child, output / "input_manifest.json")
        elif child.is_dir():
            shutil.copytree(child, output / child.name)
        else:
            shutil.copyfile(child, output / child.name)
    shutil.copytree(source / "task/source/src", output / "source")
    for namespace in ("forecast_live", "carrier_repr"):
        shutil.copytree(
            PROJECT / "src/disastertrace" / namespace,
            output / "source/disastertrace" / namespace,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    shutil.copytree(
        PROJECT / "tests/p8_carrier_repr",
        output / "tests",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    source_manifest = seal(output / "source")
    phase_id = fingerprint(
        {"input_id": input_manifest["package_id"], "nonce": uuid.uuid4().hex, "kind": kind}
    )
    slots = assign(public, declared, phase_id)
    native = read(source / "native_execution.json")
    at = now()
    deadline = None
    if kind == "model":
        deadline = min(
            datetime.fromisoformat(at) + timedelta(seconds=7200),
            datetime.fromisoformat(autonomy_deadline),
        )
        if deadline <= datetime.now(timezone.utc):
            raise ValueError("autonomous window exhausted")
        deadline = deadline.isoformat()
    plan = {
        "schema_version": "carrier_representation_execution_v1",
        "execution_id": None,
        "phase_id": phase_id,
        "kind": kind,
        "generation_authorized": kind == "model",
        "source_binding_id": input_manifest["package_id"],
        "source_id": inputs["source_id"],
        "source_native_report_id": inputs["native_report_id"],
        "settings": SETTINGS,
        "bounds": BOUNDS,
        "created_at": at,
        "deadline_utc": deadline,
        "autonomy_deadline": autonomy_deadline,
        "run_root": str(Path(run_root).resolve()) if run_root else None,
        "launch_registry": str(output.resolve().with_name(output.name + "_launch_claims")),
        "source_files": source_manifest["files"],
        "task_package_id": native["task_package_id"],
        "model_identity": native["model_identity"],
        "environment_sha256": native["environment_sha256"],
        "backend_files": native["backend_files"],
        "schedule_sha256": fingerprint(slots),
        "preflight_sha256": fingerprint(preflight),
        "validation_sha256": fingerprint(validation),
        "eligible_answers": inputs["eligible"],
        "diagnostic_expectations": inputs["diagnostic_expectations"],
        "authorization_basis": "User authorizes ten hours of autonomous next-plan execution, maximum four H100s.",
    }
    del plan["execution_id"]
    plan["execution_id"] = fingerprint(plan)
    write(output / "schedule.json", slots)
    write(output / "preflight.json", preflight)
    write(output / "validation.json", validation)
    write(output / "execution.json", plan)
    seal(output)
    verify(output)
    return plan


def verify(root, *, code=False):
    root = Path(root)
    verify_seal(root)
    plan = read(root / "execution.json")
    inputs = read(root / "input_manifest.json")
    source_manifest = verify_seal(root / "source")
    if (
        plan["execution_id"] != fingerprint({k: v for k, v in plan.items() if k != "execution_id"})
        or plan["source_binding_id"] != inputs["package_id"]
        or inputs["package_id"]
        != fingerprint({k: v for k, v in inputs.items() if k != "package_id"})
        or any(digest(root / name) != sha for name, sha in inputs["files"].items())
    ):
        raise ValueError("execution or source-prefix input closure differs")
    source, public, declared = reconstruct_source(root)
    native = read(root / "native_execution.json")
    slots = read(root / "schedule.json")
    if (
        plan["kind"] not in ("diagnostic", "preflight", "model")
        or plan["settings"] != SETTINGS
        or plan["bounds"] != BOUNDS
        or plan["generation_authorized"] != (plan["kind"] == "model")
        or slots != assign(public, declared, plan["phase_id"])
        or plan["schedule_sha256"] != fingerprint(slots)
        or plan["source_files"] != source_manifest["files"]
        or plan["source_id"] != source["source_id"]
        or plan["source_native_report_id"] != source["native_report_id"]
        or plan["eligible_answers"] != source["eligible"]
        or plan["diagnostic_expectations"] != source["diagnostic_expectations"]
        or any(
            plan[k] != native[k] for k in ("model_identity", "environment_sha256", "backend_files")
        )
        or plan["task_package_id"] != verify_seal(root / "task")["package_id"]
    ):
        raise ValueError("paired population, source, eligibility, settings or ownership differs")
    for name, key in (
        ("model_snapshot", "model_identity"),
        ("environment", "environment_sha256"),
        ("preflight", "preflight_sha256"),
        ("validation", "validation_sha256"),
    ):
        if fingerprint(read(root / (name + ".json"))) != plan[key]:
            raise ValueError("bound runtime/validation resource differs")
    parent_source = inventory(root / "task/source/src")
    if any(source_manifest["files"].get(name) != sha for name, sha in parent_source.items()):
        raise ValueError("native task implementation changed")
    if any(
        source_manifest["files"].get(name) != sha for name, sha in native["source_files"].items()
    ):
        raise ValueError("audited native collector implementation changed")
    if code:
        loaded = Path(__file__).resolve().parents[2]
        if any(
            not (loaded / name).is_file() or digest(loaded / name) != sha
            for name, sha in source_manifest["files"].items()
        ):
            raise ValueError("executing source differs from paired freeze")
    if plan["kind"] == "model":
        from .launch import validate_cpu, validate_preflight

        validate_cpu(read(root / "validation.json"), plan)
        validate_preflight(read(root / "preflight.json"), plan)
        delta = datetime.fromisoformat(plan["deadline_utc"]) - datetime.fromisoformat(
            plan["created_at"]
        )
        if not timedelta(0) < delta <= timedelta(seconds=7200) or datetime.fromisoformat(
            plan["deadline_utc"]
        ) > datetime.fromisoformat(plan["autonomy_deadline"]):
            raise ValueError("paired phase or autonomous deadline exceeded")
    return plan, public, slots
