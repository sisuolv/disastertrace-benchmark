"""Protect matched comparisons from denominator drift and loss of failed checkpoints."""

from copy import deepcopy

import pytest
from compare_stress import paired_scores

from disastertrace.controlled.scorer import METRICS


def scores():
    counts = {d: 1 for _, d in METRICS.values()}
    counts["all_correct"] = 1
    base = {
        "metrics": {"all_correct": {"numerator": 1, "denominator": 2}},
        "per_checkpoint": [
            {
                "episode_id": "base",
                "checkpoint_id": "c1",
                "group_id": "storm",
                "status": "ok",
                "counts": counts,
            },
            {
                "episode_id": "base",
                "checkpoint_id": "c2",
                "group_id": "storm",
                "status": "missing",
                "counts": {**counts, "all_correct": 0},
            },
        ],
    }
    stress = deepcopy(base)
    for row in stress["per_checkpoint"]:
        row["episode_id"] = "stress"
    mapping = {"stress": "base"}
    meta = {
        ("stress", c): {"family": "U1", "case": "control", "effective_label": "zero_effect_control"}
        for c in ("c1", "c2")
    }
    return base, stress, mapping, meta


def test_failed_and_zero_effect_checkpoints_remain():
    base, stress, mapping, meta = scores()
    result = paired_scores(base, stress, mapping, meta)
    assert result["matched_checkpoints"] == 2
    assert result["paired_outcomes"] == {"both_correct": 1, "neither": 1}
    controls = next(s for s in result["strata"] if s["dimension"] == "effective")
    assert controls["planned"] == 2
    assert result["checkpoint_pairs"][1]["stress_status"] == "missing"


def test_opposite_transitions_are_not_net_counts():
    base, stress, mapping, meta = scores()
    stress["per_checkpoint"][0]["counts"]["all_correct"] = 0
    stress["per_checkpoint"][1]["counts"]["all_correct"] = 1
    result = paired_scores(base, stress, mapping, meta)
    assert result["paired_outcomes"] == {"base_only_correct": 1, "stress_only_correct": 1}


def test_primary_denominator_drift_rejected():
    args = scores()
    args[1]["metrics"]["all_correct"]["denominator"] = 1
    with pytest.raises(ValueError, match="metric denominators"):
        paired_scores(*args)


def test_checkpoint_opportunity_drift_rejected():
    args = scores()
    denominator = next(iter(METRICS.values()))[1]
    args[1]["per_checkpoint"][0]["counts"][denominator] = 0
    with pytest.raises(ValueError, match="opportunity"):
        paired_scores(*args)


def test_missing_checkpoint_rejected():
    args = scores()
    args[1]["per_checkpoint"].pop()
    with pytest.raises(ValueError, match="checkpoint set"):
        paired_scores(*args)


def test_duplicate_mapped_checkpoint_rejected():
    args = scores()
    args[1]["per_checkpoint"].append(deepcopy(args[1]["per_checkpoint"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        paired_scores(*args)


def test_source_group_drift_rejected():
    args = scores()
    args[1]["per_checkpoint"][0]["group_id"] = "other-storm"
    with pytest.raises(ValueError, match="source group"):
        paired_scores(*args)
