"""Verify selected review files, the reading ZIP, and optionally all evidence objects."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

HERE = Path("publication/v7_adaptive_review_20260913")
ZIP_NAME = "DisasterTrace_V7_Adaptive_Review_20260913.zip"


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def main(args):
    manifest_path = args.root / HERE / "EXPORT_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    failures, selected, names = [], [], set()
    for row in manifest["files"]:
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts or row["path"] in names:
            raise ValueError("Unsafe or duplicate selected path")
        names.add(row["path"])
        if args.scope == "reading" and not row["in_reading_zip"]:
            continue
        selected.append(row)
        path = args.root / relative
        if not path.is_file() or path.is_symlink():
            failures.append({"path": row["path"], "reason": "missing_or_not_regular"})
        elif path.stat().st_size != row["bytes"] or digest(path) != row["sha256"]:
            failures.append({"path": row["path"], "reason": "identity_mismatch"})
    archive_path = args.root / HERE / ZIP_NAME
    zip_checked = False
    if archive_path.exists():
        with zipfile.ZipFile(archive_path) as archive:
            expected = {r["path"]: r for r in manifest["files"] if r["in_reading_zip"]}
            manifest_name = str(HERE / "EXPORT_MANIFEST.json")
            if set(archive.namelist()) != set(expected) | {manifest_name} or len(archive.namelist()) != len(expected) + 1:
                raise ValueError("Reading ZIP file list differs")
            if archive.testzip() is not None or archive.read(manifest_name) != manifest_path.read_bytes():
                raise ValueError("Reading ZIP CRC or manifest mismatch")
            for name, row in expected.items():
                data = archive.read(name)
                if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
                    raise ValueError("Reading ZIP bytes differ: " + name)
        zip_checked = True
    elif args.scope == "full":
        failures.append({"path": str(HERE / ZIP_NAME), "reason": "missing_reading_archive"})
    checked_units = []
    if args.verify_evidence:
        from evidence_archive import restore

        index = json.loads((args.root / HERE / "EVIDENCE_INDEX.json").read_text())
        for unit in index["units"]:
            result = restore(args.root / unit["location"], verify_only=True)
            checked_units.append({"unit": unit["unit"], "result": result})
    result = {"passed": not failures, "scope": args.scope,
              "selected_files_checked": len(selected), "reading_zip_checked": zip_checked,
              "evidence_content_checks": checked_units, "failures": failures,
              "interpretation": "Selected payload identity only; scientific replay is a separate recorded check."}
    if args.receipt:
        with args.receipt.open("x") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "evidence_content_checks"}))
    return bool(failures)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--scope", choices=["full", "reading"], default="full")
    parser.add_argument("--verify-evidence", action="store_true")
    parser.add_argument("--receipt", type=Path)
    raise SystemExit(main(parser.parse_args()))
