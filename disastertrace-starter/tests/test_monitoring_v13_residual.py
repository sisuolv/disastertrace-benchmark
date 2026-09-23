"""New acquisition intent respects existing requests and payer-scoped entitlement."""

import copy

import pytest
from test_monitoring_native_feature_session import setup
from test_monitoring_residual_query_plan import parent

from disastertrace.monitoring_v1.residual_query_plan import freeze_residual_plan, validate_residual_plan
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.targets import canonical_hash


@pytest.mark.parametrize("rule", ["none", "first_new", "second_new", "all_new"])
def test_v2_intents_execute_through_inherited_controller(rule):
    data, bank, checkpoint, opportunity = parent()
    plan = freeze_residual_plan(data, checkpoint, opportunity["opportunity_id"], rule,
                                version="disastertrace.residual_query_plan.v2")
    branch = SessionCoordinator.restore(checkpoint, data, bank)
    branch.step({"residual_query_plan":plan})
    report = branch.finish()
    n = len(checkpoint["payload"]["controller"]["source_receipts"])
    assert [r["query_id"] for r in report["source_receipts"][n:]] == plan["planned_query_order"]
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert report["actual_model_calls"] == 0
    validate_residual_plan(data, checkpoint, plan)


def shared_parent(scope):
    data, bank, config = setup(authorization_mode=scope, request_budget=10)
    # Reuse the prior paid slot in the next registered target's evidence contract.
    first, last = sorted({o["cutoff"] for o in data["opportunities"]})[:2]
    target = next(o for o in data["opportunities"] if o["cutoff"] == last)
    old = next(p for p in data["e_f_pairs"] if next(o for o in data["opportunities"]
               if o["opportunity_id"] == p["opportunity_id"])["cutoff"] == first)
    pair = next(p for p in data["e_f_pairs"] if p["opportunity_id"] == target["opportunity_id"])
    pair["query_ids"] = list(dict.fromkeys(old["query_ids"] + pair["query_ids"]))
    session = SessionCoordinator(data, bank, config)
    session.step()
    return data, bank, session.snapshot(), target


@pytest.mark.parametrize("scope", ["session_shared","target_private"])
def test_real_previous_cache_obeys_scope(scope):
    data, bank, checkpoint, target = shared_parent(scope)
    plan = freeze_residual_plan(data, checkpoint, target["opportunity_id"], "all_new",
                                version="disastertrace.residual_query_plan.v2")
    cached = [r for r in plan["catalog_inventory"] if r["related"] and r["already_cached"]]
    if scope == "session_shared":
        assert cached
        assert not set(r["catalog"]["query_id"] for r in cached) & set(plan["planned_query_order"])
    else:
        assert not cached
        assert all(a["asset_id"].startswith(target["target_id"]+"::") is False
                   for a in checkpoint["payload"]["store"]["assets"])
    branch = SessionCoordinator.restore(checkpoint, data, bank)
    branch.step({"residual_query_plan":plan})
    assert branch.report["frames"][-1]["residual_query_plan"]["planned_query_order"] == plan["planned_query_order"]


@pytest.mark.parametrize("outcome", ["execution_unknown", "reserved", "failed_not_sent"])
def test_requested_slots_are_excluded_even_when_not_cached(outcome):
    data, _, checkpoint, target = parent()
    initial = freeze_residual_plan(data, checkpoint, target["opportunity_id"], "all")
    qid = initial["eligible_query_order"][0]
    from disastertrace.monitoring_v1.policies import stable_rank
    p = checkpoint["payload"]
    p["ledger"]["events"].append({"event":"reserve", "receipt_id":"query-"+stable_rank(qid)})
    if outcome != "reserved":
        p["ledger"]["events"].append({"event":outcome, "receipt_id":"query-"+stable_rank(qid)})
    checkpoint["sha256"] = canonical_hash(p)
    plan = freeze_residual_plan(data, checkpoint, target["opportunity_id"], "first_new",
                                version="disastertrace.residual_query_plan.v2")
    assert qid not in plan["remaining_new_query_order"]
    assert "already_requested_no_automatic_retry" in next(r for r in plan["catalog_inventory"]
            if r["catalog"]["query_id"] == qid)["exclusion_reasons"]


def test_v2_parent_binding_and_empty_second():
    data, _, checkpoint, target = parent()
    for r in data["query_catalog"]: r["available_at"] = target["cutoff"] + 1
    checkpoint["payload"]["data_sha256"] = canonical_hash(data)
    checkpoint["sha256"] = canonical_hash(checkpoint["payload"])
    plan = freeze_residual_plan(data, checkpoint, target["opportunity_id"], "second_new",
                                version="disastertrace.residual_query_plan.v2")
    assert plan["empty_reason"] == "no_second_new_query" and not plan["planned_query_order"]
    wrong = copy.deepcopy(checkpoint); wrong["payload"]["clock"] += 1
    with pytest.raises(ValueError): validate_residual_plan(data, wrong, plan)
