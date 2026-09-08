"""Actual public evidence differences, independent of factor labels or model scores."""

from disastertrace.automated.common import canonical, fingerprint
from disastertrace.controlled.public_oracle import answer, parse_evidence


def _semantic_view(request):
    entries = parse_evidence(request)
    facts = {
        canonical(
            {k: v for k, v in e["assertion"].items() if k not in ("revision_id", "supersedes")}
        )
        for e in entries
    }
    relevant = [
        e for e in entries if all(e["assertion"][k] == v for k, v in request["target"].items())
    ]
    decision = answer(request)
    return {
        "unique_fact_value_signatures": sorted(facts),
        "delivered_assertions": len(entries),
        "unique_revisions": len({e["assertion"]["revision_id"] for e in entries}),
        "target_assertions": len(relevant),
        "off_target_assertions": len(entries) - len(relevant),
        "current_target_state": {
            field: {k: value[k] for k in ("status", "value")}
            for field, value in decision["state"].items()
        },
    }


def carrier(request):
    return {k: request[k] for k in ("previous_state", "answer_history") if k in request}


def compare_evidence(base, treatment):
    a, b = base["evidence"], treatment["evidence"]
    by_a = {r["record_id"]: (r["text"], r["issued_at"]) for r in a}
    by_b = {r["record_id"]: (r["text"], r["issued_at"]) for r in b}
    same = canonical(a) == canonical(b)
    result = {
        "new_unique_records": len(set(by_b) - set(by_a)),
        "modified_existing_records": sum(by_a[k] != by_b[k] for k in by_a.keys() & by_b.keys()),
        "extra_deliveries": len(b) - len(a),
        "added_factor_visible": not same,
        "evidence_byte_equal": same,
        "base_evidence_sha256": fingerprint(a),
        "condition_evidence_sha256": fingerprint(b),
        "carrier_equal": carrier(base) == carrier(treatment),
        "full_public_request_equal": canonical(base) == canonical(treatment),
        "semantic_mapping_policy": "fact_key_unit_value_sets_ignore_locator_revision_and_delivery_identity; current_target_resolved_separately",
    }
    try:
        left, right = _semantic_view(base), _semantic_view(treatment)
    except (ValueError, TypeError, KeyError):
        result.update(
            semantic_comparison_status="invalid_public_input",
            semantic_equal=None,
            current_target_value_equal=None,
            effective_strength=None,
        )
    else:
        result.update(
            semantic_comparison_status="verified_public_parse",
            semantic_equal=left["unique_fact_value_signatures"]
            == right["unique_fact_value_signatures"],
            current_target_value_equal=left["current_target_state"]
            == right["current_target_state"],
            effective_strength={
                k: right[k] - left[k]
                for k in (
                    "delivered_assertions",
                    "unique_revisions",
                    "target_assertions",
                    "off_target_assertions",
                )
            },
        )
    return result


def exposure_series(base_requests, condition_requests):
    if len(base_requests) != len(condition_requests):
        raise ValueError("paired checkpoint opportunities differ")
    rows = [compare_evidence(a, b) for a, b in zip(base_requests, condition_requests)]
    first = next((i for i, r in enumerate(rows) if r["added_factor_visible"]), None)
    for i, row in enumerate(rows):
        row["first_exposed_checkpoint"] = None if first is None else f"c{first}"
        row["exposure_status"] = (
            "never_exposed"
            if first is None
            else "before_first_exposure"
            if i < first
            else "exposed"
        )
    return rows
