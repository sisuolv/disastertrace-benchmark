"""Strict P2 types and source admission; independent of the legacy five-field task."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal

from disastertrace.automated.common import strict_json

PROTOCOL = "disastertrace_controlled_v1"
FIELDS = ("maximum_wind_mph", "minimum_pressure_mb", "latitude_deg", "longitude_deg")
METHODS = ("snapshot", "structured_state", "answer_history")
UNITS = dict(zip(FIELDS, ("mph", "mb", "degree", "degree")))
RANGES = dict(zip(FIELDS, ((0, 300), (800, 1100), (-90, 90), (-180, 180))))
POLICY = {
    "variable": "maximum_wind_mph",
    "threshold": 100,
    "known_at_or_above": "prepare",
    "known_below": "monitor",
    "unknown": "request_evidence",
    "kind": "research_rule_not_operational_advice",
}
ASSERTION_KEYS = {
    "revision_id",
    "entity_id",
    "variable",
    "valid_start",
    "valid_end",
    "measurement_kind",
    "unit",
    "value",
    "supersedes",
}
TARGET_KEYS = {"entity_id", "valid_start", "valid_end", "measurement_kind"}


def exact(value: object, keys: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("invalid " + label + " fields")


def identifier(value: object) -> None:
    if not isinstance(value, str) or not value or len(value) > 200:
        raise ValueError("nonempty bounded identifier required")
    if any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise ValueError("identifier must use printable ASCII without spaces")


def aware(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise ValueError("invalid timestamp") from None
    if parsed.utcoffset() is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def validate_target(target: dict) -> None:
    exact(target, TARGET_KEYS, "target")
    identifier(target["entity_id"])
    if target["measurement_kind"] != "controlled_observation":
        raise ValueError("unsupported measurement kind")
    if aware(target["valid_start"]) >= aware(target["valid_end"]):
        raise ValueError("positive half-open valid window required")


def validate_number(field: str, value: object) -> None:
    if field not in FIELDS or type(value) not in (int, float):
        raise ValueError("typed weather number required")
    try:
        valid = math.isfinite(value) and RANGES[field][0] <= value <= RANGES[field][1]
    except (ValueError, OverflowError):
        valid = False
    if not valid or Decimal(str(value)) != Decimal(str(value)).quantize(Decimal("0.01")):
        raise ValueError("number outside field range or two-decimal precision")


def fact_key(assertion: dict) -> tuple:
    return (
        assertion["entity_id"],
        assertion["variable"],
        aware(assertion["valid_start"]),
        aware(assertion["valid_end"]),
        assertion["measurement_kind"],
    )


def validate_assertion(assertion: dict) -> None:
    exact(assertion, ASSERTION_KEYS, "assertion")
    identifier(assertion["revision_id"])
    validate_target({key: assertion[key] for key in TARGET_KEYS})
    field = assertion["variable"]
    validate_number(field, assertion["value"])
    if assertion["unit"] != UNITS[field]:
        raise ValueError("unit mismatch")
    if assertion["supersedes"] is not None:
        identifier(assertion["supersedes"])


def validate_provenance(episode: dict) -> None:
    provenance = episode["provenance"]
    common = {
        "origin",
        "inherited_values",
        "parent_source_sha256",
        "generator_version",
        "seed",
        "generated_components",
        "official_historical_correction",
        "physical_process_realism_validated",
    }
    development = episode["split"] == "development"
    extra = (
        {
            "group_id",
            "split",
            "source_record_id",
            "source_record_sha256",
            "source_url",
            "source_field_evidence",
        }
        if development
        else set()
    )
    exact(provenance, common | extra, "provenance")
    identifier(provenance["generator_version"])
    if type(provenance["seed"]) is not int:
        raise ValueError("integer generator seed required")
    if (
        provenance["generated_components"]
        != [
            "entity_and_windows",
            "revision_graph",
            "update_values",
            "delivery_times",
            "controlled_record_text",
        ]
        or provenance["official_historical_correction"] is not False
        or provenance["physical_process_realism_validated"] is not False
    ):
        raise ValueError("generated provenance boundaries changed")
    if not development:
        if (
            provenance["origin"] != "synthetic_software_fixture"
            or provenance["inherited_values"] != {}
            or provenance["parent_source_sha256"] is not None
        ):
            raise ValueError("fixture origin mismatch")
        return
    if (
        provenance["origin"] != "controlled_generated_with_source_inherited_initial_values"
        or provenance["group_id"] != episode["group_id"]
        or provenance["split"] != "development"
    ):
        raise ValueError("development origin mismatch")
    identifier(provenance["source_record_id"])
    if not isinstance(provenance["source_url"], str) or not provenance["source_url"].startswith(
        "https://"
    ):
        raise ValueError("source URL required")
    for name in ("parent_source_sha256", "source_record_sha256"):
        digest = provenance[name]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError("source SHA-256 required")
    exact(provenance["inherited_values"], set(FIELDS), "inherited values")
    exact(provenance["source_field_evidence"], set(FIELDS), "source field evidence")
    for field in FIELDS:
        validate_number(field, provenance["inherited_values"][field])
        span = provenance["source_field_evidence"][field]
        exact(span, {"line_start", "line_end", "text"}, "inherited source span")
        if (
            type(span["line_start"]) is not int
            or type(span["line_end"]) is not int
            or not 1 <= span["line_start"] <= span["line_end"]
            or not isinstance(span["text"], str)
            or not span["text"]
        ):
            raise ValueError("invalid inherited source span")


def validate_episode(episode: dict) -> None:
    exact(
        episode,
        {
            "protocol",
            "episode_id",
            "root_id",
            "group_id",
            "split",
            "family",
            "case",
            "branch",
            "target",
            "records",
            "deliveries",
            "checkpoints",
            "provenance",
        },
        "episode",
    )
    if episode["protocol"] != PROTOCOL or episode["split"] not in (
        "development",
        "synthetic_fixture",
    ):
        raise ValueError("unsupported controlled scope")
    if episode["family"] not in ("U1", "U2", "U3") or episode["case"] not in (
        "primary",
        "secondary",
    ):
        raise ValueError("unsupported family/case")
    if episode["branch"] not in ("active", "control"):
        raise ValueError("unsupported branch")
    for name in ("episode_id", "root_id", "group_id"):
        identifier(episode[name])
    validate_target(episode["target"])
    validate_provenance(episode)
    if not isinstance(episode["records"], list) or not isinstance(episode["deliveries"], list):
        raise ValueError("records and deliveries must be JSON arrays")
    records, revisions, children, roots = {}, {}, {}, {}
    for record in episode["records"]:
        exact(
            record, {"record_id", "issued_at", "operation", "source_origin", "assertions"}, "record"
        )
        identifier(record["record_id"])
        if record["record_id"] in records or record["source_origin"] != "controlled_generated":
            raise ValueError("duplicate record or wrong origin")
        if record["operation"] not in ("SET", "PATCH"):
            raise ValueError("unsupported operation")
        aware(record["issued_at"])
        if not isinstance(record["assertions"], list) or not record["assertions"]:
            raise ValueError("nonempty assertions required")
        records[record["record_id"]] = record
        keys = set()
        for assertion in record["assertions"]:
            validate_assertion(assertion)
            key, revision = fact_key(assertion), assertion["revision_id"]
            if key in keys or revision in revisions:
                raise ValueError("duplicate key or revision")
            keys.add(key)
            revisions[revision] = (assertion, record)
            parent = assertion["supersedes"]
            if (record["operation"] == "SET") != (parent is None):
                raise ValueError("SET is root-only; PATCH requires explicit parent")
            if parent is None:
                if key in roots:
                    raise ValueError("multiple roots for a fact key")
                roots[key] = revision
            else:
                if parent in children:
                    raise ValueError("forked revision chain")
                children[parent] = revision
    if episode["split"] == "development":
        for field in FIELDS:
            key = fact_key({**episode["target"], "variable": field})
            if (
                key not in roots
                or revisions[roots[key]][0]["value"]
                != episode["provenance"]["inherited_values"][field]
            ):
                raise ValueError("initial target root differs from declared inherited source value")
    for assertion, record in revisions.values():
        parent_id = assertion["supersedes"]
        if parent_id is not None:
            if parent_id not in revisions:
                raise ValueError("missing parent revision")
            parent, parent_record = revisions[parent_id]
            if fact_key(parent) != fact_key(assertion):
                raise ValueError("cross-key replacement")
            if aware(parent_record["issued_at"]) >= aware(record["issued_at"]):
                raise ValueError("revision issue times must strictly increase")
    seen, delivery_ids, delivered_records = set(), set(), set()
    prior_at = None
    for delivery in episode["deliveries"]:
        exact(delivery, {"delivery_id", "record_id", "delivered_at"}, "delivery")
        identifier(delivery["delivery_id"])
        at = aware(delivery["delivered_at"])
        record_id = delivery["record_id"]
        identifier(record_id)
        if delivery["delivery_id"] in delivery_ids or record_id not in records:
            raise ValueError("duplicate delivery or unknown record")
        if prior_at is not None and at < prior_at:
            raise ValueError("deliveries must be ordered")
        prior_at = at
        delivery_ids.add(delivery["delivery_id"])
        record = records[record_id]
        if aware(record["issued_at"]) > at:
            raise ValueError("future-issued record delivered")
        for assertion in record["assertions"]:
            if assertion["supersedes"] is not None and assertion["supersedes"] not in seen:
                raise ValueError("parent must be visible in an earlier delivery")
        seen.update(a["revision_id"] for a in record["assertions"])
        delivered_records.add(record_id)
    if set(records) != delivered_records:
        raise ValueError("all admitted records require a scheduled delivery")
    checkpoints = episode["checkpoints"]
    if not isinstance(checkpoints, list) or len(checkpoints) != 5:
        raise ValueError("this version requires five checkpoints")
    previous = None
    for index, cp in enumerate(checkpoints):
        exact(cp, {"checkpoint_id", "at"}, "checkpoint")
        at = aware(cp["at"])
        if cp["checkpoint_id"] != f"c{index}" or previous is not None and at <= previous:
            raise ValueError("invalid checkpoint sequence")
        previous = at
    if prior_at is not None and prior_at > previous:
        raise ValueError("delivery after final checkpoint")


def parse_decision(raw: str) -> dict:
    value = strict_json(raw)
    exact(value, {"state", "action"}, "answer")
    if not isinstance(value["action"], str) or value["action"] not in {
        "monitor",
        "prepare",
        "request_evidence",
    }:
        raise ValueError("action must be an allowed string")
    exact(value["state"], set(FIELDS), "state")
    for field, slot in value["state"].items():
        exact(slot, {"status", "value", "evidence"}, "slot")
        if slot["status"] == "unknown":
            if slot["value"] is not None or slot["evidence"] != []:
                raise ValueError("unknown requires null and empty evidence")
        elif slot["status"] == "known":
            validate_number(field, slot["value"])
        else:
            raise ValueError("invalid status")
        if not isinstance(slot["evidence"], list):
            raise ValueError("evidence list required")
        for ref in slot["evidence"]:
            exact(ref, {"record_id", "line"}, "citation")
            identifier(ref["record_id"])
            if type(ref["line"]) is not int or ref["line"] < 1:
                raise ValueError("positive integer citation line required")
    return value


def action_for(state: dict) -> str:
    slot = state["maximum_wind_mph"]
    return (
        "request_evidence"
        if slot["status"] == "unknown"
        else ("prepare" if slot["value"] >= 100 else "monitor")
    )


def empty_decision() -> dict:
    state = {field: {"status": "unknown", "value": None, "evidence": []} for field in FIELDS}
    return {"state": state, "action": "request_evidence"}
