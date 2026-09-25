import pytest

from disastertrace.monitoring_v1.natural_synthetic_score_v21 import run_score


def test_v21_natural_score_preserves_process_failures_and_common_roster(tmp_path):
    artifact = run_score(tmp_path / "score.json")
    assert artifact["settled"]["comparison_eligible"] is True
    assert artifact["settled"]["methods"] == ["fixed", "no_extra", "source_rr", "source_hash", "active"]
    assert artifact["failure_denominator"]["active_carry_forward_cells"] == 3
    assert artifact["failure_denominator"]["fixed_invalid_cells"] == 3
    assert artifact["failure_denominator"]["registered"] == 45
    assert all(item["comparison_eligible"] for item in artifact["cases"])


def test_v21_active_value_is_conditional_and_harm_case_is_retained(tmp_path):
    artifact = run_score(tmp_path / "score.json")
    cases = {item["case_id"]: item for item in artifact["cases"]}
    assert cases["signal_low"]["method_losses"]["active"] < cases["signal_low"]["method_losses"]["fixed"]
    assert cases["signal_high"]["method_losses"]["active"] < cases["signal_high"]["method_losses"]["fixed"]
    assert cases["signal_mismatch"]["method_losses"]["active"] > cases["signal_mismatch"]["method_losses"]["fixed"]


def test_v21_missing_y_probe_uses_one_target_outcome_for_all_checkpoints(tmp_path):
    artifact = run_score(tmp_path / "score.json")
    probe = artifact["missing_y_probe"]
    assert probe["opportunities"] == 45
    assert probe["missing"] == 45
    assert probe["missing_target_groups"] == 3
    assert probe["lower"] < probe["upper"]


def test_v21_active_is_compared_to_nonadaptive_controls_on_the_same_f(tmp_path):
    artifact = run_score(tmp_path / "score.json")
    mean_losses = artifact["settled"]["mean_loss_by_method"]
    assert mean_losses["active"] == pytest.approx(0.24)
    assert mean_losses["source_rr"] > mean_losses["active"]
    # This small fixture deliberately does not establish an active-policy
    # advantage over every non-adaptive control; the best non-active arm ties
    # it. That result is retained as a go/no-go diagnostic.
    assert artifact["settled"]["active_minus_best_non_active"] == 0.0
