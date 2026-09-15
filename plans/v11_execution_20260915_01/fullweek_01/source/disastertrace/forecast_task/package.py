"""Freeze and reconstruct an offline execution with a complete copied source closure."""

import importlib.metadata
import platform
import shutil
from pathlib import Path

from .common import digest, fingerprint, inventory, read, seal, verify, write
from .compiler import compile_bundle
from .contract import SCHEMA, SYSTEM
from .diagnostics import run_programs
from .protocol import METHODS, REPEATS, schedule

CONTEXT_LIMIT = 32768
OUTPUT_RESERVATION = 8192
TOKENIZER_FILES = (
    "config.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "vocab.json",
    "merges.txt",
)
SOURCE_DEPENDENCIES = (
    "src/disastertrace/__init__.py",
    "src/disastertrace/models.py",
    "src/disastertrace/forecast_source/__init__.py",
    "src/disastertrace/forecast_source/normalization.py",
    "src/disastertrace/forecast_source/parser_a.py",
    "src/disastertrace/forecast_source/parser_b.py",
)


def prepare_request(
    messages, tokenizer, context_limit=CONTEXT_LIMIT, output_reservation=OUTPUT_RESERVATION
):
    if (
        type(context_limit) is not int
        or type(output_reservation) is not int
        or not 0 < output_reservation < context_limit
    ):
        raise ValueError("invalid context reservation")
    if any("</think>" in m["content"] for m in messages):
        raise ValueError("prompt contains a reasoning closing delimiter")
    ids = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, enable_thinking=True
    )
    if len(ids) + output_reservation > context_limit:
        raise ValueError("full output reservation exceeds context; no truncation permitted")
    return {
        "request_sha256": fingerprint(messages),
        "prompt_tokens": len(ids),
        "prompt_token_ids_sha256": fingerprint(ids),
        "reserved_output_tokens": output_reservation,
        "context_limit": context_limit,
    }


def context_report(requests, tokenizer_root):
    from transformers import AutoTokenizer

    tokenizer_root = Path(tokenizer_root)
    config = read(tokenizer_root / "config.json")
    if CONTEXT_LIMIT > config["max_position_embeddings"]:
        raise ValueError("context exceeds the pinned model configuration")
    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_root, local_files_only=True, trust_remote_code=False
    )
    checks = []
    for request_hash, messages in sorted(requests.items()):
        prepared = prepare_request(messages, tokenizer)
        if prepared["request_sha256"] != request_hash:
            raise ValueError("saved request hash differs")
        checks.append(prepared)
    return {
        "schema_version": "forecast_task_context_v1",
        "status": "passed",
        "tokenizer_files": inventory(tokenizer_root),
        "chat_template_sha256": fingerprint(tokenizer.chat_template),
        "tokenizer_class": type(tokenizer).__name__,
        "context_limit": CONTEXT_LIMIT,
        "reserved_output_tokens": OUTPUT_RESERVATION,
        "thinking_enabled": True,
        "unique_requests": len(checks),
        "max_prompt_tokens": max(c["prompt_tokens"] for c in checks),
        "maximum_reserved_total": max(c["prompt_tokens"] for c in checks) + OUTPUT_RESERVATION,
        "actual_model_carriers_checked": False,
        "runtime_context_recheck_required": True,
        "checks": checks,
    }


def _copy_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output:
        output.write(source.read_bytes())


def snapshot_source(project_root, output):
    names = set(SOURCE_DEPENDENCIES)
    names.update(
        p.relative_to(project_root).as_posix()
        for p in (project_root / "src/disastertrace/forecast_task").glob("*.py")
    )
    names.update(
        p.relative_to(project_root).as_posix()
        for p in (project_root / "tests/p7_forecast_task").glob("*.py")
    )
    for name in sorted(names):
        _copy_file(project_root / name, output / name)
    return seal(output)


def _runtime():
    return {
        "python": platform.python_version(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("pydantic", "transformers", "tokenizers", "Jinja2")
        },
    }


def _write_diagnostics(root, diagnostics):
    write(root / "requests.json", diagnostics["requests"])
    for policy in diagnostics["captures"]:
        write(root / "diagnostics" / policy / "captures.json", diagnostics["captures"][policy])
        write(root / "diagnostics" / policy / "scores.json", diagnostics["scores"][policy])


def build_execution(source_input, output, project_root, tokenizer_root, protocol_path):
    output, project_root = Path(output), Path(project_root)
    output.mkdir(parents=True, exist_ok=False)
    source_copy = output / "input_sources"
    for name in ("acquisition", "review_v1", "input_evidence"):
        shutil.copytree(
            Path(source_input) / name,
            source_copy / name,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    _copy_file(Path(source_input) / "SOURCE_SCOPE.json", source_copy / "SOURCE_SCOPE.json")
    source_manifest = snapshot_source(project_root, output / "source")
    for name in TOKENIZER_FILES:
        _copy_file(Path(tokenizer_root) / name, output / "tokenizer" / name)
    _copy_file(Path(protocol_path), output / "PROTOCOL.md")
    compiled = compile_bundle(source_copy)
    for name, value in compiled.items():
        write(output / "data" / (name + ".json"), value)
    slots = schedule(compiled["public"])
    write(output / "schedule.json", slots)
    write(output / "answer_schema.json", SCHEMA)
    write(output / "system_contract.json", {"text": SYSTEM})
    diagnostics = run_programs(compiled["public"], compiled["private_reference"], slots)
    _write_diagnostics(output, diagnostics)
    context = context_report(diagnostics["requests"], output / "tokenizer")
    write(output / "context.json", context)
    execution = {
        "schema_version": "forecast_task_offline_execution_v1",
        "dataset_id": compiled["dataset"]["dataset_id"],
        "source_package_id": source_manifest["package_id"],
        "protocol_sha256": digest(output / "PROTOCOL.md"),
        "schedule_sha256": fingerprint(slots),
        "schema_sha256": fingerprint(SCHEMA),
        "system_sha256": fingerprint(SYSTEM),
        "requests_sha256": fingerprint(diagnostics["requests"]),
        "context_sha256": fingerprint(context),
        "runtime": _runtime(),
        "methods": list(METHODS),
        "repeats": REPEATS,
        "condition": "native_text_natural_issue_order_controlled_delivery",
        "independent_storms": compiled["dataset"]["counts"]["independent_storms"],
        "target_episodes": len(compiled["public"]["episodes"]),
        "checkpoint_queries": len(compiled["public"]["opportunities"]),
        "planned_slots_per_policy": len(slots),
        "planned_variable_slots_per_policy": len(slots) * 3,
        "candidate_model_answers": len(slots),
        "maximum_requested_output_tokens": len(slots) * OUTPUT_RESERVATION,
        "context_limit": CONTEXT_LIMIT,
        "output_reservation": OUTPUT_RESERVATION,
        "generation_authorized": False,
        "dispatch_compatible": False,
        "model_generations": 0,
        "source_downloads": 0,
        "new_human_gold_annotations": 0,
        "llm_judge": False,
        "diagnostic_policies": list(diagnostics["captures"]),
        "diagnostic_origin": "public_program_diagnostic",
        "diagnostic_file_hashes": inventory(output / "diagnostics"),
        "future_gpu_ceiling": 4,
    }
    execution["execution_id"] = fingerprint(execution)
    write(output / "execution.json", execution)
    manifest = seal(output)
    return {
        "execution_id": execution["execution_id"],
        "package_id": manifest["package_id"],
        "dataset_counts": compiled["dataset"]["counts"],
        "diagnostics": {p: v["counts"]["all_correct"] for p, v in diagnostics["scores"].items()},
        "slots_per_policy": len(slots),
        "context_unique_requests": context["unique_requests"],
        "maximum_reserved_total": context["maximum_reserved_total"],
        "model_generations": 0,
    }


def verify_execution(root):
    root = Path(root)
    manifest = verify(root)
    execution = read(root / "execution.json")
    if execution["execution_id"] != fingerprint(
        {k: v for k, v in execution.items() if k != "execution_id"}
    ):
        raise ValueError("execution identity mismatch")
    if (
        execution["generation_authorized"] is not False
        or execution["dispatch_compatible"] is not False
    ):
        raise ValueError("offline package cannot enable generation")
    source_manifest = verify(root / "source")
    running_root = Path(__file__).resolve().parents[3]
    for name, value in source_manifest["files"].items():
        if name.startswith("src/") and digest(running_root / name) != value:
            raise ValueError("running implementation differs from frozen source: " + name)
    compiled = compile_bundle(root / "input_sources")
    for name, value in compiled.items():
        if read(root / "data" / (name + ".json")) != value:
            raise ValueError("dataset reconstruction differs: " + name)
    slots = schedule(compiled["public"])
    if read(root / "schedule.json") != slots:
        raise ValueError("schedule reconstruction differs")
    if read(root / "answer_schema.json") != SCHEMA or read(root / "system_contract.json") != {
        "text": SYSTEM
    }:
        raise ValueError("output contract differs")
    reconstructed = run_programs(compiled["public"], compiled["private_reference"], slots)
    if reconstructed["requests"] != read(root / "requests.json"):
        raise ValueError("public request reconstruction differs")
    for policy in reconstructed["captures"]:
        for name in ("captures", "scores"):
            if (
                read(root / "diagnostics" / policy / (name + ".json"))
                != reconstructed[name][policy]
            ):
                raise ValueError("program reconstruction differs: " + policy + "/" + name)
    context = context_report(reconstructed["requests"], root / "tokenizer")
    if context != read(root / "context.json"):
        raise ValueError("pinned-tokenizer context reconstruction differs")
    bindings = {
        "dataset_id": compiled["dataset"]["dataset_id"],
        "source_package_id": source_manifest["package_id"],
        "schedule_sha256": fingerprint(slots),
        "schema_sha256": fingerprint(SCHEMA),
        "system_sha256": fingerprint(SYSTEM),
        "requests_sha256": fingerprint(reconstructed["requests"]),
        "context_sha256": fingerprint(context),
        "protocol_sha256": digest(root / "PROTOCOL.md"),
        "runtime": _runtime(),
        "diagnostic_file_hashes": inventory(root / "diagnostics"),
        "methods": list(METHODS),
        "repeats": REPEATS,
        "planned_slots_per_policy": len(slots),
        "candidate_model_answers": len(slots),
    }
    if any(execution[k] != v for k, v in bindings.items()):
        raise ValueError("execution bindings differ")
    return {
        "status": "passed",
        "execution_id": execution["execution_id"],
        "package_id": manifest["package_id"],
        "files_verified": len(manifest["files"]),
        "dataset_id": execution["dataset_id"],
        "slots_per_policy": len(slots),
        "policies": len(reconstructed["scores"]),
        "unique_requests": len(reconstructed["requests"]),
        "context_checks": len(context["checks"]),
        "model_generations": 0,
    }
