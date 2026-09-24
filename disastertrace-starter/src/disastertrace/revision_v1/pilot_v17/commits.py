"""Strict pilot validation layered over the existing public commit contract."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
import math

from ..belief_commit import validate_commit_schema
from .provider import digest

ROOT_FIELDS = {"schema_version", "episode_id", "target_id", "parent_commit_id", "as_of",
               "operation", "forecast_op", "evidence_ids", "fact_updates", "forecast_updates", "next_action"}
FACT_FIELDS = {"active_source_ids", "valid_start", "valid_end", "relation_status"}


def no_duplicates(items):
    out = {}
    for key, value in items:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def strict_loads(content):
    def invalid_constant(value):
        raise ValueError("non-finite JSON constant")
    return json.loads(content, object_pairs_hook=no_duplicates, parse_constant=invalid_constant)


def normalize_time(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone required")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def id_list(value, visible):
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("source IDs must be strings in a list")
    if len(value) != len(set(value)):
        raise ValueError("duplicate source ID")
    if not set(value) <= visible:
        raise ValueError("source ID was not visible")
    return sorted(value)


def validate(commit, view, before):
    errors = []
    try:
        if not isinstance(commit, dict) or set(commit) != ROOT_FIELDS:
            raise ValueError("root fields differ from public contract")
        old = validate_commit_schema(commit)
        if not old["valid"]:
            raise ValueError(old["error"])
        if commit["episode_id"] != view["episode_id"] or commit["target_id"] != view["target_id"]:
            raise ValueError("target or episode mismatch")
        if normalize_time(commit["as_of"]) != normalize_time(view["as_of"]):
            raise ValueError("as_of differs from requested cutoff")
        if commit["parent_commit_id"] != before["parent_commit_id"]:
            raise ValueError("wrong valid parent commit")
        visible = {row["source_id"] for row in view["evidence"]}
        id_list(commit["evidence_ids"], visible)
        if commit["operation"] not in ("UPDATE", "HOLD"):
            raise ValueError("FOLLOW not qualified for this pilot")
        op = commit["forecast_op"]
        if op not in ("SET_PROBABILITY", "KEEP_PROBABILITY"):
            raise ValueError("unsupported probability operation")
        updates = commit["forecast_updates"]
        if op == "KEEP_PROBABILITY" and updates:
            raise ValueError("KEEP has forecast updates")
        if op == "SET_PROBABILITY" and len(updates) != 1:
            raise ValueError("SET requires exactly one probability")
        for update in updates:
            if set(update) != {"target_id", "event_probability"} or update["target_id"] != view["target_id"]:
                raise ValueError("forecast target/fields mismatch")
        if len(commit["fact_updates"]) > 1:
            raise ValueError("duplicate fact slot")
        for update in commit["fact_updates"]:
            if set(update) != {"slot", "operation", "support_status", "value", "source_ids"}:
                raise ValueError("fact update fields mismatch")
            if update["slot"] != "target_source_state" or update["operation"] != "SET":
                raise ValueError("pilot uses one explicitly SET fact-state slot")
            if update["support_status"] != "supported":
                raise ValueError("fact state SET must use supported status")
            value = update["value"]
            if not isinstance(value, dict) or set(value) != FACT_FIELDS:
                raise ValueError("fact-state fields mismatch")
            active = id_list(value["active_source_ids"], visible)
            cited = id_list(update["source_ids"], visible)
            if active != cited or not set(cited) <= set(commit["evidence_ids"]):
                raise ValueError("fact source IDs and cited evidence disagree")
            status = value["relation_status"]
            if status not in ("RESOLVED", "UNRESOLVED", "NO_APPLICABLE_EVIDENCE"):
                raise ValueError("invalid relation status")
            if status == "RESOLVED":
                if len(active) != 1:
                    raise ValueError("resolved current state requires one source")
                lower, upper = normalize_time(value["valid_start"]), normalize_time(value["valid_end"])
                if lower >= upper:
                    raise ValueError("inverted validity range")
            elif active or value["valid_start"] is not None or value["valid_end"] is not None:
                raise ValueError("unknown/no-applicable state must have empty active source and null bounds")
        if commit["next_action"] != {"kind": "WAIT", "until_or_args": None}:
            raise ValueError("pilot uses the fixed checkpoint schedule")
        if commit["operation"] == "HOLD" and op != "KEEP_PROBABILITY":
            raise ValueError("HOLD cannot set probability")
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        errors.append(str(error))
    return {"valid": not errors, "errors": errors}


def apply_commit(before, commit, validation):
    after = copy.deepcopy(before)
    if not validation["valid"]:
        return after
    for update in commit["fact_updates"]:
        value = copy.deepcopy(update["value"])
        value["active_source_ids"] = sorted(value["active_source_ids"])
        for field in ("valid_start", "valid_end"):
            if value[field] is not None:
                value[field] = normalize_time(value[field])
        after["fact_state"] = value
    if commit["forecast_op"] == "SET_PROBABILITY":
        after["probability"] = commit["forecast_updates"][0]["event_probability"]
        after["probability_origin"] = "MODEL_SET"
    # Include forecast_op and every actual submitted field in parent identity.
    after["parent_commit_id"] = digest(commit)
    return after


def consume_response(capture, view, before):
    commit = None
    try:
        if capture.get("http_status") != 200:
            raise ValueError("provider response not successful")
        response = capture["provider_response"]
        choices = response.get("choices", [])
        if len(choices) != 1:
            raise ValueError("expected one response choice")
        if choices[0].get("finish_reason") != "stop":
            raise ValueError("non-stop finish reason: " + str(choices[0].get("finish_reason")))
        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty or non-text final answer")
        commit = strict_loads(content)
        validation = validate(commit, view, before)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        validation = {"valid": False, "errors": [str(error)]}
    after = apply_commit(before, commit, validation)
    return {"parsed_commit": commit, "validation": validation, "before": copy.deepcopy(before),
            "after": after, "technical_probability_fallback": after["probability_origin"] == "TECHNICAL_FALLBACK"}
