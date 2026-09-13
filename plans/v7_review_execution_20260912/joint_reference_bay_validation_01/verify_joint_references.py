"""Recompute saved calendar joint E witnesses with the strengthened validator."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from analyze_calendar import digest, load, write
from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.reachability import validate_witness
from freeze_active import slice_session
from run_strong_controls import joint_reference


def main(args):
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "verify_joint_references.py")
    summary = load(args.controls / "SUMMARY.json")
    if summary["source_audit_sha256"] != digest(
        args.dataset / "REGIONAL_JOIN_AUDIT.json"
    ):
        raise ValueError("Control source cohort differs")
    data = load_session(
        args.dataset,
        stations=args.stations,
        hours=summary["hours"],
        threshold=summary["threshold_m"],
    )
    cutoffs = sorted({r["cutoff"] for r in data["opportunities"]})
    reports = []
    for path in sorted(args.controls.glob("block-*/JOINT-budget*.json")):
        block = int(path.parent.name.removeprefix("block-"))
        start = block * summary["block_hours"]
        selected = slice_session(data, cutoffs[start : start + summary["block_hours"]])
        recorded = load(path)
        rebuilt = joint_reference(
            selected, recorded["limits"]["requests"], summary["threshold_m"]
        )
        if json.loads(json.dumps(rebuilt)) != recorded:
            raise ValueError("Saved joint reference does not reconstruct: " + str(path))
        reports.append(
            {
                "path": str(path),
                "sha256": digest(path),
                "joint_E_utility": recorded["joint_E_utility"],
                "hourly_frontier_witnesses": sum(
                    len(row["reference"]["frontier"])
                    for row in recorded["hourly_references"]
                ),
                "whole_session_path_valid": True,
                "exact_reference_unchanged": True,
            }
        )
        print(path.name, block, recorded["joint_E_utility"], flush=True)
    expected = (
        (summary["hours"] + summary["block_hours"] - 1) // summary["block_hours"] * 3
    )
    if len(reports) != expected:
        raise ValueError("A saved budget/block reference is missing")
    write(
        args.output / "VERIFIED.json",
        {
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "controls": str(args.controls),
            "source_audit_sha256": summary["source_audit_sha256"],
            "reference_count": len(reports),
            "references": reports,
            "new_model_calls": 0,
            "new_network_requests": 0,
            "validator_sha256": digest(Path(validate_witness.__code__.co_filename)),
            "joint_builder_sha256": digest(Path(joint_reference.__code__.co_filename)),
            "implementation_sha256": digest(args.output / "verify_joint_references.py"),
            "interpretation": "Every hourly Pareto frontier and combined path reconstructs. This checks the frozen query-only E optimum with calendar pacing, not F-optimal or model-inference scheduling.",
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--stations", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
