"""Freeze and verify the completed T6 artifacts without extraction or model calls."""

import argparse
import hashlib
import json
import re
import tarfile
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parents[1]
REPO = PROJECT.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def verify():
    manifest = read(BASE / "archive_manifest.json")
    if sha(BASE / manifest["archive"]) != manifest["archive_sha256"]:
        raise ValueError("archive digest mismatch")
    with tarfile.open(BASE / manifest["archive"], "r:gz") as archive:
        members = archive.getmembers()
        if len(members) != len(manifest["files"]) or {m.name for m in members} != set(
            manifest["files"]
        ):
            raise ValueError("archive inventory differs")
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
    protected = read(PROJECT / "artifacts/next_phase_v1/baseline/protected_files.json")
    changed = [name for name, expected in protected.items() if sha(REPO / name) != expected]
    if changed:
        raise ValueError("historical protection failure")
    return {
        "status": "passed",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "archive_files": len(manifest["files"]),
        "archive_sha256": manifest["archive_sha256"],
        "historical_files_verified": len(protected),
        "historical_files_changed": [],
        "additional_model_calls": 0,
    }


def prepare():
    completion = read(BASE / "runtime/completion.json")
    audit = read(BASE / "runtime/final_audit.json")
    report = read(BASE / "runtime/report/report.json")
    if (
        completion["diagnostic"] is not False
        or not audit["complete"]
        or audit["audit_id"] != report["audit_id"]
        or audit["attempts"] != 270
        or audit["received"] != 270
        or report["selected_output_tokens"] != 8192
        or audit["budget"]["pending"] != "0"
    ):
        raise ValueError("expected the completed audited T6 matrix")
    archive_path = BASE / "t6_results_v1.tar.gz"
    if archive_path.exists():
        raise ValueError("archive exists; use --verify-only")
    exclude = {"t6_results_v1.tar.gz", "archive_manifest.json", "verification.json", "package.log"}
    paths = [
        p
        for p in BASE.rglob("*")
        if p.is_file()
        and p.name not in exclude
        and "__pycache__" not in p.parts
        and p.suffix != ".pyc"
    ]
    run = Path(read(BASE / "launch_manifest.json")["run_output"])
    paths.extend(p for p in run.rglob("*") if p.is_file())
    paths.extend(
        PROJECT / name
        for name in (
            "README.md",
            "README_T6_CALIBRATION_V1.md",
            "README_NEXT_PHASE_V1.md",
            "README_CONTROLLED_V1.md",
            "IMPLEMENTATION_STATUS.md",
            "DECISIONS.md",
            "BLOCKERS.md",
            "AGENTS.md",
            "artifacts/next_phase_v1/baseline/protected_files.json",
            "artifacts/next_phase_v1/validation/environment.json",
            "artifacts/next_phase_v1/validation/requirements-installed.txt",
            "artifacts/next_phase_v1/validation/acceptance_002/tests.log",
        )
    )
    paths.append(REPO / "README.md")
    paths = sorted(set(paths))
    token_pattern = re.compile(rb"sk-[A-Za-z0-9]{24,}")
    if any(token_pattern.search(p.read_bytes()) for p in paths):
        raise ValueError("key-like material requires inspection before packaging")
    files = {str(p.relative_to(REPO)): sha(p) for p in paths}
    with tarfile.open(archive_path, "w:gz", compresslevel=6) as archive:
        for path in paths:
            archive.add(path, arcname=str(path.relative_to(REPO)), recursive=False)
    manifest = {
        "schema_version": "t6_results_archive_v1",
        "archive": archive_path.name,
        "archive_sha256": sha(archive_path),
        "archive_bytes": archive_path.stat().st_size,
        "files": files,
        "execution_id": report["execution_id"],
        "audit_id": report["audit_id"],
        "actual_model_attempts": 270,
        "additional_packaging_model_calls": 0,
        "selected_output_tokens": 8192,
        "requires_project_environment_for_reexecution": True,
    }
    (BASE / "archive_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    result = verify()
    (BASE / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    if parser.parse_args().verify_only:
        print(json.dumps(verify()))
    else:
        prepare()
