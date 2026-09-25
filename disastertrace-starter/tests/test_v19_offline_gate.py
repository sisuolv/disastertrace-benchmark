from scripts.build_v19_offline_gate import build


def test_offline_gate_contains_shared_y_and_process_denominator(tmp_path):
    artifact = build(tmp_path)
    assert artifact["status"] == "OFFLINE_READY"
    assert artifact["provider_calls"] == 0
    assert artifact["grid"]["registered"] == 4
    assert artifact["grid"]["status_counts"]["not_dispatched"] == 1
    assert artifact["conflict_isolated"] == 1
    assert artifact["natural"]["terminal"] is True


def test_offline_gate_exercises_the_real_checkpoint_grid_and_y1_adapter(tmp_path):
    """Track E (v20 plan): roster construction (the real T-60/T-40/T-20
    qualifier) and outcome settlement (the real Y1 adapter) chained
    end-to-end, entirely offline -- neither claim is new; this proves the
    two pieces actually compose, not just that each works in isolation."""
    artifact = build(tmp_path)
    assert artifact["checkpoint_grid"]["checkpoint_ids"] == ["T-60", "T-40", "T-20"]
    assert artifact["checkpoint_grid"]["excluded_checkpoints"] == 0
    assert artifact["synthetic_outcome_settled"] is True
    assert artifact["synthetic_outcome_availability_basis"] == "synthetic_fixture"
    assert artifact["outcomes_accessed"] is False  # settling a synthetic outcome is not real access
    assert artifact["api_capture_module_imported"] is False
