from copy import deepcopy

import compare_overlap
import pytest


def example():
    episode = {"episode_id": "a", "checkpoints": [{"checkpoint_id": "c0"}]}
    counts = {key: 1 for pair in compare_overlap.METRICS.values() for key in pair}
    score = {"per_checkpoint": [{"episode_id": "a", "checkpoint_id": "c0", "counts": counts}]}
    return episode, score


def test_overlap_does_not_use_extra_episodes_or_change_denominators():
    episode, score = example()
    other = {"episode_id": "b", "checkpoints": [{"checkpoint_id": "c0"}]}
    new_score = deepcopy(score)
    new_score["per_checkpoint"] += [
        {
            "episode_id": "b",
            "checkpoint_id": "c0",
            "counts": {k: 999 for k in score["per_checkpoint"][0]["counts"]},
        }
    ]
    result = compare_overlap.matched_metrics([episode], [episode, other], score, new_score)
    assert result["matched_checkpoints"] == 1
    assert result["historical_deepseek"] == result["current_qwen_shared_subset"]


@pytest.mark.parametrize("mutation", ["episode", "duplicate", "missing", "denominator"])
def test_bad_overlap_rejected(mutation):
    episode, score = example()
    new_episode, new_score = deepcopy(episode), deepcopy(score)
    if mutation == "episode":
        new_episode["hidden_difference"] = True
    if mutation == "duplicate":
        new_score["per_checkpoint"] *= 2
    if mutation == "missing":
        new_score["per_checkpoint"] = []
    if mutation == "denominator":
        new_score["per_checkpoint"][0]["counts"]["known"] += 1
    with pytest.raises(ValueError):
        compare_overlap.matched_metrics([episode], [new_episode], score, new_score)
