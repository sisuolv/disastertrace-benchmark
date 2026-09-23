"""Structure, current query coverage, citation legality and correctness stay distinct."""

import json
import re

from disastertrace.multimodal_v1.scoring import rate

from .tasks import FIELDS, RELATIONS

VALUE_FIELDS = {"relation", "watched", "inspection_required"}


def parse(raw, family):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("non-JSON constant: " + value)

    if not isinstance(raw, str) or len(raw.encode()) > 65536:
        raise ValueError("final text exceeds contract")
    data = json.loads(raw, object_pairs_hook=unique, parse_constant=constant)
    if not isinstance(data, dict) or set(data) != {"state"} or not isinstance(data["state"], dict):
        raise ValueError("site-keyed state object required")
    if len(data["state"]) > 64:
        raise ValueError("site cap exceeded")
    for sid, row in data["state"].items():
        if not 1 <= len(sid) <= 32 or not isinstance(row, dict) or set(row) != set(FIELDS[family]):
            raise ValueError("unexpected site fields")
        for field, value in row.items():
            if field == "relation":
                if not isinstance(value, str) or value not in RELATIONS:
                    raise ValueError("invalid relation")
            elif field in VALUE_FIELDS:
                if value is not None and type(value) is not bool:
                    raise ValueError("boolean or null required")
            elif value is not None and (not isinstance(value, str) or not 1 <= len(value) <= 80):
                raise ValueError("bounded reference or null required")
    return data


def parsed(raw, family):
    try:
        return {"status": "received_valid", "value": parse(raw, family)}
    except (ValueError, TypeError, RecursionError):
        return {"status": "received_invalid"}


def citation_legal(task, sid, row):
    """Check public source/locator admissibility, not current authority or value truth."""
    inp, family = task["inputs"], task["family"]
    if family == "logic":
        return None
    if family == "selection":
        delivered = {d["artifact_id"] for d in inp["deliveries"]}
        for field, key, modality in (
            ("map_source", "map_target", "image"),
            ("rule_source", "watch_target", "text"),
        ):
            eligible = {
                m["artifact_id"]
                for m in inp["metadata"]
                if m["target"] == inp[key]
                and m["modality"] == modality
                and m["artifact_id"] in delivered
            }
            if row.get(field) not in eligible and not (
                field in row and row[field] is None and not eligible
            ):
                return False
        return True
    prefix = "map" if family == "spatial" else "rule"
    source, locator = row.get(prefix + "_source"), row.get(prefix + "_locator")
    modality = "image" if family == "spatial" else "text"
    eligible = [
        e
        for e in inp["evidence"]
        if e["meta"]["target"] == inp["target"] and e["meta"]["modality"] == modality
    ]
    if source is None:
        if locator is not None:
            return False
        if family == "watch":
            return not any(
                re.fullmatch(r"WATCH " + re.escape(sid) + r" (true|false)", line)
                for e in eligible
                for line in e["content"]["lines"]
            )
        return not eligible
    item = next((e for e in eligible if e["meta"]["artifact_id"] == source), None)
    if item is None:
        return False
    if family == "spatial":
        q = next(q for q in inp["queries"] if q["site_id"] == sid)
        return locator in {q["grid"], "point:" + sid}
    match = re.fullmatch(r"L([1-9][0-9]*)", locator or "")
    return bool(match and int(match[1]) <= len(item["content"]["lines"]))


def score(task, reference, outcome, finish):
    valid = outcome["status"] == "received_valid"
    state = outcome["value"]["state"] if valid else {}
    expected_ids = {q["site_id"] for q in task["inputs"]["queries"]}
    if expected_ids != set(reference["state"]):
        raise ValueError("reference/query identity mismatch")
    values, citations, legal, differences = [], [], [], []
    for sid, gold in reference["state"].items():
        actual = state.get(sid, {})
        if task["family"] != "logic":
            legal.append(bool(valid and sid in state and citation_legal(task, sid, actual)))
        for field, expected in gold.items():
            equal = field in actual and actual[field] == expected
            if (
                field == "map_locator"
                and expected is not None
                and actual.get(field) == "point:" + sid
            ):
                equal = True
            (values if field in VALUE_FIELDS else citations).append(equal)
            if not equal:
                differences.append(
                    {
                        "site_id": sid,
                        "field": field,
                        "expected": expected,
                        "actual_present": field in actual,
                        "actual": actual.get(field),
                    }
                )
    complete = valid and set(state) == expected_ids
    fields_correct = complete and all(values + citations)
    return {
        "task_id": task["task_id"],
        "family": task["family"],
        "track": task["track"],
        "status": outcome["status"],
        "structural_valid": valid,
        "finish_reason": finish,
        "query_complete": complete,
        "missing_sites": sorted(expected_ids - set(state)),
        "extra_sites": sorted(set(state) - expected_ids),
        "value_fields": rate(sum(values), len(values)),
        "citation_fields": rate(sum(citations), len(citations)),
        "citation_legal_sites": rate(sum(legal), len(legal)),
        "fields_correct": fields_correct,
        "strict_correct": fields_correct and finish == "eos",
        "differences": differences,
    }


def aggregate(rows):
    result = {}
    for family in FIELDS:
        selected = [r for r in rows if r["family"] == family]
        group = {
            k: rate(sum(r[k] for r in selected), len(selected))
            for k in ("structural_valid", "query_complete", "fields_correct", "strict_correct")
        }
        for metric in ("value_fields", "citation_fields", "citation_legal_sites"):
            group[metric] = rate(
                sum(r[metric]["numerator"] for r in selected),
                sum(r[metric]["denominator"] for r in selected),
            )
        result[family] = group
    return result
