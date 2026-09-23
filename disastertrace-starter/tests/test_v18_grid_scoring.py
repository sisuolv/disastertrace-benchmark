import pytest

from disastertrace.monitoring_v1.grid_scoring_v18 import materialize_grid, score_complete_grid


def registrations():
    return [
        {"target_id": "t1", "method": "m1", "checkpoint_id": "c1", "checkpoint_index": 0, "base": 0.2, "fallback": 0.2, "outcome": 0},
        {"target_id": "t1", "method": "m1", "checkpoint_id": "c2", "checkpoint_index": 1, "base": 0.2, "fallback": 0.2, "outcome": 1},
        {"target_id": "t1", "method": "m1", "checkpoint_id": "c3", "checkpoint_index": 2, "base": 0.2, "fallback": 0.2, "outcome": None},
    ]


def test_registered_denominator_survives_missing_and_invalid():
    result = score_complete_grid(
        registrations(),
        [
            {"target_id": "t1", "method": "m1", "checkpoint_id": "c1", "status": "valid", "probability": 0.1},
            {"target_id": "t1", "method": "m1", "checkpoint_id": "c2", "status": "invalid", "probability": "bad"},
        ],
    )
    assert result["registered"] == 3
    assert result["scored"] == 3
    assert result["valid_submissions"] == 1
    assert result["carry_forward"] == 2
    assert result["fallback"] == 0
    assert result["submission_status_counts"] == {"invalid": 1, "missing": 1, "valid": 1}
    assert result["report"]["opportunities"] == 3
    assert result["report"]["missing"] == 1


def test_invalid_current_cell_does_not_erase_prior_valid_prediction():
    rows = materialize_grid(
        registrations(),
        [
            {"target_id": "t1", "method": "m1", "checkpoint_id": "c1", "status": "valid", "probability": 0.7},
            {"target_id": "t1", "method": "m1", "checkpoint_id": "c2", "status": "invalid"},
        ],
    )
    assert rows[1]["prediction"] == 0.7
    assert rows[1]["prediction_source"] == "carry_forward"
    assert rows[1]["submission_valid"] is False


def test_unregistered_or_duplicate_cells_are_rejected():
    with pytest.raises(ValueError, match="not registered"):
        materialize_grid(registrations(), [{"target_id": "t1", "method": "m2", "checkpoint_id": "c1", "status": "valid", "probability": 0.2}])
    with pytest.raises(ValueError, match="Duplicate registered"):
        materialize_grid(registrations() + [dict(registrations()[0])], [])


def test_missing_outcome_is_shared_in_complete_grid():
    result = score_complete_grid(registrations(), [])
    assert result["report"]["missing"] == 1
    assert result["report"]["opportunities"] == 3


def test_carry_forward_uses_checkpoint_order_not_registration_order():
    rows = registrations()
    result = materialize_grid(list(reversed(rows)), [
        {"target_id": "t1", "method": "m1", "checkpoint_id": "c1", "status": "valid", "probability": 0.7},
    ])
    assert [row["checkpoint_id"] for row in result] == ["c1", "c2", "c3"]
    assert [row["prediction_source"] for row in result] == ["submission", "carry_forward", "carry_forward"]


def test_shared_missing_target_y_uses_joint_completion_bounds():
    rows = [
        {"target_id": "t", "method": "m", "checkpoint_id": "c1", "checkpoint_index": 0, "base": 0.2, "fallback": 0.2, "outcome": None},
        {"target_id": "t", "method": "m", "checkpoint_id": "c2", "checkpoint_index": 1, "base": 0.2, "fallback": 0.2, "outcome": None},
    ]
    result = score_complete_grid(rows, [
        {"target_id": "t", "method": "m", "checkpoint_id": "c1", "status": "valid", "probability": 0.0},
        {"target_id": "t", "method": "m", "checkpoint_id": "c2", "status": "valid", "probability": 1.0},
    ])
    assert result["report"]["full_population_gain_bounds"] == pytest.approx([-0.46, 0.14])
    assert result["report"]["missing_target_groups"] == 1


def test_boolean_outcome_is_not_a_binary_outcome():
    bad = dict(registrations()[0], outcome=True)
    with pytest.raises(ValueError, match="Outcome"):
        materialize_grid([bad], [])


def test_float_outcome_and_negative_checkpoint_are_rejected():
    with pytest.raises(ValueError, match="Outcome"):
        materialize_grid([dict(registrations()[0], outcome=0.0)], [])
    with pytest.raises(ValueError, match="checkpoint_index"):
        materialize_grid([dict(registrations()[0], checkpoint_index=-1)], [])


def test_pending_outcome_defaults_to_none():
    row = dict(registrations()[0])
    row.pop("outcome")
    result = materialize_grid([row], [])
    assert result[0]["outcome"] is None


def test_checkpoint_weights_are_normalized_within_each_trajectory():
    rows = [
        {"target_id": "t", "method": "m", "checkpoint_id": "c1", "checkpoint_index": 0, "checkpoint_weight": 1, "base": 0.2, "fallback": 0.2, "outcome": None},
        {"target_id": "t", "method": "m", "checkpoint_id": "c2", "checkpoint_index": 1, "checkpoint_weight": 3, "base": 0.2, "fallback": 0.2, "outcome": None},
    ]
    result = score_complete_grid(rows, [
        {"target_id": "t", "method": "m", "checkpoint_id": "c1", "status": "valid", "probability": 0.0},
        {"target_id": "t", "method": "m", "checkpoint_id": "c2", "status": "valid", "probability": 1.0},
    ])
    assert [row["score_weight"] for row in result["rows"]] == pytest.approx([0.25, 0.75])
    assert result["report"]["full_population_gain_bounds"] == pytest.approx([-0.71, 0.39])
    assert result["report"]["score_weight_total"] == pytest.approx(1.0)
