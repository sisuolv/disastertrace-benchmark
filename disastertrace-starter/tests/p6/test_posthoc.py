"""Known counterexamples for the new overlay; the historical scorer stays unchanged."""

from copy import deepcopy

import pytest

from disastertrace.controlled.compiler import reference_at
from disastertrace.controlled.generator import micro_episodes
from disastertrace.controlled.renderer import render_request
from disastertrace.controlled.schema import FIELDS
from disastertrace.post_p5.citations import classify_field
from disastertrace.post_p5.exposure import compare_evidence, exposure_series
from disastertrace.post_p5.policies import solve


@pytest.fixture
def episode():
    return next(
        e
        for e in micro_episodes()
        if e["family"] == "U1" and e["case"] == "primary" and e["branch"] == "active"
    )


@pytest.fixture
def item(episode):
    request = render_request(episode, "c4", method="snapshot")
    gold = reference_at(episode, "c4")["state"][FIELDS[0]]
    return request, gold


@pytest.mark.parametrize(
    "change,reason",
    [
        ("missing", "missing_citation"),
        ("unknown", "unknown_record_id"),
        ("bounds", "out_of_bounds_line"),
        ("header", "non_assertion_or_unparseable_line"),
        ("wrong_field", "wrong_variable_or_unit"),
        ("stale", "superseded_different_value"),
    ],
)
def test_reference_failure_taxonomy(item, change, reason):
    request, gold = item
    predicted = deepcopy(gold)
    ref = predicted["evidence"][0]
    if change == "missing":
        predicted["evidence"] = []
    elif change == "unknown":
        ref["record_id"] = "unknown-record"
    elif change == "bounds":
        ref["line"] = 1000
    elif change == "header":
        ref["line"] = 1
    elif change == "wrong_field":
        predicted["evidence"] = [{"record_id": request["evidence"][0]["record_id"], "line": 3}]
    else:
        predicted["evidence"] = [{"record_id": request["evidence"][0]["record_id"], "line": 2}]
    result = classify_field(request, FIELDS[0], predicted, gold)
    assert result["legacy_value_correct"] and not result["legacy_grounded_correct"]
    assert result["primary_error"] == reason


def test_undelivered_record_is_not_rescued_by_private_catalogue(episode):
    request = render_request(episode, "c1", method="snapshot")
    gold = reference_at(episode, "c1")["state"][FIELDS[0]]
    predicted = deepcopy(gold)
    future_id = episode["records"][1]["record_id"]
    predicted["evidence"] = [{"record_id": future_id, "line": 2}]
    row = classify_field(request, FIELDS[0], predicted, gold, all_record_ids={future_id})
    assert row["primary_error"] == "record_not_in_public_view"
    assert row["citation_details"][0]["assertion"] is None


def test_same_value_revision_still_requires_fresh_source():
    ep = next(e for e in micro_episodes() if e["family"] == "U1" and e["case"] == "secondary")
    request = render_request(ep, "c2", method="snapshot")
    gold = reference_at(ep, "c2")["state"][FIELDS[0]]
    predicted = reference_at(ep, "c1")["state"][FIELDS[0]]
    row = classify_field(request, FIELDS[0], predicted, gold, previous=predicted)
    assert row["primary_error"] == "superseded_same_value"
    assert row["cited_value_supported"] is True
    assert row["flags"]["matches_previous_carrier_reference"] is True


def test_mixed_and_duplicate_references_do_not_multiply_field_denominator(item):
    request, gold = item
    predicted = deepcopy(gold)
    predicted["evidence"] += deepcopy(predicted["evidence"])
    predicted["evidence"].append({"record_id": "unknown-record", "line": 2})
    row = classify_field(request, FIELDS[0], predicted, gold)
    assert row["primary_error"] == "unknown_record_id"
    assert row["flags"]["has_valid_and_invalid_citations"]
    assert row["flags"]["duplicate_references"]
    assert len(row["citation_details"]) == 3


def test_value_error_not_double_counted_as_citation_only(item):
    request, gold = item
    predicted = deepcopy(gold)
    predicted["value"] += 1
    predicted["evidence"] = []
    row = classify_field(request, FIELDS[0], predicted, gold)
    assert row["primary_error"] == "status_or_value_mismatch"
    assert not row["citation_only_error"]


@pytest.mark.parametrize("status", ["invalid", "unsubmitted", "attempted_unresolved"])
def test_missing_and_invalid_are_separate_from_citation_failures(item, status):
    request, gold = item
    row = classify_field(request, FIELDS[0], None, gold, status=status)
    assert row["primary_error"] == status and not row["citation_only_error"]


def test_modified_existing_text_counts_as_exposure(episode):
    request = render_request(episode, "c2", method="snapshot")
    changed = deepcopy(request)
    changed["evidence"][1]["text"] += " "
    result = compare_evidence(request, changed)
    assert result["new_unique_records"] == 0
    assert result["modified_existing_records"] == 1 and result["added_factor_visible"]


def test_exposure_partition_and_zero_effect(episode):
    base = [render_request(episode, f"c{i}", method="snapshot") for i in range(5)]
    altered = deepcopy(base)
    altered[4]["evidence"].append({**altered[4]["evidence"][0], "delivery_id": "extra"})
    rows = exposure_series(base, altered)
    assert [r["exposure_status"] for r in rows] == ["before_first_exposure"] * 4 + ["exposed"]
    assert all(r["first_exposed_checkpoint"] == "c4" for r in rows)
    assert {r["exposure_status"] for r in exposure_series(base, base)} == {"never_exposed"}


@pytest.mark.parametrize("method", ["snapshot", "structured_state", "answer_history"])
def test_latest_issued_matches_independent_compiler_on_current_domain(method):
    for ep in micro_episodes():
        for cp in ep["checkpoints"]:
            request = render_request(ep, cp["checkpoint_id"], method=method)
            assert solve(request, "latest_issued_per_key") == reference_at(ep, cp["checkpoint_id"])


def test_latest_delivery_is_distinguishable_without_changing_valid_solver(episode):
    request = render_request(episode, "c4", method="snapshot")
    assert solve(request, "last_delivered") != reference_at(episode, "c4")
    assert solve(request, "latest_issued_per_key") == reference_at(episode, "c4")


def test_policy_must_not_receive_hidden_catalogue(episode):
    request = render_request(episode, "c1", method="snapshot")
    request["private_reference"] = reference_at(episode, "c4")
    with pytest.raises(ValueError):
        solve(request, "latest_issued_per_key")
