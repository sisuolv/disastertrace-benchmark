"""Outcome-independent fork selection and requests from a shared audited native prefix."""

from collections import defaultdict

from disastertrace.forecast_task.common import canonical, fingerprint, strict_json
from disastertrace.forecast_task.protocol import request as native_request

from .codec import LEGEND, PREFIX, from_text, render

VERSION = "native_repr_shared_prefix_one_step_v1"
CONTEXT = "\n\nEvidence context:\n"
CARRIER = "\n\nPrevious answer carrier:\n"


def select(source_execution_id, public, source_slots):
    selected = [
        s
        for s in source_slots
        if s["method"] == "structured_state"
        and public["opportunities"][s["opportunity_id"]]["previous_checkpoint_ids"]
    ]
    rows = []
    for source in selected:
        pair = fingerprint(
            {
                "design": VERSION,
                "source_execution_id": source_execution_id,
                "source_slot_id": source["slot_id"],
            }
        )
        seed = int(
            fingerprint({"seed_protocol": "paired_native_representation_v1", "pair_id": pair})[:8],
            16,
        ) % (2**31)
        for encoding in ("json", "text"):
            rows.append(
                {
                    "pair_id": pair,
                    "encoding": encoding,
                    "seed": seed,
                    "source_slot_id": source["slot_id"],
                    "source_trajectory_id": source["trajectory_id"],
                    "episode_id": source["episode_id"],
                    "opportunity_id": source["opportunity_id"],
                    "repeat": source["repeat"],
                    "slot_id": fingerprint({"pair_id": pair, "encoding": encoding}),
                }
            )
    return rows


def represent(messages, encoding):
    payload = strict_json(messages[1]["content"])
    carrier = payload.pop("carrier")
    text = LEGEND + CONTEXT + canonical(payload) + CARRIER + render(carrier, encoding)
    return [messages[0], {"role": "user", "content": text}]


def restore(messages):
    content = messages[1]["content"]
    if not content.startswith(LEGEND + CONTEXT):
        raise ValueError("shared representation legend differs")
    context, separator, encoded = content[len(LEGEND + CONTEXT) :].partition(CARRIER)
    if not separator:
        raise ValueError("missing explicit carrier section")
    payload = strict_json(context)
    if "carrier" in payload:
        raise ValueError("duplicate carrier exposure")
    payload["carrier"] = (
        from_text(encoded) if encoded.startswith(PREFIX + "\n") else strict_json(encoded)
    )
    return [messages[0], {"role": "user", "content": canonical(payload)}]


def bind(source_execution_id, public, source_slots, source_audit, declared):
    if (
        source_audit["execution_id"] != source_execution_id
        or source_audit["kind"] != "model"
        or select(source_execution_id, public, source_slots) != declared
    ):
        raise ValueError("prefix source identity or predeclared fork population differs")
    captures = [c for w in source_audit["workers"] for c in w["captures"]]
    by_id = {c["slot_id"]: c for c in captures}
    if (
        len(by_id) != len(captures)
        or any(c["origin"] != "local_model_vllm_native_forecast_v1" for c in captures)
        or not set(by_id) <= {s["slot_id"] for s in source_slots}
    ):
        raise ValueError("duplicate, foreign or non-model prefix capture")
    by_trajectory = defaultdict(list)
    for slot in source_slots:
        by_trajectory[slot["trajectory_id"]].append(slot)
    slot_map, result = {s["slot_id"]: s for s in source_slots}, {}
    for row in declared:
        source = slot_map[row["source_slot_id"]]
        trajectory = by_trajectory[source["trajectory_id"]]
        index = next(i for i, s in enumerate(trajectory) if s["slot_id"] == source["slot_id"])
        previous = trajectory[:index]
        expected_ids = public["opportunities"][source["opportunity_id"]]["previous_checkpoint_ids"]
        if [
            public["opportunities"][s["opportunity_id"]]["checkpoint_id"] for s in previous
        ] != expected_ids:
            raise ValueError("source trajectory checkpoint order differs")
        missing = [s["slot_id"] for s in previous if s["slot_id"] not in by_id]
        history = [
            {
                "checkpoint_id": public["opportunities"][s["opportunity_id"]]["checkpoint_id"],
                "final_text": by_id[s["slot_id"]]["final_text"],
            }
            for s in previous
            if s["slot_id"] in by_id
        ]
        request = None
        if not missing:
            native = native_request(public, source["opportunity_id"], "structured_state", history)
            request = represent(native, row["encoding"])
            if canonical(restore(request)) != canonical(native):
                raise ValueError("lossless native request restoration failed")
        result[row["slot_id"]] = {
            "eligible": not missing,
            "messages": request,
            "source_prefix_slot_ids": [s["slot_id"] for s in previous],
            "missing_source_slot_ids": missing,
            "source_prefix_sha256": fingerprint(history),
            "representation": row["encoding"],
            "source_slot_id": source["slot_id"],
        }
    return result
