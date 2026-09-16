"""Public-only query priorities, actual scheduling, and controller recovery."""

import copy

import pytest
from test_monitoring_forecast_schedule import expected_schedule, scheduled

from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.public_query_selectors import KINDS, query_priority
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator


def public():
    return {
        "b": {"entity": "BBB", "baseline_probability": 0.8,
              "public_query_ids": ["shared", "qb"]},
        "a": {"entity": "AAA", "baseline_probability": 0.2,
              "public_query_ids": ["shared", "qa"]},
        "c": {"entity": "CCC", "baseline_probability": 0.4,
              "public_query_ids": ["qc"]},
    }


def rank(kind, target="a", query="qa", tick=0, acquired=0, available_at=1, common=None):
    return query_priority(kind, seed=13, tick=tick, acquired=acquired,
                          target_id=target, query_id=query,
                          common=public() if common is None else common,
                          available_at=available_at)


def test_round_robin_cycles_entities_and_each_successful_acquisition():
    winners = []
    for tick, acquired in [(0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (0, 3)]:
        winners.append(min(public(), key=lambda t: rank(
            "round_robin_cycle.v1", t, "q"+t, tick, acquired)))
    assert winners == ["a", "b", "c", "b", "c", "a"]


def test_public_risk_sums_served_targets_before_publication_recency():
    kind = "public_risk_age.v1"
    assert rank(kind, query="shared", available_at=1) < rank(kind, "b", "qb", available_at=99)
    assert rank(kind, "b", "qb", available_at=1) < rank(kind, "c", "qc", available_at=99)
    assert rank(kind, available_at=2) < rank(kind, available_at=1)


def test_fixed_hash_is_independent_of_risk_time_target_and_iteration_order():
    altered = dict(reversed(list(public().items())))
    for row in altered.values():
        row["baseline_probability"] = 0.99
    assert rank("fixed_hash.v1") == rank(
        "fixed_hash.v1", "b", tick=9, acquired=8, available_at=88, common=altered)
    assert rank("fixed_hash.v1", query="qa") != rank("fixed_hash.v1", query="qb")


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_priority_does_not_access_private_or_returned_values(kind):
    class PublicOnly(dict):
        def __getitem__(self, key):
            assert key in {"entity", "baseline_probability", "public_query_ids"}
            return super().__getitem__(key)
    clean = public()
    guarded = {t: PublicOnly(row, returned_value=object(), outcome=object()) for t, row in clean.items()}
    assert rank(kind, common=guarded) == rank(kind, common=clean)


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_new_selectors_require_program_and_fixed_slots(kind):
    data, bank, config = scheduled(selector_kind=kind)
    config.pop("forecast_schedule")
    with pytest.raises(ValueError, match="fixed program forecast"):
        run_session(data, bank, config)


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_actual_controller_preserves_schedule_denominator_and_restore(kind):
    data, bank, config = scheduled(selector_kind=kind, authorization_mode="session_shared")
    report = run_session(data, bank, config)
    assert [(c["opportunity_id"], c["started_at"]) for c in report["calls"]] == expected_schedule(data, config)
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert report["resource_spent"]["requests"] <= config["request_budget"]
    assert all(v == 0 for v in report["resource_reserved"].values())
    coordinator = SessionCoordinator(data, bank, config)
    coordinator.step()
    assert SessionCoordinator.restore(coordinator.snapshot(), data, bank).finish() == report


@pytest.mark.parametrize("kind", sorted(KINDS))
@pytest.mark.parametrize("condition", ["zero_budget", "late", "not_yet_public"])
def test_unavailable_queries_do_not_erase_forecast_opportunities(kind, condition):
    data, bank, config = scheduled(selector_kind=kind)
    data = copy.deepcopy(data)
    if condition == "zero_budget":
        config["request_budget"] = 0
    else:
        for row in data["query_catalog"]:
            row["latency_ms" if condition == "late" else "available_at"] = 10**18
    report = run_session(data, bank, config)
    assert not report["source_receipts"]
    assert [(c["opportunity_id"], c["started_at"]) for c in report["calls"]] == expected_schedule(data, config)
    assert len(report["snapshots"]) == len(data["opportunities"])


def test_unknown_version_is_rejected():
    with pytest.raises(ValueError, match="public query selector"):
        rank("fixed_hash.v99")
