"""Append-only local journal for controlled provider runs.

The journal records registration and dispatch intent before transport.  It is
deliberately provider agnostic: an uncertain transport is a terminal attempt
state and is never retried by this module.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


_SENSITIVE_KEY = re.compile(r"(?:api[_-]?key|authorization|bearer|(?:^|[_-])token(?:$|[_-])|secret|password|credential)", re.I)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_safe(value: Any, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _SENSITIVE_KEY.search(str(key)):
                raise ValueError(f"Sensitive field is not permitted in journal: {path}.{key}")
            _check_safe(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _check_safe(item, f"{path}[{index}]")
    elif isinstance(value, str) and _SENSITIVE_KEY.search(value):
        raise ValueError("Credential-like text is not permitted in journal payload")


class RunJournal:
    """Create a new run directory and persist every local state transition."""

    def __init__(self, path: str | os.PathLike[str], *, run_id: str, scope: str, config: Mapping[str, Any]):
        self.path = Path(path)
        if not isinstance(run_id, str) or not run_id.strip() or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}", run_id):
            raise ValueError("run_id must be a stable nonempty identifier")
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("run scope is required")
        _check_safe(config)
        self.path.mkdir(parents=True, exist_ok=False)
        self.run_id = run_id
        self.registration = {
            "schema": "disastertrace.v18.run_journal.v1",
            "run_id": run_id,
            "scope": scope,
            "config": json.loads(json.dumps(dict(config), allow_nan=False)),
            "registered_at": _utc(),
            "status": "OPEN",
        }
        self._write_exclusive("registration.json", self.registration)
        self._append("REGISTERED", {"run_id": run_id, "scope": scope})

    @classmethod
    def open_existing(cls, path: str | os.PathLike[str]) -> "RunJournal":
        root = Path(path)
        registration = json.loads((root / "registration.json").read_text(encoding="utf-8"))
        obj = object.__new__(cls)
        obj.path, obj.run_id, obj.registration = root, registration["run_id"], registration
        return obj

    def _write_exclusive(self, name: str, value: Mapping[str, Any]) -> None:
        _check_safe(value)
        target = self.path / name
        with target.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _append(self, event: str, payload: Mapping[str, Any]) -> None:
        _check_safe(payload)
        row = {"event": event, "at": _utc(), **dict(payload)}
        target = self.path / "events.jsonl"
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def is_closed(self) -> bool:
        return (self.path / "CLOSED.json").exists()

    def dispatch(self, *, request_id: str, request_sha256: str, model: str, settings: Mapping[str, Any]) -> None:
        if self.is_closed():
            raise ValueError("Cannot dispatch a CLOSED run")
        if not isinstance(request_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", request_sha256):
            raise ValueError("request_sha256 must be a SHA-256 hex digest")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("requested model is required")
        _check_safe(settings)
        self._append("DISPATCH_INTENT", {
            "request_id": request_id,
            "request_sha256": request_sha256,
            "requested_model": model,
            "settings": dict(settings),
        })

    def response(self, *, request_id: str, http_status: int | None, provider_model: str | None,
                 provider_request_id: str | None, response_sha256: str, parse_status: str) -> None:
        if not isinstance(response_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", response_sha256):
            raise ValueError("response_sha256 must be a SHA-256 hex digest")
        self._append("RESPONSE_RECEIVED", {
            "request_id": request_id,
            "http_status": http_status,
            "provider_model": provider_model,
            "provider_request_id": provider_request_id,
            "response_sha256": response_sha256,
            "parse_status": parse_status,
        })

    def close(self, *, reason: str = "completed") -> None:
        if self.is_closed():
            raise ValueError("Run is already CLOSED")
        marker = {"schema": "disastertrace.v18.run_journal.closed.v1", "run_id": self.run_id,
                  "reason": reason, "closed_at": _utc(), "status": "CLOSED"}
        self._write_exclusive("CLOSED.json", marker)
        self._append("CLOSED", {"reason": reason})
