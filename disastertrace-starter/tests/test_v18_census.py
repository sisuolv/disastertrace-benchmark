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


def test_census_uses_only_the_last_checkpoint_on_a_v3_roster_not_all_three():
    # A v3 (T-60/T-40/T-20) episode re-qualifies the same 2-row stream at each
    # checkpoint, with visibility only growing. Counting every checkpoint
    # would triple the row denominator for the same underlying evidence; the
    # census must use only the last (most complete) checkpoint.
    episode = {
        "episode_id": "e1",
        "checkpoints": [
            {"checkpoint_id": "T-60", "qualifications": [q("NEW_TARGET_CONTENT", True, True)]},
            {
                "checkpoint_id": "T-40",
                "qualifications": [q("NEW_TARGET_CONTENT", True, True), q("NOT_YET_AVAILABLE", False, None, "unknown")],
            },
            {
                "checkpoint_id": "T-20",
                "qualifications": [q("NEW_TARGET_CONTENT", True, True), q("TARGET_CONTENT_CHANGE", True, True)],
            },
        ],
    }
    report = evidence_census([episode])
    assert report["evidence_row_denominator"] == 2  # T-20's row count, not 1+2+2=5
    assert report["episode_rows"][0]["status_counts"] == {"NEW_TARGET_CONTENT": 1, "TARGET_CONTENT_CHANGE": 1}


def test_census_rejects_a_v3_episode_whose_last_checkpoint_has_no_qualifications():
    with pytest.raises(ValueError, match="Every episode needs qualification rows"):
        evidence_census([{"episode_id": "e1", "checkpoints": [{"checkpoint_id": "T-20", "qualifications": []}]}])
