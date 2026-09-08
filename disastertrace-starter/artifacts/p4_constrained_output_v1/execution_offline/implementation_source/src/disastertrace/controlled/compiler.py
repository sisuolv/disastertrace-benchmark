"""Private structured-event compiler; it never parses public text or calls the oracle."""

from copy import deepcopy

from .schema import FIELDS, action_for, aware, empty_decision, fact_key, validate_episode


def reference_at(episode: dict, checkpoint_id: str) -> dict:
    validate_episode(episode)
    matches = [c for c in episode["checkpoints"] if c["checkpoint_id"] == checkpoint_id]
    if len(matches) != 1:
        raise ValueError("unknown checkpoint")
    at = aware(matches[0]["at"])
    records = {r["record_id"]: r for r in episode["records"]}
    heads, seen = {}, set()
    for delivery in episode["deliveries"]:
        if aware(delivery["delivered_at"]) > at:
            break
        record = records[delivery["record_id"]]
        for line, assertion in enumerate(record["assertions"], 2):
            revision = assertion["revision_id"]
            if revision in seen:
                continue
            key = fact_key(assertion)
            parent = assertion["supersedes"]
            if parent is not None and heads[key]["revision_id"] != parent:
                raise ValueError("replacement is not the visible head")
            heads[key] = {
                "revision_id": revision,
                "slot": {
                    "status": "known",
                    "value": assertion["value"],
                    "evidence": [{"record_id": record["record_id"], "line": line}],
                },
            }
            seen.add(revision)
    answer = empty_decision()
    for field in FIELDS:
        key = fact_key({**episode["target"], "variable": field})
        if key in heads:
            answer["state"][field] = deepcopy(heads[key]["slot"])
    answer["action"] = action_for(answer["state"])
    return answer
