"""Verify a selected V7 publication snapshot without omitted raw datasets."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    manifest = json.loads(
        (args.root / "publication/v7_overall_review_20260912/EXPORT_MANIFEST.json").read_text()
    )
    failures = []
    for row in manifest["files"]:
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe manifest path")
        path = args.root / relative
        if not path.is_file():
            failures.append({"path": row["path"], "reason": "missing"})
            continue
        data = path.read_bytes()
        if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            failures.append({"path": row["path"], "reason": "identity_mismatch"})
    print(json.dumps({
        "passed": not failures, "selected_files": len(manifest["files"]),
        "failures": failures, "scope": "Selected publication bytes only",
    }))
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
