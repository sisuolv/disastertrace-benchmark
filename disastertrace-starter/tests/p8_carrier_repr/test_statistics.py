"""Paired direction and dependent denominators use every planned query."""

import pytest

from disastertrace.carrier_repr.statistics import paired
from disastertrace.forecast_task.common import read


def test_discordant_direction_missing_pairs_and_lengths_are_explicit(bundle):
    root, _, _, public, slots, _, _ = bundle
    selected = slots[:8]
    expected = [(True, True), (True, False), (False, True), (False, False)]
    scores, captures = {"records": []}, []
    for index, slot in enumerate(selected):
        correct = expected[index // 2][index % 2]
        scores["records"].append({"slot_id": slot["slot_id"], "score": {"all_correct": correct}})
        if index < 6:
            captures.append({"slot_id": slot["slot_id"], "prompt_tokens": 100 + 10 * (index % 2)})
    private = read(root / "task/data/private_reference.json")
    result = paired(selected, scores, public, private, captures)
    assert result["planned_pairs"] == 4 and result["text_minus_json_correct_count"] == 0
    assert set(result["counts"].values()) == {1} and len(result["counts"]) == 4
    assert result["capture_availability"] == {"both_captured": 3, "neither_captured": 1}
    assert result["captured_pair_prompt_token_difference"]["mean"] == 10
    scores["records"][2]["score"]["all_correct"] = False
    result = paired(selected, scores, public, private, captures)
    assert result["text_minus_json_accuracy"] == 0.25
    assert result["population_inference"] is False
    assert sum(sum(v.values()) for v in result["by_transition"].values()) == 4
    with pytest.raises(ValueError, match="denominator"):
        paired(selected, {"records": scores["records"][:-1]}, public, private, captures)
