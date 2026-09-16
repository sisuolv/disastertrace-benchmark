"""A task-independent structural schema; factual correctness stays in the scorer."""

import json
import math
from hashlib import sha256

from disastertrace.automated.common import strict_json
from disastertrace.controlled.schema import FIELDS, exact, parse_decision

VERSION = "controlled_structure_only_json_v1"
ACTIONS = ("monitor", "prepare", "request_evidence")


def _object(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def schema():
    citation = _object({"record_id": {"type": "string"}, "line": {"type": "integer"}})
    slot = _object(
        {
            "status": {"type": "string", "enum": ["known", "unknown"]},
            "value": {"type": ["number", "null"]},
            "evidence": {"type": "array", "items": citation},
        }
    )
    return _object(
        {
            "state": _object({field: slot for field in FIELDS}),
            "action": {"type": "string", "enum": list(ACTIONS)},
        }
    )


def schema_text():
    # XGrammar emits properties in schema order. Bind those bytes, not sorted JSON.
    return json.dumps(schema(), ensure_ascii=True, separators=(",", ":"))


def identity():
    return {
        "version": VERSION,
        "schema_sha256": sha256(schema_text().encode()).hexdigest(),
        "scope": "containers_keys_types_literals_only",
        "property_order": {
            "root": ["state", "action"],
            "state": list(FIELDS),
            "slot": ["status", "value", "evidence"],
            "citation": ["record_id", "line"],
        },
        "request_dependent": False,
        "gold_dependent": False,
        "numeric_ranges_or_precision": False,
        "unknown_value_evidence_relation": False,
        "citation_identifier_or_line_restrictions": False,
        "action_value_relation": False,
    }


def validate_structure(value):
    """Small CPU-only validator for this specific structural schema."""
    exact(value, {"state", "action"}, "structure root")
    if type(value["action"]) is not str or value["action"] not in ACTIONS:
        raise ValueError("invalid structural action literal")
    exact(value["state"], set(FIELDS), "structure state")
    for slot in value["state"].values():
        exact(slot, {"status", "value", "evidence"}, "structure slot")
        if type(slot["status"]) is not str or slot["status"] not in ("known", "unknown"):
            raise ValueError("invalid structural status literal")
        if slot["value"] is not None and type(slot["value"]) not in (int, float):
            raise ValueError("structural value must be number or null")
        if type(slot["evidence"]) is not list:
            raise ValueError("structural evidence must be an array")
        for ref in slot["evidence"]:
            exact(ref, {"record_id", "line"}, "structure citation")
            line = ref["line"]
            integer = type(line) is int or (
                type(line) is float and math.isfinite(line) and line.is_integer()
            )
            if type(ref["record_id"]) is not str or not integer:
                raise ValueError("invalid structural citation types")
    return value


def inspect(raw):
    result = {"json_valid": False, "structure_valid": False, "task_contract_valid": False}
    try:
        value = strict_json(raw)
        result["json_valid"] = True
        validate_structure(value)
        result["structure_valid"] = True
        parse_decision(raw)
        result["task_contract_valid"] = True
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        pass
    return result


def serialize_fixture(value):
    """Order program fixture keys to exercise the grammar; never repair model text."""
    validate_structure(value)
    ordered = {
        "state": {
            field: {
                "status": value["state"][field]["status"],
                "value": value["state"][field]["value"],
                "evidence": [
                    {"record_id": ref["record_id"], "line": ref["line"]}
                    for ref in value["state"][field]["evidence"]
                ],
            }
            for field in FIELDS
        },
        "action": value["action"],
    }
    return json.dumps(ordered, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
