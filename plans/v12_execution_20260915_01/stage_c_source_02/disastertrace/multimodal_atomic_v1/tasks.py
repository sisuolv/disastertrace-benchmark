"""Public projections only; no reference or previous model answer is read here."""

import copy
from collections import Counter

from disastertrace.multimodal_v1.storage import read

FIELDS = {
    "spatial": ("relation", "map_source", "map_locator"),
    "watch": ("watched", "rule_source", "rule_locator"),
    "logic": ("inspection_required",),
    "selection": ("map_source", "rule_source"),
}
RELATIONS = ("inside", "outside", "boundary_ambiguous", "unknown")
INSTRUCTIONS = {
    "spatial": (
        "For the single current site, read its relation to the 34 KT forecast envelope "
        "in the attached map. Use the supplied pixel coordinates and palette. No map "
        "means relation unknown and both citations null. Cite map artifact_id and the "
        "query grid or point:<site_id>. Do not calculate watched or an inspection action."
    ),
    "watch": (
        "Read only the exercise watch-list line for the current site. Match the watch "
        "target exactly. Report watched as true, false or null. If the matching list or "
        "site line is absent, all three fields are null. Cite its artifact_id and L plus "
        "the one-based line number, counting the disclaimer as L1. An intensity excerpt "
        "is not a watch list. These are benchmark exercise lists, not official warnings."
    ),
    "logic": (
        "Use only the explicitly supplied diagnostic facts. inspection_required = "
        "watched AND forecast_inside. inside maps to true, outside to false, and "
        "boundary_ambiguous and unknown to null. false AND anything is false; "
        "true AND true is true; every other combination is null. These prescribed "
        "facts are privileged logic inputs, not a test of visual reading."
    ),
    "selection": (
        "Select the currently authoritative map and watch-list artifact for EVERY "
        "current query site. Match the complete map_target or watch_target, including "
        "event, product, variable, threshold, valid_at and spatial_scope, and the "
        "required modality (image for maps, text for watch lists). Only delivered "
        "artifacts are eligible. Select greatest issued_at, then greatest version; "
        "redelivery does not change authority. Return null when no match exists. "
        "This metadata-only task selects the whole watch artifact regardless of "
        "whether it contains a site line; do not infer spatial relations or watched "
        "values. The same chosen artifact applies to every current query site."
    ),
}


def contract(family):
    properties = {}
    for field in FIELDS[family]:
        if field == "relation":
            spec = {"type": "string", "enum": list(RELATIONS)}
        elif field in {"watched", "inspection_required"}:
            spec = {"type": ["boolean", "null"]}
        else:
            spec = {"type": ["string", "null"], "minLength": 1, "maxLength": 80}
        properties[field] = spec
    return {
        "version": "atomic_site_mapping_v1",
        "instruction": INSTRUCTIONS[family],
        "root": "Return only JSON: state is an OBJECT keyed by each current site_id. "
        "Include exactly the current queries, each with every listed field. No markdown.",
        "json_schema": {
            "type": "object",
            "required": ["state"],
            "additionalProperties": False,
            "properties": {
                "state": {
                    "type": "object",
                    "maxProperties": 64,
                    "propertyNames": {"type": "string", "minLength": 1, "maxLength": 32},
                    "additionalProperties": {
                        "type": "object",
                        "required": list(FIELDS[family]),
                        "properties": properties,
                        "additionalProperties": False,
                    },
                }
            },
        },
        "max_final_utf8_bytes": 65536,
    }


def make(task_id, family, track, inputs):
    return {
        "task_id": task_id,
        "family": family,
        "track": track,
        "inputs": copy.deepcopy(inputs),
        "output_contract": contract(family),
    }


def build(public_root):
    final = read(public_root / "base/c4.json")
    artifacts = {e["meta"]["artifact_id"]: e for e in final["evidence"]}
    target = final["target"]
    watch_target = dict(target, product="benchmark_watch_list", variable="watched")
    tasks = []
    for aid in ("map-01", "map-02", None):
        for query in final["queries"]:
            inputs = {
                "target": target,
                "queries": [query],
                "evidence": [artifacts[aid]] if aid else [],
            }
            tasks.append(
                make(
                    f"spatial-{aid or 'absent'}-{query['site_id']}",
                    "spatial",
                    "public_static_projection",
                    inputs,
                )
            )
    for aid in ("watch-01", "watch-02", None):
        for query in final["queries"]:
            inputs = {
                "target": watch_target,
                "queries": [{"site_id": query["site_id"]}],
                "evidence": [artifacts[aid]]
                if aid
                else [artifacts["context-05"], artifacts["context-07"]],
            }
            tasks.append(
                make(
                    f"watch-{aid or 'absent'}-{query['site_id']}",
                    "watch",
                    "public_static_projection",
                    inputs,
                )
            )
    for relation in RELATIONS:
        for watched in (True, False, None):
            token = {True: "true", False: "false", None: "null"}[watched]
            inputs = {
                "queries": [{"site_id": "A"}],
                "evidence": [],
                "explicit_facts": {"A": {"relation": relation, "watched": watched}},
                "fact_origin": "prescribed_synthetic_logic_inputs",
            }
            tasks.append(
                make(f"logic-{relation}-{token}", "logic", "privileged_logic_facts", inputs)
            )
    selected = [("base", f"c{i}") for i in range(5)] + [
        (branch, "c4")
        for branch in (
            "without_stale_replay",
            "without_new_map",
            "without_maps",
            "without_watch_list",
            "delayed_new_map",
        )
    ]
    for branch, checkpoint in selected:
        source = read(public_root / branch / (checkpoint + ".json"))
        inputs = {
            "map_target": target,
            "watch_target": watch_target,
            "queries": [{"site_id": q["site_id"]} for q in source["queries"]],
            "evidence": [],
            "metadata": [e["meta"] for e in source["evidence"]],
            "deliveries": source["deliveries"],
            "source_checkpoint": checkpoint,
        }
        tasks.append(
            make(
                f"selection-{branch}-{checkpoint}",
                "selection",
                "public_metadata_projection",
                inputs,
            )
        )
    if Counter(t["family"] for t in tasks) != {
        "spatial": 9,
        "watch": 9,
        "logic": 12,
        "selection": 10,
    }:
        raise ValueError("unexpected atomic task scope")
    # Rotate task families and retain each independent request on one worker.
    groups = {family: [t for t in tasks if t["family"] == family] for family in FIELDS}
    assignments = {str(i): [] for i in range(4)}
    offset = 0
    for group in groups.values():
        for i, task in enumerate(group):
            assignments[str((offset + i) % 4)].append(task["task_id"])
        offset += len(group)
    for worker, ids in assignments.items():
        by_id = {t["task_id"]: t for t in tasks}
        queues = {f: [tid for tid in ids if by_id[tid]["family"] == f] for f in FIELDS}
        order = list(FIELDS)
        order = order[int(worker) :] + order[: int(worker)]
        assignments[worker] = [queues[f][i] for i in range(3) for f in order if i < len(queues[f])]
    return {
        "schema": "mm-atomic-public-plan-v1",
        "tasks": tasks,
        "assignments": assignments,
        "carrier_policy": "independent_empty_history",
        "independent_events": 1,
        "event_id": "AL062024",
        "max_generations": 40,
    }
