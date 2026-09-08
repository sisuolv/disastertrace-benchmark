"""Explicit public projection; private source bindings and future deliveries stay local."""

from copy import deepcopy

from disastertrace.automated.common import canonical

from .schema import FIELDS, METHODS, POLICY, PROTOCOL, aware, parse_decision

INSTRUCTION = (
    "Research-generated weather records, not official corrections or operational advice. "
    "Answer only the target entity, half-open valid window and measurement kind. "
    "SET creates root fact versions; PATCH replaces only explicitly listed same-key "
    "parents via supersedes. Omission does not clear a fact. Replayed old versions "
    "cannot replace a newer version. Other entities/windows do not affect the target. "
    "Use only delivered evidence, with issued_at no later than checkpoint_time. "
    "Return one JSON object with exactly state and action, no prose or fences. "
    "State contains exactly maximum_wind_mph, minimum_pressure_mb, latitude_deg, "
    "longitude_deg. Each slot has exactly status, value, evidence. Unknown means "
    "status=unknown, value=null, evidence=[]. Known means status=known, finite numeric "
    "value with at most two decimal places, evidence=[{record_id:string,line:integer}]. "
    "Wind range 0..300 mph, pressure 800..1100 mb, latitude -90..90 and longitude "
    "-180..180 degrees. Cite the ASSERT line of the current authoritative version "
    "for each known fact; all citations must support it. Known empty evidence is "
    "structurally accepted but earns no grounded credit. Duplicate JSON keys and "
    "booleans as numbers are forbidden. Action is the string prepare for known wind "
    ">=100, monitor for known wind<100, or request_evidence for unknown wind. "
    "Prior answers are model claims, not authoritative source records."
)


def render_record(record: dict) -> str:
    header = {key: record[key] for key in ("record_id", "issued_at", "operation", "source_origin")}
    lines = ["CONTROLLED_RECORD " + canonical(header)]
    lines += ["ASSERT " + canonical(assertion) for assertion in record["assertions"]]
    return "\n".join(f"{i}: {line}" for i, line in enumerate(lines, 1))


def render_request(
    episode: dict, checkpoint_id: str, *, method: str, previous=None, history=None
) -> dict:
    if method not in METHODS:
        raise ValueError("unsupported method")
    checkpoint = next(
        (c for c in episode["checkpoints"] if c["checkpoint_id"] == checkpoint_id), None
    )
    if checkpoint is None:
        raise ValueError("unknown checkpoint")
    records = {r["record_id"]: r for r in episode["records"]}
    evidence = []
    for delivery in episode["deliveries"]:
        if aware(delivery["delivered_at"]) > aware(checkpoint["at"]):
            continue
        record = records[delivery["record_id"]]
        evidence.append(
            {
                "delivery_id": delivery["delivery_id"],
                "record_id": record["record_id"],
                "issued_at": record["issued_at"],
                "text": render_record(record),
            }
        )
    request = {
        "protocol": PROTOCOL,
        "instruction": INSTRUCTION,
        "checkpoint_time": checkpoint["at"],
        "target": deepcopy(episode["target"]),
        "required_fields": list(FIELDS),
        "policy": dict(POLICY),
        "evidence": evidence,
        "method": method,
    }
    if method == "structured_state":
        request["previous_state"] = (
            None if previous is None else parse_decision(canonical(previous))
        )
    elif method == "answer_history":
        if history is not None and not isinstance(history, list):
            raise ValueError("history must be a list")
        request["answer_history"] = [
            parse_decision(canonical(answer)) for answer in (history or [])
        ]
    return request
