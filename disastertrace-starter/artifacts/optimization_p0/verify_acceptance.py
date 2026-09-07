"""Verify the saved Ida trial and immutable history without model inference."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.automated.common import file_hash, strict_json, write_json
from disastertrace.automated.rescoring import verify_rescore
from disastertrace.automated.workflow import implementation_snapshot


def read(path: Path) -> dict:
    return strict_json(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--score-v1", type=Path, required=True)
    parser.add_argument("--score-v2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("acceptance output exists; use a fresh path")
    root = Path(__file__).resolve().parents[2]
    verification = verify_rescore(args.package)
    old = read(args.score_v1)
    new = read(args.score_v2)
    historical = read(root / "artifacts/deepseek_probe_v1/rescore.json")
    if old != historical:
        raise ValueError("historical v1 score did not reproduce exactly")

    expected = {
        "schema_success": (10, 10),
        "state_accuracy": (50, 50),
        "grounded_state": (50, 50),
        "known_value_accuracy": (32, 32),
        "known_grounded_accuracy": (32, 32),
        "unknown_accuracy": (18, 18),
        "known_answer_coverage": (32, 32),
        "action_accuracy": (10, 10),
        "gold_transition_success": (22, 22),
        "gold_preservation": (18, 18),
        "provenance_refresh": (2, 2),
        "self_error_recovery": (0, 0),
        "all_correct_checkpoints": (10, 10),
    }
    for name, (numerator, denominator) in expected.items():
        metric = new["metrics"][name]
        if metric != {
            "numerator": numerator,
            "denominator": denominator,
            "value": numerator / denominator if denominator else None,
        }:
            raise ValueError(f"unexpected trial metric: {name}")

    def slots(score: dict) -> dict:
        return {
            (row["episode_id"], row["checkpoint_id"], field): value
            for row in score["per_checkpoint"]
            for field, value in row["slots"].items()
        }

    before, after = slots(old), slots(new)
    if before.keys() != after.keys():
        raise ValueError("rescoring changed the set of scored slots")
    differences = []
    for key, prior in before.items():
        current = after[key]
        if prior["value_correct"] != current["value_correct"]:
            raise ValueError("rescoring changed factual correctness")
        if prior["grounded_correct"] != current["grounded_correct"]:
            differences.append(key)
    if differences != [("al092021:controlled:base", "c4", "maximum_wind_mph")]:
        raise ValueError("unexpected grounding differences")

    inventory = read(root / "artifacts/optimization_p0/historical_inventory_before.json")
    changed = [
        name for name, digest in inventory["files"].items() if file_hash(root / name) != digest
    ]
    if changed:
        raise ValueError(f"historical files changed: {changed}")
    write_json(
        args.output,
        {
            "schema_version": "p0_real_trial_acceptance_v1",
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "implementation_id": implementation_snapshot()["implementation_id"],
            "package_verification": verification,
            "historical_v1_exact_match": True,
            "historical_files_unchanged": len(inventory["files"]),
            "historical_inventory_sha256": file_hash(
                root / "artifacts/optimization_p0/historical_inventory_before.json"
            ),
            "score_v1_sha256": file_hash(args.score_v1),
            "score_v2_sha256": file_hash(args.score_v2),
            "expected_metrics_passed": list(expected),
            "changed_grounding_slots": differences,
            "new_provider_requests": 0,
        },
    )
    print(
        f"PASS: original v1 reproduced; {len(expected)} v2 metric checks; "
        f"one explained citation difference; {len(inventory['files'])} historical files unchanged."
    )


if __name__ == "__main__":
    main()
