"""Run the explicitly bounded v18 Y-free controlled pilot.

The API key is read from stdin once and is never written to an artifact. Raw
model responses are retained because malformed and transport failures are part
of the fixed denominator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from disastertrace.monitoring_v1.agent_view_v18 import public_checkpoint, public_prefix


ENDPOINT = "https://api.siliconflow.cn/v1/chat/completions"
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V4-Flash"
# Keep the historical name available to callers that import this script, while
# making the requested model an explicit run-level value below.
MODEL = DEFAULT_MODEL
# Same-complete-prefix Raw arm: the whole legitimate evidence history at the
# checkpoint cutoff, no carried model state and no retrieval.  The first three
# arms keep their original single-snapshot payloads.
FULL_PREFIX_ARM = "FULL_PREFIX_TRANSCRIPT"
ARMS = ("TRULY_FRESH", "PRIOR_P_ONLY", "PRIOR_P_FACT", FULL_PREFIX_ARM)
# The fixed decision grid of scripts/build_v18_dev_episodes.py
# (CHECKPOINT_OFFSETS_US), earliest first.  It is kept literal here so the
# runner does not import the archive reader; a test pins the two together.
CHECKPOINT_IDS = ("T-60", "T-40", "T-20")
# The availability labels public_checkpoint/public_prefix accept.
VISIBLE_AVAILABILITY = frozenset({"available", "known"})
# Mirrors scripts/build_v18_dev_episodes.py's CHECKPOINT_OFFSETS_US so this
# module does not need to import the archive reader; a test pins the two
# together. Used only to verify a roster's own declared cutoffs actually
# match what their checkpoint_id claims -- require_complete_roster previously
# checked the labels and the ordering but never that "T-60" really sits 60
# minutes before target_start, so a mislabeled or tampered roster (not
# producible by build_roster itself, but not excluded either) would have
# been silently accepted and dispatched under the wrong label.
CHECKPOINT_OFFSETS_US = {"T-60": 3_600_000_000, "T-40": 2_400_000_000, "T-20": 1_200_000_000}


def _is_timestamp(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_visible_availability(value: Any) -> bool:
    # A bare `value in VISIBLE_AVAILABILITY` raises TypeError for an
    # unhashable value instead of just being false.
    return isinstance(value, str) and value in VISIBLE_AVAILABILITY


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def parse_output(content: str | None) -> tuple[dict | None, str]:
    if not isinstance(content, str) or not content.strip():
        return None, "empty"
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None, "not_json"
    if not isinstance(value, dict) or set(value) != {"risk_probability", "target_state", "next_action"}:
        return None, "schema"
    p = value["risk_probability"]
    if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1:
        return None, "probability"
    state = value["target_state"]
    if not isinstance(state, dict) or set(state) != {"visibility_m", "confidence"}:
        return None, "state_or_action"
    visibility_m = state["visibility_m"]
    confidence = state.get("confidence")
    next_action = value.get("next_action")
    if (
        isinstance(visibility_m, bool)
        or not isinstance(visibility_m, (int, float))
        or not math.isfinite(visibility_m)
        or not 0 <= visibility_m <= 100_000
        or not isinstance(confidence, str)
        or confidence not in {"low", "medium", "high", "unknown"}
        or not isinstance(next_action, str)
        or next_action not in {"UPDATE", "WAIT", "STOP"}
    ):
        return None, "state_or_action"
    return value, "valid"


def checkpoint_inputs(
    episode: Mapping[str, Any], checkpoint: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Adapt one ``episode["checkpoints"]`` entry to the agent-view inputs.

    ``public_checkpoint`` and ``public_prefix`` take an episode with a flat
    ``qualifications`` list, plus one qualification-shaped checkpoint whose
    ``witness["as_of"]`` is the cutoff.  Returns
    ``(episode_view, checkpoint_view)``:

    * ``episode_view`` has the target fields, this checkpoint's cutoff as
      ``as_of`` and this checkpoint's own qualification list.  So
      ``public_prefix`` never reads another checkpoint's rows, and its
      ``as_of`` fallback resolves to this cutoff.
    * ``checkpoint_view`` is a minimal synthetic checkpoint: this cutoff plus
      the latest record ``public_checkpoint`` itself would accept as visible
      (availability ``available``/``known`` and ``available_at`` not after
      the cutoff).  If nothing is visible yet it carries only the cutoff, and
      the current evidence is legitimately empty.

    A row qualified against a different cutoff means the roster was
    mis-assembled, so it is refused rather than silently dropped.  A row
    qualified with no cutoff at all (``as_of`` None, i.e. ``known``) is
    accepted, because both views judge its ``available_at`` against this
    cutoff.
    """

    if not isinstance(episode, Mapping) or not isinstance(checkpoint, Mapping):
        raise ValueError("episode and checkpoint mappings are required")
    cutoff = checkpoint.get("as_of")
    qualifications = checkpoint.get("qualifications")
    if not _is_timestamp(cutoff):
        raise ValueError("Checkpoint cutoff must be an integer timestamp")
    if not isinstance(qualifications, list):
        raise ValueError("Checkpoint qualifications must be a list")
    latest = None
    for entry in qualifications:
        witness = entry.get("witness") if isinstance(entry, Mapping) else None
        if not isinstance(witness, Mapping):
            raise ValueError("Every checkpoint qualification needs a witness")
        entry_cutoff = witness.get("as_of")
        if entry_cutoff is not None and not (_is_timestamp(entry_cutoff) and entry_cutoff == cutoff):
            raise ValueError("Checkpoint rows must be qualified at the checkpoint's own cutoff")
        available_at = witness.get("available_at")
        if (
            _is_visible_availability(entry.get("availability"))
            and _is_timestamp(available_at)
            and available_at <= cutoff
        ):
            latest = entry  # arrival order: the last match is the latest visible
    episode_view = {
        "episode_id": episode.get("episode_id"),
        "station": episode.get("station"),
        "target_start": episode.get("target_start"),
        "target_end": episode.get("target_end"),
        "as_of": cutoff,
        "qualifications": qualifications,
    }
    # availability None is not a visible label, so no evidence is rendered.
    checkpoint_view: dict[str, Any] = {"availability": None, "witness": {"as_of": cutoff}}
    if latest is not None:
        checkpoint_view = {
            "availability": latest["availability"],
            "witness": {
                "as_of": cutoff,
                "available_at": latest["witness"]["available_at"],
                "current_projection": latest["witness"].get("current_projection"),
            },
        }
    return episode_view, checkpoint_view


def require_complete_roster(episodes: list) -> None:
    """Refuse any roster that is not the complete T-60/T-40/T-20 grid.

    This runs before registration or dispatch, so a malformed roster costs no
    request.  Each checkpoint also goes through both public views once, so
    their validation cannot abort a run halfway through -- which requires
    episode_id to be checked here too, not discovered missing mid-loop later.

    Checking the checkpoint_id labels and their ordering is not enough: a
    roster could carry the right labels in the right order with cutoffs that
    do not actually correspond to those labels (e.g. a "T-60" checkpoint
    whose as_of sits 3 microseconds, not 60 minutes, before target_start).
    build_v18_dev_episodes.py's own build_roster() cannot produce this, but
    nothing upstream of this function guaranteed that, so it is checked here
    explicitly (adversarial-review finding).
    """

    episode_ids = [episode.get("episode_id") if isinstance(episode, Mapping) else None for episode in episodes]
    if any(not isinstance(episode_id, str) or not episode_id for episode_id in episode_ids):
        raise SystemExit("Every episode needs a nonempty episode_id")
    if len(set(episode_ids)) != len(episode_ids):
        raise SystemExit("Episode ids must be unique across the registered roster")
    for episode in episodes:
        checkpoints = episode.get("checkpoints") if isinstance(episode, Mapping) else None
        if (
            not isinstance(checkpoints, list)
            or not all(isinstance(checkpoint, Mapping) for checkpoint in checkpoints)
            or tuple(checkpoint.get("checkpoint_id") for checkpoint in checkpoints) != CHECKPOINT_IDS
        ):
            raise SystemExit("Every registered episode needs the complete three-checkpoint roster (T-60, T-40, T-20)")
        bounds = [checkpoint.get("as_of") for checkpoint in checkpoints] + [episode.get("target_start")]
        if not all(_is_timestamp(value) for value in bounds) or any(
            later <= earlier for earlier, later in zip(bounds, bounds[1:])
        ):
            raise SystemExit("Checkpoint cutoffs must strictly increase and precede target_start")
        target_start = episode.get("target_start")
        for checkpoint in checkpoints:
            checkpoint_id = checkpoint.get("checkpoint_id")
            declared_offset = CHECKPOINT_OFFSETS_US[checkpoint_id]
            if target_start - checkpoint["as_of"] != declared_offset:
                raise SystemExit(
                    f"Checkpoint {checkpoint_id!r} of {episode.get('episode_id')!r} is mislabeled: "
                    f"its as_of does not sit {declared_offset} us before target_start as its own "
                    "checkpoint_id claims"
                )
            try:
                public_prefix(*checkpoint_inputs(episode, checkpoint))
            except (ValueError, TypeError) as exc:
                raise SystemExit(
                    f"Invalid checkpoint {checkpoint_id} of {episode.get('episode_id')}: {exc}"
                ) from exc


def prompt_for(
    arm: str, episode: dict, checkpoint: dict, prior: dict | None
) -> list[dict[str, str]]:
    """Render one arm's messages from one checkpoint's public view.

    ``episode``/``checkpoint`` are the agent-view inputs (a flat
    ``qualifications`` list and a qualification-shaped checkpoint).  For a
    roster checkpoint, build them with ``checkpoint_inputs()``.
    """

    system = (
        "You are in a controlled weather-risk state-maintenance pilot. "
        "Use only the supplied target and evidence. Do not retrieve sources. "
        "Return exactly JSON with risk_probability, target_state, next_action. "
        "target_state MUST be a JSON object such as {\"visibility_m\": 4000, \"confidence\": \"medium\"}, never a string. "
        "risk_probability is a number in [0,1]; next_action is UPDATE, WAIT, or STOP."
    )
    view = public_checkpoint(episode, checkpoint)
    if "checkpoints" in episode or not isinstance(episode.get("qualifications"), (list, tuple)):
        # A roster episode keeps one qualification list per checkpoint.  Given
        # one directly, public_prefix would find no rows and send an empty
        # history with no error, and a single row would stand in for a
        # checkpoint again.
        raise ValueError("prompt_for needs one checkpoint's view; build it with checkpoint_inputs()")
    payload = {
        "arm": arm,
        "target": {
            "station": episode["station"],
            "target_start": view["target_start"],
            "target_end": view["target_end"],
            "proposition": "future routine report visibility below 5000 m",
        },
        "current_evidence": view["current_evidence"],
    }
    if arm == FULL_PREFIX_ARM:
        # The ordered history replaces the single snapshot; this arm never
        # carries prior model output (prior is ignored, as for TRULY_FRESH).
        del payload["current_evidence"]
        payload["evidence_history"] = public_prefix(episode, checkpoint)
        system += (
            " In this arm you receive the full legitimate evidence history so far: "
            "evidence_history lists, in arrival order, every evidence record available at this "
            "checkpoint's decision cutoff, not only the latest one. "
            "Timestamps use the same integer clock as target_start and target_end. "
            "Use only this supplied history; do not retrieve sources or call tools."
        )
    if arm in {"PRIOR_P_ONLY", "PRIOR_P_FACT"}:
        payload["previous_probability"] = None if prior is None else prior.get("risk_probability")
    if arm == "PRIOR_P_FACT":
        payload["previous_target_state"] = None if prior is None else prior.get("target_state")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, sort_keys=True, separators=(",", ":"))},
    ]


def call(
    key: str, messages: list[dict[str, str]], model: str, max_tokens: int, timeout: float
) -> tuple[int | None, dict | None, str | None]:
    body = json.dumps(
        {"model": model, "messages": messages, "temperature": 0.0, "max_tokens": max_tokens, "stream": False}
    )
    try:
        request = Request(
            ENDPOINT,
            data=body.encode("utf-8"),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            raw = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        # HTTP failures are retained as failures; an error body is never
        # treated as a valid completion merely because it contains choices.
        status = int(exc.code)
        raw = exc.read().decode("utf-8", errors="replace")
    except (URLError, TimeoutError, OSError) as exc:
        return None, None, type(exc).__name__
    except Exception as exc:  # preserve transport failure without retry
        return None, None, type(exc).__name__
    try:
        return status, json.loads(raw), raw
    except json.JSONDecodeError:
        return status, None, raw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-episodes", type=int, default=12)
    # len(CHECKPOINT_IDS) checkpoints x len(ARMS) per episode.  This is derived,
    # not a magic number, so a later change to either count cannot leave the
    # default below what a full default-sized run needs.  That happened when
    # the arm count grew from 3 to 4 and the hardcoded 72 fell short.
    parser.add_argument("--max-calls", type=int, default=12 * len(CHECKPOINT_IDS) * len(ARMS))
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--run-id", default="v18-controlled-yfree-deepseek-v4-flash-20260922")
    args = parser.parse_args()
    default_run_id = "v18-controlled-yfree-deepseek-v4-flash-20260922"
    if args.model != DEFAULT_MODEL and args.run_id == default_run_id:
        raise SystemExit("A non-default model requires a new explicit --run-id")
    # Refuse reuse/overwrite before consuming credentials or dispatching any
    # request.  A prior CLOSED artifact is immutable evidence, not a cache.
    if args.out.exists():
        try:
            existing = json.loads(args.out.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            existing = None
        if isinstance(existing, dict) and existing.get("status") == "CLOSED":
            raise SystemExit("Refusing to dispatch a CLOSED run artifact")
        raise SystemExit("Refusing to overwrite an existing run artifact")
    sidecars = (
        args.out.with_name(args.out.name + ".registration.json"),
        args.out.with_name(args.out.name + ".dispatch.jsonl"),
        args.out.with_name(args.out.name + ".responses.jsonl"),
    )
    if any(path.exists() for path in sidecars):
        raise SystemExit("Refusing to reuse an existing run journal")
    key = sys.stdin.readline().strip()
    if not key:
        raise SystemExit("API key must be provided on stdin")
    source = json.loads(args.episodes.read_text(encoding="utf-8"))
    episodes = source["episodes"][: args.max_episodes]
    require_complete_roster(episodes)
    expected = len(episodes) * len(CHECKPOINT_IDS) * len(ARMS)
    if expected > args.max_calls:
        raise SystemExit(f"registered calls {expected} exceed max-calls {args.max_calls}")
    started = datetime.now(timezone.utc).isoformat()
    attempts = []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    registration_path = args.out.with_name(args.out.name + ".registration.json")
    dispatch_path = args.out.with_name(args.out.name + ".dispatch.jsonl")
    response_path = args.out.with_name(args.out.name + ".responses.jsonl")
    registration = {
        "schema": "disastertrace.v18.run_registration.v1",
        "run_id": args.run_id,
        "model": args.model,
        "episodes": len(episodes),
        "checkpoints": len(episodes) * len(CHECKPOINT_IDS),
        "checkpoint_ids": list(CHECKPOINT_IDS),
        "attempts": expected,
        "max_tokens": args.max_tokens,
        "timeout": args.timeout,
        "retry_policy": "none",
        "registered_at": started,
    }
    try:
        with registration_path.open("x", encoding="utf-8") as registration_file:
            registration_file.write(json.dumps(registration, indent=2) + "\n")
            registration_file.flush()
    except FileExistsError as exc:
        raise SystemExit("Refusing to reuse an existing run journal") from exc
    valid_by_arm = {arm: 0 for arm in ARMS}
    for episode in episodes:
        prior_by_arm = {arm: None for arm in ARMS}
        # Checkpoints run in T-60, T-40, T-20 order (enforced above), so each
        # PRIOR arm carries its latest valid output forward in time.
        for checkpoint_index, checkpoint in enumerate(episode["checkpoints"]):
            episode_view, checkpoint_view = checkpoint_inputs(episode, checkpoint)
            for arm in ARMS:
                messages = prompt_for(arm, episode_view, checkpoint_view, prior_by_arm[arm])
                request_id = f"{episode['episode_id']}::{checkpoint_index}::{arm}"
                dispatch = {
                    "request_id": request_id,
                    "run_id": args.run_id,
                    "dispatched_at": datetime.now(timezone.utc).isoformat(),
                    "requested_model": args.model,
                    "max_tokens": args.max_tokens,
                    "request_sha256": digest({
                        "messages": messages,
                        "model": args.model,
                        "temperature": 0.0,
                        "max_tokens": args.max_tokens,
                        "stream": False,
                        "endpoint": ENDPOINT,
                    }),
                }
                with dispatch_path.open("a", encoding="utf-8") as journal:
                    journal.write(json.dumps(dispatch, sort_keys=True) + "\n")
                    journal.flush()
                status, response, raw = call(key, messages, args.model, args.max_tokens, args.timeout)
                content = None
                usage = None
                provider_model = None
                provider_request_id = None
                finish_reason = None
                response_is_object = isinstance(response, dict)
                if response_is_object:
                    provider_model = response.get("model")
                    provider_request_id = response.get("id")
                    choices = response.get("choices")
                    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                        finish_reason = choices[0].get("finish_reason")
                        message = choices[0].get("message")
                        if isinstance(message, dict):
                            content = message.get("content")
                    usage = response.get("usage")
                if status is None:
                    parsed, parse_status = None, "transport_error"
                elif status != 200:
                    parsed, parse_status = None, "http_error"
                elif response is None:
                    parsed, parse_status = None, "response_not_json"
                elif not response_is_object:
                    parsed, parse_status = None, "response_not_object"
                elif provider_model != args.model:
                    parsed, parse_status = None, "model_mismatch" if provider_model else "model_missing"
                else:
                    parsed, parse_status = parse_output(content)
                if parsed is not None:
                    valid_by_arm[arm] += 1
                    prior_by_arm[arm] = parsed
                attempts.append(
                    {
                        "attempt_id": len(attempts),
                        "request_id": request_id,
                        "episode_id": episode["episode_id"],
                        "checkpoint_index": checkpoint_index,
                        "checkpoint_id": checkpoint["checkpoint_id"],
                        "arm": arm,
                        "requested_model": args.model,
                        "model": args.model,
                        "provider_model": provider_model,
                        "provider_request_id": provider_request_id,
                        "finish_reason": finish_reason,
                        "model_identity_status": "matched" if provider_model == args.model else "mismatch_or_missing",
                        "http_status": status,
                        "parse_status": parse_status,
                        "request_sha256": dispatch["request_sha256"],
                        "response_sha256": digest(raw),
                        "response_content": content,
                        "usage": usage,
                    }
                )
                with response_path.open("a", encoding="utf-8") as journal:
                    journal.write(json.dumps({
                        "request_id": request_id,
                        "received_at": datetime.now(timezone.utc).isoformat(),
                        "http_status": status,
                        "provider_model": provider_model,
                        "provider_request_id": provider_request_id,
                        "finish_reason": finish_reason,
                        "parse_status": parse_status,
                        "response_sha256": digest(raw),
                    }, sort_keys=True) + "\n")
                    journal.flush()
    payload = {
        "schema": "disastertrace.v18.controlled_api_pilot.v3",
        "run_id": args.run_id,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "model_identity_contract": "provider response model must equal requested model; HTTP 200 required",
        "endpoint": ENDPOINT,
        "registered_episodes": len(episodes),
        "registered_checkpoints": len(episodes) * len(CHECKPOINT_IDS),
        "checkpoint_ids": list(CHECKPOINT_IDS),
        "registered_attempts": expected,
        "actual_attempts": len(attempts),
        "max_tokens": args.max_tokens,
        "retry_policy": "none",
        "outcomes_accessed": False,
        "raw_weather_accessed": False,
        "holdout_accessed": False,
        "valid_by_arm": valid_by_arm,
        "attempts": attempts,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "attempts": len(attempts), "valid_by_arm": valid_by_arm, "out": str(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
