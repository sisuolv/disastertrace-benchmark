"""Select reviewable source/report bytes and build a deterministic reading ZIP."""

import hashlib
import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGE = ROOT / "disastertrace-starter"
FEAS = ROOT / "plans/v5_0910_feasibility_12h_20260910"
CORE = PACKAGE / "artifacts/active_forecast_core_v1"
SUFFIXES = {
    ".py",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
    ".csv",
    ".log",
    ".zip",
}


def sha(body):
    return hashlib.sha256(body).hexdigest()


def encode(value):
    return (
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    ).encode()


def main():
    selected, reading = set(), set()

    def add(path, attachment=False):
        if (
            not path.is_file()
            or path.is_symlink()
            or not path.resolve().is_relative_to(ROOT)
        ):
            raise ValueError("invalid publication path: " + str(path))
        if "__pycache__" in path.parts or path.name.startswith(".env"):
            return
        if path.stat().st_size >= 32 * 1024 * 1024:
            raise ValueError("large input outside selected reading scope: " + str(path))
        selected.add(path)
        if attachment:
            reading.add(path)

    for directory in (PACKAGE / "src", PACKAGE / "tests", PACKAGE / "docs"):
        for path in directory.rglob("*"):
            if (
                path.is_file()
                and path.suffix in SUFFIXES
                and "__pycache__" not in path.parts
            ):
                add(path, attachment="active_forecast" in path.parts)
    for name in (
        "pyproject.toml",
        "IMPLEMENTATION_STATUS.md",
        "CURRENT_PHASE.md",
        "THIRD_PARTY_NOTICES.md",
    ):
        add(PACKAGE / name, attachment=True)
    for path in PACKAGE.glob("*.md"):
        add(path)
    for name in (
        "LATEST_PROGRESS_20260911_CN.md",
        "RESULTS_20260909.md",
        "SOURCE_REVIEW.md",
        "REFERENCE_BUNDLE.md",
    ):
        add(ROOT / name, attachment=name.startswith("LATEST"))
    for path in (ROOT / "plans/v5_0910_integrated").rglob("*"):
        if path.is_file() and path.suffix in SUFFIXES:
            add(path, attachment=path.parent.name != "inputs" and path.suffix == ".md")
    original_manifest = json.loads((FEAS / "REVIEW_PACKAGE_MANIFEST.json").read_text())
    for item in original_manifest["files"]:
        path = FEAS / item["path"]
        if sha(path.read_bytes()) != item["sha256"]:
            raise ValueError("frozen feasibility review bytes changed: " + str(path))
        add(path, attachment=True)
    add(FEAS / "REVIEW_PACKAGE_MANIFEST.json", attachment=True)
    for path in (FEAS / "code").glob("*.py"):
        add(path, attachment=True)
    for path in CORE.rglob("*"):
        if path.is_file() and path.suffix in SUFFIXES:
            add(path, attachment=True)
    for directory in (PACKAGE / "artifacts/multimodal_v1").iterdir():
        if directory.is_dir():
            for path in directory.iterdir():
                if path.is_file() and path.suffix in SUFFIXES:
                    add(path)
    for relative in ("plans/multimodal_v1", "plans/p6"):
        for path in (ROOT / relative).glob("*.md"):
            add(path)
    prior_publication = ROOT / "publication/autonomy_review_20260909"
    for path in prior_publication.iterdir():
        if path.is_file() and path.suffix in {".py", ".md"}:
            add(path)
    for path in (prior_publication / "result_tables_v1").glob("*"):
        if path.is_file() and path.suffix in SUFFIXES:
            add(path)
    add(PACKAGE / "artifacts/autonomy_10h_v1/POST_WINDOW_PRIORITIES.md")
    for path in HERE.iterdir():
        if path.is_file() and path.suffix in {".py", ".md"}:
            add(path, attachment=True)
    # Include package import dependencies so the focused unit tests are runnable.
    for name in ("__init__.py", "models.py"):
        add(PACKAGE / "src/disastertrace" / name, attachment=True)

    content = {str(p.relative_to(ROOT)): p.read_bytes() for p in sorted(reading)}
    notes = {
        "purpose": "latest research and code review; not complete data/GPU reproduction",
        "start_here": "LATEST_PROGRESS_20260911_CN.md",
        "excluded": [
            "model weights",
            "raw HTTP captures",
            "full radar arrays",
            "complete inference logs",
            "large historical evidence volumes",
            "credentials and environments",
        ],
        "files_sha256": {name: sha(body) for name, body in content.items()},
    }
    content["READING_CONTENTS.json"] = encode(notes)
    archive_path = HERE / "chatgpt_review_20260911.zip"
    with zipfile.ZipFile(
        archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name, body in sorted(content.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 11, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, body)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(content):
            raise ValueError("reading ZIP verification failed")
        for name, expected in content.items():
            if archive.read(name) != expected:
                raise ValueError("reading ZIP bytes differ: " + name)
    selected.add(archive_path)
    record = {
        "purpose": "incremental source and selected-report publication",
        "reading_archive": str(archive_path.relative_to(ROOT)),
        "reading_archive_sha256": sha(archive_path.read_bytes()),
        "reading_archive_bytes": archive_path.stat().st_size,
        "reading_archive_members": len(content),
        "selected_files": len(selected),
        "files_sha256": {
            str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted(selected)
        },
        "full_reconstruction_bundle": False,
        "existing_staged_historical_archives_included": False,
        "model_calls": 0,
    }
    with (HERE / "PUBLICATION_FILES.json").open("xb") as stream:
        stream.write(encode(record))
    print(
        json.dumps({k: v for k, v in record.items() if k != "files_sha256"}, indent=2)
    )


if __name__ == "__main__":
    main()
