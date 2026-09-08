"""Reconstruct historical reports with their frozen implementation; never generate."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project = args.project.resolve()
    args.output.mkdir(parents=True, exist_ok=False)

    def guard(event, fields):
        if event == "socket.connect":
            raise RuntimeError("baseline reconstruction must remain offline")

    sys.addaudithook(guard)
    from disastertrace.constrained_eval import audit as base_audit
    from disastertrace.local_eval.storage import digest, now, read, write
    from disastertrace.stress_eval import audit

    bundle = project / "artifacts/p5_stress_level4_v1"
    results = {}
    base = project / "artifacts/p4_constrained_output_v1"
    results["base"] = base_audit.report(
        base / "execution_live", project / "work/p4-qwen3-constrained-v1",
        base / "model_report", require_model=True, verify=True,
    )
    for factor in ("revision_chain", "irrelevant_scope", "late_stale_replay"):
        unit = bundle / "units" / factor
        results[factor] = audit.report(
            unit / "execution_live",
            project / ("work/p5-qwen3-" + factor.replace("_", "-") + "-v1"),
            unit / "model_report", require_model=True, verify=True,
        )
        print(factor, results[factor], flush=True)
    counts = {}
    for name in ("OFFLINE_ACCEPTANCE.json", "LIVE_ACCEPTANCE.json"):
        mapping = read(bundle / name)["evidence_sha256"]
        for path, expected in mapping.items():
            if digest(bundle / path) != expected:
                raise ValueError("historical evidence changed: " + path)
        counts[name] = len(mapping)
    env = {**os.environ, "SUDO_UID": "11329"}
    tree = subprocess.check_output(["git", "ls-tree", "-rz", "HEAD"], cwd=project.parent, env=env)
    entries = {}
    for row in tree.split(b"\0"):
        if row:
            metadata, path = row.split(b"\t", 1)
            mode, kind, blob = metadata.decode().split()
            entries[path.decode()] = {"mode": mode, "kind": kind, "git_blob": blob}
    write(args.output / "protected_git_tree.json", entries)
    write(args.output / "repo_baseline.json", {
        "at": now(), "status": "passed", "python": sys.version,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project, env=env, text=True).strip(),
        "frozen_source_root": str(Path(audit.__file__).resolve().parents[3]),
        "full_capture_verified": True, "reports": results,
        "acceptance_entries_unchanged": counts, "additional_model_calls": 0,
        "historical_records_are_not_new_samples": True,
    })


if __name__ == "__main__":
    main()
