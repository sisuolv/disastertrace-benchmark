"""One explicitly requested DeepSeek SDK probe; no retries or persisted credential."""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import openai
from openai import OpenAI


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("choose a new output directory to preserve prior attempts")
    credential = os.environ.get("DEEPSEEK_API_KEY") or getpass.getpass(
        "DeepSeek API key (not saved): "
    )
    if not credential or any(ord(char) < 33 or ord(char) > 126 for char in credential):
        parser.error("a nonempty printable API credential is required")
    logging.disable(logging.CRITICAL)
    arguments = {
        "model": "deepseek-v4-flash",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
        ],
        "stream": False,
        "max_tokens": 1024,
        "reasoning_effort": "high",
        "extra_body": {"thinking": {"type": "enabled"}},
    }
    args.output.mkdir(parents=True, exist_ok=False)

    def save(name: str, value: dict) -> None:
        serialized = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
        serialized = serialized.replace(credential, "[REDACTED]")
        serialized = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", serialized)
        (args.output / name).write_text(serialized + "\n", encoding="utf-8")

    record = {
        "schema_version": "deepseek_sdk_probe_v1",
        "purpose": "one_connectivity_probe_not_a_benchmark_score",
        "base_url": "https://api.deepseek.com",
        "credential_env": "DEEPSEEK_API_KEY",
        "credential_persisted": False,
        "sdk": "openai",
        "sdk_version": openai.__version__,
        "arguments": arguments,
        "automatic_retries": 0,
        "attempts": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "started",
        "reported_usage": None,
        "cost": None,
    }
    save("probe.json", record)
    started = time.monotonic()
    try:
        with OpenAI(
            api_key=credential, base_url=record["base_url"], max_retries=0, timeout=60
        ) as client:
            response = client.chat.completions.create(**arguments)
        data = response.model_dump(mode="json")
        save("response.json", data)
        record.update(
            status="completed",
            response_model=response.model,
            reported_usage=data.get("usage"),
            finish_reason=response.choices[0].finish_reason,
            answer=response.choices[0].message.content,
        )
    except openai.APIStatusError as exc:
        record.update(
            status="http_error",
            http_status=exc.status_code,
            error_type=type(exc).__name__,
            error_body=exc.body,
        )
    except (openai.APIConnectionError, openai.APITimeoutError) as exc:
        record.update(status="connection_error", error_type=type(exc).__name__)
    finally:
        record["elapsed_seconds"] = round(time.monotonic() - started, 3)
        save("probe.json", record)
    public = {key: record[key] for key in ("status", "elapsed_seconds", "reported_usage")}
    for key in ("http_status", "error_type", "response_model", "finish_reason", "answer"):
        if key in record:
            public[key] = record[key]
    print(json.dumps(public, ensure_ascii=False, indent=2).replace(credential, "[REDACTED]"))
    return 0 if record["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
