"""A full fresh matrix changing only public target IDs after the first pilot."""

import copy
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.active_warning_v1 import Episode, Outcome
from gpu_worker import digest, save

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]


def main():
    original = BASE / "gpu_01"
    old = json.loads((original / "PLAN.json").read_text())
    for name, sha in old["evaluation_bindings"].items():
        if digest(REPO / name) != sha:
            raise ValueError("first-pilot evaluation input changed")
    data = BASE / "dataset_short_ids_v1"
    data.mkdir(exist_ok=False)
    episodes = json.loads((BASE / "dataset_v2/episodes.json").read_text())
    aliases = {e["id"]: f"t{i:03d}" for i, e in enumerate(episodes, 1)}
    new_episodes = []
    for episode in episodes:
        updated = {**episode, "id": aliases[episode["id"]]}
        Episode.model_validate(updated)
        new_episodes.append(updated)
    outcomes = json.loads((BASE / "dataset_v2/outcomes_private.json").read_text())
    new_outcomes = []
    for outcome in outcomes:
        updated = {**outcome, "episode_id": aliases[outcome["episode_id"]]}
        Outcome.model_validate(updated)
        new_outcomes.append(updated)
    pilot = json.loads((BASE / "dataset_v2/pilot_ids.json").read_text())
    save(data / "episodes.json", new_episodes)
    save(data / "outcomes_private.json", new_outcomes)
    save(data / "pilot_ids.json", [aliases[eid] for eid in pilot])
    save(data / "ALIAS_MAP.json", aliases)
    shutil.copyfile(
        BASE / "dataset_v2/SOURCE_BINDINGS.json", data / "SOURCE_BINDINGS.json"
    )
    save(
        data / "AMENDMENT.json",
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "reason": "17 of 400 first-pilot forecast replies copied long opaque target IDs incorrectly",
            "change": "short public target handles; original content identifiers retained in ALIAS_MAP",
            "unchanged": [
                "source values",
                "source times",
                "outcomes",
                "pilot selection",
                "model",
                "prompts",
                "policies",
                "scenarios",
                "budgets",
                "scorer",
                "all 200 trajectories",
            ],
            "selection_based_on_model_errors": False,
            "target_number_is_not_an_outcome_label": True,
            "exposed_development_only": True,
        },
    )
    batch = BASE / "gpu_02"
    batch.mkdir(exist_ok=False)
    save(
        batch / "episodes.json",
        [e for e in new_episodes if e["id"] in {aliases[x] for x in pilot}],
    )
    for name, sha in old["files"].items():
        if digest(original / name) != sha:
            raise ValueError("first-pilot frozen runtime changed")
        if name.startswith("source/"):
            dest = batch / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original / name, dest)
    plan = copy.deepcopy(old)
    plan["frozen_at"] = datetime.now(timezone.utc).isoformat()
    plan["amends_plan_sha256"] = digest(original / "PLAN.json")
    plan["amendment"] = (
        "full development rerun with short target IDs; no selective replacements"
    )
    plan["evaluator_outcomes_path"] = str(
        (data / "outcomes_private.json").relative_to(REPO)
    )
    for tasks in plan["workers"].values():
        for task in tasks:
            task["episode_id"] = aliases[task["episode_id"]]
            task["run_id"] = (
                task["episode_id"] + "-" + task["scenario"] + "-" + task["policy"]
            )
    plan["files"] = {
        str(p.relative_to(batch)): digest(p) for p in batch.rglob("*") if p.is_file()
    }
    for path in [*data.glob("*.json"), Path(__file__), BASE / "collect_models.py"]:
        plan["evaluation_bindings"][str(path.relative_to(REPO))] = digest(path)
    save(batch / "PLAN.json", plan)
    print(
        json.dumps(
            {
                "batch": str(batch),
                "plan_sha256": digest(batch / "PLAN.json"),
                "targets": len(pilot),
                "trajectories": 200,
                "maximum_model_calls": 560,
                "change": "only target identifiers",
            }
        )
    )


if __name__ == "__main__":
    main()
