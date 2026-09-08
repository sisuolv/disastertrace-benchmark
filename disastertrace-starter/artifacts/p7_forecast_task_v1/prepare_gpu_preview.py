"""No-dispatch four-worker preview for irregular native target episode lengths."""

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from disastertrace.forecast_task.common import digest, fingerprint, read, verify, write


def build(execution):
    execution = Path(execution)
    verify(execution)
    plan = read(execution / "execution.json")
    public = read(execution / "data/public.json")
    slots = read(execution / "schedule.json")
    groups = defaultdict(list)
    for index, slot in enumerate(slots):
        groups[slot["episode_id"]].append(index)
    assignments = [[] for _ in range(4)]
    storms = sorted({e["query"]["storm_id"] for e in public["episodes"].values()})
    storm_loads = [Counter() for _ in range(4)]
    total_loads = [0] * 4
    for storm in storms:
        episodes = sorted(
            (eid for eid in groups if public["episodes"][eid]["query"]["storm_id"] == storm),
            key=lambda eid: (-len(groups[eid]), public["episodes"][eid]["query"]["valid_at"], eid),
        )
        for episode in episodes:
            worker = min(range(4), key=lambda w: (storm_loads[w][storm], total_loads[w], w))
            assignments[worker].extend(groups[episode])
            storm_loads[worker][storm] += len(groups[episode])
            total_loads[worker] += len(groups[episode])
    workers = []
    for worker_id, indices in enumerate(assignments):
        selected = [slots[i] for i in sorted(indices)]
        workers.append(
            {
                "worker_id": worker_id,
                "source_slot_indices": sorted(indices),
                "source_slot_ids": [s["slot_id"] for s in selected],
                "episode_ids": sorted({s["episode_id"] for s in selected}),
                "planned_answers": len(selected),
                "trajectories": len({s["trajectory_id"] for s in selected}),
                "by_storm": dict(sorted(storm_loads[worker_id].items())),
                "by_method": dict(sorted(Counter(s["method"] for s in selected).items())),
                "by_repeat": dict(sorted(Counter(str(s["repeat"]) for s in selected).items())),
            }
        )
    result = {
        "schema_version": "forecast_task_four_worker_preview_v1",
        "source_execution_id": plan["execution_id"],
        "recipe_sha256": digest(__file__),
        "assignment_rule": "per-storm descending episode length; least storm load then total load then worker ID",
        "worker_count": 4,
        "gpus_per_worker": 1,
        "tensor_parallel_size": 1,
        "planned_answers": len(slots),
        "workers": workers,
        "generation_authorized": False,
        "dispatch_compatible": False,
        "source_slot_ids_are_provenance_not_live_attempt_claims": True,
        "measured_speedup": None,
    }
    result["layout_id"] = fingerprint(result)
    validate(result, slots)
    return result


def validate(layout, slots):
    if layout["generation_authorized"] is not False or layout["dispatch_compatible"] is not False:
        raise ValueError("preview cannot dispatch")
    all_indices, ownership = [], {}
    for worker in layout["workers"]:
        indices = worker["source_slot_indices"]
        if worker["planned_answers"] != len(indices) or worker["source_slot_ids"] != [
            slots[i]["slot_id"] for i in indices
        ]:
            raise ValueError("worker count or slot identity differs")
        all_indices.extend(indices)
        for index in indices:
            episode = slots[index]["episode_id"]
            if episode in ownership and ownership[episode] != worker["worker_id"]:
                raise ValueError("target episode split across workers")
            ownership[episode] = worker["worker_id"]
    if sorted(all_indices) != list(range(len(slots))):
        raise ValueError("worker slots are not a disjoint complete cover")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = build(args.execution)
    if args.verify:
        if read(args.output) != result:
            raise ValueError("saved worker preview differs")
    else:
        write(args.output, result)
    print(
        {
            "layout_id": result["layout_id"],
            "planned": result["planned_answers"],
            "per_worker": [w["planned_answers"] for w in result["workers"]],
            "generation_authorized": False,
        }
    )


if __name__ == "__main__":
    main()
