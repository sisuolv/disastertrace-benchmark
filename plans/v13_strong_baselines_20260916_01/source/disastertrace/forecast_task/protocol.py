"""Requests accept only public evidence and a method's own prior final texts."""

from .common import canonical, fingerprint
from .contract import SYSTEM, parse_answer

METHODS = ("snapshot", "structured_state", "answer_history")
REPEATS = 2


def carrier(method, history):
    if method not in METHODS:
        raise ValueError("unknown method")
    if method == "snapshot" or not history:
        return None
    if method == "answer_history":
        return [
            {"checkpoint_id": h["checkpoint_id"], "final_text": h["final_text"]} for h in history
        ]
    last = history[-1]
    if last["final_text"] is None:
        value = {"kind": "missing", "answer": None}
    else:
        try:
            value = {"kind": "answer", "answer": parse_answer(last["final_text"])}
        except (TypeError, ValueError):
            value = {"kind": "invalid", "answer": None}
    return {"checkpoint_id": last["checkpoint_id"], **value}


def request(public, opportunity_id, method, history):
    opportunity = public["opportunities"][opportunity_id]
    query = opportunity["query"]
    expected_prefix = opportunity["previous_checkpoint_ids"]
    if [h["checkpoint_id"] for h in history] != expected_prefix:
        raise ValueError("carrier must be the exact prior checkpoint prefix of this target")
    documents = []
    for source_id in opportunity["visible_source_ids"]:
        source = public["documents"][source_id]
        documents.append(
            {
                "source_id": source_id,
                "delivery_step": source["delivery_step"],
                "delivery_elapsed_hours": source["delivery_elapsed_hours"],
                "numbered_text": source["numbered_text"],
            }
        )
    payload = {
        "query": {
            "storm_id": query["storm_id"],
            "valid_at": query["valid_at"],
            "measurement_kind": "forecast",
        },
        "checkpoint": {
            "delivery_step": opportunity["delivery_step"],
            "delivery_elapsed_hours": opportunity["delivery_elapsed_hours"],
            "forecast_reference_at": opportunity["forecast_reference_at"],
            "delivery_is_controlled": True,
        },
        "documents": documents,
        "method": method,
        "carrier": carrier(method, history),
    }
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": canonical(payload)}]


def schedule(public):
    slots = []
    for episode_id, episode in sorted(public["episodes"].items()):
        for method in METHODS:
            for repeat in range(REPEATS):
                trajectory_id = fingerprint(
                    {"episode_id": episode_id, "method": method, "repeat": repeat}
                )
                for opportunity_id in episode["opportunity_ids"]:
                    key = {
                        "trajectory_id": trajectory_id,
                        "opportunity_id": opportunity_id,
                        "method": method,
                        "repeat": repeat,
                    }
                    seed_digest = fingerprint({"seed_protocol": "forecast_task_v1", **key})
                    slots.append(
                        {
                            **key,
                            "episode_id": episode_id,
                            "slot_id": fingerprint(key),
                            "seed": int(seed_digest[:8], 16) % (2**31),
                        }
                    )
    if len({s["slot_id"] for s in slots}) != len(slots):
        raise ValueError("duplicate scheduled slot")
    return slots
