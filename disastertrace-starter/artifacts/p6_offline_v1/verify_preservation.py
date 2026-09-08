"""Compare historical tracked bytes and both P5 acceptance inventories after P6 work."""

import argparse
import hashlib
from pathlib import Path

from disastertrace.local_eval.storage import digest, read, write

NAVIGATION = {
    "README.md",
    "disastertrace-starter/AGENTS.md",
    "disastertrace-starter/IMPLEMENTATION_STATUS.md",
    "disastertrace-starter/DECISIONS.md",
    "disastertrace-starter/BLOCKERS.md",
}


def git_blob(path):
    checksum = hashlib.sha1()
    checksum.update(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            checksum.update(part)
    return checksum.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bundle = Path(__file__).resolve().parent
    project = bundle.parents[1]
    repo = project.parent
    protected = read(bundle / "baseline/protected_git_tree.json")
    checked, navigation = 0, {}
    for name, entry in protected.items():
        if entry["kind"] != "blob":
            raise ValueError("unexpected non-file historical entry")
        path = repo / name
        if name in NAVIGATION:
            navigation[name] = {
                "old_git_blob": entry["git_blob"],
                "current_git_blob": git_blob(path),
            }
            continue
        if not path.is_file() or git_blob(path) != entry["git_blob"]:
            raise ValueError("historical tracked content changed: " + name)
        checked += 1
    counts = {}
    for name in ("OFFLINE_ACCEPTANCE.json", "LIVE_ACCEPTANCE.json"):
        parent = project / "artifacts/p5_stress_level4_v1"
        mapping = read(parent / name)["evidence_sha256"]
        for item, expected in mapping.items():
            if digest(parent / item) != expected:
                raise ValueError("frozen P5 evidence changed: " + item)
        counts[name] = len(mapping)
    result = {
        "status": "passed",
        "protected_tracked_files": checked,
        "navigation_exceptions": navigation,
        "p5_acceptance_entries": counts,
        "additional_model_calls": 0,
    }
    write(args.output, result)
    print({k: v for k, v in result.items() if k != "navigation_exceptions"}, flush=True)


if __name__ == "__main__":
    main()
