"""Fast-forward a checked publication tree using an isolated index and commit-tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PUBLICATION = HERE.relative_to(REPO)
REMOTE = "ssh://git@ssh.github.com:443/sisuolv/disastertrace-benchmark.git"
BRANCH = "next-phase-v1"
SSH = ("ssh -i /mnt/afs/260010168/.ssh/github_ed25519 -o IdentitiesOnly=yes "
       "-o BatchMode=yes -o StrictHostKeyChecking=yes "
       "-o UserKnownHostsFile=/mnt/afs/260010168/.ssh/github_review_known_hosts -o ConnectTimeout=15")


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def main(args):
    root = args.snapshot.resolve()
    manifest = json.loads((root / PUBLICATION / "EXPORT_MANIFEST.json").read_text())
    preserved = json.loads((HERE / "GIT_START.json").read_text())
    if args.receipt.exists():
        raise ValueError("Publication receipt already exists; inspect rather than repeating")
    with tempfile.TemporaryDirectory(prefix="disastertrace-v7-publish-") as temporary:
        work = Path(temporary)
        config = work / "gitconfig"
        config.write_text("[safe]\n\tdirectory = " + str(REPO) + "\n")
        env = dict(os.environ, GIT_CONFIG_GLOBAL=str(config), GIT_OPTIONAL_LOCKS="0", GIT_SSH_COMMAND=SSH)

        def git(*arguments, data=None, timeout=600):
            result = subprocess.run(["git", *arguments], cwd=REPO, env=env, input=data,
                                    capture_output=True, timeout=timeout, check=True)
            return result.stdout

        def unchanged():
            if git("rev-parse", "HEAD").decode().strip() != preserved["local_HEAD"]:
                raise ValueError("Local HEAD changed since publication preservation check")
            if digest(Path(preserved["real_index_path"])) != preserved["real_index_sha256"]:
                raise ValueError("Real index changed since publication preservation check")

        unchanged()
        base = git("ls-remote", REMOTE, "refs/heads/" + BRANCH).decode().split()[0]
        if base != manifest["base_commit"]:
            raise ValueError("Remote tip differs from the checked publication base")
        files = []
        for row in manifest["files"]:
            path = root / row["path"]
            if path.is_symlink() or path.stat().st_size != row["bytes"] or digest(path) != row["sha256"]:
                raise ValueError("Selected publication file changed: " + row["path"])
            files.append(row["path"])
        for name in ("EXPORT_MANIFEST.json", "DisasterTrace_V7_Latest_Review_20260913.zip"):
            files.append(str(PUBLICATION / name))
        if len(files) != len(set(files)) or any("\n" in name or "\0" in name for name in files):
            raise ValueError("Duplicate or unsupported publication path")
        files.sort()
        env["GIT_INDEX_FILE"] = str(work / "index")
        git("read-tree", base)
        paths = "".join(str(root / name) + "\n" for name in files).encode()
        blobs = git("hash-object", "-w", "--no-filters", "--stdin-paths", data=paths).decode().splitlines()
        if len(blobs) != len(files):
            raise ValueError("Publication blob count differs")
        updates = b"".join(("100644 " + blob + "\t" + name + "\0").encode()
                           for name, blob in zip(files, blobs, strict=True))
        git("update-index", "-z", "--index-info", data=updates)
        tree = git("write-tree").decode().strip()
        entries = {}
        for item in git("ls-tree", "-r", "-z", tree).split(b"\0"):
            if item:
                metadata, name = item.split(b"\t", 1)
                entries[name.decode()] = metadata.decode().split()
        for name, blob in zip(files, blobs, strict=True):
            if entries.get(name) != ["100644", "blob", blob]:
                raise ValueError("Published tree does not bind the selected file")
        if git("diff-tree", "--no-commit-id", "--name-only", "--diff-filter=D", "-r", base, tree):
            raise ValueError("Publication unexpectedly deletes remote files")
        diff = git("diff-tree", "--no-commit-id", "--name-status", "-r", base, tree).decode()
        env.setdefault("GIT_AUTHOR_NAME", "Codex")
        env.setdefault("GIT_AUTHOR_EMAIL", "codex@localhost")
        env.setdefault("GIT_COMMITTER_NAME", env["GIT_AUTHOR_NAME"])
        env.setdefault("GIT_COMMITTER_EMAIL", env["GIT_AUTHOR_EMAIL"])
        message = ("Publish v7 fixed-evidence execution, source validation and CPU replay\n\n"
                   "Preserve v7 research scope; include two-year local calibration, typed fixed-evidence "
                   "interfaces, 720 actual H100 calls, source qualification and portable CPU replay. "
                   "Retain negative results and unresolved scientific admission gates.\n")
        commit = git("commit-tree", tree, "-p", base, data=message.encode()).decode().strip()
        unchanged()
        prepared = {"base": base, "commit": commit, "tree": tree, "selected_files": len(files),
                    "local_HEAD_preserved": preserved["local_HEAD"],
                    "real_index_sha256_preserved": preserved["real_index_sha256"],
                    "manifest_sha256": digest(root / PUBLICATION / "EXPORT_MANIFEST.json"),
                    "reading_zip_sha256": digest(root / PUBLICATION / "DisasterTrace_V7_Latest_Review_20260913.zip")}
        with args.receipt.with_suffix(".prepared.json").open("x") as stream:
            json.dump(prepared, stream, indent=2)
            stream.write("\n")
        args.receipt.with_suffix(".diff.txt").write_text(diff)
        push = git("push", REMOTE, commit + ":refs/heads/" + BRANCH, timeout=1800)
        actual = git("ls-remote", REMOTE, "refs/heads/" + BRANCH).decode().split()[0]
        if actual != commit:
            raise ValueError("Remote branch did not confirm the published commit")
        unchanged()
        prepared.update(published_at=datetime.now(timezone.utc).isoformat(), remote=REMOTE,
                        branch=BRANCH, remote_verified=True, force_push=False,
                        private_repository_visibility_unchanged=True, push_stdout=push.decode())
        with args.receipt.open("x") as stream:
            json.dump(prepared, stream, indent=2)
            stream.write("\n")
        print(json.dumps({"commit": commit, "remote_verified": True, "local_HEAD_and_index_preserved": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    main(parser.parse_args())
