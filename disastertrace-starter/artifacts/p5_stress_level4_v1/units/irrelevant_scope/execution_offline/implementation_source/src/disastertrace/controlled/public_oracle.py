"""Independent public-text resolver and deliberately limited diagnostic controls.

This module never reads private assertions, the compiler, or renderer helpers.
Malformed public graphs are rejected; they are not evidence-insufficiency Gold.
"""

from __future__ import annotations

import copy
import json
import math
import re
from datetime import datetime, timezone
from decimal import Decimal

backends = (
    "correct",
    "latest-arrival",
    "global-latest-document",
    "clear-omitted",
    "always-unknown",
    "always-known",
    "always-copy-previous",
    "correct-value-wrong-source",
    "per-key-latest-issued",
)

_FIELDS = ("maximum_wind_mph", "minimum_pressure_mb", "latitude_deg", "longitude_deg")
_UNITS = dict(zip(_FIELDS, ("mph", "mb", "degree", "degree")))
_SCOPE = {"entity_id", "valid_start", "valid_end", "measurement_kind"}
_ASSERTION = _SCOPE | {"revision_id", "variable", "unit", "value", "supersedes"}
_POLICY = {
    "variable": "maximum_wind_mph",
    "threshold": 100,
    "known_at_or_above": "prepare",
    "known_below": "monitor",
    "unknown": "request_evidence",
    "kind": "research_rule_not_operational_advice",
}


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate public JSON key")
        result[key] = value
    return result


def _invalid_number(value):
    raise ValueError("non-finite public JSON number")


def _parse_json(text):
    try:
        value = json.loads(text, object_pairs_hook=_object_pairs, parse_constant=_invalid_number)
        if not isinstance(value, dict) or _canonical(value) != text:
            raise ValueError("public record payload must be a canonical JSON object")
        return value
    except (TypeError, OverflowError, json.JSONDecodeError) as exc:
        raise ValueError("invalid public JSON payload") from exc


def _keys(value, expected, name):
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"invalid {name} fields")


def _identifier(value):
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 200
        or any(ord(char) < 33 or ord(char) > 126 for char in value)
    ):
        raise ValueError("bounded printable ASCII public identifier required")


def _time(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be text")  # noqa: TRY004 - malformed protocol data
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid public timestamp") from exc
    if parsed.utcoffset() is None:
        raise ValueError("public timestamp must have a timezone")
    return parsed.astimezone(timezone.utc)


def _scope(value):
    _identifier(value["entity_id"])
    if value["measurement_kind"] != "controlled_observation":
        raise ValueError("unsupported public measurement kind")
    start, end = _time(value["valid_start"]), _time(value["valid_end"])
    if start >= end:
        raise ValueError("public valid window must increase")
    return value["entity_id"], start, end, value["measurement_kind"]


def _number(field, value):
    if type(value) not in (int, float):
        raise ValueError("public assertion value must be a finite number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    bounds = {
        "maximum_wind_mph": (0, 300),
        "minimum_pressure_mb": (800, 1100),
        "latitude_deg": (-90, 90),
        "longitude_deg": (-180, 180),
    }
    lower, upper = bounds[field]
    if not finite or not lower <= value <= upper:
        raise ValueError("public assertion value outside field range")
    number = Decimal(str(value))
    if number != number.quantize(Decimal("0.01")):
        raise ValueError("public assertion exceeds two-decimal precision")


def _key(assertion):
    return (*_scope(assertion), assertion["variable"])


def _validate_request(request):
    if not isinstance(request, dict):
        raise ValueError("public request must be an object")  # noqa: TRY004
    keys = {
        "protocol",
        "instruction",
        "checkpoint_time",
        "target",
        "required_fields",
        "policy",
        "evidence",
        "method",
    }
    method = request.get("method")
    if method == "structured_state":
        keys.add("previous_state")
    elif method == "answer_history":
        keys.add("answer_history")
    elif method != "snapshot":
        raise ValueError("invalid public method")
    _keys(request, keys, "request")
    if request["protocol"] != "disastertrace_controlled_v1":
        raise ValueError("invalid controlled protocol")
    if not isinstance(request["instruction"], str) or not request["instruction"].strip():
        raise ValueError("public instruction required")
    if request["required_fields"] != list(_FIELDS):
        raise ValueError("unexpected required fields")
    if request["policy"] != _POLICY or type(request["policy"].get("threshold")) is not int:
        raise ValueError("invalid research action policy")
    _keys(request["target"], _SCOPE, "target")
    _scope(request["target"])
    if not isinstance(request["evidence"], list):
        raise ValueError("public evidence must be a list")  # noqa: TRY004
    if method == "answer_history" and not isinstance(request["answer_history"], list):
        raise ValueError("answer history must be a list")
    from .schema import parse_decision

    carriers = (
        request["answer_history"]
        if method == "answer_history"
        else [request["previous_state"]]
        if method == "structured_state"
        else []
    )
    for carrier in carriers:
        if carrier is None and method == "structured_state":
            continue
        try:
            parse_decision(_canonical(carrier))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("public carrier must contain valid decisions") from exc
    return _time(request["checkpoint_time"])


def parse_evidence(request: dict) -> list[dict]:
    """Parse and validate actual public lines, preserving replay deliveries.

    Each returned dictionary contains assertion, record_id, line, issued_at,
    and delivery_index. Its assertion is a fresh parsed object. The public graph
    must have one root and one head per FactKey, with parents in earlier deliveries.
    """
    checkpoint = _validate_request(request)
    result, deliveries, records, revisions, successors, roots = [], set(), {}, {}, {}, {}
    for delivery_index, item in enumerate(request["evidence"]):
        _keys(item, {"delivery_id", "record_id", "issued_at", "text"}, "evidence item")
        _identifier(item["delivery_id"])
        _identifier(item["record_id"])
        if item["delivery_id"] in deliveries:
            raise ValueError("duplicate public delivery identity")
        deliveries.add(item["delivery_id"])
        issued = _time(item["issued_at"])
        if issued > checkpoint:
            raise ValueError("public record was issued after checkpoint")
        text = item["text"]
        if not isinstance(text, str):
            raise ValueError("public record text required")  # noqa: TRY004
        lines = text.split("\n")
        if len(lines) < 2:
            raise ValueError("public record requires at least one assertion")
        header = None
        entries = []
        local_ids, local_keys = set(), set()
        for number, line in enumerate(lines, 1):
            tag = "CONTROLLED_RECORD" if number == 1 else "ASSERT"
            match = re.fullmatch(rf"{number}: {tag} (.+)", line)
            if not match:
                raise ValueError("invalid public numbered-line grammar")
            payload = _parse_json(match.group(1))
            if number == 1:
                _keys(
                    payload,
                    {"record_id", "issued_at", "operation", "source_origin"},
                    "record header",
                )
                if payload["record_id"] != item["record_id"]:
                    raise ValueError("public record identity mismatch")
                if payload["issued_at"] != item["issued_at"]:
                    raise ValueError("public record issue time mismatch")
                if payload["operation"] not in ("SET", "PATCH"):
                    raise ValueError("unsupported record operation")
                if payload["source_origin"] != "controlled_generated":
                    raise ValueError("unsupported record origin")
                header = payload
                continue
            _keys(payload, _ASSERTION, "assertion")
            _identifier(payload["revision_id"])
            field = payload["variable"]
            if not isinstance(field, str) or field not in _FIELDS:
                raise ValueError("unsupported assertion variable")
            if payload["unit"] != _UNITS[field]:
                raise ValueError("noncanonical assertion unit")
            _number(field, payload["value"])
            key = _key(payload)
            if payload["revision_id"] in local_ids or key in local_keys:
                raise ValueError("duplicate revision or FactKey in a public record")
            local_ids.add(payload["revision_id"])
            local_keys.add(key)
            parent = payload["supersedes"]
            if header["operation"] == "SET" and parent is not None:
                raise ValueError("SET assertions must introduce roots")
            if header["operation"] == "PATCH" and parent is None:
                raise ValueError("PATCH assertions require parents")
            if parent is not None:
                _identifier(parent)
            entries.append(
                {
                    "assertion": payload,
                    "record_id": item["record_id"],
                    "line": number,
                    "issued_at": item["issued_at"],
                    "delivery_index": delivery_index,
                }
            )
        record_id = item["record_id"]
        if record_id in records:
            if records[record_id] != (item["issued_at"], text):
                raise ValueError("replayed record changed its public content")
            result.extend(entries)
            continue
        # Commit a delivery only after every parent has been checked against
        # earlier deliveries. Sibling lines cannot create each other's parents.
        for entry in entries:
            assertion = entry["assertion"]
            revision, parent, key = (
                assertion["revision_id"],
                assertion["supersedes"],
                _key(assertion),
            )
            if revision in revisions:
                raise ValueError("revision identity reused outside exact record replay")
            if parent is None:
                if key in roots:
                    raise ValueError("multiple roots for one public FactKey")
            else:
                if parent not in revisions:
                    raise ValueError("parent revision is not visible in an earlier delivery")
                previous = revisions[parent]
                if _key(previous["assertion"]) != key:
                    raise ValueError("revision parent has a different FactKey")
                if issued <= _time(previous["issued_at"]):
                    raise ValueError("child issue time must follow parent issue time")
                if parent in successors:
                    raise ValueError("forked public revision chain")
        for entry in entries:
            assertion = entry["assertion"]
            revision, parent, key = (
                assertion["revision_id"],
                assertion["supersedes"],
                _key(assertion),
            )
            revisions[revision] = entry
            if parent is None:
                roots[key] = revision
            else:
                successors[parent] = revision
        records[record_id] = (item["issued_at"], text)
        result.extend(entries)
    return result


def _empty():
    return {field: {"status": "unknown", "value": None, "evidence": []} for field in _FIELDS}


def _decision(state):
    value = state["maximum_wind_mph"]["value"]
    action = "request_evidence" if value is None else "prepare" if value >= 100 else "monitor"
    return {"state": state, "action": action}


def _from_entries(entries):
    state = _empty()
    for entry in entries:
        assertion = entry["assertion"]
        state[assertion["variable"]] = {
            "status": "known",
            "value": assertion["value"],
            "evidence": [{"record_id": entry["record_id"], "line": entry["line"]}],
        }
    return state


def _previous(request):
    from .schema import parse_decision

    candidates = []
    if request["method"] == "structured_state":
        candidates = [request["previous_state"]]
    elif request["method"] == "answer_history":
        candidates = list(reversed(request["answer_history"]))
    for candidate in candidates:
        try:
            parsed = parse_decision(_canonical(candidate))
        except (TypeError, ValueError, OverflowError):
            continue
        return copy.deepcopy(parsed)
    return _decision(_empty())


def answer(request: dict, backend: str = "correct") -> dict:
    """Resolve public authority or run a named deterministic diagnostic control.

    latest-arrival ignores supersession; global-latest-document keeps only the
    newest document; clear-omitted keeps only the final delivery. The latter two
    intentionally discard unrelated retained fields. per-key-latest-issued may
    be correct throughout the supported monotonic single-chain grammar.
    """
    if backend not in backends:
        raise ValueError("unknown controlled diagnostic backend")
    entries = parse_evidence(request)
    target = _scope(request["target"])
    relevant = [entry for entry in entries if _scope(entry["assertion"]) == target]
    if backend == "always-unknown":
        return _decision(_empty())
    if backend == "always-copy-previous":
        return _previous(request)
    if backend == "latest-arrival":
        return _decision(_from_entries(relevant))
    if backend in ("global-latest-document", "clear-omitted"):
        if not entries:
            return _decision(_empty())
        last = (
            max(entries, key=lambda item: (_time(item["issued_at"]), item["delivery_index"]))
            if backend == "global-latest-document"
            else entries[-1]
        )
        return _decision(
            _from_entries(
                [item for item in relevant if item["delivery_index"] == last["delivery_index"]]
            )
        )
    if backend == "per-key-latest-issued":
        return _decision(_from_entries(sorted(relevant, key=lambda item: _time(item["issued_at"]))))
    superseded = {entry["assertion"]["supersedes"] for entry in relevant}
    heads = {
        entry["assertion"]["revision_id"]: entry
        for entry in relevant
        if entry["assertion"]["revision_id"] not in superseded
    }
    state = _from_entries(heads.values())
    if backend == "always-known":
        for field, slot in state.items():
            if slot["status"] == "unknown":
                slot.update(status="known", value=1000 if field == "minimum_pressure_mb" else 0)
    elif backend == "correct-value-wrong-source":
        for slot in state.values():
            if slot["status"] == "known":
                # The real record header exists but cannot support a field value.
                slot["evidence"][0]["line"] = 1
    return _decision(state)
