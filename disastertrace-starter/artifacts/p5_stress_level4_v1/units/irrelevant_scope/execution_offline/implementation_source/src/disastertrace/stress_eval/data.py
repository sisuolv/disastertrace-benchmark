"""Regenerate predeclared stress tasks and prove their checkpoint Gold equivalence."""

import shutil
from pathlib import Path

from disastertrace.automated.common import fingerprint, read_jsonl, write_jsonl
from disastertrace.controlled import compiler, public_oracle, renderer, runtime, scorer
from disastertrace.controlled.schema import METHODS
from disastertrace.local_eval import data as balanced
from disastertrace.local_eval import difficulty
from disastertrace.local_eval.storage import read, seal, verify_seal, write

PROFILE = "controlled_stress_level4_data_v1"
LEVEL = 4
FACTORS = difficulty.FACTORS


def denominators(value, prefix=()):
    result = {}
    if isinstance(value, dict):
        if {"numerator", "denominator"} <= value.keys():
            result[prefix] = value["denominator"]
        for key, child in value.items():
            result.update(denominators(child, (*prefix, key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.update(denominators(child, (*prefix, index)))
    return result


def select(base, candidates, factor):
    if factor not in FACTORS:
        raise ValueError("only the three predeclared stress factors are supported")
    expected = [
        difficulty.transform(ep, f, level)
        for f in FACTORS
        for level in difficulty.LEVELS
        for ep in base
    ]
    if candidates != expected:
        raise ValueError("predeclared candidate regeneration mismatch")
    return [difficulty.transform(ep, factor, LEVEL) for ep in base]


def schedule(episodes, base_slots):
    mapping = {ep["episode_id"].rsplit(":", 1)[0]: ep for ep in episodes}
    slots = []
    for slot in base_slots:
        ep = mapping[slot["episode_id"]]
        trajectory = slot["method"] + ":" + ep["episode_id"]
        slots.append(
            {
                **slot,
                "episode_id": ep["episode_id"],
                "trajectory_id": trajectory,
                "slot_id": trajectory + ":" + slot["checkpoint_id"],
                "base_episode_id": slot["episode_id"],
                "base_slot_id": slot["slot_id"],
            }
        )
    return slots


def core(base, episodes, base_slots):
    gold, proof, effective = [], [], []
    for original, ep in zip(base, episodes, strict=True):
        effective.append(
            {
                "base_episode_id": original["episode_id"],
                "episode_id": ep["episode_id"],
                "added_records": len(ep["records"]) - len(original["records"]),
                "added_deliveries": len(ep["deliveries"]) - len(original["deliveries"]),
            }
        )
        for cp in ep["checkpoints"]:
            checkpoint = cp["checkpoint_id"]
            answer = compiler.reference_at(ep, checkpoint)
            old = compiler.reference_at(original, checkpoint)
            if answer != old:
                raise ValueError("stress transformation changed checkpoint Gold")
            gold.append(
                {"episode_id": ep["episode_id"], "checkpoint_id": checkpoint, "reference": answer}
            )
            proof.append(
                {
                    "episode_id": ep["episode_id"],
                    "base_episode_id": original["episode_id"],
                    "checkpoint_id": checkpoint,
                    "base_reference_sha256": fingerprint(old),
                    "stress_reference_sha256": fingerprint(answer),
                }
            )
    return {
        "episodes": episodes,
        "schedule": schedule(episodes, base_slots),
        "gold": gold,
        "gold_equivalence": proof,
        "effective_factor_counts": effective,
    }


def diagnose(base, episodes):
    comparisons = 0
    for ep in episodes:
        for cp in ep["checkpoints"]:
            answer = compiler.reference_at(ep, cp["checkpoint_id"])
            for method in METHODS:
                request = renderer.render_request(ep, cp["checkpoint_id"], method=method)
                if public_oracle.answer(request) != answer:
                    raise ValueError("stress public oracle disagrees with private Gold")
                comparisons += 1
    scores, opportunity_checks = {}, {}
    for method in METHODS:
        original = scorer.score(base, runtime.rehearse(base, method), method)
        for backend in (*public_oracle.backends, "invalid-control"):
            score = scorer.score(episodes, runtime.rehearse(episodes, method, backend), method)
            if denominators(score) != denominators(original):
                raise ValueError("stress metric denominators changed")
            for before, after in zip(
                original["per_checkpoint"], score["per_checkpoint"], strict=True
            ):
                if any(
                    before["counts"][denominator] != after["counts"][denominator]
                    for _, denominator in scorer.METRICS.values()
                ):
                    raise ValueError("stress checkpoint opportunity changed")
            if backend in ("correct", "per-key-latest-issued") and (
                score["metrics"]["all_correct_checkpoints"]["numerator"] != 180
            ):
                raise ValueError("correct stress control failed")
            if backend == "invalid-control" and (
                score["metrics"]["schema_success"]["numerator"] != 144
            ):
                raise ValueError("invalid stress control was dropped or repaired")
            scores[method + "/" + backend] = score
        opportunity_checks[method] = {
            "metric_denominators": len(denominators(original)),
            "checkpoint_opportunities": len(original["per_checkpoint"]),
        }
    return {
        "oracle_comparisons": comparisons,
        "diagnostic_responses": len(episodes)
        * 5
        * len(METHODS)
        * (len(public_oracle.backends) + 1),
        "opportunity_checks": opportunity_checks,
        "scores": scores,
        "model_calls": 0,
    }


def metadata(base_plan, candidate_id, factor, content):
    identity = {
        "profile": PROFILE,
        "factor": factor,
        "level": LEVEL,
        "base_dataset_content_id": base_plan["dataset_content_id"],
        "candidate_package_id": candidate_id,
        **content,
    }
    return {
        "profile": PROFILE,
        "factor": factor,
        "level": LEVEL,
        "dataset_content_id": fingerprint(identity),
        "base_dataset_content_id": base_plan["dataset_content_id"],
        "candidate_package_id": candidate_id,
        "source_groups": base_plan["source_groups"],
        "episodes": 36,
        "matched_roots": 18,
        "trajectories": 108,
        "planned_responses": 540,
        "schedule_order": "same_base_slot_order_with_distinct_stress_identities",
        "sampling_seeds": "derived_from_new_slot_ids_using_unchanged_adapter",
        "gold_equivalence_checkpoints": 180,
        "zero_effect_episodes": sum(
            row["added_records"] == row["added_deliveries"] == 0
            for row in content["effective_factor_counts"]
        ),
        "selection_depends_on_model_errors": False,
        "new_independent_weather_events": 0,
        "model_calls": 0,
        "heldout_calls": 0,
        "new_human_annotations": 0,
        "llm_judge": False,
    }


def prepare(base_dataset, candidates, output, *, factor):
    base_dataset, candidates, output = map(Path, (base_dataset, candidates, output))
    if output.exists():
        raise ValueError("preserve existing stress dataset")
    base_plan, base, base_slots = balanced.verify(base_dataset, full=False)
    candidate_id = verify_seal(candidates)["package_id"]
    episodes = select(base, read_jsonl(candidates / "episodes.jsonl"), factor)
    content = core(base, episodes, base_slots)
    diagnostics = diagnose(base, episodes)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(base_dataset, output / "base_dataset")
    shutil.copytree(candidates, output / "candidates")
    for name in ("episodes", "schedule", "gold", "gold_equivalence", "effective_factor_counts"):
        prefix = "private/" if name in ("gold", "gold_equivalence") else ""
        write_jsonl(output / (prefix + name + ".jsonl"), content[name])
    write(output / "diagnostics.json", diagnostics)
    plan = metadata(base_plan, candidate_id, factor, content)
    write(output / "plan.json", plan)
    manifest = seal(output)
    return {**plan, "package_id": manifest["package_id"]}


def verify(output, *, full=True):
    output = Path(output)
    verify_seal(output)
    plan = read(output / "plan.json")
    base_plan, base, base_slots = balanced.verify(output / "base_dataset", full=False)
    candidate_id = verify_seal(output / "candidates")["package_id"]
    episodes = select(base, read_jsonl(output / "candidates/episodes.jsonl"), plan["factor"])
    content = core(base, episodes, base_slots)
    expected = metadata(base_plan, candidate_id, plan["factor"], content)
    if plan != expected:
        raise ValueError("stress profile metadata or identity changed")
    for name in ("episodes", "schedule", "gold", "gold_equivalence", "effective_factor_counts"):
        prefix = "private/" if name in ("gold", "gold_equivalence") else ""
        if read_jsonl(output / (prefix + name + ".jsonl")) != content[name]:
            raise ValueError("stress regeneration mismatch: " + name)
    if full and read(output / "diagnostics.json") != diagnose(base, episodes):
        raise ValueError("stress diagnostics changed")
    return plan, episodes, content["schedule"]
