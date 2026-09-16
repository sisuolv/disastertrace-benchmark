"""Run identity includes condition; paired sampling identity deliberately excludes it."""

import random
from collections import Counter

from disastertrace.automated.common import fingerprint
from disastertrace.constrained_eval import adapter
from disastertrace.controlled.compiler import reference_at
from disastertrace.controlled.schema import METHODS, validate_episode

CONDITIONS = ("base", "irrelevant_scope")
VERSION = "p6_paired_scope_offline_v1"


def sampling_key(model_identity, base_episode_id, method, checkpoint_id, repeat):
    return {
        "scheme": "paired_sampling_v1",
        "master_seed": 60719,
        "model_identity": model_identity,
        "base_episode_id": base_episode_id,
        "method": method,
        "checkpoint_id": checkpoint_id,
        "repeat": repeat,
    }


def sampling_seed(key):
    return int(fingerprint(key)[:8], 16)


def dataset_mapping(datasets):
    if tuple(datasets) != CONDITIONS:
        raise ValueError("fixed base/scope conditions required")
    bases = datasets["base"]
    if not bases or len({e["episode_id"] for e in bases}) != len(bases):
        raise ValueError("unique nonempty base cohort required")
    if len(datasets["irrelevant_scope"]) != len(bases):
        raise ValueError("condition cohort mismatch")
    mapping = []
    for base, stress in zip(bases, datasets["irrelevant_scope"]):
        for ep in (base, stress):
            validate_episode(ep)
            if [c["checkpoint_id"] for c in ep["checkpoints"]] != [f"c{i}" for i in range(5)]:
                raise ValueError("five fixed checkpoints required")
        for key in ("group_id", "family", "case", "branch", "target", "checkpoints"):
            if base[key] != stress[key]:
                raise ValueError("paired task metadata differs")
        for cp in base["checkpoints"]:
            if reference_at(base, cp["checkpoint_id"]) != reference_at(stress, cp["checkpoint_id"]):
                raise ValueError("paired Gold differs")
        mapping.append(
            {
                "base_episode_id": base["episode_id"],
                "episodes": {"base": base["episode_id"], "irrelevant_scope": stress["episode_id"]},
                **{k: base[k] for k in ("group_id", "family", "case", "branch")},
            }
        )
    return mapping


def schedule(plan):
    repeats = plan["repeats"]
    if type(repeats) is not int or not 1 <= repeats <= 8:
        raise ValueError("repeat count outside bounded offline protocol")
    rng = random.Random(60720)
    pairs = [
        (r, mapping, method, i * len(METHODS) + j)
        for r in range(repeats)
        for i, mapping in enumerate(plan["mapping"])
        for j, method in enumerate(METHODS)
    ]
    rng.shuffle(pairs)
    slots, seen_seeds = [], {}
    for cp in (f"c{i}" for i in range(5)):
        for repeat, mapping, method, base_method_index in pairs:
            key = sampling_key(
                plan["model_identity"], mapping["base_episode_id"], method, cp, repeat
            )
            seed = sampling_seed(key)
            if seed in seen_seeds and seen_seeds[seed] != key:
                raise ValueError("unintended sampling seed collision")
            seen_seeds[seed] = key
            order = (
                CONDITIONS if (base_method_index + repeat) % 2 == 0 else tuple(reversed(CONDITIONS))
            )
            for condition in order:
                trajectory = fingerprint(
                    {
                        "experiment_id": plan["experiment_id"],
                        "model_identity": plan["model_identity"],
                        "condition": condition,
                        "repeat": repeat,
                        "method": method,
                        "base_episode_id": mapping["base_episode_id"],
                    }
                )
                slot_id = fingerprint({"trajectory_id": trajectory, "checkpoint_id": cp})
                slots.append(
                    {
                        "slot_index": len(slots),
                        "slot_id": slot_id,
                        "trajectory_id": trajectory,
                        "pair_id": fingerprint(key),
                        "sampling_key": key,
                        "sampling_seed": seed,
                        "attempt_id": fingerprint({"slot_id": slot_id, "attempt": 0}),
                        "condition": condition,
                        "repeat": repeat,
                        "method": method,
                        "checkpoint_id": cp,
                        "base_episode_id": mapping["base_episode_id"],
                        "episode_id": mapping["episodes"][condition],
                        **{k: mapping[k] for k in ("group_id", "family", "case", "branch")},
                    }
                )
    if len({s["slot_id"] for s in slots}) != len(slots):
        raise ValueError("duplicate run slot")
    if set(Counter(s["pair_id"] for s in slots).values()) != {2}:
        raise ValueError("incomplete condition pair")
    return slots


def batches(slots, size=12):
    if type(size) is not int or not 1 <= size <= 12:
        raise ValueError("invalid batch cap")
    current = []
    for slot in slots:
        if current and (
            slot["checkpoint_id"] != current[0]["checkpoint_id"] or len(current) == size
        ):
            yield current
            current = []
        current.append(slot)
    if current:
        yield current


def prepare_request(request, slot, tokenizer):
    if slot["sampling_seed"] != sampling_seed(slot["sampling_key"]):
        raise ValueError("sampling identity differs")
    prepared = adapter.prepare(request, slot, tokenizer)
    # Preserve the original public prompt/grammar and replace only the declared RNG key.
    prepared["sampling"]["seed"] = slot["sampling_seed"]
    prepared["attempt_id"] = slot["attempt_id"]
    return prepared
