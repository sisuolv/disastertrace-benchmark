"""Residual E reference uses a single actual resource/authorization state."""

import pytest

from disastertrace.monitoring_v1.reachability import Goal
from disastertrace.monitoring_v1.resources import BudgetLedger, Cost
from disastertrace.monitoring_v1.views import EvidenceStore


def query(key, owner="A", *, upper=1, actual=1, duration=1):
    from disastertrace.monitoring_v1.residual_reachability import ResidualQuery

    return ResidualQuery(key + "@" + owner, key, owner, {"query_id": key},
                         Cost(requests=upper), Cost(requests=actual), 0, duration)


def solve(ledger, store, queries, goals, **kw):
    from disastertrace.monitoring_v1.residual_reachability import solve_residual

    return solve_residual(ledger, store, queries, goals, start=0, **kw)


def test_spent_and_unresolved_reservations_cannot_be_spent_again():
    ledger = BudgetLedger({"requests": 3})
    ledger.reserve("paid", Cost(requests=1), "A")
    ledger.settle("paid", Cost(requests=1))
    ledger.reserve("remote", Cost(requests=1), "B")
    ledger.mark_unknown("remote", {"original_response_missing": True})
    store = EvidenceStore("session_shared", ["A", "B"])
    goals = [Goal("A", 5, (frozenset({"x"}),)), Goal("B", 5, (frozenset({"y"}),))]
    result = solve(ledger, store, [query("x"), query("y", "B")], goals)
    assert result["exact"] and result["lower_bound"] == result["upper_bound"] == 1
    assert set(result["individual_status"].values()) == {"reachable_relaxation"}
    assert ledger.spent.requests == ledger.reserved.requests == 1


def test_cached_shared_asset_is_free_but_private_cache_does_not_grant_others():
    for mode, expected in [("session_shared", 2), ("target_private", 1)]:
        ledger = BudgetLedger({"requests": 1})
        ledger.reserve("paid", Cost(requests=1), "A")
        ledger.settle("paid", Cost(requests=1))
        store = EvidenceStore(mode, ["A", "B"])
        store.register("cached", {"query_id": "cached"}, owner="A", receipt_id="paid")
        goals = [Goal(t, 5, (frozenset({"cached"}),)) for t in ("A", "B")]
        result = solve(ledger, store, [], goals, cached_completed={"cached": 0})
        assert result["lower_bound"] == expected


def test_shared_asset_has_one_payer_and_must_fit_that_payers_quota():
    ledger = BudgetLedger({"requests": 2}, allocation_mode="fixed_quota",
                          quotas={"A": {"requests": 0}, "B": {"requests": 2}})
    store = EvidenceStore("session_shared", ["A", "B"])
    goals = [Goal(t, 5, (frozenset({"shared"}),)) for t in ("A", "B")]
    denied = solve(ledger, store, [query("shared")], goals)
    admitted = solve(ledger, store, [query("shared"), query("shared", "B")], goals)
    assert denied["upper_bound"] == 0 and admitted["lower_bound"] == 2
    best = next(w for w in admitted["frontier"] if len(w["resolved"]) == 2)
    assert len(best["actions"]) == 1 and best["actions"][0]["query_key"] == "shared@B"


def test_reservation_upper_must_fit_even_when_known_actual_is_cheaper():
    ledger = BudgetLedger({"requests": 2})
    store = EvidenceStore("session_shared", ["A", "B"])
    qs = [query("x", upper=2), query("y", "B", upper=2)]
    goals = [Goal("A", 5, (frozenset({"x"}),)), Goal("B", 5, (frozenset({"y"}),))]
    assert solve(ledger, store, qs, goals)["upper_bound"] == 1


def test_serial_completion_cannot_splice_fast_time_and_cheap_path():
    ledger = BudgetLedger({"requests": 1})
    store = EvidenceStore("session_shared", ["A"])
    qs = [query("slow", duration=8), query("fast", upper=2, actual=2)]
    goals = [Goal("A", 1, (frozenset({"slow"}), frozenset({"fast"}))) ]
    assert solve(ledger, store, qs, goals)["upper_bound"] == 0


def test_actual_ledger_independently_replays_every_returned_witness():
    from disastertrace.monitoring_v1.residual_reachability import replay_residual_witness

    ledger = BudgetLedger({"requests": 2})
    store = EvidenceStore("session_shared", ["A", "B"])
    qs = [query("x"), query("y", "B")]
    goals = [Goal("A", 2, (frozenset({"x"}),)), Goal("B", 2, (frozenset({"y"}),))]
    result = solve(ledger, store, qs, goals)
    for witness in result["frontier"]:
        assert replay_residual_witness(witness, ledger, store, qs, goals, start=0)["passed"]
    best = next(w for w in result["frontier"] if len(w["resolved"]) == 2)
    best["actions"][1]["started_at"] = 0
    with pytest.raises(ValueError, match="serial|duration"):
        replay_residual_witness(best, ledger, store, qs, goals, start=0)


def test_search_truncation_keeps_a_bound_and_does_not_declare_unreachable():
    ledger = BudgetLedger({"requests": 2})
    store = EvidenceStore("session_shared", ["A"])
    result = solve(ledger, store, [query("x")], [Goal("A", 5, (frozenset({"x"}),))], max_states=1)
    assert not result["exact"] and result["upper_bound"] == 1
    assert result["individual_status"]["A"] == "unknown_search_truncated"


def test_a_cache_without_an_actual_paid_receipt_is_rejected():
    ledger = BudgetLedger({"requests": 2})
    store = EvidenceStore("session_shared", ["A"])
    store.register("x", {}, owner="A", receipt_id="invented")
    with pytest.raises(ValueError, match="receipt|settled"):
        solve(ledger, store, [], [Goal("A", 5, (frozenset({"x"}),))], cached_completed={"x": 0})
