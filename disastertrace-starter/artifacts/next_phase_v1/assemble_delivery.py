"""Archive validated offline outputs; verify without extraction or network access."""

import argparse
import hashlib
import json
import re
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parents[1]
REPO = PROJECT.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n")


def protected():
    files = read(BASE / "baseline/protected_files.json")
    changed = [p for p, sha in files.items() if not (REPO / p).is_file() or digest(REPO / p) != sha]
    if changed:
        raise ValueError("historical protection failure: " + ", ".join(changed))
    return {"verified_files": len(files), "changed": [], "status": "passed"}


def verify():
    manifest = read(BASE / "archive_manifest.json")
    archive = BASE / manifest["archive"]
    if digest(archive) != manifest["archive_sha256"]:
        raise ValueError("archive hash mismatch")
    with tarfile.open(archive, "r:gz") as saved:
        members = saved.getmembers()
        if len(members) != len(manifest["files"]) or {m.name for m in members} != set(
            manifest["files"]
        ):
            raise ValueError("archive inventory differs")
        for member in members:
            if (
                not member.isfile()
                or ".." in Path(member.name).parts
                or Path(member.name).is_absolute()
            ):
                raise ValueError("unsafe archive member")
            with saved.extractfile(member) as stream:
                if hashlib.sha256(stream.read()).hexdigest() != manifest["files"][member.name]:
                    raise ValueError("archive member changed: " + member.name)
    return {
        "status": "passed",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "archive_sha256": manifest["archive_sha256"],
        "archive_files": len(manifest["files"]),
        "historical_protection": protected(),
        "model_calls": 0,
    }


def assemble():
    from disastertrace.automated import live_calibration

    if (BASE / "offline_package_v1.tar.gz").exists():
        raise ValueError("delivery archive already exists; use --verify-only")
    validation = BASE / "validation"
    validation.mkdir(exist_ok=False)
    runs = []
    for number in (1, 2, 3):
        source = PROJECT / "work" / f"next-phase-acceptance-{number:03}"
        commands = read(source / "commands.json")
        if any(row["exit_code"] != 0 for row in commands["records"]):
            raise ValueError("cannot package failed acceptance")
        target = validation / f"acceptance_{number:03}"
        target.mkdir()
        for path in [source / "commands.json", *source.glob("*.log")]:
            shutil.copyfile(path, target / path.name)
        runs.append(
            {
                "run": str(source.relative_to(PROJECT)),
                "tests_requested": commands["tests_requested"],
                "steps": len(commands["records"]),
                "all_exit_zero": True,
                "model_calls": commands["model_calls"],
            }
        )
    final = PROJECT / "work/next-phase-acceptance-003"
    execution = live_calibration.verify_execution(final / "execution")
    p2 = read(final / "p2/plan.json")
    audit = read(final / "execution_audit.json")
    report = read(final / "report/report.json")
    test_log = (validation / "acceptance_002/tests.log").read_text()
    if not re.search(r"949 passed in 131\.14s", test_log):
        raise ValueError("unexpected full-suite evidence")
    if (
        not audit["complete"]
        or audit["model_api_calls"] != 0
        or report["selected_output_tokens"] is not None
        or report["live_recommendation"]
        or p2["live_ready"]
        or p2["model_calls"] != 0
    ):
        raise ValueError("offline delivery scope mismatch")
    environment = live_calibration.environment_identity()
    write(
        validation / "environment.json",
        {
            "executable": sys.executable,
            "imported_collector": live_calibration.__file__,
            **environment,
        },
    )
    (validation / "requirements-installed.txt").write_text(
        "".join(f"{name}=={version}\n" for name, version in environment["packages"])
    )
    write(
        validation / "status.json",
        {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "baseline": read(BASE / "baseline/baseline.json"),
            "runs": runs,
            "full_suite": {"passed": 949, "skipped": 0, "seconds": 131.14, "run": "acceptance_002"},
            "final_source_change": read(BASE / "root_checks/format_equivalence.json"),
            "build_id": read(final / "build/manifest.json")["build_id"],
            "preparation_id": execution["parent_preparation_id"],
            "execution_id": execution["execution_id"],
            "execution_source_identity": execution["source_identity"]["identity"],
            "p2_dataset_content_id": p2["dataset_content_id"],
            "p2_package_id": read(final / "p2/manifest.json")["package_id"],
            "p2_state": p2["status"],
            "p2_live_ready": p2["live_ready"],
            "diagnostic_received": audit["received"],
            "diagnostic_attempts": audit["attempts"],
            "selected_output_tokens": report["selected_output_tokens"],
            "model_calls": 0,
            "historical_protection": protected(),
        },
    )
    for name in ("execution_audit.json",):
        shutil.copyfile(final / name, validation / name)
    shutil.copyfile(final / "report/report.json", validation / "calibration_report.json")
    shutil.copyfile(final / "p2/plan.json", validation / "p2_plan.json")
    roots = [
        final,
        PROJECT / "src",
        PROJECT / "tests",
        PROJECT / "scripts",
        PROJECT / "docs",
        REPO / "references",
        REPO / "plans",
        REPO / ".github",
        validation,
        BASE / "baseline",
        BASE / "root_checks",
    ]
    paths = {
        p
        for root in roots
        for p in root.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    }
    paths.update(PROJECT.glob("*.md"))
    paths.update(
        {
            PROJECT / "pyproject.toml",
            REPO / "README.md",
            BASE / "README.md",
            Path(__file__).resolve(),
            PROJECT / "artifacts/p1_deepseek_development/provider.json",
        }
    )
    paths.update((PROJECT / "artifacts/p1_deepseek_development/docs").glob("*"))
    paths = sorted(p for p in paths if p.is_file())
    files = {str(p.relative_to(REPO)): digest(p) for p in paths}
    archive = BASE / "offline_package_v1.tar.gz"
    with tarfile.open(archive, "w:gz", compresslevel=6) as output:
        for path in paths:
            output.add(path, arcname=str(path.relative_to(REPO)), recursive=False)
    write(
        BASE / "archive_manifest.json",
        {
            "schema_version": "next_phase_offline_archive_v1",
            "archive": archive.name,
            "archive_sha256": digest(archive),
            "archive_bytes": archive.stat().st_size,
            "files": files,
            "requires_baseline_repository_for_full_historical_tests": True,
        },
    )
    result = verify()
    write(BASE / "verification.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    if parser.parse_args().verify_only:
        print(json.dumps(verify()))
    else:
        assemble()
