"""Freeze a network-free pilot matrix, diagnostic runs and collection rehearsal."""

from __future__ import annotations

from pathlib import Path

from .collection import collect_model
from .collection_audit import audit_collection
from .common import canonical, file_hash, fingerprint, safe_child, strict_json, write_json
from .dataset_audit import audit_dataset
from .dynamic import diagnostic_response
from .methods import METHODS, method_contract
from .model_workflow import _match_collection_trace
from .provider import ProviderClient, ProviderConfig
from .workflow import (
    _require_implementation,
    report,
    run,
    score,
    selected_episodes,
    verify_build,
)


def _read(path: Path) -> dict:
    return strict_json(path.read_text(encoding="utf-8"))


def _validate_verification(verification: dict, implementation_id: str) -> None:
    if (
        not isinstance(verification, dict)
        or verification.get("schema_version") != "offline_verification_v1"
        or verification.get("implementation_id") != implementation_id
        or not isinstance(verification.get("checks"), list)
        or not verification["checks"]
        or type(verification.get("pytest_passed")) is not int
        or verification["pytest_passed"] < 1
        or type(verification.get("pytest_skipped")) is not int
        or verification["pytest_skipped"] != 0
    ):
        raise ValueError(
            "verification must cover this implementation with passing, unskipped tests"
        )


def experiment_matrix(build_path: Path, specification: dict) -> dict:
    if (
        not isinstance(specification, dict)
        or set(specification)
        != {"schema_version", "model_slots", "methods", "repeats", "smoke_event_ids"}
        or specification["schema_version"] != "pre_api_pilot_v1"
        or specification["model_slots"] != ["model_a", "model_b"]
        or specification["methods"] != list(METHODS)
        or type(specification["repeats"]) is not int
        or specification["repeats"] != 1
    ):
        raise ValueError("unsupported frozen pilot specification")
    matrix = []
    for phase, split, groups in (
        ("smoke", "development", specification["smoke_event_ids"]),
        ("development", "development", None),
        ("heldout", "heldout", None),
    ):
        episodes = selected_episodes(build_path, split, group_ids=groups)
        if phase == "smoke" and not groups:
            raise ValueError("smoke requires an explicit development event selection")
        for slot in specification["model_slots"]:
            for method in METHODS:
                matrix.append(
                    {
                        "phase": phase,
                        "split": split,
                        "model_slot": slot,
                        "method": method,
                        "repeat": 1,
                        "group_ids": list(dict.fromkeys(ep["group_id"] for ep in episodes)),
                        "episode_ids": [ep["episode_id"] for ep in episodes],
                        "max_queries": sum(len(ep["checkpoints"]) for ep in episodes),
                    }
                )
    return {
        "schema_version": "frozen_experiment_matrix_v1",
        "specification": specification,
        "method_contracts": [method_contract(method) for method in METHODS],
        "cells": matrix,
        "requests_by_phase": {
            phase: sum(cell["max_queries"] for cell in matrix if cell["phase"] == phase)
            for phase in ("smoke", "development", "heldout")
        },
        "phase_execution": "smoke_then_development_then_heldout; separate collections",
        "smoke_overlap": "smoke is a development subset; do not pool duplicate runs or reuse answers as independent samples",
        "model_selection": "two distinct model families recommended; actual identities unresolved",
        "pending_live_configuration": [
            "served_model_ids_and_versions",
            "provider_endpoints_and_parameter_support",
            "credential_environment_variables",
            "context_and_output_token_limits",
            "provider_pricing_and_trial_money_budget",
        ],
        "primary_reporting": [
            "grounded_state",
            "schema_success",
            "known_answer_coverage",
            "necessary_change_and_preservation_with_opportunity_counts",
            "action_accuracy_as_secondary_metric",
            "per_event_and_event_macro_and_pooled",
        ],
        "no_new_human_item_review": True,
        "prompt_or_parser_tuning_on_heldout": False,
        "independent_sampling_repeats": 1,
        "confidence_intervals": "not claimed for this small purposeful cohort",
        "eligible_for_llm_leaderboard": False,
    }


def rehearse_collection(build_path: Path, output: Path, *, groups: list[str], method: str) -> dict:
    """Exercise real journal code with an injected deterministic transport, no sockets."""
    episodes = selected_episodes(build_path, "development", group_ids=groups)
    calls = []

    def transport(url, body, headers, timeout, max_response_bytes):
        payload = strict_json(body.decode("utf-8"))
        request = strict_json(payload["messages"][1]["content"])
        calls.append(request)
        envelope = {
            "model": "offline-rule-fixture-not-an-llm",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": diagnostic_response(request, "rule"),
                    },
                }
            ],
        }
        return 200, canonical(envelope).encode("utf-8")

    config = ProviderConfig(
        model="offline-rule-fixture-not-an-llm",
        base_url="http://127.0.0.1:8000/v1",
        key_env=None,
        max_output_tokens=1024,
        token_parameter="max_tokens",
        temperature=0,
        timeout=60,
        max_response_bytes=1048576,
    )
    total = sum(len(ep["checkpoints"]) for ep in episodes)
    partial_cap = min(3, total - 1)
    if partial_cap < 1:
        raise ValueError("rehearsal requires at least two checkpoints")
    partial = collect_model(
        episodes,
        config,
        output / "partial",
        max_queries=partial_cap,
        method=method,
        client=ProviderClient(config, transport=transport),
        max_request_bytes=262144,
        max_reserved_output_tokens=partial_cap * 1024,
    )
    partial_audit = audit_collection(episodes, output / "partial")
    if not partial_audit["safe_to_resume"]:
        raise ValueError("offline partial collection is not safely resumable")
    resumed = collect_model(
        episodes,
        config,
        output / "resumed",
        max_queries=total,
        method=method,
        client=ProviderClient(config, transport=transport),
        resume_from=output / "partial",
        max_request_bytes=262144,
        max_reserved_output_tokens=total * 1024,
    )
    audit = audit_collection(episodes, output / "resumed")
    if (
        len(calls) != total
        or [row["public_request"] for row in audit["verified_requests"]] != calls
    ):
        raise ValueError("rehearsal resume repeated or changed a request")
    imported = output / "imported_run"
    run(
        build_path,
        imported,
        track="dynamic",
        backend="submissions",
        method=method,
        split="development",
        group_ids=groups,
        max_queries=total,
        predictions_path=output / "resumed/responses.jsonl",
    )
    from .common import read_jsonl

    _match_collection_trace(audit, read_jsonl(imported / "trace.jsonl"))
    result = score(build_path, imported, output / "score.json")
    if result["metrics"]["grounded_state"]["value"] != 1:
        raise ValueError("offline collection rehearsal did not match the expected diagnostic")
    write_json(output / "audit.json", audit)
    summary = {
        "method": method,
        "fixture_transport_calls": len(calls),
        "live_model_calls": 0,
        "partial_status": partial["status"],
        "resumed_status": resumed["status"],
        "completed_checkpoints": audit["completed_checkpoints"],
        "requests_not_repeated": True,
        "actual_requests_match_scored_trace": True,
        "reported_tokens": None,
        "metrics": result["metrics"],
        "interpretation": "Deterministic injected transport; not a model evaluation or endpoint compatibility test.",
    }
    write_json(output / "rehearsal.json", summary)
    return summary


def prepare_experiment(
    build_path: Path,
    specification_path: Path,
    output: Path,
    *,
    verification_path: Path | None = None,
) -> dict:
    manifest = verify_build(build_path)
    implementation = _require_implementation(build_path)
    matrix = experiment_matrix(build_path, _read(specification_path))
    audit = audit_dataset(build_path)
    if not audit["all_required_checks_pass"]:
        raise ValueError("required dataset audit checks failed")
    if output.exists():
        raise ValueError("preflight output exists; choose a new directory")
    output.mkdir(parents=True)
    verification = None
    if verification_path is not None:
        verification = _read(verification_path)
        _validate_verification(verification, implementation["implementation_id"])
        for index, check in enumerate(verification["checks"]):
            log = safe_child(verification_path.parent, check["log"])
            if check["exit_code"] != 0 or file_hash(log) != check["log_sha256"]:
                raise ValueError("verification command failed or its log changed")
            target = output / "verification" / f"check-{index}.log"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(log.read_bytes())
            check["original_log"] = check["log"]
            check["log"] = target.name
        write_json(output / "verification/record.json", verification)
    write_json(output / "dataset_audit.json", audit)
    write_json(output / "experiment_matrix.json", matrix)
    scores, diagnostics = [], []
    for split in ("development", "heldout"):
        checkpoints = sum(len(ep["checkpoints"]) for ep in selected_episodes(build_path, split))
        for method in METHODS:
            for backend in ("rule", "last-arrival", "no-update"):
                name = f"{split}-{method}-{backend}"
                run_path, score_path = output / "runs" / name, output / "scores" / f"{name}.json"
                run(
                    build_path,
                    run_path,
                    track="dynamic",
                    backend=backend,
                    split=split,
                    method=method,
                    max_queries=checkpoints,
                )
                result = score(build_path, run_path, score_path)
                metrics = result["metrics"]
                if (
                    metrics["schema_success"]["value"] != 1
                    or (
                        backend == "rule"
                        and any(
                            metrics[key]["value"] != 1
                            for key in ("grounded_state", "action_accuracy")
                        )
                    )
                    or (backend != "rule" and metrics["grounded_state"]["value"] >= 1)
                ):
                    raise ValueError(f"dynamic control failed: {name}")
                scores.append(score_path)
                diagnostics.append(
                    {
                        "split": split,
                        "method": method,
                        "backend": backend,
                        "metrics": result["metrics"],
                    }
                )
    for backend in ("reference-fixture", "empty-control"):
        run_path, score_path = output / "runs" / backend, output / "scores" / f"{backend}.json"
        task_count = _read(build_path / "summary.json")["disasterbench_admitted"]
        run(build_path, run_path, track="disasterbench", backend=backend, max_queries=task_count)
        planning = score(build_path, run_path, score_path)["aggregate"]
        if planning["expected_tasks"] != task_count or planning["correct_tasks"] != (
            task_count if backend == "reference-fixture" else 0
        ):
            raise ValueError(f"planning control failed: {backend}")
        scores.append(score_path)
    report(build_path, scores, output / "REPORT.md")
    rehearsals = [
        rehearse_collection(
            build_path,
            output / "rehearsal" / method,
            groups=matrix["specification"]["smoke_event_ids"],
            method=method,
        )
        for method in METHODS
    ]
    result = {
        "schema_version": "pre_api_readiness_v1",
        "build_id": manifest["build_id"],
        "implementation_id": implementation["implementation_id"],
        "offline_ready": verification is not None,
        "live_ready": False,
        "offline_suite_evidence_attached": verification is not None,
        "dataset_checks_pass": True,
        "diagnostic_expectations_pass": True,
        "diagnostic_runs": len(diagnostics),
        "planning_control_runs": 2,
        "collection_rehearsals": rehearsals,
        "requests_by_phase": matrix["requests_by_phase"],
        "live_model_calls": 0,
        "new_human_reviews": 0,
        "pending_live_configuration": matrix["pending_live_configuration"],
        "diagnostics": diagnostics,
        "interpretation": "Ready to configure a first model pilot when offline checks pass; no real LLM result, formal benchmark release, or current provider compatibility claim.",
    }
    write_json(output / "readiness.json", result)
    lock = {
        "schema_version": "pre_api_artifact_manifest_v1",
        "build_id": manifest["build_id"],
        "implementation_id": implementation["implementation_id"],
        "files": {
            str(path.relative_to(output)): file_hash(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        },
    }
    lock["package_id"] = fingerprint(lock)
    write_json(output / "manifest.json", lock)
    return {
        key: value
        for key, value in result.items()
        if key not in {"diagnostics", "collection_rehearsals"}
    } | {"package_id": lock["package_id"]}


def verify_preflight(build_path: Path, output: Path) -> dict:
    build_manifest = verify_build(build_path)
    implementation = _require_implementation(build_path)
    lock = _read(output / "manifest.json")
    if lock["package_id"] != fingerprint(
        {key: value for key, value in lock.items() if key != "package_id"}
    ):
        raise ValueError("preflight manifest fingerprint mismatch")
    if (
        lock["build_id"] != build_manifest["build_id"]
        or lock["implementation_id"] != implementation["implementation_id"]
    ):
        raise ValueError("preflight build/implementation mismatch")
    required = {"readiness.json", "dataset_audit.json", "experiment_matrix.json", "REPORT.md"}
    if not isinstance(lock["files"], dict) or not required <= set(lock["files"]):
        raise ValueError("preflight manifest lacks required artifacts")
    for relative, expected in lock["files"].items():
        if file_hash(safe_child(output, relative)) != expected:
            raise ValueError(f"preflight artifact changed: {relative}")
    readiness = _read(output / "readiness.json")
    if (
        readiness["build_id"] != lock["build_id"]
        or readiness["implementation_id"] != lock["implementation_id"]
    ):
        raise ValueError("preflight readiness identity mismatch")
    dataset = _read(output / "dataset_audit.json")
    if dataset != audit_dataset(build_path):
        raise ValueError("preflight dataset audit mismatch")
    matrix = _read(output / "experiment_matrix.json")
    if matrix != experiment_matrix(build_path, matrix["specification"]):
        raise ValueError("preflight experiment matrix mismatch")
    if readiness["offline_ready"]:
        if "verification/record.json" not in lock["files"]:
            raise ValueError("ready preflight lacks required verification record")
        verification = _read(output / "verification/record.json")
        _validate_verification(verification, lock["implementation_id"])
        for check in verification["checks"]:
            log = safe_child(output / "verification", check["log"])
            if check["exit_code"] != 0 or file_hash(log) != check["log_sha256"]:
                raise ValueError("preflight verification log mismatch")
    return {
        "valid": True,
        "offline_ready": readiness["offline_ready"],
        "live_ready": False,
        "package_id": lock["package_id"],
        "files_verified": len(lock["files"]),
    }
