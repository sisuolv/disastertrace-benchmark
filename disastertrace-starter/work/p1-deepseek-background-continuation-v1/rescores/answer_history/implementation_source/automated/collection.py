"""Sequential collection with durable per-request records and a global attempt cap."""

from __future__ import annotations

import copy
import os
from dataclasses import asdict
from pathlib import Path

from .collection_audit import ARTIFACTS, _guard, audit_collection, validate_completion
from .common import canonical, file_hash, fingerprint, read_jsonl, strict_json, write_json
from .dynamic import parse_decision, render_request, validate_episode
from .methods import DEFAULT_METHOD, validate_method
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
    method: str = DEFAULT_METHOD,
    resume_from: Path | None = None,
    max_request_bytes: int | None = None,
    max_reserved_output_tokens: int | None = None,
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
    validate_method(method)
    for name, value in (
        ("max_request_bytes", max_request_bytes),
        ("max_reserved_output_tokens", max_reserved_output_tokens),
    ):
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError(name + " must be a nonnegative integer or null")
    if not isinstance(config, ProviderConfig):
        raise TypeError("validated ProviderConfig required")
    client = client or ProviderClient(config)
    if client.config != config:
        raise ValueError("client configuration does not match collection configuration")
    recovered = None
    lineage = None
    if resume_from is not None:
        resume_from = Path(resume_from)
        recovered = audit_collection(episodes, resume_from, allow_incomplete=True)
        if not recovered["safe_to_resume"]:
            raise ValueError("cannot resume an uncertain in-flight attempt or provider_error")
        old_plan = strict_json((resume_from / "plan.json").read_text(encoding="utf-8"))
        if (
            old_plan["config_sha256"] != fingerprint(asdict(config))
            or recovered["method"] != method
            or old_plan["transport_kind"]
            != getattr(client, "transport_kind", "custom_client_unverified")
        ):
            raise ValueError(
                "resume requires identical config, method, episodes and transport kind"
            )
        if recovered["counters"]["attempts_started"] > max_queries:
            raise ValueError("resume total max_queries is below previously started attempts")
        if (
            max_reserved_output_tokens is not None
            and recovered["counters"]["reserved_output_tokens"] > max_reserved_output_tokens
        ):
            raise ValueError("resume output reservation cap is below previously reserved tokens")
        if max_request_bytes is not None and any(
            len(row["prepared"]["raw_request"].encode("utf-8")) > max_request_bytes
            for row in recovered["verified_requests"]
        ):
            raise ValueError("resume request byte cap excludes previous requests")
        lineage = {
            "collection_path": str(resume_from.resolve()),
            "plan_sha256": fingerprint(old_plan),
            "summary_sha256": file_hash(resume_from / "summary.json"),
            "copied_attempts": recovered["counters"]["attempts_started"],
        }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    checkpoints = [
        {"episode_id": episode["episode_id"], "checkpoint_id": checkpoint["checkpoint_id"]}
        for episode in episodes
        for checkpoint in episode["checkpoints"]
    ]
    plan = {
        "schema_version": "provider_collection_v2",
        "method": method,
        "config": asdict(config),
        "config_sha256": fingerprint(asdict(config)),
        "episodes_sha256": fingerprint(episodes),
        "episodes": [
            {
                "episode_id": episode["episode_id"],
                "checkpoint_count": len(episode["checkpoints"]),
                "episode_sha256": fingerprint(episode),
            }
            for episode in episodes
        ],
        "checkpoints": checkpoints,
        "max_queries": max_queries,
        "max_request_bytes": max_request_bytes,
        "max_reserved_output_tokens": max_reserved_output_tokens,
        "resume_from": lineage,
        "transport_kind": getattr(client, "transport_kind", "custom_client_unverified"),
        "automatic_retry": False,
        "resume_supported": True,
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
        "schema_version": "provider_collection_v2",
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
        "reserved_output_tokens": 0,
        "request_bytes_sent": 0,
        "transport_kind": plan["transport_kind"],
        "stop_error": None,
        "stop_guard": None,
        "automatic_retry": False,
        "aggregate_token_cap_enforced": False,
        "monetary_cap_enforced": False,
        "cost": None,
        "eligible_for_llm_leaderboard": False,
    }
    if recovered is not None:
        # Preserve completed invalid responses too: a paid attempt is never repeated.
        verified_prefix = {
            "requests.jsonl": recovered["verified_requests"],
            "outcomes.jsonl": recovered["verified_outcomes"],
            "responses.jsonl": recovered["responses"],
        }
        for name, rows in verified_prefix.items():
            for row in rows:
                _append(output / name, row)
        summary.update(recovered["counters"])
    write_json(output / "summary.json", summary)
    stopped = False
    slot_index = 0
    recovered_outcomes = read_jsonl(output / "outcomes.jsonl")
    for episode in episodes:
        previous = None
        history = []
        for checkpoint in episode["checkpoints"]:
            if slot_index < len(recovered_outcomes):
                outcome = recovered_outcomes[slot_index]
                previous = copy.deepcopy(outcome["state_after"])
                if outcome["status"] == "accepted":
                    history.append(copy.deepcopy(previous))
                slot_index += 1
                continue
            if summary["attempts_started"] >= max_queries:
                stopped = True
                summary["status"] = "budget_exhausted"
                break
            public_request = render_request(
                episode, checkpoint["checkpoint_id"], previous, method=method, history=history
            )
            prepared = client.prepare(public_request)
            identifiers = {
                "episode_id": episode["episode_id"],
                "checkpoint_id": checkpoint["checkpoint_id"],
            }
            guard = _guard(prepared, summary, plan, identifiers)
            if guard is not None:
                summary["status"], summary["stop_guard"] = guard
                stopped = True
                break
            request_record = {
                **identifiers,
                "attempt_number": summary["attempts_started"] + 1,
                "public_request": public_request,
                "public_request_sha256": fingerprint(public_request),
                "prepared": prepared,
            }
            _append(output / "requests.jsonl", request_record)
            summary["attempts_started"] += 1
            summary["reserved_output_tokens"] += config.max_output_tokens
            summary["request_bytes_sent"] += len(prepared["raw_request"].encode("utf-8"))
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
                try:
                    validate_completion(
                        completion["raw_response"], completion["metadata"], prepared, config
                    )
                except (ValueError, TypeError, KeyError, IndexError):
                    raise ProviderError(
                        "collection_metadata_mismatch", request_may_have_reached_provider=True
                    ) from None
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
                history.append(copy.deepcopy(previous))
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
            slot_index += 1
        if stopped:
            break
    if not stopped:
        summary["status"] = "completed"
    summary["unsubmitted_checkpoints"] = len(checkpoints) - summary["completions_received"]
    summary["artifact_sha256"] = {name: file_hash(output / name) for name in ARTIFACTS}
    write_json(output / "summary.json", summary)
    return summary
