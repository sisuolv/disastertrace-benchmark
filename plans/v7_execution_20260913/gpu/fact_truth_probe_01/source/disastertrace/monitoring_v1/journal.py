"""Fsynced, hash-chained receipts with explicit non-destructive tail recovery."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .targets import canonical_hash


@dataclass(frozen=True)
class JournalRead:
    records: tuple[dict, ...]
    incomplete_tail: bytes
    complete_prefix: bytes


def read_journal(path):
    raw = Path(path).read_bytes() if Path(path).exists() else b""
    last_newline = raw.rfind(b"\n")
    prefix, tail = raw[: last_newline + 1], raw[last_newline + 1 :]
    rows, previous, ids = [], "0" * 64, set()
    for line in prefix.splitlines():
        record = json.loads(line)
        signed = {k: record[k] for k in ("sequence", "event_id", "previous_sha256", "payload")}
        if (
            record["sequence"] != len(rows)
            or record["previous_sha256"] != previous
            or record["sha256"] != canonical_hash(signed)
            or record["event_id"] in ids
        ):
            raise ValueError("Journal hash/sequence/identity verification failed")
        previous = record["sha256"]
        ids.add(record["event_id"])
        rows.append(record)
    return JournalRead(tuple(rows), tail, prefix)


class EventJournal:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+b")
        try:
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            replay = read_journal(self.path)
            if replay.incomplete_tail:
                raise ValueError("Journal has a partial tail; recover to a fresh path")
            self.records = list(replay.records)
            self.by_id = {r["event_id"]: r for r in self.records}
        except BaseException:
            self.stream.close()
            raise

    def append(self, event_id, payload):
        if not event_id:
            raise ValueError("Event identity required")
        frozen = json.loads(json.dumps(payload, sort_keys=True, allow_nan=False))
        if event_id in self.by_id:
            old = self.by_id[event_id]
            if old["payload"] != frozen:
                raise ValueError("Conflicting idempotency replay")
            return old["sha256"]
        record = {
            "sequence": len(self.records),
            "event_id": event_id,
            "payload": frozen,
            "previous_sha256": self.records[-1]["sha256"] if self.records else "0" * 64,
        }
        record["sha256"] = canonical_hash(record)
        self.stream.write((json.dumps(record, sort_keys=True, allow_nan=False) + "\n").encode())
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.records.append(record)
        self.by_id[event_id] = record
        return record["sha256"]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stream.close()


def recover_prefix(original, destination):
    original, destination = Path(original), Path(destination)
    # The old file is never truncated, so the failed completion remains auditable.
    with original.open("rb") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        replay = read_journal(original)
        with destination.open("xb") as recovered:
            recovered.write(replay.complete_prefix)
            recovered.flush()
            os.fsync(recovered.fileno())
    receipt = {
        "source": str(original),
        "destination": str(destination),
        "complete_records": len(replay.records),
        "incomplete_tail_bytes": len(replay.incomplete_tail),
        "incomplete_tail_sha256": hashlib.sha256(replay.incomplete_tail).hexdigest(),
        "prefix_sha256": hashlib.sha256(replay.complete_prefix).hexdigest(),
    }
    destination.with_suffix(destination.suffix + ".recovery.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )
    return receipt
