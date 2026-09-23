"""Source semantics and hidden-information boundaries of the fixed C2 bridge."""

import json
from pathlib import Path

import pytest

from disastertrace.monitoring_fixed_v1.aviation import visible_e_status
from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle
from disastertrace.monitoring_fixed_v1.support_bridge import (
    certified_metadata,
    compile_recipes,
    native_slot_support,
    subset_bundle,
    taf_coverage,
)

MATRIX = (
    Path(__file__).resolve().parents[2] / "plans/v7_execution_20260913/evidence_bundle/matrix_01"
)


def real_bundle():
    rows = json.loads((MATRIX / "MANIFEST.json").read_text())
    row = next(r for r in rows if r["condition"] == "all_registered")
    return EvidenceBundle.restore(
        json.loads((MATRIX / "policy" / (row["call_id"] + ".json")).read_text())
    )


def test_bridge_recomputes_native_disclosed_intervals_and_keeps_missing_slots():
    b = real_bundle()
    assert native_slot_support(b)["status"] == visible_e_status(b)
    assert native_slot_support(subset_bundle(b, []))["status"] == "undetermined"
    assert native_slot_support(b)["support_scope"] == "native_report_label_only"


def test_forged_parsed_value_is_not_certified_by_reference_metadata():
    row = real_bundle().policy_view()
    row["assets"][0]["content"]["reports"][0]["visibility"]["lower"] = 0
    with pytest.raises(ValueError, match="Native"):
        native_slot_support(EvidenceBundle.freeze(row))


def test_future_acquisition_does_not_enter_current_support():
    b = real_bundle()
    at = min(a["completed_at"] for a in b.policy_view()["assets"]) - 1
    assert native_slot_support(b, at=at)["status"] == "undetermined"


def test_reference_enum_conversion_is_not_a_string_rename():
    assert certified_metadata("product_label", "product_exact", "policy_after_query") == (
        "product_label",
        "product_exact",
        "policy",
    )
    assert certified_metadata("measurement", "bounded_error", "policy_after_query") == (
        "measurement",
        "bounded_measurement",
        "policy",
    )
    for args in [
        ("raw_sensor", "product_exact", "policy_after_query"),
        ("product_label", "product_exact", "evaluator"),
        ("measurement", "product_exact", "policy_after_query"),
    ]:
        with pytest.raises(ValueError):
            certified_metadata(*args)


def test_taf_coverage_reparsed_from_full_native_product():
    report = taf_coverage(real_bundle())
    assert report["status"] == "supported"
    assert report["coverage_fraction"] == 1
    assert report["model_head_qualified"] is False


def test_taf_unknown_operator_is_explicitly_unsupported():
    row = real_bundle().policy_view()
    row["baseline"]["content"]["native_taf"]["raw"] = row["baseline"]["content"]["native_taf"][
        "raw"
    ].replace("=", " UNKNOWN_OPERATOR=")
    report = taf_coverage(EvidenceBundle.freeze(row))
    assert report["status"] == "unsupported"


def test_recipes_are_minimal_finite_and_not_in_policy_view():
    b = real_bundle()
    recipes = compile_recipes(b)
    assert recipes
    for recipe in recipes:
        assert native_slot_support(subset_bundle(b, recipe))["status"] in {"supported", "refuted"}
        for qid in recipe:
            assert native_slot_support(subset_bundle(b, recipe - {qid}))["status"] == "undetermined"
    assert "recipes" not in b.policy_view()


def test_native_report_censoring_is_not_a_physical_measurement_error_bound():
    row = real_bundle().policy_view()
    row["assets"][0]["reference_kind"] = "measurement"
    row["assets"][0]["support_assumption"] = "bounded_error"
    with pytest.raises(ValueError, match="report-label"):
        native_slot_support(EvidenceBundle.freeze(row))
