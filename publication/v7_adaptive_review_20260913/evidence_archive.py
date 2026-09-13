"""Deduplicate accepted bytes into bounded ZIP parts and restore without overwrites."""

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

MAX_BLOB = 512 * 1024 * 1024
PART_LIMIT = 80 * 1024 * 1024
HEX = re.compile(r"[0-9a-f]{64}\Z")
FORBIDDEN = {".git", ".github", ".venv", "__pycache__", ".env", "credentials.json"}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(data)
    return value.hexdigest()


def read(path):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("duplicate manifest key")
            out[key] = value
        return out
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs)


def write(path, value):
    with Path(path).open("xb") as stream:
        stream.write(encoded(value) + b"\n")


def safe_path(root, name):
    relative = PurePosixPath(name)
    if (not name or relative.is_absolute() or ".." in relative.parts or "\\" in name
            or any(part in FORBIDDEN or part.startswith(".env.") for part in relative.parts)
            or str(relative) != name):
        raise ValueError("unsafe publication path: " + name)
    root = Path(root).resolve()
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("symlink in publication path: " + name)
    if not path.resolve().is_relative_to(root):
        raise ValueError("publication path escaped root")
    return path


def collect(repo, acceptances):
    repo = Path(repo).resolve()
    project = repo / "disastertrace-starter"
    files, proofs = {}, {}

    def add(name, expected):
        path = safe_path(repo, name)
        if not HEX.fullmatch(expected) or not path.is_file() or digest(path) != expected:
            raise ValueError("accepted bytes differ: " + name)
        row = {"sha256": expected, "bytes": path.stat().st_size,
               "mode": 0o755 if path.stat().st_mode & 0o111 else 0o644}
        if row["bytes"] > MAX_BLOB:
            raise ValueError("file exceeds bounded restoration size: " + name)
        if name in files and files[name] != row:
            raise ValueError("accepted inventories conflict: " + name)
        files[name] = row

    for name in acceptances:
        path = safe_path(repo, name)
        record = read(path)
        if record["acceptance_id"] != sha(encoded({k: v for k, v in record.items()
                                                   if k != "acceptance_id"})):
            raise ValueError("acceptance identity differs: " + name)
        evidence = record.get("evidence_sha256", record.get("files"))
        if not isinstance(evidence, dict) or not evidence:
            raise ValueError("acceptance lacks an evidence inventory")
        for relative, expected in evidence.items():
            target = Path(os.path.abspath(project / relative))
            if not target.is_relative_to(repo):
                raise ValueError("accepted path is outside publication repository")
            add(target.relative_to(repo).as_posix(), expected)
        add(name, digest(path))
        proofs[name] = {"acceptance_id": record["acceptance_id"], "sha256": digest(path),
                       "evidence_files": len(evidence)}
    return files, proofs


def build(repo, acceptances, output, *, part_limit=PART_LIMIT):
    repo, output = Path(repo).resolve(), Path(output).resolve()
    files, proofs = collect(repo, acceptances)
    output.mkdir(parents=True, exist_ok=False)
    write(output / "BUILD_CLAIM.json", {"acceptances": proofs,
          "file_count": len(files), "part_limit": part_limit})
    representatives = {}
    for name, row in sorted(files.items()):
        representatives.setdefault(row["sha256"], name)
    parts, objects, archive, count = {}, {}, None, 0

    def finish_part():
        nonlocal archive
        if archive is not None:
            path = Path(archive.filename)
            archive.close()
            if path.stat().st_size >= part_limit:
                raise ValueError("compressed part exceeded its registered limit")
            parts[path.name] = {"sha256": digest(path), "bytes": path.stat().st_size}
            archive = None

    try:
        for identity, name in sorted(representatives.items()):
            data = safe_path(repo, name).read_bytes()
            if len(data) != files[name]["bytes"] or sha(data) != identity:
                raise ValueError("evidence changed after collection: " + name)
            compressed = gzip.compress(data, compresslevel=6, mtime=0)
            if len(compressed) + 4096 >= part_limit:
                raise ValueError("one object cannot fit a bounded publication part")
            if archive is not None and archive.fp.tell() + len(compressed) + 4096 + count * 256 >= part_limit:
                finish_part()
            if archive is None:
                archive = zipfile.ZipFile(output / f"part-{len(parts):04d}.zip", "x",
                                          compression=zipfile.ZIP_STORED)
                count = 0
            member = "objects/" + identity + ".gz"
            info = zipfile.ZipInfo(member, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, compressed)
            objects[identity] = {"archive": Path(archive.filename).name, "member": member,
                                 "bytes": len(data), "compressed_bytes": len(compressed)}
            count += 1
            if len(objects) % 1000 == 0:
                print(json.dumps({"objects_written": len(objects), "paths": len(files)}), flush=True)
        finish_part()
    finally:
        if archive is not None:
            archive.close()
    record = {"schema_version": "accepted_evidence_cas_v1", "files": files,
              "objects": objects, "parts": parts, "acceptances": proofs,
              "source_bytes": sum(v["bytes"] for v in files.values()),
              "unique_bytes": sum(v["bytes"] for v in objects.values()),
              "archive_bytes": sum(v["bytes"] for v in parts.values()),
              "part_limit": part_limit, "model_weights_included": False,
              "scientific_bytes_modified": False}
    record["manifest_id"] = sha(encoded(record))
    write(output / "manifest.json", record)
    return record


def validate_manifest(bundle):
    bundle = Path(bundle).resolve()
    record = read(bundle / "manifest.json")
    if record["manifest_id"] != sha(encoded({k: v for k, v in record.items()
                                             if k != "manifest_id"})):
        raise ValueError("archive manifest identity differs")
    for identity, obj in record["objects"].items():
        if (not HEX.fullmatch(identity) or obj["member"] != "objects/" + identity + ".gz"
                or obj["archive"] not in record["parts"] or type(obj["bytes"]) is not int
                or not 0 <= obj["bytes"] <= MAX_BLOB):
            raise ValueError("invalid object descriptor")
    for name, row in record["files"].items():
        safe_path(bundle, name)
        if (row["sha256"] not in record["objects"] or row["mode"] not in (0o644, 0o755)
                or row["bytes"] != record["objects"][row["sha256"]]["bytes"]):
            raise ValueError("invalid file descriptor")
    for name, info in record["parts"].items():
        path = safe_path(bundle, name)
        if path.stat().st_size != info["bytes"] or digest(path) != info["sha256"]:
            raise ValueError("archive part differs: " + name)
    return record


def restore(bundle, target=None, *, verify_only=False):
    bundle = Path(bundle).resolve()
    record = validate_manifest(bundle)
    target = Path(target).absolute() if target is not None else None
    if target is not None and target.resolve() != target:
        raise ValueError("restoration root must not contain symlinks")
    if not verify_only and target is None:
        raise ValueError("restoration needs a target")
    destinations = {}
    for name, row in record["files"].items():
        if target is not None:
            path = safe_path(target, name)
            if path.exists() and (not path.is_file() or digest(path) != row["sha256"]):
                raise ValueError("existing destination differs; nothing overwritten: " + name)
            if verify_only and not path.exists():
                raise ValueError("restored evidence is missing: " + name)
            destinations.setdefault(row["sha256"], []).append((path, row["mode"]))
    checked, written = set(), 0
    for part in sorted(record["parts"]):
        expected = {v["member"]: (k, v) for k, v in record["objects"].items()
                    if v["archive"] == part}
        with zipfile.ZipFile(bundle / part) as archive:
            if len(archive.namelist()) != len(expected) or set(archive.namelist()) != set(expected):
                raise ValueError("unregistered or duplicate archive member")
            for info in archive.infolist():
                if not stat.S_ISREG(info.external_attr >> 16):
                    raise ValueError("nonregular archived object")
                identity, obj = expected[info.filename]
                if info.file_size != obj["compressed_bytes"]:
                    raise ValueError("compressed object size differs")
                with gzip.GzipFile(fileobj=io.BytesIO(archive.read(info))) as stream:
                    data = stream.read(obj["bytes"] + 1)
                if len(data) != obj["bytes"] or sha(data) != identity:
                    raise ValueError("decoded evidence bytes differ")
                checked.add(identity)
                if not verify_only:
                    for path, mode in destinations[identity]:
                        if not path.exists():
                            path.parent.mkdir(parents=True, exist_ok=True)
                            with path.open("xb") as stream:
                                stream.write(data)
                            os.chmod(path, mode)
                            written += 1
        print(json.dumps({"archive_checked": part, "objects_checked": len(checked)}), flush=True)
    if checked != set(record["objects"]):
        raise ValueError("not all accepted objects were verified")
    return {"status": "passed", "manifest_id": record["manifest_id"],
            "objects_verified": len(checked), "evidence_paths": len(record["files"]),
            "written": written, "verify_only": verify_only, "model_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build")
    build_parser.add_argument("--repo", type=Path, required=True)
    build_parser.add_argument("--acceptance", action="append", required=True)
    build_parser.add_argument("--output", type=Path, required=True)
    for action in ("restore", "verify"):
        sub = commands.add_parser(action)
        sub.add_argument("--bundle", type=Path, required=True)
        sub.add_argument("--target", type=Path, required=action == "restore")
        sub.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        value = build(args.repo, args.acceptance, args.output)
        print(json.dumps({k: v for k, v in value.items() if k not in ("files", "objects", "parts", "acceptances")}))
    else:
        value = restore(args.bundle, args.target, verify_only=args.command == "verify")
        write(args.receipt, value)
        print(json.dumps(value))


if __name__ == "__main__":
    main()
