"""Assign whole paired episodes to workers without making executable model claims."""

from collections import Counter, defaultdict

from disastertrace.automated.common import fingerprint
from disastertrace.repeat_eval import protocol


def prepare(plan, slots, worker_count=4):
    if type(worker_count) is not int or worker_count not in (1, 2, 4):
        raise ValueError("balanced four-variant strata support one, two or four workers")
    if slots != protocol.schedule(plan):
        raise ValueError("input schedule differs from the frozen paired protocol")
    metadata = plan["mapping"]
    if not metadata or len({m["base_episode_id"] for m in metadata}) != len(metadata):
        raise ValueError("unique nonempty episode metadata required")
    strata = defaultdict(list)
    for item in metadata:
        strata[item["group_id"], item["family"]].append(item)
    ownership = {}
    for stratum_index, (_, items) in enumerate(sorted(strata.items())):
        variants = sorted(items, key=lambda m: (m["case"], m["branch"], m["base_episode_id"]))
        if len(variants) != 4 or len({(m["case"], m["branch"]) for m in variants}) != 4:
            raise ValueError("each source/family stratum needs four distinct case/branch variants")
        # Rotate variants across strata; each worker retains an episode's methods and repeats.
        for index, item in enumerate(variants):
            ownership[item["base_episode_id"]] = (index + stratum_index) % worker_count
    workers = []
    for worker in range(worker_count):
        selected = [s for s in slots if ownership[s["base_episode_id"]] == worker]
        strata_counts = Counter((s["group_id"], s["family"]) for s in selected)
        cells = Counter((s["group_id"], s["condition"], s["method"], s["repeat"]) for s in selected)
        variants = Counter((s["case"], s["branch"]) for s in selected)
        workers.append(
            {
                "worker_index": worker,
                "gpus": 1,
                "tensor_parallel_size": 1,
                "base_episode_ids": sorted(k for k, v in ownership.items() if v == worker),
                "source_slot_indices": [s["slot_index"] for s in selected],
                "source_slot_ids": [s["slot_id"] for s in selected],
                "opportunities": len(selected),
                "trajectories": len({s["trajectory_id"] for s in selected}),
                "pairs": len({s["pair_id"] for s in selected}),
                "batches_at_original_cap": len(list(protocol.batches(selected))),
                "source_family_counts": [
                    {"source": group, "family": family, "opportunities": count}
                    for (group, family), count in sorted(strata_counts.items())
                ],
                "source_condition_method_repeat_counts": [
                    {
                        "source": group,
                        "condition": condition,
                        "method": method,
                        "repeat": repeat,
                        "opportunities": count,
                    }
                    for (group, condition, method, repeat), count in sorted(cells.items())
                ],
                "case_branch_counts": [
                    {"case": case, "branch": branch, "opportunities": count}
                    for (case, branch), count in sorted(variants.items())
                ],
            }
        )
    result = {
        "schema_version": "paired_parallel_layout_preview_v1",
        "source_execution_id": plan["execution_id"],
        "source_schedule_fingerprint": fingerprint(slots),
        "generation_authorized": False,
        "dispatch_compatible": False,
        "worker_count": worker_count,
        "total_gpus": worker_count,
        "assignment_unit": "base_episode_all_conditions_methods_repeats_checkpoints",
        "source_opportunities": len(slots),
        "source_trajectories": len({s["trajectory_id"] for s in slots}),
        "source_pairs": len({s["pair_id"] for s in slots}),
        "workers": workers,
        "fresh_execution_and_attempt_identities_required": True,
        "source_single_worker_run_must_not_be_rescheduled": True,
        "expected_speedup_measured": False,
        "model_generations": 0,
        "gpu_submissions": 0,
    }
    result["layout_id"] = fingerprint(result)
    validate(result, slots)
    return result


def validate(layout, slots):
    if layout["layout_id"] != fingerprint({k: v for k, v in layout.items() if k != "layout_id"}):
        raise ValueError("layout identity differs")
    if layout["generation_authorized"] is not False or layout["dispatch_compatible"] is not False:
        raise ValueError("preview cannot authorize model dispatch")
    if (
        layout["source_schedule_fingerprint"] != fingerprint(slots)
        or layout["source_opportunities"] != len(slots)
        or layout["source_trajectories"] != len({s["trajectory_id"] for s in slots})
        or layout["source_pairs"] != len({s["pair_id"] for s in slots})
        or layout["fresh_execution_and_attempt_identities_required"] is not True
        or layout["source_single_worker_run_must_not_be_rescheduled"] is not True
        or layout["expected_speedup_measured"] is not False
        or type(layout["model_generations"]) is not int
        or layout["model_generations"] != 0
        or type(layout["gpu_submissions"]) is not int
        or layout["gpu_submissions"] != 0
    ):
        raise ValueError("source summary or non-execution boundary differs")
    count = layout["worker_count"]
    if type(count) is not int or count not in (1, 2, 4) or layout["total_gpus"] != count:
        raise ValueError("unsupported worker count or GPU allocation")
    if len(layout["workers"]) != count:
        raise ValueError("worker inventory differs")
    assigned = {}
    group_owner = {}
    cell_tables = []
    for index, worker in enumerate(layout["workers"]):
        if (
            type(worker["worker_index"]) is not int
            or worker["worker_index"] != index
            or type(worker["gpus"]) is not int
            or worker["gpus"] != 1
            or type(worker["tensor_parallel_size"]) is not int
            or worker["tensor_parallel_size"] != 1
        ):
            raise ValueError("worker hardware proposal differs")
        indices = worker["source_slot_indices"]
        if indices != sorted(set(indices)) or any(
            type(i) is not int or not 0 <= i < len(slots) for i in indices
        ):
            raise ValueError("worker schedule indices are duplicated, reordered or invalid")
        selected = [slots[i] for i in indices]
        if worker["source_slot_ids"] != [s["slot_id"] for s in selected]:
            raise ValueError("worker source slot binding differs")
        if worker["base_episode_ids"] != sorted({s["base_episode_id"] for s in selected}):
            raise ValueError("worker episode inventory differs")
        for slot in selected:
            if slot["slot_index"] in assigned:
                raise ValueError("opportunity assigned to multiple workers")
            assigned[slot["slot_index"]] = index
            for kind in ("base_episode_id", "trajectory_id", "pair_id"):
                key = kind, slot[kind]
                if key in group_owner and group_owner[key] != index:
                    raise ValueError("a paired episode or trajectory crosses workers")
                group_owner[key] = index
        expected = {
            "opportunities": len(selected),
            "trajectories": len({s["trajectory_id"] for s in selected}),
            "pairs": len({s["pair_id"] for s in selected}),
            "batches_at_original_cap": len(list(protocol.batches(selected))),
        }
        if any(worker[k] != v for k, v in expected.items()):
            raise ValueError("worker opportunity summary differs")
        strata = Counter((s["group_id"], s["family"]) for s in selected)
        method_cells = Counter(
            (s["group_id"], s["condition"], s["method"], s["repeat"]) for s in selected
        )
        variants = Counter((s["case"], s["branch"]) for s in selected)
        expected_tables = {
            "source_family_counts": [
                {"source": group, "family": family, "opportunities": number}
                for (group, family), number in sorted(strata.items())
            ],
            "source_condition_method_repeat_counts": [
                {
                    "source": group,
                    "condition": condition,
                    "method": method,
                    "repeat": repeat,
                    "opportunities": number,
                }
                for (group, condition, method, repeat), number in sorted(method_cells.items())
            ],
            "case_branch_counts": [
                {"case": case, "branch": branch, "opportunities": number}
                for (case, branch), number in sorted(variants.items())
            ],
        }
        if any(worker[k] != v for k, v in expected_tables.items()):
            raise ValueError("worker balance tables differ from assigned opportunities")
        cells = Counter(
            (s["group_id"], s["family"], s["condition"], s["method"], s["repeat"]) for s in selected
        )
        cell_tables.append(cells)
    if set(assigned) != set(range(len(slots))):
        raise ValueError("not all source opportunities are assigned")
    if any(table != cell_tables[0] for table in cell_tables[1:]):
        raise ValueError("source/family/condition/method/repeat balance differs across workers")
    return {
        "status": "passed",
        "workers": count,
        "opportunities": len(assigned),
        "model_generations": 0,
    }
