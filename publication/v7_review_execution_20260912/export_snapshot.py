"""Publish selected v7 code and checked evidence without touching the worktree index."""

from __future__ import annotations

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

from build_evidence import BUNDLE, HERE, REPO, SECRET_PATTERNS

PUBLICATION = HERE.relative_to(REPO)
ZIP_NAME = "DisasterTrace_v7_Implementation_Review_20260913.zip"
TEXT = {".py", ".md", ".json", ".xml", ".log", ".txt", ".toml", ".sh"}
IGNORE = {"__pycache__", ".pytest_cache", ".ruff_cache"}
EXCLUDED_NAMES = {"ROWS.json", "ACCOUNT_GPU_1829.json", "submission.lock"}


def screen(path, data):
    patterns = (rb"(?<![A-Za-z0-9_])sk-[A-Za-z0-9_-]{25,}", *SECRET_PATTERNS[1:])
    if any(re.search(pattern, data) for pattern in patterns):
        raise ValueError("Potential sensitive value in selected file: " + str(path))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    selected, reading, omitted = {}, set(), []

    def write(relative, data, read=True):
        relative = Path(relative)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe publication path")
        if len(data) >= 100 * 1024**2:
            raise ValueError("GitHub individual-file size bound exceeded")
        screen(relative, data)
        if relative.suffix == ".py":
            ast.parse(data.decode(), filename=str(relative))
        destination = args.output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if str(relative) in selected and destination.read_bytes() != data:
            raise ValueError("Two different values selected for the same path")
        destination.write_bytes(data)
        selected[str(relative)] = {
            "path": str(relative), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "in_reading_zip": read,
        }
        if read:
            reading.add(str(relative))

    def add(path, read=True):
        if path.is_symlink():
            raise ValueError("Symlink is outside the publication contract")
        write(path.relative_to(REPO), path.read_bytes(), read)

    def small_tree(directory, *, exclude=()):
        for folder, directories, names in os.walk(directory):
            directories[:] = sorted(n for n in directories if n not in IGNORE)
            for name in sorted(names):
                path = Path(folder) / name
                if name in EXCLUDED_NAMES or name in exclude:
                    omitted.append(str(path.relative_to(REPO)))
                    continue
                if path.suffix in TEXT or path.suffix in {".png", ".svg"}:
                    if path.stat().st_size > 16 * 1024**2:
                        omitted.append(str(path.relative_to(REPO)))
                    else:
                        add(path)

    for path in sorted(BUNDLE.iterdir()):
        if path.is_file() and path.suffix in TEXT and path.name not in EXCLUDED_NAMES:
            add(path)
    for name in ("inputs", "review_replay_01"):
        small_tree(BUNDLE / name)
    for name in ("OVERALL_PLAN_CN.md", "HAZARD_DATA_PLAN_CN.md", "OVERALL_HAZARD_CONTRACTS.json",
                 "RELATED_WORK_MATRIX_CN.md", "EXPERIMENT_MATRIX.json", "MASTER_MILESTONES.json"):
        add(REPO / "plans/v7_0912_overall_research" / name)
    for directory in sorted(BUNDLE.iterdir()):
        if not directory.is_dir():
            continue
        name = directory.name
        if name.startswith(("calendar_analysis_", "wrapper_analysis_", "static_baselines_", "ranking_analysis_", "e_order_analysis_", "resource_analysis_", "joint_E_analysis_",
                            "e_diagnostic_analysis_", "report_event_profile_", "cohort_profiles_", "figures_execution_",
                            "packaged_replay_")) or "_validation_" in name:
            small_tree(directory)
        elif name.startswith("offline_"):
            for relative in ("INPUT_BINDINGS.json", "PROCESS.json", "REPLAY_REPORT.json", "REPLAY.log",
                             "validation/REPLAY_REPORT.json"):
                if (directory / relative).is_file():
                    add(directory / relative)
        elif name.startswith(("calendar_controls_", "strong_controls_", "programs_")):
            for relative in ("CONFIGURATIONS.json", "SOURCE_BINDINGS.json", "SUMMARY.json"):
                if (directory / relative).is_file():
                    add(directory / relative)
        elif name.startswith("gpu_") and (directory / "PLAN.json").is_file():
            add(directory / "PLAN.json")
            for relative in ("INTENT.json", "CONSUMED.json", "FREEZE.json"):
                if (directory / relative).is_file():
                    add(directory / relative)
            for path in sorted(directory.glob("worker-[0-9]/*.json")):
                if path.name in {"COMPLETE.json", "HARDWARE.json"}:
                    add(path)
        elif name in {"gpu_queue_01", "delivery_queue_01", "e_order_queue_01"} or name.startswith("live_version_observer_"):
            small_tree(directory)
        elif (directory / "REGIONAL_JOIN_AUDIT.json").is_file():
            add(directory / "REGIONAL_JOIN_AUDIT.json")
            add(directory / "SOURCES.json")
        elif name.startswith("calibration_bank_"):
            small_tree(directory, exclude={"CHECK_ROWS.json", "FIT_IDS.json"})

    package = REPO / "disastertrace-starter"
    small_tree(package / "src/disastertrace/monitoring_v1")
    for name in ("__init__.py", "models.py"):
        add(package / "src/disastertrace" / name)
    for path in sorted((package / "tests").glob("test_monitoring_*.py")):
        add(path)
    for name in ("IMPLEMENTATION_STATUS.md", "DECISIONS.md", "BLOCKERS.md", "pyproject.toml"):
        add(package / name)

    for path in sorted(HERE.iterdir()):
        if path.is_file() and path.suffix in TEXT and path.name not in {
            "PUBLISH_RESULT.json", "EXPORT_MANIFEST.json", "EXCLUDED_ASSETS.json",
            "SCREEN_AFTER.xml",
        }:
            add(path)
    index = []
    for path in sorted((HERE / "inventories").glob("*_ARCHIVE_CHECK.json")):
        check = json.loads(path.read_text())
        if not check["full_archive_content_reverified"]:
            raise ValueError("Archive is not verified: " + path.name)
        unit = HERE / "evidence" / check["name"]
        manifest = unit / "manifest.json"
        if hashlib.sha256(manifest.read_bytes()).hexdigest() != check["manifest_sha256"]:
            raise ValueError("Archive manifest changed")
        add(path, False)
        add(path.with_name(check["name"] + ".json"), False)
        for file in sorted(unit.iterdir()):
            add(file, False)
        index.append({
            "unit": check["name"], "files": check["files"],
            "source_bytes": check["source_bytes"], "archive_bytes": check["archive_bytes"],
            "manifest_sha256": check["manifest_sha256"],
            "location": str(unit.relative_to(REPO)), "content_check": True,
        })
    write(PUBLICATION / "EVIDENCE_INDEX.json", encoded({
        "units": index, "compressed_bytes": sum(r["archive_bytes"] for r in index),
        "scope": "Original model/data/control evidence, including failures. Byte integrity is not scientific admission.",
    }))

    with tempfile.TemporaryDirectory(prefix="disastertrace-v7-export-") as temporary:
        config = Path(temporary) / "gitconfig"
        config.write_text("[safe]\n\tdirectory = " + str(REPO) + "\n")
        env = dict(os.environ, GIT_CONFIG_GLOBAL=str(config), GIT_OPTIONAL_LOCKS="0")

        def git(*arguments):
            return subprocess.run(["git", *arguments], cwd=REPO, env=env,
                                  capture_output=True, check=True).stdout

        base = git("rev-parse", args.base).decode().strip()
        intro = (HERE / "README_INTRO_CN.md").read_text()
        for name in ("README.md", "LATEST_PROGRESS_20260912_CN.md"):
            original = git("show", base + ":" + name).decode()
            title, _, body = original.partition("\n")
            write(name, (title + "\n\n" + intro + "\n\n" + body.lstrip("\n")).encode())
    write(PUBLICATION / "EXCLUDED_ASSETS.json", encoded({
        "large_reading_artifacts": omitted,
        "not_selected": ["credentials", "model weights", "installed environments and libraries",
                         "duplicate offline replay checkouts", "unrelated old experiment worktree changes",
                         "unverified incomplete worker outputs",
                         "SCREEN_AFTER.xml contains synthetic credential-like pytest IDs; SCREEN_AFTER_02.xml uses named IDs"],
        "large_rows_reconstructable_from": "Checked model/control evidence archives and analyze_calendar.py",
    }))
    manifest_data = encoded({
        "schema": "disastertrace.v7.implementation_publication.v1", "base_commit": base,
        "files": sorted(selected.values(), key=lambda row: row["path"]),
        "file_count": len(selected), "bytes": sum(row["bytes"] for row in selected.values()),
        "reading_files": len(reading), "real_index_and_HEAD_unchanged": True,
    })
    manifest_relative = PUBLICATION / "EXPORT_MANIFEST.json"
    (args.output / manifest_relative).write_bytes(manifest_data)
    archive_path = args.output / PUBLICATION / ZIP_NAME
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(reading):
            archive.write(args.output / name, name)
        archive.writestr(str(manifest_relative), manifest_data)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Reading ZIP CRC failed")
        for name in sorted(reading):
            if hashlib.sha256(archive.read(name)).hexdigest() != selected[name]["sha256"]:
                raise ValueError("Reading ZIP content mismatch")
    print(json.dumps({"base": base, "selected_files": len(selected),
                      "selected_bytes": sum(row["bytes"] for row in selected.values()),
                      "reading_zip_bytes": archive_path.stat().st_size,
                      "checked_evidence_units": len(index), "reading_zip_verified": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base", required=True)
    main(parser.parse_args())
