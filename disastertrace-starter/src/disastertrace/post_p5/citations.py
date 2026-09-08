"""Deterministic citation attribution, separate from the frozen primary score."""

import hashlib
import re

from disastertrace.automated.common import canonical, strict_json
from disastertrace.controlled.public_oracle import parse_evidence
from disastertrace.controlled.schema import UNITS

PRIORITY = (
    "missing_citation",
    "record_not_in_public_view",
    "unknown_record_id",
    "out_of_bounds_line",
    "non_assertion_or_unparseable_line",
    "wrong_entity",
    "wrong_valid_window_or_measurement_kind",
    "wrong_variable_or_unit",
    "superseded_different_value",
    "superseded_same_value",
    "wrong_value_on_same_key",
    "other_unverifiable",
)


def classify_field(
    request,
    field,
    predicted,
    expected,
    *,
    all_record_ids=(),
    previous=None,
    earlier_correct_refs=(),
    status="ok",
):
    value_ok = predicted is not None and (predicted["status"], predicted["value"]) == (
        expected["status"],
        expected["value"],
    )
    refs = [] if predicted is None else predicted["evidence"]
    known = expected["status"] == "known"
    grounded = value_ok and (
        not known or bool(refs) and all(r in expected["evidence"] for r in refs)
    )
    records = {r["record_id"]: r for r in request["evidence"]}
    entries = parse_evidence(request)
    superseded = {e["assertion"]["supersedes"] for e in entries}
    details = []
    for ref in refs:
        record = records.get(ref["record_id"])
        reason, assertion, text = None, None, None
        if record is None:
            reason = (
                "record_not_in_public_view"
                if ref["record_id"] in all_record_ids
                else "unknown_record_id"
            )
        else:
            lines = record["text"].split("\n")
            if type(ref["line"]) is not int or not 1 <= ref["line"] <= len(lines):
                reason = "out_of_bounds_line"
            else:
                text = lines[ref["line"] - 1]
                match = re.fullmatch(r"\d+: ASSERT (.+)", text)
                try:
                    assertion = strict_json(match.group(1)) if match else None
                except (ValueError, TypeError, RecursionError):
                    assertion = None
                if assertion is None:
                    reason = "non_assertion_or_unparseable_line"
                elif assertion["entity_id"] != request["target"]["entity_id"]:
                    reason = "wrong_entity"
                elif any(
                    assertion[k] != request["target"][k]
                    for k in ("valid_start", "valid_end", "measurement_kind")
                ):
                    reason = "wrong_valid_window_or_measurement_kind"
                elif assertion["variable"] != field or assertion["unit"] != UNITS[field]:
                    reason = "wrong_variable_or_unit"
                elif ref not in expected["evidence"]:
                    if assertion["revision_id"] in superseded:
                        reason = (
                            "superseded_same_value"
                            if assertion["value"] == expected["value"]
                            else "superseded_different_value"
                        )
                    elif predicted is not None and assertion["value"] != predicted["value"]:
                        reason = "wrong_value_on_same_key"
                    else:
                        reason = "other_unverifiable"
        fact_key_matches = (
            assertion is not None
            and all(assertion[k] == request["target"][k] for k in request["target"])
            and assertion["variable"] == field
            and assertion["unit"] == UNITS[field]
        )
        details.append(
            {
                "reference": ref,
                "error": reason,
                "assertion": assertion,
                "line_sha256": None if text is None else hashlib.sha256(text.encode()).hexdigest(),
                "locator_valid": assertion is not None,
                "fact_key_matches": fact_key_matches,
                "value_supported": bool(
                    fact_key_matches
                    and predicted is not None
                    and assertion["value"] == predicted["value"]
                ),
                "current_authority_correct": ref in expected["evidence"],
            }
        )
    reasons = {r["error"] for r in details if r["error"]}
    if known and not refs:
        reasons.add("missing_citation")
    if predicted is None:
        primary = status
    elif not value_ok:
        primary = "status_or_value_mismatch"
    elif grounded:
        primary = None
    else:
        primary = next((r for r in PRIORITY if r in reasons), "other_unverifiable")
    return {
        "diagnostic_version": "p6_citation_attribution_v1",
        "field": field,
        "legacy_value_correct": bool(value_ok),
        "legacy_grounded_correct": bool(grounded),
        "citation_only_error": bool(value_ok and not grounded),
        "primary_error": primary,
        "cited_value_supported": bool(refs) and all(r["value_supported"] for r in details),
        "citation_details": details,
        "flags": {
            "duplicate_references": len({canonical(r) for r in refs}) != len(refs),
            "has_valid_and_invalid_citations": any(r["current_authority_correct"] for r in details)
            and any(not r["current_authority_correct"] for r in details),
            "record_exists_but_wrong_line": any(
                r["error"]
                in (
                    "out_of_bounds_line",
                    "non_assertion_or_unparseable_line",
                    "wrong_variable_or_unit",
                )
                for r in details
            ),
            "same_numeric_value_in_wrong_field": any(
                r["assertion"] is not None
                and r["error"] == "wrong_variable_or_unit"
                and predicted is not None
                and r["assertion"]["value"] == predicted["value"]
                for r in details
            ),
            "matches_previous_carrier_reference": previous is not None
            and any(r in previous["evidence"] for r in refs),
            "reference_was_correct_at_earlier_checkpoint": any(
                r in earlier_correct_refs for r in refs
            ),
            "multiple_bad_references": sum(r["error"] is not None for r in details) > 1,
        },
        "changes_original_score": False,
    }
