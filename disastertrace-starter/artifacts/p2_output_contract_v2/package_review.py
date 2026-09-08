"""Package and verify the completed v2 offline review, preserving prior artifacts."""

import argparse
import hashlib
import importlib.util
import json
import re
import tarfile
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parents[1]
REPO = PROJECT.parent


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected():
    spec = importlib.util.spec_from_file_location(
        "v2_historical_artifacts", PROJECT / "scripts/historical_artifacts.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    history = module.HistoricalFiles(REPO)
    files = read(BASE / "baseline/protected_files.json")
    changed = [name for name, value in files.items() if history.digest(name) != value]
    if changed:
        raise ValueError("historical protection failure: " + ", ".join(changed))
    return {"files_verified": len(files), "changed": []}


def verify():
    manifest = read(BASE / "archive_manifest.json")
    path = BASE / manifest["archive"]
    if path.parent != BASE or digest(path) != manifest["archive_sha256"]:
        raise ValueError("archive path/hash mismatch")
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) != len(manifest["files"]) or {m.name for m in members} != set(
            manifest["files"]
        ):
            raise ValueError("archive inventory mismatch")
        for member in members:
            if (
                not member.isfile()
                or Path(member.name).is_absolute()
                or ".." in Path(member.name).parts
            ):
                raise ValueError("unsafe archive member")
            with archive.extractfile(member) as stream:
                if hashlib.sha256(stream.read()).hexdigest() != manifest["files"][member.name]:
                    raise ValueError("archive member mismatch")
    return {
        "status": "passed",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "archive_sha256": manifest["archive_sha256"],
        "archive_files": len(manifest["files"]),
        "historical_protection": protected(),
        "additional_model_calls": 0,
    }


def assemble(run):
    run = Path(run).resolve()
    if not run.is_relative_to(PROJECT / "work"):
        raise ValueError("expected a project-local acceptance directory")
    status = read(run / "status.json")
    pipeline = Path(status["pipeline_path"])
    if not pipeline.is_relative_to(PROJECT / "work"):
        raise ValueError("expected project-local completed pipeline")
    if status["status"] != "P2_OUTPUT_CONTRACT_V2_OFFLINE_READY" or status["model_calls"] != 0:
        raise ValueError("completed v2 offline acceptance required")
    for directory, required in ((run, 5), (pipeline, 13)):
        commands = read(directory / "commands.json")
        if len(commands["records"]) != required or not commands["tests_requested"]:
            raise ValueError("complete full-suite acceptance required")
        for row in commands["records"]:
            if (
                row["exit_code"] != 0
                or digest(directory / (row["name"] + ".log")) != row["log_sha256"]
            ):
                raise ValueError("acceptance command or log verification failed")
    tests = (pipeline / "tests.log").read_text()
    matched = re.search(r"(\d+) passed in ([\d.]+)s", tests)
    if matched is None or re.search(r"\d+ (failed|skipped|errors?)", tests):
        raise ValueError("unexpected full-suite result")
    protected()
    archive_path = BASE / "p2_output_contract_v2_review.tar.gz"
    if archive_path.exists():
        raise ValueError("archive already exists; use --verify-only")
    paths = set()
    excluded = {"archive_verification.json", "package.log", archive_path.name}
    folders = (
        run,
        pipeline.parent,
        PROJECT / "src",
        PROJECT / "tests",
        PROJECT / "scripts",
        REPO / "plans",
        BASE,
        PROJECT / "artifacts/p2_deepseek_development_v1",
        PROJECT / "work/p2-deepseek-development-v1",
        PROJECT / "work/p2-execution-acceptance-002/live_registry",
    )
    for folder in folders:
        paths.update(
            p
            for p in folder.rglob("*")
            if p.is_file()
            and not p.is_symlink()
            and "__pycache__" not in p.parts
            and p.suffix != ".pyc"
            and not (p.parent == BASE and p.name in excluded | {"archive_manifest.json"})
        )
    for name in (
        "pyproject.toml",
        "AGENTS.md",
        "IMPLEMENTATION_STATUS.md",
        "DECISIONS.md",
        "BLOCKERS.md",
        "README.md",
        "README_CONTROLLED_V1.md",
        "README_NEXT_PHASE_V1.md",
        "README_P2_EXECUTION_V1.md",
        "README_P2_DEEPSEEK_V1.md",
        "README_P2_OUTPUT_CONTRACT_V2.md",
        "docs/P2_CONTROLLED_SEMANTICS_V1.md",
        "docs/P2_AUTOMATIC_GOLD_VALIDATION.md",
        "docs/P2_EXECUTION_V1.md",
        "docs/P2_OUTPUT_CONTRACT_V2.md",
        "THIRD_PARTY_NOTICES.md",
    ):
        paths.add(PROJECT / name)
    paths.add(REPO / "README.md")
    token_pattern = re.compile(rb"sk-[A-Za-z0-9]{24,}")
    if any(token_pattern.search(p.read_bytes()) for p in paths):
        raise ValueError("key-like material detected before packaging")
    files = {str(p.relative_to(REPO)): digest(p) for p in sorted(paths)}
    with tarfile.open(archive_path, "w:gz", compresslevel=6) as archive:
        for path in sorted(paths):
            archive.add(path, arcname=str(path.relative_to(REPO)), recursive=False)
    manifest = {
        "schema_version": "p2_output_contract_v2_review_archive_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "archive": archive_path.name,
        "archive_sha256": digest(archive_path),
        "archive_bytes": archive_path.stat().st_size,
        "files": files,
        "execution_id": status["execution_id"],
        "output_contract": status["output_contract"],
        "audit_id": status["audit_id"],
        "actual_model_calls_added": 0,
        "diagnostic_responses": status["diagnostic_responses"],
        "full_suite": {"passed": int(matched[1]), "seconds": float(matched[2]), "skipped": 0},
        "requires_project_environment_and_historical_inputs_for_reexecution": True,
    }
    (BASE / "archive_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    result = verify()
    (BASE / "archive_verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        print(json.dumps(verify()))
    elif args.run:
        assemble(args.run)
    else:
        parser.error("--run or --verify-only required")
