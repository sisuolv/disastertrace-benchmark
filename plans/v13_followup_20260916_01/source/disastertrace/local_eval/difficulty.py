"""Predeclared, answer-preserving stress factors; offline acceptance only."""

import argparse
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

from disastertrace.automated.common import fingerprint, write_jsonl
from disastertrace.controlled import compiler, public_oracle, renderer
from disastertrace.controlled.schema import METHODS, validate_episode

from . import data
from .storage import seal, write

FACTORS = ("revision_chain", "irrelevant_scope", "late_stale_replay")
LEVELS = (4, 16)


def transform(episode, factor, level):
    if factor not in FACTORS or level not in LEVELS:
        raise ValueError("only predeclared stress levels are supported")
    ep = deepcopy(episode)
    profile = f"{factor}-{level}"
    ep["episode_id"] += ":" + profile
    ep["root_id"] += ":" + profile
    ep["provenance"]["generator_version"] = "controlled_stress_offline_v1"

    def identity(kind, name):
        return (
            kind
            + "-"
            + fingerprint({"episode": episode["episode_id"], "profile": profile, "name": name})[:24]
        )

    if factor == "revision_chain":
        parents = {a["revision_id"]: r for r in ep["records"] for a in r["assertions"]}
        inserted = {}
        for record in ep["records"]:
            if record["operation"] != "PATCH":
                continue
            children = []
            for assertion in record["assertions"]:
                parent = assertion["supersedes"]
                start = datetime.fromisoformat(parents[parent]["issued_at"])
                end = datetime.fromisoformat(record["issued_at"])
                for index in range(level):
                    key = record["record_id"] + ":" + assertion["variable"] + ":" + str(index)
                    revision = identity("revision", key)
                    # Same-value intermediate revisions isolate chain length from new answers.
                    child = {
                        "record_id": identity("record", key),
                        "operation": "PATCH",
                        "issued_at": (
                            start + (end - start) * ((index + 1) / (level + 1))
                        ).isoformat(),
                        "source_origin": "controlled_generated",
                        "assertions": [
                            {**assertion, "revision_id": revision, "supersedes": parent}
                        ],
                    }
                    children.append(child)
                    parent = revision
                assertion["supersedes"] = parent
            inserted[record["record_id"]] = children
        ep["records"] = [
            item
            for record in ep["records"]
            for item in (*inserted.get(record["record_id"], []), record)
        ]
        deliveries, expanded = [], set()
        for delivery in ep["deliveries"]:
            record_id = delivery["record_id"]
            if record_id not in expanded:
                for child in inserted.get(record_id, []):
                    deliveries.append(
                        {
                            "delivery_id": identity("delivery", child["record_id"]),
                            "record_id": child["record_id"],
                            "delivered_at": delivery["delivered_at"],
                        }
                    )
                expanded.add(record_id)
            deliveries.append(delivery)
        ep["deliveries"] = deliveries
    elif factor == "irrelevant_scope":
        template = next(r for r in ep["records"] if r["operation"] == "SET")
        delivered_at = ep["checkpoints"][2]["at"]
        for index in range(level):
            record = deepcopy(template)
            record["record_id"] = identity("record", str(index))
            record["issued_at"] = delivered_at
            for assertion in record["assertions"]:
                if index % 2:
                    assertion["entity_id"] = identity("other-entity", str(index))
                else:
                    for name in ("valid_start", "valid_end"):
                        assertion[name] = (
                            datetime.fromisoformat(assertion[name]) + timedelta(days=index + 10)
                        ).isoformat()
                assertion["revision_id"] = identity("revision", str(index) + assertion["variable"])
            ep["records"].append(record)
            ep["deliveries"].append(
                {
                    "delivery_id": identity("delivery", str(index)),
                    "record_id": record["record_id"],
                    "delivered_at": delivered_at,
                }
            )
        ep["deliveries"].sort(key=lambda d: d["delivered_at"])
    else:
        initial = ep["records"][0]
        for index in range(level):
            ep["deliveries"].append(
                {
                    "delivery_id": identity("delivery", str(index)),
                    "record_id": initial["record_id"],
                    "delivered_at": ep["checkpoints"][-1]["at"],
                }
            )
    validate_episode(ep)
    return ep


def build(dataset, output):
    output = Path(output)
    if output.exists():
        raise ValueError("preserve prior stress package")
    _, episodes, _ = data.verify(dataset, full=False)
    result, cells = [], []
    for factor in FACTORS:
        for level in LEVELS:
            comparisons, unchanged, effective = 0, 0, []
            for original in episodes:
                ep = transform(original, factor, level)
                effective.append(
                    {
                        "episode_id": ep["episode_id"],
                        "added_records": len(ep["records"]) - len(original["records"]),
                        "added_deliveries": len(ep["deliveries"]) - len(original["deliveries"]),
                    }
                )
                for cp in ep["checkpoints"]:
                    answer = compiler.reference_at(ep, cp["checkpoint_id"])
                    if answer != compiler.reference_at(original, cp["checkpoint_id"]):
                        raise ValueError("stress factor changed checkpoint Gold")
                    unchanged += 1
                    for method in METHODS:
                        request = renderer.render_request(ep, cp["checkpoint_id"], method=method)
                        if public_oracle.answer(request) != answer:
                            raise ValueError("stress public oracle/Gold mismatch")
                        comparisons += 1
                result.append(ep)
            cells.append(
                {
                    "factor": factor,
                    "level": level,
                    "episodes": len(episodes),
                    "unchanged_checkpoint_gold": unchanged,
                    "oracle_comparisons": comparisons,
                    "effective_factor_counts": effective,
                }
            )
    output.mkdir(parents=True, exist_ok=False)
    write_jsonl(output / "episodes.jsonl", result)
    acceptance = {
        "profile": "controlled_stress_offline_v1",
        "status": "offline_verified",
        "episodes": len(result),
        "cells": cells,
        "model_calls": 0,
        "selection_depends_on_model_errors": False,
        "inference_authorized": False,
        "automatic_gold": True,
        "new_human_annotations": 0,
        "llm_judge": False,
        "unchanged_checkpoint_gold": sum(c["unchanged_checkpoint_gold"] for c in cells),
        "oracle_comparisons": sum(c["oracle_comparisons"] for c in cells),
        "note": "One factor at a time. Some control episodes have no PATCH to expand; "
        "report effective factor counts before any future inference. "
        "Token/context budgets are not yet calibrated for this stress matrix.",
    }
    write(output / "acceptance.json", acceptance)
    seal(output)
    return acceptance


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build(args.dataset, args.output))
