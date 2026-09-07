"""Run the authorized ten-checkpoint Ida development sample, without saving a key."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import time
from pathlib import Path

from disastertrace.automated.model_workflow import collect_from_build


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("choose a new output directory")
    existing = os.environ.get("DEEPSEEK_API_KEY")
    credential = existing or getpass.getpass("DeepSeek API key (not saved): ")
    if not credential:
        parser.error("credential required")
    os.environ["DEEPSEEK_API_KEY"] = credential
    start = time.monotonic()
    try:
        result = collect_from_build(
            args.build,
            args.config,
            args.output,
            split="development",
            group_ids=["AL092021"],
            method="structured_state",
            max_queries=10,
            max_request_bytes=262144,
            max_reserved_output_tokens=40960,
        )
    finally:
        if existing is None:
            os.environ.pop("DEEPSEEK_API_KEY", None)
    collection = result["collection"]
    print(
        json.dumps(
            {
                "status": collection["status"],
                "elapsed_seconds": round(time.monotonic() - start, 3),
                "attempts_started": collection["attempts_started"],
                "completions_received": collection["completions_received"],
                "reported_prompt_tokens": collection["reported_prompt_tokens"],
                "reported_completion_tokens": collection["reported_completion_tokens"],
                "responses_missing_usage": collection["responses_missing_usage"],
                "metrics": result["metrics"],
            },
            indent=2,
        )
    )
    return 0 if collection["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
