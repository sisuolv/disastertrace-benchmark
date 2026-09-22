"""Rebuild captured diagnostic records without dispatching another provider call."""

from __future__ import annotations

import json
from pathlib import Path

from disastertrace.revision_v1.pilot_v17.agent_view import NativeReader, public_view
from disastertrace.revision_v1.pilot_v17.commits import consume_response
from disastertrace.revision_v1.pilot_v17.provider import append_json, canonical, digest
from disastertrace.revision_v1.pilot_v17.qualification import readset_rows


def lines(path):
    path = Path(path)
    return [json.loads(line) for line in path.read_text().splitlines() if line] if path.exists() else []


def reconstruct(run):
    run = Path(run)
    episodes = {row["episode_id"]: row for row in lines(run / "episodes.jsonl")}
    main = {row["logical_id"]: row for row in lines(run / "main_steps.jsonl")}
    attempts = {row["logical_id"]: row for row in lines(run / "attempts.jsonl") if row["stage"] == "e2"}
    captures = {row["logical_id"]: row for row in lines(run / "responses.jsonl") if row["stage"] == "e2"}
    existing = {row["logical_id"] for row in lines(run / "paired_diagnostics.jsonl")}
    reader = NativeReader(json.loads((run / "protocol.json").read_text())["readset_path"])
    rebuilt = []
    for logical_id, capture in captures.items():
        if logical_id in existing:
            continue
        attempt = attempts[logical_id]
        metadata = attempt["metadata"]
        anchor = main[metadata["anchor_logical_id"]]
        view = public_view(episodes[metadata["episode_id"]], metadata["checkpoint_index"], reader)
        consumed = consume_response(capture, view, anchor["before"])
        record = {
            "logical_id": logical_id,
            "stage": "e2",
            "model": attempt["model"],
            "arm": metadata["arm"],
            "episode_id": metadata["episode_id"],
            "as_of": metadata["as_of"],
            "variant": metadata["variant"],
            "input_metadata": metadata,
            "request_sha256": attempt["request_sha256"],
            "capture_logical_id": logical_id,
            "first_http_status": capture.get("http_status"),
            "retry_logical_id": capture.get("retry_of"),
            "elapsed_including_queue_s": capture.get("latency_s"),
            "completed_at": capture.get("completed_at"),
            **consumed,
            "reconstructed_from_capture": True,
        }
        append_json(run / "paired_diagnostics.jsonl", record)
        rebuilt.append(record)
    missing = []
    for logical_id, attempt in attempts.items():
        if logical_id not in captures:
            missing.append({
                "logical_id": logical_id,
                "stage": "e2",
                "model": attempt["model"],
                "metadata": attempt["metadata"],
                "request_sha256": attempt["request_sha256"],
                "status": "ATTEMPT_WITHOUT_CAPTURE_PROVIDER_EXITED",
            })
    (run / "audit" / "e2_missing_attempts.jsonl").write_text(
        "".join(canonical(row) + "\n" for row in missing)
    )
    print(canonical({
        "captured_e2": len(captures),
        "rebuilt": len(rebuilt),
        "already_present": len(existing),
        "attempts_without_capture": len(missing),
        "diagnostics_total": len(existing) + len(rebuilt),
    }))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    reconstruct(parser.parse_args().run)
