"""Versioned output instructions for offline calibration; the parser is unchanged."""

from __future__ import annotations

from .common import canonical, fingerprint
from .dynamic import FIELDS, render_request
from .methods import DEFAULT_METHOD

LEGACY_CONTRACT = "legacy_v1"
EXPLICIT_CONTRACT = "explicit_v1"


def _output_schema() -> dict:
    citation = {
        "type": "object",
        "additionalProperties": False,
        "required": ["record_id", "line"],
        "properties": {
            "record_id": {"type": "string"},
            "line": {"type": "integer", "minimum": 1},
        },
    }
    known = {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "value", "evidence"],
        "properties": {
            "status": {"const": "known"},
            "value": {"type": "number"},
            "evidence": {"type": "array", "items": {"$ref": "#/$defs/citation"}},
        },
    }
    unknown = {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "value", "evidence"],
        "properties": {
            "status": {"const": "unknown"},
            "value": {"type": "null"},
            "evidence": {"type": "array", "maxItems": 0},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["state", "action"],
        "properties": {
            "state": {
                "type": "object",
                "additionalProperties": False,
                "required": list(FIELDS),
                "properties": {field: {"$ref": "#/$defs/slot"} for field in FIELDS},
            },
            "action": {"type": "string", "enum": ["monitor", "prepare", "request_evidence"]},
        },
        "$defs": {"citation": citation, "slot": {"oneOf": [known, unknown]}},
    }


def contract_spec(contract: str = EXPLICIT_CONTRACT) -> dict:
    """Return a fresh descriptor whose ID binds schema, wording, and lexical rules.

    JSON Schema describes structural constraints. Strict JSON lexical constraints
    below preserve the existing parser's duplicate-key, finite-number, and
    integer-token behavior, which a generic JSON Schema validator cannot certify.
    """
    if not isinstance(contract, str) or contract not in {LEGACY_CONTRACT, EXPLICIT_CONTRACT}:
        raise ValueError("unsupported output contract")
    schema = _output_schema()
    spec = {
        "schema_version": "calibration_output_contract_v1",
        "contract": contract,
        "protocol": "disastertrace_text_v1",
        "marker": "DISASTERTRACE_OUTPUT_CONTRACT " + contract,
        "json_schema": schema,
        "schema_sha256": fingerprint(schema),
        "lexical_requirements": [
            "Return one complete JSON object with no Markdown fences, prose, or trailing data.",
            "Use double-quoted object keys and strings; duplicate object keys are forbidden.",
            "Known values must parse as finite JSON numbers, excluding booleans, NaN, "
            "infinity, and numeric overflow.",
            "Each citation line must use a positive integer JSON token, without a fractional "
            "part or exponent; booleans are not line numbers.",
        ],
        "grounding_requirement": (
            "For a known value to receive grounded credit, provide at least one supported "
            "reference to numbered lines of a currently provided record. The schema and "
            "frozen parser permit empty evidence for known values structurally; empty "
            "evidence does not establish grounding. A well-formed reference alone does "
            "not establish factual correctness or evidence support."
        ),
        "instruction_suffix": (
            "The action must be a string: monitor, prepare, or request_evidence. "
            "The state must be an object containing exactly the five required field names. "
            "Each field must contain exactly status, value, and evidence. "
            "For unknown status use a null value and an empty evidence array. "
            "For known status use a finite numeric value and an evidence array. "
            "Each reference contains exactly a record_id string and a positive integer line. "
            "Do not put the action inside an object or exchange the state and action shapes. "
            "Return no keys outside the JSON Schema."
        )
        if contract == EXPLICIT_CONTRACT
        else "",
        "parser_authority": "disastertrace.automated.dynamic.parse_decision",
        "scope": "offline_prompt_calibration_only",
        "provider_json_mode": False,
    }
    spec["contract_id"] = fingerprint(spec)
    return spec


def render_calibration_request(
    episode: dict,
    checkpoint_id: str,
    previous: dict | None,
    *,
    method: str = DEFAULT_METHOD,
    history: list[dict] | None = None,
    contract: str = EXPLICIT_CONTRACT,
) -> dict:
    """Change only the shared instruction; preserve visible evidence and actual carriers."""
    spec = contract_spec(contract)
    request = render_request(episode, checkpoint_id, previous, method=method, history=history)
    if contract == LEGACY_CONTRACT:
        return request
    request["instruction"] += "\n\n" + "\n".join(
        [
            spec["marker"] + " contract_id=" + spec["contract_id"],
            spec["instruction_suffix"],
            *spec["lexical_requirements"],
            spec["grounding_requirement"],
            "JSON Schema: " + canonical(spec["json_schema"]),
        ]
    )
    return request
