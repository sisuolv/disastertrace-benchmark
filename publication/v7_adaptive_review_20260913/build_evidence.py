"""Preserve both completed executions and screen the selected publication bytes."""

import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from evidence_archive import build, digest, encoded, restore, sha, write

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BUNDLES = (
    "plans/v7_next_20260913_2",
    "plans/v7_followup_execution_20260913",
    "plans/v7_adaptive_execution_20260913",
)
SKIP = {"__pycache__", ".pytest_cache", ".ruff_cache"}
FORBIDDEN = {".git", ".venv", ".env", ".ssh", "credentials", "credentials.json",
             ".netrc", ".cdsapirc", ".adsapirc", ".ewdsapirc"}
PATTERNS = (
    rb"(?<![A-Za-z0-9_])sk-[A-Za-z0-9_-]{25,}",
    rb"eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}",
    rb"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----",
    rb"[?&](?:Signature|Key-Pair-Id)=",
    rb"(?im)^\s*[\"']?(?:key|api_key|access_token)[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_-]{25,}",
    rb"\bgh[pousr]_[A-Za-z0-9]{30,}",
    rb"\bgithub_pat_[A-Za-z0-9_]{30,}",
)


def screen(data, name, seen=None):
    if seen is None:
        seen = set()
    identity = sha(data)
    if identity in seen:
        return
    seen.add(identity)
    if any(re.search(pattern, data) for pattern in PATTERNS):
        raise ValueError("Potential credential in selected file: " + name)
    if data.startswith(b"PK\x03\x04"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for item in archive.infolist():
                path = Path(item.filename)
                if path.is_absolute() or ".." in path.parts or any(p in FORBIDDEN for p in path.parts):
                    raise ValueError("Forbidden nested archive path: " + name)
                if not item.is_dir():
                    screen(archive.read(item), name + "!" + item.filename, seen)


def verify_execution(relative):
    folder = REPO / relative
    path = folder / "FINAL_MANIFEST.json"
    record = json.loads(path.read_text())
    files = record["files"]
    rows = ([dict(info, path=name) for name, info in files.items()]
            if isinstance(files, dict) else files)
    for row in rows:
        original = folder / row["path"]
        if original.stat().st_size != row["bytes"] or digest(original) != row["sha256"]:
            raise ValueError("Completed execution changed: " + str(original))
    return {"path": str(path.relative_to(REPO)), "sha256": digest(path),
            "verified_files": len(rows)}


def main():
    preserved = [verify_execution(relative) for relative in BUNDLES[1:]]
    paths = set()
    for relative in (*BUNDLES,
                     "disastertrace-starter/src/disastertrace/monitoring_fixed_v1",
                     "disastertrace-starter/src/disastertrace/monitoring_v1"):
        for folder, directories, names in os.walk(REPO / relative):
            directories[:] = sorted(n for n in directories if n not in SKIP)
            for name in names:
                path = Path(folder) / name
                if path.is_symlink() or any(p in FORBIDDEN for p in path.parts):
                    raise ValueError("Forbidden publication path: " + str(path.relative_to(REPO)))
                paths.add(path)
    for name in ("IMPLEMENTATION_STATUS.md", "DECISIONS.md", "BLOCKERS.md"):
        paths.add(REPO / "disastertrace-starter" / name)
    paths.update((REPO / "disastertrace-starter/tests").glob("test_monitoring*.py"))
    inventory, seen = {}, set()
    for path in sorted(paths):
        data = path.read_bytes()
        screen(data, str(path.relative_to(REPO)), seen)
        inventory[os.path.relpath(path, REPO / "disastertrace-starter")] = sha(data)
    acceptance = {
        "scope": "byte preservation inventory; not scientific task admission",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": inventory, "credential_patterns_screened": True,
        "nested_zip_contents_screened": True, "preserved_execution_manifests": preserved,
    }
    acceptance["acceptance_id"] = sha(encoded(acceptance))
    write(HERE / "BYTE_INVENTORY.json", acceptance)
    bundle = HERE / "evidence/full_execution"
    result = build(REPO, [str((HERE / "BYTE_INVENTORY.json").relative_to(REPO))], bundle)
    checked = restore(bundle, verify_only=True)
    checked.update(
        files=len(result["files"]), source_bytes=result["source_bytes"],
        unique_bytes=result["unique_bytes"], archive_bytes=result["archive_bytes"],
        parts=len(result["parts"]), full_archive_content_reverified=True,
        manifest_sha256=digest(bundle / "manifest.json"),
        preserved_execution_manifests=preserved,
    )
    write(HERE / "ARCHIVE_VALIDATION.json", checked)
    print(json.dumps(checked, indent=2))


if __name__ == "__main__":
    main()
