"""Inspect the staged publication, including nested archives, without exposing keys."""

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[2]
PATTERNS = {
    "provider_key": re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b"),
    "github_token": re.compile(rb"\bgh[opusr]_[A-Za-z0-9]{30,}\b"),
    "github_pat": re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    "private_key": re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    ),
}
FORBIDDEN = {".env", "hosts.yml", "credentials.json", "id_rsa", "id_ed25519"}
MAX_MEMBER_BYTES = 512 * 1024 * 1024
MAX_TAR_CONTAINER_BYTES = 1024 * 1024 * 1024


def inspect(name, content, issues, depth=0):
    if depth > 6:
        raise ValueError("unexpected archive nesting")
    path = PurePosixPath(name.split("!/")[-1])
    if path.is_absolute() or ".." in path.parts:
        issues.append({"path": name, "rule": "unsafe_archive_path"})
    if path.name in FORBIDDEN or path.name.startswith(".env."):
        issues.append({"path": name, "rule": "credential_path"})
    for rule, pattern in PATTERNS.items():
        for match in pattern.finditer(content):
            issues.append(
                {
                    "path": name,
                    "rule": rule,
                    "line": content.count(b"\n", 0, match.start()) + 1,
                }
            )
    archived = 0
    # CAS object names are hashes, so inspect compression by bytes, not file extension.
    if content.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(content)) as stream:
            prefix = stream.read(512)
            # The preserved P5 TAR is about 700 MB in total; each inner file
            # remains subject to the smaller individual-member bound.
            limit = MAX_TAR_CONTAINER_BYTES if prefix[257:262] == b"ustar" else MAX_MEMBER_BYTES
            decoded = prefix + stream.read(limit - len(prefix) + 1)
        if len(decoded) > limit:
            raise ValueError("compressed member exceeds inspection bound")
        archived += 1 + inspect(name + "!/gzip-content", decoded, issues, depth + 1)
    elif zipfile.is_zipfile(io.BytesIO(content)):
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for member in archive.infolist():
                member_name = name + "!/" + member.filename
                if stat.S_ISLNK(member.external_attr >> 16):
                    issues.append({"path": member_name, "rule": "nonregular_archive_member"})
                if not member.is_dir():
                    if member.file_size > MAX_MEMBER_BYTES:
                        raise ValueError("ZIP member exceeds inspection bound")
                    archived += 1 + inspect(member_name, archive.read(member), issues, depth + 1)
    elif content[257:262] == b"ustar":
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:") as archive:
            for member in archive:
                member_name = name + "!/" + member.name
                if not member.isfile():
                    if not member.isdir():
                        issues.append({"path": member_name, "rule": "nonregular_archive_member"})
                    continue
                if member.size > MAX_MEMBER_BYTES:
                    raise ValueError("TAR member exceeds inspection bound")
                with archive.extractfile(member) as stream:
                    archived += 1 + inspect(member_name, stream.read(), issues, depth + 1)
    return archived


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    env = {**os.environ, "SUDO_UID": "11329"}
    entries = subprocess.check_output(
        ["git", "ls-files", "--stage", "-z"], cwd=REPO, env=env
    )
    archived, total_bytes, issues, hashes = 0, 0, [], {}
    largest = (0, "")
    for item in entries.split(b"\0"):
        if not item:
            continue
        metadata, raw_name = item.split(b"\t", 1)
        mode, blob, stage = metadata.decode().split()
        name = os.fsdecode(raw_name)
        path = REPO / name
        if stage != "0" or mode not in ("100644", "100755") or path.is_symlink():
            raise ValueError("unmerged or nonregular staged path: " + name)
        content = path.read_bytes()
        observed = hashlib.sha1(
            b"blob " + str(len(content)).encode() + b"\0" + content
        ).hexdigest()
        if observed != blob:
            raise ValueError("staged bytes differ from the reviewed file: " + name)
        if len(content) >= 100 * 1024 * 1024:
            issues.append({"path": name, "rule": "github_file_size_limit"})
        if name.startswith(".github/workflows/"):
            issues.append({"path": name, "rule": "workflow_outside_publication_scope"})
        archived += inspect(name, content, issues)
        hashes[name] = hashlib.sha256(content).hexdigest()
        total_bytes += len(content)
        largest = max(largest, (len(content), name))
        if len(hashes) % 1000 == 0:
            print(
                json.dumps({"files_checked": len(hashes), "archive_members": archived}),
                flush=True,
            )
    record = {
        "schema_version": "autonomy_publication_payload_check_v1",
        "at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if not issues else "requires_review",
        "staged_files_checked": len(hashes),
        "archive_members_checked": archived,
        "staged_bytes": total_bytes,
        "largest_file": {"path": largest[1], "bytes": largest[0]},
        "issues": issues,
        "matched_values_printed": False,
        "files_sha256": hashes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(record, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in record.items() if k != "files_sha256"}))
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
