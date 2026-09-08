"""Read-only progress view; only the final independent audit establishes results."""

import json
import os
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    manifest = json.loads((HERE / "launch_manifest.json").read_text())
    runtime = HERE / "runtime"
    process = json.loads((runtime / "process.json").read_text())
    try:
        os.kill(process["pid"], 0)
        stat = Path(f"/proc/{process['pid']}/stat").read_text()
        running = stat.rsplit(") ", 1)[1].split()[0] != "Z"
    except (ProcessLookupError, FileNotFoundError):
        running = False
    raw = (Path(manifest["run_output"]) / "journal.jsonl").read_bytes()
    lines = raw.splitlines()
    partial_tail = bool(raw) and not raw.endswith(b"\n")
    if partial_tail:
        lines = lines[:-1]
    events = [json.loads(line) for line in lines]
    kinds = Counter(row["kind"] for row in events)
    statuses = Counter(row["data"]["status"] for row in events if row["kind"] == "decision")
    settlements = [row["data"]["settlement"] for row in events if row["kind"] == "settled"]
    settled_ids = {row["attempt_id"] for row in settlements}
    outstanding = [
        row["data"]["reservation"]
        for row in events
        if row["kind"] == "reserved" and row["data"]["reservation"]["attempt_id"] not in settled_ids
    ]
    result = {
        "read_only_monitor": True,
        "independent_final_audit": False,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "pid": process["pid"],
        "worker_running": running,
        "started_at": process["started_at"],
        "execution_id": manifest["execution_id"],
        "planned": 270,
        "send_intents": kinds["send_intent"],
        "captures": kinds["capture"],
        "finalized": kinds["decision"],
        "schema_statuses": dict(statuses),
        "settled_conservative_usd": str(
            sum((Decimal(row["cost"]) for row in settlements), Decimal(0))
        ),
        "outstanding_reservation_usd": str(
            sum((Decimal(row["reservation"]) for row in outstanding), Decimal(0))
        ),
        "last_event": events[-1]["kind"] if events else None,
        "last_slot": events[-1]["data"].get("slot_index") if events else None,
        "partial_tail_ignored": partial_tail,
        "stop_reasons": [row["data"]["reason"] for row in events if row["kind"] == "halt"],
    }
    completion = runtime / "completion.json"
    if completion.exists():
        done = json.loads(completion.read_text())
        result["final_report"] = done.get("report")
        result["collection_error_type"] = done.get("collection_error_type")
        result["finalization_error_type"] = done.get("finalization_error_type")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
