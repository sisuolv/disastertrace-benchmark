"""Export browseable files and a reading ZIP alongside the full evidence archive."""

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

from build_evidence import PATTERNS
from evidence_archive import digest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PUBLICATION = HERE.relative_to(REPO)
BUNDLE = REPO / "plans/v7_execution_20260913"
ZIP_NAME = "DisasterTrace_V7_Latest_Review_20260913.zip"
TEXT = {".py", ".md", ".json", ".xml", ".log", ".txt", ".toml", ".sh"}
SKIP = {"__pycache__", ".pytest_cache", ".ruff_cache", "package_01", "raw"}


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    selected, omitted = {}, []

    def write(relative, data, reading=True):
        relative = Path(relative)
        if relative.is_absolute() or ".." in relative.parts or len(data) >= 100 * 1024**2:
            raise ValueError("Invalid export path/size: " + str(relative))
        if any(re.search(pattern, data) for pattern in PATTERNS):
            raise ValueError("Potential credential in export: " + str(relative))
        if relative.suffix == ".py":
            ast.parse(data.decode(), filename=str(relative))
        path = args.output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        selected[str(relative)] = {
            "path": str(relative), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "in_reading_zip": reading,
        }

    def add(path, reading=True):
        if path.is_symlink():
            raise ValueError("Symlink in export")
        write(path.relative_to(REPO), path.read_bytes(), reading)

    for directory in (BUNDLE, REPO / "plans/v7_integrated_20260913"):
        for folder, directories, names in os.walk(directory):
            directories[:] = sorted(n for n in directories if n not in SKIP)
            for name in sorted(names):
                path = Path(folder) / name
                relative = path.relative_to(directory)
                is_source = path.suffix in {".py", ".md"}
                is_large_data = any(
                    part in {"environment", "private", "captures", "responses", "policy"}
                    or part.startswith(("worker-", "full_captures_", "full_native_", "full_native_new_"))
                    for part in relative.parts[:-1]
                )
                if path.suffix not in TEXT or path.stat().st_size > 2 * 1024**2 or (is_large_data and not is_source):
                    omitted.append(str(path.relative_to(REPO)))
                    continue
                add(path)
    # Current-source tests use these exact fixed inputs; make a clone runnable
    # without requiring the larger raw-data archive to be expanded first.
    for path in sorted((BUNDLE / "evidence_bundle/matrix_01/policy").glob("*.json")):
        add(path, False)
    add(BUNDLE / "replay/DisasterTrace_V7_CPU_Replay_20260913.zip", False)
    add(BUNDLE / "replay/package_01/README_CN.md")
    # Older regression tests consume this real regional fixture, which was
    # previously available only through the older evidence archive.
    for path in sorted((REPO / "plans/v7_review_execution_20260912/regional_01").rglob("*.json")):
        add(path, False)
    package = REPO / "disastertrace-starter"
    for directory in (package / "src/disastertrace/monitoring_fixed_v1", package / "src/disastertrace/monitoring_v1"):
        for path in sorted(directory.rglob("*.py")):
            add(path)
    for path in sorted((package / "tests").glob("test_monitoring*.py")):
        add(path)
    for name in ("IMPLEMENTATION_STATUS.md", "DECISIONS.md", "BLOCKERS.md", "pyproject.toml"):
        add(package / name)
    for path in sorted(HERE.iterdir()):
        if path.is_file() and path.suffix in TEXT and path.name not in {
            "PUBLISH_RESULT.json", "EXPORT_MANIFEST.json", "TRACKED_STATUS_START.txt",
        }:
            add(path, path.stat().st_size < 2 * 1024**2)

    check = json.loads((HERE / "ARCHIVE_VALIDATION.json").read_text())
    if not check["full_archive_content_reverified"]:
        raise ValueError("Full evidence must be verified before export")
    unit = HERE / "evidence/full_execution"
    if digest(unit / "manifest.json") != check["manifest_sha256"]:
        raise ValueError("Full evidence manifest changed")
    for path in sorted(unit.iterdir()):
        add(path, False)
    write(PUBLICATION / "EVIDENCE_INDEX.json", (json.dumps({
        "units": [{"unit": "full_execution", "location": str(unit.relative_to(REPO)),
                   "files": check["files"], "archive_bytes": check["archive_bytes"],
                   "manifest_sha256": check["manifest_sha256"], "content_check": True}],
        "scope": "complete current execution and integrated plan, including failed records; no scientific admission implied",
    }, indent=2) + "\n").encode())
    write(PUBLICATION / "BROWSE_SCOPE.json", (json.dumps({
        "not_expanded_in_reading_tree": sorted(set(omitted) - set(selected)),
        "complete_execution_material": str(unit.relative_to(REPO)),
        "only_caches_omitted_from_full_execution": sorted(SKIP - {"package_01", "raw"}),
        "credentials_and_model_weights_included": False,
    }, indent=2) + "\n").encode())
    start = json.loads((HERE / "GIT_START.json").read_text())
    with tempfile.TemporaryDirectory(prefix="dt-v7-export-git-") as tmp:
        config = Path(tmp) / "gitconfig"
        config.write_text("[safe]\n\tdirectory = " + str(REPO) + "\n")
        env = dict(os.environ, GIT_CONFIG_GLOBAL=str(config), GIT_OPTIONAL_LOCKS="0")
        original = subprocess.run(
            ["git", "show", start["remote_base"] + ":README.md"], cwd=REPO, env=env,
            capture_output=True, timeout=60, check=True,
        ).stdout.decode()
    title, _, body = original.partition("\n")
    intro = (HERE / "README_INTRO_CN.md").read_text()
    write("README.md", (title + "\n\n" + intro + "\n\n" + body.lstrip("\n")).encode())
    write("LATEST_PROGRESS_20260913_CN.md", (
        "# 最新执行与发布入口\n\n" + intro
    ).encode())
    manifest = {
        "schema": "disastertrace.v7.fixed_execution_publication.v1",
        "base_commit": start["remote_base"],
        "files": sorted(selected.values(), key=lambda row: row["path"]),
        "file_count": len(selected), "bytes": sum(r["bytes"] for r in selected.values()),
        "real_index_and_HEAD_unchanged": True,
    }
    manifest_path = args.output / PUBLICATION / "EXPORT_MANIFEST.json"
    manifest_data = (json.dumps(manifest, indent=2) + "\n").encode()
    manifest_path.write_bytes(manifest_data)
    archive_path = args.output / PUBLICATION / ZIP_NAME
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for row in manifest["files"]:
            if row["in_reading_zip"]:
                archive.write(args.output / row["path"], row["path"])
        archive.writestr(str(PUBLICATION / "EXPORT_MANIFEST.json"), manifest_data)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Reading ZIP CRC failed")
        for row in manifest["files"]:
            if row["in_reading_zip"] and hashlib.sha256(archive.read(row["path"])).hexdigest() != row["sha256"]:
                raise ValueError("Reading ZIP content mismatch")
    print(json.dumps({"files": len(selected), "bytes": manifest["bytes"],
                      "reading_zip_bytes": archive_path.stat().st_size,
                      "full_evidence_archive_bytes": check["archive_bytes"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
