"""Exact finite actions must reach the real query consumer with inherited costs."""

import copy

import pytest
from test_monitoring_native_feature_session import setup

from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator


def parent():
    data, bank, config = setup(authorization_mode="session_shared")
    session = SessionCoordinator(data, bank, config)
    session.step()
    checkpoint = session.snapshot()
    cutoff = sorted({o["cutoff"] for o in data["opportunities"]})[checkpoint["payload"]["next_tick"]]
    opportunity = next(o for o in data["opportunities"] if o["cutoff"] == cutoff)
    return data, bank, checkpoint, opportunity


@pytest.mark.parametrize("rule", ["no_further_paid_query", "first", "second", "all"])
def test_finite_query_plan_executes_exact_ids_and_keeps_forecasts(rule):
    from disastertrace.monitoring_v1.residual_query_plan import freeze_residual_plan

    data, bank, checkpoint, opportunity = parent()
    before = copy.deepcopy(checkpoint)
    plan = freeze_residual_plan(data, checkpoint, opportunity["opportunity_id"], rule)
    branch = SessionCoordinator.restore(checkpoint, data, bank)
    branch.step({"residual_query_plan": plan})
    result = branch.finish()
    prefix_n = len(checkpoint["payload"]["controller"]["source_receipts"])
    executed = [r["query_id"] for r in result["source_receipts"][prefix_n:]]
    assert executed == plan["planned_query_order"]
    assert len(result["snapshots"]) == len(data["opportunities"])
    assert result["resource_spent"]["requests"] == checkpoint["payload"]["ledger"]["spent"]["requests"] + len(executed)
    trace = next(f["residual_query_plan"] for f in result["frames"] if "residual_query_plan" in f)
    assert trace["planned_query_order"] == plan["planned_query_order"]
    assert trace["executed_query_order"] == executed
    assert result["actual_model_calls"] == 0
    assert checkpoint == before


def test_plan_cannot_smuggle_unknown_query_payer_or_payload():
    from disastertrace.monitoring_v1.residual_query_plan import freeze_residual_plan

    data, bank, checkpoint, opportunity = parent()
    plan = freeze_residual_plan(data, checkpoint, opportunity["opportunity_id"], "first")
    for field, value in [("planned_query_order", ["hidden-unregistered-query"]),
                         ("payer_target", "wrong-target"), ("future_outcome", 1)]:
        changed = {**plan, field: value}
        branch = SessionCoordinator.restore(checkpoint, data, bank)
        with pytest.raises(ValueError):
            branch.step({"residual_query_plan": changed})


def test_no_query_is_a_treatment_not_original_policy_continuation():
    from disastertrace.monitoring_v1.residual_query_plan import freeze_residual_plan

    data, bank, checkpoint, opportunity = parent()
    original = SessionCoordinator.restore(checkpoint, data, bank).finish()
    plan = freeze_residual_plan(data, checkpoint, opportunity["opportunity_id"], "no_further_paid_query")
    branch = SessionCoordinator.restore(checkpoint, data, bank)
    branch.step({"residual_query_plan": plan})
    stopped = branch.finish()
    assert stopped["resource_spent"]["requests"] < original["resource_spent"]["requests"]
    assert [s["opportunity_id"] for s in stopped["snapshots"]] == [s["opportunity_id"] for s in original["snapshots"]]


def test_query_plan_is_a_registered_intervention_without_relaxing_other_keys():
    from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
    from disastertrace.monitoring_v1.residual_query_plan import freeze_residual_plan

    data, _, checkpoint, opportunity = parent()
    plan = freeze_residual_plan(data, checkpoint, opportunity["opportunity_id"], "first")
    base = {"other": "invariant"}
    comparison = ComparisonContract(base, {"selector_kind": ["coverage"], "residual_query_plan": [None, plan]})
    comparison.validate(base, {"selector_kind": "coverage"})
    comparison.validate(base, {"selector_kind": "coverage", "residual_query_plan": plan})
    with pytest.raises(ValueError):
        comparison.validate(base, {"residual_query_plan": plan})


def test_finite_plan_retains_unexecuted_tail_and_cannot_be_replaced():
    from disastertrace.monitoring_v1.residual_query_plan import freeze_residual_plan

    data, bank, checkpoint, opportunity = parent()
    plan = freeze_residual_plan(data, checkpoint, opportunity["opportunity_id"], "all")
    branch = SessionCoordinator.restore(checkpoint, data, bank)
    branch.step({"residual_query_plan": plan, "query_limit_per_tick": 0})
    trace = branch.report["frames"][-1]["residual_query_plan"]
    assert not trace["executed_query_order"]
    assert [d["query_id"] for d in trace["dispositions"]] == plan["planned_query_order"]
    assert trace["dispositions"][0]["status"] == "query_limit_reached"
    with pytest.raises(ValueError, match="replaced"):
        branch.step({"residual_query_plan": None})
