"""Balanced source x case coverage, without changing legacy task semantics."""

import random
import shutil
from collections import Counter
from pathlib import Path

from disastertrace.automated.common import fingerprint, read_jsonl, write_jsonl
from disastertrace.automated.sources import parse_nhc
from disastertrace.controlled import compiler, generator, public_oracle, renderer, runtime, scorer
from disastertrace.controlled.schema import METHODS, validate_episode

from .storage import digest, read, seal, verify_seal, write

PROFILE = "controlled_source_case_balanced_v1"
SEED = 20260907


def balanced_episodes(bindings):
    # Exercise the existing binding guard; its historical case allocation is unchanged.
    generator.from_bindings(bindings)
    return [
        generator._episode(
            binding["group_id"],
            family,
            case,
            branch,
            binding["inherited_values"],
            {
                **{k: v for k, v in binding.items() if k != "source_build_id"},
                "origin": "controlled_generated_with_source_inherited_initial_values",
            },
            "development",
        )
        for binding in bindings
        for family in ("U1", "U2", "U3")
        for case in ("primary", "secondary")
        for branch in ("active", "control")
    ]


def schedule(episodes):
    trajectories = [(ep, method) for ep in episodes for method in METHODS]
    random.Random(SEED).shuffle(trajectories)
    return [
        {
            "slot_index": i,
            "slot_id": method + ":" + ep["episode_id"] + ":" + cp,
            "trajectory_id": method + ":" + ep["episode_id"],
            "episode_id": ep["episode_id"],
            "method": method,
            "checkpoint_id": cp,
            "group_id": ep["group_id"],
            "family": ep["family"],
            "case": ep["case"],
            "branch": ep["branch"],
            "repeat": 0,
        }
        for i, (ep, method, cp) in enumerate(
            (ep, method, f"c{c}") for c in range(5) for ep, method in trajectories
        )
    ]


def verify_parents(parents, bindings):
    if len(parents) != 3 or [p["storm_id"] for p in parents] != list(generator.EVENTS):
        raise ValueError("exact development parent source scope required")
    for record in parents:
        provenance = record["provenance"]
        parsed = parse_nhc(
            record["raw_text"],
            source_id=record["source_id"],
            source_url=provenance["source_url"],
            source_sha256=provenance["source_sha256"],
        )
        import hashlib

        if hashlib.sha256(record["raw_text"].encode()).hexdigest() != provenance["source_sha256"]:
            raise ValueError("source raw text digest mismatch")
        if not parsed["admitted"] or parsed["record"] != record:
            raise ValueError("source reparse mismatch")
    ids = {b["source_build_id"] for b in bindings}
    if len(ids) != 1 or generator.bindings_from_records(parents, next(iter(ids))) != bindings:
        raise ValueError("source inheritance mismatch")


def generated(bindings):
    episodes = balanced_episodes(bindings)
    gold, checks = [], 0
    for ep in episodes + generator.micro_episodes():
        validate_episode(ep)
        for cp in ep["checkpoints"]:
            answer = compiler.reference_at(ep, cp["checkpoint_id"])
            if ep["split"] == "development":
                gold.append(
                    {
                        "episode_id": ep["episode_id"],
                        "checkpoint_id": cp["checkpoint_id"],
                        "reference": answer,
                    }
                )
            for method in METHODS:
                if (
                    public_oracle.answer(
                        renderer.render_request(ep, cp["checkpoint_id"], method=method)
                    )
                    != answer
                ):
                    raise ValueError("private compiler/public oracle disagree")
                checks += 1
    controls = {}
    faults = {
        "clear-omitted": ("U1", "preservation"),
        "latest-arrival": ("U2", "known_grounded_accuracy"),
        "global-latest-document": ("U1", "preservation"),
        "always-unknown": ("U3", "known_grounded_accuracy"),
        "always-known": ("U3", "unknown_accuracy"),
        "always-copy-previous": ("U1", "update_success"),
        "correct-value-wrong-source": ("U2", "provenance_refresh"),
    }
    for method in METHODS:
        for backend in (*public_oracle.backends, "invalid-control"):
            result = scorer.score(episodes, runtime.rehearse(episodes, method, backend), method)
            if backend in ("correct", "per-key-latest-issued"):
                if result["metrics"]["overall_grounding"]["value"] != 1:
                    raise ValueError("correct control failed")
            if backend in faults:
                family, metric = faults[backend]
                if result["by_family"][family]["metrics"][metric]["value"] >= 1:
                    raise ValueError("targeted mutant not detected")
            if (
                backend == "invalid-control"
                and result["metrics"]["schema_success"]["numerator"] != 144
            ):
                raise ValueError("invalid answers dropped from denominator")
            controls[method + "/" + backend] = result
    return {
        "episodes": episodes,
        "schedule": schedule(episodes),
        "gold": gold,
        "oracle_comparisons": checks,
        "diagnostic_scores": controls,
    }


def prepare(parent, output):
    parent, output = Path(parent), Path(output)
    if output.exists():
        raise ValueError("preserve existing balanced dataset")
    bindings = read(parent / "source_bindings.json")
    parents = read_jsonl(parent / "parent_sources.jsonl")
    verify_parents(parents, bindings)
    content = generated(bindings)
    output.mkdir(parents=True, exist_ok=False)
    for name in ("source_bindings.json", "parent_sources.jsonl"):
        shutil.copyfile(parent / name, output / name)
    for key in ("episodes", "schedule", "gold"):
        write_jsonl(output / (("private/" if key == "gold" else "") + key + ".jsonl"), content[key])
    write(output / "diagnostic_scores.json", content["diagnostic_scores"])
    plan = metadata(output, bindings, content)
    write(output / "plan.json", plan)
    manifest = seal(output)
    return {**plan, "package_id": manifest["package_id"]}


def metadata(parent, bindings, content):
    cells = Counter(
        (s["group_id"], s["family"], s["case"], s["method"]) for s in content["schedule"]
    )
    return {
        "profile": PROFILE,
        "seed": SEED,
        "episodes": 36,
        "matched_roots": 18,
        "trajectories": 108,
        "planned_responses": 540,
        "source_groups": list(generator.EVENTS),
        "source_family_case_method_cells": [
            {"cell": list(k), "count": v} for k, v in sorted(cells.items())
        ],
        "parent_files": {
            name: digest(parent / name) for name in ("source_bindings.json", "parent_sources.jsonl")
        },
        "dataset_content_id": fingerprint(
            {
                "profile": PROFILE,
                "bindings": bindings,
                "episodes": content["episodes"],
                "gold": content["gold"],
                "schedule": content["schedule"],
            }
        ),
        "oracle_comparisons": 720,
        "diagnostic_responses": 5400,
        "model_calls": 0,
        "heldout_model_calls": 0,
        "new_human_annotations": 0,
        "llm_judge": False,
        "legacy_overlap_episodes": 18,
    }


def verify(output, *, full=True):
    output = Path(output)
    verify_seal(output)
    bindings = read(output / "source_bindings.json")
    verify_parents(read_jsonl(output / "parent_sources.jsonl"), bindings)
    episodes = read_jsonl(output / "episodes.jsonl")
    slots = read_jsonl(output / "schedule.jsonl")
    if episodes != balanced_episodes(bindings) or slots != schedule(episodes):
        raise ValueError("balanced semantic regeneration changed")
    plan = read(output / "plan.json")
    gold = [
        {
            "episode_id": ep["episode_id"],
            "checkpoint_id": cp["checkpoint_id"],
            "reference": compiler.reference_at(ep, cp["checkpoint_id"]),
        }
        for ep in episodes
        for cp in ep["checkpoints"]
    ]
    expected = fingerprint(
        {
            "profile": PROFILE,
            "bindings": bindings,
            "episodes": episodes,
            "gold": gold,
            "schedule": slots,
        }
    )
    if plan["dataset_content_id"] != expected or read_jsonl(output / "private/gold.jsonl") != gold:
        raise ValueError("balanced content identity or Gold mismatch")
    if plan != metadata(output, bindings, {"episodes": episodes, "schedule": slots, "gold": gold}):
        raise ValueError("balanced plan metadata mismatch")
    if full:
        regenerated = generated(bindings)
        if read(output / "diagnostic_scores.json") != regenerated["diagnostic_scores"]:
            raise ValueError("balanced diagnostic regeneration changed")
    return plan, episodes, slots
