"""Verify staged contents/flags without mistaking index cache refreshes for edits."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
GITDIR = Path(
    "/mnt/afs/260010168/extreme_weather_benchmark/github_review/disastertrace-benchmark/.git/worktrees/disastertrace-next"
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_index():
    baseline = json.loads((HERE / "BASELINE.json").read_text())
    original = HERE / "baseline_source/git-index.bin"
    current = Path(baseline["index_path"])
    assert sha(original) == baseline["index_sha256"], "Original index snapshot changed"
    values, records = [], []
    for path in (original, current):
        command = [
            "git",
            "--git-dir=" + str(GITDIR),
            "--work-tree=" + str(REPO),
            "ls-files",
            "--stage",
            "-v",
            "-z",
        ]
        result = subprocess.run(
            command,
            env=dict(os.environ, GIT_INDEX_FILE=str(path), GIT_OPTIONAL_LOCKS="0"),
            capture_output=True,
            check=True,
        )
        values.append(result.stdout)
        records.append(
            {
                "index_sha256": sha(path),
                "staged_entries_sha256": hashlib.sha256(result.stdout).hexdigest(),
                "staged_entry_count": len(result.stdout.split(b"\0")) - 1,
            }
        )
    if values[0] != values[1]:
        raise ValueError(
            "Unexpected staged content or flags changed; stop before submission"
        )
    return {
        "passed": True,
        "original": records[0],
        "current": records[1],
        "byte_identical": records[0]["index_sha256"] == records[1]["index_sha256"],
        "staged_paths_objects_modes_stages_and_flags_identical": True,
        "git_index_written_by_this_check": False,
        "scope": "Preserves original raw index snapshot and exact staged object/flag identity. Index stat-cache/extensions need not be byte-identical; frozen experiment source/data bytes are checked separately.",
    }
