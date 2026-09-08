"""Frozen expanded task with two tokenizers and independent CPU reconstruction."""

import shutil
from pathlib import Path

from disastertrace.forecast_task import package as inherited
from disastertrace.forecast_task.common import (
    digest,
    fingerprint,
    inventory,
    read,
    seal,
    verify,
    write,
)
from disastertrace.forecast_task.contract import SCHEMA, SYSTEM
from disastertrace.forecast_task.diagnostics import run_programs

from .loader import compile_bundle
from .protocol import METHODS, REPEATS, schedule

PROFILES = ("qwen3", "deepseek_r1")


def snapshot_source(project, output):
    names = set(inherited.SOURCE_DEPENDENCIES)
    for namespace in ("forecast_task", "forecast_catalog", "forecast_cohort"):
        names.update(
            p.relative_to(project).as_posix()
            for p in (project / "src/disastertrace" / namespace).glob("*.py")
        )
    for directory in ("tests/p7_forecast_task", "tests/p10_forecast_cohort"):
        names.update(p.relative_to(project).as_posix() for p in (project / directory).glob("*.py"))
    for name in sorted(names):
        inherited._copy_file(project / name, output / name)
    return seal(output)


def reconstruction(root):
    compiled = compile_bundle(root / "input_sources")
    slots = schedule(compiled["public"])
    diagnostics = run_programs(compiled["public"], compiled["private_reference"], slots)
    contexts = {
        name: inherited.context_report(diagnostics["requests"], root / "tokenizers" / name)
        for name in PROFILES
    }
    return compiled, slots, diagnostics, contexts


def bindings(root, source, compiled, slots, diagnostics, contexts):
    return {
        "schema_version": "forecast_cohort_offline_execution_v1",
        "dataset_id": compiled["dataset"]["dataset_id"],
        "source_package_id": source["package_id"],
        "review_package_id": compiled["dataset"]["source_identity"]["review_package_id"],
        "protocol_sha256": digest(root / "PROTOCOL.md"),
        "schedule_sha256": fingerprint(slots),
        "schema_sha256": fingerprint(SCHEMA),
        "system_sha256": fingerprint(SYSTEM),
        "requests_sha256": fingerprint(diagnostics["requests"]),
        "contexts_sha256": fingerprint(contexts),
        "diagnostic_file_hashes": inventory(root / "diagnostics"),
        "runtime": inherited._runtime(),
        "methods": list(METHODS),
        "repeats": REPEATS,
        "repeat_ids": [0],
        "condition": "native_text_natural_issue_order_controlled_delivery",
        "independent_storms": 6,
        "target_episodes": len(compiled["public"]["episodes"]),
        "checkpoint_queries": len(compiled["public"]["opportunities"]),
        "planned_slots_per_policy": len(slots),
        "candidate_answers_per_model": len(slots),
        "candidate_model_profiles": list(PROFILES),
        "candidate_answers_two_models": 2 * len(slots),
        "max_requested_output_tokens_per_model": len(slots) * 8192,
        "context_limit": 32768,
        "output_reservation": 8192,
        "diagnostic_policies": list(diagnostics["captures"]),
        "generation_authorized": False,
        "dispatch_compatible": False,
        "model_generations": 0,
        "new_downloads": 0,
        "heldout_inference": 0,
        "human_gold_annotations": 0,
        "llm_judge": False,
    }


def build_execution(source_input, output, project_root, tokenizer_roots, protocol_path):
    output, project = Path(output), Path(project_root)
    if set(tokenizer_roots) != set(PROFILES):
        raise ValueError("both declared tokenizer profiles required")
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(
        source_input, output / "input_sources", ignore=shutil.ignore_patterns("__pycache__")
    )
    source = snapshot_source(project, output / "source")
    for name, root in tokenizer_roots.items():
        root = Path(root)
        for filename in (*inherited.TOKENIZER_FILES, "generation_config.json"):
            if (root / filename).is_file():
                inherited._copy_file(root / filename, output / "tokenizers" / name / filename)
    inherited._copy_file(Path(protocol_path), output / "PROTOCOL.md")
    compiled, slots, diagnostics, contexts = reconstruction(output)
    for name, value in compiled.items():
        write(output / "data" / (name + ".json"), value)
    write(output / "schedule.json", slots)
    write(output / "answer_schema.json", SCHEMA)
    write(output / "system_contract.json", {"text": SYSTEM})
    inherited._write_diagnostics(output, diagnostics)
    write(output / "contexts.json", contexts)
    execution = bindings(output, source, compiled, slots, diagnostics, contexts)
    execution["execution_id"] = fingerprint(execution)
    write(output / "execution.json", execution)
    manifest = seal(output)
    return {
        "status": "built",
        "execution_id": execution["execution_id"],
        "package_id": manifest["package_id"],
        "counts": compiled["dataset"]["counts"],
        "planned_per_model": len(slots),
        "diagnostics_correct": {
            p: s["counts"]["all_correct"] for p, s in diagnostics["scores"].items()
        },
        "context_checks_per_model": {p: v["unique_requests"] for p, v in contexts.items()},
        "maximum_reserved_total": {p: v["maximum_reserved_total"] for p, v in contexts.items()},
        "model_generations": 0,
    }


def verify_execution(root):
    root = Path(root)
    manifest, source = verify(root), verify(root / "source")
    running = Path(__file__).resolve().parents[3]
    for name, expected in source["files"].items():
        if name.startswith("src/") and digest(running / name) != expected:
            raise ValueError("running source differs: " + name)
    compiled, slots, diagnostics, contexts = reconstruction(root)
    for name, value in compiled.items():
        if read(root / "data" / (name + ".json")) != value:
            raise ValueError("dataset reconstruction differs: " + name)
    for name, value in (
        ("schedule", slots),
        ("answer_schema", SCHEMA),
        ("system_contract", {"text": SYSTEM}),
        ("requests", diagnostics["requests"]),
        ("contexts", contexts),
    ):
        if read(root / (name + ".json")) != value:
            raise ValueError("task reconstruction differs: " + name)
    for policy in diagnostics["captures"]:
        for name in ("captures", "scores"):
            if read(root / "diagnostics" / policy / (name + ".json")) != diagnostics[name][policy]:
                raise ValueError("diagnostic reconstruction differs")
    expected = bindings(root, source, compiled, slots, diagnostics, contexts)
    expected["execution_id"] = fingerprint(expected)
    if read(root / "execution.json") != expected:
        raise ValueError("complete execution binding differs")
    return {
        "status": "passed",
        "execution_id": expected["execution_id"],
        "package_id": manifest["package_id"],
        "source_package_id": source["package_id"],
        "files_verified": len(manifest["files"]),
        "planned_per_model": len(slots),
        "model_generations": 0,
    }
