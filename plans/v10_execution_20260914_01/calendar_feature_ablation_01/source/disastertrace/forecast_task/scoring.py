"""Score frozen references without parsing or repairing source or model text."""

from collections import Counter, defaultdict

from .contract import FIELDS, parse_answer, utc_stamp

FLAGS = (
    "received",
    "shape_valid",
    "storm_correct",
    "time_correct",
    "kind_correct",
    "key_correct",
    "status_correct",
    "current_source",
    "locator_correct",
    "all_correct",
)


def score_one(final_text, opportunity, reference, private):
    result = {name: False for name in FLAGS}
    result.update(
        received=final_text is not None,
        values={f: False for f in FIELDS},
        units={f: False for f in FIELDS},
        fields={f: False for f in FIELDS},
        literal_support={f: False for f in FIELDS},
        error_category="missing_response" if final_text is None else "invalid_json_shape",
    )
    try:
        answer = parse_answer(final_text)
    except (TypeError, ValueError):
        return result
    gold = reference["answer"]
    result["shape_valid"] = True
    result["storm_correct"] = answer["storm_id"] == gold["storm_id"]
    try:
        result["time_correct"] = utc_stamp(answer["valid_at"]) == gold["valid_at"]
    except ValueError:
        pass
    result["kind_correct"] = answer["measurement_kind"] == "forecast"
    result["key_correct"] = all(
        result[k] for k in ("storm_correct", "time_correct", "kind_correct")
    )
    result["status_correct"] = answer["status"] == gold["status"]
    for field in FIELDS:
        result["values"][field] = answer[field]["value"] == gold[field]["value"]
        result["units"][field] = answer[field]["unit"] == gold[field]["unit"]
        result["fields"][field] = all(
            (
                result["key_correct"],
                result["status_correct"],
                result["values"][field],
                result["units"][field],
            )
        )
    citation = answer["citation"]
    target = opportunity["query"]["valid_at"]
    visible = opportunity["visible_source_ids"]
    cited = None
    if citation is not None and citation["source_id"] in visible:
        sid = citation["source_id"]
        if private["sources"][sid]["storm_id"] == opportunity["query"]["storm_id"]:
            claim = private["claims"][sid].get(target)
            cited = claim["answer"] if claim else None
    if gold["citation"] is None:
        result["current_source"] = citation is None
        result["locator_correct"] = citation is None
    else:
        result["current_source"] = (
            citation is not None and citation["source_id"] == gold["citation"]["source_id"]
        )
        if cited is not None:
            result["locator_correct"] = citation == cited["citation"]
    if cited is not None and result["key_correct"]:
        for field in FIELDS:
            location = citation["forecast_line"] == cited["citation"]["forecast_line"]
            if field == "max_sustained_wind":
                location = location and citation["wind_line"] == cited["citation"]["wind_line"]
            result["literal_support"][field] = (
                location and answer["status"] == cited["status"] and answer[field] == cited[field]
            )
    result["all_correct"] = (
        all(result["fields"].values()) and result["current_source"] and result["locator_correct"]
    )
    if result["all_correct"]:
        category = "correct"
    elif not result["key_correct"]:
        category = "wrong_key"
    elif not all(result["fields"].values()):
        category = "wrong_value_status_or_unit"
    elif citation is None:
        category = "missing_citation"
    elif citation["source_id"] not in visible:
        category = "unseen_source"
    elif all(result["literal_support"].values()) and not result["current_source"]:
        category = "superseded_same_value"
    elif not result["current_source"]:
        category = "wrong_source_version"
    else:
        category = "wrong_locator"
    result["error_category"] = category
    return result


def _totals(rows):
    return {
        "planned": len(rows),
        **{name: sum(r[name] for r in rows) for name in FLAGS},
        **{
            kind: {f: sum(r[kind][f] for r in rows) for f in FIELDS}
            for kind in ("values", "units", "fields", "literal_support")
        },
        "errors": dict(sorted(Counter(r["error_category"] for r in rows).items())),
    }


def summarize(slots, captures, public, private):
    if len({s["slot_id"] for s in slots}) != len(slots):
        raise ValueError("duplicate planned slot")
    captured = {c["slot_id"]: c for c in captures}
    if len(captured) != len(captures) or not set(captured) <= {s["slot_id"] for s in slots}:
        raise ValueError("duplicate or unscheduled capture")
    records, groups, trajectories, episode_methods = (
        [],
        defaultdict(list),
        defaultdict(list),
        defaultdict(list),
    )
    for slot in slots:
        oid = slot["opportunity_id"]
        opportunity, reference = public["opportunities"][oid], private["references"][oid]
        capture = captured.get(slot["slot_id"])
        final = capture["final_text"] if capture else None
        score = score_one(final, opportunity, reference, private)
        records.append({"slot_id": slot["slot_id"], "opportunity_id": oid, "score": score})
        for dimension, name in (
            ("method", slot["method"]),
            ("repeat", str(slot["repeat"])),
            ("storm", opportunity["query"]["storm_id"]),
            ("transition", reference["transition"]),
            ("status", reference["answer"]["status"]),
        ):
            groups[dimension, name].append(score)
        trajectories[slot["trajectory_id"]].append(score["all_correct"])
        episode_methods[slot["method"], slot["episode_id"]].append(score["all_correct"])
    return {
        "schema_version": "forecast_task_scores_v1",
        "counts": _totals([r["score"] for r in records]),
        "capture_records": len(captures),
        "absent_capture_records": len(slots) - len(captures),
        "literal_support_note": "positive/terminal source claims only; not_stated has no literal citation",
        "breakdowns": {
            dimension: {
                name: _totals(rows) for (d, name), rows in sorted(groups.items()) if d == dimension
            }
            for dimension in ("method", "repeat", "storm", "transition", "status")
        },
        "whole_trajectories": {
            "planned": len(trajectories),
            "all_checkpoints_correct": sum(all(v) for v in trajectories.values()),
        },
        "both_repeats": {
            method: {
                "planned_episodes": sum(m == method for m, _ in episode_methods),
                "all_checkpoints_both_repeats_correct": sum(
                    all(v) for (m, _), v in episode_methods.items() if m == method
                ),
            }
            for method in sorted({s["method"] for s in slots})
        },
        "records": records,
    }
