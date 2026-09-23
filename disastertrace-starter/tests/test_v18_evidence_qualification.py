from disastertrace.monitoring_v1.evidence_qualification_v18 import (
    EvidenceRecord,
    qualify_evidence,
    qualify_stream,
    target_content_projection,
)
import pytest


TARGET_START = 100
TARGET_END = 200


def record(**changes):
    row = {
        "source_id": "taf-kden",
        "source_revision": "r1",
        "kind": "taf",
        "issued_at": 10,
        "available_at": 20,
        "valid_start": 100,
        "valid_end": 200,
        "content": {"periods": [{"valid_start": 100, "valid_end": 200, "visibility_m": 8000}]},
    }
    row.update(changes)
    return row


def test_ordinary_new_taf_target_content_change_is_not_no_change():
    result = qualify_evidence(
        record(source_revision="r2", content={"periods": [{"valid_start": 100, "valid_end": 200, "visibility_m": 4000}]}),
        record(),
        target_start=TARGET_START,
        target_end=TARGET_END,
        as_of=30,
    )
    assert result.status == "TARGET_CONTENT_CHANGE"
    assert result.source_change is True
    assert result.target_content_change is True


def test_source_revision_with_only_transport_metadata_is_separate():
    result = qualify_evidence(
        record(source_revision="r2", content={"periods": [{"valid_start": 100, "valid_end": 200, "visibility_m": 8000}]}),
        record(),
        target_start=TARGET_START,
        target_end=TARGET_END,
        as_of=30,
    )
    assert result.status == "SOURCE_CHANGE_NO_TARGET_CHANGE"
    assert result.target_content_change is False


def test_outside_target_update_does_not_become_target_change():
    result = qualify_evidence(
        record(
            source_revision="r2",
            valid_start=300,
            valid_end=400,
            content={"periods": [{"valid_start": 300, "valid_end": 400, "visibility_m": 100}]},
        ),
        record(),
        target_start=TARGET_START,
        target_end=TARGET_END,
        as_of=30,
    )
    assert result.status == "TARGET_IRRELEVANT_CHANGE"
    assert result.target_content_change is False


def test_unknown_availability_is_not_silent_no_change():
    result = qualify_evidence(
        record(source_revision="r2", available_at=None),
        record(),
        target_start=TARGET_START,
        target_end=TARGET_END,
        as_of=30,
    )
    assert result.status == "UNKNOWN_AVAILABILITY"
    assert result.availability == "unknown"
    assert result.target_content_change is None


def test_issued_time_does_not_make_future_record_visible():
    result = qualify_evidence(
        record(issued_at=1, available_at=50, source_revision="r2"),
        record(),
        target_start=TARGET_START,
        target_end=TARGET_END,
        as_of=30,
    )
    assert result.status == "NOT_YET_AVAILABLE"
    assert result.availability == "not_yet_available"


def test_stream_retains_duplicate_and_projection_witness():
    rows = qualify_stream(
        [record(), record()], target_start=TARGET_START, target_end=TARGET_END, as_of=30
    )
    assert [row.status for row in rows] == ["NEW_TARGET_CONTENT", "DUPLICATE"]
    assert rows[1].witness["current_projection"]["periods"][0]["visibility_m"] == 8000


def test_projection_filters_non_overlapping_periods():
    projected = target_content_projection(
        EvidenceRecord.from_mapping(
            record(
                content={
                    "periods": [
                        {"valid_start": 0, "valid_end": 50, "visibility_m": 100},
                        {"valid_start": 100, "valid_end": 200, "visibility_m": 8000},
                    ]
                }
            )
        ),
        TARGET_START,
        TARGET_END,
    )
    assert projected["content"]["periods"] == [
        {"valid_start": 100, "valid_end": 200, "visibility_m": 8000}
    ]


def test_stream_rejects_reordered_arrivals():
    with pytest.raises(ValueError, match="chronological"):
        qualify_stream(
            [record(issued_at=20), record(issued_at=10)],
            target_start=TARGET_START,
            target_end=TARGET_END,
            as_of=30,
        )


def test_missing_identity_is_rejected_instead_of_stringifying_none():
    with pytest.raises(ValueError, match="identity"):
        EvidenceRecord.from_mapping(record(source_revision=None))


def test_same_time_distinct_arrivals_require_an_explicit_tiebreak():
    with pytest.raises(ValueError, match="same chronology"):
        qualify_stream(
            [record(), record(source_revision="r2")],
            target_start=TARGET_START,
            target_end=TARGET_END,
            as_of=30,
        )


def test_same_identity_changed_content_is_a_conflict():
    with pytest.raises(ValueError, match="Conflicting content"):
        qualify_stream(
            [record(), record(content={"periods": [{"valid_start": 100, "valid_end": 200, "visibility_m": 4000}]})],
            target_start=TARGET_START,
            target_end=TARGET_END,
            as_of=30,
        )
