"""Bind optional model preparation/collection to a frozen build and event split."""

from __future__ import annotations

import os
from pathlib import Path

from .common import file_hash, strict_json, write_json
from .dynamic import render_request
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
) -> dict:
    manifest = verify_build(build_path)
    implementation = _require_implementation(build_path)
    if type(max_queries) is not int or max_queries < 0:
        raise ValueError("max_queries must be a nonnegative integer")
    config = _configuration(config_path)
    episodes = selected_episodes(build_path, split)
    if output.exists():
        raise ValueError("model preparation output exists; choose a new path")
    first = episodes[0]
    request = render_request(first, first["checkpoints"][0]["checkpoint_id"], None)
    prepared = ProviderClient(config).prepare(request)
    placeholder = "REPLACE_WITH" in config.model
    result = {
        "schema_version": "model_preparation_v1",
        "build_id": manifest["build_id"],
        "implementation_id": implementation["implementation_id"],
        "split": split,
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
) -> dict:
    from .collection import collect_model

    manifest = verify_build(build_path)
    implementation = _require_implementation(build_path)
    config = _configuration(config_path)
    if "REPLACE_WITH" in config.model:
        raise ValueError("replace the example model identifier before collection")
    if type(max_queries) is not int or max_queries < 0:
        raise ValueError("max_queries must be a nonnegative integer")
    episodes = selected_episodes(build_path, split)
    if output.exists():
        raise ValueError("model collection output exists; choose a new path")
    output.mkdir(parents=True)
    context = {
        "schema_version": "model_collection_build_v1",
        "build_id": manifest["build_id"],
        "implementation_id": implementation["implementation_id"],
        "split": split,
        "selected_episode_ids": [ep["episode_id"] for ep in episodes],
        "provider_config_sha256": file_hash(config_path),
        "max_queries": max_queries,
        "eligible_for_llm_leaderboard": False,
    }
    write_json(output / "build_context.json", context)
    collection = collect_model(episodes, config, output / "collection", max_queries=max_queries)
    imported = run(
        build_path,
        output / "imported_run",
        track="dynamic",
        backend="submissions",
        predictions_path=output / "collection/responses.jsonl",
        max_queries=max_queries,
        split=split,
    )
    scored = score(build_path, output / "imported_run", output / "score.json")
    result = {
        **context,
        "collection": collection,
        "offline_import": imported,
        "metrics": scored["metrics"],
        "interpretation": "Actual collection telemetry is separate from the zero-network offline submission import; no certified leaderboard claim.",
    }
    write_json(output / "result.json", result)
    return result
