"""Create and verify a local review snapshot after offline result finalization."""

import hashlib
import json
import re
import tarfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
REPO = PROJECT.parent
ARCHIVE = "p2_deepseek_output_contract_v2_review.tar.gz"
EXCLUDE = {ARCHIVE, "archive_manifest.json", "archive_verification.json"}


def sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            result.update(block)
    return result.hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")


def main():
    status = json.loads((HERE / "FINAL_STATUS.json").read_text())
    if status["offline_finalization"]["status"] != "passed":
        raise ValueError("final independent reconstruction must pass before packaging")
    paths = {}

    def add(path):
        if not path.is_file():
            return
        if path.is_symlink() or not path.resolve().is_relative_to(REPO):
            raise ValueError("unsafe archive source path")
        relative = path.relative_to(REPO)
        if any(part in {"__pycache__", ".pytest_cache", ".ruff_cache"} for part in relative.parts):
            return
        if path.suffix == ".pyc" or path.name.endswith(".tar.gz"):
            return
        if path.parent == HERE and path.name in EXCLUDE:
            return
        paths[str(relative)] = path

    for name in ("README.md", "INTEGRATED_BENCHMARK_PLAN.md"):
        add(REPO / name)
    for directory in (
        REPO / "plans",
        PROJECT / "src",
        PROJECT / "tests",
        PROJECT / "scripts",
        PROJECT / "docs",
    ):
        for path in directory.rglob("*"):
            add(path)
    for pattern in ("*.md", "pyproject.toml", "*requirements*.txt", "*.lock"):
        for path in PROJECT.glob(pattern):
            add(path)
    for bundle in (
        HERE,
        HERE.parent / "p2_deepseek_development_v1",
        HERE.parent / "p2_output_contract_v2",
    ):
        for path in bundle.rglob("*"):
            add(path)
    for bundle in (HERE, HERE.parent / "p2_deepseek_development_v1"):
        plan = json.loads((bundle / "launch_manifest.json").read_text())
        run = Path(plan["run_output"])
        if not (run / "journal.jsonl").is_file():
            raise ValueError("original run journal required")
        for path in run.rglob("*"):
            add(path)
        claim = Path(plan["canonical_registry_path"]) / (plan["execution_id"] + ".json")
        if not claim.is_file():
            raise ValueError("original production claim required")
        add(claim)
    suspicious = [
        name
        for name, path in paths.items()
        if re.search(rb"sk-[A-Za-z0-9]{20,}", path.read_bytes())
    ]
    if suspicious:
        raise ValueError("possible credential in review files: " + ", ".join(suspicious))
    files = {name: sha(path) for name, path in sorted(paths.items())}
    target = HERE / ARCHIVE
    with target.open("xb") as stream, tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for name, path in sorted(paths.items()):
            archive.add(path, arcname=name, recursive=False)
    verified = {}
    with tarfile.open(target, "r:gz") as archive:
        for member in archive:
            path = Path(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts:
                raise ValueError("unsafe archive member")
            if member.name in verified:
                raise ValueError("duplicate archive member")
            with archive.extractfile(member) as stream:
                verified[member.name] = hashlib.sha256(stream.read()).hexdigest()
    if verified != files or any(sha(paths[name]) != value for name, value in files.items()):
        raise ValueError("archive bytes differ from source snapshot")
    manifest = {
        "schema_version": "p2_output_contract_v2_model_review_archive_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "archive": ARCHIVE,
        "archive_sha256": sha(target),
        "archive_bytes": target.stat().st_size,
        "file_count": len(files),
        "files": files,
        "execution_id": status["execution_id"],
        "audit_id": status["audit_id"],
        "model_calls": status["model_calls"],
        "additional_model_calls": 0,
        "purpose": "Local review snapshot; original paths and execution identities are retained.",
        "portability_limit": (
            "Strict report reconstruction requires the bound environment and original canonical "
            "run/registry paths. Full historical protection also requires the original workspace; "
            "this snapshot is not a full workspace backup."
        ),
    }
    write(HERE / "archive_manifest.json", manifest)
    verification = {
        "status": "passed",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "archive_sha256": manifest["archive_sha256"],
        "archive_bytes": manifest["archive_bytes"],
        "files_verified": len(verified),
        "source_snapshot_matches": True,
        "credential_pattern_matches": 0,
        "archive_extracted": False,
        "additional_model_calls": 0,
    }
    write(HERE / "archive_verification.json", verification)
    print(json.dumps(verification))


if __name__ == "__main__":
    main()
