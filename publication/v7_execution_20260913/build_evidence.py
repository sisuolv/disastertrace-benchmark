"""Seal this execution's complete material with the prior checked archive utility."""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PREVIOUS = HERE.parent / "v7_review_execution_20260912"
sys.path.insert(0, str(PREVIOUS))

from evidence_archive import build, digest, encoded, restore, sha, write

SKIP = {"__pycache__", ".pytest_cache", ".ruff_cache"}
PATTERNS = (
    rb"(?<![A-Za-z0-9_])sk-[A-Za-z0-9_-]{25,}",
    rb"eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}",
    rb"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----",
    rb"[?&](?:Signature|Key-Pair-Id)=",
    rb"(?im)^\s*[\"']?(?:key|api_key|access_token)[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_-]{25,}",
)


def main():
    paths = set()
    for relative in (
        "plans/v7_execution_20260913", "plans/v7_integrated_20260913",
        "disastertrace-starter/src/disastertrace/monitoring_fixed_v1",
    ):
        for folder, directories, names in os.walk(REPO / relative):
            directories[:] = sorted(n for n in directories if n not in SKIP)
            for name in names:
                path = Path(folder) / name
                if path.is_symlink() or any(p in {".git", ".venv", ".env", "credentials"} for p in path.parts):
                    raise ValueError("Forbidden publication path: " + str(path.relative_to(REPO)))
                paths.add(path)
    for name in ("IMPLEMENTATION_STATUS.md", "DECISIONS.md", "BLOCKERS.md"):
        paths.add(REPO / "disastertrace-starter" / name)
    bound = json.loads((REPO / "plans/v7_execution_20260913/DELIVERY_MANIFEST.json").read_text())
    for name, expected in bound["files"].items():
        if digest(REPO / name) != expected:
            raise ValueError("Completed delivery changed: " + name)
    inventory = {}
    for path in sorted(paths):
        data = path.read_bytes()
        if any(re.search(pattern, data) for pattern in PATTERNS):
            raise ValueError("Potential credential in selected file: " + str(path.relative_to(REPO)))
        relative = os.path.relpath(path, REPO / "disastertrace-starter")
        inventory[relative] = sha(data)
    acceptance = {
        "scope": "byte preservation inventory; not scientific task admission",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": inventory,
        "credential_patterns_screened": True,
        "execution_manifest_sha256": digest(REPO / "plans/v7_execution_20260913/DELIVERY_MANIFEST.json"),
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
    )
    write(HERE / "ARCHIVE_VALIDATION.json", checked)
    print(json.dumps(checked, indent=2))


if __name__ == "__main__":
    main()
