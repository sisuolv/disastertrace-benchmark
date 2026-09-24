from scripts.build_v19_offline_gate import build


def test_offline_gate_contains_shared_y_and_process_denominator(tmp_path):
    artifact = build(tmp_path)
    assert artifact["status"] == "OFFLINE_READY"
    assert artifact["provider_calls"] == 0
    assert artifact["grid"]["registered"] == 4
    assert artifact["grid"]["status_counts"]["not_dispatched"] == 1
    assert artifact["conflict_isolated"] == 1
    assert artifact["natural"]["terminal"] is True
