#!/usr/bin/env python3
"""Validate a run specification without making network or data calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


SCOPES = {"CODE", "SOURCE", "PROVIDER", "OUTCOME", "PROSPECTIVE", "CONFIRMATION"}
SENSITIVE = re.compile(r"(?:api[_-]?key|authorization|bearer|(?:^|[_-])token(?:$|[_-])|secret|password|credential)", re.I)


def _walk(value: Any, path: str = "root"):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield path, str(key), item
            yield from _walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")


def validate(spec: Mapping[str, Any]) -> dict[str, Any]:
    if spec.get("schema") not in {"disastertrace.v18.run_spec.v1", "disastertrace.v19.run_spec.v1"}:
        raise ValueError("Unsupported run-spec schema")
    run_id = spec.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}", run_id):
        raise ValueError("run_id must be a stable unique identifier")
    if spec.get("status", "PLANNED") in {"CLOSED", "DISPATCHED"}:
        raise ValueError("A closed/dispatched run spec cannot be reused")
    scopes = spec.get("scopes", [spec.get("scope")] if spec.get("scope") else [])
    if not isinstance(scopes, list) or not scopes or any(scope not in SCOPES for scope in scopes):
        raise ValueError("scopes must explicitly name one or more allowed experiment scopes")
    permissions = spec.get("permissions", {})
    if not isinstance(permissions, Mapping):
        raise ValueError("permissions must be a mapping")
    for scope in scopes:
        if permissions.get(scope) is not True:
            raise ValueError(f"Explicit permission missing for scope {scope}")
    for path, key, value in _walk(spec):
        if SENSITIVE.search(key):
            raise ValueError(f"Sensitive key is forbidden at {path}.{key}")
        if isinstance(value, str) and SENSITIVE.search(value):
            raise ValueError("Credential-like text is forbidden in run specs")
        if isinstance(value, str) and any(part in value.split("/") for part in ("data_real_v16", "quarantine_holdout")):
            raise ValueError("Raw/holdout paths are not accepted by offline validation")
    canonical = json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {"valid": True, "run_id": run_id, "scopes": scopes, "spec_sha256": hashlib.sha256(canonical).hexdigest(),
            "external_calls": 0, "raw_weather_accessed": False, "outcomes_accessed": False, "holdout_accessed": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--offline", action="store_true", help="required; never performs external work")
    args = parser.parse_args()
    if not args.offline:
        parser.error("Only --offline validation is implemented")
    spec = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = validate(spec)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
