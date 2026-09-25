from disastertrace.monitoring_v1.repair_trial_v21 import run_repair_trial


def test_v21_original_repair_sham_controller_has_semantic_negative_control():
    artifact = run_repair_trial()
    assert artifact["status"] == "APPLIED"
    assert artifact["sham_matches_original"] is True
    assert artifact["repair_changes_suffix"] is True
    assert artifact["sources_unchanged"] is True
    assert artifact["repair_witness"]["evicted"]["q0"]["reason"] == "content_differs_from_source"
