"""Regression checks for missing slots, repeat naming and matched comparisons."""

from copy import deepcopy

import pytest

from disastertrace.forecast_task.common import fingerprint
from disastertrace.role_review.analysis import compare, single_repeat_targets


def test_missing_checkpoint_prevents_single_repeat_whole_target_success():
    slots = [
        {"slot_id": str(i), "repeat": 0, "method": "snapshot", "episode_id": "a" if i < 2 else "b"}
        for i in range(3)
    ]
    scores = {
        "0": {"all_correct": True, "received": True},
        "1": {"all_correct": False, "received": False},
        "2": {"all_correct": True, "received": True},
    }
    assert single_repeat_targets(slots, scores) == {
        "snapshot": {
            "planned_targets": 2,
            "whole_target_single_repeat": 1,
            "fully_captured_targets": 1,
        }
    }
    with pytest.raises(ValueError, match="repeat0"):
        single_repeat_targets([{**slots[0], "repeat": 1}], {"0": scores["0"]})
    with pytest.raises(ValueError, match="coverage"):
        single_repeat_targets(slots, {"0": scores["0"]})


def fixture():
    metrics = (
        "received",
        "shape_valid",
        "key_correct",
        "status_correct",
        "current_source",
        "locator_correct",
        "all_correct",
    )
    record = {
        "slot_id": "slot",
        "opportunity_id": "opportunity",
        "episode_id": "episode",
        "storm_id": "storm",
        "method": "snapshot",
        "score": {key: False for key in metrics},
    }
    left = {
        "track": "default_spacing",
        "task_package_id": "task",
        "resource_package_id": "model",
        "model_profile": "qwen3",
        "matched_schedule_sha256": "schedule",
        "settings": {
            "dtype": "bfloat16",
            "structured_engine_options": {"guided_decoding_disable_any_whitespace": True},
        },
        "records": [record],
    }
    right = deepcopy(left)
    right["track"] = "qwen_user"
    right["settings"]["prompt_role_policy"] = "system_contract_prepended_to_user_v1"
    right["records"][0]["score"] = {key: True for key in metrics}
    return left, right


def sealed(value):
    value = {k: v for k, v in value.items() if k != "analysis_id"}
    return {**value, "analysis_id": fingerprint(value)}


def test_comparison_retains_missing_native_slot_in_full_denominator():
    before, after = fixture()
    result = compare(sealed(before), sealed(after))
    all_rows = result["paired_tables"]["all"]
    assert all_rows["planned"] == 1 and all_rows["system_received"] == 0
    assert all_rows["user_received"] == 1 and all_rows["pair_wrong_correct"] == 1
    assert all_rows["all_correct_difference_percentage_points"] == 100
    assert result["shared_prefix_causal_effect"] is False


@pytest.mark.parametrize(
    "change", ["schedule", "task", "resource", "dtype", "repeat_identity", "duplicate"]
)
def test_invalid_comparisons_are_rejected_even_with_resealed_documents(change):
    before, after = fixture()
    if change == "schedule":
        after["matched_schedule_sha256"] = "different"
    elif change == "task":
        after["task_package_id"] = "different"
    elif change == "resource":
        after["resource_package_id"] = "different"
    elif change == "dtype":
        after["settings"]["dtype"] = "float16"
    elif change == "repeat_identity":
        after["records"][0]["opportunity_id"] = "different"
    else:
        after["records"].append(deepcopy(after["records"][0]))
    with pytest.raises(ValueError):
        compare(sealed(before), sealed(after))
