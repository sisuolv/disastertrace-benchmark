"""Exclusive durable artifacts and deterministic content identities."""

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.automated.common import canonical, fingerprint, safe_child, strict_json


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read(path):
    return strict_json(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def inventory(root, *, exclude=()):
    root = Path(root)
    return {
        str(p.relative_to(root)): digest(p)
        for p in sorted(root.rglob("*"))
        if p.is_file() and str(p.relative_to(root)) not in exclude and "__pycache__" not in p.parts
    }


def seal(root):
    manifest = {"schema_version": "local_eval_manifest_v1", "files": inventory(root)}
    manifest["package_id"] = fingerprint(manifest)
    write(Path(root) / "manifest.json", manifest)
    return manifest


def verify_seal(root):
    root = Path(root)
    manifest = read(root / "manifest.json")
    if manifest["package_id"] != fingerprint(
        {k: v for k, v in manifest.items() if k != "package_id"}
    ):
        raise ValueError("package identity mismatch")
    if manifest["files"] != inventory(root, exclude=("manifest.json",)):
        raise ValueError("package content/inventory mismatch")
    for name in manifest["files"]:
        safe_child(root, name)
    return manifest
