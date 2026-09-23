import pytest

from disastertrace.monitoring_v1.reachability import (
    Goal,
    Query,
    Witness,
    solve_joint,
    validate_witness,
)
from disastertrace.monitoring_v1.resources import Cost


def test_two_individual_paths_are_not_jointly_feasible():
    queries = [Query("a", Cost(requests=1), 0, 1), Query("b", Cost(requests=1), 0, 1)]
    goals = [Goal("A", 3, (frozenset({"a"}),)), Goal("B", 3, (frozenset({"b"}),))]
    result = solve_joint(queries, goals, {"requests": 1}, concurrency=2)
    assert result.exact
    assert result.individual_status == {"A": "reachable_relaxation", "B": "reachable_relaxation"}
    assert result.lower_bound == result.upper_bound == 1
    assert all(len(w.resolved) <= 1 for w in result.frontier)


def test_shared_product_resolves_two_with_one_payment():
    query = Query("shared", Cost(requests=1), 0, 1)
    result = solve_joint(
        [query], [Goal(t, 3, (frozenset({"shared"}),)) for t in ("A", "B")], {"requests": 1}
    )
    assert result.lower_bound == 2
    witness = next(w for w in result.frontier if set(w.resolved) == {"A", "B"})
    assert witness.cost.requests == 1
    assert len(witness.starts) == 1


def test_min_cost_and_min_completion_cannot_be_spliced():
    queries = [Query("cheap", Cost(requests=1), 0, 8), Query("fast", Cost(requests=2), 0, 1)]
    goal = Goal("A", 1, (frozenset({"cheap"}), frozenset({"fast"})))
    result = solve_joint(queries, [goal], {"requests": 1})
    assert result.lower_bound == 0
    assert result.individual_status["A"] == "unreachable_in_frozen_graph"
    wide = solve_joint(queries, [Goal("A", 10, goal.alternatives)], {"requests": 2})
    pairs = {(w.cost.requests, w.completion_time) for w in wide.frontier if "A" in w.resolved}
    assert (1, 8) in pairs and (2, 1) in pairs
    assert (1, 1) not in pairs


def test_concurrency_dependency_and_release_all_apply_to_one_path():
    queries = [Query("a", Cost(requests=1), 0, 2), Query("b", Cost(requests=1), 0, 2)]
    goals = [Goal("A", 2, (frozenset({"a"}),)), Goal("B", 2, (frozenset({"b"}),))]
    assert solve_joint(queries, goals, {"requests": 2}, concurrency=1).lower_bound == 1
    assert solve_joint(queries, goals, {"requests": 2}, concurrency=2).lower_bound == 2
    dependent = Query("b", Cost(requests=1), 0, 1, dependencies=frozenset({"a"}))
    assert (
        solve_joint([queries[0], dependent], [goals[1]], {"requests": 2}, concurrency=2).lower_bound
        == 0
    )
    released = Query("late", Cost(requests=1), 3, 1)
    assert (
        solve_joint([released], [Goal("A", 3, (frozenset({"late"}),))], {"requests": 1}).lower_bound
        == 0
    )


def test_equal_deadline_durable_completion_is_eligible():
    query = Query("q", Cost(requests=1), 1, 2)
    result = solve_joint([query], [Goal("A", 3, (frozenset({"q"}),))], {"requests": 1})
    assert result.lower_bound == 1


def test_expired_evidence_cannot_certify_current_goal():
    query = Query("old", Cost(requests=1), 0, 1, valid_until=2)
    result = solve_joint([query], [Goal("A", 3, (frozenset({"old"}),))], {"requests": 1})
    assert result.lower_bound == 0


def test_resources_are_componentwise_hard_limits():
    query = Query("q", Cost(requests=1, bytes=50, tokens=8), 0, 1)
    goals = [Goal("A", 2, (frozenset({"q"}),))]
    assert solve_joint([query], goals, {"requests": 2, "bytes": 49}).lower_bound == 0
    assert solve_joint([query], goals, {"requests": 1, "bytes": 50, "tokens": 8}).lower_bound == 1


def test_truncated_search_never_claims_exact_unreachability():
    query = Query("q", Cost(requests=1), 0, 1)
    result = solve_joint(
        [query], [Goal("A", 2, (frozenset({"q"}),))], {"requests": 1}, max_states=1
    )
    assert not result.exact
    assert result.lower_bound <= 1 <= result.upper_bound
    assert result.individual_status["A"] != "unreachable_in_frozen_graph"


def test_empty_recipe_is_already_supported_and_not_a_query_failure():
    result = solve_joint([], [Goal("A", 3, (frozenset(),))], {"requests": 0})
    assert result.lower_bound == 1


def test_invalid_graph_is_rejected_instead_of_silently_ignoring_dependencies():
    with pytest.raises(ValueError):
        solve_joint([Query("q", Cost(), 0, 1, dependencies=frozenset({"missing"}))], [], {})


def test_witness_rejects_spliced_completion_metadata():
    query = Query("cheap", Cost(requests=1), 0, 8)
    goal = Goal("A", 10, (frozenset({"cheap"}),))
    valid = Witness((("cheap", 0, 8),), ("A",), Cost(requests=1), 8)
    assert validate_witness(valid, [query], [goal], {"requests": 1})
    spliced = Witness(valid.starts, valid.resolved, valid.cost, 1)
    with pytest.raises(ValueError, match="completion"):
        validate_witness(spliced, [query], [goal], {"requests": 1})


def test_witness_rejects_queries_outside_frozen_horizon():
    query = Query("late", Cost(requests=1), 0, 8)
    goal = Goal("A", 3, (frozenset({"late"}),))
    outside = Witness((("late", 0, 8),), (), Cost(requests=1), 8)
    with pytest.raises(ValueError, match="horizon"):
        validate_witness(outside, [query], [goal], {"requests": 1})
