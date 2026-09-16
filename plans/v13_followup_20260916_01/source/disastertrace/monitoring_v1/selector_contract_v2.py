"""One contract for query intent; acquisition and forecast timing stay in runtime."""

import json

from ..forecast_task.common import strict_json

VERSION = "selector_query_only.v2"
FIELD = "query_order"


def contract(query_handles):
    handles = list(query_handles)
    if any(type(h) is not str or not h for h in handles) or len(set(handles)) != len(handles):
        raise ValueError("Unique nonempty query handles required")
    items = {"type": "string", **({"enum": handles} if handles else {})}
    schema = {"type": "object", "properties": {
        FIELD: {"type": "array", "items": items, "maxItems": len(handles), "uniqueItems": True}},
        "required": [FIELD], "additionalProperties": False}
    return {
        "version": VERSION, "logical_schema": schema,
        "provider_schema": {"type": "json_schema", "json_schema": {
            "name": "selector_query_only_v2", "strict": True, "schema": schema}},
        "system": (
            "Allocate the shared source budget to improve forecasts of fixed future native visibility reports. "
            "Use only supplied common professional TAFs and legally acquired reports. "
            "Extra queries reveal past registered neighbor report slots and may serve multiple targets. "
            "This selector consumes one model call and its measured tokens and compute. "
            "Remaining resources exclude that reservation; account for future calendar opportunities. "
            "Forecasts are produced by the frozen program at fixed slots. "
            "An ordered query intent may be empty, a subset, all candidates, or a reordering. "
            "The runtime enforces budget, availability, entitlement and deadlines on the executed prefix. "
            "Fact sufficiency does not imply predictive value. "
            "Return only bare JSON satisfying this schema, with no code fences or extra fields: "
            + json.dumps(schema, sort_keys=True, separators=(",", ":"))
        ),
        "request_instruction": "Rank registered queries only; forecasts use fixed program slots.",
    }


def parse_query_only(raw, query_handles):
    spec = contract(query_handles)
    if type(raw) is not str:
        raise ValueError("Selector requires bare JSON text")
    value = strict_json(raw)
    if type(value) is not dict or set(value) != {FIELD}:
        raise ValueError("Invalid query-only selector schema")
    sequence = value[FIELD]
    if (type(sequence) is not list or any(type(v) is not str for v in sequence)
            or len(sequence) != len(set(sequence))
            or not set(sequence) <= set(query_handles)
            or len(sequence) > spec["logical_schema"]["properties"][FIELD]["maxItems"]):
        raise ValueError("Selector returned duplicate or unregistered query handles")
    return value


def to_internal(value):
    return {FIELD: list(value[FIELD]), "forecast_handles": []}


def selection_system(config, request):
    from .selection import SELECTOR_SYSTEM

    version = config.get("selector_contract_version", "selector.v1")
    if version == "selector.v1":
        if "selector_contract_version" in request:
            raise ValueError("Legacy selector request cannot declare a new contract")
        return SELECTOR_SYSTEM
    if version != VERSION or request.get("selector_contract_version") != VERSION:
        raise ValueError("Selector contract version mismatch")
    return contract(request["queries"])["system"]
