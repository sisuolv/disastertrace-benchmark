import pytest

from disastertrace.monitoring_v1.grid_scoring_v18 import materialize_grid, score_complete_grid
from disastertrace.monitoring_v1.scoring import brier_report


def registrations():
    # One target has one binary Y.  This ordinary fixture previously encoded
    # the impossible settlement [0, 1, None] (audit F04); conflicting targets
    # are now covered only by the dedicated conflict test below.
    return [
        {"target_id": "t1", "method": "m1", "checkpoint_id": "c1", "checkpoint_index": 0, "base": 0.2, "fallback": 0.2, "outcome": 0},
        {"target_id": "t1", "method": "m1", "checkpoint_id": "c2", "checkpoint_index": 1, "base": 0.2, "fallback": 0.2, "outcome": 0},
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


def test_settled_target_conflict_is_excluded_from_qualified_score():
    def reg(target, cid, index, outcome, weight=1):
        return {"target_id": target, "method": "m", "checkpoint_id": cid, "checkpoint_index": index,
                "checkpoint_weight": weight, "base": 0.5, "fallback": 0.5, "outcome": outcome}

    def sub(target, cid, probability):
        return {"target_id": target, "method": "m", "checkpoint_id": cid, "status": "valid",
                "probability": probability}

    # Audit F04 minimal reproduction: one target, Y=[0,1], predictions=Y,
    # base 0.5, score weights 0.5 each.  Hand computation of the old
    # (now audit-only) all-row numbers: base loss 0.25 and loss 0 per row,
    # so gain 0.25 per row and bounds [0.25, 0.25].
    f04_regs = [reg("f04", "c0", 0, 0), reg("f04", "c1", 1, 1)]
    f04_subs = [sub("f04", "c0", 0.0), sub("f04", "c1", 1.0)]
    report = score_complete_grid(f04_regs, f04_subs)["report"]
    assert report["inconsistent_target_groups"] == 1
    assert report["inconsistent_target_group_rows_excluded"] == 2
    assert (report["opportunities"], report["settled"], report["missing"]) == (2, 0, 0)
    for field in ("base_brier", "system_brier", "net_realized_gain", "g_plus", "g_minus",
                  "full_population_gain_bounds"):
        assert report[field] is None, field
    assert report["qualified_score_weight_total"] == 0
    legacy = report["legacy_all_rows_including_conflicts"]
    assert legacy["audit_only"] is True and legacy["qualified"] is False
    assert legacy["system_brier"] == pytest.approx(0.0)
    assert legacy["net_realized_gain"] == pytest.approx(0.25)
    assert legacy["full_population_gain_bounds"] == pytest.approx([0.25, 0.25])

    # Same F04 target plus a mixed conflict/missing target and a clean target.
    # mixed: Y=[0,1,None], weights 1:1:2 -> 0.25, 0.25, 0.5; p=[0,1,0.9].
    # clean: Y=[1,None], weights 0.5 each; p=[0.8,0.6]; hidden Y is 1.
    regs = f04_regs + [
        reg("mixed", "c0", 0, 0), reg("mixed", "c1", 1, 1), reg("mixed", "c2", 2, None, weight=2),
        reg("clean", "c0", 0, 1), reg("clean", "c1", 1, None),
    ]
    subs = f04_subs + [
        sub("mixed", "c0", 0.0), sub("mixed", "c1", 1.0), sub("mixed", "c2", 0.9),
        sub("clean", "c0", 0.8), sub("clean", "c1", 0.6),
    ]
    report = score_complete_grid(regs, subs)["report"]
    assert report["inconsistent_target_groups"] == 2
    assert report["inconsistent_target_group_rows_excluded"] == 5
    assert (report["opportunities"], report["settled"], report["missing"]) == (7, 1, 1)
    assert report["missing_target_groups"] == 1
    # Qualified score = clean target only.  clean c0: base loss 0.25,
    # loss (0.8-1)^2 = 0.04, gain 0.21.  clean c1 with Y=1:
    # gain 0.25 - (0.6-1)^2 = 0.09.  Bounds 0.5*0.21 + 0.5*0.09 = 0.15.
    assert report["base_brier"] == pytest.approx(0.25)
    assert report["system_brier"] == pytest.approx(0.04)
    assert report["net_realized_gain"] == pytest.approx(0.21)
    assert report["g_plus"] == pytest.approx(0.21)
    assert report["g_minus"] == pytest.approx(0.0)
    assert report["full_population_gain_bounds"] == pytest.approx([0.15, 0.15])
    assert report["qualified_score_weight_total"] == pytest.approx(1.0)
    assert report["score_weight_total"] == pytest.approx(3.0)
    # Audit-only all-row view.  Settled rows (weight, gain): f04 (0.5, 0.25)
    # x2, mixed (0.25, 0.25) x2, clean (0.5, 0.21); total weight 2.0, weighted
    # gain 0.48, weighted loss 0.5*0.04 = 0.02.  Missing: mixed c2 independent
    # Y gives 0.5*[-0.56, 0.24] = [-0.28, 0.12]; clean c1 gives 0.045.
    # Bounds [(0.48-0.28+0.045)/3, (0.48+0.12+0.045)/3] = [0.245/3, 0.215].
    legacy = report["legacy_all_rows_including_conflicts"]
    assert (legacy["settled"], legacy["missing"], legacy["missing_target_groups"]) == (5, 2, 2)
    assert legacy["system_brier"] == pytest.approx(0.01)
    assert legacy["net_realized_gain"] == pytest.approx(0.24)
    assert legacy["full_population_gain_bounds"] == pytest.approx([0.245 / 3, 0.215])


def test_falsy_target_id_is_rejected_not_silently_dropped():
    # target_id=0 or "" is a present-but-falsy value that `if target_id` would
    # silently discard, collapsing the row into a singleton opportunity-level
    # group as if no target_id had ever been supplied. That must be a loud
    # error, not a quiet behavior change.
    for bad_target_id in (0, ""):
        row = {
            "opportunity_id": "opp-1", "target_id": bad_target_id, "base": 0.5,
            "prediction": 0.5, "outcome": 0,
        }
        with pytest.raises(ValueError, match="target_id must not be"):
            brier_report([row])
    # None (or omitting the key) is the legitimate "no target_id" case and must
    # still work exactly as before.
    row = {"opportunity_id": "opp-1", "target_id": None, "base": 0.5, "prediction": 0.5, "outcome": 0}
    assert brier_report([row])["settled"] == 1
    row_no_key = {"opportunity_id": "opp-2", "base": 0.5, "prediction": 0.5, "outcome": 0}
    assert brier_report([row_no_key])["settled"] == 1


def test_target_id_colliding_with_another_rows_opportunity_id_is_rejected():
    # Row A explicitly declares target_id="opp-2". Row B has no target_id and
    # therefore falls back to using its own opportunity_id, "opp-2", as its
    # group key. Without a check, these two semantically-unrelated rows would
    # silently merge into one target group.
    rows = [
        {"opportunity_id": "opp-1", "target_id": "opp-2", "base": 0.5, "prediction": 0.5, "outcome": 0},
        {"opportunity_id": "opp-2", "base": 0.5, "prediction": 0.5, "outcome": 0},
    ]
    with pytest.raises(ValueError, match="collides with another row's opportunity_id"):
        brier_report(rows)
