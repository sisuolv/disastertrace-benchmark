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


def test_flipped_is_amendment_alone_is_not_a_target_content_change():
    """Track B-0 (v20 plan): is_amendment/ftype/source_row_is_tempo are
    excluded from comparison_content_only() -- the change-detection hash --
    so an identical forecast re-issued with is_amendment flipped True->False
    is not misclassified as TARGET_CONTENT_CHANGE. This is deliberately a
    NARROWER exclusion than weather_content_only() (the agent-visible
    projection) uses -- see test_current_projection_still_shows_is_amendment
    below: these fields must stay visible to an agent even though they don't
    affect the comparison. An earlier version of this fix wrongly stripped
    them from the agent view too; corrected after independent review."""
    same_period = {
        "valid_start": 100, "valid_end": 200, "visibility_m": 8000,
        "is_amendment": True, "ftype": "Forecast", "source_row_is_tempo": False,
    }
    other_period = dict(same_period, is_amendment=False, ftype="Correction", source_row_is_tempo=True)
    result = qualify_evidence(
        record(source_revision="r2", content={"periods": [other_period]}),
        record(content={"periods": [same_period]}),
        target_start=TARGET_START,
        target_end=TARGET_END,
        as_of=30,
    )
    assert result.status == "SOURCE_CHANGE_NO_TARGET_CHANGE"
    assert result.target_content_change is False


def test_current_projection_still_shows_is_amendment_and_ftype_to_the_agent():
    """Track B-0 correction (v20 plan): comparison_content_only() only
    affects the internal change-detection hash. witness["current_projection"]
    -- what public_checkpoint/public_prefix actually send to an agent -- must
    still include is_amendment/ftype/source_row_is_tempo. An agent that can
    no longer tell whether a TAF was amended is a real, undisclosed
    regression the first version of this fix introduced silently."""
    period = {
        "valid_start": 100, "valid_end": 200, "visibility_m": 8000,
        "is_amendment": True, "ftype": "Forecast", "source_row_is_tempo": False,
    }
    result = qualify_evidence(
        record(content={"periods": [period]}), None,
        target_start=TARGET_START, target_end=TARGET_END, as_of=30,
    )
    shown_period = result.witness["current_projection"]["periods"][0]
    assert shown_period["is_amendment"] is True
    assert shown_period["ftype"] == "Forecast"
    assert shown_period["source_row_is_tempo"] is False


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


def test_known_arrival_reordering_is_rejected_across_unknown_availability():
    with pytest.raises(ValueError, match="chronological"):
        qualify_stream(
            [
                record(source_revision="r1", available_at=20),
                record(source_revision="r-unknown", available_at=None),
                record(source_revision="r0", available_at=10),
            ],
            target_start=TARGET_START,
            target_end=TARGET_END,
            as_of=30,
        )
