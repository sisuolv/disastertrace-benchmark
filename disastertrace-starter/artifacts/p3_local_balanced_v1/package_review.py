"""Create and independently verify a portable local review archive, without weights."""

import argparse
import hashlib
import tarfile
from pathlib import Path

from disastertrace.local_eval.storage import digest, now, read, write

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
NAME = "p3_local_balanced_v1_review.tar.gz"
EXCLUDED = {NAME, "archive_manifest.json", "archive_verification.json"}


def candidates():
    paths = [
        p
        for p in HERE.rglob("*")
        if p.is_file() and p.name not in EXCLUDED and "__pycache__" not in p.parts
    ]
    plan = read(HERE / "execution/execution.json")
    paths += [p for p in Path(plan["run_path"]).rglob("*") if p.is_file()]
    paths += [
        PROJECT / name
        for name in (
            "README_P3_LOCAL_BALANCED_V1.md",
            "AGENTS.md",
            "IMPLEMENTATION_STATUS.md",
            "DECISIONS.md",
            "BLOCKERS.md",
            "pyproject.toml",
            "README.md",
            "docs/P3_LOCAL_BALANCED_V1.md",
            "tests/test_local_balanced.py",
            "tests/test_local_difficulty.py",
        )
    ]
    return sorted(set(paths))


def verify():
    manifest = read(HERE / "archive_manifest.json")
    path = HERE / NAME
    if (
        digest(path) != manifest["archive_sha256"]
        or path.stat().st_size != manifest["archive_bytes"]
    ):
        raise ValueError("review archive digest/size mismatch")
    observed = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            name = member.name
            if (
                not member.isfile()
                or Path(name).is_absolute()
                or ".." in Path(name).parts
                or name in observed
            ):
                raise ValueError("unsafe or duplicate archive member")
            hasher = hashlib.sha256()
            with archive.extractfile(member) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(block)
            observed[name] = hasher.hexdigest()
    if observed != manifest["files"]:
        raise ValueError("review archive inventory mismatch")
    return {
        "status": "passed",
        "at": now(),
        "archive_sha256": manifest["archive_sha256"],
        "archive_bytes": manifest["archive_bytes"],
        "files_verified": len(observed),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        print(verify())
        return
    if not read(HERE / "runtime/observer_completion.json")["all_commands_exit_zero"]:
        raise ValueError("complete independently verified model run required for this release")
    if not read(HERE / "FINAL_STATUS.json")["complete"]:
        raise ValueError("final documentation/status required")
    paths = candidates()
    files = {str(p.relative_to(PROJECT)): digest(p) for p in paths}
    with (HERE / NAME).open("xb") as sink:
        with tarfile.open(fileobj=sink, mode="w:gz") as archive:
            for path in paths:
                archive.add(path, arcname=str(path.relative_to(PROJECT)), recursive=False)
    manifest = {
        "schema_version": "p3_review_archive_v1",
        "created_at": now(),
        "archive": NAME,
        "archive_sha256": digest(HERE / NAME),
        "archive_bytes": (HERE / NAME).stat().st_size,
        "files": files,
        "weights_included": False,
        "published": False,
    }
    write(HERE / "archive_manifest.json", manifest)
    result = verify()
    write(HERE / "archive_verification.json", result)
    print(result)


if __name__ == "__main__":
    main()
