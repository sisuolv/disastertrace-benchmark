import pytest

from disastertrace.monitoring_v1.resources import BudgetLedger, Cost
from disastertrace.monitoring_v1.scoring import brier_report, generic_missing_gain_bounds
from disastertrace.monitoring_v1.state import Baseline, Event, MonitoringEngine
from disastertrace.monitoring_v1.targets import Opportunity, TargetSpec
from disastertrace.monitoring_v1.views import EvidenceStore, selector_view


def target(ident="A", **kwargs):
    return TargetSpec(
        target_id=ident,
        entity=ident,
        variable="visibility",
        units="m",
        event_operator="lt",
        threshold=1000,
        spatial_support="station:" + ident,
        physical_start=100,
        physical_end=110,
        report_policy="routine.v1",
        outcome_kind="native_report",
        temporal_semantics="future_physical",
        **kwargs,
    )


def base(t=None, *, revision="r1", content=None, p=0.2, released=0, until=90, calibrator="cal.v1"):
    return Baseline(
        target=t or target(),
        product_revision_id=revision,
        relevant_content={"members": [0, 0, 100, 100]} if content is None else content,
        probability=p,
        released_at=released,
        valid_until=until,
        calibrator_version=calibrator,
        source_id="official",
    )


def engine(protocol="base_bound_override", cutoffs=(12, 15)):
    return MonitoringEngine(
        [Opportunity("o" + str(c), target(), c) for c in cutoffs],
        fallback_probabilities={"A": 0.1},
        protocol=protocol,
    )


def events_for_candidate(*, new_base=None, complete=11, expires=15):
    events = [
        Event("base1", 0, "baseline", {"baseline": base()}),
        Event("begin1", 5, "begin", {"call_id": "c", "target_id": "A"}),
        Event(
            "finish1",
            complete,
            "candidate",
            {"call_id": "c", "probability": 0.9, "expires_at": expires, "raw": "model raw output"},
        ),
    ]
    if new_base is not None:
        events.append(Event("base2", 10, "baseline", {"baseline": new_base}))
    return events


def test_relevant_distribution_hash_is_not_mean_or_transport_hash():
    assert base().context_hash != base(content={"members": [49, 49, 51, 51]}).context_hash
    assert base().context_hash == base(revision="mirror-rewrap").context_hash
    assert base().context_hash != base(calibrator="cal.v2").context_hash


def test_baseline_freezes_caller_owned_content():
    content = {"members": [1, 2]}
    baseline = base(content=content)
    original = baseline.context_hash
    content["members"][0] = 100
    assert baseline.context_hash == original
    assert baseline.policy_view()["relevant_content"]["members"] == [1, 2]


def test_stale_candidate_fixed_trace_separates_wrappers():
    events = events_for_candidate(new_base=base(revision="r2", p=0.1, released=10))
    bound, persistent = engine(), engine("persistent_override")
    bound.run(events)
    persistent.run(events)
    assert bound.snapshots["o12"]["probability"] == 0.1
    assert persistent.snapshots["o12"]["probability"] == 0.9
    assert bound.attempts[0]["status"] == "expired_base_context"
    assert bound.attempts[0]["raw"] == "model raw output"
    assert persistent.attempts[0]["status"] == "accepted"


def test_same_content_reissue_does_not_invalidate_override():
    runtime = engine()
    runtime.run(events_for_candidate(new_base=base(revision="mirror", released=10)))
    assert runtime.snapshots["o12"]["probability"] == 0.9


def test_withdrawn_professional_product_cannot_silently_resurrect_older_baseline():
    events = events_for_candidate()
    events.append(
        Event(
            "withdraw",
            10,
            "baseline_withdrawal",
            {
                "target_id": "A",
                "product_revision_id": "r2-CNL",
                "reason": "canceled",
            },
        )
    )
    bound, persistent = engine(), engine("persistent_override")
    bound.run(events)
    persistent.run(events)
    assert bound.snapshots["o12"]["probability"] == 0.1
    assert bound.snapshots["o12"]["baseline_kind"] == "fallback"
    assert bound.attempts[0]["status"] == "expired_base_context"
    assert persistent.snapshots["o12"]["probability"] == 0.9
    assert any(r["kind"] == "baseline_withdrawn" for r in bound.audit)
    restored = MonitoringEngine.restore(bound.export())
    assert restored.snapshots == bound.snapshots


def test_new_legal_product_reinstates_baseline_after_withdrawal():
    runtime = engine()
    runtime.run(
        [
            Event("base1", 0, "baseline", {"baseline": base()}),
            Event(
                "withdraw",
                8,
                "baseline_withdrawal",
                {
                    "target_id": "A",
                    "product_revision_id": "r2-NIL",
                    "reason": "nil",
                },
            ),
            Event("base3", 14, "baseline", {"baseline": base(revision="r3", released=14, p=0.3)}),
        ]
    )
    assert runtime.snapshots["o12"]["probability"] == 0.1
    assert runtime.snapshots["o15"]["probability"] == 0.3


def test_empty_clock_advance_still_forbids_later_backdating():
    runtime = engine()
    runtime.run([], until=9)
    with pytest.raises(ValueError, match="backdated"):
        runtime.run([Event("late-insertion", 8, "baseline", {"baseline": base(released=8)})])


def test_baseline_expires_to_frozen_fallback_without_new_release():
    runtime = engine(cutoffs=(12, 15))
    runtime.run([Event("b", 0, "baseline", {"baseline": base(until=12)})])
    assert runtime.snapshots["o12"]["probability"] == 0.2
    assert runtime.snapshots["o15"]["probability"] == 0.1
    assert runtime.snapshots["o15"]["baseline_kind"] == "fallback"


def test_first_opportunity_does_not_close_target():
    runtime = engine()
    runtime.run(events_for_candidate(complete=14))
    assert runtime.snapshots["o12"]["probability"] == 0.2
    assert runtime.snapshots["o15"]["probability"] == 0.9


def test_durable_completion_at_cutoff_precedes_snapshot():
    runtime = engine()
    runtime.run(events_for_candidate(complete=12, expires=12))
    assert runtime.snapshots["o12"]["probability"] == 0.9
    assert runtime.snapshots["o15"]["probability"] == 0.2


def test_release_at_cutoff_precedes_inflight_completion():
    runtime = engine()
    events = events_for_candidate(complete=12)
    events.append(
        Event("new", 12, "baseline", {"baseline": base(revision="new", p=0.3, released=12)})
    )
    runtime.run(list(reversed(events)))
    assert runtime.snapshots["o12"]["probability"] == 0.3
    assert runtime.attempts[0]["status"] == "expired_base_context"


def test_missing_begin_and_late_results_are_retained_but_never_backdated():
    runtime = engine()
    runtime.run(
        [
            Event(
                "unknown",
                11,
                "candidate",
                {"call_id": "unknown", "probability": 0.8, "expires_at": 15},
            )
        ]
    )
    assert runtime.attempts[0]["status"] == "missing_begin"
    assert len(runtime.snapshots) == 2
    late = engine()
    late.run(events_for_candidate(complete=16, expires=20))
    assert late.attempts[0]["status"] == "late"
    assert late.snapshots["o15"]["probability"] == 0.2


def test_follow_changes_prediction_without_erasing_action():
    runtime = engine()
    events = events_for_candidate()
    events += [
        Event("d", 6, "action", {"target_id": "A", "action_id": "warn", "expires_at": 50}),
        Event("nochange", 13, "no_change", {"target_id": "A"}),
        Event("follow", 14, "follow", {"target_id": "A"}),
    ]
    runtime.run(events)
    assert runtime.snapshots["o12"]["probability"] == 0.9
    assert runtime.snapshots["o15"]["probability"] == 0.2
    assert "warn" in runtime.actions


def test_event_replay_is_idempotent_and_restore_reconstructs_snapshots():
    runtime = engine()
    events = events_for_candidate()
    runtime.run(events + events)
    assert len(runtime.attempts) == 1
    restored = MonitoringEngine.restore(runtime.export())
    assert restored.snapshots == runtime.snapshots
    assert restored.attempts == runtime.attempts
    with pytest.raises(ValueError):
        runtime.run([Event("backdated", 1, "follow", {"target_id": "A"})])


def test_nan_model_output_keeps_all_opportunities():
    runtime = engine()
    events = events_for_candidate()
    events[-1].payload["probability"] = float("nan")
    runtime.run(events)
    assert runtime.attempts[0]["status"] == "invalid_probability"
    assert len(runtime.snapshots) == 2


def test_reservation_includes_inflight_and_actual_failure_cost():
    ledger = BudgetLedger({"requests": 2, "bytes": 100})
    ledger.reserve("r1", Cost(requests=1, bytes=80), "A")
    with pytest.raises(ValueError):
        ledger.reserve("r2", Cost(requests=1, bytes=30), "B")
    ledger.settle("r1", Cost(requests=1, bytes=50), outcome="failed")
    assert ledger.spent == Cost(requests=1, bytes=50)
    ledger.reserve("r2", Cost(requests=1, bytes=50), "B")
    assert ledger.spent + ledger.reserved == Cost(requests=2, bytes=100)


def test_settlement_overrun_does_not_release_reserved_budget():
    ledger = BudgetLedger({"tokens": 10})
    ledger.reserve("call", Cost(tokens=10), "A")
    with pytest.raises(ValueError):
        ledger.settle("call", Cost(tokens=11))
    assert ledger.reserved.tokens == 10 and ledger.spent.tokens == 0


def test_fixed_quotas_use_declared_initiator_pays_rule():
    ledger = BudgetLedger(
        {"requests": 2},
        allocation_mode="fixed_quota",
        quotas={"A": {"requests": 1}, "B": {"requests": 1}},
    )
    with pytest.raises(ValueError):
        ledger.reserve("shared", Cost(requests=2), "A")
    ledger.reserve("shared", Cost(requests=1), "A")
    assert not ledger.reserve("shared", Cost(requests=1), "A")
    with pytest.raises(ValueError):
        ledger.reserve("shared", Cost(requests=1), "B")


def test_private_values_do_not_reach_global_selector_or_other_target_view():
    store = EvidenceStore("target_private", ("A", "B"))
    store.register("private", {"secret_bit": 1}, owner="A", receipt_id="r1")
    assert not store.view("B")
    assert store.view("A")[0]["content"]["secret_bit"] == 1
    common = {
        "A": {"baseline_probability": 0.3, "deadline": 10, "private_summary": "one"},
        "B": {"baseline_probability": 0.2, "deadline": 10},
    }
    first = selector_view(common)
    common["A"]["private_summary"] = "zero"
    assert selector_view(common) == first
    assert "private_summary" not in first["A"]


def test_derived_assets_inherit_intersection_of_parent_entitlements():
    private = EvidenceStore("target_private", ("A", "B"))
    private.register("a", {"value": 1}, owner="A", receipt_id="ra")
    private.register("b", {"value": 2}, owner="B", receipt_id="rb")
    private.derive("ab", {"mean": 1.5}, ("a", "b"))
    assert all(row["asset_id"] != "ab" for row in private.view("A") + private.view("B"))
    shared = EvidenceStore("session_shared", ("A", "B"))
    shared.register("q", {"value": 1}, owner="A", receipt_id="rq")
    assert shared.view("A") == shared.view("B")


def test_common_mask_missingness_bounds_do_not_assert_population_gain():
    lower, upper = generic_missing_gain_bounds(0.9, 0.01)
    assert lower == pytest.approx(-0.091)
    assert upper == pytest.approx(0.109)
    rows = [
        {"opportunity_id": "a", "base": 0.2, "prediction": 0.4, "outcome": 1},
        {"opportunity_id": "b", "base": 0.2, "prediction": 0.4, "outcome": None},
    ]
    report = brier_report(rows)
    assert report["opportunities"] == 2 and report["settled"] == 1
    assert report["net_realized_gain"] == pytest.approx(0.28)
    assert report["full_population_gain_bounds"] == pytest.approx([0.08, 0.28])
    assert report["g_plus"] - report["g_minus"] == pytest.approx(report["net_realized_gain"])
