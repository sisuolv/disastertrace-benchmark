from disastertrace.monitoring_v1.interventions_v18 import apply_intervention


def parent():
    return [
        {
            "source_id": "s",
            "source_revision": "r1",
            "kind": "taf",
            "issued_at": 1,
            "available_at": 2,
            "valid_start": 100,
            "valid_end": 200,
            "content": {"periods": [{"valid_start": 100, "valid_end": 200, "visibility_m": 8000}]},
        },
        {
            "source_id": "s",
            "source_revision": "r2",
            "kind": "taf",
            "issued_at": 3,
            "available_at": 4,
            "valid_start": 100,
            "valid_end": 200,
            "content": {"periods": [{"valid_start": 100, "valid_end": 200, "visibility_m": 4000}]},
        },
    ]


def test_identity_repeat_is_duplicate_and_keeps_content():
    result = apply_intervention(parent(), "identity_repeat", target_start=100, target_end=200, as_of=10)
    assert result.qualification[-1]["status"] == "DUPLICATE"
    assert result.held_fields == ["target_start", "target_end", "issued_at"]


def test_matched_sham_does_not_change_target_projection():
    result = apply_intervention(parent(), "matched_sham", target_start=100, target_end=200, as_of=10)
    assert result.qualification[-1]["status"] == "SOURCE_CHANGE_NO_TARGET_CHANGE"


def test_delay_is_not_natural_no_change():
    result = apply_intervention(parent(), "delay", target_start=100, target_end=200, as_of=10)
    assert result.qualification[-1]["status"] == "NOT_YET_AVAILABLE"
