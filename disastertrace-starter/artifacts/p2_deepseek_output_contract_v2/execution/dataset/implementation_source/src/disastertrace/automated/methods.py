"""Declared answer carriers; all methods receive the same cumulative evidence."""

from __future__ import annotations

DEFAULT_METHOD = "structured_state"
METHODS = (DEFAULT_METHOD, "snapshot", "answer_history")


def validate_method(method: str) -> str:
    if not isinstance(method, str) or method not in METHODS:
        raise ValueError("unsupported declared method")
    return method


def request_method(request: dict) -> str:
    if not isinstance(request, dict):
        raise ValueError("public request must be an object")
    return validate_method(request.get("method", DEFAULT_METHOD))


def method_contract(method: str) -> dict:
    method = validate_method(method)
    return {
        "schema_version": "declared_method_v1",
        "method": method,
        "evidence_view": "all_delivered_records_with_arrival_duplicates",
        "carrier": {
            "structured_state": "latest_schema_valid_model_decision_or_null",
            "snapshot": "none",
            "answer_history": "chronological_schema_valid_model_decisions",
        }[method],
        "history_includes_invalid_responses": False,
        "carrier_fact_checked_or_corrected": False,
        "fresh_messages_per_checkpoint": True,
        "causal_carrier_dependence_established": False,
    }
