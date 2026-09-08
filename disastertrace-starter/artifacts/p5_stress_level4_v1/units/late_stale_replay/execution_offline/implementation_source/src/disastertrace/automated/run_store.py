"""Single-host durable journal and experiment claim on the deployment filesystem."""

import fcntl
import os
import re
from pathlib import Path

from .common import canonical, fingerprint, strict_json


def sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def durable_json(path: Path, value: dict) -> None:
    path = Path(path)
    temporary = path.with_name(path.name + ".writing")
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(canonical(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def read_events(output: Path) -> list[dict]:
    path = Path(output) / "journal.jsonl"
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("incomplete journal tail; offline inspection only")
    rows, previous = [], None
    for line in raw.splitlines():
        row = strict_json(line.decode("utf-8"))
        if not isinstance(row, dict) or set(row) != {"seq", "prev", "kind", "data", "hash"}:
            raise ValueError("invalid journal row")
        unsigned = {k: v for k, v in row.items() if k != "hash"}
        if (
            type(row["seq"]) is not int
            or row["seq"] != len(rows)
            or row["prev"] != previous
            or fingerprint(unsigned) != row["hash"]
        ):
            raise ValueError("journal hash chain mismatch")
        rows.append(row)
        previous = row["hash"]
    return rows


class RunStore:
    def __init__(self, output: Path, execution_id: str, registry: Path, *, resume=False):
        if re.fullmatch("[0-9a-f]{64}", execution_id) is None:
            raise ValueError("invalid execution identity")
        self.output = Path(output).resolve()
        self.registry = Path(registry).resolve()
        self.execution_id = execution_id
        self.resume = resume
        self.lock = None
        self.acquired = False

    def __enter__(self):
        self.registry.mkdir(parents=True, exist_ok=True)
        self.lock = (self.registry / (self.execution_id + ".lock")).open("a+b")
        try:
            try:
                fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.acquired = True
            except BlockingIOError:
                raise ValueError("experiment already has a writer") from None
            claim_path = self.registry / (self.execution_id + ".json")
            claim = {"execution_id": self.execution_id, "output": str(self.output)}
            if claim_path.exists():
                if not self.resume or strict_json(claim_path.read_text()) != claim:
                    raise ValueError("experiment claim cannot be reused with a new output")
                read_events(self.output)
            else:
                if self.resume or self.output.exists():
                    raise ValueError("fresh output required for initial claim")
                self.output.mkdir(parents=True)
                with (self.output / "journal.jsonl").open("xb") as stream:
                    stream.flush()
                    os.fsync(stream.fileno())
                durable_json(claim_path, claim)
                sync_directory(self.output)
            self.events = read_events(self.output)
            self.journal_size = (self.output / "journal.jsonl").stat().st_size
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def append(self, kind: str, data: dict) -> dict:
        if self.lock is None or self.lock.closed:
            raise ValueError("writer lock required")
        if (self.output / "journal.jsonl").stat().st_size != self.journal_size:
            raise ValueError("journal changed outside this writer")
        rows = self.events
        unsigned = {
            "seq": len(rows),
            "prev": rows[-1]["hash"] if rows else None,
            "kind": kind,
            "data": data,
        }
        row = {**unsigned, "hash": fingerprint(unsigned)}
        with (self.output / "journal.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(canonical(row) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.events.append(row)
        self.journal_size = (self.output / "journal.jsonl").stat().st_size
        return row

    def __exit__(self, *_):
        if self.lock is not None and not self.lock.closed:
            try:
                if self.acquired:
                    fcntl.flock(self.lock.fileno(), fcntl.LOCK_UN)
            finally:
                self.acquired = False
                self.lock.close()
