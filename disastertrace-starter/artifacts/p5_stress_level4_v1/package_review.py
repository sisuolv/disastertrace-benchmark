"""Create and verify a standalone local P5/P4 review archive without model weights."""

import argparse
import hashlib
import tarfile

from acp_common import FACTORS, HERE, PROJECT

from disastertrace.local_eval.storage import digest, now, read, write

NAME = "p5_stress_level4_acp_v1_review.tar.gz"
EXCLUDED = {NAME, "archive_manifest.json", "archive_verification.json"}


def candidates():
    paths = []
    for path in HERE.rglob("*"):
        parts = path.relative_to(HERE).parts
        if (
            path.is_file()
            and path.name not in EXCLUDED
            and not {"cache", "__pycache__"}.intersection(parts)
            and not any(part.startswith("package_review") for part in parts[:-1])
        ):
            paths.append(path)
    for factor in FACTORS:
        plan = read(HERE / "units" / factor / "execution_live/execution.json")
        run = PROJECT / "work" / ("p5-qwen3-" + factor.replace("_", "-") + "-v1")
        if plan["run_path"] != str(run):
            raise ValueError("unexpected production path")
        paths += [p for p in run.rglob("*") if p.is_file()]
    base = HERE.parent / "p4_constrained_output_v1"
    for folder in (
        base / "execution_live",
        base / "model_report",
        base / "third_party_licenses",
        PROJECT / "work/p4-qwen3-constrained-v1",
    ):
        paths += [p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    paths += [base / "FINDINGS.md", base / "NEXT_PHASE_PLAN.md"]
    paths += [
        PROJECT / name
        for name in (
            "README_P5_ACP_V1.md",
            "README_P5_STRESS_LEVEL4_V1.md",
            "README.md",
            "AGENTS.md",
            "IMPLEMENTATION_STATUS.md",
            "DECISIONS.md",
            "BLOCKERS.md",
            "pyproject.toml",
            "docs/P5_STRESS_LEVEL4_V1.md",
            "tests/test_stress_level4.py",
        )
    ]
    paths = sorted(set(paths))
    if any(p.is_symlink() or p.suffix == ".safetensors" for p in paths):
        raise ValueError("review must contain regular files and no model weights")
    return paths


def verify():
    manifest = read(HERE / "archive_manifest.json")
    archive_path = HERE / NAME
    if (
        digest(archive_path) != manifest["archive_sha256"]
        or archive_path.stat().st_size != manifest["archive_bytes"]
    ):
        raise ValueError("archive digest/size mismatch")
    found = {}
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive:
            name = member.name
            if (
                not member.isfile()
                or name.startswith("/")
                or ".." in name.split("/")
                or name in found
            ):
                raise ValueError("unsafe or duplicate archive member")
            hasher = hashlib.sha256()
            with archive.extractfile(member) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(block)
            found[name] = hasher.hexdigest()
    if found != manifest["files"]:
        raise ValueError("archive member inventory mismatch")
    return {
        "status": "passed",
        "at": now(),
        "files_verified": len(found),
        "archive_sha256": manifest["archive_sha256"],
        "archive_bytes": manifest["archive_bytes"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        print(verify())
        return
    if (
        not read(HERE / "FINAL_STATUS.json")["complete"]
        or read(HERE / "completed_jobs_verified.json")["status"] != "passed"
    ):
        raise ValueError("complete audited phase required")
    paths = candidates()
    files = {str(p.relative_to(PROJECT)): digest(p) for p in paths}
    internal = HERE / "review_contents.json"
    write(internal, {"schema_version": "p5_internal_review_inventory_v1", "files": files})
    paths.append(internal)
    files[str(internal.relative_to(PROJECT))] = digest(internal)
    with (HERE / NAME).open("xb") as sink, tarfile.open(fileobj=sink, mode="w:gz") as archive:
        for path in paths:
            archive.add(path, arcname=str(path.relative_to(PROJECT)), recursive=False)
    write(
        HERE / "archive_manifest.json",
        {
            "schema_version": "p5_review_archive_v1",
            "at": now(),
            "archive": NAME,
            "archive_sha256": digest(HERE / NAME),
            "archive_bytes": (HERE / NAME).stat().st_size,
            "files": files,
            "weights_included": False,
            "published": False,
        },
    )
    result = verify()
    write(HERE / "archive_verification.json", result)
    print(result)


if __name__ == "__main__":
    main()
