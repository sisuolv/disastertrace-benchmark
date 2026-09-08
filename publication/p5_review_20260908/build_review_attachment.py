"""Package an explicit code-reading selection; this is not a full execution archive."""

import hashlib
import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROJECT = REPO / "disastertrace-starter"
BUNDLE = PROJECT / "artifacts/p5_stress_level4_v1"


def encoded(value):
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def main():
    archive = HERE / "chatgpt_pro_p5_review.zip"
    manifest_path = HERE / "attachment_manifest.json"
    if archive.exists() or manifest_path.exists():
        raise FileExistsError("use a new versioned publication directory")
    selected = set()

    def add(path):
        if not path.is_file() or path.is_symlink():
            raise ValueError("missing or nonregular reading input: " + str(path))
        selected.add(path)

    for name in (
        "README.md",
        "SOURCE_REVIEW.md",
        "REFERENCE_BUNDLE.md",
        "INTEGRATED_BENCHMARK_PLAN.md",
    ):
        add(REPO / name)
    for name in ("README.md", "build_review_attachment.py", "check_payload.py"):
        add(HERE / name)
    for name in (
        "REVIEW_FOR_CHATGPT_PRO_P5.md",
        "IMPLEMENTATION_STATUS.md",
        "DECISIONS.md",
        "BLOCKERS.md",
        "THIRD_PARTY_NOTICES.md",
        "DISASTERTRACE_CODEX_PLAN.md",
        "pyproject.toml",
    ):
        add(PROJECT / name)
    for root, pattern in (
        (REPO / "plans", "**/*.md"),
        (PROJECT, "README*.md"),
        (PROJECT / "src", "**/*.py"),
        (PROJECT / "tests", "**/*.py"),
        (PROJECT / "docs", "**/*.md"),
        (BUNDLE, "*.md"),
        (BUNDLE, "*.py"),
        (BUNDLE / "analysis", "*"),
        (BUNDLE / "stress_comparison", "*.json"),
        (BUNDLE / "validation/tests_acp_launcher", "*.py"),
        (BUNDLE / "validation/tests_stress_comparison", "*.py"),
        (
            BUNDLE / "units/revision_chain/execution_live/implementation_source",
            "**/*.py",
        ),
    ):
        for path in root.glob(pattern):
            if path.is_file():
                add(path)
    for name in (
        "FINAL_STATUS.json",
        "OFFLINE_ACCEPTANCE.json",
        "LIVE_ACCEPTANCE.json",
        "portable_model_verification.json",
        "completed_jobs_verified.json",
        "archive_verification.json",
        "requirements-review.txt",
    ):
        add(BUNDLE / name)
    for factor in ("revision_chain", "irrelevant_scope", "late_stale_replay"):
        unit = BUNDLE / "units" / factor
        for name in (
            "execution.json",
            "constraint.json",
            "manifest.json",
            "model_snapshot.json",
        ):
            add(unit / "execution_live" / name)
        for name in ("report.json", "trace.json", "manifest.json"):
            add(unit / "model_report" / name)
        for path in (unit / "execution_live/dataset").glob("*"):
            if path.is_file() and path.name != "diagnostics.json":
                add(path)
    content = {
        str(path.relative_to(REPO)): path.read_bytes() for path in sorted(selected)
    }
    inventory = {
        "schema_version": "p5_reading_attachment_contents_v1",
        "purpose": "code_and_design_review_not_full_capture_reconstruction",
        "excluded": [
            "full_raw_runs",
            "tokenizer",
            "weights",
            "environments",
            "many_historical_artifacts",
        ],
        "files_sha256": {
            name: hashlib.sha256(data).hexdigest() for name, data in content.items()
        },
    }
    content["REVIEW_ATTACHMENT_CONTENTS.json"] = encoded(inventory)
    with zipfile.ZipFile(
        archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as stream:
        for name, data in sorted(content.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 8, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            stream.writestr(info, data)
    with zipfile.ZipFile(archive) as stream:
        if len(stream.namelist()) != len(content) or stream.testzip() is not None:
            raise ValueError("attachment member/CRC mismatch")
        for name, expected in content.items():
            if stream.read(name) != expected:
                raise ValueError("attachment bytes differ: " + name)
    record = {
        "schema_version": "p5_reading_attachment_v1",
        "archive": archive.name,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "archive_bytes": archive.stat().st_size,
        "members_verified": len(content),
        "reading_files": len(selected),
        "full_reconstruction_package": False,
    }
    with manifest_path.open("xb") as stream:
        stream.write(encoded(record))
    print(json.dumps(record))


if __name__ == "__main__":
    main()
