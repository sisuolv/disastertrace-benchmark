"""Reconstruct a collection from public episodes, requests and response bodies.

This is a consistency audit, not provider authentication: a party able to replace
every local artifact can fabricate a mutually consistent collection.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path

from .common import file_hash, fingerprint, read_jsonl, strict_json
from .dynamic import parse_decision, render_request, validate_episode
from .methods import DEFAULT_METHOD, validate_method
from .provider import ProviderClient, ProviderConfig, _parse_response

ARTIFACTS = ("plan.json", "requests.jsonl", "outcomes.jsonl", "responses.jsonl")
COUNTERS = (
    "attempts_started",
    "completions_received",
    "accepted_decisions",
    "invalid_decisions",
    "unsubmitted_checkpoints",
    "reported_prompt_tokens",
    "reported_completion_tokens",
    "responses_missing_usage",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("collection audit: " + message)


def validate_collection_inputs(episodes: list[dict]) -> None:
    _require(isinstance(episodes, list) and bool(episodes), "nonempty episodes required")
    for episode in episodes:
        validate_episode(episode)
    _require(len({row["episode_id"] for row in episodes}) == len(episodes), "duplicate episodes")


def _same(left: object, right: object) -> bool:
    return fingerprint(left) == fingerprint(right)


def _identifier(episode: dict, checkpoint: dict) -> dict:
    return {"episode_id": episode["episode_id"], "checkpoint_id": checkpoint["checkpoint_id"]}


def _count_start(total: int) -> dict:
    return {
        "attempts_started": 0,
        "completions_received": 0,
        "accepted_decisions": 0,
        "invalid_decisions": 0,
        "unsubmitted_checkpoints": total,
        "reported_prompt_tokens": 0,
        "reported_completion_tokens": 0,
        "responses_missing_usage": 0,
        "reserved_output_tokens": 0,
        "request_bytes_sent": 0,
    }


def validate_completion(raw: str, metadata: dict, prepared: dict, config: ProviderConfig) -> None:
    """Validate wire/body-derived metadata before a response enters state history."""
    _require(isinstance(raw, str) and isinstance(metadata, dict), "invalid completion shape")
    for key, value in prepared.items():
        _require(
            _same(metadata.get(key), value), "completion metadata differs from request: " + key
        )
    _require(metadata.get("schema_version") == "provider_completion_v1", "metadata schema")
    body = metadata.get("raw_response_body")
    _require(isinstance(body, str), "raw response body missing")
    _require(len(body.encode("utf-8")) <= config.max_response_bytes, "oversized response body")
    parsed_raw, model, reason, usage = _parse_response(strict_json(body))
    _require(parsed_raw == raw, "raw response differs from provider body")
    derived = {
        "response_model": model,
        "finish_reason": reason,
        "usage": usage,
        "usage_available": usage is not None,
        "reported_output_token_cap_exceeded": (
            usage["completion_tokens"] > config.max_output_tokens if usage is not None else None
        ),
        "http_status": 200,
        "attempt_count": 1,
        "automatic_retry": False,
        "cost": None,
        "aggregate_token_cap_enforced": False,
        "monetary_cap_enforced": False,
    }
    for key, value in derived.items():
        _require(
            key in metadata and _same(metadata[key], value), "invalid response metadata: " + key
        )
    _require(
        set(metadata)
        == set(prepared)
        | set(derived)
        | {"schema_version", "raw_response_body", "elapsed_seconds"},
        "unexpected completion metadata fields",
    )
    elapsed = metadata.get("elapsed_seconds")
    _require(
        type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0,
        "invalid elapsed time",
    )


def _guard(
    prepared: dict, counters: dict, plan: dict, identifiers: dict
) -> tuple[str, dict] | None:
    size = len(prepared["raw_request"].encode("utf-8"))
    byte_limit = plan.get("max_request_bytes")
    reservation_limit = plan.get("max_reserved_output_tokens")
    if byte_limit is not None and size > byte_limit:
        return "request_bytes_exceeded", {
            **identifiers,
            "request_bytes": size,
            "max_request_bytes": byte_limit,
        }
    next_reservation = counters["reserved_output_tokens"] + plan["config"]["max_output_tokens"]
    if reservation_limit is not None and next_reservation > reservation_limit:
        return "output_reservation_exhausted", {
            **identifiers,
            "reserved_output_tokens": counters["reserved_output_tokens"],
            "next_reserved_output_tokens": next_reservation,
            "max_reserved_output_tokens": reservation_limit,
        }
    return None


def audit_collection(
    episodes: list[dict], collection_path: Path, *, allow_incomplete: bool = False
) -> dict:
    """Audit offline; incomplete clean prefixes are resumable, in-flight calls are not."""
    validate_collection_inputs(episodes)
    root = Path(collection_path)
    plan = strict_json((root / "plan.json").read_text(encoding="utf-8"))
    summary = strict_json((root / "summary.json").read_text(encoding="utf-8"))
    _require(isinstance(plan, dict) and isinstance(summary, dict), "object plan/summary required")
    version = plan.get("schema_version")
    _require(version in {"provider_collection_v1", "provider_collection_v2"}, "unsupported schema")
    _require(summary.get("schema_version") == version, "summary schema mismatch")
    if version == "provider_collection_v2":
        _require(
            all(
                key in plan
                for key in (
                    "method",
                    "max_request_bytes",
                    "max_reserved_output_tokens",
                    "resume_from",
                )
            ),
            "missing v2 plan fields",
        )
        _require(plan.get("resume_supported") is True, "v2 recovery contract mismatch")
        lineage = plan["resume_from"]
        if lineage is not None:
            _require(
                isinstance(lineage, dict)
                and set(lineage)
                == {"collection_path", "plan_sha256", "summary_sha256", "copied_attempts"},
                "invalid recovery lineage",
            )
            _require(
                isinstance(lineage["collection_path"], str) and bool(lineage["collection_path"]),
                "invalid parent path",
            )
            _require(
                type(lineage["copied_attempts"]) is int and lineage["copied_attempts"] >= 0,
                "invalid recovered attempt count",
            )
            for key in ("plan_sha256", "summary_sha256"):
                _require(
                    isinstance(lineage[key], str)
                    and len(lineage[key]) == 64
                    and all(char in "0123456789abcdef" for char in lineage[key]),
                    "invalid parent hash",
                )
    config = ProviderConfig.from_dict(plan.get("config"))
    method = plan.get("method", DEFAULT_METHOD)
    validate_method(method)
    _require(plan.get("config_sha256") == fingerprint(plan["config"]), "config hash mismatch")
    _require(plan.get("episodes_sha256") == fingerprint(episodes), "episodes fingerprint mismatch")
    slots = [(episode, checkpoint) for episode in episodes for checkpoint in episode["checkpoints"]]
    identities = [_identifier(*slot) for slot in slots]
    _require(_same(plan.get("checkpoints"), identities), "checkpoint plan mismatch")
    expected_episodes = [
        {
            "episode_id": ep["episode_id"],
            "checkpoint_count": len(ep["checkpoints"]),
            **({"episode_sha256": fingerprint(ep)} if version == "provider_collection_v2" else {}),
        }
        for ep in episodes
    ]
    _require(_same(plan.get("episodes"), expected_episodes), "episode plan mismatch")
    for key in ("max_queries", "max_request_bytes", "max_reserved_output_tokens"):
        value = plan.get(key)
        _require(
            (key != "max_queries" and value is None) or (type(value) is int and value >= 0),
            "invalid " + key,
        )
    _require(summary.get("plan_sha256") == fingerprint(plan), "summary plan hash mismatch")
    _require(_same(summary.get("planned_checkpoints"), len(slots)), "planned denominator mismatch")
    _require(_same(summary.get("max_queries"), plan["max_queries"]), "budget mismatch")
    _require(
        summary.get("transport_kind") == plan.get("transport_kind"), "transport label mismatch"
    )
    for document in (plan, summary):
        for key in (
            "automatic_retry",
            "aggregate_token_cap_enforced",
            "monetary_cap_enforced",
            "eligible_for_llm_leaderboard",
        ):
            _require(document.get(key) is False, "unsupported claim: " + key)
    running = summary.get("status") == "running"
    _require("cost" in summary and summary["cost"] is None, "unverified monetary cost claim")
    if running:
        _require(
            summary.get("stop_error") is None and summary.get("stop_guard") is None,
            "running summary has stop reason",
        )
    _require(not running or allow_incomplete, "incomplete running collection")
    hashes = summary.get("artifact_sha256")
    if hashes is not None:
        _require(
            isinstance(hashes, dict) and set(hashes) == set(ARTIFACTS), "artifact manifest mismatch"
        )
        for name in ARTIFACTS:
            _require(file_hash(root / name) == hashes[name], "artifact hash mismatch: " + name)
    else:
        _require(running and allow_incomplete, "final collection requires artifact hashes")
    requests = read_jsonl(root / "requests.jsonl")
    outcomes = read_jsonl(root / "outcomes.jsonl")
    responses = read_jsonl(root / "responses.jsonl")
    _require(len(requests) <= min(len(slots), plan["max_queries"]), "attempt cap exceeded")
    if version == "provider_collection_v2" and plan["resume_from"] is not None:
        _require(
            plan["resume_from"]["copied_attempts"] <= len(requests),
            "recovery lineage exceeds attempts",
        )
    _require(len(outcomes) <= len(requests) <= len(outcomes) + 1, "nonsequential journal")
    pending = len(requests) > len(outcomes)
    _require(not pending or running, "final collection has in-flight request")
    client = ProviderClient(config)
    counters = _count_start(len(slots))
    snapshots = [copy.deepcopy(counters)]
    previous = None
    history = []
    last_episode = None
    response_index = 0
    verified_requests = []
    stop_error = None
    for index, row in enumerate(requests):
        episode, checkpoint = slots[index]
        identifiers = identities[index]
        if last_episode != episode["episode_id"]:
            previous, history = None, []
            last_episode = episode["episode_id"]
        public = render_request(
            episode, checkpoint["checkpoint_id"], previous, method=method, history=history
        )
        prepared = client.prepare(public)
        expected = {
            **identifiers,
            "attempt_number": index + 1,
            "public_request": public,
            "public_request_sha256": fingerprint(public),
            "prepared": prepared,
        }
        _require(_same(row, expected), "request/carrier/wire mismatch at attempt " + str(index + 1))
        _require(
            _guard(prepared, counters, plan, identifiers) is None,
            "journaled request violates guard",
        )
        verified_requests.append(expected)
        counters["attempts_started"] += 1
        counters["reserved_output_tokens"] += config.max_output_tokens
        counters["request_bytes_sent"] += len(prepared["raw_request"].encode("utf-8"))
        snapshots.append(copy.deepcopy(counters))
        if index >= len(outcomes):
            break
        outcome = outcomes[index]
        for key, value in {**identifiers, "request_sha256": prepared["request_sha256"]}.items():
            _require(outcome.get(key) == value, "outcome request binding mismatch")
        if outcome.get("status") == "provider_error":
            _require(index == len(requests) - 1, "continued after provider error")
            _require(
                set(outcome) == {*identifiers, "request_sha256", "status", "error", "state_after"},
                "error outcome shape",
            )
            error = outcome["error"]
            _require(
                isinstance(error, dict)
                and set(error)
                == {"code", "status", "request_may_have_reached_provider", "automatic_retry"},
                "invalid provider error",
            )
            _require(
                isinstance(error["code"], str)
                and bool(error["code"])
                and error["automatic_retry"] is False
                and type(error["request_may_have_reached_provider"]) is bool,
                "invalid provider error values",
            )
            _require(
                error["status"] is None
                or (type(error["status"]) is int and 100 <= error["status"] <= 599),
                "invalid provider error HTTP status",
            )
            _require(_same(outcome["state_after"], previous), "error changed carrier")
            stop_error = error
            continue
        _require(
            set(outcome)
            == {
                *identifiers,
                "request_sha256",
                "raw_response_sha256",
                "metadata",
                "metadata_sha256",
                "status",
                "state_after",
            },
            "completion outcome shape",
        )
        _require(response_index < len(responses), "missing response file row")
        response = responses[response_index]
        _require(
            set(response) == {*identifiers, "raw_response"}
            and all(response[key] == value for key, value in identifiers.items()),
            "response checkpoint binding mismatch",
        )
        raw = response["raw_response"]
        metadata = outcome["metadata"]
        _require(outcome["raw_response_sha256"] == fingerprint(raw), "raw response hash mismatch")
        _require(outcome["metadata_sha256"] == fingerprint(metadata), "metadata hash mismatch")
        validate_completion(raw, metadata, prepared, config)
        status = "accepted"
        try:
            parsed = parse_decision(raw)
        except (ValueError, TypeError, KeyError):
            status = "invalid"
        else:
            previous = parsed
            history.append(copy.deepcopy(parsed))
        _require(outcome["status"] == status, "decision validity mismatch")
        _require(_same(outcome["state_after"], previous), "actual response carrier mismatch")
        counters["completions_received"] += 1
        counters["accepted_decisions" if status == "accepted" else "invalid_decisions"] += 1
        counters["unsubmitted_checkpoints"] -= 1
        usage = metadata["usage"]
        if usage is None:
            counters["responses_missing_usage"] += 1
        else:
            counters["reported_prompt_tokens"] += usage["prompt_tokens"]
            counters["reported_completion_tokens"] += usage["completion_tokens"]
        response_index += 1
        snapshots.append(copy.deepcopy(counters))
    extra_responses = len(responses) - response_index
    _require(extra_responses == 0 or (pending and extra_responses == 1), "unbound extra responses")
    if extra_responses:
        orphan = responses[-1]
        _require(
            set(orphan) == {*identities[len(requests) - 1], "raw_response"}
            and isinstance(orphan["raw_response"], str)
            and all(orphan[key] == value for key, value in identities[len(requests) - 1].items()),
            "invalid in-flight response",
        )
    counter_keys = COUNTERS + (
        ("reserved_output_tokens", "request_bytes_sent")
        if version == "provider_collection_v2"
        else ()
    )
    observed_counts = {key: summary.get(key) for key in counter_keys}
    _require(
        all(type(value) is int and value >= 0 for value in observed_counts.values()),
        "invalid summary counters",
    )
    allowed = snapshots[-2:] if running else [counters]
    _require(
        any(_same(observed_counts, {key: row[key] for key in counter_keys}) for row in allowed),
        "summary counters inconsistent with journal",
    )
    if not running:
        expected_status = "completed"
        expected_guard = None
        if stop_error is not None:
            expected_status = "provider_error"
        elif len(requests) < len(slots):
            if len(requests) >= plan["max_queries"]:
                expected_status = "budget_exhausted"
            else:
                episode, checkpoint = slots[len(requests)]
                if last_episode != episode["episode_id"]:
                    previous, history = None, []
                prepared = client.prepare(
                    render_request(
                        episode,
                        checkpoint["checkpoint_id"],
                        previous,
                        method=method,
                        history=history,
                    )
                )
                guard = _guard(prepared, counters, plan, identities[len(requests)])
                _require(guard is not None, "unexplained early stop")
                expected_status, expected_guard = guard
        _require(summary.get("status") == expected_status, "final status mismatch")
        _require(_same(summary.get("stop_error"), stop_error), "stop error mismatch")
        _require(_same(summary.get("stop_guard"), expected_guard), "guard stop mismatch")
    return {
        "schema_version": "provider_collection_audit_v1",
        "valid": True,
        "status": summary["status"],
        "safe_to_resume": not pending and stop_error is None,
        "method": method,
        "config_sha256": plan["config_sha256"],
        "episodes_sha256": plan["episodes_sha256"],
        "counters": counters,
        "verified_requests": verified_requests,
        "verified_outcomes": copy.deepcopy(outcomes),
        "responses": responses[:response_index],
        "completed_checkpoints": response_index,
        "next_checkpoint_index": len(requests),
        "inflight_request": pending,
        "provider_authenticated": False,
        "interpretation": "Local semantic consistency only; provider identity and execution are not authenticated.",
    }
