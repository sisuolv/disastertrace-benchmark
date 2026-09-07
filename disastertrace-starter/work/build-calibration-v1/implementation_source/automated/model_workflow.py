"""Bind optional model preparation/collection to a frozen build and event split."""

from __future__ import annotations

import os
from pathlib import Path

from .common import file_hash, fingerprint, read_jsonl, strict_json, write_json
from .dynamic import render_request
from .methods import DEFAULT_METHOD, method_contract, validate_method
from .provider import ProviderClient, ProviderConfig
from .workflow import _require_implementation, run, score, selected_episodes, verify_build


def _configuration(path: Path) -> ProviderConfig:
    return ProviderConfig.from_dict(strict_json(path.read_text(encoding="utf-8")))


def prepare_model(
    build_path: Path,
    config_path: Path,
    output: Path,
    *,
    split: str = "development",
    max_queries: int,
    method: str = DEFAULT_METHOD,
    group_ids: list[str] | None = None,
) -> dict:
    manifest = verify_build(build_path)
    implementation = _require_implementation(build_path)
    if type(max_queries) is not int or max_queries < 0:
        raise ValueError("max_queries must be a nonnegative integer")
    config = _configuration(config_path)
    method = validate_method(method)
    episodes = selected_episodes(build_path, split, group_ids=group_ids)
    if output.exists():
        raise ValueError("model preparation output exists; choose a new path")
    first = episodes[0]
    request = render_request(first, first["checkpoints"][0]["checkpoint_id"], None, method=method)
    prepared = ProviderClient(config).prepare(request)
    placeholder = "REPLACE_WITH" in config.model
    result = {
        "schema_version": "model_preparation_v1",
        "build_id": manifest["build_id"],
        "implementation_id": implementation["implementation_id"],
        "split": split,
        "method": method,
        "method_contract": method_contract(method),
        "group_ids": group_ids,
        "selected_episode_ids": [ep["episode_id"] for ep in episodes],
        "expected_checkpoints": sum(len(ep["checkpoints"]) for ep in episodes),
        "max_queries": max_queries,
        "model_calls": 0,
        "model_configuration_complete": not placeholder,
        "credential_configured": bool(os.environ.get(config.key_env)) if config.key_env else None,
        "endpoint_connectivity_tested": False,
        "monetary_cap_enforced": False,
        "aggregate_token_cap_enforced": False,
        "first_request_only": prepared,
        "remaining_requests": "constructed_sequentially_from_actual_accepted_responses",
        "eligible_for_llm_leaderboard": False,
    }
    write_json(output, result)
    return result


def collect_from_build(
    build_path: Path,
    config_path: Path,
    output: Path,
    *,
    split: str = "development",
    max_queries: int,
    method: str = DEFAULT_METHOD,
    group_ids: list[str] | None = None,
    resume_from: Path | None = None,
    max_request_bytes: int | None = None,
    max_reserved_output_tokens: int | None = None,
) -> dict:
    from .collection import collect_model
    from .collection_audit import audit_collection

    manifest = verify_build(build_path)
    implementation = _require_implementation(build_path)
    config = _configuration(config_path)
    if "REPLACE_WITH" in config.model:
        raise ValueError("replace the example model identifier before collection")
    if type(max_queries) is not int or max_queries < 0:
        raise ValueError("max_queries must be a nonnegative integer")
    method = validate_method(method)
    episodes = selected_episodes(build_path, split, group_ids=group_ids)
    if output.exists():
        raise ValueError("model collection output exists; choose a new path")
    output.mkdir(parents=True)
    context = {
        "schema_version": "model_collection_build_v1",
        "build_id": manifest["build_id"],
        "implementation_id": implementation["implementation_id"],
        "split": split,
        "method": method,
        "method_contract": method_contract(method),
        "group_ids": group_ids,
        "selected_episode_ids": [ep["episode_id"] for ep in episodes],
        "provider_config_sha256": file_hash(config_path),
        "max_queries": max_queries,
        "max_request_bytes": max_request_bytes,
        "max_reserved_output_tokens": max_reserved_output_tokens,
        "eligible_for_llm_leaderboard": False,
    }
    write_json(output / "build_context.json", context)
    collection = collect_model(
        episodes,
        config,
        output / "collection",
        max_queries=max_queries,
        method=method,
        resume_from=resume_from,
        max_request_bytes=max_request_bytes,
        max_reserved_output_tokens=max_reserved_output_tokens,
    )
    audit = audit_collection(episodes, output / "collection")
    write_json(output / "collection_audit.json", audit)
    imported = run(
        build_path,
        output / "imported_run",
        track="dynamic",
        backend="submissions",
        predictions_path=output / "collection/responses.jsonl",
        max_queries=max_queries,
        split=split,
        method=method,
        group_ids=group_ids,
    )
    traces = read_jsonl(output / "imported_run/trace.jsonl")
    _match_collection_trace(audit, traces)
    imported["collection_binding"] = {
        "relative_path": "../collection",
        "audit_sha256": fingerprint(audit),
        "artifact_sha256": {
            path.name: file_hash(path)
            for path in sorted((output / "collection").iterdir())
            if path.is_file()
        },
    }
    write_json(output / "imported_run/run.json", imported)
    scored = score(build_path, output / "imported_run", output / "score.json")
    result = {
        **context,
        "collection": collection,
        "collection_audit_sha256": fingerprint(audit),
        "offline_import": imported,
        "metrics": scored["metrics"],
        "interpretation": "Actual collection telemetry is separate from the zero-network offline submission import; no certified leaderboard claim.",
    }
    write_json(output / "result.json", result)
    return result


def _match_collection_trace(audit: dict, traces: list[dict]) -> None:
    """Tie independently verified model exposures to the trace used for scoring."""
    indexed = {(row["episode_id"], row["checkpoint_id"]): row for row in traces}
    if len(indexed) != len(traces):
        raise ValueError("duplicate checkpoint in collection-bound trace")
    responses = {(row["episode_id"], row["checkpoint_id"]): row for row in audit["responses"]}
    for key, row in indexed.items():
        if row.get("method", DEFAULT_METHOD) != audit["method"]:
            raise ValueError("trace method differs from audited collection")
        if key not in responses and (
            row["raw_response"] != "" or row["status"] not in {"missing", "budget_exhausted"}
        ):
            raise ValueError("trace contains a response without audited collection evidence")
    for request in audit["verified_requests"]:
        row = indexed.get((request["episode_id"], request["checkpoint_id"]))
        if row is None or row["request"] != request["public_request"]:
            raise ValueError("imported trace differs from audited collection request")
    for response in audit["responses"]:
        row = indexed.get((response["episode_id"], response["checkpoint_id"]))
        if row is None or row["raw_response"] != response["raw_response"]:
            raise ValueError("imported trace differs from audited collection response")
