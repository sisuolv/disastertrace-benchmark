"""Exact, bounded scheduling for a frozen finite evidence-recipe graph.

This is an evaluator reference, not an online policy. Recipes must be compiled
from public support contracts; it does not infer physical truth from raw images.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass

from .resources import DIMENSIONS, Cost, validate_limits
from .targets import canonical_hash


@dataclass(frozen=True)
class Query:
    query_id: str
    cost: Cost
    released_at: int
    duration: int
    dependencies: frozenset[str] = frozenset()
    valid_until: int | None = None

    def __post_init__(self):
        if not self.query_id or type(self.duration) is not int or self.duration <= 0:
            raise ValueError("Queries need an identity and positive integer duration")


@dataclass(frozen=True)
class Goal:
    target_id: str
    deadline: int
    alternatives: tuple[frozenset[str], ...]
    weight: float = 1.0

    def __post_init__(self):
        if not self.target_id or not math.isfinite(self.weight) or self.weight <= 0:
            raise ValueError("Goals need an identity and positive finite weight")


@dataclass(frozen=True)
class Witness:
    starts: tuple[tuple[str, int, int], ...]
    resolved: tuple[str, ...]
    cost: Cost
    completion_time: int

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ReachabilityResult:
    exact: bool
    lower_bound: float
    upper_bound: float
    individual_status: dict[str, str]
    frontier: tuple[Witness, ...]
    explored_states: int
    max_states: int
    graph_hash: str
    scope: str = "finite_nonpreemptive_fixed_duration_public_recipe_graph"

    def to_dict(self):
        return asdict(self)


def _dominates(a: Witness, b: Witness):
    return (
        set(a.resolved) >= set(b.resolved)
        and a.completion_time <= b.completion_time
        and all(getattr(a.cost, k) <= getattr(b.cost, k) for k in DIMENSIONS)
    )


def solve_joint(
    queries: list[Query],
    goals: list[Goal],
    limits: Mapping[str, int | None],
    *,
    concurrency: int = 1,
    start: int = 0,
    max_states: int = 50000,
) -> ReachabilityResult:
    validate_limits(limits)
    qmap = {q.query_id: q for q in queries}
    if len(qmap) != len(queries) or len({g.target_id for g in goals}) != len(goals):
        raise ValueError("Duplicate graph identities")
    if concurrency < 1 or max_states < 1 or any(g.deadline < start for g in goals):
        raise ValueError("Invalid search limits or past deadline")
    if any(not q.dependencies <= qmap.keys() or q.query_id in q.dependencies for q in queries):
        raise ValueError("Invalid query dependencies")
    if any(not recipe <= qmap.keys() for g in goals for recipe in g.alternatives):
        raise ValueError("Unknown query in evidence recipe")
    graph = {
        "queries": [dict(asdict(q), dependencies=sorted(q.dependencies)) for q in queries],
        "goals": [dict(asdict(g), alternatives=[sorted(a) for a in g.alternatives]) for g in goals],
        "limits": dict(limits),
        "concurrency": concurrency,
        "start": start,
    }
    horizon = max((g.deadline for g in goals), default=start)
    # A state stores actual starts, hence joint cost/time combinations cannot be
    # accidentally assembled from unrelated single-target optima.
    pending = [(start, (), ())]
    seen = set()
    frontier = []
    reachable = set()
    lower = 0.0
    truncated = False
    while pending:
        time, starts, sealed = pending.pop()
        state_key = (time, starts, sealed)
        if state_key in seen:
            continue
        if len(seen) >= max_states:
            truncated = True
            break
        seen.add(state_key)
        selected = {q for q, _, _ in starts}
        complete = {q: finish for q, _, finish in starts if finish <= time}
        running = sum(finish > time for _, _, finish in starts)
        cost = Cost()
        for qid in selected:
            cost += qmap[qid].cost
        resolved = dict(sealed)
        for goal in goals:
            if goal.deadline <= time and goal.target_id not in resolved:
                eligible = {
                    qid
                    for qid, finish in complete.items()
                    if finish <= goal.deadline
                    and (qmap[qid].valid_until is None or goal.deadline <= qmap[qid].valid_until)
                }
                resolved[goal.target_id] = any(recipe <= eligible for recipe in goal.alternatives)
        sealed = tuple(sorted(resolved.items()))
        if time == horizon:
            satisfied = tuple(sorted(t for t, ok in resolved.items() if ok))
            reachable.update(satisfied)
            utility = sum(g.weight for g in goals if g.target_id in satisfied)
            lower = max(lower, utility)
            witness = Witness(
                starts, satisfied, cost, max((e for _, _, e in starts), default=start)
            )
            if not any(_dominates(w, witness) for w in frontier):
                frontier = [w for w in frontier if not _dominates(witness, w)] + [witness]
            continue
        next_times = [g.deadline for g in goals if g.deadline > time]
        next_times += [q.released_at for q in queries if time < q.released_at <= horizon]
        next_times += [end for _, _, end in starts if end > time]
        if next_times:
            pending.append((min(next_times), starts, sealed))
        if running < concurrency:
            for query in sorted(queries, key=lambda q: q.query_id, reverse=True):
                if (
                    query.query_id in selected
                    or query.released_at > time
                    or not query.dependencies <= complete.keys()
                    or time + query.duration > horizon
                    or not (cost + query.cost).within(limits)
                ):
                    continue
                updated = tuple(sorted(starts + ((query.query_id, time, time + query.duration),)))
                pending.append((time, updated, sealed))
    exact = not truncated
    statuses = {
        g.target_id: (
            "reachable_relaxation"
            if g.target_id in reachable
            else "unreachable_in_frozen_graph"
            if exact
            else "unknown_search_truncated"
        )
        for g in goals
    }
    return ReachabilityResult(
        exact,
        lower,
        lower if exact else sum(g.weight for g in goals),
        statuses,
        tuple(sorted(frontier, key=lambda w: (w.resolved, w.completion_time, w.starts))),
        len(seen),
        max_states,
        canonical_hash(graph),
    )


def validate_witness(
    witness: Witness, queries: list[Query], goals: list[Goal], limits, *, concurrency=1, start=0
):
    """Independent replay of a returned feasible path, including each cutoff."""
    validate_limits(limits)
    qmap = {q.query_id: q for q in queries}
    if (
        len(qmap) != len(queries)
        or len({g.target_id for g in goals}) != len(goals)
        or concurrency < 1
        or any(g.deadline < start for g in goals)
    ):
        raise ValueError("Invalid witness graph or limits")
    if len({q for q, _, _ in witness.starts}) != len(witness.starts):
        raise ValueError("Duplicate payment/execution")
    if any(q not in qmap for q, _, _ in witness.starts):
        raise ValueError("Unknown witness query")
    horizon = max((g.deadline for g in goals), default=start)
    if any(end > horizon for _, _, end in witness.starts):
        raise ValueError("Query exceeds the frozen horizon")
    if witness.completion_time != max((end for _, _, end in witness.starts), default=start):
        raise ValueError("Incorrect witness completion time")
    finishes = {q: end for q, _, end in witness.starts}
    total = Cost()
    for qid, begin, end in witness.starts:
        query = qmap[qid]
        if begin < max(start, query.released_at) or end != begin + query.duration:
            raise ValueError("Illegal release or duration")
        if any(dep not in finishes or finishes[dep] > begin for dep in query.dependencies):
            raise ValueError("Unmet dependency")
        total += query.cost
        if sum(b <= begin < e for _, b, e in witness.starts) > concurrency:
            raise ValueError("Concurrency limit")
    if total != witness.cost or not total.within(limits):
        raise ValueError("Incorrect joint cost")
    expected = []
    for goal in goals:
        eligible = {
            q
            for q, end in finishes.items()
            if end <= goal.deadline
            and (qmap[q].valid_until is None or goal.deadline <= qmap[q].valid_until)
        }
        if any(recipe <= eligible for recipe in goal.alternatives):
            expected.append(goal.target_id)
    if tuple(sorted(expected)) != witness.resolved:
        raise ValueError("Incorrect resolved set")
    return True
