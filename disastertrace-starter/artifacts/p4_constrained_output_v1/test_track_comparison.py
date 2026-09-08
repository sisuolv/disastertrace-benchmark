"""Reject mismatched opportunities instead of comparing incompatible scores."""

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

from disastertrace.controlled import generator, runtime, scorer

spec = importlib.util.spec_from_file_location(
    "p4_tracks", Path(__file__).with_name("compare_tracks.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def scores():
    episodes = generator.micro_episodes()
    return [
        scorer.score(episodes, runtime.rehearse(episodes, "snapshot", backend), "snapshot")
        for backend in ("correct", "invalid-control")
    ]


def test_same_task_scores_pair_every_checkpoint(scores):
    result = module.compare_scores(*scores)
    assert result["matched_checkpoints"] == 60
    assert sum(result["paired_checkpoint_outcomes"].values()) == 60
    assert result["paired_checkpoint_outcomes"]["free_only"] == 12


@pytest.mark.parametrize(
    "mutation", ["aggregate", "checkpoint", "missing", "duplicate", "source-group"]
)
def test_comparison_rejects_incompatible_denominators(scores, mutation):
    right = deepcopy(scores[1])
    if mutation == "aggregate":
        right["metrics"]["schema_success"]["denominator"] += 1
    elif mutation == "checkpoint":
        right["per_checkpoint"][0]["counts"]["known"] += 1
    elif mutation == "missing":
        right["per_checkpoint"].pop()
    elif mutation == "duplicate":
        right["per_checkpoint"].append(right["per_checkpoint"][0])
    else:
        right["per_checkpoint"][0]["group_id"] = "wrong-group"
    with pytest.raises(ValueError):
        module.compare_scores(scores[0], right)
