"""Check the exact staged tree, including archives, without printing secret values."""

import hashlib
import io
import os
import re
import subprocess
import tarfile
import zipfile
from pathlib import Path

from disastertrace.local_eval.storage import now, write

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PATTERNS = {
    "provider_key": re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b"),
    "github_token": re.compile(rb"\bgh[opusr]_[A-Za-z0-9]{30,}\b"),
    "github_pat": re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
}
FORBIDDEN = {".env", "hosts.yml", "credentials.json", "id_rsa", "id_ed25519"}


def main():
    env = {**os.environ, "SUDO_UID": "11329"}
    result = subprocess.run(
        ["git", "ls-files", "--stage", "-z"], cwd=REPO, env=env,
        capture_output=True, check=True,
    )
    scanned, archived, issues = 0, 0, []
    hashes = {}

    def inspect(name, content, depth=0):
        nonlocal archived
        if depth > 6:
            raise ValueError("unexpected archive nesting")
        path = Path(name.split("!/")[-1])
        if path.name in FORBIDDEN or path.name.startswith(".env."):
            issues.append({"path": name, "rule": "credential_path"})
        for rule, pattern in PATTERNS.items():
            for match in pattern.finditer(content):
                issues.append({"path": name, "rule": rule,
                               "line": content.count(b"\n", 0, match.start()) + 1})
        if name.endswith((".tar.gz", ".tgz")):
            with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as archive:
                for member in archive:
                    if not member.isfile():
                        if not member.isdir():
                            issues.append({"path": name + "!/" + member.name,
                                           "rule": "nonregular_archive_member"})
                        continue
                    with archive.extractfile(member) as stream:
                        inspect(name + "!/" + member.name, stream.read(), depth + 1)
                    archived += 1
        elif name.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                for member in archive.infolist():
                    if not member.is_dir():
                        inspect(name + "!/" + member.filename, archive.read(member), depth + 1)
                        archived += 1

    for item in result.stdout.split(b"\0"):
        if not item:
            continue
        metadata, raw_name = item.split(b"\t", 1)
        mode, blob, stage = metadata.decode().split()
        name = os.fsdecode(raw_name)
        path = REPO / name
        if stage != "0" or mode not in ("100644", "100755") or path.is_symlink():
            raise ValueError("unmerged or nonregular staged path: " + name)
        content = path.read_bytes()
        observed = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if observed != blob:
            raise ValueError("staged bytes differ from the reviewed file: " + name)
        if len(content) >= 100 * 1024 * 1024:
            issues.append({"path": name, "rule": "github_file_size_limit"})
        inspect(name, content)
        hashes[name] = hashlib.sha256(content).hexdigest()
        scanned += 1
    record = {"at": now(), "status": "passed" if not issues else "requires_review",
              "staged_files_checked": scanned, "archive_members_checked": archived,
              "issues": issues, "matched_values_printed": False, "files_sha256": hashes}
    write(HERE / "publication_preflight.json", record)
    print({k: v for k, v in record.items() if k != "files_sha256"})
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
