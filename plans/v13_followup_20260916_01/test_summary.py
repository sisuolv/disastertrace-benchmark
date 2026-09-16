"""Independent scoring boundary checks for the new completion analysis."""
import pytest
from finalize import paired


def row(arm, p, y, oid="one"):
    return {"case":"case", "arm":arm, "opportunity_id":oid,
            "probability":p, "outcome":y, "loss":None if y is None else (p-y)**2}


def test_missing_y_bound_contains_both_possible_future_losses():
    rows = [row("a",.9,None),row("b",.1,None)]
    score = paired(rows,"a","b")
    assert score["registered"] == 1 and score["settled"] == 0
    assert score["all_opportunity_missing_Y_bound"] == pytest.approx([-.8,.8])


def test_positive_and_negative_effects_remain_separate():
    rows = [row("a",.9,1),row("b",.1,1),row("a",.9,0,"two"),row("b",.1,0,"two")]
    score = paired(rows,"a","b")
    assert score["settled_mean_gain"] == pytest.approx(0)
    assert score["positive_mean_gain"] == pytest.approx(-.8)
    assert score["negative_mean_gain"] == pytest.approx(.8)


def test_zero_effect_is_valid_without_synthetic_positive_gain():
    score = paired([row("a",.2,0),row("b",.2,0)],"a","b")
    assert score["settled_mean_gain"] == 0
    assert score["all_opportunity_missing_Y_bound"] == [0,0]


@pytest.mark.parametrize("rows",[
    [row("a",.2,0)],
    [row("a",.2,0),row("a",.2,0),row("b",.2,0)],
    [row("a",.2,None),row("b",.2,0)],
])
def test_denominator_and_common_mask_violations_are_not_silently_scored(rows):
    with pytest.raises(ValueError):
        paired(rows,"a","b")
