"""Cross-artifact acceptance assertions for the full offline E1 matrix."""

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from disastertrace.automated.common import read_jsonl
from disastertrace.local_eval.storage import read, verify_seal, write
from disastertrace.repeat_eval.package import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    plan, _, slots = verify(root / "execution")
    if (
        len(slots),
        len({s["trajectory_id"] for s in slots}),
        len({s["sampling_seed"] for s in slots}),
    ) != (2160, 432, 1080):
        raise ValueError("E1 identity cardinalities differ")
    trajectories = defaultdict(list)
    first_conditions = {}
    for i in range(0, len(slots), 2):
        left, right = slots[i : i + 2]
        if (
            left["pair_id"] != right["pair_id"]
            or left["sampling_seed"] != right["sampling_seed"]
            or left["slot_id"] == right["slot_id"]
        ):
            raise ValueError("condition pairing differs")
        first_conditions[
            left["base_episode_id"], left["method"], left["checkpoint_id"], left["repeat"]
        ] = left["condition"]
    for key, value in first_conditions.items():
        if key[-1] == 0 and first_conditions[(*key[:-1], 1)] == value:
            raise ValueError("repeat did not counterbalance condition order")
    order_counts = Counter((k[2], k[3], v) for k, v in first_conditions.items())
    if set(order_counts.values()) != {54}:
        raise ValueError("condition order not balanced within checkpoint/repeat")
    for slot in slots:
        trajectories[slot["trajectory_id"]].append(slot["checkpoint_id"])
    if any(cps != [f"c{i}" for i in range(5)] for cps in trajectories.values()):
        raise ValueError("trajectory checkpoint order differs")
    verify_seal(root / "posthoc_final")
    posthoc = read(root / "posthoc_final/conservation.json")
    if posthoc["first_exposure_episodes"] != {
        "revision_chain": {"c2": 30, "never": 6},
        "irrelevant_scope": {"c2": 36},
        "late_stale_replay": {"c4": 36},
    }:
        raise ValueError("actual P5 exposure differs")
    if len(read_jsonl(root / "posthoc_final/field_diagnostics.jsonl")) != 6480:
        raise ValueError("P5 field denominator differs")
    context = read(root / "context/report.json")
    verify_seal(root / "context")
    if context["program_requests"] != 10800 or context["maximum_prompt_tokens"] + 8192 > 16384:
        raise ValueError("context reservation failed")
    reports = {}
    for mode, valid, screens, pass2 in (
        ("correct", 2160, 36, 1.0),
        ("invalid-control", 1728, 0, 0.0),
    ):
        path = root / "reports" / mode
        verify_seal(path)
        audit, scores = read(path / "audit.json"), read(path / "scores.json")
        if (
            not audit["complete"]
            or audit["received"] != 2160
            or audit["additional_model_calls"] != 0
        ):
            raise ValueError("program collection incomplete")
        if (
            scores["counts"]["checkpoints"],
            scores["counts"]["schema_valid"],
            scores["counts"]["all_correct"],
        ) != (2160, valid, valid):
            raise ValueError("fixed denominator or control effect differs")
        if (
            len(scores["format_screens"]) != 36
            or sum(s["passed"] for s in scores["format_screens"]) != screens
        ):
            raise ValueError("format screening differs")
        if len(scores["trajectory_errors"]) != 432 or len(scores["source_repeat_table"]) != 36:
            raise ValueError("source/repeat/trajectory reporting incomplete")
        if any(e["pass_power_2"] != pass2 for e in scores["episode_reliability"]):
            raise ValueError("episode-level repeated reliability differs")
        if scores["eligible_for_model_leaderboard"] is not False:
            raise ValueError("program score relabelled as model")
        reports[mode] = {
            "audit_id": audit["audit_id"],
            "planned": 2160,
            "received": 2160,
            "valid": valid,
            "all_correct": valid,
            "format_screens_passed": screens,
            "episode_pass_power_2": pass2,
        }
    result = {
        "status": "passed",
        "execution_id": plan["execution_id"],
        "unique_slots": 2160,
        "unique_trajectories": 432,
        "sampling_pairs": 1080,
        "condition_order_counterbalanced": True,
        "posthoc_conserved": True,
        "context": context,
        "reports": reports,
        "additional_model_calls": 0,
    }
    write(args.output, result)
    print({k: v for k, v in result.items() if k != "context"}, flush=True)


if __name__ == "__main__":
    main()
