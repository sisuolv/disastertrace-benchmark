import copy
from collections import Counter, defaultdict

import pytest

from disastertrace.automated.common import fingerprint
from disastertrace.repeat_eval import protocol
from disastertrace.repeat_parallel.layout import prepare, validate


@pytest.fixture
def matrix():
    metadata = []
    for source in ("storm-a", "storm-b", "storm-c"):
        for family in ("U1", "U2", "U3"):
            for case in ("primary", "secondary"):
                for branch in ("active", "control"):
                    episode = f"{source}:{family}:{case}:{branch}"
                    metadata.append(
                        {
                            "base_episode_id": episode,
                            "group_id": source,
                            "family": family,
                            "case": case,
                            "branch": branch,
                            "episodes": {"base": episode, "irrelevant_scope": episode + ":scope"},
                        }
                    )
    plan = {
        "execution_id": "synthetic-layout-fixture",
        "experiment_id": "synthetic-no-generation",
        "model_identity": "fixture-not-a-model",
        "repeats": 2,
        "mapping": metadata,
    }
    return plan, protocol.schedule(plan)


def rehash(layout):
    layout["layout_id"] = fingerprint({k: v for k, v in layout.items() if k != "layout_id"})


@pytest.mark.parametrize("workers", (1, 2, 4))
def test_all_opportunities_are_balanced_without_splitting_episodes(matrix, workers):
    plan, slots = matrix
    layout = prepare(plan, slots, workers)
    assert layout == prepare(plan, slots, workers)
    assert layout["source_opportunities"] == 2160
    assert layout["source_trajectories"] == 432
    assert layout["source_pairs"] == 1080
    assigned, owners, balances = [], defaultdict(set), []
    for worker in layout["workers"]:
        selected = [slots[i] for i in worker["source_slot_indices"]]
        assigned.extend(worker["source_slot_indices"])
        assert worker["opportunities"] == 2160 // workers
        assert worker["batches_at_original_cap"] == 180 // workers
        assert len(worker["base_episode_ids"]) == 36 // workers
        for slot in selected:
            owners[slot["base_episode_id"]].add(worker["worker_index"])
        balances.append(
            Counter(
                (s["group_id"], s["family"], s["method"], s["condition"], s["repeat"])
                for s in selected
            )
        )
        assert set(Counter(s["trajectory_id"] for s in selected).values()) == {5}
        assert set(Counter(s["pair_id"] for s in selected).values()) == {2}
        assert worker["source_slot_indices"] == sorted(worker["source_slot_indices"])
    assert sorted(assigned) == list(range(2160))
    assert all(len(value) == 1 for value in owners.values())
    assert all(balances[0] == b for b in balances)
    assert validate(layout, slots)["model_generations"] == 0


@pytest.mark.parametrize("workers", (0, 3, 5, True))
def test_unsupported_or_boolean_gpu_count_fails(matrix, workers):
    with pytest.raises(ValueError, match="one, two or four"):
        prepare(*matrix, workers)


@pytest.mark.parametrize("corruption", ("missing", "duplicate", "seed", "reorder"))
def test_input_schedule_mutation_fails(matrix, corruption):
    plan, original = matrix
    slots = copy.deepcopy(original)
    if corruption == "missing":
        slots.pop()
    elif corruption == "duplicate":
        slots.append(slots[0])
    elif corruption == "seed":
        slots[0]["sampling_seed"] += 1
    else:
        slots[0], slots[1] = slots[1], slots[0]
    with pytest.raises(ValueError, match="input schedule"):
        prepare(plan, slots)


@pytest.mark.parametrize(
    "field", ("generation_authorized", "dispatch_compatible", "expected_speedup_measured")
)
def test_rehashed_preview_cannot_claim_dispatch_or_measured_speedup(matrix, field):
    layout = prepare(*matrix)
    layout[field] = True
    rehash(layout)
    with pytest.raises(ValueError):
        validate(layout, matrix[1])


def test_rehashed_opportunity_and_balance_summaries_are_checked(matrix):
    original = prepare(*matrix)
    for corruption in ("total", "worker_total", "strata"):
        layout = copy.deepcopy(original)
        if corruption == "total":
            layout["source_opportunities"] -= 1
        elif corruption == "worker_total":
            layout["workers"][0]["opportunities"] -= 1
        else:
            layout["workers"][0]["source_family_counts"][0]["opportunities"] -= 1
        rehash(layout)
        with pytest.raises(ValueError):
            validate(layout, matrix[1])


def test_rehashed_cross_worker_trajectory_is_rejected(matrix):
    plan, slots = matrix
    layout = prepare(plan, slots)
    original_worker, other_worker = layout["workers"][:2]
    moved = original_worker["source_slot_indices"].pop()
    original_worker["source_slot_ids"].pop()
    other_worker["source_slot_indices"].append(moved)
    other_worker["source_slot_indices"].sort()
    other_worker["source_slot_ids"] = [
        slots[i]["slot_id"] for i in other_worker["source_slot_indices"]
    ]
    rehash(layout)
    with pytest.raises(ValueError):
        validate(layout, slots)


def test_non_four_variant_stratum_fails(matrix):
    plan, _ = matrix
    plan["mapping"].pop()
    with pytest.raises(ValueError, match="four distinct"):
        prepare(plan, protocol.schedule(plan))


def test_single_worker_preserves_original_schedule_and_ids(matrix):
    layout = prepare(*matrix, worker_count=1)
    assert layout["workers"][0]["source_slot_indices"] == list(range(2160))
    assert layout["workers"][0]["source_slot_ids"] == [s["slot_id"] for s in matrix[1]]
    assert "attempt_id" not in layout["workers"][0]
    assert layout["fresh_execution_and_attempt_identities_required"] is True
