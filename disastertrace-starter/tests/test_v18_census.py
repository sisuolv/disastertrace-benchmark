import pytest

from disastertrace.monitoring_v1.census_v18 import evidence_census


def q(status, source_change, content_change, availability="available"):
    return {
        "status": status,
        "source_change": source_change,
        "target_content_change": content_change,
        "availability": availability,
    }


def test_census_has_separate_source_and_content_denominators():
    report = evidence_census(
        [
            {"episode_id": "e1", "qualifications": [q("NEW_TARGET_CONTENT", True, True), q("DUPLICATE", False, False)]},
            {"episode_id": "e2", "qualifications": [q("UNKNOWN_AVAILABILITY", True, None, "unknown")]},
        ]
    )
    assert report["episode_denominator"] == 2
    assert report["evidence_row_denominator"] == 3
    assert report["source_change_rows"] == 2
    assert report["target_content_change_rows"] == 1
    assert report["unknown_target_content_rows"] == 1
    assert report["status_counts"]["UNKNOWN_AVAILABILITY"] == 1


def test_census_rejects_duplicate_episode_identity():
    with pytest.raises(ValueError, match="Duplicate"):
        evidence_census([
            {"episode_id": "e1", "qualifications": [q("DUPLICATE", False, False)]},
            {"episode_id": "e1", "qualifications": [q("DUPLICATE", False, False)]},
        ])
