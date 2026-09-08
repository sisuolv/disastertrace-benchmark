from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json(text: str) -> Any:
    def reject(value: str) -> None:
        raise ValueError(f"non-finite JSON number: {value}")

    return json.loads(text, object_pairs_hook=_unique_pairs, parse_constant=reject)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        row = strict_json(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{number}: expected a JSON object")
        rows.append(row)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(canonical(row) + "\n")


def safe_child(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute():
        raise ValueError("manifest path must be relative")
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError("manifest path escapes its root")
    return candidate
