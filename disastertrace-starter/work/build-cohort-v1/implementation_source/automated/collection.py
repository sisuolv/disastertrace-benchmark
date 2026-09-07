"""Sequential collection with durable per-request records and a global attempt cap."""

from __future__ import annotations

import copy
import os
from dataclasses import asdict
from pathlib import Path

from .common import canonical, file_hash, fingerprint, write_json
from .dynamic import parse_decision, render_request, validate_episode
from .provider import ProviderClient, ProviderConfig, ProviderError


def _append(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(canonical(row) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def collect_model(
    episodes: list[dict],
    config: ProviderConfig,
    output: Path,
    *,
    max_queries: int,
    client: ProviderClient | None = None,
) -> dict:
    """Collect public responses with at most one configured HTTP attempt per selected slot."""
    if not isinstance(episodes, list) or not episodes:
        raise ValueError("nonempty episodes required")
    for episode in episodes:
        validate_episode(episode)
    if len({episode["episode_id"] for episode in episodes}) != len(episodes):
        raise ValueError("unique episode IDs required")
    if type(max_queries) is not int or max_queries < 0:
        raise ValueError("max_queries must be a nonnegative integer")
    if not isinstance(config, ProviderConfig):
        raise TypeError("validated ProviderConfig required")
    client = client or ProviderClient(config)
    if client.config != config:
        raise ValueError("client configuration does not match collection configuration")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    checkpoints = [
        {"episode_id": episode["episode_id"], "checkpoint_id": checkpoint["checkpoint_id"]}
        for episode in episodes
        for checkpoint in episode["checkpoints"]
    ]
    plan = {
        "schema_version": "provider_collection_v1",
        "config": asdict(config),
        "config_sha256": fingerprint(asdict(config)),
        "episodes_sha256": fingerprint(episodes),
        "episodes": [
            {"episode_id": episode["episode_id"], "checkpoint_count": len(episode["checkpoints"])}
            for episode in episodes
        ],
        "checkpoints": checkpoints,
        "max_queries": max_queries,
        "transport_kind": getattr(client, "transport_kind", "custom_client_unverified"),
        "automatic_retry": False,
        "resume_supported": False,
        "aggregate_token_cap_enforced": False,
        "monetary_cap_enforced": False,
        "eligible_for_llm_leaderboard": False,
    }
    write_json(output / "plan.json", plan)
    for name in ("requests.jsonl", "outcomes.jsonl", "responses.jsonl"):
        with (output / name).open("x", encoding="utf-8") as stream:
            stream.flush()
            os.fsync(stream.fileno())
    summary = {
        "schema_version": "provider_collection_v1",
        "status": "running",
        "plan_sha256": fingerprint(plan),
        "planned_checkpoints": len(checkpoints),
        "max_queries": max_queries,
        "attempts_started": 0,
        "completions_received": 0,
        "accepted_decisions": 0,
        "invalid_decisions": 0,
        "unsubmitted_checkpoints": len(checkpoints),
        "reported_prompt_tokens": 0,
        "reported_completion_tokens": 0,
        "responses_missing_usage": 0,
        "transport_kind": plan["transport_kind"],
        "stop_error": None,
        "automatic_retry": False,
        "aggregate_token_cap_enforced": False,
        "monetary_cap_enforced": False,
        "cost": None,
        "eligible_for_llm_leaderboard": False,
    }
    write_json(output / "summary.json", summary)
    stopped = False
    for episode in episodes:
        previous = None
        for checkpoint in episode["checkpoints"]:
            if summary["attempts_started"] >= max_queries:
                stopped = True
                summary["status"] = "budget_exhausted"
                break
            public_request = render_request(episode, checkpoint["checkpoint_id"], previous)
            prepared = client.prepare(public_request)
            identifiers = {
                "episode_id": episode["episode_id"],
                "checkpoint_id": checkpoint["checkpoint_id"],
            }
            request_record = {
                **identifiers,
                "attempt_number": summary["attempts_started"] + 1,
                "public_request": public_request,
                "public_request_sha256": fingerprint(public_request),
                "prepared": prepared,
            }
            _append(output / "requests.jsonl", request_record)
            summary["attempts_started"] += 1
            write_json(output / "summary.json", summary)
            try:
                completion = client.complete(copy.deepcopy(public_request))
                if (
                    not isinstance(completion, dict)
                    or not isinstance(completion.get("raw_response"), str)
                    or not isinstance(completion.get("metadata"), dict)
                    or completion["metadata"].get("request_sha256") != prepared["request_sha256"]
                ):
                    raise ProviderError(
                        "collection_metadata_mismatch", request_may_have_reached_provider=True
                    )
            except Exception as error:
                if not isinstance(error, ProviderError):
                    error = ProviderError(
                        "collection_client_error", request_may_have_reached_provider=True
                    )
                _append(
                    output / "outcomes.jsonl",
                    {
                        **identifiers,
                        "request_sha256": prepared["request_sha256"],
                        "status": "provider_error",
                        "error": error.as_dict(),
                        "state_after": copy.deepcopy(previous),
                    },
                )
                summary["status"] = "provider_error"
                summary["stop_error"] = error.as_dict()
                stopped = True
                break
            raw = completion["raw_response"]
            _append(output / "responses.jsonl", {**identifiers, "raw_response": raw})
            summary["completions_received"] += 1
            status = "accepted"
            try:
                previous = parse_decision(raw)
                summary["accepted_decisions"] += 1
            except (ValueError, TypeError, KeyError):
                status = "invalid"
                summary["invalid_decisions"] += 1
            metadata = completion["metadata"]
            usage = metadata.get("usage")
            if usage is None:
                summary["responses_missing_usage"] += 1
            else:
                summary["reported_prompt_tokens"] += usage["prompt_tokens"]
                summary["reported_completion_tokens"] += usage["completion_tokens"]
            _append(
                output / "outcomes.jsonl",
                {
                    **identifiers,
                    "request_sha256": prepared["request_sha256"],
                    "raw_response_sha256": fingerprint(raw),
                    "metadata": metadata,
                    "metadata_sha256": fingerprint(metadata),
                    "status": status,
                    "state_after": copy.deepcopy(previous),
                },
            )
            summary["unsubmitted_checkpoints"] = len(checkpoints) - summary["completions_received"]
            write_json(output / "summary.json", summary)
        if stopped:
            break
    if not stopped:
        summary["status"] = "completed"
    summary["unsubmitted_checkpoints"] = len(checkpoints) - summary["completions_received"]
    summary["artifact_sha256"] = {
        name: file_hash(output / name)
        for name in ("plan.json", "requests.jsonl", "outcomes.jsonl", "responses.jsonl")
    }
    write_json(output / "summary.json", summary)
    return summary
