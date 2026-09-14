"""Deterministic, exclusive artifacts for the native forecast task."""

import hashlib
import json
import os
from pathlib import Path


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError("nonfinite JSON number: " + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)


def read(path):
    return strict_json(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def inventory(root, exclude=()):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("symlink in sealed package")
        name = path.relative_to(root).as_posix()
        if path.is_file() and "__pycache__" not in path.parts and name not in exclude:
            result[name] = digest(path)
    return result


def seal(root):
    result = {"schema_version": "forecast_task_package_v1", "files": inventory(root)}
    result["package_id"] = fingerprint(result)
    write(Path(root) / "manifest.json", result)
    return result


def verify(root):
    root = Path(root)
    record = read(root / "manifest.json")
    if record["package_id"] != fingerprint({k: v for k, v in record.items() if k != "package_id"}):
        raise ValueError("package identity mismatch")
    if record["files"] != inventory(root, ("manifest.json",)):
        raise ValueError("package inventory mismatch")
    return record
