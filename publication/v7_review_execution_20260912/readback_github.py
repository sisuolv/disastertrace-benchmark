"""Fetch the published commit in a separate bare repository and verify reading files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from publish_snapshot import BRANCH, PUBLICATION, REMOTE, SSH, digest


def main(args):
    result = json.loads(args.publication_receipt.read_text())
    if not result["remote_verified"] or result["remote"] != REMOTE or result["branch"] != BRANCH:
        raise ValueError("A confirmed publication receipt is required")
    manifest_path = args.snapshot / PUBLICATION / "EXPORT_MANIFEST.json"
    if digest(manifest_path) != result["manifest_sha256"]:
        raise ValueError("Publication manifest changed after push")
    manifest = json.loads(manifest_path.read_text())
    expected = {row["path"]: row for row in manifest["files"]}
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    bare = root / "remote.git"
    config = root / "gitconfig"
    config.write_text("[safe]\n\tdirectory = " + str(bare) + "\n")
    env = dict(os.environ, GIT_CONFIG_GLOBAL=str(config), GIT_SSH_COMMAND=SSH,
               GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    commands = []

    def git(*arguments, cwd=bare):
        run = subprocess.run(["git", *arguments], cwd=cwd, env=env, capture_output=True,
                             timeout=600, check=False)
        commands.append({"argv": ["git", *arguments], "returncode": run.returncode,
                         "stderr": run.stderr.decode(errors="replace")})
        (root / "COMMANDS.json").write_text(json.dumps(commands, indent=2) + "\n")
        if run.returncode:
            raise ValueError("GitHub readback failed; inspect the preserved command receipt")
        return run.stdout

    git("init", "--bare", str(bare), cwd=root)
    git("remote", "add", "origin", REMOTE)
    git("config", "remote.origin.promisor", "true")
    git("config", "remote.origin.partialclonefilter", "blob:none")
    git("fetch", "--depth=1", "--filter=blob:none", "origin", "refs/heads/" + BRANCH)
    actual = git("rev-parse", "FETCH_HEAD").decode().strip()
    if actual != result["commit"]:
        raise ValueError("Fetched remote tip differs from the publication receipt")
    names = [
        "README.md",
        "plans/v7_review_execution_20260912/FINAL_REPORT_CN.md",
        "plans/v7_review_execution_20260912/PLAN_AMENDMENT_CN.md",
        "disastertrace-starter/src/disastertrace/monitoring_v1/reachability.py",
        "disastertrace-starter/src/disastertrace/monitoring_v1/scoring.py",
        str(PUBLICATION / "EXPORT_MANIFEST.json"),
        str(PUBLICATION / "DisasterTrace_v7_Implementation_Review_20260913.zip"),
    ]
    rows = []
    for name in names:
        data = git("show", actual + ":" + name)
        checksum = hashlib.sha256(data).hexdigest()
        if name.endswith("/EXPORT_MANIFEST.json"):
            required = result["manifest_sha256"]
        elif name.endswith(".zip"):
            required = result["reading_zip_sha256"]
        else:
            required = expected[name]["sha256"]
        if checksum != required:
            raise ValueError("Remote file differs from the checked snapshot: " + name)
        target = root / "reading_files" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        rows.append({"path": name, "bytes": len(data), "sha256": checksum})
    receipt = {"finished_at": datetime.now(timezone.utc).isoformat(), "commit": actual,
               "remote": REMOTE, "branch": BRANCH, "remote_ref_matches": True,
               "files": rows, "all_selected_readback_hashes_match": True,
               "existing_project_HEAD_index_and_worktree_used": False,
               "scope": "Independent shallow network fetch and seven reading-file blob checks. Large evidence parts were not downloaded again; source/model reruns are separate evidence."}
    (root / "READBACK.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"commit": actual, "readback_files": len(rows), "hashes_match": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--publication-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
