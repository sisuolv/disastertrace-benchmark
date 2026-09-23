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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ENDPOINT = "https://api.siliconflow.cn/v1/chat/completions"
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V4-Flash"
# Keep the historical name available to callers that import this script, while
# making the requested model an explicit run-level value below.
MODEL = DEFAULT_MODEL
ARMS = ("TRULY_FRESH", "PRIOR_P_ONLY", "PRIOR_P_FACT")


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
    if (
        isinstance(visibility_m, bool)
        or not isinstance(visibility_m, (int, float))
        or not math.isfinite(visibility_m)
        or not 0 <= visibility_m <= 100_000
        or state["confidence"] not in {"low", "medium", "high", "unknown"}
        or value["next_action"] not in {"UPDATE", "WAIT", "STOP"}
    ):
        return None, "state_or_action"
    return value, "valid"


def prompt_for(
    arm: str, episode: dict, checkpoint: dict, prior: dict | None
) -> list[dict[str, str]]:
    system = (
        "You are in a controlled weather-risk state-maintenance pilot. "
        "Use only the supplied target and evidence. Do not retrieve sources. "
        "Return exactly JSON with risk_probability, target_state, next_action. "
        "target_state MUST be a JSON object such as {\"visibility_m\": 4000, \"confidence\": \"medium\"}, never a string. "
        "risk_probability is a number in [0,1]; next_action is UPDATE, WAIT, or STOP."
    )
    payload = {
        "arm": arm,
        "target": {
            "station": episode["station"],
            "target_start": episode["target_start"],
            "target_end": episode["target_end"],
            "proposition": "future routine report visibility below 5000 m",
        },
        "current_evidence": checkpoint["witness"]["current_projection"],
        "source_qualification": checkpoint["status"],
    }
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
        result = subprocess.run(
            [
                "curl",
                "-sS",
                "--connect-timeout",
                str(min(5.0, timeout)),
                "--max-time",
                str(timeout),
                "-w",
                "\n__DISASTERTRACE_HTTP_STATUS__%{http_code}",
                "-X",
                "POST",
                ENDPOINT,
                "-H",
                f"Authorization: Bearer {key}",
                "-H",
                "Content-Type: application/json",
                "--data",
                body,
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
            check=False,
        )
        marker = "\n__DISASTERTRACE_HTTP_STATUS__"
        if marker not in result.stdout:
            return None, None, result.stderr.strip() or "transport_no_status"
        raw, status_text = result.stdout.rsplit(marker, 1)
        try:
            status = int(status_text.strip())
        except ValueError:
            return None, None, raw
        if result.returncode != 0:
            return status or None, None, raw
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
    parser.add_argument("--max-calls", type=int, default=72)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--run-id", default="v18-controlled-yfree-deepseek-v4-flash-20260922")
    args = parser.parse_args()
    default_run_id = "v18-controlled-yfree-deepseek-v4-flash-20260922"
    if args.model != DEFAULT_MODEL and args.run_id == default_run_id:
        raise SystemExit("A non-default model requires a new explicit --run-id")
    key = sys.stdin.readline().strip()
    if not key:
        raise SystemExit("API key must be provided on stdin")
    source = json.loads(args.episodes.read_text(encoding="utf-8"))
    episodes = source["episodes"][: args.max_episodes]
    expected = len(episodes) * 2 * len(ARMS)
    if expected > args.max_calls:
        raise SystemExit(f"registered calls {expected} exceed max-calls {args.max_calls}")
    started = datetime.now(timezone.utc).isoformat()
    attempts = []
    valid_by_arm = {arm: 0 for arm in ARMS}
    for episode in episodes:
        prior_by_arm = {arm: None for arm in ARMS}
        for checkpoint_index, checkpoint in enumerate(episode["qualifications"][:2]):
            for arm in ARMS:
                messages = prompt_for(arm, episode, checkpoint, prior_by_arm[arm])
                request_id = f"{episode['episode_id']}::{checkpoint_index}::{arm}"
                status, response, raw = call(key, messages, args.model, args.max_tokens, args.timeout)
                content = None
                usage = None
                provider_model = None
                provider_request_id = None
                response_is_object = isinstance(response, dict)
                if response_is_object:
                    provider_model = response.get("model")
                    provider_request_id = response.get("id")
                    choices = response.get("choices")
                    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                        message = choices[0].get("message") or {}
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
                        "arm": arm,
                        "requested_model": args.model,
                        "model": args.model,
                        "provider_model": provider_model,
                        "provider_request_id": provider_request_id,
                        "model_identity_status": "matched" if provider_model == args.model else "mismatch_or_missing",
                        "http_status": status,
                        "parse_status": parse_status,
                        "request_sha256": digest(messages),
                        "response_sha256": digest(raw),
                        "response_content": content,
                        "usage": usage,
                    }
                )
    payload = {
        "schema": "disastertrace.v18.controlled_api_pilot.v2",
        "run_id": args.run_id,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "model_identity_contract": "provider response model must equal requested model; HTTP 200 required",
        "endpoint": ENDPOINT,
        "registered_episodes": len(episodes),
        "registered_checkpoints": len(episodes) * 2,
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
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "attempts": len(attempts), "valid_by_arm": valid_by_arm, "out": str(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
